"""
agents/project_manager.py
项目经理Agent节点
职责：协调调度所有agent，增加最大迭代次数防止无限bug修复循环
"""
from state import SoftwareDevState
from utils.logger import logger

MAX_FIX_ITERATION = 3  # 最大允许bug修复迭代轮次，可以自行修改


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

    # 阶段4：已经有代码，拿到测试报告
    elif test_report is not None:
        has_bug = "bug" in test_report.lower() or "缺陷" in test_report.lower()
        if has_bug:
            if fix_iter >= MAX_FIX_ITERATION:
                # ✅兜底：达到最大修复次数，强制终止，不再修复
                warn_msg = f"⚠️已到达最大bug修复迭代次数{MAX_FIX_ITERATION}，停止迭代修复，输出当前全部结果。"
                logger.warning(warn_msg)
                extra_log = warn_msg
                is_finish_flag = True
                # 拼接最终输出，带上警告
                final_output = f"""[软件Agent团队产出]
{warn_msg}

## PRD需求文档
{prd}

## 架构与技术栈
{arch_doc}
{state.tech_stack_decision or ""}

## 代码文件
"""
                for f in code_files:
                    final_output += f"\n### {f['file_name']}\n```python\n{f['content']}\n```\n"

                final_output += f"""
## 测试用例
{state.test_case_doc or ''}

## 最终测试报告
{test_report}
"""
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
            final_output = f"""[软件Agent团队产出]

## PRD需求文档
{prd}

## 架构与技术栈
{arch_doc}
{state.tech_stack_decision or ""}

## 代码文件
"""
            for f in code_files:
                final_output += f"\n### {f['file_name']}\n```python\n{f['content']}\n```\n"

            final_output += f"""
## 测试用例
{state.test_case_doc or ''}

## 最终测试报告
{test_report}
"""
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
    # 迭代计数更新
    if test_report is not None and ("bug" in test_report.lower() or "缺陷" in test_report.lower()) and fix_iter <= MAX_FIX_ITERATION:
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
