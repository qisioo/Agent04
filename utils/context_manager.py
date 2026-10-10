"""
utils/context_manager.py
上下文 / Token 管理工具
解决多Agent开发中"上下文无限膨胀、token消耗爆炸"问题，通过：
1. chat_history 滑动窗口：只保留最近N条，防止跨对话无限累积
2. 超长文本限长：传给下游Agent的PRD/架构/测试报告超长时保留头尾，控制token
"""
from utils.logger import logger

# chat_history 最大保留条数，防止无限膨胀
MAX_CHAT_HISTORY = 30


def trim_chat_history(history, max_len: int = MAX_CHAT_HISTORY):
    """
    chat_history 滑动窗口截断：只保留最近 max_len 条
    :param history: [(role, content), ...]
    :param max_len: 最大保留条数
    :return: 截断后的列表
    """
    if not history:
        return history
    if len(history) <= max_len:
        return history
    trimmed = history[-max_len:]
    logger.info(f"上下文管理：chat_history滑动窗口截断，{len(history)}条→{len(trimmed)}条")
    return trimmed


def limit_text(text, max_chars: int = 4000, head_ratio: float = 0.6):
    """
    超长文本限长：保留头部+尾部，中间省略，控制传入LLM的token
    :param text: 原始文本
    :param max_chars: 最大保留字符数
    :param head_ratio: 头部占比（0~1）
    :return: 截断后的文本
    """
    if not text:
        return text
    if len(text) <= max_chars:
        return text
    head_len = int(max_chars * head_ratio)
    tail_len = max_chars - head_len
    head = text[:head_len]
    tail = text[-tail_len:]
    omitted = len(text) - max_chars
    logger.info(f"上下文管理：超长文本限长，{len(text)}字符→{max_chars}字符（省略{omitted}字符）")
    return f"{head}\n……[中间省略{omitted}字符]……\n{tail}"
