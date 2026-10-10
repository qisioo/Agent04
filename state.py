""" state.py 【项目根目录】 全局Graph状态定义，使用Pydantic BaseModel 约束：
 1. 字段不允许外部随意改写，所有变更只允许各个node返回增量dict完成reducer更新
 2. raw_user_requirement 用户原始输入，一旦初始化后不允许改写
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Annotated


class SoftwareDevState(BaseModel):
    # ========== 用户输入层 ==========
    raw_user_requirement: Annotated[str, Field(description="用户原始输入，初始化后禁止改写")]
    """用户原始需求输入，初始化后不允许修改"""

    # ========== 输入预处理输出 ==========
    refined_requirement: Optional[str] = None
    """输入预处理输出：标准化开发需求"""

    # ✅新增：意图识别标记，用于graph条件路由
    intention: Optional[str] = Field(default=None, description="意图: chat=普通闲聊 | software_dev=软件开发任务")

    # ✅新增：全局统一对话历史，闲聊、Agent产出全部存入此处，共享上下文记忆
    chat_history: List[tuple[str, str]] = Field(default_factory=list, description="对话历史，格式[(role,content)], role: user / assistant")

    # ========== 产品经理输出 ==========
    product_prd: Optional[str] = None
    """PRD产品需求文档"""

    # ========== 架构师输出 ==========
    architecture_doc: Optional[str] = None
    """系统架构设计文档"""
    tech_stack_decision: Optional[str] = None
    """技术栈选型结论"""

    # ========== 程序员输出 ==========
    code_files: List[dict] = Field(default_factory=list)
    """代码文件列表 [{file_name:str, content:str}]"""
    dev_notes: List[str] = Field(default_factory=list)
    """开发备注信息"""
    code_file_paths: List[str] = Field(default_factory=list)
    """代码落盘路径列表，供用户查看运行"""

    # ========== 测试工程师输出 ==========
    test_case_doc: Optional[str] = None
    """测试用例文档"""
    test_report: Optional[str] = None
    """测试报告，标记是否存在bug"""

    # ========== 日志与异常 ==========
    step_log: List[str] = Field(default_factory=list)
    error_messages: List[str] = Field(default_factory=list)

    # ========== 流程控制字段 ==========
    current_agent: Optional[str] = None
    fix_iteration: int = 0   # ✅新增：bug修复迭代计数器
    """bug修复循环迭代计数，防止无限循环"""
    is_finished: bool = False

    # ✅新增：代码版本号对比，区分"当前代码是否已测试"
    # 修复"修完bug后不重新测试、项目经理复用旧测试报告反复判定有bug"的调度缺陷
    code_version: int = 0  # 代码版本号，程序员每次产出/修复代码时+1
    tested_code_version: int = -1  # 已测试过的代码版本号，-1表示尚未测试过任何代码

    # ========== 对外最终输出 ==========
    final_output: Optional[str] = None
