# 节点 · product_manager（产品经理）

> 根据标准化需求生成 PRD 产品需求文档。

## 职责
读取 `refined_requirement`，生成完整 PRD（项目概述、核心功能、输入输出、非功能约束）。

## 读取（输入）state 字段
- `refined_requirement`（标准化开发需求）

## 处理逻辑
1. `build_prd_prompt(refined_req)` 构造 prompt，以**主模型**（`model_level="main"`）调用；
2. 模型输出直接作为 PRD 存入 `product_prd`。

## 写入（输出）state 字段
- `product_prd`、`step_log`
- 失败时：`error_messages`

## 下一步路由
- 执行完 → `project_manager`

## 关键规则
- **只写** `product_prd`，不触碰其他字段；
- 模型级别固定 **main**（复杂文本生成）。

## 关联
- 提示词：`utils/prompt_templates.py::build_prd_prompt`
- 模型级别：`TASK_MODEL["prd"]="main"`
