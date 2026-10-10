# 共享约定 · 路由规则 + 熔断规则

> 与 `agents/project_manager.py`、`main.py` 完全一致。各节点只读取与本节点相关的路由分支。

## 1. 输入预处理后路由（main.py: `route_after_input_optimize`）
| `intention` | 下一节点 |
|---|---|
| `chat` | `simple_chat_node` |
| `software_dev` | `project_manager_node` |
| 其他/异常 | END |

## 2. 项目经理阶段调度（project_manager.py: `project_manager_node`）
按顺序判定，命中即分发：

| 判定条件 | 下一节点 | 含义 |
|---|---|---|
| `product_prd is None` | product_manager | 无 PRD，先产出需求文档 |
| `architecture_doc is None` | architect | PRD 就绪，缺架构 |
| `len(code_files) == 0` | developer | 架构就绪，缺代码（全新开发） |
| `tested_code_version != code_version` | tester | 代码有更新但未重新测试 |
| `test_report is not None` 且判定有 bug | developer（若未达熔断）/ 结束（达到熔断） | 修复或终止 |
| `test_report is not None` 且判定无 bug | 结束 | 全部完成 |
| 其他（有代码无测试报告） | tester | 初次测试 |

## 3. 架构评审后路由（main.py: `route_after_arch_review`）
| 用户反馈 | 下一节点 |
|---|---|
| 确认（"继续/确认/可以/没问题..."） | project_manager_node |
| 优化意见 | architect_node（重新生成架构） |

## 4. 业务节点统一回项目经理
`product_manager / developer / tester` 执行完 → `project_manager_node`；`architect` 执行完 → `architecture_review_node`（中断等用户确认）。

## 5. 熔断规则（防死循环，本项目三个层级）

| 熔断点 | 阈值 | 作用 | 位置 |
|---|---|---|---|
| **图级最大轮次** | `MAX_ITERATIONS=5`（.env 可配） | 整个图单次执行最多 5 轮，超限抛 `GraphRecursionError` | LangGraph 配置 |
| **bug 修复迭代** | `MAX_FIX_ITERATION=3` | 同一开发指令内最多修 3 次 bug，达到后强制输出当前结果 | project_manager |
| **单次修复内部重试** | `MAX_FIX_ATTEMPTS=2` | 程序员修复后真实运行失败，最多内部重试 2 次 | developer |

## 6. 跨对话隔离（重要）
- `fix_iteration` 在**新的开发指令到来时由 input_optimize 重置为 0**——一次对话的三次熔断锁死**不会影响**同一会话记录下的下一次对话继续开发。

## 7. Bug 判定规则（project_manager: `_judge_has_bug`）
1. **优先**解析测试报告末尾「测试结论」标记（tester 按 prompt 强制输出）：`通过/全部通过` → 无 bug；其余 → 有 bug；
2. 无标记时回退关键词判断，且**排除否定表述**（"无bug/没有bug/未发现任何bug/全部通过..."）；
3. 出现**具体 bug 编号/描述**（`Bug 1`、`bug:`、`缺陷1`）→ 直接判定有 bug（即使报告里有"无bug"字样）。
