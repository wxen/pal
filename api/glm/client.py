"""
智谱 GLM API 客户端
兼容 OpenAI Chat Completions 格式
API 文档: https://open.bigmodel.cn/dev/api/overview
"""

import os
from pal_api_openai_compat import OpenAICompatibleClient


class GLMClient(OpenAICompatibleClient):
    """智谱 GLM API 客户端"""

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        super().__init__(
            api_key=api_key or os.getenv("GLM_API_KEY", ""),
            base_url="https://open.bigmodel.cn/api/paas/v4",
            default_model="glm-4-flash",
            timeout=timeout,
        )


glm_client = GLMClient()
