"""
utils/checkpoint_manager.py
LangGraph 会话检查点管理
- thread_id：一个软件开发项目对应唯一thread_id
- 同thread_id：加载历史上下文，支持中断继续迭代开发
- 不同thread_id：会话完全隔离
- 默认使用内存MemorySaver；后续可无缝切换 SqliteSaver / RedisSaver
"""
import uuid
from langgraph.checkpoint.memory import MemorySaver

# 全局检查点实例，开发调试内存版本
# 生产替换示例: from langgraph.checkpoint.sqlite import SqliteSaver
# memory_saver = SqliteSaver.from_conn_string("./checkpoint/checkpoint.db")
memory_saver = MemorySaver()


def get_checkpointer() -> MemorySaver:
    """获取检查点实例，编译Graph时传入"""
    return memory_saver


def build_graph_config(thread_id: str) -> dict:
    """
    构造 graph.invoke / graph.stream 使用的config
    :param thread_id: 会话唯一标识
    :return: langgraph config dict
    """
    return {
        "configurable": {
            "thread_id": thread_id
        }
    }


def resolve_thread_id(user_input_thread_id: str | None) -> str:
    """
    解析thread_id逻辑：
    - 用户传入不为None，直接使用用户设定thread_id
    - 用户未传入，自动生成 proj_xxxx 格式唯一id
    """
    if user_input_thread_id and user_input_thread_id.strip():
        return user_input_thread_id.strip()
    return f"proj_{uuid.uuid4().hex[:16]}"
