"""
utils/prompt_templates.py
提示词体系化模板库
把所有Agent的提示词集中管理，与节点代码解耦：
- 指令、格式要求、输入占位分离，便于统一修改、复用、调优
- 每个模板是一个独立函数，接收参数返回完整prompt
- 配套定义【模型分级】：任务 → 模型级别（简单任务用轻量模型，复杂任务用主模型）
"""
from utils.context_manager import limit_text


# ================= 模型分级：任务 → 模型级别 =================
# model_level="main"  → 主模型（复杂任务：PRD/架构/代码/测试）
# model_level="light" → 轻量模型（简单任务：意图识别/闲聊/摘要/格式校验）
# 各节点调用 safe_llm_invoke_sync(prompt, model_level=TASK_MODEL["xxx"])
TASK_MODEL = {
    "intent": "light",   # 意图识别（简单，轻量模型）
    "chat": "light",     # 闲聊应答（简单，轻量模型）
    "prd": "main",       # 产品需求文档（复杂）
    "arch": "main",      # 架构设计（复杂）
    "dev": "main",       # 代码开发（复杂）
    "fix": "main",       # 代码修复（复杂）
    "fix_retry": "main", # 修复后运行失败重试（复杂）
    "test": "main",      # 测试审查（复杂）
}


# ================= 意图识别（轻量模型） =================
def build_intent_prompt(raw_input: str) -> str:
    """判断用户输入是否软件开发需求，输出标准化需求JSON"""
    return f"""
你是输入意图校验处理器。
用户原始输入：{raw_input}

规则：
任务A：判断用户输入是否属于【软件开发相关需求】。
软件开发需求包括：写Python代码、开发工具、做接口、写项目、写测试用例、设计系统等。
非软件开发：闲聊、问答、生活、科普、普通聊天对话等。

输出严格JSON格式，**不要额外解释，不要markdown**：
{{
  "is_dev_task":true/false,
  "refined_requirement":"is_dev_task=true时输出标准化开发需求；false输出空字符串"
}}
"""


# ================= 产品经理：PRD文档 =================
def build_prd_prompt(refined_req: str) -> str:
    """根据标准化需求输出PRD产品需求文档"""
    return f"""
你是一名资深软件产品经理，根据下面用户开发需求，输出一份规范简洁的PRD产品需求文档。
用户开发需求：
{refined_req}

PRD文档需要包含：
1.项目概述：这个工具/程序要解决什么问题
2.核心功能列表：逐条列出需要实现的功能
3.输入与输出说明
4.非功能约束：运行环境、边界、异常处理要求

直接输出PRD正文，不要多余开场白，不要对话。
"""


# ================= 架构师：架构方案 + 技术栈 + 项目摘要 =================
def build_arch_prompt(prd_content: str, user_feedback: str = "") -> str:
    """根据PRD输出系统架构设计、技术栈选型、项目设计摘要三段内容"""
    feedback_section = ""
    if user_feedback:
        feedback_section = f"""

【用户对上次架构的优化意见，请据此调整架构方案】
{user_feedback}
"""
    return f"""
你是资深Python后端架构师，基于下面PRD需求文档输出架构设计方案与技术栈选型。
==== PRD需求文档 ====
{prd_content}
{feedback_section}

输出三部分内容：
# 一、系统架构设计
1.模块划分：拆分出程序内部各个功能模块，写明每个模块职责
2.模块之间数据如何流转调用
3.关键边界、异常处理设计

# 二、技术栈选型
明确写出需要使用的Python第三方库，不要引入过重的web框架，尽量使用轻量库；写明运行环境要求。

# 三、项目设计摘要
用3-5句话概括：本程序要解决什么问题、核心功能、模块划分概览、关键约束。供后续Agent（尤其修复循环）快速掌握项目全局，防止多轮迭代中丢失目标。

直接输出正文，不要多余寒暄对话。
"""


# ================= 程序员：全新开发 =================
def build_dev_prompt(prd, arch, tech) -> str:
    """根据PRD、架构、技术栈输出完整可运行Python代码"""
    return f"""
你是Python开发工程师，根据PRD、架构文档、技术栈，输出完整可运行Python程序。
【PRD需求】
{limit_text(prd, 4000)}

【架构方案】
{limit_text(arch, 4000)}

【技术栈选型】
{limit_text(tech, 2000)}

要求：
1.代码完整可直接运行，增加必要注释，处理异常；
2.输出JSON格式，key为 file_name 和 content；
{{
  "file_name":"main.py",
  "content":"完整python代码写在这里"
}}
只返回JSON，不要多余对话、不要markdown包裹。
"""


# ================= 程序员：修复模式（增量Diff + 上下文分区） =================
def build_fix_prompt(tech, brief, code_section, code_section_title, test_report) -> str:
    """修复模式：只挂载 技术栈 + 项目摘要 + 代码区 + 测试区，不传完整PRD/架构"""
    return f"""
你是Python开发工程师，负责修复下面代码中的Bug。

【技术栈】
{limit_text(tech, 2000)}

【项目目标与设计摘要】（程序要干什么、总体框架，修复时保持整体方向不跑偏）
{limit_text(brief, 800)}

{code_section_title}
{code_section}

【测试工程师Bug报告】
{limit_text(test_report, 4000)}

修复要求：
1. 必须【实际修改代码】把测试报告指出的Bug修好，修复后的代码必须能正常运行通过；
2. 只修改Bug相关位置，不要改动无关的正常逻辑；未展示的函数体请按原有逻辑原样保留；
3. 严禁原样返回！修复后的代码必须与修复前存在实际差异，否则视为修复无效；
4. 输出完整可运行的Python代码（在旧代码基础上修改Bug处）；
5. 返回结果格式JSON，key为 file_name 和 content；
{{
  "file_name":"main.py",
  "content":"完整的python代码字符串"
}}
只返回JSON，不要其他解释文本。
"""


def build_fix_retry_suffix(success, error_detail) -> str:
    """修复后真实运行仍失败时，追加给LLM的重试反馈片段"""
    return f"""

【⚠️上次修复后真实运行仍失败，必须基于下面错误继续修复】
运行是否成功: {success}
运行错误信息:
{error_detail}
请务必【实际修改代码】消除该运行错误，使修复后代码能正常通过运行。
"""


# ================= 测试工程师：测试用例 + 测试报告 =================
def build_tester_prompt(prd, arch, code_all_text, run_evidence) -> str:
    """根据PRD、架构、代码、真实运行证据，输出测试用例与测试报告"""
    return f"""
你是资深Python测试工程师。
参照PRD需求文档、架构方案，对下面代码做测试分析与审查。

【PRD需求】
{limit_text(prd, 4000)}

【架构方案】
{limit_text(arch, 3000)}

【待审查全部代码】
{code_all_text}

【⚠️真实运行验证结果（最高优先级事实依据，审查必须以此为准）】
{run_evidence}

审查规则：
1. 以【真实运行验证结果】为最高优先级事实：运行报错/超时=必然存在bug；运行成功也不代表无逻辑问题，要继续排查。
2. 真实运行报错时，必须把运行错误信息作为bug逐条写入测试报告。
3. 核对代码是否完整实现PRD全部功能；
4. 检查异常捕获、边界条件、潜在逻辑bug；
5. 仅当真实运行成功 且 逻辑审查无问题，才可写"无bug，全部功能测试通过"。

输出分为两大部分：
# 一、测试用例 test_case_doc
编写多条可执行测试用例，包含：测试场景、输入、预期输出。

# 二、测试报告 test_report
1. 真实运行验证结论：每个文件是否真实运行成功，报错/超时情况；
2. 核对代码是否完整实现PRD全部功能；
3. 检查异常捕获、边界条件、潜在逻辑bug；
4. 如果发现bug：逐条描述bug现象、触发条件、问题位置；
5. 如果没有bug：明确写"无bug，全部功能测试通过"。

【必须】在测试报告最末尾，单独一行输出测试结论标记（不要放在其他文字里）：
- 当真实运行成功 且 未发现任何bug时，输出：测试结论: 通过
- 当真实运行失败 或 发现任何bug时，输出：测试结论: 存在bug

直接输出正文，不要多余开场白。
"""
