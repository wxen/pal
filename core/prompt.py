"""
提示词构建器
组装系统提示词：基础模板 + 人格 + 工具 + 记忆 + 对话历史 + 用户消息
处理正常模式和压缩后重建模式
"""

import json
import time
import logging
from pathlib import Path

from core.config import Config
from core.persona import load_persona_with_system

logger = logging.getLogger("pal.prompt")


class PromptBuilder:
    """提示词组装器"""

    def __init__(self, lang: str | None = None, persona: str | None = None):
        self.lang = lang or Config.LANG
        self.persona = persona or Config.PERSONA_NAME
        self._lang_data: dict = {}
        self._load_lang()

    def _load_lang(self):
        """加载语言 JSON"""
        path = Config.LANG_DIR / f"{self.lang}.json"
        if path.exists():
            self._lang_data = json.loads(path.read_text(encoding="utf-8"))
        else:
            # fallback to zh
            fallback = Config.LANG_DIR / "zh.json"
            if fallback.exists():
                self._lang_data = json.loads(fallback.read_text(encoding="utf-8"))

    def _t(self, *keys) -> str:
        """获取翻译文本，支持多级 key 访问"""
        data = self._lang_data
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k, "")
            else:
                return ""
        return data if isinstance(data, str) else ""

    def _dict(self, *keys) -> dict:
        """获取字典"""
        data = self._lang_data
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k, {})
            else:
                return {}
        return data if isinstance(data, dict) else {}

    def _list(self, *keys) -> list:
        """获取列表"""
        data = self._lang_data
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k, [])
            else:
                return []
        return data if isinstance(data, list) else []

    # ── 公共 API ──────────────────────────────────────

    def build_base_prompt(
        self,
        user_message: str,
        timestamp: str | None = None,
        persona_content: str | None = None,
        tools_text: str = "",
        memory_text: str = "",
        history_text: str = "",
        tool_errors: set | None = None,
        tool_definitions: list | None = None,
    ) -> str:
        tool_errors = tool_errors or set()
        # 合并内置工具和动态工具定义
        all_tool_defs = dict(self._dict("builtin_tools"))
        if tool_definitions:
            for td in tool_definitions:
                name = td.get("name", "")
                if name:
                    all_tool_defs[name] = td
        """构建基础系统提示词（正常每轮对话）"""
        ts = timestamp or time.strftime("%Y-%m-%d %H:%M:%S")
        parts = []

        # 1. 身份 + 规则
        parts.append(self._t("system", "identity"))
        for rule in self._list("system", "rules"):
            parts.append(rule)
        parts.append("")

        # 2. 系统说明
        parts.append("# 系统")
        for info in self._list("system", "system_info"):
            parts.append(f"- {info}")
        parts.append("")

        # 3. 工具使用规则
        parts.append("# 使用你的工具")
        for rule in self._list("tool_usage"):
            parts.append(f"- {rule}")
        parts.append("")

        # 4. 语气与风格
        parts.append("# 语气与风格")
        for tone in self._list("tone"):
            parts.append(f"- {tone}")
        parts.append("")
        # 风格示例
        examples = self._lang_data.get("tone_examples", [])
        if examples:
            for ex in examples:
                parts.append("<example>")
                parts.append("")
                for line in ex.get("lines", []):
                    parts.append(line)
                parts.append("")
                parts.append("</example>")
                parts.append("")
        parts.append("")

        # 5. 输出效率
        parts.append("# 输出效率")
        for eff in self._list("output_efficiency"):
            parts.append(f"- {eff}")
        parts.append("")

        # 6. 角色设定
        parts.append("# 角色设定")
        if persona_content:
            parts.append(persona_content)
        else:
            try:
                pc = load_persona_with_system(self.persona, Config.PERSONA_DIR)
                parts.append(pc)
            except FileNotFoundError:
                parts.append("（未配置角色）")
        parts.append("")

        # 7. 对话历史（如有）
        if history_text:
            parts.append("# 对话历史")
            parts.append(history_text)
            parts.append("")

        # 8. 当前用户消息
        parts.append("# 当前用户消息")
        parts.append(f"[user]:{user_message}")
        parts.append(f"[{ts}]")
        parts.append("")

        # 9. 可用工具
        parts.append("# 可用工具")
        parts.append("你可以利用这些工具发送消息，理解用户表达，实现复杂的消息发送策略。")
        parts.append("")
        # 内置工具
        builtin = self._dict("builtin_tools")
        for name, defn in builtin.items():
            parts.append(f"## {name}")
            parts.append(defn.get("description", ""))
            parts.append("")
            parts.append("用法：")
            for param, pdesc in defn.get("usage", {}).items():
                parts.append(f"- {param}（{pdesc}）")
            notes = defn.get("notes", [])
            if notes:
                parts.append("")
                parts.append("重要说明：")
                for note in notes:
                    parts.append(f"- {note}")
            parts.append("")
        # 扩展工具
        if tools_text:
            parts.append(tools_text)
        parts.append("")

        # 10. 工具调用格式
        parts.append("# 工具调用格式")
        parts.append("你仅能通过工具调用与用户沟通。每一轮都必须使用工具调用格式输出，禁止直接输出裸文本。")
        parts.append("你的消息调用格式如下")
        parts.append("")
        if not tool_errors:
            parts.append(self._t("tool_call_format", "normal"))
        else:
            # 有错误 → 注入示例
            parts.append(self._t("tool_call_format", "error_example", "intro") or "## 规范")
            parts.append("")
            parts.append(self._t("tool_call_format", "normal"))
            stop = self._t("tool_call_format", "stop_signal")
            if stop:
                parts.append("")
                parts.append(stop)
            parts.append("")
            parts.append("## 示例")
            for ex in self._list("tool_call_format", "error_example", "examples"):
                if ex in tool_errors:
                    defn = all_tool_defs.get(ex, {})
                    if defn:
                        params = defn.get("usage", defn.get("parameters", {}))
                        parts.append(f"<tool_call>")
                        parts.append(f"<name>{ex}</name>")
                        parts.append(f"<parameters>")
                        for param in params:
                            # 用真实值替换占位符
                            example_val = {
                                "interval": "120000",
                                "content": "具体消息文本",
                                "query": "搜索内容",
                                "max_results": "5",
                                "title": "记忆标题",
                                "reason": "删除理由",
                            }.get(param, "示例值")
                            parts.append(f"<{param}>{example_val}</{param}>")
                        parts.append(f"</parameters>")
                        parts.append(f"</tool_call>")
                        parts.append("")
        parts.append("")

        # 11. 记忆内容
        parts.append("# 记忆内容")
        if memory_text:
            parts.append(memory_text)
        else:
            parts.append(self._t("memory_section", "placeholder"))

        return "\n".join(parts)

    def build_compression_prompt(self) -> str:
        """构建上下文压缩提示词（无工具模式）"""
        return """#无工具前导

关键：仅回复文本。不要调用任何工具。

· 不要使用 WebSearch、ScheduledMessage 或任何其他工具。
· 你已经从上面的对话中获得了所需的所有上下文。
· 工具调用将被拒绝并浪费你唯一的一轮 — 你将无法完成任务。
· 你的整个响应必须是纯文本：一个 <analysis> 块，后跟一个 <summary> 块。

#执行规范

在提供最终摘要之前，将你的分析包装在 <analysis> 标签中。在分析中：

1. 按时间顺序分析每条消息和每个部分。对每个部分，彻底识别：
   · 用户的显式请求和意图
   · 你处理用户请求的方法
   · 关键决策、角色设定和对话策略
   · 具体细节：角色口癖、句式特征、动作描写、情感基调
   · 你遇到的角色一致性偏差及如何修复
   · 特别注意你收到的特定用户反馈
2. 双重检查角色人设准确性和剧情逻辑完整性。

#输出格式

输出格式为 <analysis> + <summary>：

<summary>
1. 主要请求与意图:
   [详细描述]
2. 核心设定与世界观概念:
   · [概念 1]
   · [概念 2]
3. 角色与互动关键:
   · [角色名 1]
     · [此角色为何重要的摘要]
     · [扮演风格与情感基调摘要]
     · [关键对话片段或典型句式]
4. 角色偏差与修复:
   · [偏差描述]:
     · [如何修复]
     · [用户反馈（如有）]
5. 剧情推进:
   [已解决的情节描述及持续发展的线索]
6. 所有用户消息:
   · [详细的非工具调用用户消息]
7. 待推进剧情节点:
   · [节点 1]
8. 当前剧情定位:
   [当前剧情状态的精确描述]
9. 可选的下一步:
   [包含最近对话中的直接引用，显示正在推进的剧情方向]

</summary>"""

    def build_rebuild_prompt(
        self,
        user_message: str,
        timestamp: str | None = None,
        persona_content: str | None = None,
        tools_text: str = "",
        memory_text: str = "",
        summary: str = "",
        recent_messages: str = "",
        tool_errors: set | None = None,
    ) -> str:
        tool_errors = tool_errors or set()
        """构建压缩后首次重建提示词"""
        ts = timestamp or time.strftime("%Y-%m-%d %H:%M:%S")
        parts = []

        # 1-5: 与 base_prompt 相同
        parts.append(self._t("system", "identity"))
        for rule in self._list("system", "rules"):
            parts.append(rule)
        parts.append("")

        parts.append("# 系统")
        for info in self._list("system", "system_info"):
            parts.append(f"- {info}")
        parts.append("")

        parts.append("# 使用你的工具")
        for rule in self._list("tool_usage"):
            parts.append(f"- {rule}")
        parts.append("")

        parts.append("# 语气与风格")
        for tone in self._list("tone"):
            parts.append(f"- {tone}")
        parts.append("")

        parts.append("# 输出效率")
        for eff in self._list("output_efficiency"):
            parts.append(f"- {eff}")
        parts.append("")

        # 6. 角色设定
        parts.append("# 角色设定")
        if persona_content:
            parts.append(persona_content)
        else:
            try:
                pc = load_persona_with_system(self.persona, Config.PERSONA_DIR)
                parts.append(pc)
            except FileNotFoundError:
                parts.append("（未配置角色）")
        parts.append("")

        # 7. 对话总结（压缩产物）
        parts.append(self._t("rebuild_intro", "conversation_summary_label"))
        parts.append(summary)
        parts.append("")

        # 8. 用户消息列表
        if recent_messages:
            parts.append(self._t("rebuild_intro", "user_message_list_label"))
            parts.append("你与用户对话历史的用户端呈现")
            parts.append("")
            parts.append(recent_messages)
            parts.append("")

        # 9. 当前用户消息
        parts.append("# 当前用户消息")
        parts.append(f"[user]:{user_message}")
        parts.append(f"[{ts}]")
        parts.append("")

        # 10-12: 工具 + 格式 + 记忆
        parts.append("# 可用工具")
        parts.append("你可以利用这些工具发送消息，理解用户表达，实现复杂的消息发送策略。")
        parts.append("")
        builtin = self._dict("builtin_tools")
        for name, defn in builtin.items():
            parts.append(f"## {name}")
            parts.append(defn.get("description", ""))
            parts.append("")
            parts.append("用法：")
            for param, pdesc in defn.get("usage", {}).items():
                parts.append(f"- {param}（{pdesc}）")
            notes = defn.get("notes", [])
            if notes:
                parts.append("")
                parts.append("重要说明：")
                for note in notes:
                    parts.append(f"- {note}")
            parts.append("")
        if tools_text:
            parts.append(tools_text)
        parts.append("")

        parts.append("# 工具调用格式")
        parts.append("你的消息调用格式如下")
        parts.append("")
        parts.append(self._t("tool_call_format", "normal"))
        parts.append("")

        parts.append("# 记忆内容")
        if memory_text:
            parts.append(memory_text)
        else:
            parts.append(self._t("memory_section", "placeholder"))

        return "\n".join(parts)
