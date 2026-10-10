# 节点 · simple_chat（闲聊应答）

> 普通对话分支，读取完整对话历史生成回答后结束。

## 职责
读取 `chat_history`（滑动窗口截断后）生成自然语言回答，追加进历史并结束流程。

## 读取（输入）state 字段
- `chat_history`（完整对话历史）

## 处理逻辑
1. `trim_chat_history(state.chat_history)` 截断到最近 30 条，防止 token 膨胀；
2. 以**轻量模型**（`model_level="light"`）调用，直接把历史列表作为输入；
3. 回答追加回 `chat_history`。

## 写入（输出）state 字段
- `chat_history`、`final_output`（`[LLM原生问答回复]\n...`）、`is_finished=True`

## 下一步路由
- 执行完 → END

## 关键规则
- 模型级别固定 **light**；
- 不进入软件开发流水线，不触碰任何业务产物字段。

## 关联
- 提示词：无模板，直接传 `chat_history` 列表
- 模型级别：`TASK_MODEL["chat"]="light"`
