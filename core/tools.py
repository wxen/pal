"""
工具加载器与执行器
- 从 /pal/tool/{persona}/tool.json 加载工具描述
- 从 /pal/tool/{persona}/tools/ 动态导入 Python 实现
"""

import json
import importlib.util
import logging
from pathlib import Path

from core.config import Config

logger = logging.getLogger("pal.tools")


class ToolRegistry:
    """工具注册表"""

    def __init__(self, persona: str | None = None):
        self.persona = persona or Config.PERSONA_NAME
        self.tool_dir = Config.PROJECT_ROOT / "tool" / self.persona
        self.defs_path = self.tool_dir / "tool.json"
        self.impl_dir = self.tool_dir / "tools"
        self.impl_dir.mkdir(parents=True, exist_ok=True)

        self._definitions: list[dict] = []
        self._implementations: dict[str, callable] = {}
        self._reload()

    def _reload(self):
        """重新加载工具定义"""
        self._definitions = []
        if self.defs_path.exists():
            try:
                data = json.loads(self.defs_path.read_text(encoding="utf-8"))
                self._definitions = data if isinstance(data, list) else []
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"工具定义加载失败: {e}")

        # 动态导入实现
        self._implementations = {}
        for tool in self._definitions:
            name = tool.get("name", "")
            if not name:
                continue
            py_path = self.impl_dir / f"{name}.py"
            if py_path.exists():
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"pal_tool_{name}", str(py_path)
                    )
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "execute"):
                        self._implementations[name] = mod.execute
                        logger.debug(f"已加载工具: {name}")
                except Exception as e:
                    logger.error(f"加载工具 {name} 失败: {e}")

    def get_definitions(self) -> list[dict]:
        """获取所有工具定义"""
        return self._definitions

    def format_for_prompt(self) -> str:
        """格式化为提示词文本"""
        if not self._definitions:
            return ""
        lines = []
        for tool in self._definitions:
            name = tool.get("name", "")
            desc = tool.get("description", "")
            lines.append(f"## {name}")
            lines.append(desc)
            lines.append("")
            lines.append("用法：")
            for param, pdesc in tool.get("parameters", {}).items():
                lines.append(f"- {param}（{pdesc}）")
            notes = tool.get("notes", [])
            if notes:
                lines.append("")
                lines.append("重要说明：")
                for note in notes:
                    lines.append(f"- {note}")
            lines.append("")
        return "\n".join(lines).strip()

    def execute(self, name: str, params: dict) -> dict | str:
        """执行工具调用"""
        if name in self._implementations:
            try:
                result = self._implementations[name](**params)
                return result
            except Exception as e:
                logger.error(f"工具 {name} 执行失败: {e}")
                return {"error": str(e)}
        # 内置工具由 engine 处理
        return None

    def has_tool(self, name: str) -> bool:
        return name in self._implementations or name in {
            "SendMessage", "ScheduledMessage", "MemorySave",
            "MemoryUpdate", "MemoryDelete"
        }

    def reload(self):
        """手动重新加载"""
        self._reload()
