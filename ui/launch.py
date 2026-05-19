#!/usr/bin/env python3
"""
Pal UI — 原生终端 TUI 启动器
"""

import os, sys
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from ui.tui import main

if __name__ == "__main__":
    main()
