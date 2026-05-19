"""
钉钉 Bot 适配器
Webhook 路径: POST /dingtalk/webhook
提取消息: data["text"]["content"]
"""

import os
import time
import hmac
import hashlib
import base64
import logging
import requests
from flask import Flask, request, jsonify

from bot.adapter import BotAdapter

logger = logging.getLogger("pal.bot.dingtalk")

DINGTALK_APP_KEY = os.environ.get("DINGTALK_APP_KEY", "")
DINGTALK_APP_SECRET = os.environ.get("DINGTALK_APP_SECRET", "")
DINGTALK_API_BASE = "https://api.dingtalk.com/v1.0"

app = Flask(__name__)


class DingTalkBot(BotAdapter):
    """钉钉 频道适配器"""

    def __init__(self):
        super().__init__(name="dingtalk")
        self._access_token = None
        self._token_expires_at = 0

    def _get_access_token(self):
        """获取钉钉 access_token"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        timestamp = str(int(time.time() * 1000))
        sign_string = f"{timestamp}\n{DINGTALK_APP_SECRET}"
        signature = hmac.new(
            DINGTALK_APP_SECRET.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        sign = base64.b64encode(signature).decode("utf-8")

        url = (
            f"https://oapi.dingtalk.com/gettoken"
            f"?appkey={DINGTALK_APP_KEY}&appsecret={DINGTALK_APP_SECRET}"
        )
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get("errcode") == 0:
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
                return self._access_token
            else:
                logger.error("钉钉获取 token 失败: %s", data.get("errmsg"))
        except Exception as e:
            logger.error("钉钉获取 token 异常: %s", e)
        return None

    def start(self):
        logger.info("钉钉 Bot 已启动")
        port = int(os.environ.get("DINGTALK_PORT", 5104))
        app.run(host="0.0.0.0", port=port, debug=False)

    def stop(self):
        logger.info("钉钉 Bot 已停止")

    def reply(self, webhook_session: str, robot_code: str, user_id: str, text: str):
        """通过钉钉机器人回复消息"""
        token = self._get_access_token()
        if not token:
            logger.error("钉钉回复失败: 无 access_token")
            return

        url = f"{DINGTALK_API_BASE}/robot/oToMessages/batchSend"
        headers = {
            "x-acs-dingtalk-access-token": token,
            "Content-Type": "application/json",
        }
        payload = {
            "robotCode": robot_code,
            "userIds": [user_id],
            "msgKey": "sampleText",
            "msgParam": json.dumps({"content": text}),
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            logger.info("钉钉回复: %s, 结果: %s", text[:50], data)
        except Exception as e:
            logger.error("钉钉回复失败: %s", e)

    @staticmethod
    def extract_text(data: dict) -> str:
        text_field = data.get("text", {})
        if isinstance(text_field, dict):
            return text_field.get("content", "")
        return text_field


_bot = DingTalkBot()


@app.route("/dingtalk/webhook", methods=["POST"])
def dingtalk_webhook():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "invalid payload"}), 400

    text = _bot.extract_text(data)
    user_id = data.get("senderStaffId", "")
    robot_code = data.get("robotCode", "")
    session_webhook = data.get("sessionWebhook", "")

    if not text:
        return jsonify({"status": "no content"}), 200

    replies = _bot.process_message(text, user_id)
    for r in replies:
        _bot.reply(session_webhook, robot_code, user_id, r.get("content", ""))

    return jsonify({"status": "ok"}), 200


@app.route("/dingtalk/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "bot": "dingtalk"}), 200


def main():
    _bot.start()


if __name__ == "__main__":
    main()
