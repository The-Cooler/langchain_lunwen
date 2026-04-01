"""LangChain LLM 配置：DeepSeek / OpenAI 兼容接口。"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

DEFAULT_BASE_URL = os.getenv("BASE_URL")
DEFAULT_MODEL = os.getenv("MODEL")
MODEL_KEY = os.getenv("API_KEY")
PLAN_BASE_URL = os.getenv("PLAN_BASE_URL")
PLAN_MODEL = os.getenv("PLAN_MODEL")
PLAN_API_KEY = os.getenv("PLAN_API_KEY")
WRITER_BASE_URL = os.getenv("WRITER_BASE_URL")
WRITER_MODEL = os.getenv("WRITER_MODEL")
WRITER_API_KEY = os.getenv("WRITER_API_KEY")


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


def get_plan_llm(
    *,
    streaming: bool = False,
    temperature: float = 0.2,
) -> ChatOpenAI:
    """规划模型：优先读取 PLAN_*，未配置时回退到全局 MODEL。"""
    return get_llm(
        base_url=PLAN_BASE_URL or DEFAULT_BASE_URL,
        model=PLAN_MODEL or DEFAULT_MODEL,
        api_key=PLAN_API_KEY or MODEL_KEY,
        temperature=temperature,
        streaming=streaming,
    )


def get_writer_llm(
    *,
    streaming: bool = True,
    temperature: float = 0.6,
) -> ChatOpenAI:
    """写作模型：优先读取 WRITER_*，未配置时回退到全局 MODEL。"""
    return get_llm(
        base_url=WRITER_BASE_URL or DEFAULT_BASE_URL,
        model=WRITER_MODEL or DEFAULT_MODEL,
        api_key=WRITER_API_KEY or MODEL_KEY,
        temperature=temperature,
        streaming=streaming,
    )
