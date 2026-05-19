"""
OpenAI 兼容 API 基类
适用于所有遵循 OpenAI /v1/chat/completions 格式的模型服务商
包括: GPT, Kimi, Qwen, GLM, MiMo, MiniMax, Mistral, DeepSeek
"""

import json
import logging
from typing import Iterator
from urllib.request import Request, urlopen

logger = logging.getLogger("pal.api")


class OpenAICompatibleClient:
    """OpenAI 兼容 API 客户端基类"""

    def __init__(self, api_key: str, base_url: str, default_model: str,
                 timeout: int = 60):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(self, messages: list[dict], model: str | None = None,
             temperature: float = 0.7, max_tokens: int = 4096,
             stream: bool = False, **kwargs) -> dict:
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            **kwargs,
        }
        url = f"{self.base_url}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers=self._headers, method="POST")
        try:
            resp = urlopen(req, timeout=self.timeout)
            return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"{self.base_url}: {e}")
            raise

    def chat_stream(self, messages: list[dict], model: str | None = None,
                    **kwargs) -> Iterator[dict]:
        model = model or self.default_model
        payload = {
            "model": model, "messages": messages, "stream": True, **kwargs
        }
        url = f"{self.base_url}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers=self._headers, method="POST")
        resp = urlopen(req, timeout=self.timeout)
        for line in resp:
            line = line.decode("utf-8").strip()
            if line.startswith("data: ") and line[6:] != "[DONE]":
                try:
                    yield json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
