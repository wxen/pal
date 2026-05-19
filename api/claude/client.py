"""
Anthropic Claude Messages API 客户端（通过 CloseAI 代理）
使用原生 Messages API，非 OpenAI 兼容格式
"""

import json
import os
import logging
from typing import Iterator
from urllib.request import Request, urlopen

logger = logging.getLogger("pal.api.claude")


class ClaudeClient:
    """Anthropic Claude Messages API 客户端"""

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY", "")
        self.base_url = "https://api.openai-proxy.org/anthropic"
        self.default_model = "claude-sonnet-4-6-20250514"
        self.anthropic_version = "2023-06-01"
        self.timeout = timeout

    @property
    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }

    def chat(self, messages: list[dict], model: str | None = None,
             temperature: float = 0.7, max_tokens: int = 4096,
             stream: bool = False, system: str | None = None,
             **kwargs) -> dict:
        """发送 Messages API 请求，返回完整响应"""
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
            **kwargs,
        }
        if system:
            payload["system"] = system

        url = f"{self.base_url}/v1/messages"
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers=self._headers, method="POST")

        try:
            resp = urlopen(req, timeout=self.timeout)
            return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Claude API 错误: {e}")
            raise

    def chat_stream(self, messages: list[dict], model: str | None = None,
                    system: str | None = None, **kwargs) -> Iterator[dict]:
        """发送 Messages API 流式请求"""
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", 4096),
            "temperature": kwargs.pop("temperature", 0.7),
            "stream": True,
            **kwargs,
        }
        if system:
            payload["system"] = system

        url = f"{self.base_url}/v1/messages"
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers=self._headers, method="POST")

        try:
            resp = urlopen(req, timeout=self.timeout)
            for line in resp:
                line = line.decode("utf-8").strip()
                if line.startswith("data: ") and line[6:] != "[DONE]":
                    try:
                        yield json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Claude 流式 API 错误: {e}")
            raise

    def get_text_from_response(self, response: dict) -> str:
        """从 Claude Messages API 响应中提取文本"""
        try:
            content = response.get("content", [])
            if content and isinstance(content, list):
                first = content[0]
                if isinstance(first, dict) and first.get("type") == "text":
                    return first.get("text", "").strip()
            return ""
        except (AttributeError, IndexError, KeyError):
            return ""

    def build_messages(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict] | None = None,
    ) -> tuple[list[dict], str]:
        """构建标准消息列表，返回 (messages, system)"""
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages, system_prompt

    def chat_with_persona(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict] | None = None,
        model: str | None = None,
        **kwargs,
    ) -> str:
        """使用 persona system prompt 进行对话，直接返回文本回复"""
        messages, _ = self.build_messages(system_prompt, user_message, history)
        response = self.chat(
            messages, model=model, system=system_prompt, **kwargs
        )
        return self.get_text_from_response(response)


claude_client = ClaudeClient()
