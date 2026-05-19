"""
Slack Bot 适配器
Webhook 路径: POST /slack/webhook
提取消息: data["event"]["text"]
"""

import os
import logging
import requests
from flask import Flask, request, jsonify

from bot.adapter import BotAdapter

logger = logging.getLogger("pal.bot.slack")

SLACK_API_BASE = "https://slack.com/api"
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

app = Flask(__name__)


class SlackBot(BotAdapter):
    """Slack 频道适配器"""

    def __init__(self):
        super().__init__(name="slack")

    def start(self):
        logger.info("Slack Bot 已启动")
        port = int(os.environ.get("SLACK_PORT", 5102))
        app.run(host="0.0.0.0", port=port, debug=False)

    def stop(self):
        logger.info("Slack Bot 已停止")

    def reply(self, channel_id: str, text: str):
        """通过 Slack API chat.postMessage 发送消息"""
        url = f"{SLACK_API_BASE}/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "channel": channel_id,
            "text": text,
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            if not data.get("ok"):
                logger.error("Slack 回复失败: %s", data.get("error", "unknown"))
                return
            logger.info("Slack 回复成功: %s", text[:50])
        except Exception as e:
            logger.error("Slack 回复失败: %s", e)

    @staticmethod
    def extract_text(data: dict) -> str:
        event = data.get("event", {})
        return event.get("text", "")


_bot = SlackBot()


@app.route("/slack/webhook", methods=["POST"])
def slack_webhook():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "invalid payload"}), 400

    # Slack 事件验证（URL 验证用 challenge）
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data.get("challenge")}), 200

    text = _bot.extract_text(data)
    event = data.get("event", {})
    channel_id = event.get("channel", "")
    user_id = event.get("user", "")

    # 忽略机器人自己发送的消息
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return jsonify({"status": "ignored"}), 200

    if not text:
        return jsonify({"status": "no content"}), 200

    replies = _bot.process_message(text, user_id)
    for r in replies:
        _bot.reply(channel_id, r.get("content", ""))

    return jsonify({"status": "ok"}), 200


@app.route("/slack/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "bot": "slack"}), 200


def main():
    _bot.start()


if __name__ == "__main__":
    main()
