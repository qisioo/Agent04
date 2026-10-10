"""
utils/llm_client.py
统一大模型客户端封装
职责：
1. 实例化 langchain-deepseek 的ChatDeepSeek对象（支持主模型 + 轻量模型双实例）
2. 集中处理大模型调用异常、网络超时，打日志
3. 全项目所有Agent统一从此导入llm实例，避免多处重复初始化
4. 【模型分级】按任务复杂度选择模型：复杂任务(架构/代码/测试)用主模型，简单任务(意图识别/闲聊/摘要)用轻量模型
依赖：config.py、utils.logger
"""
from langchain_deepseek import ChatDeepSeek
from langchain_core.exceptions import LangChainException
from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    LIGHTWEIGHT_MODEL,
    DEEPSEEK_BASE_URL,
    LLM_TEMPERATURE,
    SANDBOX_TIMEOUT
)
from utils.logger import logger


def build_llm_client(model: str) -> ChatDeepSeek:
    """
    构建DeepSeek LLM实例
    :param model: 模型名称
    :return: 可直接调用invoke / ainvoke 的chat模型对象
    """
    llm = ChatDeepSeek(
        api_key=DEEPSEEK_API_KEY,
        model=model,
        base_url=DEEPSEEK_BASE_URL,
        temperature=LLM_TEMPERATURE,
        timeout=SANDBOX_TIMEOUT
    )
    return llm


# ============【模型分级】双实例：主模型 + 轻量模型 ============
# main_llm：主模型，处理复杂任务（PRD/架构/代码/测试）
# light_llm：轻量模型，处理简单任务（意图识别/闲聊/格式校验/摘要）；未配置则与主模型相同
main_llm = build_llm_client(DEEPSEEK_MODEL)
light_llm = build_llm_client(LIGHTWEIGHT_MODEL)
logger.info(f"LLM客户端初始化完成，main_model={DEEPSEEK_MODEL}, light_model={LIGHTWEIGHT_MODEL}")

_MODEL_INSTANCES = {
    "main": main_llm,
    "light": light_llm,
}


def _get_llm(model_level: str = "main") -> ChatDeepSeek:
    """按模型级别返回对应llm实例，未知级别回退主模型"""
    return _MODEL_INSTANCES.get(model_level, main_llm)


async def safe_llm_invoke(prompt: str, model_level: str = "main"):
    """
    安全调用大模型（异步），捕获异常并记录日志
    :param prompt: 输入prompt字符串
    :param model_level: 模型级别，"main"主模型 / "light"轻量模型
    :return: 返回模型输出文本；发生异常返回None
    """
    llm = _get_llm(model_level)
    try:
        resp = await llm.ainvoke(prompt)
        return resp.content
    except LangChainException as e:
        logger.error(f"LLM调用异常({model_level}): {str(e)}")
        return None
    except Exception as e:
        logger.error(f"LLM未知异常({model_level}): {str(e)}", exc_info=True)
        return None


def safe_llm_invoke_sync(prompt: str, model_level: str = "main"):
    """
    同步版本安全调用，适合部分不需要异步的场景
    :param prompt:输入prompt字符串
    :param model_level: 模型级别，"main"主模型 / "light"轻量模型；默认主模型，兼容旧调用
    :return:模型输出文本，异常返回None
    """
    llm = _get_llm(model_level)
    try:
        resp = llm.invoke(prompt)
        return resp.content
    except LangChainException as e:
        logger.error(f"LLM同步调用异常({model_level}): {str(e)}")
        return None
    except Exception as e:
        logger.error(f"LLM同步未知异常({model_level}): {str(e)}", exc_info=True)
        return None


if __name__ == "__main__":
    """
    自测命令：uv run python -m utils.llm_client
    简单ping测试大模型连通性
    """
    test_prompt = "你好，请只回复ok两个字母，不要多余内容"
    result = safe_llm_invoke_sync(test_prompt, model_level="light")
    if result:
        print(f"✅ LLM连通测试成功，模型返回：{result.strip()}")
    else:
        print("❌ LLM调用失败，请检查api_key、网络")
