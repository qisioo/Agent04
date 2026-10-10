# 节点 · input_optimize（输入优化与意图识别）

> 唯一入口节点。只处理「识别意图 + 标准化需求」，不生成业务产物。

## 职责
1. 将本轮用户消息追加写入 `chat_history`（滑动窗口截断，防无限膨胀）；
2. 调用轻量模型识别意图 `software_dev` / `chat`；
3. 若是开发任务，输出标准化需求 `refined_requirement`，并**重置 `fix_iteration=0`**（隔离跨对话熔断）。

## 读取（输入）state 字段
- `raw_user_requirement`（用户原始输入）
- `chat_history`（追加本轮输入用）

## 处理逻辑
1. 用 `prompt_templates.build_intent_prompt(raw)` 构造意图识别 prompt，**以轻量模型**（`model_level="light"`）调用；
2. 解析返回 JSON：`{"is_dev_task":bool, "refined_requirement":str}`；
3. 识别为开发任务 → 置 `intention="software_dev"`、写入 `refined_requirement`、`fix_iteration=0`；
4. 否则 → `intention="chat"`、`refined_requirement=None`。

## 写入（输出）state 字段
- `chat_history`、`intention`、`refined_requirement`、`fix_iteration`、`step_log`
- 异常/解析失败时：写 `error_messages`，并置 `is_finished=True`、`final_output` 为错误提示。

## 下一步路由
- `intention == chat` → `simple_chat`
- `intention == software_dev` → `project_manager`
- 其他/异常 → END

## 关键规则
- **禁止**改写 `raw_user_requirement`；
- 模型级别固定 **light**（简单任务）；
- 每次新开发指令必重置 `fix_iteration`，保证三次熔断只作用于本次指令。

## 关联
- 提示词：`utils/prompt_templates.py::build_intent_prompt`
- 模型级别：`TASK_MODEL["intent"]="light"`
