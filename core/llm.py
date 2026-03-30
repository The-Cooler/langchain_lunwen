"""LangChain LLM 配置：DeepSeek / OpenAI 兼容接口。"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# 兼容两套环境变量命名：
# 1) 旧版：BASE_URL / MODEL / API_KEY
# 2) 当前项目 .env：DEEPSEEK_BASE_URL / DEEPSEEK_MODEL / DEEPSEEK_API_KEY（以及 DEEPSEEK_KEY）
DEFAULT_BASE_URL = (
    os.getenv("DEEPSEEK_BASE_URL")
    or os.getenv("BASE_URL")
    or "https://api.deepseek.com"
)
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL") or os.getenv("MODEL") or "deepseek-chat"
MODEL_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY") or os.getenv("API_KEY")


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
    # api_key 允许为 None（适合本地不鉴权的情况），但 model/base_url 必须有效。
    if not model:
        raise ValueError("模型名 model 为空，请检查环境变量 DEEPSEEK_MODEL 或 MODEL")
    if not base_url:
        raise ValueError("base_url 为空，请检查环境变量 DEEPSEEK_BASE_URL 或 BASE_URL")

    return ChatOpenAI(
        base_url=base_url,
        model=model,
        api_key=api_key or MODEL_KEY,
        temperature=temperature,
        streaming=streaming,
    )
