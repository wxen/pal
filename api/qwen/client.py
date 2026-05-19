"""
阿里 Qwen（通义千问）API 客户端
兼容 OpenAI Chat Completions 格式
API 文档: https://help.aliyun.com/zh/model-studio/developer-reference/compatible-api
"""

import os
from pal_api_openai_compat import OpenAICompatibleClient


class QwenClient(OpenAICompatibleClient):
    """阿里 Qwen API 客户端"""

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        super().__init__(
            api_key=api_key or os.getenv("QWEN_API_KEY", ""),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_model="qwen-plus",
            timeout=timeout,
        )


qwen_client = QwenClient()
