# Pal

AI Role-Playing Chat Framework — multi-agent, multi-channel, multi-model.

**Developer**: Wang Xi (China)

---

## Overview

Pal is a lightweight framework for creating AI role-playing chatbots that connect to messaging platforms. Each agent runs independently with its own persona, language, API backend, and chat channel.

### Features

- **Multi-Agent** — create, configure, and run multiple independent agents
- **Multi-Model** — DeepSeek, OpenAI, Claude, Gemini, Kimi, Qwen, GLM, Mistral, MiniMax, Ollama
- **Multi-Channel** — WeChat ClawBot, Discord, Telegram, Slack, LINE, DingTalk, Feishu, QQ
- **Memory System** — long-term memory with save/update/delete tools
- **Context Compression** — auto-summarize + rebuild when token threshold reached
- **Dynamic Tool Injection** — keyword-aware tool examples (WebSearch, ScheduledMessage, etc.)
- **11 Languages** — zh, en, ja, ko, de, es, fr, pt, ru, ar, id
- **TUI Dashboard** — Textual-based terminal management interface
- **One-Click Deploy** — `install.sh` / `install.bat`

---

## Quick Start

```bash
# Linux / macOS
git clone <repo-url> && cd pal
bash install.sh
source ~/.bashrc

# Windows
install.bat
```

```bash
# Create an agent with default config
pal create mybot

# Configure it non-interactively
pal config mybot api_key sk-your-key
pal config mybot api_model deepseek-chat
pal config mybot persona_path /path/to/persona.md

# Start the agent (WeChat QR login)
pal start mybot

# List all agents
pal list
```

---

## CLI Commands

```
pal                          Show banner and help hint
pal --help                   Full command reference

=== Agent Lifecycle ===
pal create <name>            Quick-create with defaults
pal create <name> --wizard   Interactive guided setup
pal edit <name>              Edit existing via wizard
pal rm <name>                Delete agent and data

=== Non-Interactive Config ===
pal config <name> <key> <value>   Set single config value
pal config <name> show             Show config as JSON

=== Agent Control ===
pal list                     Dashboard with auto-refresh
pal show <name>              Detailed config view
pal start <name> [names...]  Start agent(s)
pal start --all              Start all agents
pal restart / stop           Restart or stop agents

=== UI ===
pal ui                       Launch Textual TUI
```

### Config Keys

| Key | Type | Example |
|-----|------|---------|
| `description` | string | `"My bot"` |
| `lang` | string | `zh`, `en`, `ja` |
| `persona_path` | path | `/abs/path/to/persona.md` |
| `api_provider` | string | `deepseek`, `openai`, `claude` |
| `api_key` | string | `sk-xxxx` |
| `api_model` | string | `deepseek-chat` |
| `bot` | string | `wechat`, `discord`, `telegram` |
| `launch_mode` | string | `silent`, `monitor`, `log`, `both` |
| `active_message` | bool | `true`, `false` |
| `active_intensity` | int | `0`-`100` |
| `context_mode` | string | `auto`, `single`, `rolling` |
| `context_threshold` | int | `0`-`100` |
| `message_delay` | bool | `true`, `false` |

---

## Architecture

```
main.py (CLI entry)
  ├── core/engine.py        PalEngine — prompt building, LLM calling, tool execution
  │    ├── core/prompt.py   PromptBuilder — base/rebuild prompt assembly
  │    ├── core/memory.py   MemoryManager — CRUD long-term memory
  │    ├── core/context.py  ContextManager — token estimation, compression, history
  │    ├── core/tools.py    ToolRegistry — dynamic tool loading
  │    ├── core/persona.py  Persona loader (persona.md / agent persona)
  │    └── core/agent.py    AgentManager — agent config CRUD
  ├── core/launcher.py      AgentLauncher — multi-agent lifecycle (singleton)
  ├── core/wizard.py        Interactive agent creation wizard
  ├── core/active.py        ActiveMessenger — random proactive messages
  ├── api/                  Model providers (OpenAI-compat base + Claude native)
  ├── bot/                  Chat channel adapters (BotAdapter base)
  ├── lang/                 11 language prompt templates (JSON)
  ├── tool/                 Extensible tool system (tool.json + Python impl)
  └── ui/                   Textual TUI management dashboard
```

## Data Flow

```
User Message → Bot Channel → PalEngine.process()
  → PromptBuilder (system + persona + tools + memory)
  → LLM API (chat/completions)
  → XML Tool Call Parser (<tool_call>SendMessage/MemorySave/WebSearch)
  → Tool Execution → Message Queue → Bot Channel Reply
```

## Context Compression

```
Token usage ≥ 80% threshold
  → Inject compression prompt (no-tool mode)
  → LLM outputs <analysis> + <summary>
  → Next turn: rebuild prompt with summary + recent messages
  → Resume normal prompt
```

## File Structure

```
pal/
├── main.py              CLI entry point
├── install.sh / .bat    One-click deploy
├── delete.sh / .bat     Clean uninstall
├── core/                Engine, memory, context, tools, agent, wizard
├── api/                 Model clients (deepseek, openai, claude, ...)
├── bot/                 Channel adapters (wechat, discord, telegram, ...)
├── lang/                Prompt templates (zh, en, ja, ko, de, ...)
├── tool/test/           Default tool definitions + WebSearch
├── ui/                  Textual TUI dashboard
├── agent/<name>/        Per-agent config, persona, tools, memory, logs
├── file/                Runtime storage
└── workspace/           User uploads
```

## Requirements

- Python 3.10+
- `textual`, `requests`, `python-dotenv`, `Pillow`

## Disclaimer

Messages are transmitted directly to API providers. No third-party data collection. Users are responsible for their own privacy. Do not share sensitive information.

## License

MIT
