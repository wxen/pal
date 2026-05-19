"""
多 Agent 启动器（单例）
CLI 和 UI 共享同一实例，状态全局一致
"""

import os, sys, json, time, logging, threading
from pathlib import Path
from core.config import Config
from core.agent import AgentManager

logger = logging.getLogger("pal.launcher")

# ── 共享状态（单例）────────────────────────────────

class AgentLauncher:
    """多 Agent 管理器 — 全局唯一实例"""

    def __init__(self):
        self._threads: dict[str, threading.Thread] = {}
        self._status: dict[str, dict] = {}   # name -> {status, started_at, bot, ...}
        self.logs: dict[str, list] = {}       # name -> [log_line, ...]
        self._lock = threading.Lock()

    # ── 日志 ──────────────────────────────────

    def _log(self, name: str, msg: str):
        with self._lock:
            self.logs.setdefault(name, []).append(
                f"{time.strftime('%H:%M:%S')} {msg}"
            )
        logger.info(f"[{name}] {msg}")

    # ── 控制 ──────────────────────────────────

    def start(self, names: list[str]):
        for name in names:
            if not AgentManager.exists(name):
                self._log("system", f"Agent '{name}' not found")
                continue
            if self.is_running(name):
                self._log("system", f"Agent '{name}' already running")
                continue
            cfg = AgentManager.load(name)
            with self._lock:
                self._status[name] = {"status": "starting", "started_at": time.time(),
                                       "bot": cfg.get("bot", "?"), "lang": cfg.get("lang", "zh")}
            t = threading.Thread(target=self._run_agent, args=(name, cfg), daemon=True)
            t.start()
            with self._lock:
                self._threads[name] = t

    def start_all(self):
        names = AgentManager.list_agents()
        if not names:
            print("  No agents found.")
            return
        self.start(names)

    def stop(self, names: list[str] | None = None):
        targets = names or list(self._threads.keys())
        for name in targets:
            if name in self._status:
                with self._lock:
                    self._status[name]["status"] = "stopping"
                    self._status[name]["stopped_at"] = time.time()
                self._log(name, "Stopped")
        # Give threads a moment, then clean up
        for name in targets:
            self._threads.pop(name, None)
            if name in self._status:
                self._status[name]["status"] = "stopped"

    def restart(self, names: list[str] | None = None):
        targets = names or list(self._threads.keys())
        self.stop(targets)
        self.start(targets)

    def is_running(self, name: str) -> bool:
        return name in self._threads and self._threads[name].is_alive()

    def get_status(self, name: str | None = None) -> dict:
        """获取单个或全部 agent 运行状态"""
        if name:
            return self._status.get(name, {})
        return dict(self._status)

    # ── Agent 运行器 ──────────────────────────

    def _run_agent(self, name: str, cfg: dict):
        bot = cfg.get("bot", "wechat")
        try:
            with self._lock:
                self._status[name]["status"] = "running"
            if bot == "wechat":
                self._run_wechat(name, cfg)
            else:
                self._log(name, f"Bot '{bot}': use 'python3 main.py {bot}' directly")
        except Exception as e:
            self._log(name, f"CRASH: {e}")
            with self._lock:
                self._status[name]["status"] = "error"

    def _run_wechat(self, name: str, cfg: dict):
        from bot.wechat.client import WeChatClient
        from core.engine import PalEngine

        wc = WeChatClient(bot_agent=name)
        agent_dir = Config.PROJECT_ROOT / "agent" / name
        session_file = agent_dir / "wechat_session.json"

        if session_file.exists():
            sess = json.loads(session_file.read_text(encoding="utf-8"))
            wc.bot_token = sess.get("bot_token")
            wc.ilink_user_id = sess.get("ilink_user_id")
            wc.api_base_url = sess.get("api_base_url")

        if not wc.is_logged_in():
            qr = wc.get_qr_code()
            qr_url = qr.get("qrcode_img_content", "")
            self._log(name, f"QR: {qr_url}")
            session = qr.get("qrcode", "")
            deadline = time.time() + 300
            while time.time() < deadline and self.is_running(name):
                resp = wc.poll_qr_status(session, timeout=20)
                if resp.get("bot_token"):
                    wc.bot_token = resp["bot_token"]
                    wc.ilink_user_id = resp.get("ilink_user_id", "")
                    wc.api_base_url = resp.get("baseurl", "https://ilinkai.weixin.qq.com")
                    session_file.parent.mkdir(parents=True, exist_ok=True)
                    session_file.write_text(json.dumps({
                        "bot_token": wc.bot_token, "ilink_user_id": wc.ilink_user_id,
                        "api_base_url": wc.api_base_url,
                    }))
                    self._log(name, "Logged in")
                    break
                elif resp.get("status") in ("expired", "binded_redirect"):
                    self._log(name, "QR expired")
                    return
                time.sleep(3)
            else:
                self._log(name, "QR timeout")
                return

        engine = PalEngine(session_id=name)
        self._log(name, "Message loop started")

        while self.is_running(name):
            try:
                resp = wc.get_updates(timeout=45)
                for msg in resp.get("msgs", []):
                    if msg.get("message_type") != 1:
                        continue
                    uid, ctx = msg.get("from_user_id", ""), msg.get("context_token", "")
                    text = ""
                    for item in msg.get("item_list", []):
                        if item.get("type") == 1:
                            text = item.get("text_item", {}).get("text", "").strip()
                            break
                    if not text:
                        continue
                    self._log(name, f"RECV: {text[:80]}")
                    results = engine.process(text)
                    for r in results:
                        if r["type"] == "send":
                            wc.send_message(uid, r["content"], ctx)
                            self._log(name, f"SEND: {r['content'][:80]}")
            except Exception as e:
                self._log(name, f"Loop: {e}")
                time.sleep(5)


# ── 全局单例 ──────────────────────────────────

launcher = AgentLauncher()
