# 节点 · project_manager（项目经理调度）

> 调度中枢：按阶段分发任务、判定 bug、执行熔断、生成最终输出。**不调用大模型**。

## 职责
1. 依据当前 state 所处阶段，决定下一个执行节点；
2. 拿到测试报告后判定是否有 bug，决定「继续修复 / 结束」；
3. 达到最大修复次数时熔断，输出当前全部结果；
4. 生成面向用户的干净 `final_output`（含代码落盘路径）。

## 读取（输入）state 字段
- `refined_requirement`、`product_prd`、`architecture_doc`、`code_files`、`test_report`
- `fix_iteration`、`tested_code_version`、`code_version`、`code_file_paths`

## 处理逻辑（按顺序判定）
1. `product_prd is None` → 交 product_manager；
2. `architecture_doc is None` → 交 architect；
3. `len(code_files)==0` → 交 developer（全新开发）；
4. `tested_code_version != code_version` → 交 tester（代码更新未重测）；
5. `test_report is not None` → 判定 bug：有 bug 且未熔断 → developer（fix_iter+1）；有 bug 且达熔断 → 结束；无 bug → 结束；
6. 其他 → tester（初次测试）。

## 写入（输出）state 字段
- `current_agent`、`step_log`、`is_finished`、`final_output`
- 触发修复时：`fix_iteration`（+1）

## 下一步路由
`current_agent` → `product_manager_node` / `architect_node` / `developer_node` / `tester_node`；`None` → END

## 关键规则
- **不调用大模型**，纯状态机判定；
- bug 判定用 `_judge_has_bug`：优先「测试结论」标记 → 回退关键词 + 否定排除 + bug 编号优先；
- 熔断阈值 `MAX_FIX_ITERATION=3`；
- `final_output` 只输出干净摘要（开发完成 + 文件路径），完整产物保留在 state，前端按需展示。

## 关联
- 实现：`agents/project_manager.py::project_manager_node`、`route_by_project_manager`
- 熔断/判定细则：`skill/shared/routing.md`
