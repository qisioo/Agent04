# 节点 · architecture_review（架构评审中断）

> human-in-the-loop 中断节点：架构师写完后暂停，等用户确认或提意见。

## 职责
在架构师产出架构后，通过 `interrupt()` 暂停图执行，把架构方案交给用户确认：
- 用户确认 → 回项目经理进入开发；
- 用户提优化意见 → 回架构师重新生成架构。

## 读取（输入）state 字段
- `architecture_doc`、`tech_stack_decision`、`project_brief`（打包进 interrupt 返回给用户）
- interrupt 恢复值 `user_feedback`（用户输入）

## 处理逻辑
1. `interrupt({...架构方案...})` 暂停，返回架构方案给前端（`code=100` + `pending=true`）；
2. 恢复后取用户输入，归一化小写去标点；
3. 命中确认词（`继续/确认/可以/没问题/同意/通过/好/ok/yes...`）或空串 → 视为确认；
4. 否则视为优化意见。

## 写入（输出）state 字段
- 确认：`arch_review_feedback=None`、`current_agent="project_manager"`、`step_log`
- 提意见：`arch_review_feedback=<意见>`、`current_agent="architect"`、`step_log`

## 下一步路由
- 确认 → `project_manager`
- 提意见 → `architect`

## 关键规则
- 使用 `langgraph.types.interrupt`；
- **langgraph 1.x 特性**：`invoke` 遇到 interrupt 不抛异常，而是返回结果 dict 带 `__interrupt__` 字段；`run_agent_workflow` 双路径兼容（except GraphInterrupt + 字段检测）；
- 体验优化：线程处于中断挂起时，用户下一条输入自动作为恢复内容（`run_agent_workflow` 内用 `get_state` 检测 pending）。

## 关联
- 实现：`main.py::architecture_review_node`、`route_after_arch_review`、`run_agent_workflow`
- 恢复值：`api.py` 的 `resume` 字段 / 自动 resume
