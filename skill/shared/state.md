# 共享约定 · 全局状态字段字典（SoftwareDevState）

> 每个节点只读取/写入与本节点相关的字段，禁止触碰其他节点产物字段。
> 字段分组与 `state.py` 完全一致。标 ✅=本层节点可写；标 👁=本层节点可读。

## 1. 用户输入层
| 字段 | 类型 | 说明 | 可写节点 |
|---|---|---|---|
| `raw_user_requirement` | str | 用户原始输入，初始化后**禁止改写** | input_optimize 写入（初始化） |

## 2. 输入预处理输出层
| 字段 | 类型 | 说明 | 可写节点 |
|---|---|---|---|
| `refined_requirement` | str? | 标准化开发需求 | input_optimize |
| `intention` | str? | `chat` / `software_dev`，用于路由 | input_optimize |
| `chat_history` | list[(role,content)] | 全局对话历史，滑动窗口截断 | input_optimize / simple_chat / 各 agent（追加摘要） |

## 3. 产品经理输出层
| 字段 | 类型 | 说明 | 可写节点 |
|---|---|---|---|
| `product_prd` | str? | PRD 产品需求文档 | product_manager |

## 4. 架构师输出层
| 字段 | 类型 | 说明 | 可写节点 |
|---|---|---|---|
| `architecture_doc` | str? | 系统架构设计文档 | architect |
| `tech_stack_decision` | str? | 技术栈选型结论 | architect |
| `project_brief` | str | 项目目标与设计摘要（防修复失忆，轻量携带） | architect |
| `arch_review_feedback` | str? | 用户对架构的确认/优化意见 | architecture_review |

## 5. 程序员输出层
| 字段 | 类型 | 说明 | 可写节点 |
|---|---|---|---|
| `code_files` | list[dict] | 代码文件 `[{file_name, content}]` | developer |
| `dev_notes` | list[str] | 开发备注（含 diff 核对结果） | developer |
| `code_file_paths` | list[str] | 代码落盘路径，供用户查看 | developer |

## 6. 测试工程师输出层
| 字段 | 类型 | 说明 | 可写节点 |
|---|---|---|---|
| `test_case_doc` | str? | 测试用例文档 | tester |
| `test_report` | str? | 测试报告，末尾含「测试结论」标记 | tester |

## 7. 日志与异常层
| 字段 | 类型 | 说明 | 可写节点 |
|---|---|---|---|
| `step_log` | list[str] | 步骤日志 | 所有节点 |
| `error_messages` | list[str] | 错误信息 | 所有节点 |

## 8. 流程控制层
| 字段 | 类型 | 说明 | 可写节点 |
|---|---|---|---|
| `current_agent` | str? | 当前要执行的 agent 名，供路由 | project_manager / architecture_review |
| `fix_iteration` | int | bug 修复迭代计数（新开发指令重置为0） | input_optimize / project_manager |
| `is_finished` | bool | 流程是否结束 | project_manager / simple_chat / input_optimize(异常) |
| `code_version` | int | 代码版本号，程序员每次产出/修复 +1 | developer |
| `tested_code_version` | int | 已测试的代码版本号（-1=未测试过） | tester |

## 9. 对外最终输出层
| 字段 | 类型 | 说明 | 可写节点 |
|---|---|---|---|
| `final_output` | str? | 面向用户的干净最终输出 | project_manager / simple_chat / input_optimize(异常) |

## 字段读写最小权限原则
- 每个节点**只写**自己产出的字段（第 2~6 层 + 自己的日志/流程字段）。
- 跨节点传递只通过**项目经理判定**（`current_agent`）与**路由**进行，节点之间**不直接读取对方业务逻辑**。
- 例外：`developer` 修复模式会读取 `product_prd`/`architecture_doc`（全新开发）或 `project_brief`（修复），`tester` 读取 `product_prd`/`architecture_doc`——这是「只读所需输入」，不写入。
