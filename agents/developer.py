""" agents/developer.py 程序员Agent节点 位置：被项目经理调度执行；测试发现Bug时会再次调度本节点完成代码修复 职责：
1.读取PRD、架构文档、技术栈选型；存在旧代码+测试报告时，基于旧代码修复Bug
2.输出code_files列表，存放生成/修复后的代码文件
3.输出dev_notes记录开发备注
4.仅修改 code_files、dev_notes、step_log、error_messages，不改动其他Agent输出产物
5.执行完毕返回state，流转回到项目经理节点
"""
import difflib
from state import SoftwareDevState
from utils.llm_client import safe_llm_invoke_sync
from utils.logger import logger
from utils.code_sandbox import run_python_code
from utils.context_manager import trim_chat_history, limit_text
from utils.code_inspect import extract_skeleton, find_bug_locations, extract_relevant_code

# 修复模式内部最大重试次数：修复后真实运行失败，反馈错误让LLM重修的次数
MAX_FIX_ATTEMPTS = 2


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

    new_file_name = "main.py"
    new_content = ""

    if is_fix_mode:
        logger.info("程序员Agent进入Bug修复模式，读取旧代码与测试报告")
        # =========【增量Diff：构建精简上下文，替代完整旧代码，省token】=========
        code_section_title = "【原有全部代码】"
        code_section = ""
        if old_code_list:
            old_code = old_code_list[0]["content"]
            skeleton = extract_skeleton(old_code)
            loc = find_bug_locations(old_code, test_report)
            relevant = extract_relevant_code(old_code, loc["funcs"], loc["lines"])
            if skeleton and relevant:
                code_section_title = "【代码信息（增量Diff精简上下文：结构骨架 + bug相关代码）】"
                code_section = (
                    f"【代码结构骨架（全文件结构预览，未展开函数体）】\n{skeleton}\n\n"
                    f"【bug相关代码（完整函数体+附近行，重点修复对象）】\n{relevant}\n"
                )
                logger.info(f"增量Diff：已定位bug位置 行号={loc['lines']} 函数={loc['funcs']}，使用精简上下文")
            else:
                for item in old_code_list:
                    code_section += f"\n==== 文件 {item['file_name']} ====\n{item['content']}\n"
                logger.info("增量Diff：无法定位bug位置，回退完整旧代码")
        # ========================================================================

        # =========【上下文分区精细化管理：修复模式挂载"项目目标摘要+代码区+测试区+技术栈"】=========
        # 不带完整PRD/架构省token；但带轻量"项目目标与设计摘要"，防止多轮修复循环中模型失忆、
        # 忘了程序要干什么、整体框架。这是长期记忆与工作记忆的分层。
        base_fix_prompt = f"""
你是Python开发工程师，负责修复下面代码中的Bug。

【技术栈】
{limit_text(tech_stack, 2000)}

【项目目标与设计摘要】（程序要干什么、总体框架，修复时保持整体方向不跑偏）
{limit_text(state.project_brief, 800)}

{code_section_title}
{code_section}

【测试工程师Bug报告】
{limit_text(test_report, 4000)}

修复要求：
1. 必须【实际修改代码】把测试报告指出的Bug修好，修复后的代码必须能正常运行通过；
2. 只修改Bug相关位置，不要改动无关的正常逻辑；未展示的函数体请按原有逻辑原样保留；
3. 严禁原样返回！修复后的代码必须与修复前存在实际差异，否则视为修复无效；
4. 输出完整可运行的Python代码（在旧代码基础上修改Bug处）；
5. 返回结果格式JSON，key为 file_name 和 content；
{{
  "file_name":"main.py",
  "content":"完整的python代码字符串"
}}
只返回JSON，不要其他解释文本。
"""
        dev_prompt = base_fix_prompt

        # =========【新增：修复后真实运行验证 + 失败反馈重修闭环】=========
        fix_attempts = 0
        run_result = None
        while True:
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

            # 修复后立即真实运行验证
            run_result = run_python_code(new_content)
            logger.info(f"程序员：修复后真实运行验证，success={run_result.success}, summary={run_result.summary}")

            if run_result.success:
                logger.info("程序员：修复后代码真实运行通过，修复有效")
                break
            if fix_attempts >= MAX_FIX_ATTEMPTS:
                logger.warning(f"程序员：修复尝试{MAX_FIX_ATTEMPTS + 1}次后运行仍失败，停止内部重试")
                break

            fix_attempts += 1
            logger.warning(f"程序员：修复后真实运行仍失败，第{fix_attempts}次内部重试")
            # 把真实运行错误反馈给LLM，要求针对该错误再次修复
            run_error_detail = (run_result.stderr or "").strip()[:1000] or run_result.summary
            dev_prompt = base_fix_prompt + f"""

【⚠️上次修复后真实运行仍失败，必须基于下面错误继续修复】
运行是否成功: {run_result.success}
运行错误信息:
{run_error_detail}
请务必【实际修改代码】消除该运行错误，使修复后代码能正常通过运行。
"""
        # ================================================================
    else:
        logger.info("程序员Agent全新开发模式，根据PRD与架构编写代码")
        dev_prompt = f"""
你是Python开发工程师，根据PRD、架构文档、技术栈，输出完整可运行Python程序。
【PRD需求】
{limit_text(prd, 4000)}

【架构方案】
{limit_text(arch_doc, 4000)}

【技术栈选型】
{limit_text(tech_stack, 2000)}

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
        # =========【新增：修复改动范围核对，防止误改正常代码】=========
        old_code_for_compare = ""
        for item in old_code_list:
            if item["file_name"] == new_file_name:
                old_code_for_compare = item["content"]
                break
        if not old_code_for_compare and old_code_list:
            old_code_for_compare = old_code_list[0]["content"]

        run_status = "通过" if (run_result and run_result.success) else "仍失败"
        run_desc = run_result.summary if run_result else "未执行运行验证"

        if old_code_for_compare:
            old_lines = old_code_for_compare.splitlines()
            new_lines = new_content.splitlines()
            diff_lines = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=0))
            added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
            total_lines = max(len(old_lines), len(new_lines), 1)
            changed_ratio = (added + removed) / total_lines
            diff_text = "\n".join(diff_lines)
            dev_note = (
                f"基于测试报告完成缺陷修复。修复后真实运行: {run_status}（{run_desc}）。"
                f"修复改动范围核对：新增{added}行、删除{removed}行、改动占比{changed_ratio:.0%}。\n改动明细(diff)：\n{diff_text}"
            )
            if not (run_result and run_result.success):
                dev_note += "\n⚠️修复后代码真实运行仍失败，请人工排查。"
            elif changed_ratio > 0.5 and (added + removed) > 3:
                logger.warning(f"程序员：修复改动占比过高({changed_ratio:.0%})且改动行数较多({added + removed}行)，可能误改了正常代码，请人工复核")
                dev_note += "\n⚠️改动占比过高且改动行数较多，可能误改了正常代码，请人工复核。"
            logger.info(f"程序员：修复改动核对完成，新增{added}行，删除{removed}行，改动占比{changed_ratio:.0%}")
        else:
            dev_note = f"基于测试报告完成代码缺陷修复。修复后真实运行: {run_status}（{run_desc}）。"
        # ==================================================================
        summary_text = f"【程序员完成Bug修复】修复后真实运行{run_status}，输出文件：{new_file_name}。完整代码保存在code_files。"
    else:
        log_msg = f"程序员：全新开发完成，输出代码文件 {new_file_name}"
        dev_note = "按照PRD与架构完成初始版本代码开发"
        summary_text = f"【程序员完成编码】全新开发输出代码文件：{new_file_name}，完整代码保存在code_files。"

    logger.info(log_msg)

    # ==========【新增：方案一摘要写入chat_history（滑动窗口，防无限膨胀）】==========
    new_chat_history = trim_chat_history(state.chat_history + [("assistant", summary_text)])
    # ================================================================================

    # ==========【新增：代码版本号递增，供项目经理判断"是否需要重新测试"】==========
    new_code_version = state.code_version + 1
    # ==============================================================================

    # ==========【新增：代码落盘到outputs目录，方便用户查看运行】==========
    from config import OUTPUTS_DIR
    import time
    code_paths = []
    try:
        save_dir = OUTPUTS_DIR / time.strftime("%Y%m%d_%H%M%S")
        save_dir.mkdir(exist_ok=True, parents=True)
        file_path = save_dir / new_file_name
        file_path.write_text(new_content, encoding="utf-8")
        code_paths = [str(file_path)]
        logger.info(f"程序员：代码已保存到 {file_path}")
    except Exception as e:
        logger.warning(f"程序员：代码落盘失败：{str(e)}")
    # =====================================================================

    return {
        "code_files": [new_code_item],
        "dev_notes": [dev_note],
        "step_log": [log_msg],
        "chat_history": new_chat_history,
        "code_version": new_code_version,
        "code_file_paths": code_paths
    }
