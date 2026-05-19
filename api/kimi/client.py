"""
月之暗面 Kimi API 客户端
兼容 OpenAI Chat Completions 格式
API 文档: https://platform.moonshot.cn/docs
"""

import os
from pal_api_openai_compat import OpenAICompatibleClient


class KimiClient(OpenAICompatibleClient):
    """月之暗面 Kimi API 客户端"""

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        super().__init__(
            api_key=api_key or os.getenv("KIMI_API_KEY", ""),
            base_url="https://api.moonshot.cn/v1",
            default_model="moonshot-v1-128k",
            timeout=timeout,
        )


kimi_client = KimiClient()
