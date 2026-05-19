"""
交互式引导创建向导
"""

import os
import sys
import json
from pathlib import Path

from core.config import Config
from core.agent import AgentManager


# ── 工具函数 ──────────────────────────────────────────────

def _input(prompt: str, default: str = "") -> str:
    """读取用户输入"""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def _menu(title: str, options: list[str], multi: bool = False) -> list[int] | int | None:
    """简单菜单选择（数字输入，无 curses 依赖）"""
    print(f"\n  {title}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    if multi:
        sel = input("  Select (comma-separated, 0=done): ").strip()
        if not sel or sel == "0":
            return []
        try:
            return [int(x.strip()) - 1 for x in sel.split(",")]
        except ValueError:
            return []
    else:
        try:
            sel = int(input("  Select: ").strip()) - 1
            if 0 <= sel < len(options):
                return sel
        except ValueError:
            pass
        return None


# ── Banner ──────────────────────────────────────────────

def show_banner():
    """显示项目标识"""
    # Load image art
    banner_path = Config.PROJECT_ROOT / "core" / "banner.txt"
    if banner_path.exists():
        print(banner_path.read_text(encoding="utf-8"))
    else:
        print("""
   ██████╗  █████╗ ██╗
   ██╔══██╗██╔══██╗██║
   ██████╔╝███████║██║
   ██╔═══╝ ██╔══██║██║
   ██║     ██║  ██║███████╗
   ╚═╝     ╚═╝  ╚═╝╚══════╝
""")
    print("  pal - AI Role-Playing Chat Framework")
    print("  Developer: Wang Xi (China)")
    print()
    print("  DISCLAIMER: Messages are sent directly to the API provider.")
    print("  No third-party data collection. Users are responsible for")
    print("  their own privacy. Do not share sensitive information.")
    print()
    print("  Type 'pal --help' or 'pal -h' for commands.")
    print()


# ── Wizard ──────────────────────────────────────────────

def run_wizard(name: str | None = None):
    """运行交互式引导创建"""
    show_banner()
    print("  === Agent Creation Wizard ===\n")

    # 1. Agent name
    if not name:
        name = _input("Agent name")
        if not name:
            print("  Agent name is required.")
            return
    if AgentManager.exists(name):
        print(f"  Agent '{name}' already exists. Editing...")
        config = AgentManager.load(name)
    else:
        config = AgentManager.create(name)

    # 2. Description
    desc = _input("Description", config.get("description", ""))
    AgentManager.update(name, description=desc)

    # 3. Language
    lang_dir = Config.LANG_DIR
    langs = sorted([f.stem for f in lang_dir.glob("*.json")])
    display_langs = [f"{l} ({_lang_label(l)})" for l in langs]
    choice = _menu("Native Language", display_langs + ["[Back]"])
    if choice is not None and choice < len(langs):
        AgentManager.update(name, lang=langs[choice])
        print(f"  Language set: {langs[choice]}")

    # 4. Persona
    print("\n  === Persona ===")
    choice = _menu("Persona Source", ["File path (absolute)", "Direct input", "[Back]"])
    if choice == 0:
        path = _input("Absolute file path")
        if path and os.path.exists(path):
            # Copy/extract to agent persona dir
            dest = AgentManager.get_persona_path(name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            content = Path(path).read_text(encoding="utf-8")
            dest.write_text(content, encoding="utf-8")
            AgentManager.update(name, persona_path=str(dest))
            print(f"  Persona saved: {dest}")
    elif choice == 1:
        text = input("  Enter persona text (end with empty line):\n")
        lines = [text]
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        content = "\n".join(lines)
        dest = AgentManager.get_persona_path(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        AgentManager.update(name, persona_path=str(dest))

    # 5. Message delay
    choice = _menu("Message Delay (simulate typing)", ["Enable", "Disable", "[Back]"])
    if choice == 0:
        AgentManager.update(name, message_delay=True)
    elif choice == 1:
        AgentManager.update(name, message_delay=False)

    # 6. Active messaging
    choice = _menu("Active Messaging", ["Enable", "Disable", "[Back]"])
    if choice == 0:
        intensity = _input("Intensity (0-100)", "30")
        try:
            AgentManager.update(name, active_message=True, active_intensity=int(intensity))
        except ValueError:
            AgentManager.update(name, active_message=True, active_intensity=30)
    elif choice == 1:
        AgentManager.update(name, active_message=False)

    # 7. Context mode
    choice = _menu("Context Mode", [
        "Single-round (no memory tools)",
        "Rolling (simple overflow cutoff)",
        "Auto-compress (summary-based rebuild)",
        "[Back]"
    ])
    modes = ["single", "rolling", "auto"]
    if choice is not None and choice < 3:
        AgentManager.update(name, context_mode=modes[choice])
        if choice == 2:  # auto
            threshold = _input("Compression threshold % (0-100)", "80")
            try:
                AgentManager.update(name, context_threshold=int(threshold))
            except ValueError:
                pass

    # 8. API provider
    providers = ["deepseek", "openai", "claude", "gemini", "kimi", "qwen",
                 "glm", "mistral", "minimax", "ollama", "custom_openai", "custom_anthropic"]
    choice = _menu("API Provider", [p.replace("_", " ").title() for p in providers] + ["[Back]"])
    if choice is not None and choice < len(providers):
        prov = providers[choice]
        if prov in ("ollama", "custom_openai", "custom_anthropic"):
            url = _input("API Base URL")
            multimodal = _menu("Multimodal Capabilities",
                               ["Image", "Voice", "Document", "None"],
                               multi=True)
            caps = []
            if multimodal and 0 in multimodal: caps.append("image")
            if multimodal and 1 in multimodal: caps.append("voice")
            if multimodal and 2 in multimodal: caps.append("document")
            max_tok = _input("Max tokens", "4096")
            AgentManager.update(name, api_provider=prov, api_key="",
                              api_model="", api_max_tokens=int(max_tok),
                              api_multimodal=caps,
                              bot_config={"base_url": url})
        else:
            key = _input("API Key (leave empty to use .env)")
            AgentManager.update(name, api_provider=prov, api_key=key)

    # 9. Bot / Gateway
    bots = ["wechat", "discord", "telegram", "slack", "line", "dingtalk", "feishu", "qq"]
    choice = _menu("Messaging Channel", [b.title() for b in bots] + ["[Back]"])
    if choice is not None and choice < len(bots):
        bot = bots[choice]
        AgentManager.update(name, bot=bot)
        if bot == "wechat":
            print("  WeChat setup: run 'pal start {0}' to scan QR code".format(name))

    # 10. Launch mode
    choice = _menu("Launch Mode", [
        "Silent (background)",
        "Monitor (terminal output)",
        "Log to file",
        "Both (monitor + log)",
        "[Back]"
    ])
    modes = ["silent", "monitor", "log", "both"]
    if choice is not None and choice < 4:
        AgentManager.update(name, launch_mode=modes[choice])
        if choice in (2, 3):  # log or both
            path = _input("Log path (absolute, or leave empty for default)")
            if path:
                AgentManager.update(name, log_path=path)

    print(f"\n  Agent '{name}' configured successfully!")
    print(f"  Start with: pal start {name}")


def _lang_label(code: str) -> str:
    labels = {"zh": "CN", "en": "EN", "ja": "JP", "ko": "KR", "de": "DE",
              "es": "ES", "fr": "FR", "pt": "PT", "ru": "RU", "ar": "AR",
              "id": "ID"}
    return labels.get(code, code.upper())
