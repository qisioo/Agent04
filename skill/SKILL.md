# Skill: Multi-Agent Software Development Pipeline

> 多 Agent 智能软件开发流水线 · 流程规范化封装
> 版本：v1.0 ｜ 技术栈：Python / LangGraph / DeepSeek / FastAPI

---

## 1. 本 Skill 是什么

把一套**多 Agent 智能软件开发流水线**（模拟软件团队分工：产品经理 → 架构师 → 程序员 → 测试工程师，由项目经理编排）沉淀为标准化的流程规范，供：
- **复用**：接入新业务场景时，按本 Skill 的节点约定直接组装，不重复搭建流程；
- **维护**：每个节点的职责、输入输出、规则独立成块，改一个节点不动全局；
- **按需读取**：每个 Agent/节点运行时**只读取自己对应的一小块文档**，不扫描整个流程，省上下文、防信息干扰。

## 2. 总体架构

```
用户输入
  │
  ▼
[input_optimize]  意图识别：software_dev / chat
  │  software_dev                     │ chat
  ▼                                   ▼
[project_manager] 项目经理调度      [simple_chat] 闲聊应答 → END
  │  按阶段分发
  ├──▶ [product_manager] 生成PRD ────────────┐
  ├──▶ [architect] 架构+技术栈+项目摘要 ─────┤（写完后进架构评审）
  │        ▼
  │   [architecture_review] 中断，等用户确认 ─┤ 确认→继续 / 提意见→回架构师
  ├──▶ [developer] 开发/修复代码（含增量Diff+分区）┐
  ├──▶ [tester] 真实运行验证+审查 ───────────────┘
  ▼  所有业务节点执行完统一回到 [project_manager] 判定是否完成/修复
END（is_finished）
```

## 3. 节点地图（分块索引）

| 节点 key | 文档 | 职责 | 模型级别 |
|---|---|---|---|
| `input_optimize` | `nodes/input_optimize.md` | 意图识别、需求标准化 | light |
| `simple_chat` | `nodes/simple_chat.md` | 普通闲聊应答 | light |
| `project_manager` | `nodes/project_manager.md` | 阶段调度、bug判定、熔断 | - |
| `product_manager` | `nodes/product_manager.md` | 输出 PRD | main |
| `architect` | `nodes/architect.md` | 架构+技术栈+项目摘要 | main |
| `architecture_review` | `nodes/architecture_review.md` | 架构评审中断(human-in-the-loop) | - |
| `developer` | `nodes/developer.md` | 开发/修复代码（增量Diff+分区） | main |
| `tester` | `nodes/tester.md` | 真实运行验证+测试审查 | main |

**共享约定**（各节点公共依赖，单独分区）：
- `shared/state.md`：全局 `SoftwareDevState` 字段字典（按节点分组标注读写权限）
- `shared/routing.md`：路由规则 + 熔断规则（防死循环）

## 4. 快速开始

```bash
# 启动 API 服务
uv run uvicorn api:app --host 127.0.0.1 --port 8000

# 调用：POST http://127.0.0.1:8000/api/agent04/run
# 请求体：{"user_input": "...", "thread_id": "..."}
# 架构评审中断时返回 code=100 + pending=true + 架构方案，用户回复"继续"或意见即自动恢复
```

## 5. 使用规范：按需读取，禁止扫描全流程

> **关键约束**：任何单个 Agent/节点的工作，只允许读取 `nodes/<自身节点>.md` + `shared/state.md` 中**与本节点相关字段** + `shared/routing.md` 中**与本节点相关路由**，**禁止读取整个 SKILL.md 或其他节点文档**。

- 各节点文档彼此独立、自包含：每个文档都单独列出「本节点职责 / 读取的 state 字段 / 处理逻辑 / 写入的 state 字段 / 下一步路由 / 关键规则」。
- 节点文档**不引用**其他节点的实现细节，只引用 `shared/state.md` 的字段定义，避免链路式扫描。
- 若需要编程方式按需加载（供扩展开发、LLM 辅助、二次开发使用），使用 `skill/loader.py`：

```python
from skill.loader import get_node_doc, get_shared, list_node_keys

doc = get_node_doc("developer")     # 只读 developer 节点文档
schema = get_shared("state")         # 只读共享 state 字段定义
keys = list_node_keys()              # 仅列出节点清单，不读内容
```

## 6. 本 Skill 的三大治理点（与代码一一对应）

| 治理点 | 落点 |
|---|---|
| **防死循环/熔断** | `shared/routing.md`：图级 `MAX_ITERATIONS`、bug修复 `MAX_FIX_ITERATION=3`、单次修复内部重试 `MAX_FIX_ATTEMPTS=2` |
| **token 节约** | `developer` 增量Diff（骨架+bug相关代码）、上下文分区（修复模式只挂 技术栈+摘要+代码+测试）、轻量/主模型分级、聊天窗口滑动截断 |
| **human-in-the-loop** | `architecture_review` 中断，用户确认/提意见后再继续 |

## 7. 目录结构

```
skill/
├── SKILL.md              # 本文件：主索引 + 使用规范
├── loader.py             # 按需加载工具（不扫描全流程）
├── nodes/                # 每个节点独立文档（节点 → 文件）
│   ├── input_optimize.md
│   ├── simple_chat.md
│   ├── project_manager.md
│   ├── product_manager.md
│   ├── architect.md
│   ├── architecture_review.md
│   ├── developer.md
│   └── tester.md
└── shared/               # 共享约定
    ├── state.md          # 全局状态字段字典
    └── routing.md        # 路由 + 熔断规则
```
