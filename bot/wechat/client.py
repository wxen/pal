"""
微信 ClawBot 协议客户端
基于 ilinkai.weixin.qq.com 官方 API，纯 Python 实现
参考: @tencent-weixin/openclaw-weixin v2.4.3

协议流程:
  1. QR 码登录 → 获取 bot_token
  2. 长轮询 get_updates → 接收消息
  3. send_message → 发送回复
"""

import json
import time
import struct
import base64
import hashlib
import logging
import threading
from http.cookiejar import CookieJar
from typing import Callable
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode

logger = logging.getLogger("wechat.client")

# ── 常量 ──────────────────────────────────────────────

ILINK_APP_ID = "bot"
CLIENT_VERSION_STR = "2.4.3"
CLIENT_VERSION_INT = (2 << 16) | (4 << 8) | 3  # 0x00020403
BOT_TYPE = "3"
QR_BASE_URL = "https://ilinkai.weixin.qq.com"
DEFAULT_TIMEOUT = 30  # 秒
LONG_POLL_TIMEOUT = 60  # 秒
QR_POLL_INTERVAL = 3  # 秒


class WeChatClient:
    """微信 ClawBot 协议客户端"""

    def __init__(self, bot_agent: str = "Pal"):
        self.bot_agent = bot_agent
        self.bot_token: str | None = None
        self.ilink_user_id: str | None = None
        self.api_base_url: str | None = None
        self._running = False
        self._message_handler: Callable | None = None
        # Cookie session for QR login
        self._cookie_jar = CookieJar()
        self._opener = build_opener(HTTPCookieProcessor(self._cookie_jar))
        # Fixed UIN for the QR session lifetime
        self._session_uin: str = self._random_uin()

    # ── 工具方法 ──────────────────────────────────────

    @staticmethod
    def _random_uin() -> str:
        """生成 X-WECHAT-UIN header（随机 uint32 → base64）"""
        import os
        num = struct.unpack(">I", os.urandom(4))[0]
        return base64.b64encode(str(num).encode()).decode()

    def _common_headers(self, with_auth: bool = True) -> dict:
        """构建公共 HTTP headers"""
        headers = {
            "iLink-App-Id": ILINK_APP_ID,
            "iLink-App-ClientVersion": str(CLIENT_VERSION_INT),
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": self._session_uin,
        }
        if with_auth and self.bot_token:
            headers["Authorization"] = f"Bearer {self.bot_token}"
        return headers

    def _base_info(self) -> dict:
        """构建每个请求的 BaseInfo"""
        return {
            "channel_version": CLIENT_VERSION_STR,
            "bot_agent": self.bot_agent,
        }

    def _post(self, url: str, body: dict, with_auth: bool = True,
              timeout: int = DEFAULT_TIMEOUT) -> dict:
        """POST JSON 请求（维护 cookie 会话）"""
        data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, headers=self._common_headers(with_auth),
                      method="POST")
        try:
            resp = self._opener.open(req, timeout=timeout)
            return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"POST {url[:60]}: {e}")
            raise

    def _get(self, url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """GET 请求（维护 cookie 会话）"""
        req = Request(url, headers=self._common_headers(with_auth=True))
        resp = self._opener.open(req, timeout=timeout)
        return resp.read().decode("utf-8")

    # ── QR 码登录 ─────────────────────────────────────

    def get_qr_code(self) -> dict:
        """
        获取登录二维码
        返回: {qrcode (session_id), qrcode_img_content (URL)}
        """
        body = {
            "base_info": self._base_info(),
            "local_token_list": [],
        }
        url = f"{QR_BASE_URL}/ilink/bot/get_bot_qrcode?bot_type={BOT_TYPE}"
        result = self._post(url, body, with_auth=False)
        # 实际 API 返回: {qrcode, qrcode_img_content, ret}
        # qrcode 字段即 session_key
        result.setdefault("session_key", result.get("qrcode", ""))
        logger.info(f"QR code fetched: {result.get('qrcode_img_content', '')[:60]}")
        return result

    def poll_qr_status(self, session_key: str, timeout: int = 15) -> dict:
        """
        轮询扫码状态（GET 长轮询，服务器会 hold 住直到有状态变化或超时）
        状态: wait → scaned → confirmed → (获得 token)
        timeout 超时会返回 {"status": "wait"}，正常行为
        """
        import urllib.error
        url = f"{QR_BASE_URL}/ilink/bot/get_qrcode_status?qrcode={session_key}"
        # GET 只需要 iLink-App-Id 和 iLink-App-ClientVersion headers
        req = Request(url)
        req.add_header("iLink-App-Id", ILINK_APP_ID)
        req.add_header("iLink-App-ClientVersion", str(CLIENT_VERSION_INT))
        try:
            resp = self._opener.open(req, timeout=timeout)
            return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                return {"status": "wait"}
            logger.warning(f"QR poll error: {e}")
            return {"status": "wait"}

    def login_with_qr(self, on_qr: Callable[[str], None] | None = None,
                      timeout: int = 300) -> bool:
        """
        完整 QR 码登录流程
        on_qr(qr_content): 收到二维码时的回调（用于展示）
        返回: 是否登录成功
        """
        result = self.get_qr_code()
        qr_content = result.get("qrcode_img_content", "") or result.get("qrcode", "")
        session_key = result.get("session_key", "")

        if not qr_content:
            logger.error("Failed to get QR code")
            return False

        logger.info("QR code received, waiting for scan...")
        if on_qr:
            on_qr(qr_content)

        deadline = time.time() + timeout
        status = "wait"

        while time.time() < deadline:
            try:
                resp = self.poll_qr_status(session_key)
                status = resp.get("status", "wait")
                logger.info(f"QR status: {status}")

                if status == "confirmed":
                    self.bot_token = resp.get("bot_token", "")
                    self.ilink_user_id = resp.get("ilink_user_id", "")
                    self.api_base_url = resp.get("baseurl", QR_BASE_URL)
                    logger.info(f"Login success! user={self.ilink_user_id}")
                    return True

                if status in ("expired", "binded_redirect"):
                    logger.warning(f"QR expired or redirected: {status}")
                    return False

                if status == "need_verifycode":
                    logger.warning("Verification code required (not supported yet)")

            except Exception as e:
                logger.warning(f"Poll error: {e}")

            time.sleep(QR_POLL_INTERVAL)

        logger.warning("QR login timed out")
        return False

    # ── 消息接收 ──────────────────────────────────────

    def get_updates(self, timeout: int = LONG_POLL_TIMEOUT) -> dict:
        """长轮询获取新消息"""
        if not self.api_base_url:
            raise RuntimeError("Not logged in")
        body = {
            "get_updates_buf": "",
            "base_info": self._base_info(),
        }
        base = self.api_base_url.rstrip("/")
        url = f"{base}/ilink/bot/getupdates"
        return self._post(url, body, timeout=timeout)

    # ── 消息发送 ──────────────────────────────────────

    def send_message(self, to_user_id: str, text: str,
                     context_token: str | None = None) -> dict:
        """
        发送文本消息
        格式: { msg: { from_user_id, to_user_id, client_id, message_type, message_state, item_list, context_token }, base_info }
        """
        if not self.api_base_url:
            raise RuntimeError("Not logged in")

        client_id = f"pal_{int(time.time() * 1000)}"
        body = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user_id,
                "client_id": client_id,
                "message_type": 2,  # BOT
                "message_state": 2,  # FINISH
                "item_list": [
                    {"type": 1, "text_item": {"text": text}}  # TEXT
                ],
                "context_token": context_token or "",
            },
            "base_info": self._base_info(),
        }
        base = self.api_base_url.rstrip("/")
        url = f"{base}/ilink/bot/sendmessage"
        return self._post(url, body)

    def send_typing(self, to_user_id: str, typing: bool = True) -> dict:
        """发送「正在输入…」状态"""
        if not self.api_base_url:
            raise RuntimeError("Not logged in")
        body = {
            "to_user_id": to_user_id,
            "status": 1 if typing else 2,
            "base_info": self._base_info(),
        }
        base = self.api_base_url.rstrip("/")
        url = f"{base}/ilink/bot/sendtyping"
        return self._post(url, body)

    # ── 事件循环 ──────────────────────────────────────

    def on_message(self, handler: Callable[[dict], str | None]):
        """注册消息处理器"""
        self._message_handler = handler

    def run_forever(self, poll_timeout: int = LONG_POLL_TIMEOUT):
        """启动消息轮询主循环"""
        self._running = True
        logger.info("Starting message loop...")

        while self._running:
            try:
                resp = self.get_updates(timeout=poll_timeout)
                messages = resp.get("msgs", resp.get("messages", resp.get("message_list", [])))

                for msg in messages:
                    self._handle_single_message(msg)

            except Exception as e:
                logger.error(f"Poll loop error: {e}")
                time.sleep(5)

    def _handle_single_message(self, msg: dict):
        """处理单条消息"""
        try:
            from_user = msg.get("from_user_id", "")
            msg_type = msg.get("message_type", 0)

            if msg_type != 1:
                return

            # 从 item_list 提取文本
            item_list = msg.get("item_list", [])
            text = ""
            for item in item_list:
                if item.get("type") == 1:  # TEXT
                    text = item.get("text_item", {}).get("text", "")
                    break
                elif item.get("type") == 3:  # VOICE
                    text = item.get("voice_item", {}).get("text", "")
                    if text:
                        break

            if not text:
                logger.debug(f"[{from_user[:8]}...] <non-text>")
                return

            logger.info(f"[{from_user[:8]}...] {text[:50]}")

            if self._message_handler:
                result = self._message_handler(msg)
                if result is None:
                    return
                # 支持新格式 (send_list, scheduled_list) 和旧格式 str
                if isinstance(result, tuple) and len(result) == 2:
                    send_list, scheduled_list = result
                    for content, ctx in send_list:
                        logger.info(f"SEND: {content[:50]}")
                        self.send_message(from_user, content, ctx)
                    for content, interval, ctx in scheduled_list:
                        logger.info(f"SCHEDULE: {interval}ms -> {content[:50]}")
                        self._schedule_message(from_user, content, ctx, interval / 1000.0)
                elif isinstance(result, str):
                    self.send_message(from_user, result)

        except Exception as e:
            logger.error(f"Handle message error: {e}")

    def _schedule_message(self, to_user: str, text: str, ctx_token: str, delay_sec: float):
        """延迟发送消息"""
        import threading
        def send_delayed():
            time.sleep(delay_sec)
            try:
                self.send_message(to_user, text, ctx_token)
                logger.info(f"DELAYED_SEND: {text[:50]}")
            except Exception as e:
                logger.error(f"Delayed send failed: {e}")
        t = threading.Thread(target=send_delayed, daemon=True)
        t.start()

    def stop(self):
        """停止消息轮询"""
        self._running = False
        logger.info("Message loop stopped")

    def is_logged_in(self) -> bool:
        return bool(self.bot_token and self.api_base_url)
