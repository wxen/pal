"""
配置管理模块
支持环境变量和 .env 文件加载
"""

import os
from pathlib import Path


def _load_dotenv_file(env_path: str | None = None):
    """在模块导入时加载 .env 文件到 os.environ"""
    if env_path is None:
        env_path = str(Path(__file__).resolve().parent.parent / ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip("\"'"))


# 模块导入时立即加载 .env
_load_dotenv_file()


class Config:
    """全局配置"""

    # 项目根目录
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    # === API 提供商 ===
    # 当前使用的提供商
    API_PROVIDER = os.getenv("API_PROVIDER", "deepseek")

    # OpenAI (CloseAI 中转)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai-proxy.org/v1")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    # Anthropic Claude (CloseAI 中转)
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_BASE_URL = os.getenv("CLAUDE_BASE_URL", "https://api.openai-proxy.org/anthropic")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6-20250514")

    # Google Gemini (CloseAI 中转)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://api.openai-proxy.org/google")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Kimi (月之暗面)
    KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
    KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
    KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-128k")

    # Qwen (阿里)
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

    # GLM (智谱)
    GLM_API_KEY = os.getenv("GLM_API_KEY", "")
    GLM_BASE_URL = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    GLM_MODEL = os.getenv("GLM_MODEL", "glm-4-flash")

    # Mistral
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
    MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

    # MiniMax
    MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
    MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "abab6.5s-chat")

    # DeepSeek (保留兼容)
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_MAX_TOKENS = int(os.getenv("DEEPSEEK_MAX_TOKENS", "4096"))
    DEEPSEEK_TEMPERATURE = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.9"))
    DEEPSEEK_TOP_P = float(os.getenv("DEEPSEEK_TOP_P", "0.95"))

    # === Bot 频道端口 ===
    DISCORD_PORT = int(os.getenv("DISCORD_PORT", "5100"))
    TELEGRAM_PORT = int(os.getenv("TELEGRAM_PORT", "5101"))
    SLACK_PORT = int(os.getenv("SLACK_PORT", "5102"))
    LINE_PORT = int(os.getenv("LINE_PORT", "5103"))
    DINGTALK_PORT = int(os.getenv("DINGTALK_PORT", "5104"))
    FEISHU_PORT = int(os.getenv("FEISHU_PORT", "5105"))
    QQ_PORT = int(os.getenv("QQ_PORT", "5106"))

    # === Persona ===
    PERSONA_DIR = str(PROJECT_ROOT / "persona")
    PERSONA_NAME = os.getenv("PERSONA_NAME", "test")

    # === 存储路径 ===
    FILE_DIR = PROJECT_ROOT / "file"
    MEMORY_DIR = PROJECT_ROOT / "file" / PERSONA_NAME / "memory"
    ARCHIVE_DIR = PROJECT_ROOT / "file" / PERSONA_NAME / "archive"
    WORKSPACE_DIR = PROJECT_ROOT / "workspace"

    # === 工具 ===
    TOOL_DIR = PROJECT_ROOT / "tool" / PERSONA_NAME
    TOOL_JSON_PATH = TOOL_DIR / "tool.json"
    TOOL_IMPL_DIR = TOOL_DIR / "tools"

    # === 语言 ===
    LANG = os.getenv("PAL_LANG", "zh")
    LANG_DIR = PROJECT_ROOT / "lang"

    # === 对话 ===
    MAX_HISTORY_ROUNDS = int(os.getenv("MAX_HISTORY_ROUNDS", "30"))
    CONTEXT_COMPRESSION_RATIO = float(os.getenv("CONTEXT_COMPRESSION_RATIO", "0.80"))
    REBUILD_HISTORY_ROUNDS = int(os.getenv("REBUILD_HISTORY_ROUNDS", "2"))
    MESSAGE_MERGE_MS = int(os.getenv("MESSAGE_MERGE_MS", "800"))

    # === Token 估算 ===
    TOKEN_ESTIMATION_RATIO = float(os.getenv("TOKEN_ESTIMATION_RATIO", "2.5"))
    CONTEXT_WINDOW_TOKENS = int(os.getenv("CONTEXT_WINDOW_TOKENS", "65536"))

    @classmethod
    def ensure_dirs(cls):
        """确保必要的目录存在"""
        for d in [cls.MEMORY_DIR, cls.ARCHIVE_DIR, cls.TOOL_IMPL_DIR, cls.WORKSPACE_DIR]:
            Path(d).mkdir(parents=True, exist_ok=True)


Config.ensure_dirs()

DEFAULT_TIMEOUT = 60
DEEPSEEK_MODELS = {
    "deepseek-chat": "DeepSeek-V3",
    "deepseek-reasoner": "DeepSeek-R1",
}
