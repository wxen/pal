"""
LINE Bot 适配器
Webhook 路径: POST /line/webhook
提取消息: data["events"][0]["message"]["text"]
"""

import os
import logging
import requests
from flask import Flask, request, jsonify

from bot.adapter import BotAdapter

logger = logging.getLogger("pal.bot.line")

LINE_API_BASE = "https://api.line.me/v2"
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

app = Flask(__name__)


class LineBot(BotAdapter):
    """LINE 频道适配器"""

    def __init__(self):
        super().__init__(name="line")

    def start(self):
        logger.info("LINE Bot 已启动")
        port = int(os.environ.get("LINE_PORT", 5103))
        app.run(host="0.0.0.0", port=port, debug=False)

    def stop(self):
        logger.info("LINE Bot 已停止")

    def reply(self, reply_token: str, messages: list[dict]):
        """通过 LINE Messaging API 回复消息"""
        url = f"{LINE_API_BASE}/bot/message/reply"
        headers = {
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "replyToken": reply_token,
            "messages": messages,
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info("LINE 回复成功，消息数: %d", len(messages))
        except Exception as e:
            logger.error("LINE 回复失败: %s", e)

    @staticmethod
    def extract_text(data: dict) -> str:
        events = data.get("events", [])
        if not events:
            return ""
        event = events[0]
        message = event.get("message", {})
        return message.get("text", "")


_bot = LineBot()


@app.route("/line/webhook", methods=["POST"])
def line_webhook():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "invalid payload"}), 400

    events = data.get("events", [])
    for event in events:
        if event.get("type") != "message" or event.get("message", {}).get("type") != "text":
            continue

        text = event.get("message", {}).get("text", "")
        reply_token = event.get("replyToken", "")
        user_id = event.get("source", {}).get("userId", "")

        if not text:
            continue

        replies = _bot.process_message(text, user_id)

        # 将回复转换为 LINE 消息格式
        line_messages = [
            {"type": "text", "text": r.get("content", "")}
            for r in replies
        ]
        if line_messages and reply_token:
            _bot.reply(reply_token, line_messages)

    return jsonify({"status": "ok"}), 200


@app.route("/line/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "bot": "line"}), 200


def main():
    _bot.start()


if __name__ == "__main__":
    main()
