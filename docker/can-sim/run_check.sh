#!/usr/bin/env bash
# =====================================================================
# run_check.sh —— CAN VCI 适配层检查（无需 ZLG 硬件）
# =====================================================================
# 做两件事：
#   1) 编译 VCI 桩库（vci_stub.c）并跑适配层单测：
#      逻辑层（Python 假库，覆盖翻译规则）+ 真实 ABI 层（桩库，覆盖结构体布局）
#   2) 把项目自身的设备层（can_core.device）接到桩库上跑收发回环
#
# 用法：
#   ./run_check.sh              # 两步都跑（默认）
#   ./run_check.sh unit         # 只跑单测
#   ./run_check.sh demo         # 只跑业务层回环
#
# 依赖：gcc、pytest（容器/开发机上一般都有；Ubuntu: apt install -y gcc python3-pytest）
# =====================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="${PROJECT:-$(cd "${HERE}/../.." && pwd)}"
OUT="${OUT:-/tmp/hud-can-sim}"
STUB="${OUT}/libusbcanfd_stub.so"
MODE="${1:-all}"

mkdir -p "${OUT}"
echo "== 编译 VCI 桩库 =="
gcc -shared -fPIC -O2 -o "${STUB}" "${HERE}/vci_stub.c" || { echo "[失败] 桩库编译失败"; exit 2; }
echo "   ${STUB}"

cd "${PROJECT}"
rc=0

if [ "${MODE}" = "all" ] || [ "${MODE}" = "unit" ]; then
    echo "== 1) 适配层单测（逻辑层 + 真实 ABI）=="
    HUD_VCI_STUB_SO="${STUB}" python -m pytest tests/test_can_vci_adapter.py -q || rc=1
fi

if [ "${MODE}" = "all" ] || [ "${MODE}" = "demo" ]; then
    echo "== 2) 业务层回环（can_core.device 跑在桩库上）=="
    HUD_ZLG_LIB="${STUB}" python "${HERE}/loopback_demo.py" || rc=1
fi

echo "== 结果: $([ ${rc} -eq 0 ] && echo 通过 || echo 失败) =="
exit ${rc}
