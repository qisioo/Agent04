"""
utils/llm_client.py
统一大模型客户端封装
职责：
1. 实例化 langchain‑deepseek 的ChatDeepSeek对象
2. 集中处理大模型调用异常、网络超时，打日志
3. 全项目所有Agent统一从此导入llm实例，避免多处重复初始化
依赖：config.py、utils.logger
"""
from langchain_deepseek import ChatDeepSeek
from langchain_core.exceptions import LangChainException
from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    DEEPSEEK_BASE_URL,
    LLM_TEMPERATURE,
    SANDBOX_TIMEOUT
)
from utils.logger import logger


def build_llm_client() -> ChatDeepSeek:
    """
    构建DeepSeek LLM实例
    返回可直接调用invoke / ainvoke 的chat模型对象
    """
    llm = ChatDeepSeek(
        api_key=DEEPSEEK_API_KEY,
        model=DEEPSEEK_MODEL,
        base_url=DEEPSEEK_BASE_URL,
        temperature=LLM_TEMPERATURE,
        timeout=SANDBOX_TIMEOUT
    )
    logger.info(f"LLM客户端初始化完成，model={DEEPSEEK_MODEL}")
    return llm


# 全局单例，整个项目共用同一个llm实例
llm = build_llm_client()


async def safe_llm_invoke(prompt: str):
    """
    安全调用大模型（异步），捕获异常并记录日志
    :param prompt: 输入prompt字符串
    :return: 返回模型输出文本；发生异常返回None
    """
    try:
        resp = await llm.ainvoke(prompt)
        return resp.content
    except LangChainException as e:
        logger.error(f"LLM调用异常: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"LLM未知异常: {str(e)}", exc_info=True)
        return None


def safe_llm_invoke_sync(prompt: str):
    """
    同步版本安全调用，适合部分不需要异步的场景
    :param prompt:输入prompt字符串
    :return:模型输出文本，异常返回None
    """
    try:
        resp = llm.invoke(prompt)
        return resp.content
    except LangChainException as e:
        logger.error(f"LLM同步调用异常: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"LLM同步未知异常: {str(e)}", exc_info=True)
        return None


if __name__ == "__main__":
    """
    自测命令：uv run python -m utils.llm_client
    简单ping测试大模型连通性
    """
    test_prompt = "你好，请只回复ok两个字母，不要多余内容"
    result = safe_llm_invoke_sync(test_prompt)
    if result:
        print(f"✅ LLM连通测试成功，模型返回：{result.strip()}")
    else:
        print("❌ LLM调用失败，请检查api_key、网络")
