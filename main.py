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
from langgraph.graph import StateGraph, END
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
            "chat_history": state.chat_history + [("user", raw_input), ("assistant", f"系统异常：{err_msg}")],
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
            "chat_history": state.chat_history + [("user", raw_input), ("assistant", parse_err)],
            "step_log": [parse_err],
            "error_messages": [parse_err],
            "is_finished": True,
            "final_output": parse_err
        }

    is_dev_task = resp_json.get("is_dev_task", False)
    refined_req = resp_json.get("refined_requirement", "")

    # =========【修改点1：手动读取旧chat_history拼接，不再返回增量片段】=========
    new_chat = state.chat_history + [("user", raw_input)]
    update_dict = {
        "chat_history": new_chat,
        "step_log": []
    }

    if is_dev_task:
        step_msg = f"输入预处理：识别为软件开发任务，标准化需求：{refined_req[:80]}..."
        logger.info(step_msg)
        update_dict["intention"] = "software_dev"
        update_dict["refined_requirement"] = refined_req
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
    # chat_history格式 [(role,content)]，直接喂给llm
    ai_content = safe_llm_invoke_sync(state.chat_history)
    if not ai_content:
        ai_content = "抱歉，当前模型暂时无法给出回答。"

    # =========【修改点4：读取旧历史，拼接AI完整返回列表】=========
    full_new_chat = state.chat_history + [("assistant", ai_content)]
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
    graph_builder.add_edge("architect_node", "project_manager_node")
    graph_builder.add_edge("developer_node", "project_manager_node")
    graph_builder.add_edge("tester_node", "project_manager_node")

    # ✅挂载检查点，开启thread_id会话记忆
    return graph_builder.compile(
        checkpointer=get_checkpointer()
    )


# 预编译全局graph实例
app_graph = build_graph()


def run_agent_workflow(user_input: str, thread_id: str | None = None) -> tuple[SoftwareDevState, str]:
    """
    对外暴露调用入口函数
    :param user_input: 用户原始输入字符串
    :param thread_id: 用户可指定会话id；不传自动生成
    :return: (解析后的State实例, 实际使用的thread_id)
    """
    used_thread_id = resolve_thread_id(thread_id)
    cfg = build_graph_config(used_thread_id)

    # =========修复：区分全新会话 / 已有会话=========
    checkpointer = app_graph.checkpointer
    existing_checkpoint = next(checkpointer.list(cfg), None)

    if existing_checkpoint is None:
        # 全新会话：传入完整初始化state
        init_state = SoftwareDevState(
            raw_user_requirement=user_input
        )
        input_payload = init_state.model_dump()
    else:
        # 已有会话！！只传入需要更新的字段，绝对不要传入全套初始化，防止覆盖chat_history
        input_payload = {
            "raw_user_requirement": user_input
        }

    result_state_dict = app_graph.invoke(
        input_payload,
        config=cfg
    )
    result_state = SoftwareDevState(**result_state_dict)
    return result_state, used_thread_id



if __name__ == "__main__":
    # 仅模块加载校验，不执行业务测试；服务统一通过 uvicorn api:app 启动
    print("✅ main.py 模块加载完成，LangGraph图对象已就绪，请使用uvicorn启动api服务，Apifox调用接口")
