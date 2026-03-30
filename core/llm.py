"""LangChain LLM 配置：DeepSeek / OpenAI 兼容接口。"""
import os

from langchain_openai import ChatOpenAI

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
MODEL_KEY = os.getenv("DEEPSEEK_KEY")


def get_llm(
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    temperature: float = 0.6,
    *,
    streaming: bool = True,
) -> ChatOpenAI:
    """创建 LangChain ChatOpenAI 实例（兼容 DeepSeek 等 OpenAI 接口）。

    streaming=True 时与 LangGraph stream_mode=\"messages\" 配合，可在终端逐 token 输出。
    """
    return ChatOpenAI(
        base_url=base_url,
        model=model,
        api_key=api_key or MODEL_KEY,
        temperature=temperature,
        streaming=streaming,
    )
