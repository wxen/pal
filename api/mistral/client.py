"""
Mistral AI API 客户端
兼容 OpenAI Chat Completions 格式
API 文档: https://docs.mistral.ai/api/
"""

import os
from pal_api_openai_compat import OpenAICompatibleClient


class MistralClient(OpenAICompatibleClient):
    """Mistral AI API 客户端"""

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        super().__init__(
            api_key=api_key or os.getenv("MISTRAL_API_KEY", ""),
            base_url="https://api.mistral.ai/v1",
            default_model="mistral-small-latest",
            timeout=timeout,
        )


mistral_client = MistralClient()
