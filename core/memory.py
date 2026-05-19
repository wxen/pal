"""
记忆管理器
存储位置: /pal/file/{persona}/memory/
"""

import json
import time
from pathlib import Path

from core.config import Config


class MemoryManager:
    """长期记忆 CRUD"""

    def __init__(self, persona: str | None = None):
        self.persona = persona or Config.PERSONA_NAME
        self.dir = Config.PROJECT_ROOT / "file" / self.persona / "memory"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, title: str) -> Path:
        safe = title.replace("/", "_").replace("\\", "_").strip()
        return self.dir / f"{safe}.json"

    def save(self, title: str, content: str) -> dict:
        """保存记忆"""
        entry = {
            "title": title,
            "content": content,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._path(title).write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        return entry

    def update(self, title: str, content: str) -> dict | None:
        """更新记忆（保留创建时间）"""
        entry = self.get(title)
        if entry is None:
            return None
        entry["content"] = content
        entry["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._path(title).write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        return entry

    def delete(self, title: str) -> bool:
        """删除记忆"""
        path = self._path(title)
        if path.exists():
            path.unlink()
            return True
        return False

    def get(self, title: str) -> dict | None:
        """获取单条记忆"""
        path = self._path(title)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def list_all(self) -> list[dict]:
        """列出所有记忆"""
        memories = []
        for f in sorted(self.dir.glob("*.json")):
            try:
                memories.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, KeyError):
                pass
        return memories

    def format_for_prompt(self) -> str:
        """格式化为提示词可用的文本"""
        memories = self.list_all()
        if not memories:
            return ""
        lines = []
        for m in memories:
            lines.append(f"## {m['title']}")
            lines.append(m["content"])
            lines.append("")
        return "\n".join(lines).strip()
