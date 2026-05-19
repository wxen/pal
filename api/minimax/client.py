"""
MiniMax API 客户端
兼容 OpenAI Chat Completions 格式
API 文档: https://platform.minimaxi.com/document/ChatCompletion%20v2
"""

import os
from pal_api_openai_compat import OpenAICompatibleClient


class MiniMaxClient(OpenAICompatibleClient):
    """MiniMax API 客户端"""

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        super().__init__(
            api_key=api_key or os.getenv("MINIMAX_API_KEY", ""),
            base_url="https://api.minimaxi.com/v1",
            default_model="abab6.5s-chat",
            timeout=timeout,
        )


minimax_client = MiniMaxClient()
