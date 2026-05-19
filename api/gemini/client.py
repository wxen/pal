"""
Google Gemini API 客户端（通过 CloseAI 代理）
CloseAI 代理已将其标准化为 OpenAI Chat Completions 格式
"""

import os
from pal_api_openai_compat import OpenAICompatibleClient


class GeminiClient(OpenAICompatibleClient):
    """Google Gemini API 客户端"""

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        super().__init__(
            api_key=api_key or os.getenv("GEMINI_API_KEY", ""),
            base_url="https://api.openai-proxy.org/google",
            default_model="gemini-2.5-flash",
            timeout=timeout,
        )


gemini_client = GeminiClient()
