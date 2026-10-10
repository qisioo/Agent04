""" agents/product_manager.py 产品经理Agent节点 位置：被项目经理调度执行，负责根据标准化需求输出PRD产品需求文档 职责：
1.读取state["refined_requirement"]已经梳理好的开发需求
2.调用大模型生成完整PRD文档：功能描述、输入输出、约束条件、使用场景
3.仅写入state["product_prd"]、state["step_log"]，不触碰其他状态字段
4.执行完毕返回，流转回到项目经理节点进行下一步任务分发
"""
from state import SoftwareDevState
from utils.llm_client import safe_llm_invoke_sync
from utils.logger import logger


def product_manager_node(state: SoftwareDevState) -> dict:
    """
    产品经理LangGraph Node函数
    :param state: 全局共享SoftwareDevState
    :return: 更新后的state字典
    """
    refined_req = state.refined_requirement
    logger.info(f"产品经理Agent开始工作，接收需求：{refined_req[:100]}...")

    prd_prompt = f"""
你是一名资深软件产品经理，根据下面用户开发需求，输出一份规范简洁的PRD产品需求文档。
用户开发需求：
{refined_req}

PRD文档需要包含：
1.项目概述：这个工具/程序要解决什么问题
2.核心功能列表：逐条列出需要实现的功能
3.输入与输出说明
4.非功能约束：运行环境、边界、异常处理要求

直接输出PRD正文，不要多余开场白，不要对话。
"""
    llm_prd_result = safe_llm_invoke_sync(prd_prompt)

    if not llm_prd_result:
        err_msg = "产品经理：调用大模型生成PRD文档失败"
        logger.error(err_msg)
        return {
            "step_log": [err_msg],
            "error_messages": [err_msg]
        }

    success_log = "产品经理：PRD产品需求文档生成完成"
    logger.info(success_log)

    # ==========【新增：方案一摘要写入chat_history，不改动原有业务逻辑】==========
    summary_text = f"【产品经理完成PRD】需求摘要：{refined_req[:120]}；已产出PRD文档，包含项目概述、功能列表、输入输出、非功能约束。"
    new_chat_history = state.chat_history + [("assistant", summary_text)]
    # =========================================================================

    return {
        "product_prd": llm_prd_result,
        "step_log": [success_log],
        "chat_history": new_chat_history
    }
