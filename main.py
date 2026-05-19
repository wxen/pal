#!/usr/bin/env python3
"""
Pal - AI Role-Playing Chat Framework
Usage:
  pal                           Show banner and help hint
  pal --help / -h               Show all commands
  pal create <name>             Quick-create agent
  pal create <name> --wizard    Interactive guided setup
  pal rm <name>                 Remove agent
  pal start <name> [names...]   Start agent(s)
  pal start --all               Start all agents
  pal restart <name> [names...] Restart agent(s)
  pal list                      List all agents
"""

import os, sys, json, time, signal, logging
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.config import Config
from core.agent import AgentManager

# ── Banner ──────────────────────────────────────────────

BANNER_PATH = os.path.join(PROJECT_ROOT, "core", "banner.txt")

def show_banner():
    # Show image art if available
    if os.path.exists(BANNER_PATH):
        with open(BANNER_PATH, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        # Fallback text logo
        print("""
   ██████╗  █████╗ ██╗
   ██╔══██╗██╔══██╗██║
   ██████╔╝███████║██║
   ██╔═══╝ ██╔══██║██║
   ██║     ██║  ██║███████╗
   ╚═╝     ╚═╝  ╚═╝╚══════╝
""")
    print("  pal - AI Role-Playing Chat Framework")
    print("  Developer: Wang Xi (China)")
    print()
    print("  DISCLAIMER: Messages are sent directly to API providers.")
    print("  No third-party data collection. Protect your privacy.")
    print("  Do not share sensitive information through this service.")
    print()


def show_full_help():
    show_banner()
    print("COMMANDS:")
    print()
    print("  pal")
    print("    Show banner, disclaimer, and help hint.")
    print()
    print("  pal --help / -h")
    print("    Show this full help message.")
    print()
    print("=== Agent Lifecycle ===")
    print()
    print("  pal create <name>")
    print("    Quick-create agent with default config.")
    print()
    print("  pal create <name> --wizard / -w")
    print("    Interactive guided setup (also works for editing).")
    print()
    print("  pal edit <name>")
    print("    Edit existing agent via wizard.")
    print()
    print("  pal rm <name>")
    print("    Delete agent and all its data.")
    print()
    print("=== Non-Interactive Config ===")
    print()
    print("  pal config <name> <key> <value>")
    print("    Set a single config value. Examples:")
    print("      pal config mybot lang ja")
    print("      pal config mybot api_key sk-xxxx")
    print("      pal config mybot api_provider openai")
    print("      pal config mybot api_model gpt-5.4-mini")
    print("      pal config mybot bot discord")
    print("      pal config mybot launch_mode both")
    print("      pal config mybot persona_path /path/to/persona.md")
    print("      pal config mybot active_message true")
    print("      pal config mybot active_intensity 30")
    print("      pal config mybot context_mode auto")
    print("      pal config mybot context_threshold 80")
    print()
    print("  pal config <name> show")
    print("    Show agent config in JSON.")
    print()
    print("=== Agent Status & Control ===")
    print()
    print("  pal list / ls")
    print("    List agents with status dashboard (auto-refresh).")
    print()
    print("  pal show <name>")
    print("    Show agent configuration.")
    print()
    print("  pal start <name> [name2 ...]")
    print("    Start one or more agents.")
    print()
    print("  pal start --all / -a")
    print("    Start all agents.")
    print()
    print("  pal restart <name> [name2 ...]")
    print("    Restart one or more agents.")
    print()
    print("  pal stop [name ...] / --all")
    print("    Stop running agents.")
    print()
    print("=== UI ===")
    print()
    print("  pal ui")
    print("    Launch Textual TUI management interface.")
    print()
    print("FILES:")
    print(f"  Config:   {Config.PROJECT_ROOT}/agent/<name>/config.json")
    print(f"  Persona:  {Config.PROJECT_ROOT}/agent/<name>/persona/<name>.md")
    print(f"  Tools:    {Config.PROJECT_ROOT}/agent/<name>/tool/tool.json")
    print(f"  Memory:   {Config.PROJECT_ROOT}/agent/<name>/file/memory/")
    print(f"  Logs:     {Config.PROJECT_ROOT}/agent/<name>/date/")
    print(f"  Language: {Config.PROJECT_ROOT}/lang/")
    print()

# ── Dynamic Dashboard ────────────────────────────────────

def _list_dashboard():
    """Dynamic agent list with auto-refresh, exit on Ctrl+C or double-Esc"""
    import select, termios, tty

    # Check terminal support
    if not sys.stdin.isatty():
        # Fallback: static list
        _list_static()
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)
        last_esc = 0.0
        while True:
            # Clear and redraw
            sys.stdout.write("\033[2J\033[H")  # clear screen, cursor home
            show_banner()
            _list_static()
            print()
            print("Auto-refreshing every 2s. Press Esc twice or Ctrl+C to exit.")
            sys.stdout.flush()

            # Wait up to 2s for keypress
            timeout = 2.0
            while timeout > 0:
                r, _, _ = select.select([sys.stdin], [], [], min(timeout, 0.1))
                if r:
                    ch = sys.stdin.read(1)
                    if ch == "\x1b":  # Esc
                        now = time.time()
                        if now - last_esc < 0.5:
                            return  # double Esc
                        last_esc = now
                    elif ord(ch) == 3:  # Ctrl+C
                        return
                timeout -= 0.1
    except (ImportError, termios.error, AttributeError):
        _list_static()
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            pass


def _list_static():
    """Print static agent list"""
    agents = AgentManager.list_agents()
    if agents:
        print("AGENTS:")
        print(f"  {'NAME':<16} {'BOT':<12} {'LANG':<6} {'API':<14} {'MODE':<12} {'ACTIVE':<8}")
        print(f"  {'-'*16} {'-'*12} {'-'*6} {'-'*14} {'-'*12} {'-'*8}")
        for a in agents:
            cfg = AgentManager.load(a) or {}
            bot = cfg.get("bot", "?")
            lang = cfg.get("lang", "?")
            api = cfg.get("api_provider", "?")
            mode = cfg.get("context_mode", "?")
            active = "ON" if cfg.get("active_message") else "-"
            print(f"  {a:<16} {bot:<12} {lang:<6} {api:<14} {mode:<12} {active:<8}")
    else:
        print("No agents configured. Use 'pal create <name>' to create one.")

def main():
    args = sys.argv[1:]

    # Bare "pal" — show banner + hint
    if not args:
        show_banner()
        print("Type 'pal --help' or 'pal -h' for available commands.")
        return

    cmd = args[0].lower()

    # --help / -h
    if cmd in ("--help", "-h", "help"):
        show_full_help()
        return

    # list / ls — dynamic refresh dashboard
    if cmd in ("list", "ls"):
        _list_dashboard()
        return

    # show <name>
    if cmd == "show" and len(args) >= 2:
        name = args[1]
        cfg = AgentManager.load(name)
        if cfg:
            print(f"Agent: {name}")
            for k, v in cfg.items():
                if k in ("api_key",) and v:
                    v = v[:8] + "***"
                print(f"  {k}: {v}")
        else:
            print(f"Agent '{name}' not found.")
        return

    # create <name> [--wizard/-w]
    if cmd == "create" and len(args) >= 2:
        name = args[1]
        wizard = "--wizard" in args or "-w" in args
        if wizard:
            from core.wizard import run_wizard
            run_wizard(name)
        else:
            cfg = AgentManager.create(name)
            print(f"Agent '{name}' created with default config.")
            print(f"Edit: {Config.PROJECT_ROOT}/agent/{name}/config.json")
            print(f"Or re-run with --wizard for guided setup.")
        return

    # rm <name>
    if cmd == "rm" and len(args) >= 2:
        name = args[1]
        confirm = input(f"Delete agent '{name}' and ALL its data? [y/N] ").strip().lower()
        if confirm in ("y", "yes"):
            AgentManager.delete(name)
            print(f"Agent '{name}' deleted.")
        else:
            print("Cancelled.")
        return

    # start <name> [names...] / --all / -a
    if cmd == "start":
        from core.launcher import launcher
        if "--all" in args or "-a" in args:
            launcher.start_all()
        else:
            names = [a for a in args[1:] if not a.startswith("-")]
            if names:
                launcher.start(names)
                # Keep alive
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nStopping...")
            else:
                print("Usage: pal start <name> [names...]  or  pal start --all")
        return

    # restart <name> [names...] / --all
    if cmd == "restart":
        from core.launcher import launcher
        if "--all" in args or "-a" in args:
            launcher.restart()
        else:
            names = [a for a in args[1:] if not a.startswith("-")]
            if names:
                launcher.restart(names)
            else:
                print("Usage: pal restart <name> [names...]  or  pal restart --all")
        return

    # stop [names] / --all
    if cmd == "stop":
        from core.launcher import launcher
        if "--all" in args or "-a" in args:
            launcher.stop()
        elif len(args) > 1:
            launcher.stop(args[1:])
        else:
            launcher.stop()
        return

    # config <name> <key> <value> / config <name> show
    if cmd == "config" and len(args) >= 2:
        _handle_config(args[1:])
        return

    # edit <name> — alias for create --wizard on existing
    if cmd == "edit" and len(args) >= 2:
        name = args[1]
        if not AgentManager.exists(name):
            print(f"Agent '{name}' not found. Create it first: pal create {name}")
        else:
            from core.wizard import run_wizard
            run_wizard(name)
        return

    # pal ui — run TUI directly in this process
    if cmd == "ui":
        from ui.tui import main as tui_main
        tui_main()
        return

    # Unknown
    print(f"Unknown command: {cmd}")
    print("Type 'pal --help' for available commands.")
    return


def _handle_config(args: list):
    """pal config <name> <key> <value> / pal config <name> show"""
    name = args[0]
    if not AgentManager.exists(name):
        print(f"Agent '{name}' not found.")
        return
    if len(args) >= 2 and args[1] == "show":
        cfg = AgentManager.load(name)
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return
    if len(args) >= 3:
        key, value = args[1], args[2]
        cfg = AgentManager.load(name)
        if key not in cfg:
            print(f"Unknown key: {key}")
            print(f"Valid: {', '.join(sorted(cfg.keys()))}")
            return
        if isinstance(cfg[key], bool):
            value = value.lower() in ("true", "1", "yes", "on")
        elif isinstance(cfg[key], int):
            value = int(value)
        elif isinstance(cfg[key], float):
            value = float(value)
        elif isinstance(cfg[key], list):
            value = value.split(",")
        AgentManager.update(name, **{key: value})
        print(f"  {name}.{key} = {value}")
        return
    print("Usage: pal config <name> <key> <value>")
    print("       pal config <name> show")


if __name__ == "__main__":
    main()
