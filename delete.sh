#!/usr/bin/env bash
# Pal - Clean removal script
# Usage: bash delete.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

echo ""
echo "  Pal - Uninstaller"
echo "  =================="
echo "  This will remove:"
echo "    - $PROJECT_ROOT (project directory)"
echo "    - ~/bin/pal (global command)"
echo "    - ~/bin/pal-ui (UI launcher)"
echo ""

read -p "  Are you sure? Type 'DELETE' to confirm: " confirm
if [ "$confirm" != "DELETE" ]; then
    echo "  Cancelled."
    exit 0
fi

echo ""
echo "[1/3] Removing global commands..."
rm -f "$HOME/bin/pal" "$HOME/bin/pal-ui"
echo "  Commands removed."

echo "[2/3] Removing project directory..."
rm -rf "$PROJECT_ROOT"
echo "  Project removed."

echo "[3/3] Cleaning PATH..."
sed -i '/export PATH="$HOME\/bin:$PATH"/d' "$HOME/.bashrc" 2>/dev/null || true
echo "  PATH cleaned."

echo ""
echo "  Uninstallation complete."
echo "  Note: Python packages (textual, flask, requests, Pillow) were not removed."
echo "  Remove manually: pip uninstall textual flask requests python-dotenv Pillow"
echo ""
