# 节点 · tester（测试工程师）

> 真实运行验证 + 代码审查 + 测试用例/报告。以真实运行为最高事实依据。

## 职责
1. 对每个代码文件做**真实运行验证**（沙箱子进程），运行结果作为最高优先级事实；
2. 编写测试用例 `test_case_doc`；
3. 代码逻辑审查，生成测试报告 `test_report`，末尾强制输出「测试结论」标记。

## 读取（输入）state 字段
- `product_prd`、`architecture_doc`（审查参照）
- `code_files`（待测代码）

## 处理逻辑
1. 遍历每个文件调用 `run_python_code` 真实运行，收集 `run_evidence`（成功/摘要/stdout）；
2. `build_tester_prompt(prd, arch, code_all, run_evidence)`，以**主模型**（`model_level="main"`）调用；
3. 按 `# 二、测试报告 test_report` 切分测试用例与测试报告；
4. 记录 `tested_code_version = state.code_version`（标记当前代码已测试）。

## 写入（输出）state 字段
- `test_case_doc`、`test_report`、`tested_code_version`、`step_log`、`chat_history`（追加摘要）
- 失败时：`error_messages`

## 下一步路由
- 执行完 → `project_manager`

## 关键规则
- **真实运行结果优先级最高**：运行报错/超时 = 必然有 bug；运行成功不代表无逻辑问题；
- 报告末尾必须输出 `测试结论: 通过` 或 `测试结论: 存在bug`（项目经理据此判定）；
- 模型级别固定 **main**。

## 关联
- 提示词：`utils/prompt_templates.py::build_tester_prompt`
- 工具：`utils/code_sandbox.py::run_python_code`
- 模型级别：`TASK_MODEL["test"]="main"`
