"""
DeepSeek API 客户端
兼容 OpenAI Chat Completions 格式
API 文档: https://api-docs.deepseek.com/zh-cn/
"""

import json
import time
from typing import Iterator

import requests  # type: ignore

from core.config import Config, DEFAULT_TIMEOUT, DEEPSEEK_MODELS


class DeepSeekClient:
    """DeepSeek API 客户端"""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or Config.DEEPSEEK_API_KEY
        self.base_url = (base_url or Config.DEEPSEEK_BASE_URL).rstrip("/")

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 或环境变量中配置")

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = Config.DEEPSEEK_TEMPERATURE,
        max_tokens: int = Config.DEEPSEEK_MAX_TOKENS,
        top_p: float = Config.DEEPSEEK_TOP_P,
        stream: bool = False,
        **kwargs,
    ) -> dict:
        """发送聊天请求，返回完整响应"""
        model = model or Config.DEEPSEEK_MODEL

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": stream,
            **kwargs,
        }

        url = f"{self.base_url}/chat/completions"

        try:
            resp = requests.post(
                url,
                headers=self._headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            raise TimeoutError(f"DeepSeek API 请求超时 ({DEFAULT_TIMEOUT}s)")
        except requests.exceptions.HTTPError as e:
            detail = e.response.text if e.response else str(e)
            raise RuntimeError(f"DeepSeek API 错误: {detail}")

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = Config.DEEPSEEK_TEMPERATURE,
        max_tokens: int = Config.DEEPSEEK_MAX_TOKENS,
        top_p: float = Config.DEEPSEEK_TOP_P,
        **kwargs,
    ) -> Iterator[dict]:
        """发送聊天请求，返回流式响应迭代器"""
        model = model or Config.DEEPSEEK_MODEL

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": True,
            **kwargs,
        }

        url = f"{self.base_url}/chat/completions"

        try:
            resp = requests.post(
                url,
                headers=self._headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT,
                stream=True,
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        yield chunk
                    except json.JSONDecodeError:
                        continue

        except requests.exceptions.Timeout:
            raise TimeoutError(f"DeepSeek API 流式请求超时 ({DEFAULT_TIMEOUT}s)")
        except requests.exceptions.HTTPError as e:
            detail = e.response.text if e.response else str(e)
            raise RuntimeError(f"DeepSeek API 错误: {detail}")

    def get_text_from_response(self, response: dict) -> str:
        """从 API 响应中提取文本内容"""
        try:
            choices = response.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return ""
        except (KeyError, IndexError, AttributeError):
            return ""

    def build_messages(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict] | None = None,
    ) -> list[dict]:
        """构建标准消息列表"""
        messages = [{"role": "system", "content": system_prompt}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})
        return messages

    def chat_with_persona(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict] | None = None,
        model: str | None = None,
        **kwargs,
    ) -> str:
        """使用 persona system prompt 进行对话，直接返回文本回复"""
        messages = self.build_messages(system_prompt, user_message, history)
        response = self.chat(messages, model=model, **kwargs)
        return self.get_text_from_response(response)

