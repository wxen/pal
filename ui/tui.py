#!/usr/bin/env python3
"""
Pal TUI — 原生终端全功能管理界面
与 CLI 共享同一 launcher 单例，零状态割裂
"""

import os, sys, time, json
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, Button, Input, Select, Switch,
    ListView, ListItem, Label, TextArea, TabbedContent, TabPane,
    RichLog, DataTable, ProgressBar, LoadingIndicator,
)
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import Screen, ModalScreen

from core.config import Config
from core.agent import AgentManager
from core.launcher import launcher


# ── 配色主题 ──────────────────────────────────────────

DARK_CSS = """
Screen { background: #121212; }
Header { background: #1e1e2e; color: #e0e0e0; }
Footer { background: #1e1e2e; }
Static { color: #e0e0e0; }
DataTable { background: #1e1e2e; }
DataTable > .datatable--header { background: #3700b3; color: #ffffff; }
DataTable > .datatable--cursor { background: #bb86fc; color: #121212; }
RichLog { background: #0d0d0d; color: #e0e0e0; }
Button { background: #3700b3; color: #ffffff; }
Button:hover { background: #bb86fc; }
Select { background: #1e1e2e; color: #e0e0e0; }
Input { background: #1e1e2e; color: #e0e0e0; }
TabbedContent Tab { background: #1e1e2e; }
TabbedContent Tab.--active { background: #3700b3; }
Switch { color: #bb86fc; }
.modal { border: solid #bb86fc; }
"""

# ── 数据 ──────────────────────────────────────────────

LANG_LABELS = {"zh":"简体中文","en":"English","ja":"日本語","ko":"한국어","de":"Deutsch",
               "es":"Español","fr":"Français","pt":"Português","ru":"Русский","ar":"العربية","id":"Indonesia"}

BOTS = ["wechat","discord","telegram","slack","line","dingtalk","feishu","qq"]

PROVIDERS = {
    "deepseek": {"base": "https://api.deepseek.com/v1", "models": ["deepseek-chat","deepseek-reasoner"], "max_tokens": 65536},
    "openai": {"base": "https://api.openai-proxy.org/v1", "models": ["gpt-5.4-mini","gpt-5.4","gpt-5.5","gpt-5.4-nano"], "max_tokens": 128000},
    "claude": {"base": "https://api.openai-proxy.org/anthropic", "models": ["claude-sonnet-4-6-20250514","claude-opus-4-7-20250514","claude-haiku-4-5-20251001"], "max_tokens": 200000},
    "gemini": {"base": "https://api.openai-proxy.org/google", "models": ["gemini-2.5-flash","gemini-2.5-pro"], "max_tokens": 1048576},
    "kimi": {"base": "https://api.moonshot.cn/v1", "models": ["moonshot-v1-8k","moonshot-v1-32k","moonshot-v1-128k"], "max_tokens": 128000},
    "kimi-global": {"base": "https://api.moonshot.ai/v1", "models": ["moonshot-v1-8k","moonshot-v1-32k","moonshot-v1-128k"], "max_tokens": 128000},
    "qwen": {"base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "models": ["qwen-plus","qwen-max","qwen-turbo"], "max_tokens": 131072},
    "glm": {"base": "https://open.bigmodel.cn/api/paas/v4", "models": ["glm-4-flash","glm-4-plus","glm-4"], "max_tokens": 128000},
    "mistral": {"base": "https://api.mistral.ai/v1", "models": ["mistral-small-latest","mistral-large-latest"], "max_tokens": 128000},
    "minimax": {"base": "https://api.minimaxi.com/v1", "models": ["abab6.5s-chat","abab7-chat"], "max_tokens": 245760},
    "ollama": {"base": "http://localhost:11434/v1", "models": [], "max_tokens": 4096},
}


# ── Agent 编辑弹窗 ───────────────────────────────────

class AgentEditScreen(ModalScreen):
    """Agent 编辑/创建弹窗"""

    def __init__(self, agent_name: str = None):
        super().__init__()
        self.agent_name = agent_name
        self.cfg = AgentManager.load(agent_name) if agent_name else {}

    def compose(self) -> ComposeResult:
        title = f"Edit: {self.agent_name}" if self.agent_name else "New Agent"
        with Container(classes="modal"):
            yield Static(f"[bold]{title}[/bold]", classes="title")
            with Horizontal(classes="row"):
                yield Static("Name")
                yield Input(value=self.agent_name or "", id="agent_name", placeholder="agent name")
            with Horizontal(classes="row"):
                yield Static("Description")
                yield Input(value=self.cfg.get("description",""), id="desc", placeholder="brief description")
            with Horizontal(classes="row"):
                yield Static("Language")
                lang_opts = [(LANG_LABELS.get(c, c), c) for c in sorted(LANG_LABELS)]
                yield Select(lang_opts, id="lang", value=self.cfg.get("lang","zh"))
            with Horizontal(classes="row"):
                yield Static("API Provider")
                prov_opts = [(p, p) for p in PROVIDERS]
                yield Select(prov_opts, id="provider", value=self.cfg.get("api_provider","deepseek"))
            with Horizontal(classes="row"):
                yield Static("Model")
                prov = self.cfg.get("api_provider","deepseek")
                models = PROVIDERS.get(prov, {}).get("models",["default"])
                model_opts = [(m, m) for m in models]
                yield Select(model_opts, id="model", value=self.cfg.get("api_model","") or models[0])
            with Horizontal(classes="row"):
                yield Static("Bot Channel")
                bot_opts = [(b, b) for b in BOTS]
                yield Select(bot_opts, id="bot", value=self.cfg.get("bot","wechat"))
            with Horizontal(classes="row"):
                yield Static("Context Mode")
                yield Select([("Auto-compress","auto"),("Single-round","single"),("Rolling","rolling")], id="context_mode", value=self.cfg.get("context_mode","auto"))
            with Horizontal(classes="row"):
                yield Static("Active Msg")
                yield Switch(value=self.cfg.get("active_message",False), id="active_msg")
            with Horizontal(classes="row"):
                yield Static("Launch Mode")
                yield Select([("Silent", "silent"), ("Monitor", "monitor"), ("Log file", "log"), ("Both", "both")], id="launch_mode", value=self.cfg.get("launch_mode","silent"))
            with Horizontal(classes="row"):
                yield Button("Save", variant="primary", id="btn_save")
                yield Button("Cancel", variant="default", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(None)
            return
        name = self.query_one("#agent_name", Input).value.strip()
        if not name:
            return
        data = {
            "description": self.query_one("#desc", Input).value,
            "lang": self.query_one("#lang", Select).value,
            "api_provider": self.query_one("#provider", Select).value,
            "api_model": self.query_one("#model", Select).value,
            "bot": self.query_one("#bot", Select).value,
            "context_mode": self.query_one("#context_mode", Select).value,
            "active_message": self.query_one("#active_msg", Switch).value,
            "launch_mode": self.query_one("#launch_mode", Select).value,
        }
        if self.agent_name and self.agent_name != name:
            # Rename
            old_cfg = AgentManager.load(self.agent_name)
            AgentManager.delete(self.agent_name)
            AgentManager.create(name, **{**old_cfg, **data})
        elif self.agent_name:
            AgentManager.update(name, **data)
        else:
            AgentManager.create(name, **data)
        self.dismiss(name)


# ── 主应用 ────────────────────────────────────────────

class PalTUI(App):
    """Pal 终端管理界面"""

    CSS = DARK_CSS + """
    Screen { align: center middle; }
    .modal { width: 60; height: auto; border: solid $primary; padding: 1; background: #1e1e2e; }
    .title { text-style: bold; padding-bottom: 1; color: #bb86fc; }
    .row { height: 3; margin-bottom: 1; align: left middle; }
    .row Static { width: 14; color: #e0e0e0; }
    .row Input, .row Select { width: 40; }
    .row Switch { margin-left: 14; }
    """

    BINDINGS = [
        Binding("d", "show_dashboard", "Dashboard"),
        Binding("a", "show_agents", "Agents"),
        Binding("l", "show_logs", "Logs"),
        Binding("q", "quit", "Quit"),
        Binding("n", "new_agent", "New"),
        Binding("e", "edit_agent", "Edit"),
        Binding("s", "toggle_agent", "Start/Stop"),
    ]

    def compose(self) -> ComposeResult:
        self._dash_summary = Static("Loading...")
        self._dash_table = DataTable()
        self._agents_table = DataTable()
        self._log_select = Select([], id="log_agent_select")
        self._log_view = RichLog(highlight=True, markup=True)
        yield Header()
        with TabbedContent():
            with TabPane("Dashboard", id="tab_dashboard"):
                yield self._dash_summary
                yield self._dash_table
            with TabPane("Agents", id="tab_agents"):
                yield self._agents_table
            with TabPane("Logs", id="tab_logs"):
                with Horizontal(id="log_toolbar"):
                    yield self._log_select
                    yield Button("Refresh", id="btn_refresh_log")
                yield self._log_view
        yield Footer()

    def on_mount(self):
        self._refresh()
        self.set_interval(2, self._refresh)

    def _refresh(self):
        try:
            self._refresh_dashboard()
            self._refresh_agents()
            self._refresh_log_selector()
        except Exception as e:
            pass

    def _refresh_dashboard(self):
        agents = AgentManager.list_agents()
        running = sum(1 for a in agents if launcher.is_running(a))
        self._dash_summary.update(f"  Agents: {len(agents)}  |  Running: {running}/{len(agents)}  |  Stopped: {len(agents)-running}")
        if not self._dash_table.columns:
            self._dash_table.add_columns("Name", "Status", "Bot", "Lang", "API")
        self._dash_table.clear()
        for name in agents:
            cfg = AgentManager.load(name) or {}
            status = "[green]● Running[/green]" if launcher.is_running(name) else "[dim]○ Stopped[/dim]"
            self._dash_table.add_row(name, status, cfg.get("bot","?"), cfg.get("lang","?"), cfg.get("api_provider","?"))

    def _refresh_agents(self):
        if not self._agents_table.columns:
            self._agents_table.add_columns("Name", "Status", "Bot", "Lang", "API Provider", "Model", "Mode")
        self._agents_table.clear()
        for name in AgentManager.list_agents():
            cfg = AgentManager.load(name) or {}
            status = "● Running" if launcher.is_running(name) else "○ Stopped"
            self._agents_table.add_row(name, status, cfg.get("bot","?"), cfg.get("lang","?"),
                         cfg.get("api_provider","?"), cfg.get("api_model","?"), cfg.get("context_mode","?"))

    def _refresh_log_selector(self):
        agents = [a for a in AgentManager.list_agents() if launcher.is_running(a)]
        self._log_select.set_options([(a, a) for a in agents])

    async def _refresh_logs(self):
        name = self._log_select.value
        self._log_view.clear()
        if name and name != Select.BLANK:
            for line in launcher.logs.get(str(name), [])[-100:]:
                self._log_view.write(line)

    def action_show_dashboard(self):
        self.query_one(TabbedContent).active = "tab_dashboard"
    def action_show_agents(self):
        self.query_one(TabbedContent).active = "tab_agents"
    def action_show_logs(self):
        self.query_one(TabbedContent).active = "tab_logs"
    def action_new_agent(self):
        self.push_screen(AgentEditScreen(), self._on_saved)
    def action_edit_agent(self):
        try:
            row = self._agents_table.cursor_row
            name = str(self._agents_table.get_row(row)[0])
            self.push_screen(AgentEditScreen(name), self._on_saved)
        except Exception:
            pass
    def action_toggle_agent(self):
        try:
            row = self._agents_table.cursor_row
            name = str(self._agents_table.get_row(row)[0])
            if launcher.is_running(name): launcher.stop([name])
            else: launcher.start([name])
        except Exception:
            pass
    def _on_saved(self, result):
        self._refresh()
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_refresh_log":
            self._refresh_logs()
    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "log_agent_select":
            self._refresh_logs()
        elif event.select.id == "provider":
            prov = event.value
            if prov and prov != Select.BLANK:
                models = PROVIDERS.get(str(prov), {}).get("models", ["default"])
                self.query_one("#model", Select).set_options([(m, m) for m in models])


def main():
    app = PalTUI()
    app.run()


if __name__ == "__main__":
    main()
