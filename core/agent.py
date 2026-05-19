"""
Agent 配置管理器
每个 agent 对应 /pal/agent/{name}/ 目录，config.json 存储所有配置
"""

import json
import os
import shutil
from pathlib import Path

from core.config import Config


AGENTS_DIR = Config.PROJECT_ROOT / "agent"

# 默认 agent 配置模板
DEFAULT_CONFIG = {
    "name": "",
    "description": "",
    "lang": "zh",
    "persona_path": "",
    "persona_text": "",
    "api_provider": "deepseek",
    "api_key": "",
    "api_model": "",
    "api_max_tokens": 0,
    "api_multimodal": [],  # ["image", "voice", "document"]
    "bot": "wechat",
    "bot_config": {},
    "message_delay": False,
    "active_message": False,
    "active_intensity": 30,
    "context_mode": "auto",  # "single" | "rolling" | "auto"
    "context_threshold": 80,  # 0-100 percentage
    "tools": [],  # copied tool names
    "launch_mode": "silent",  # "silent" | "monitor" | "log" | "both"
    "log_path": "",
}


class AgentManager:
    """Agent 配置的 CRUD 管理"""

    @staticmethod
    def ensure_dirs():
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def list_agents() -> list[str]:
        """列出所有 agent 名称"""
        if not AGENTS_DIR.exists():
            return []
        return sorted([
            d.name for d in AGENTS_DIR.iterdir()
            if d.is_dir() and (d / "config.json").exists()
        ])

    @staticmethod
    def exists(name: str) -> bool:
        return (AGENTS_DIR / name / "config.json").exists()

    @staticmethod
    def create(name: str, **overrides) -> dict:
        """创建新 agent"""
        AgentManager.ensure_dirs()
        agent_dir = AGENTS_DIR / name
        agent_dir.mkdir(parents=True, exist_ok=True)

        config = dict(DEFAULT_CONFIG)
        config["name"] = name
        config.update(overrides)

        # 确保子目录
        for sub in ["persona", "tool/tools", "file/memory", "file/archive", "data"]:
            (agent_dir / sub).mkdir(parents=True, exist_ok=True)

        AgentManager._save(name, config)
        return config

    @staticmethod
    def load(name: str) -> dict | None:
        """加载 agent 配置"""
        path = AGENTS_DIR / name / "config.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _save(name: str, config: dict):
        """保存 agent 配置"""
        agent_dir = AGENTS_DIR / name
        agent_dir.mkdir(parents=True, exist_ok=True)
        path = agent_dir / "config.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    @staticmethod
    def update(name: str, **kwargs) -> dict | None:
        """更新 agent 配置"""
        config = AgentManager.load(name)
        if config is None:
            return None
        config.update(kwargs)
        AgentManager._save(name, config)
        return config

    @staticmethod
    def delete(name: str) -> bool:
        """删除整个 agent 目录"""
        agent_dir = AGENTS_DIR / name
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
            return True
        return False

    @staticmethod
    def get_persona_path(name: str) -> Path:
        """获取 agent 的 persona 文件路径"""
        return AGENTS_DIR / name / "persona" / f"{name}.md"

    @staticmethod
    def get_tool_dir(name: str) -> Path:
        """获取 agent 的 tool 目录"""
        return AGENTS_DIR / name / "tool"

    @staticmethod
    def get_memory_dir(name: str) -> Path:
        return AGENTS_DIR / name / "file" / "memory"

    @staticmethod
    def get_archive_dir(name: str) -> Path:
        return AGENTS_DIR / name / "file" / "archive"
