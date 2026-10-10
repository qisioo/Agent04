""" agents/developer.py 程序员Agent节点 位置：被项目经理调度执行；测试发现Bug时会再次调度本节点完成代码修复 职责：
1.读取PRD、架构文档、技术栈选型；存在旧代码+测试报告时，基于旧代码修复Bug
2.输出code_files列表，存放生成/修复后的代码文件
3.输出dev_notes记录开发备注
4.仅修改 code_files、dev_notes、step_log、error_messages，不改动其他Agent输出产物
5.执行完毕返回state，流转回到项目经理节点
"""
from state import SoftwareDevState
from utils.llm_client import safe_llm_invoke_sync
from utils.logger import logger


def developer_node(state: SoftwareDevState) -> dict:
    """
    程序员LangGraph Node函数
    :param state: 全局共享SoftwareDevState
    :return: 更新后的state字典
    """
    prd = state.product_prd
    arch_doc = state.architecture_doc
    tech_stack = state.tech_stack_decision
    old_code_list = state.code_files
    test_report = state.test_report
    # 判断模式：全新开发 / Bug修复模式
    is_fix_mode = len(old_code_list) > 0 and test_report is not None and ("bug" in test_report.lower() or "缺陷" in test_report.lower())

    if is_fix_mode:
        logger.info("程序员Agent进入Bug修复模式，读取旧代码与测试报告")
        old_code_text = ""
        for item in old_code_list:
            old_code_text += f"\n==== 文件 {item['file_name']} ====\n{item['content']}\n"

        dev_prompt = f"""
你是Python开发工程师。需要基于原有代码修复Bug。
【PRD需求】
{prd}

【架构方案】
{arch_doc}

【技术栈】
{tech_stack}

【原有全部代码】
{old_code_text}

【测试工程师Bug报告】
{test_report}

要求：
1.定位并且修复全部Bug，保持原有整体结构不变；
2.输出完整可运行的Python代码，不要片段；
3.返回结果格式JSON，key为 file_name 和 content；
{{
  "file_name":"main.py",
  "content":"完整的python代码字符串"
}}
只返回JSON，不要其他解释文本。
"""
    else:
        logger.info("程序员Agent全新开发模式，根据PRD与架构编写代码")
        dev_prompt = f"""
你是Python开发工程师，根据PRD、架构文档、技术栈，输出完整可运行Python程序。
【PRD需求】
{prd}

【架构方案】
{arch_doc}

【技术栈选型】
{tech_stack}

要求：
1.代码完整可直接运行，增加必要注释，处理异常；
2.输出JSON格式，key为 file_name 和 content；
{{
  "file_name":"main.py",
  "content":"完整python代码写在这里"
}}
只返回JSON，不要多余对话、不要markdown包裹。
"""

    llm_dev_result = safe_llm_invoke_sync(dev_prompt)
    if not llm_dev_result:
        err_msg = "程序员：调用大模型生成/修复代码失败"
        logger.error(err_msg)
        return {
            "step_log": [err_msg],
            "error_messages": [err_msg]
        }

    import json
    try:
        code_json = json.loads(llm_dev_result)
    except json.JSONDecodeError:
        parse_err = f"程序员：代码JSON解析失败，原始返回：{llm_dev_result[:200]}"
        logger.error(parse_err)
        return {
            "step_log": [parse_err],
            "error_messages": [parse_err]
        }

    new_file_name = code_json.get("file_name", "main.py")
    new_content = code_json.get("content", "")
    new_code_item = {"file_name": new_file_name, "content": new_content}

    if is_fix_mode:
        log_msg = f"程序员：Bug修复完成，输出修复后代码文件 {new_file_name}"
        dev_note = "基于测试报告完成代码缺陷修复"
        summary_text = f"【程序员完成Bug修复】针对测试报告缺陷完成修复，输出文件：{new_file_name}。完整代码保存在code_files。"
    else:
        log_msg = f"程序员：全新开发完成，输出代码文件 {new_file_name}"
        dev_note = "按照PRD与架构完成初始版本代码开发"
        summary_text = f"【程序员完成编码】全新开发输出代码文件：{new_file_name}，完整代码保存在code_files。"

    logger.info(log_msg)

    # ==========【新增：方案一摘要写入chat_history】==========
    new_chat_history = state.chat_history + [("assistant", summary_text)]
    # ========================================================

    return {
        "code_files": [new_code_item],
        "dev_notes": [dev_note],
        "step_log": [log_msg],
        "chat_history": new_chat_history
    }
