"""
agents/project_manager.py
项目经理Agent节点
职责：协调调度所有agent，增加最大迭代次数防止无限bug修复循环
"""
import re
from state import SoftwareDevState
from utils.logger import logger

MAX_FIX_ITERATION = 3  # 最大允许bug修复迭代轮次，可以自行修改


def _judge_has_bug(test_report: str | None) -> bool:
    """
    判断测试报告是否判定存在bug
    1. 优先解析测试报告末尾的"测试结论"标记（tester按prompt要求输出），最可靠
    2. 找不到标记时，退回关键词判断，并排除"无bug/没有bug/无缺陷"等否定表述
    """
    if not test_report:
        return False
    # 优先解析明确的测试结论标记
    m = re.search(r"测试结论[:：]\s*(通过|全部通过|存在bug|有bug|不通过|失败)", test_report, re.IGNORECASE)
    if m:
        return m.group(1) not in ("通过", "全部通过")
    # 退回关键词判断
    low = test_report.lower()
    has_words = ("bug" in low or "缺陷" in low)
    if not has_words:
        return False
    # 出现具体bug编号/描述（如"Bug 1"、"bug："、"缺陷1"）→ 判定有bug（即使报告中出现"无bug"字样）
    if re.search(r"bug\s*[1-9０-９]|缺陷\s*[1-9０-９]|bug\s*[:：]|缺陷\s*[:：]", test_report, re.IGNORECASE):
        return True
    # 无具体编号：只有明确表述"无bug/通过"才判定无bug
    neg_markers = ("无bug", "没有bug", "未发现bug", "未发现任何bug", "无缺陷", "没有缺陷", "未发现缺陷", "无任何bug", "无任何缺陷", "全部通过", "测试通过")
    has_neg = any(n in low for n in neg_markers)
    return not has_neg


def _build_friendly_output(success: bool, code_paths: list, warn_msg: str = "") -> str:
    """
    生成面向用户的干净最终输出
    不把完整PRD/架构/代码/测试报告堆成一个超长字符串，避免前端展示混乱；
    完整产物仍保存在state对应字段，前端可另做详情页按需读取。
    """
    code_display = code_paths[-1] if code_paths else "（未落盘，见系统状态 code_files）"
    if success:
        return (
            "[软件Agent团队]\n"
            "✅ 程序开发完成\n\n"
            f"📁 代码文件：{code_display}\n"
            "📋 测试结论：全部测试通过\n"
            "📝 可打开上方路径查看并运行程序。\n"
            "\n（详细产物：PRD、架构、测试报告保存在系统状态中，前端可按需展示。）"
        )
    return (
        "[软件Agent团队]\n"
        f"{warn_msg}\n\n"
        f"📁 最新代码文件：{code_display}\n"
        "📋 测试结论：仍存在未解决bug\n"
        "📝 请查看系统状态中的测试报告定位问题。\n"
        "\n（详细产物：PRD、架构、测试报告保存在系统状态中，前端可按需展示。）"
    )


def project_manager_node(state: SoftwareDevState) -> dict:
    step_count = len(state.step_log)
    refined_req = state.refined_requirement
    prd = state.product_prd
    arch_doc = state.architecture_doc
    code_files = state.code_files
    test_report = state.test_report
    fix_iter = state.fix_iteration

    next_agent = None
    extra_log = ""
    final_output = None
    is_finish_flag = False

    # 阶段1：没有PRD，先交给产品经理
    if prd is None:
        next_agent = "product_manager"
        extra_log = "项目经理：分发任务，交由产品经理生成PRD需求文档"

    # 阶段2：PRD完成，没有架构文档，交给架构师
    elif arch_doc is None:
        next_agent = "architect"
        extra_log = "项目经理：PRD已就绪，分发任务交由架构师输出架构方案"

    # 阶段3：架构完成，没有代码，交给程序员全新开发
    elif len(code_files) == 0:
        next_agent = "developer"
        extra_log = "项目经理：架构方案就绪，分发任务交由程序员完成代码开发"

    # 阶段4：有代码，但当前代码有更新尚未测试（如刚修复完）→ 先交给测试工程师重新真实运行验证
    elif state.tested_code_version != state.code_version:
        next_agent = "tester"
        extra_log = "项目经理：代码已更新但尚未重新测试，交由测试工程师真实运行验证"

    # 阶段5：当前代码已测试过，依据测试报告判断
    elif test_report is not None:
        has_bug = _judge_has_bug(test_report)
        if has_bug:
            if fix_iter >= MAX_FIX_ITERATION:
                # ✅兜底：达到最大修复次数，强制终止，不再修复
                warn_msg = f"⚠️已到达最大bug修复迭代次数{MAX_FIX_ITERATION}，停止迭代修复，输出当前全部结果。"
                logger.warning(warn_msg)
                extra_log = warn_msg
                is_finish_flag = True
                final_output = _build_friendly_output(success=False, code_paths=state.code_file_paths, warn_msg=warn_msg)
                next_agent = None
            else:
                # 未到上限，继续修复bug，迭代计数+1
                next_agent = "developer"
                fix_iter += 1
                extra_log = f"项目经理：测试发现bug，迭代轮次{fix_iter}/{MAX_FIX_ITERATION}，交由程序员修复代码"
        else:
            # 无bug，全部流程正常结束
            extra_log = "项目经理：测试工程师确认无bug，全部开发流程完成"
            is_finish_flag = True
            final_output = _build_friendly_output(success=True, code_paths=state.code_file_paths)
            next_agent = None
    else:
        # 有代码但是还没有测试报告 → 交给测试工程师
        next_agent = "tester"
        extra_log = "项目经理：代码开发完成，分发任务交由测试工程师做代码审查"

    logger.info(extra_log)

    ret_dict = {
        "current_agent": next_agent,
        "step_log": [extra_log],
        "is_finished": is_finish_flag
    }
    # 迭代计数更新（与判定逻辑一致）
    if test_report is not None and fix_iter <= MAX_FIX_ITERATION and _judge_has_bug(test_report):
        ret_dict["fix_iteration"] = fix_iter
    if final_output is not None:
        ret_dict["final_output"] = final_output

    return ret_dict


def route_by_project_manager(state: SoftwareDevState) -> str | None:
    """
    项目经理之后条件路由函数
    """
    agent_map = {
        "product_manager": "product_manager_node",
        "architect": "architect_node",
        "developer": "developer_node",
        "tester": "tester_node"
    }
    agent_key = state.current_agent
    if agent_key is None:
        return None
    return agent_map.get(agent_key)
