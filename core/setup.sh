#!/usr/bin/env bash
# Pal - 角色扮演聊天服务端 一键部署脚本
# 用法: bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Pal 项目部署 ==="

# ── Python 环境 ──
PYTHON=""
for py in python3 python3.12 python3.11 python3.10 python; do
    if command -v "$py" &>/dev/null; then
        PYTHON="$py"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERR] 未找到 Python，请先安装 Python 3.10+"
    exit 1
fi

echo "[OK] Python: $($PYTHON --version)"

# ── 虚拟环境 ──
if [ ! -d ".venv" ]; then
    echo "[*] 创建虚拟环境..."
    if $PYTHON -m venv .venv 2>/dev/null; then
        echo "[OK] venv 创建成功"
    else
        echo "[!] venv 不可用（缺少 python3-venv），使用系统环境"
        # 尝试安装 pip
        $PYTHON -m pip --version 2>/dev/null || {
            echo "[*] 安装 pip..."
            curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON --break-system-packages 2>/dev/null || \
            $PYTHON /tmp/get-pip.py --break-system-packages 2>/dev/null || true
        }
    fi
fi

# ── 安装依赖 ──
if [ -f ".venv/bin/pip" ]; then
    PIP=".venv/bin/pip"
    INSTALL_CMD="$PIP install -r requirements.txt -q"
else
    PIP="$PYTHON -m pip"
    INSTALL_CMD="$PIP install --break-system-packages -r requirements.txt -q"
fi

echo "[*] 安装依赖..."
$INSTALL_CMD 2>&1 | tail -3
echo "[OK] 依赖安装完成"

# ── .env 配置 ──
if [ ! -f ".env" ]; then
    echo "[*] 创建 .env 配置..."
    cp .env.example .env
    echo "[!] 请编辑 .env 文件填入你的 API Key"
    echo "    vim .env"
fi

# ── 目录 ──
mkdir -p file workspace persona/*/  2>/dev/null || true

echo ""
echo "=== 部署完成 ==="
echo ""
echo "  启动微信频道:"
if [ -f ".venv/bin/python" ]; then
    echo "  .venv/bin/python main.py wechat"
else
    echo "  python3 main.py wechat"
fi
echo ""
echo "  查看人格:"
echo "  python3 main.py persona list"
