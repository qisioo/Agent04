"""
skill/loader.py
按需加载工具：每个 Agent/节点只读取自己对应的一小块文档，不扫描整个流程。

用法：
    from skill.loader import get_node_doc, get_shared, list_node_keys
    doc = get_node_doc("developer")     # 只读 developer 节点文档
    schema = get_shared("state")         # 只读共享 state 字段定义
    keys = list_node_keys()              # 仅列出节点清单，不读内容

设计要点：
- 节点文档独立分块，禁止一次读取全部节点（防上下文浪费、信息干扰）；
- 用 key 白名单 + 路径解析约束，防止路径穿越/越界读取；
- 不依赖 LangGraph，可被任何 Agent/脚本单独引用。
"""
from pathlib import Path

_SKILL_DIR = Path(__file__).parent

# 节点 key → 文档相对路径（白名单，禁止越界）
NODE_FILES = {
    "input_optimize": "nodes/input_optimize.md",
    "simple_chat": "nodes/simple_chat.md",
    "project_manager": "nodes/project_manager.md",
    "product_manager": "nodes/product_manager.md",
    "architect": "nodes/architect.md",
    "architecture_review": "nodes/architecture_review.md",
    "developer": "nodes/developer.md",
    "tester": "nodes/tester.md",
}

# 共享块 key → 相对路径（白名单）
SHARED_FILES = {
    "state": "shared/state.md",
    "routing": "shared/routing.md",
}

# 主入口文件
SKILL_MAIN = "SKILL.md"


def _read(file_rel: str) -> str:
    """读取 skill 目录下指定相对路径文件，白名单外的路径直接拒绝"""
    path = (_SKILL_DIR / file_rel).resolve()
    # 防路径穿越：确保解析后仍在 skill 目录内
    if _SKILL_DIR.resolve() not in path.parents:
        raise ValueError(f"非法路径: {file_rel}")
    return path.read_text(encoding="utf-8")


def get_node_doc(node_key: str) -> str:
    """只读取指定节点文档（不读取其他节点、不读取全流程）"""
    if node_key not in NODE_FILES:
        raise KeyError(f"未知节点key: {node_key}，可用: {list(NODE_FILES.keys())}")
    return _read(NODE_FILES[node_key])


def get_shared(shared_key: str) -> str:
    """只读取指定共享块（state 字段字典 / 路由熔断规则）"""
    if shared_key not in SHARED_FILES:
        raise KeyError(f"未知共享块key: {shared_key}，可用: {list(SHARED_FILES.keys())}")
    return _read(SHARED_FILES[shared_key])


def get_skill_main() -> str:
    """只读取主入口 SKILL.md（索引/使用规范）"""
    return _read(SKILL_MAIN)


def list_node_keys() -> list:
    """仅列出节点清单（不读取任何文档内容）"""
    return list(NODE_FILES.keys())


def list_shared_keys() -> list:
    """仅列出共享块清单"""
    return list(SHARED_FILES.keys())


if __name__ == "__main__":
    print("skill/loader.py 自检")
    print("节点清单:", list_node_keys())
    print("共享块:", list_shared_keys())
    dev_doc = get_node_doc("developer")
    print(f"读取 developer 文档: {len(dev_doc)} 字符，首行: {dev_doc.splitlines()[0]}")
    schema = get_shared("state")
    print(f"读取 state 共享块: {len(schema)} 字符")
    try:
        get_node_doc("../main.py")  # 应被白名单拒绝
    except (KeyError, ValueError) as e:
        print(f"越界读取被拒绝: {e}")
    print("✅ loader 按需加载正常")
