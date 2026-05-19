"""
微信频道消息处理
将 WeChatClient 与 PalEngine 连接
"""

import logging
from typing import Any

from core.config import Config

logger = logging.getLogger("wechat.handler")


class WeChatHandler:
    """微信消息 → PalEngine 桥接器"""

    def __init__(self, wechat_client=None, engine=None):
        self.wechat = wechat_client
        self._engine = engine
        self._last_msg_time: dict[str, str] = {}

    @property
    def engine(self):
        if self._engine is None:
            from core.engine import PalEngine
            self._engine = PalEngine(session_id="wechat")
        return self._engine

    def handle_message(self, wechat_msg: dict):
        """
        处理来自微信的消息，返回 (send_list, scheduled_list)
        send_list: [(text, context_token), ...]
        scheduled_list: [(text, interval_ms, context_token), ...]
        """
        from_user = wechat_msg.get("from_user_id", "")
        ctx_token = wechat_msg.get("context_token", "")

        # 从 item_list 提取文本
        user_msg = ""
        for item in wechat_msg.get("item_list", []):
            if item.get("type") == 1:
                user_msg = item.get("text_item", {}).get("text", "").strip()
                break
            elif item.get("type") == 3:  # VOICE
                user_msg = item.get("voice_item", {}).get("text", "").strip()
                if user_msg:
                    break

        # 兼容旧格式
        if not user_msg:
            msg_body = wechat_msg.get("message", {})
            user_msg = msg_body.get("text", "").strip()

        if not user_msg:
            return [], []

        import time
        ts = time.strftime("%Y-%m-%d %H:%M:%S")

        self._last_msg_time[from_user] = ts

        try:
            results = self.engine.process(user_msg, timestamp=ts)
        except Exception as e:
            logger.error(f"Engine error: {e}")
            return [], []

        send_list = []
        scheduled_list = []
        for r in results:
            if r["type"] == "send":
                send_list.append((r["content"], ctx_token))
            elif r["type"] == "scheduled":
                interval = r.get("interval", 0)
                scheduled_list.append((r["content"], interval, ctx_token))

        return send_list, scheduled_list

    def register_with_client(self, wechat_client):
        """注册到 WeChatClient"""
        self.wechat = wechat_client
        wechat_client.on_message(self.handle_message)
