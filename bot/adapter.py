"""
聊天频道适配器基类
统一接口: receive → engine.process → reply
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("pal.bot")


class BotAdapter(ABC):
    """聊天频道适配器基类"""

    def __init__(self, name: str, engine=None):
        self.name = name
        self._engine = engine

    @property
    def engine(self):
        if self._engine is None:
            from core.engine import PalEngine
            import os
            self._engine = PalEngine(
                session_id=self.name,
                persona=os.environ.get("PAL_PERSONA", None),
                api_key=os.environ.get("PAL_API_KEY", None),
                api_provider=os.environ.get("PAL_API_PROVIDER", None),
                api_model=os.environ.get("PAL_API_MODEL", None),
            )
        return self._engine

    @abstractmethod
    def start(self):
        """启动频道服务"""
        ...

    @abstractmethod
    def stop(self):
        """停止频道服务"""
        ...

    def process_message(self, text: str, user_id: str = "") -> list[dict]:
        """通用消息处理：文本 → engine → 消息列表"""
        results = self.engine.process(text)
        return [r for r in results if r["type"] == "send"]

    @staticmethod
    def extract_text(data: dict) -> str:
        """从平台特定数据中提取文本（子类覆写）"""
        return data.get("text", data.get("content", data.get("message", "")))
