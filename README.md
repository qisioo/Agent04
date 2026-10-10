# 🤖 多Agent智能软件开发流水线（Agent04）

> 基于 **LangGraph** 的模拟软件团队多 Agent 自动化开发流水线。
> 一句话需求 → 自动完成「需求分析 → 架构设计 → 架构人工评审 → 代码编写 → 真实运行验证 → 测试审查」全流程闭环。

---

## 🎯 项目定位

单 Agent 开发存在**角色模糊、质量不稳定、流程不可靠、上下文膨胀导致 Token 成本高**等行业痛点。本项目模拟真实软件团队分工，用 LangGraph 编排 5 类专业 Agent，把"用户一句话需求"自动变成**可运行、已测试、已落盘**的代码产物。

核心回答的问题不是"能不能跑通流程"，而是企业级多 Agent 落地的关键：**能不能稳定、可控、低成本地跑通**。

---

## ✨ 核心亮点

| 亮点 | 说明 |
|---|---|
| 🧩 **多角色协作** | 产品经理 / 架构师 / 程序员 / 测试工程师 / 项目经理，角色边界清晰 |
| 🛡️ **三层熔断** | 图级5轮 / Bug修复3次 / 单次修复重试2次，防死循环与成本失控 |
| ✅ **真实运行验证** | 代码在子进程沙箱中真实执行，杜绝"看起来对但跑不起来" |
| 💾 **增量 Diff 机制** | 修复模式只传"代码骨架 + bug相关代码"，修复 Prompt 体积 **降低 70.2%** |
| 🧠 **上下文分区管理** | 按角色最小权限挂载上下文 + 项目摘要锚点，防失忆、省 Token |
| 🎛️ **模型分级调用** | 简单任务用轻量模型，复杂任务用主模型，压成本提效率 |
| 👤 **架构人工评审** | Human-in-the-Loop，关键设计节点由用户确认，避免错误方向白跑 |
| 📦 **流程 Skill 化封装** | 8 节点独立文档 + 按需加载，流程可复用、可维护 |

---

## 🏗️ 系统架构

### Agent 团队与调度流程

```
                 ┌─────────────────────────────┐
                 │   输入预处理 input_optimize   │  意图识别 + 需求标准化
                 └──────────────┬──────────────┘
                                │ intention?
                ┌───────────────┴───────────────┐
            chat│                              │software_dev
                ▼                              ▼
        ┌──────────────┐              ┌──────────────────┐
        │  simple_chat  │              │  project_manager  │ ← 调度大脑 + 熔断闸
        │  (闲聊应答)   │              └────────┬─────────┘
        └──────────────┘                       │ 分发
                        ┌──────────────────────┼──────────────────────┐
                        ▼                      ▼                      ▼
                 ┌───────────┐          ┌────────────┐          ┌───────────┐
                 │product_mgr│          │ architect  │          │developer  │
                 │  (PRD)    │          │ (架构+摘要)│          │ (代码+落盘)│
                 └───────────┘          └─────┬──────┘          └─────┬─────┘
                        │                    │ 架构评审                 │
                        │             ┌──────▼──────┐                 │
                        │             │architecture │ ← 中断，用户确认   │
                        │             │  _review    │    或提意见回炉    │
                        │             └──────┬──────┘                 │
                        └────────────────────┼────────────────────────┘
                                             ▼
                                      ┌───────────┐
                                      │  tester   │ ← 真实运行 + 测试审查
                                      └─────┬─────┘
                                            ▼
                                    无bug → 完成，代码落盘 outputs/
```

### 状态流转（LangGraph StateGraph）

所有 Agent 通过共享 `SoftwareDevState`（Pydantic 模型）协作。项目经理作为唯一调度中心，按阶段判断下一步路由；每个 Agent 只写入自己负责的状态字段，**不改动其他 Agent 的产物**。

```
raw_user_requirement → refined_requirement(intention)
  → product_prd → architecture_doc + tech_stack_decision + project_brief
  → code_files(code_version) → test_report(tested_code_version)
  → final_output（干净结论 + 落盘路径）
```

---

## 📁 目录结构

```
Agent04/
├── main.py                    # LangGraph 图编排、架构评审中断、意图路由、run入口
├── api.py                     # FastAPI 接口层（线程池执行，并发不阻塞）
├── state.py                   # 全局状态字段定义（Pydantic约束）
├── config.py                  # 配置（.env读取 + 密钥脱敏）
├── pyproject.toml             # 依赖（uv管理，清华源）
├── .env.example               # 环境变量模板（占位符，无真实密钥）
│
├── agents/                    # 5个业务Agent节点
│   ├── project_manager.py     # 项目经理：调度 + 三层熔断 + bug判定 + 干净输出
│   ├── product_manager.py     # 产品经理：输出PRD
│   ├── architect.py           # 架构师：架构 + 技术栈 + 项目摘要(brief)
│   ├── developer.py           # 程序员：增量Diff + 分区上下文 + 真实运行修复闭环
│   └── tester.py              # 测试工程师：真实运行验证 + 测试用例 + 测试报告
│
├── utils/                     # 工具层
│   ├── llm_client.py          # 双实例LLM(main/light) + model_level分级调用
│   ├── prompt_templates.py    # 提示词模板库 + 任务分级映射
│   ├── code_inspect.py        # 增量Diff：AST骨架 / bug定位 / 相关代码提取
│   ├── code_sandbox.py        # 子进程真实运行沙箱
│   ├── context_manager.py     # 滑动窗口 + 长文本截断
│   └── checkpoint_manager.py  # LangGraph checkpoint 会话持久化
│
├── skill/                     # 流程Skill化封装（按需加载）
│   ├── SKILL.md               # 主索引 + 使用规范
│   ├── loader.py              # 按需加载工具（白名单 + 防路径穿越）
│   ├── nodes/                 # 8个节点独立文档
│   └── shared/                # 状态字段字典 + 路由/熔断规则
│
└── outputs/                   # 代码产物落盘（按时间戳分目录，git忽略）
```

---

## 🛠️ 技术栈

- **Python 3.11+**
- **LangGraph**：StateGraph 多节点编排 + 条件路由 + checkpoint 状态持久化
- **LangChain + langchain-deepseek**：LLM 调用封装
- **Pydantic v2**：状态模型强约束 + 结构化校验
- **FastAPI + Uvicorn**：HTTP 服务接口
- **python-dotenv**：环境变量管理

```toml
# pyproject.toml 依赖
langchain>=0.3.0
langgraph>=0.2.0
langchain-deepseek>=1.0.0
python-dotenv>=1.0.0
pydantic>=2.0.0
fastapi>=0.141.1
uvicorn>=0.53.0
```

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装 uv（依赖 Python 3.11+）
# 使用清华源（已在 pyproject.toml 配置默认索引）

uv sync          # 安装依赖
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入真实值：

```ini
DEEPSEEK_API_KEY=你的DeepSeek密钥     # 必填
DEEPSEEK_MODEL=deepseek-chat          # 主模型
# LIGHTWEIGHT_MODEL=xxx               # 选填：轻量模型，不配则默认主模型
MAX_ITERATIONS=5                      # 选填：图级最大轮次
SANDBOX_TIMEOUT=60                    # 选填：沙箱超时秒数
```

> ⚠️ `.env` 已被 `.gitignore` 排除，**不会提交到 git**，请勿泄露真实密钥。

### 3. 启动服务

```bash
uv run uvicorn api:app --host 127.0.0.1 --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即启动成功。

### 4. 调用接口

```
POST http://127.0.0.1:8000/api/agent04/run
```

**场景一：软件开发任务（含架构评审中断）**

第 1 步——发起开发：
```json
{
  "user_input": "写一个Python程序：依次打印'开始'、做一次10除以0的除法、打印'结束'",
  "thread_id": "test-1"
}
```
→ 流程跑到架构师后**中断**，返回架构方案等待确认（`code=100`）。

第 2 步——确认架构继续开发：
```json
{
  "user_input": "继续",
  "thread_id": "test-1",
  "resume": "继续"
}
```
→ 确认后进入开发，完成后返回干净结果：
```json
{
  "code": 0,
  "data": {
    "is_finished": true,
    "final_output": "[软件Agent团队]\n✅ 程序开发完成\n📁 代码文件：.../outputs/20261010_150358/main.py\n📋 测试结论：全部测试通过",
    "refined_requirement": "..."
  }
}
```
（提优化意见时，把 `resume` 改成意见内容，架构师会重写架构再中断。）

**场景二：普通闲聊**
```json
{ "user_input": "你好，介绍一下你自己", "thread_id": "test-1" }
```
→ 走闲聊节点直接返回 LLM 回答。

> 注：`user_input` 至少 1 个字符，resume 恢复时也不能传空串。

---

## 🧠 核心机制详解

### 1. 三层熔断（防死循环与成本失控）
- **图级熔断**：`MAX_ITERATIONS` 控制整个工作流最大轮次
- **修复熔断**：`MAX_FIX_ITERATION`（=3）控制同一轮 Bug 修复最多迭代次数
- **单次熔断**：`MAX_FIX_ATTEMPTS`（=2）控制一次修复内部重试次数

> `fix_iteration` 绑定"当前这一个开发任务"，**新任务自动重置**，不污染后续对话。

### 2. 增量 Diff 机制（省 Token）
修复模式不再传完整旧代码，而是传「**代码结构骨架**（AST 提取函数签名）+ **bug 相关代码**（从测试报告定位行号提取函数体）」。修复 Prompt 体积 **降低 70.2%**，模型只盯着要改的地方，修复更准。

### 3. 上下文分区管理（防失忆 + 省 Token）
按角色最小权限挂载上下文：程序员修 Bug 只挂「技术栈 + 代码区 + 测试区」，并带 `project_brief`（项目目标与设计摘要，3~5 句）作为**记忆锚点**，多轮修复也不会忘掉程序和框架。

### 4. 提示词体系化 + 模型分级
提示词抽成**模板库**（`prompt_templates.py`），指令/格式/示例解耦；任务按难度分级映射到 main/light 两个模型实例，简单任务用轻量模型压成本。

### 5. 真实运行验证
测试工程师通过 `code_sandbox` **子进程真实执行**代码，捕获输出、错误、超时；并用「**测试结论标记 + Bug编号 + 否定词排除**」三重判定 bug，杜绝漏判。

### 6. 流程 Skill 化封装
`skill/` 目录把整套流程固化为可加载文档：8 个节点独立文档 + 状态字段权限字典 + 路由熔断规则，通过 `loader.py` **按需加载**，运行时不扫全量，可复用可维护。

---

## 📈 项目演进（4 次迭代）

| Commit | 内容 |
|---|---|
| `27af7e6` 基础骨架 | LangGraph 图、5 Agent 基础节点、状态定义 |
| `359c5d2` 优化1 | 真实运行沙箱、三层熔断、版本号重测、跨对话隔离 |
| `7c6407d` 优化2 | 增量Diff、上下文分区、架构评审中断 |
| `15e4166` 优化3 | 提示词体系化 + 模型分级、Skill 化封装、并发修复 |

---

## 🧪 验证结果（端到端实测）

完整 8 节点流程**一次通过**：输入 → PRD → 架构 → 中断确认 → 开发 → 测试 → 完成，无 bug 无修复循环，落盘代码运行正确。

---

## 📄 License

MIT License

---

*本项目用于学习与作品展示。密钥仅存于本地 `.env`，仓库内不含任何真实密钥。*
