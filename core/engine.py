"""
Pal 对话引擎
编排：提示词构建 → LLM调用 → 工具解析 → 工具执行 → 消息投递 → 记忆管理 → 上下文压缩
"""

import re
import time
import json
import logging
from datetime import datetime
from typing import Callable

from core.config import Config
from core.persona import load_persona_with_system
from core.memory import MemoryManager
from core.tools import ToolRegistry
from core.context import ContextManager
from core.prompt import PromptBuilder

logger = logging.getLogger("pal.engine")


class PalEngine:
    """Pal 主对话引擎"""

    def __init__(
        self,
        session_id: str = "default",
        persona: str | None = None,
        lang: str | None = None,
        api_key: str | None = None,
        api_provider: str | None = None,
        api_base_url: str | None = None,
        api_model: str | None = None,
    ):
        self.session_id = session_id
        persona_name = persona or Config.PERSONA_NAME
        lang = lang or Config.LANG
        self._api_key = api_key
        self._api_provider = api_provider
        self._api_base_url = api_base_url
        self._api_model = api_model

        # 子模块 — 全部使用指定的 persona_name
        self.persona_name = persona_name
        self.memory = MemoryManager(persona_name)
        self.tools = ToolRegistry(persona_name)
        self.context = ContextManager(session_id, persona_name)
        self.prompt_builder = PromptBuilder(lang, persona_name)

        # LLM 客户端（惰性加载）
        self._llm = None

        # 消息队列（引擎输出→外部投递）
        self._message_queue: list[dict] = []
        self._scheduled_queue: list[dict] = []

        # 工具错误跟踪
        self._tool_errors: set = set()

    @property
    def llm(self):
        if self._llm is None:
            provider = self._api_provider or Config.API_PROVIDER
            key = self._api_key or getattr(Config, f"{provider.upper()}_API_KEY", "")
            if provider in ("openai", "kimi", "qwen", "glm", "mistral", "minimax", "gemini"):
                from api.openai_compat import OpenAICompatibleClient
                url = self._api_base_url or getattr(Config, f"{provider.upper()}_BASE_URL", "")
                model = self._api_model or getattr(Config, f"{provider.upper()}_MODEL", "default")
                self._llm = OpenAICompatibleClient(api_key=key, base_url=url, default_model=model)
            elif provider == "claude":
                from api.claude.client import ClaudeClient
                url = self._api_base_url or Config.CLAUDE_BASE_URL
                model = self._api_model or Config.CLAUDE_MODEL
                self._llm = ClaudeClient(api_key=key, base_url=url, default_model=model)
            else:
                from api.deepseek.client import DeepSeekClient
                self._llm = DeepSeekClient(api_key=key or None)
        return self._llm

    # ── 主入口 ────────────────────────────────────────

    def process(self, user_message: str, timestamp: str | None = None) -> list[dict]:
        """
        处理用户消息，返回需投递的消息列表
        """
        if not user_message.strip():
            return []

        self._message_queue = []
        self._scheduled_queue = []
        self._tool_results = []  # 存储工具执行结果供二次 LLM 调用

        # 0. 检测用户意图，动态注入对应工具示例
        self._detect_tool_hints(user_message)

        # 1. 构建系统提示词
        system_prompt = self._build_prompt(user_message, timestamp)

        # 2. 检查是否需要压缩
        if self.context.should_compress(system_prompt):
            logger.info("触发上下文压缩")
            compression_result = self._do_compression(system_prompt)
            if compression_result:
                system_prompt = self._build_prompt(user_message, timestamp, rebuild=True)

        # 3. 调用 LLM
        try:
            response_text = self._call_llm(system_prompt)
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return self._fallback_reply()

        # 4. 解析工具调用
        tool_calls = self._parse_tool_calls(response_text)

        if not tool_calls:
            logger.info("模型未用工具格式，按换行拆分")
            for part in response_text.split("\n\n"):
                part = part.strip()
                if part:
                    self._message_queue.append({"type": "send", "content": part})
        else:
            for tc in tool_calls:
                self._execute_tool(tc["name"], tc["params"])

        # 5. 更新对话历史
        self.context.add_user_message(user_message, timestamp)
        self.context.add_assistant_raw(response_text)

        # 5b. Agent 循环：工具结果 → LLM 二次加工
        if self._tool_results:
            continuation = (
                f"# 工具执行结果\n\n{self._tool_results[0]}\n\n"
                "请将以上搜索结果用角色的语气和风格转述给用户。"
                "必须使用多次SendMessage调用，将搜索到的具体信息拆分发送。"
            )
            full_prompt = system_prompt + "\n\n" + continuation
            try:
                response2 = self._call_llm(full_prompt)
                tc2 = self._parse_tool_calls(response2)
                if tc2:
                    for tc in tc2:
                        self._execute_tool(tc["name"], tc["params"])
                else:
                    for part in response2.split("\n\n"):
                        part = part.strip()
                        if part:
                            self._message_queue.append({"type": "send", "content": part})
                self.context.add_assistant_raw(response2)
            except Exception as e:
                logger.error(f"Agent loop LLM failed: {e}")

        # 6. 合并消息队列
        all_messages = list(self._message_queue)
        all_messages.extend(self._scheduled_queue)
        return all_messages

    # ── 提示词构建 ────────────────────────────────────

    def _build_prompt(self, user_message: str, timestamp: str | None = None,
                      rebuild: bool = False) -> str:
        """构建系统提示词（不含对话历史——历史通过API messages数组传递）"""
        persona_content = None
        try:
            persona_content = load_persona_with_system(
                self.persona_name, Config.PERSONA_DIR
            )
        except FileNotFoundError:
            pass

        tools_text = self.tools.format_for_prompt()
        tool_defs = self.tools.get_definitions()
        memory_text = self.memory.format_for_prompt()
        tool_errors = self._tool_errors or set()

        if rebuild or self.context.is_rebuild_first_round:
            recent_msgs = self.context.format_recent_user_view()
            prompt = self.prompt_builder.build_rebuild_prompt(
                user_message=user_message,
                timestamp=timestamp,
                persona_content=persona_content,
                tools_text=tools_text,
                memory_text=memory_text,
                summary=self.context.compression_summary,
                recent_messages=recent_msgs,
                tool_errors=tool_errors,
                tool_definitions=tool_defs,
            )
            self.context.finish_rebuild_round()
            return prompt

        return self.prompt_builder.build_base_prompt(
            user_message=user_message,
            timestamp=timestamp,
            persona_content=persona_content,
            tools_text=tools_text,
            memory_text=memory_text,
            history_text="",  # 历史通过messages数组传递，不嵌入系统提示词
            tool_errors=tool_errors,
        )

    # ── LLM 调用 ──────────────────────────────────────

    def _call_llm(self, system_prompt: str) -> str:
        """调用 LLM，通过 messages 数组传递对话历史"""
        messages = [{"role": "system", "content": system_prompt}]
        # 将历史消息作为原生 conversation 传递
        for h in self.context.get_history_messages():
            messages.append(h)
        # 确保至少有一条 user 消息（某些 API 如 GLM 要求）
        if not any(m.get("role") == "user" for m in messages):
            messages.append({"role": "user", "content": "."})
        response = self.llm.chat(
            messages=messages,
            temperature=0.7,
        )
        choices = response.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
        return ""

    # ── 工具调用解析 ──────────────────────────────────

    def _parse_tool_calls(self, text: str) -> list[dict]:
        """解析 XML 格式的工具调用"""
        tool_calls = []

        # 匹配 <tool_call>...</tool_call> 或 <tool_use>...</tool_use>
        for match in re.finditer(
            r"<(tool_call|tool_use)>(.*?)</\1>",
            text,
            re.DOTALL,
        ):
            block = match.group(2)
            name_match = re.search(r"<name>(.*?)</name>", block, re.DOTALL)
            if not name_match:
                continue
            name = name_match.group(1).strip()

            params = {}
            params_match = re.search(r"<parameters>(.*?)</parameters>", block, re.DOTALL)
            if params_match:
                for param_match in re.finditer(
                    r"<(\w+)>(.*?)</\1>",
                    params_match.group(1),
                    re.DOTALL,
                ):
                    params[param_match.group(1)] = param_match.group(2).strip()

            tool_calls.append({"name": name, "params": params})

        return tool_calls

    # ── 工具执行 ──────────────────────────────────────

    def _execute_tool(self, name: str, params: dict):
        """执行单个工具调用"""
        logger.info(f"工具调用: {name} {str(params)[:100]}")

        if name == "SendMessage":
            content = params.get("content", "")
            if content:
                self._message_queue.append({"type": "send", "content": content})

        elif name == "ScheduledMessage":
            content = params.get("content", "")
            interval = int(params.get("interval", 0))
            if content:
                self._scheduled_queue.append({
                    "type": "scheduled",
                    "content": content,
                    "interval": interval,
                })

        elif name == "MemorySave":
            title = params.get("title", "")
            content = params.get("content", "")
            if title and content:
                self.memory.save(title, content)
                self._tool_errors.discard("MemorySave")
                logger.info(f"MemorySave: {title}")
            else:
                self._tool_errors.add("MemorySave")

        elif name == "MemoryUpdate":
            title = params.get("title", "")
            content = params.get("content", "")
            if title and content:
                result = self.memory.update(title, content)
                if result:
                    self._tool_errors.discard("MemoryUpdate")
                    logger.info(f"MemoryUpdate: {title}")
                else:
                    self._tool_errors.add("MemoryUpdate")
            else:
                self._tool_errors.add("MemoryUpdate")

        elif name == "MemoryDelete":
            title = params.get("title", "")
            if title:
                self.memory.delete(title)
                self._tool_errors.discard("MemoryDelete")
                logger.info(f"MemoryDelete: {title}")
            else:
                self._tool_errors.add("MemoryDelete")

        else:
            # 动态工具：参数别名容错
            self._normalize_params(name, params)
            result = self.tools.execute(name, params)
            if result is None:
                logger.warning(f"未知工具: {name}")
            elif isinstance(result, str) and result.strip():
                self._tool_results.append(result)
            elif isinstance(result, dict) and "error" not in result:
                self._tool_results.append(json.dumps(result, ensure_ascii=False, indent=2))

    # ── 压缩 ─────────────────────────────────────────

    def _do_compression(self, current_prompt: str) -> bool:
        """执行上下文压缩"""
        compression_prompt = self.prompt_builder.build_compression_prompt()

        # 把压缩指令 + 当前对话内容一起发给 LLM
        combined = compression_prompt + "\n\n# 当前对话内容\n\n" + current_prompt

        try:
            messages = [{"role": "user", "content": combined}]
            response = self.llm.chat(
                messages=messages,
                model=Config.DEEPSEEK_MODEL,
                temperature=0.3,
                max_tokens=2048,
            )
            text = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # 提取 summary
            summary_match = re.search(r"<summary>(.*?)</summary>", text, re.DOTALL)
            if summary_match:
                summary = summary_match.group(1).strip()
                self.context.mark_compressed(summary)
                logger.info(f"压缩完成，摘要长度: {len(summary)}")
                return True
            else:
                logger.warning("压缩响应中未找到 <summary> 标签")
                return False
        except Exception as e:
            logger.error(f"压缩失败: {e}")
            return False

    def _detect_tool_hints(self, user_message: str):
        """检测用户意图，动态注入工具示例（避免提示词膨胀）"""
        msg = user_message.lower()
        # ScheduledMessage: 提醒/定时/xx分钟后/xx小时后
        if any(kw in msg for kw in ["提醒", "分钟后", "小时后", "叫我", "通知", "定时", "闹钟"]):
            self._tool_errors.add("ScheduledMessage")
        # MemorySave: 记住/保存/记录
        if any(kw in msg for kw in ["记住", "记下", "保存", "记录一下", "别忘了", "提醒我记住"]):
            self._tool_errors.add("MemorySave")
        # WebSearch: 搜索/查/找/新闻/发生什么/最新
        if any(kw in msg for kw in ["搜索", "查一下", "找一下", "帮我搜", "搜一下", "帮我查", "新闻", "发生什么", "最新", "查找"]):
            self._tool_errors.add("WebSearch")

    def _normalize_params(self, tool_name: str, params: dict):
        """参数别名容错：处理模型用错参数名的情况"""
        aliases = {
            "WebSearch": {"content": "query", "search": "query", "q": "query"},
            "SendMessage": {"text": "content", "message": "content", "msg": "content"},
        }
        if tool_name in aliases:
            for wrong, correct in aliases[tool_name].items():
                if wrong in params and correct not in params:
                    params[correct] = params.pop(wrong)

    def _fallback_reply(self) -> list[dict]:
        """LLM 失败时返回空（静默重试）"""
        return []
