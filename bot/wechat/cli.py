#!/usr/bin/env python3
"""
微信 ClawBot CLI
用法: python3 bot/wechat/cli.py
"""

import os
import sys
import json
import time
import base64
import logging
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from core.config import Config
from bot.wechat.client import WeChatClient
from bot.wechat.handler import WeChatHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pal.wechat")

STATE_DIR = Path(Config.FILE_DIR) / "wechat"
STATE_FILE = STATE_DIR / "session.json"


def save_session(client: WeChatClient):
    """保存登录状态到 file/wechat/"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "bot_token": client.bot_token,
        "ilink_user_id": client.ilink_user_id,
        "api_base_url": client.api_base_url,
        "bot_agent": client.bot_agent,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Session saved")


def load_session() -> dict | None:
    """加载上次登录状态"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def restore_client(client: WeChatClient, data: dict) -> bool:
    """从保存的状态恢复 client"""
    client.bot_token = data.get("bot_token")
    client.ilink_user_id = data.get("ilink_user_id")
    client.api_base_url = data.get("api_base_url")
    return client.is_logged_in()


def display_qr(qr_content: str):
    """在终端显示二维码"""
    # qrcode_img_content 现在是 URL（如 https://liteapp.weixin.qq.com/...）
    # 但也可能直接就是 base64 图片
    qr_text = qr_content

    # 如果是 URL 就直接用它生成 QR
    try:
        import qrcode
        qr = qrcode.QRCode()
        qr.add_data(qr_text)
        qr.make()
        qr.print_ascii(invert=True)
        return
    except ImportError:
        pass

    # 降级：保存 URL 文本
    print(f"\n二维码内容（URL）:")
    print(f"  {qr_text[:120]}")
    print(f"\n请复制到浏览器打开，或在微信中打开此链接")


def main():
    print("╔══════════════════════════════════╗")
    print("║   Pal - 微信 ClawBot 登录       ║")
    print(f"║   Persona: {Config.PERSONA_NAME:<20} ║")
    print("╚══════════════════════════════════╝")
    print()

    client = WeChatClient(bot_agent="Pal")
    handler = WeChatHandler()

    # ── 尝试恢复会话 ──
    saved = load_session()
    if saved:
        if restore_client(client, saved):
            print(f"[*] 已恢复登录: user={client.ilink_user_id}")
            print(f"    保存时间: {saved.get('saved_at', 'unknown')}")
            resp = input("\n使用已有登录? [Y/n] ").strip().lower()
            if resp in ("", "y", "yes"):
                handler.register_with_client(client)
                print("[*] 启动消息轮询...\n")
                try:
                    client.run_forever()
                except KeyboardInterrupt:
                    print("\n[*] 停止")
                return
            else:
                print("[*] 重新登录...")
        else:
            print("[*] 保存的会话已失效，重新登录")

    # ── QR 码登录 ──
    print("[*] 获取登录二维码...\n")

    def on_qr_received(qr_content: str):
        display_qr(qr_content)
        print("\n请用微信扫描上方二维码 (300秒内)")
        print("微信路径: 我 → 设置 → 插件 → 微信 ClawBot\n")

    try:
        success = client.login_with_qr(on_qr=on_qr_received, timeout=300)
    except KeyboardInterrupt:
        print("\n[*] 登录取消")
        return

    if not success:
        print("\n[!] 登录失败或超时")
        return

    print(f"\n[OK] 登录成功! user={client.ilink_user_id}")

    # 保存会话
    save_session(client)

    # ── 注册处理器并启动 ──
    handler.register_with_client(client)
    print(f"[*] Persona: {Config.PERSONA_NAME}")
    print(f"[*] Model: {'Mock' if handler.mock_mode() else Config.DEEPSEEK_MODEL}")
    print("[*] 开始接收消息 (Ctrl+C 停止)...\n")

    try:
        client.run_forever()
    except KeyboardInterrupt:
        print("\n[*] 停止服务")


if __name__ == "__main__":
    main()
