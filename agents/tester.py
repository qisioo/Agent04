""" agents/tester.py 测试工程师Agent节点 位置：被项目经理调度执行，接收程序员产出的代码，完成代码审查与测试分析 职责：
1.读取PRD需求、架构文档、code_files代码列表
2.编写对应的测试用例，存入test_case_doc
3.执行代码逻辑审查，查找功能缺失、异常漏洞、逻辑bug，生成test_report
4.报告中明确写明是否存在bug；存在bug则详细描述问题；无bug输出测试全部通过
5.仅修改 test_case_doc、test_report、step_log、error_messages，不改动其他state字段
6.执行完毕返回state，流转回到项目经理，由项目经理决定后续流程
"""
from state import SoftwareDevState
from utils.llm_client import safe_llm_invoke_sync
from utils.logger import logger


def tester_node(state: SoftwareDevState) -> dict:
    """
    测试工程师LangGraph Node函数
    :param state: 全局共享SoftwareDevState
    :return: 更新后的state字典
    """
    prd = state.product_prd
    arch_doc = state.architecture_doc
    code_file_list = state.code_files
    logger.info(f"测试工程师Agent开始工作，收到{len(code_file_list)}份代码文件，开始审查")

    code_all_text = ""
    for file in code_file_list:
        code_all_text += f"\n==== 文件：{file['file_name']} ====\n{file['content']}\n"

    tester_prompt = f"""
你是资深Python测试工程师。
参照PRD需求文档、架构方案，对下面代码做完整代码审查与测试分析。

【PRD需求】
{prd}

【架构方案】
{arch_doc}

【待审查全部代码】
{code_all_text}

输出分为两大部分：
# 一、测试用例 test_case_doc
编写多条可执行测试用例，包含：测试场景、输入、预期输出。

# 二、测试报告 test_report
1.核对代码是否完整实现PRD全部功能；
2.检查异常捕获、边界条件、潜在逻辑bug；
3.如果发现bug：逐条描述bug现象、触发条件、问题位置；
4.如果没有bug：明确写"无bug，全部功能测试通过"。

直接输出正文，不要多余开场白。
"""
    llm_tester_result = safe_llm_invoke_sync(tester_prompt)

    if not llm_tester_result:
        err_msg = "测试工程师：调用大模型生成测试报告失败"
        logger.error(err_msg)
        return {
            "step_log": [err_msg],
            "error_messages": [err_msg]
        }

    # 分割测试用例和测试报告两部分
    split_marker = "# 二、测试报告 test_report"
    split_pos = llm_tester_result.find(split_marker)
    if split_pos != -1:
        test_case_doc = llm_tester_result[:split_pos].strip()
        test_report = llm_tester_result[split_pos + len(split_marker):].strip()
    else:
        test_case_doc = llm_tester_result
        test_report = "未能分离独立测试报告，请查看测试用例内容"

    success_log = "测试工程师：代码审查、测试用例、测试报告生成完成"
    logger.info(success_log)

    # ==========【新增：方案一摘要写入chat_history】==========
    summary_text = "【测试工程师完成测试审查】完成测试用例编写，对代码做功能核对、边界与逻辑Bug扫描；完整测试用例、报告保存在state对应字段。"
    new_chat_history = state.chat_history + [("assistant", summary_text)]
    # ========================================================

    return {
        "test_case_doc": test_case_doc,
        "test_report": test_report,
        "step_log": [success_log],
        "chat_history": new_chat_history
    }
