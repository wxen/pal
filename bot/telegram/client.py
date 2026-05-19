"""
Telegram Bot 适配器
Webhook 路径: POST /telegram/webhook
提取消息: data["message"]["text"]
"""

import os
import logging
import requests
from flask import Flask, request, jsonify

from bot.adapter import BotAdapter

logger = logging.getLogger("pal.bot.telegram")

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

app = Flask(__name__)


class TelegramBot(BotAdapter):
    """Telegram 频道适配器"""

    def __init__(self):
        super().__init__(name="telegram")

    def start(self):
        logger.info("Telegram Bot 已启动")
        port = int(os.environ.get("TELEGRAM_PORT", 5101))
        app.run(host="0.0.0.0", port=port, debug=False)

    def stop(self):
        logger.info("Telegram Bot 已停止")

    def reply(self, chat_id: int, text: str):
        """通过 Telegram API 发送消息"""
        url = f"{TELEGRAM_API_BASE}/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("Telegram 回复成功: %s", text[:50])
        except Exception as e:
            logger.error("Telegram 回复失败: %s", e)

    @staticmethod
    def extract_text(data: dict) -> str:
        message = data.get("message", {})
        return message.get("text", "")


_bot = TelegramBot()


@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "invalid payload"}), 400

    text = _bot.extract_text(data)
    message = data.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id", 0)
    user_id = str(message.get("from", {}).get("id", ""))

    if not text:
        return jsonify({"status": "no content"}), 200

    replies = _bot.process_message(text, user_id)
    for r in replies:
        _bot.reply(chat_id, r.get("content", ""))

    return jsonify({"status": "ok"}), 200


@app.route("/telegram/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "bot": "telegram"}), 200


def main():
    _bot.start()


if __name__ == "__main__":
    main()
