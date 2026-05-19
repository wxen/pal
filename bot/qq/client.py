"""
QQ Bot 适配器 — WebSocket 模式（无需公网 IP）
连接 QQ 开放平台 WebSocket 网关收发消息
"""

import os, json, time, threading, logging
from bot.adapter import BotAdapter

logger = logging.getLogger("pal.bot.qq")

QQ_BOT_APP_ID = os.environ.get("QQ_BOT_APP_ID", "")
QQ_BOT_SECRET = os.environ.get("QQ_BOT_SECRET", "")

import requests as _requests

def _get_access_token():
    try:
        r = _requests.post("https://bots.qq.com/app/getAppAccessToken",
            json={"appId": QQ_BOT_APP_ID, "clientSecret": QQ_BOT_SECRET}, timeout=10)
        d = r.json()
        return d.get("access_token", "")
    except Exception as e:
        logger.error(f"QQ auth: {e}")
        return ""

def _get_ws_url():
    token = _get_access_token()
    if not token: return None
    try:
        r = _requests.get("https://api.sgroup.qq.com/gateway/bot",
            headers={"Authorization": f"QQBot {token}"}, timeout=10)
        return r.json().get("url", "")
    except Exception as e:
        logger.error(f"QQ gateway: {e}")
        return None


class QQBot(BotAdapter):
    def __init__(self):
        super().__init__(name="qq")
        self._ws = None
        self._seq = 0
        self._session_id = ""
        self._running = False
        self._heartbeat_thread = None

    def start(self):
        logger.info("QQ Bot WebSocket 连接中...")
        self._running = True
        _connect_ws(self)

    def stop(self):
        self._running = False
        if self._ws: self._ws.close()

    def reply(self, channel_id: str, msg_id: str, text: str, msg_type: str = "", seq: int = 1):
        """通过 QQ API 发送消息——根据消息类型选择正确端点"""
        token = _get_access_token()
        if not token: return
        headers = {"Authorization": f"QQBot {token}", "Content-Type": "application/json"}
        payload = {"content": text, "msg_id": msg_id, "msg_seq": seq}

        # C2C 私聊用 users 端点, 频道消息用 channels 端点
        if msg_type in ("C2C_MESSAGE_CREATE", "DIRECT_MESSAGE_CREATE"):
            url = f"https://api.sgroup.qq.com/v2/users/{channel_id}/messages"
        else:
            url = f"https://api.sgroup.qq.com/v2/channels/{channel_id}/messages"

        try:
            resp = _requests.post(url, json=payload, headers=headers, timeout=10)
            d = resp.json()
            if d.get("code"):
                logger.error(f"QQ reply err [{d.get('code')}]: {d.get('message', str(d)[:100])}")
            else:
                logger.info(f"QQ reply OK: {text[:30]}")
        except Exception as e:
            logger.error(f"QQ reply ex: {e}")

    @staticmethod
    def extract_text(data: dict) -> str:
        return data.get("content", "").strip()


def _connect_ws(bot: QQBot):
    import websocket
    url = _get_ws_url()
    if not url:
        logger.error("QQ WebSocket URL 获取失败")
        return

    ws = websocket.WebSocketApp(url,
        on_open=lambda ws: _on_open(ws, bot),
        on_message=lambda ws, msg: _on_message(ws, msg, bot),
        on_close=lambda ws, code, msg: _on_close(ws, code, msg, bot),
        on_error=lambda ws, err: logger.error(f"QQ WS err: {err}"),
    )
    bot._ws = ws

    def heartbeat():
        while bot._running:
            time.sleep(30)
            if bot._ws and bot._running:
                try:
                    bot._ws.send(json.dumps({"op": 1, "d": bot._seq}))
                except: break
    bot._heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    bot._heartbeat_thread.start()

    ws.run_forever(ping_interval=10, ping_timeout=5)


def _on_open(ws, bot):
    token = _get_access_token()
    if not token: return
    auth = {
        "op": 2,
        "d": {
            "token": f"QQBot {token}",
            "intents": 512 | 1 | 4096 | 33554432,  # Guilds + GuildMessages + DirectMessage + GroupC2C
            "shard": [0, 1],
        }
    }
    ws.send(json.dumps(auth))
    logger.info("QQ WS connected, auth sent")


def _on_message(ws, message, bot):
    try:
        data = json.loads(message)
        op = data.get("op", 0)
        bot._seq = data.get("s", bot._seq)

        if op == 10:  # Hello
            bot._session_id = data["d"].get("session_id", "")
            logger.info("QQ Hello, session ok")
        elif op == 0 and data.get("t") in ("MESSAGE_CREATE", "C2C_MESSAGE_CREATE", "AT_MESSAGE_CREATE", "DIRECT_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE"):
            d = data["d"]
            event_type = data["t"]
            text = d.get("content", "").strip()
            user_id = d.get("author", {}).get("id", "")
            channel_id = d.get("channel_id", "") or user_id  # C2C 没有 channel_id，用 user_id
            msg_id = d.get("id", "")

            if not text: return
            logger.info(f"QQ MSG[{event_type}]: {text[:50]}")

            replies = bot.process_message(text, user_id)
            for seq, r in enumerate(replies):
                bot.reply(channel_id, msg_id, r.get("content", ""), event_type, seq + 1)
    except Exception as e:
        logger.error(f"QQ msg err: {e}")


def _on_close(ws, code, msg, bot):
    logger.info(f"QQ WS closed: {code}, reconnecting in 3s...")
    if bot._running:
        time.sleep(3)
        _connect_ws(bot)


_bot = QQBot()

def main():
    print("QQ Bot WebSocket 启动中...")
    _bot.start()

if __name__ == "__main__":
    main()
