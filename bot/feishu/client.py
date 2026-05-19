"""
飞书 Bot 适配器
Webhook 路径: POST /feishu/webhook
提取消息: data["event"]["message"]["content"]
"""

import os
import logging
import requests
from flask import Flask, request, jsonify

from bot.adapter import BotAdapter

logger = logging.getLogger("pal.bot.feishu")

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

app = Flask(__name__)


class FeishuBot(BotAdapter):
    """飞书 频道适配器"""

    def __init__(self):
        super().__init__(name="feishu")
        self._tenant_access_token = None

    def _get_tenant_access_token(self):
        """获取飞书 tenant_access_token"""
        if self._tenant_access_token:
            return self._tenant_access_token

        url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                self._tenant_access_token = data["tenant_access_token"]
                return self._tenant_access_token
            else:
                logger.error("飞书获取 token 失败: %s", data.get("msg"))
        except Exception as e:
            logger.error("飞书获取 token 异常: %s", e)
        return None

    def start(self):
        logger.info("飞书 Bot 已启动")
        port = int(os.environ.get("FEISHU_PORT", 5105))
        app.run(host="0.0.0.0", port=port, debug=False)

    def stop(self):
        logger.info("飞书 Bot 已停止")

    def reply(self, msg_id: str, text: str):
        """通过飞书 API 回复消息"""
        token = self._get_tenant_access_token()
        if not token:
            logger.error("飞书回复失败: 无 tenant_access_token")
            return

        url = f"{FEISHU_API_BASE}/im/v1/messages/{msg_id}/reply"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "content": json.dumps({"text": text}),
            "msg_type": "text",
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                logger.info("飞书回复成功: %s", text[:50])
            else:
                logger.error("飞书回复失败: %s", data.get("msg"))
        except Exception as e:
            logger.error("飞书回复失败: %s", e)

    @staticmethod
    def extract_text(data: dict) -> str:
        event = data.get("event", {})
        message = event.get("message", {})
        content_str = message.get("content", "{}")
        try:
            content = json.loads(content_str)
            return content.get("text", "")
        except (json.JSONDecodeError, TypeError):
            return content_str


_bot = FeishuBot()


@app.route("/feishu/webhook", methods=["POST"])
def feishu_webhook():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "invalid payload"}), 400

    # 飞书事件验证（URL 验证用 challenge）
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data.get("challenge")}), 200

    text = _bot.extract_text(data)
    event = data.get("event", {})
    message = event.get("message", {})
    msg_id = message.get("message_id", "")
    user_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")

    if not text:
        return jsonify({"status": "no content"}), 200

    replies = _bot.process_message(text, user_id)
    for r in replies:
        _bot.reply(msg_id, r.get("content", ""))

    return jsonify({"status": "ok"}), 200


@app.route("/feishu/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "bot": "feishu"}), 200


def main():
    _bot.start()


if __name__ == "__main__":
    main()
