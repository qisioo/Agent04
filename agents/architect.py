""" agents/architect.py 架构师Agent节点 位置：被项目经理调度执行，接收PRD需求文档输出系统架构方案与技术栈选型 职责：
1.读取state["product_prd"]产品需求文档
2.输出系统架构文档：模块划分、模块职责、数据流转逻辑
3.输出tech_stack_decision：确定本项目选用的python库、依赖、运行环境
4.仅写入 architecture_doc、tech_stack_decision、step_log、error_messages，不修改其他state字段
5.执行完毕返回state，流转回到项目经理节点继续分发任务
"""
from state import SoftwareDevState
from utils.llm_client import safe_llm_invoke_sync
from utils.logger import logger


def architect_node(state: SoftwareDevState) -> dict:
    """
    架构师LangGraph Node函数
    :param state: 全局共享SoftwareDevState
    :return: 更新后的state字典
    """
    prd_content = state.product_prd
    user_feedback = state.arch_review_feedback
    feedback_section = ""
    if user_feedback:
        logger.info(f"架构师：收到用户对架构的优化意见，据此调整架构：{user_feedback[:100]}")
        feedback_section = f"""

【用户对上次架构的优化意见，请据此调整架构方案】
{user_feedback}
"""
    logger.info(f"架构师Agent开始工作，读取PRD文档：{prd_content[:120]}...")

    arch_prompt = f"""
你是资深Python后端架构师，基于下面PRD需求文档输出架构设计方案与技术栈选型。
==== PRD需求文档 ====
{prd_content}
{feedback_section}

输出三部分内容：
# 一、系统架构设计
1.模块划分：拆分出程序内部各个功能模块，写明每个模块职责
2.模块之间数据如何流转调用
3.关键边界、异常处理设计

# 二、技术栈选型
明确写出需要使用的Python第三方库，不要引入过重的web框架，尽量使用轻量库；写明运行环境要求。

# 三、项目设计摘要
用3-5句话概括：本程序要解决什么问题、核心功能、模块划分概览、关键约束。供后续Agent（尤其修复循环）快速掌握项目全局，防止多轮迭代中丢失目标。

直接输出正文，不要多余寒暄对话。
"""
    llm_arch_result = safe_llm_invoke_sync(arch_prompt)
    if not llm_arch_result:
        err_msg = "架构师：调用大模型生成架构方案失败"
        logger.error(err_msg)
        return {
            "step_log": [err_msg],
            "error_messages": [err_msg],
            "arch_done": True
        }

    # 分离架构文档、技术栈、项目设计摘要三部分
    split_index = llm_arch_result.find("# 二、技术栈选型")
    brief_marker = "# 三、项目设计摘要"
    brief_pos = llm_arch_result.find(brief_marker)
    project_brief = ""
    if split_index != -1:
        arch_doc = llm_arch_result[:split_index].strip()
        if brief_pos != -1:
            tech_stack = llm_arch_result[split_index:brief_pos].strip()
            project_brief = llm_arch_result[brief_pos + len(brief_marker):].strip()
        else:
            tech_stack = llm_arch_result[split_index:].strip()
    else:
        arch_doc = llm_arch_result
        tech_stack = "未分离出独立技术栈内容，请参考架构文档"
    # 兜底：未生成项目摘要时，用PRD概述前300字
    if not project_brief:
        project_brief = (prd_content or "")[:300]

    success_log = "架构师：系统架构方案、技术栈选型、项目设计摘要生成完成"
    logger.info(success_log)

    # ==========【新增：方案一摘要写入chat_history，原有业务逻辑完全不变】==========
    summary_text = "【架构师完成架构设计】已完成模块划分、模块数据流转、边界异常处理设计；输出项目依赖库与运行环境技术栈选型。"
    new_chat_history = state.chat_history + [("assistant", summary_text)]
    # =========================================================================

    return {
        "architecture_doc": arch_doc,
        "tech_stack_decision": tech_stack,
        "project_brief": project_brief,
        # 架构师已消费用户意见并重新生成，清空意见标记
        "arch_review_feedback": None,
        "arch_done": True,
        "step_log": [success_log],
        "chat_history": new_chat_history
    }
