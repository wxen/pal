"""
Persona（人格）加载器
从 markdown 文件读取角色扮演的人格描述
"""

import re
from pathlib import Path


def _find_persona_path(name: str, persona_dir: str | Path) -> Path:
    """查找 persona 文件：先在 persona/ 下找，再在 agent/ 下找"""
    # 1. persona/{name}/persona.md
    p = Path(persona_dir) / name / "persona.md"
    if p.exists():
        return p
    # 2. agent/{name}/persona/{name}.md
    agent_p = Path(persona_dir).parent / "agent" / name / "persona" / f"{name}.md"
    if agent_p.exists():
        return agent_p
    raise FileNotFoundError(f"Persona 文件不存在: {p}")


def load_persona(name: str, persona_dir: str | Path = "persona") -> str:
    persona_path = _find_persona_path(name, persona_dir)
    content = persona_path.read_text(encoding="utf-8")
    content = re.sub(r"^# .+$", "", content, flags=re.MULTILINE)
    return content.strip()


def load_persona_with_system(name: str, persona_dir: str | Path = "persona") -> str:
    """
    加载 persona 内容（原始 markdown 去除一级标题）
    直接返回人格描述文本，不包装系统提示词
    """
    return load_persona(name, persona_dir)


def list_personas(persona_dir: str | Path = "persona") -> list[str]:
    """列出所有可用的 persona"""
    p = Path(persona_dir)
    if not p.exists():
        return []
    return [
        d.name
        for d in p.iterdir()
        if d.is_dir() and (d / "persona.md").exists()
    ]
