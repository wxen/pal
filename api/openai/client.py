"""
OpenAI GPT API 客户端（通过 CloseAI 代理）
兼容 OpenAI Chat Completions 格式
"""

import os
from pal_api_openai_compat import OpenAICompatibleClient


class OpenAIClient(OpenAICompatibleClient):
    """OpenAI GPT API 客户端"""

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        super().__init__(
            api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
            base_url="https://api.openai-proxy.org/v1",
            default_model="gpt-5.4-mini",
            timeout=timeout,
        )


openai_client = OpenAIClient()
