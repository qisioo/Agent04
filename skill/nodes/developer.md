# 节点 · developer（程序员）

> 开发/修复代码。含三大治理：**增量Diff**、**上下文分区**、**真实运行修复闭环**。

## 职责
1. 全新开发：按 PRD + 架构 + 技术栈输出完整可运行代码；
2. 修复模式：基于旧代码 + 测试报告定位并修复 bug，**只改 bug 位置，不误改正常逻辑**；
3. 修复后真实运行验证，失败则反馈错误重试（内部 `MAX_FIX_ATTEMPTS=2`）；
4. 代码落盘到 `outputs/`，输出代码版本号。

## 读取（输入）state 字段
- 全新模式：`product_prd`、`architecture_doc`、`tech_stack_decision`
- 修复模式：`tech_stack_decision`、`project_brief`（轻量摘要防失忆）、`code_files`（旧代码）、`test_report`

## 处理逻辑
- **全新开发**：`build_dev_prompt(prd, arch, tech)`，主模型调用，输出 JSON `{file_name, content}`；
- **修复模式**：
  1. 增量Diff：`extract_skeleton`（AST 提取全文件函数签名骨架） + `find_bug_locations`（从测试报告定位行号+真实函数名） + `extract_relevant_code`（提取 bug 相关函数体±8行）；
  2. 构造 `build_fix_prompt`：只挂 **技术栈 + 项目摘要 + 代码区(骨架+bug代码) + 测试报告**，不传完整 PRD/架构 → 省 token；
  3. 若 AST 失败/定位不到 → 回退完整旧代码；
  4. 修复后 `run_python_code` 真实运行，失败用 `build_fix_retry_suffix` 反馈错误重试；
  5. diff 核对改动占比，过高（>50% 且 >3 行）告警防误改。

## 写入（输出）state 字段
- `code_files`、`dev_notes`、`step_log`、`code_file_paths`、`code_version`（+1）、`chat_history`（追加摘要）
- 失败时：`error_messages`

## 下一步路由
- 执行完 → `project_manager`

## 关键规则
- **token 节约核心**：修复模式用「骨架 + bug 相关代码」替代完整旧代码；用 `project_brief` 替代完整 PRD/架构防失忆；
- 修复必须【实际修改】代码（禁止原样返回），修复后必须真实运行通过；
- 模型级别：开发/修复均 **main**。

## 关联
- 提示词：`utils/prompt_templates.py::build_dev_prompt / build_fix_prompt / build_fix_retry_suffix`
- 工具：`utils/code_inspect.py`（骨架/定位/相关代码）、`utils/code_sandbox.py`（真实运行）
- 模型级别：`TASK_MODEL["dev"]="main"`、`TASK_MODEL["fix"]="main"`
