"""
上下文与 Token 管理器
- Token 估算（字符数 / 比例）
- 上下文压缩触发判断
- 对话历史维护
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime

from core.config import Config

logger = logging.getLogger("pal.context")


class ContextManager:
    """上下文管理器"""

    def __init__(self, session_id: str = "default", persona: str | None = None):
        self.session_id = session_id
        self.persona = persona or Config.PERSONA_NAME
        self.history: list[dict] = []  # [{role, content, timestamp}]
        self._compressed = False
        self._compression_summary = ""
        self._rebuild_first_round = False
        self.archive_dir = Config.PROJECT_ROOT / "file" / self.persona / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    # ── Token 估算 ───────────────────────────────────

    def estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数（中文约 1.5 字符/token，英文约 4 字符/token）"""
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / Config.TOKEN_ESTIMATION_RATIO)

    def current_usage_ratio(self, system_prompt: str) -> float:
        """估算当前上下文占用比例"""
        total_tokens = self.estimate_tokens(system_prompt)
        for msg in self.history:
            total_tokens += self.estimate_tokens(msg.get("content", ""))
        return total_tokens / Config.CONTEXT_WINDOW_TOKENS

    def should_compress(self, system_prompt: str) -> bool:
        """判断是否需要压缩"""
        ratio = self.current_usage_ratio(system_prompt)
        return ratio >= Config.CONTEXT_COMPRESSION_RATIO

    # ── 对话历史 ─────────────────────────────────────

    def add_user_message(self, content: str, timestamp: str | None = None):
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history.append({"role": "user", "content": content, "timestamp": ts})

    def add_assistant_message(self, content: str, timestamp: str | None = None):
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history.append({"role": "assistant", "content": content, "timestamp": ts})

    def add_assistant_raw(self, raw_response: str, timestamp: str | None = None):
        """保存模型原始输出（含 tool_call XML），用于下轮 API 消息"""
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history.append({"role": "assistant", "content": raw_response, "timestamp": ts, "raw": True})

    def get_history_messages(self, max_rounds: int | None = None) -> list[dict]:
        """获取 API 兼容的消息历史（user/assistant 交替）"""
        n = max_rounds or Config.MAX_HISTORY_ROUNDS
        recent = self.history[-n * 2:]
        messages = []
        for h in recent:
            role = h["role"]
            if role in ("user", "assistant", "system"):
                messages.append({"role": role, "content": h["content"]})
        return messages

    def add_system_turn(self, content: str):
        """记录一次系统轮次（不含工具调用）"""
        self.history.append({"role": "system", "content": content})

    def format_recent_history(self, rounds: int | None = None) -> str:
        """格式化最近 N 轮对话"""
        n = rounds or Config.MAX_HISTORY_ROUNDS
        recent = self.history[-n * 2:]  # user+assistant per round
        lines = []
        for msg in recent:
            role = msg["role"]
            ts = msg.get("timestamp", "")
            if role == "user":
                lines.append(f"Q:{msg['content']} [{ts}]")
            elif role == "assistant":
                lines.append(f"A:{msg['content']} [{ts}]")
        return "\n".join(lines)

    def format_recent_user_view(self, rounds: int | None = None) -> str:
        """格式化最近 N 轮的用户视角（用于重建）"""
        n = rounds or Config.REBUILD_HISTORY_ROUNDS
        recent = self.history[-n * 2:]
        lines = []
        for msg in recent:
            role = msg["role"]
            ts = msg.get("timestamp", "")
            if role == "user":
                lines.append(f"Q:{msg['content']} [{ts}]")
            elif role == "assistant":
                lines.append(f"A:{msg['content']} [{ts}]")
        return "\n".join(lines)

    # ── 压缩 ─────────────────────────────────────────

    @property
    def is_compressed(self) -> bool:
        return self._compressed

    @property
    def compression_summary(self) -> str:
        return self._compression_summary

    def mark_compressed(self, summary: str):
        """标记已压缩并存储摘要"""
        self._compressed = True
        self._compression_summary = summary
        self._rebuild_first_round = True

        # 存入 archive
        archive_path = self.archive_dir / f"archive_{int(time.time())}.json"
        archive_path.write_text(json.dumps({
            "session_id": self.session_id,
            "compressed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "history_rounds": len(self.history) // 2,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        # 只保留最近 N 轮
        keep = Config.REBUILD_HISTORY_ROUNDS * 2
        if len(self.history) > keep:
            self.history = self.history[-keep:]

    @property
    def is_rebuild_first_round(self) -> bool:
        """是否为压缩后的第一轮（需要注入摘要 + 历史消息列表）"""
        return self._rebuild_first_round

    def finish_rebuild_round(self):
        """标记重建轮次完成（后续不再注入用户消息列表）"""
        self._rebuild_first_round = False

    def reset(self):
        """重置上下文"""
        self.history = []
        self._compressed = False
        self._compression_summary = ""
        self._rebuild_first_round = False

    # ── 消息合并 ─────────────────────────────────────

    @staticmethod
    def should_merge(last_ts: str, current_ts: str) -> bool:
        """判断两条消息是否应合并（800ms 阈值）"""
        try:
            t1 = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            try:
                t1 = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return False
        try:
            t2 = datetime.strptime(current_ts, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            try:
                t2 = datetime.strptime(current_ts, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return False
        return abs((t2 - t1).total_seconds() * 1000) <= Config.MESSAGE_MERGE_MS
