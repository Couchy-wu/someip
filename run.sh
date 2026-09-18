#!/usr/bin/env bash
# =============================================================================
# HudAutoTest 启动脚本（Ubuntu 22.04 / 通用 Linux）
# -----------------------------------------------------------------------------
# 用法：
#   ./run.sh                # 启动 GUI
#   ./run.sh --check        # 仅做环境自检（不启动 GUI）
#   HUD_ZLG_LIB=/path/libzlgcan.so ./run.sh
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

# ---- 1. Python 检查 ----
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "[错误] 未找到 $PYTHON_BIN，请安装：sudo apt install -y python3 python3-pip python3-tk"
    exit 1
fi
PY_VER="$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "[信息] Python 版本: $PY_VER ($(command -v "$PYTHON_BIN"))"

# ---- 2. tkinter 检查（GUI 必需）----
if ! "$PYTHON_BIN" -c 'import tkinter' >/dev/null 2>&1; then
    echo "[错误] 缺少 tkinter：sudo apt install -y python3-tk"
    exit 1
fi

# ---- 3. 中文字体提示（UI 显示）----
if ! fc-list 2>/dev/null | grep -qi "CJK\|WenQuanYi\|Noto Sans CJK"; then
    echo "[警告] 未检测到中文字体，界面可能显示方块："
    echo "        sudo apt install -y fonts-noto-cjk"
fi

# ---- 4. 环境自检 ----
if [ "${1:-}" = "--check" ]; then
    exec "$PYTHON_BIN" tools/check_env.py
fi

# ---- 5. 启动 ----
echo "[信息] 启动 HudAutoTest ..."
exec "$PYTHON_BIN" main.py "$@"
