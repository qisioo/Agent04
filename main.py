""" main.py 项目根目录 项目程序入口，LangGraph图定义、运行入口
包含：【输入优化校验预处理节点】graph第一个node、完整StateGraph组装、对外运行入口、自测代码
职责：
1. input_optimize_node：输入预处理节点，Graph首个执行节点
    - 解析用户输入，写入chat_history，识别意图intention：chat普通对话 / software_dev软件开发任务
2. simple_chat_node：普通闲聊应答节点，读取完整chat_history生成回答，写入chat_history后结束流程
3. build_graph()：构建完整多Agent软件开发团队StateGraph实例
4. run_agent_workflow(user_input)：对外调用入口，传入用户字符串，返回最终带标记的输出结果 + 实际thread_id
5. 自测main块，用于快速调试
依赖：state、config、utils工具、全部agents模块
"""
from state import SoftwareDevState
from utils.llm_client import safe_llm_invoke_sync
from utils.logger import logger
from utils.checkpoint_manager import get_checkpointer, build_graph_config, resolve_thread_id
from utils.context_manager import trim_chat_history
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.errors import GraphInterrupt
from agents.project_manager import project_manager_node, route_by_project_manager
from agents.product_manager import product_manager_node
from agents.architect import architect_node
from agents.developer import developer_node
from agents.tester import tester_node
import json


def input_optimize_node(state: SoftwareDevState) -> dict:
    """
    输入优化&意图校验预处理节点
    【Graph第一个执行节点】
    不再直接生成回答；只做两件事：
    1. 将本轮用户消息追加写入chat_history（手动拼接旧历史，方案二）
    2. 识别意图，输出intention标记：chat / software_dev
    :param state: Pydantic SoftwareDevState模型实例
    :return: 更新增量字典，LangGraph自动合并状态
    """
    raw_input = state.raw_user_requirement
    logger.info(f"输入预处理节点收到用户原始输入：{raw_input}")

    intent_prompt = f"""
你是输入意图校验处理器。
用户原始输入：{raw_input}

规则：
任务A：判断用户输入是否属于【软件开发相关需求】。
软件开发需求包括：写Python代码、开发工具、做接口、写项目、写测试用例、设计系统等。
非软件开发：闲聊、问答、生活、科普、普通聊天对话等。

输出严格JSON格式，**不要额外解释，不要markdown**：
{{
  "is_dev_task":true/false,
  "refined_requirement":"is_dev_task=true时输出标准化开发需求；false输出空字符串"
}}
"""
    llm_result = safe_llm_invoke_sync(intent_prompt)
    if not llm_result:
        err_msg = "输入预处理调用大模型失败"
        logger.error(err_msg)
        # 异常：读取旧历史，拼接user+assistant错误提示
        return {
            "chat_history": trim_chat_history(state.chat_history + [("user", raw_input), ("assistant", f"系统异常：{err_msg}")]),
            "step_log": [err_msg],
            "error_messages": [err_msg],
            "is_finished": True,
            "final_output": f"系统异常：{err_msg}"
        }

    try:
        resp_json = json.loads(llm_result)
    except json.JSONDecodeError:
        parse_err = "输入预处理：大模型返回JSON解析失败"
        logger.error(parse_err)
        # 异常：读取旧历史，拼接user+assistant错误提示
        return {
            "chat_history": trim_chat_history(state.chat_history + [("user", raw_input), ("assistant", parse_err)]),
            "step_log": [parse_err],
            "error_messages": [parse_err],
            "is_finished": True,
            "final_output": parse_err
        }

    is_dev_task = resp_json.get("is_dev_task", False)
    refined_req = resp_json.get("refined_requirement", "")

    # =========【修改点1：手动读取旧chat_history拼接（滑动窗口，防无限膨胀）】=========
    new_chat = trim_chat_history(state.chat_history + [("user", raw_input)])
    update_dict = {
        "chat_history": new_chat,
        "step_log": []
    }

    if is_dev_task:
        step_msg = f"输入预处理：识别为软件开发任务，标准化需求：{refined_req[:80]}..."
        logger.info(step_msg)
        update_dict["intention"] = "software_dev"
        update_dict["refined_requirement"] = refined_req
        # ✅新增：新的一轮开发指令到来时重置bug修复计数
        # 修复"fix_iteration跨对话累积"缺陷：三次锁死只作用于本次指令内部，不影响下一次对话继续开发
        update_dict["fix_iteration"] = 0
        update_dict["step_log"].append(step_msg)
    else:
        step_msg = "输入预处理：识别为普通对话，跳转闲聊应答节点"
        logger.info(step_msg)
        update_dict["intention"] = "chat"
        update_dict["refined_requirement"] = None
        update_dict["step_log"].append(step_msg)

    return update_dict


def simple_chat_node(state: SoftwareDevState) -> dict:
    """
    ✅新增：普通闲聊应答节点
    读取state完整chat_history（包含历史闲聊+agent产出）生成回答
    AI回答手动拼接进完整chat_history，结束graph流程
    """
    logger.info("进入闲聊应答节点，读取完整对话历史生成回答")
    # chat_history格式 [(role,content)]，滑动窗口截断后喂给llm，防token无限膨胀
    chat_for_llm = trim_chat_history(state.chat_history)
    ai_content = safe_llm_invoke_sync(chat_for_llm)
    if not ai_content:
        ai_content = "抱歉，当前模型暂时无法给出回答。"

    # =========【修改点4：读取旧历史，拼接AI完整返回列表（滑动窗口）】=========
    full_new_chat = trim_chat_history(state.chat_history + [("assistant", ai_content)])
    return {
        "chat_history": full_new_chat,
        "final_output": f"[LLM原生问答回复]\n{ai_content}",
        "is_finished": True
    }


def route_after_input_optimize(state: SoftwareDevState) -> str:
    """
    改造预处理后条件路由函数：依据intention分支
    intention == chat → simple_chat_node
    intention == software_dev → project_manager_node
    """
    if state.intention == "chat":
        return "simple_chat_node"
    elif state.intention == "software_dev":
        return "project_manager_node"
    else:
        # 异常兜底直接结束
        return END


def architecture_review_node(state: SoftwareDevState) -> dict:
    """
    架构评审中断节点（human-in-the-loop）
    架构师写完架构后暂停，把架构方案交给用户确认：
    - 首次执行到 interrupt() 会暂停图，返回架构方案给用户
    - resume 后读取用户输入：确认→进开发；提优化意见→回架构师重新生成
    """
    user_feedback = interrupt({
        "type": "architecture_review",
        "message": "架构师已完成架构设计与技术栈选型，请确认是否符合需求，或提出优化意见（回复\"继续\"即按此架构进入开发）",
        "architecture_doc": state.architecture_doc,
        "tech_stack": state.tech_stack_decision,
        "project_brief": state.project_brief,
    })
    fb = str(user_feedback or "").strip().lower().rstrip("。！!,. ")
    confirm_prefix = ("继续", "确认", "可以", "没问题", "同意", "通过", "好", "ok", "yes", "y", "就这个")
    is_confirm = fb == "" or fb.startswith(confirm_prefix)
    if is_confirm:
        # 用户确认架构 → 回到项目经理，继续进入开发
        return {
            "arch_review_feedback": None,
            "current_agent": "project_manager",
            "step_log": ["架构评审：用户确认架构，继续进入开发"]
        }
    # 用户提出优化意见 → 回架构师重新生成
    return {
        "arch_review_feedback": str(user_feedback).strip(),
        "current_agent": "architect",
        "step_log": [f"架构评审：用户提出优化意见，交回架构师调整。意见：{str(user_feedback).strip()[:120]}"]
    }


def route_after_arch_review(state: SoftwareDevState) -> str:
    """
    架构评审之后的条件路由
    用户确认 → project_manager_node（继续开发）
    用户提意见 → architect_node（重新生成架构）
    """
    agent_map = {
        "architect": "architect_node",
        "project_manager": "project_manager_node",
    }
    return agent_map.get(state.current_agent, END)


def build_graph() -> StateGraph:
    """
    构建完整多Agent软件开发团队图
    注册所有node、边、条件分支
    返回编译完成可执行graph实例（挂载checkpointer）
    """
    from langgraph.managed import IsLastStep

    graph_builder = StateGraph(
        SoftwareDevState,
        managed_fields={"is_last_step": IsLastStep()}
    )

    # =========注册所有节点=========
    graph_builder.add_node("input_optimize_node", input_optimize_node)
    graph_builder.add_node("simple_chat_node", simple_chat_node)  # 注册新增闲聊节点
    graph_builder.add_node("project_manager_node", project_manager_node)
    graph_builder.add_node("product_manager_node", product_manager_node)
    graph_builder.add_node("architect_node", architect_node)
    graph_builder.add_node("architecture_review_node", architecture_review_node)  # 架构评审中断节点
    graph_builder.add_node("developer_node", developer_node)
    graph_builder.add_node("tester_node", tester_node)

    # 设置图入口
    graph_builder.set_entry_point("input_optimize_node")

    # =========条件边：输入预处理之后，按意图路由=========
    graph_builder.add_conditional_edges(
        "input_optimize_node",
        route_after_input_optimize,
        {
            "simple_chat_node": "simple_chat_node",
            "project_manager_node": "project_manager_node",
            END: END
        }
    )

    # 闲聊节点执行完毕直接结束图
    graph_builder.add_edge("simple_chat_node", END)

    # =========条件边：项目经理调度各个业务Agent=========
    # =========条件边：项目经理调度各个业务Agent=========
    graph_builder.add_conditional_edges(
        "project_manager_node",
        route_by_project_manager,
        {
            "product_manager_node": "product_manager_node",
            "architect_node": "architect_node",
            "developer_node": "developer_node",
            "tester_node": "tester_node",
            None: END
        }
    )

    # =========所有业务Agent执行完成后，统一回到项目经理节点=========
    graph_builder.add_edge("product_manager_node", "project_manager_node")
    # 架构师写完后，先进入架构评审中断节点（等用户确认/提意见），不直接回项目经理
    graph_builder.add_edge("architect_node", "architecture_review_node")
    graph_builder.add_edge("developer_node", "project_manager_node")
    graph_builder.add_edge("tester_node", "project_manager_node")

    # =========架构评审中断后按用户反馈路由：确认→项目经理继续开发；提意见→回架构师=========
    graph_builder.add_conditional_edges(
        "architecture_review_node",
        route_after_arch_review,
        {
            "architect_node": "architect_node",
            "project_manager_node": "project_manager_node",
            END: END
        }
    )

    # ✅挂载检查点，开启thread_id会话记忆
    return graph_builder.compile(
        checkpointer=get_checkpointer()
    )


# 预编译全局graph实例
app_graph = build_graph()


def run_agent_workflow(user_input: str, thread_id: str | None = None, resume_value: str | None = None) -> dict:
    """
    对外暴露调用入口函数（支持human-in-the-loop中断/恢复）
    :param user_input: 用户原始输入字符串
    :param thread_id: 用户可指定会话id；不传自动生成
    :param resume_value: 架构评审确认/意见；中断后携带继续执行
    :return: dict
        - pending=True: 流程在架构评审处中断，等待用户确认（含架构方案）
        - pending=False: 流程正常结束，含 state 对象
    """
    used_thread_id = resolve_thread_id(thread_id)
    cfg = build_graph_config(used_thread_id)

    # =========体验优化：线程处于架构评审中断挂起时，用户的下一条输入自动作为恢复内容=========
    # 无需用户手动传resume，直接发"继续"或优化意见即可恢复中断
    if resume_value is None:
        try:
            snapshot = app_graph.get_state(cfg)
            tasks = getattr(snapshot, "tasks", None) or []
            has_pending_interrupt = any(getattr(t, "interrupts", None) for t in tasks)
            if has_pending_interrupt:
                resume_value = user_input
                logger.info("检测到线程处于架构评审中断挂起，自动将用户输入作为恢复内容")
        except Exception:
            pass  # 状态查询失败不影响正常流程
    # =====================================================================================

    try:
        if resume_value is not None:
            # 中断后恢复：把用户的确认/意见通过Command(resume=...)传回图
            result_state_dict = app_graph.invoke(Command(resume=resume_value), config=cfg)
        else:
            # =========区分全新会话 / 已有会话=========
            checkpointer = app_graph.checkpointer
            existing_checkpoint = next(checkpointer.list(cfg), None)
            if existing_checkpoint is None:
                init_state = SoftwareDevState(raw_user_requirement=user_input)
                input_payload = init_state.model_dump()
            else:
                input_payload = {"raw_user_requirement": user_input}
            result_state_dict = app_graph.invoke(input_payload, config=cfg)
    except GraphInterrupt as e:
        # 架构评审中断：返回pending状态，附架构方案，等待用户确认
        payload = {}
        if getattr(e, "interrupts", None):
            payload = e.interrupts[0].value or {}
        logger.info("流程在架构评审处中断，等待用户确认架构")
        return {
            "pending": True,
            "thread_id": used_thread_id,
            "message": payload.get("message", "架构待确认"),
            "architecture_doc": payload.get("architecture_doc"),
            "tech_stack": payload.get("tech_stack"),
            "project_brief": payload.get("project_brief"),
        }

    # langgraph 1.x：interrupt 不抛异常，而是返回结果dict里的 __interrupt__ 字段
    if isinstance(result_state_dict, dict) and result_state_dict.get("__interrupt__"):
        interrupts = result_state_dict["__interrupt__"]
        payload = interrupts[0].value if interrupts else {}
        logger.info("流程在架构评审处中断，等待用户确认架构")
        return {
            "pending": True,
            "thread_id": used_thread_id,
            "message": payload.get("message", "架构待确认"),
            "architecture_doc": payload.get("architecture_doc"),
            "tech_stack": payload.get("tech_stack"),
            "project_brief": payload.get("project_brief"),
        }

    result_state = SoftwareDevState(**result_state_dict)
    return {"pending": False, "state": result_state, "thread_id": used_thread_id}



if __name__ == "__main__":
    # 仅模块加载校验，不执行业务测试；服务统一通过 uvicorn api:app 启动
    print("✅ main.py 模块加载完成，LangGraph图对象已就绪，请使用uvicorn启动api服务，Apifox调用接口")
