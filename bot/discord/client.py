"""
Discord Bot 适配器
Webhook 路径: POST /discord/webhook
提取消息: data["content"]
"""

import os
import logging
import requests
from flask import Flask, request, jsonify

from bot.adapter import BotAdapter

logger = logging.getLogger("pal.bot.discord")

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "")

app = Flask(__name__)


class DiscordBot(BotAdapter):
    """Discord 频道适配器"""

    def __init__(self):
        super().__init__(name="discord")

    def start(self):
        logger.info("Discord Bot 已启动")
        port = int(os.environ.get("DISCORD_PORT", 5100))
        app.run(host="0.0.0.0", port=port, debug=False)

    def stop(self):
        logger.info("Discord Bot 已停止")

    def reply(self, channel_id: str, text: str):
        """通过 Discord API 发送消息到频道"""
        url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {"content": text}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info("Discord 回复成功: %s", text[:50])
        except Exception as e:
            logger.error("Discord 回复失败: %s", e)

    @staticmethod
    def extract_text(data: dict) -> str:
        return data.get("content", "")


_bot = DiscordBot()


@app.route("/discord/webhook", methods=["POST"])
def discord_webhook():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "invalid payload"}), 400

    text = _bot.extract_text(data)
    user_id = data.get("author", {}).get("id", "")
    channel_id = data.get("channel_id", DISCORD_CHANNEL_ID)

    if not text:
        return jsonify({"status": "no content"}), 200

    replies = _bot.process_message(text, user_id)
    for r in replies:
        _bot.reply(channel_id, r.get("content", ""))

    return jsonify({"status": "ok"}), 200


@app.route("/discord/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "bot": "discord"}), 200


def main():
    _bot.start()


if __name__ == "__main__":
    main()
