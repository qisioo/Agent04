""" agents/tester.py 测试工程师Agent节点 位置：被项目经理调度执行，接收程序员产出的代码，完成代码审查与测试分析 职责：
1.读取PRD需求、架构文档、code_files代码列表
2.编写对应的测试用例，存入test_case_doc
3.【真实运行验证】在沙箱中真实运行代码，拿到运行结果作为测试事实依据
4.执行代码逻辑审查，查找功能缺失、异常漏洞、逻辑bug，生成test_report
5.报告中明确写明是否存在bug；存在bug则详细描述问题；无bug输出测试全部通过
6.仅修改 test_case_doc、test_report、step_log、error_messages，不改动其他state字段
7.执行完毕返回state，流转回到项目经理，由项目经理决定后续流程
"""
from state import SoftwareDevState
from utils.llm_client import safe_llm_invoke_sync
from utils.logger import logger
from utils.code_sandbox import run_python_code
from utils.context_manager import trim_chat_history, limit_text


def tester_node(state: SoftwareDevState) -> dict:
    """
    测试工程师LangGraph Node函数
    :param state: 全局共享SoftwareDevState
    :return: 更新后的state字典
    """
    prd = state.product_prd
    arch_doc = state.architecture_doc
    code_file_list = state.code_files
    logger.info(f"测试工程师Agent开始工作，收到{len(code_file_list)}份代码文件，开始真实运行验证与审查")

    code_all_text = ""
    run_evidence = ""   # 【新增】真实运行验证证据，作为测试事实依据
    for file in code_file_list:
        code_all_text += f"\n==== 文件：{file['file_name']} ====\n{file['content']}\n"
        # =========【新增：对每个文件做真实运行验证】=========
        logger.info(f"测试工程师：真实运行文件 {file['file_name']}")
        result = run_python_code(file["content"])
        run_evidence += (
            f"\n==== 文件 {file['file_name']} 真实运行结果 ====\n"
            f"运行是否成功: {result.success}\n"
            f"运行摘要: {result.summary}\n"
            f"标准输出: {(result.stdout or '').strip()[:800]}\n"
        )

    tester_prompt = f"""
你是资深Python测试工程师。
参照PRD需求文档、架构方案，对下面代码做测试分析与审查。

【PRD需求】
{limit_text(prd, 4000)}

【架构方案】
{limit_text(arch_doc, 3000)}

【待审查全部代码】
{code_all_text}

【⚠️真实运行验证结果（最高优先级事实依据，审查必须以此为准）】
{run_evidence}

审查规则：
1. 以【真实运行验证结果】为最高优先级事实：运行报错/超时=必然存在bug；运行成功也不代表无逻辑问题，要继续排查。
2. 真实运行报错时，必须把运行错误信息作为bug逐条写入测试报告。
3. 核对代码是否完整实现PRD全部功能；
4. 检查异常捕获、边界条件、潜在逻辑bug；
5. 仅当真实运行成功 且 逻辑审查无问题，才可写"无bug，全部功能测试通过"。

输出分为两大部分：
# 一、测试用例 test_case_doc
编写多条可执行测试用例，包含：测试场景、输入、预期输出。

# 二、测试报告 test_report
1. 真实运行验证结论：每个文件是否真实运行成功，报错/超时情况；
2. 核对代码是否完整实现PRD全部功能；
3. 检查异常捕获、边界条件、潜在逻辑bug；
4. 如果发现bug：逐条描述bug现象、触发条件、问题位置；
5. 如果没有bug：明确写"无bug，全部功能测试通过"。

【必须】在测试报告最末尾，单独一行输出测试结论标记（不要放在其他文字里）：
- 当真实运行成功 且 未发现任何bug时，输出：测试结论: 通过
- 当真实运行失败 或 发现任何bug时，输出：测试结论: 存在bug

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

    success_log = "测试工程师：真实运行验证、代码审查、测试用例、测试报告生成完成"
    logger.info(success_log)

    # ==========【新增：方案一摘要写入chat_history（滑动窗口，防无限膨胀）】==========
    summary_text = "【测试工程师完成测试】完成真实运行验证与代码审查，完整测试用例、报告保存在state对应字段。"
    new_chat_history = trim_chat_history(state.chat_history + [("assistant", summary_text)])
    # ================================================================================

    return {
        "test_case_doc": test_case_doc,
        "test_report": test_report,
        "step_log": [success_log],
        "chat_history": new_chat_history,
        "tested_code_version": state.code_version
    }
