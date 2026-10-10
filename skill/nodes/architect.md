# 节点 · architect（架构师）

> 基于 PRD 输出架构设计、技术栈选型、项目设计摘要三段内容。

## 职责
1. 输出系统架构文档（模块划分、数据流转、边界异常）；
2. 输出技术栈选型；
3. 输出项目设计摘要 `project_brief`（防多轮修复失忆）；
4. 若用户对上次架构提了优化意见，据此调整重写。

## 读取（输入）state 字段
- `product_prd`（PRD）
- `arch_review_feedback`（用户优化意见，可空）

## 处理逻辑
1. `build_arch_prompt(prd, feedback)` 构造 prompt，以**主模型**（`model_level="main"`）调用；
2. 按三个分节标记（`# 二、技术栈选型`、`# 三、项目设计摘要`）切分架构文档 / 技术栈 / 摘要；
3. 未生成摘要时兜底用 PRD 前 300 字；
4. 消费用户意见后，将 `arch_review_feedback` 清空。

## 写入（输出）state 字段
- `architecture_doc`、`tech_stack_decision`、`project_brief`、`arch_done=True`、`arch_review_feedback=None`、`step_log`
- 失败时：`error_messages`

## 下一步路由
- 执行完 → `architecture_review`（中断等用户确认，**不直接回项目经理**）

## 关键规则
- 只写架构相关字段；
- 模型级别固定 **main**；
- 三段输出结构是下游解析硬依赖，改动须同步。

## 关联
- 提示词：`utils/prompt_templates.py::build_arch_prompt`
- 模型级别：`TASK_MODEL["arch"]="main"`
