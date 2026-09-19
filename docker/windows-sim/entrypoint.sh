#!/usr/bin/env bash
# =====================================================================
# entrypoint.sh —— Windows 验证容器入口
# =====================================================================
# 容器内约定的路径：
#   项目代码  : 宿主项目根目录挂载到 /work（Wine 中即 Z:\work）
#   Python    : C:\Program Files\Python313\python.exe（Windows 版 CPython 3.13）
#   驱动桩库  : /opt/stub/zlgcan.dll（MinGW 交叉编译，用于 CAN 加载链路验证）
#
# 子命令：
#   verify            运行完整功能验证套件（默认）
#   check             运行项目自检 tools/check_env.py
#   selftest          运行 hudcore 回归自测 tools/selftest.py
#   py <args...>      用 Windows Python 直接执行（如 py -m pip list）
#   script <file>     用 Windows Python 执行指定脚本（项目内相对路径）
#   shell             进入交互 bash
# =====================================================================
set -uo pipefail

# 说明：本项目用 python-build-standalone 的 Windows 构建（解压即用）安装到
#       C:\Python313（而非安装器的 "C:\Program Files\Python313"）。
WINPY="C:\\Python313\\python.exe"
WINPY_UNIX="${WINEPREFIX}/drive_c/Python313/python.exe"
PROJECT_DIR="${PROJECT_DIR:-/work}"
STUB_SRC="/opt/stub/zlgcan.dll"
STUB_DST="${PROJECT_DIR}/drivers/windows/zlgcan.dll"

log() { printf '\n\033[1;36m=== %s ===\033[0m\n' "$*"; }

STUB_CREATED=""          # 记录"本次运行是否由我们创建了桩库文件"

# 退出清理：桩库只是验证用的替身（本项目 drivers/windows/ 下的 zlgcan.dll 会被
# hudcore 当作真实驱动加载），因此除显式 KEEP_STUB=1 外，运行结束即删除，
# 避免把"假驱动"留在使用者的工作副本里造成误解。
cleanup() {
    if [ -n "${STUB_CREATED}" ] && [ "${KEEP_STUB:-0}" != "1" ] && [ -f "${STUB_DST}" ]; then
        rm -f "${STUB_DST}"
        echo "[清理] 已移除验证用桩库: ${STUB_DST}（保留请设置 KEEP_STUB=1）"
    fi
}
trap cleanup EXIT

# 加载原生 UCRT 的 DLL 覆盖（镜像构建时生成）：
# 缺它时 numpy/pandas/opencv 等 MSVC 构建的扩展会因 Wine 内置 UCRT 缺函数而崩溃。
if [ -f /opt/ucrt_overrides.env ]; then
    # shellcheck disable=SC1091
    . /opt/ucrt_overrides.env
    echo "[准备] 已加载原生 UCRT 覆盖（$(printf '%s' "${WINEDLLOVERRIDES}" | tr ';' '\n' | wc -l) 项）"
fi

# Windows Python 是否就绪
have_winpy() { [ -f "${WINPY_UNIX}" ]; }

# 统一用 xvfb-run 提供虚拟显示（Tk 需要；-a 自动挑选空闲 display）
# 说明：Windows 程序在 Wine + 模拟层下较慢，且个别调用可能阻塞，因此：
#   · 所有 wine 调用都套 timeout（默认 900s）；
#   · 验证套件的单项超时放宽到 180s（HUD_VERIFY_TIMEOUT）。
export HUD_VERIFY_TIMEOUT="${HUD_VERIFY_TIMEOUT:-180}"
WINE_TIMEOUT="${WINE_TIMEOUT:-900}"
DISPLAY_NUM="${DISPLAY_NUM:-:99}"

# 自起 Xvfb（不用 xvfb-run：实测在本环境的模拟层下会自动选号卡住）
ensure_display() {
    export DISPLAY="${DISPLAY_NUM}"
    if [ -S "/tmp/.X11-unix/X${DISPLAY_NUM#:}" ]; then return 0; fi
    rm -f "/tmp/.X${DISPLAY_NUM#:}-lock" 2>/dev/null || true
    Xvfb "${DISPLAY_NUM}" -screen 0 1280x800x24 >/tmp/xvfb.log 2>&1 &
    for _ in $(seq 1 30); do
        [ -S "/tmp/.X11-unix/X${DISPLAY_NUM#:}" ] && return 0
        sleep 0.5
    done
    echo "[警告] Xvfb 启动超时（GUI 相关项可能失败）" >&2
}

winrun() { ensure_display; timeout "${WINE_TIMEOUT}" wine "$@" </dev/null; }

prepare() {
    if ! have_winpy; then
        echo "[错误] 未找到 Windows 版 Python：${WINPY_UNIX}" >&2
        echo "       镜像构建阶段安装失败？请重新构建镜像。" >&2
        exit 2
    fi
    # 放置 CAN 驱动"桩库"（drivers/*/*.dll 已在 .gitignore，不会污染仓库）
    #   · 首选镜像内 MinGW 交叉编译的 zlgcan.dll（有真实 ZCAN_* 导出）
    #   · 镜像未编译（无 MinGW）时，用 Windows Python 自带的 python313.dll 充当：
    #     同样走「探测 → WinDLL 加载 → 调用导出函数」全链路，只是导出名不同
    mkdir -p "$(dirname "${STUB_DST}")"
    if [ -f "${STUB_DST}" ]; then
        echo "[准备] 复用已有 ${STUB_DST}（运行结束不会删除非本次创建的文件）"
    elif [ -f "${STUB_SRC}" ]; then
        cp -f "${STUB_SRC}" "${STUB_DST}"; STUB_CREATED=1
        echo "[准备] CAN 桩库: MinGW 编译版 zlgcan.dll"
    elif [ -f "${WINPY_UNIX%/python.exe}/python313.dll" ]; then
        cp -f "${WINPY_UNIX%/python.exe}/python313.dll" "${STUB_DST}"; STUB_CREATED=1
        echo "[准备] CAN 桩库: 回退为 python313.dll（导出 Py_GetVersion，用于验证加载链路）"
    else
        echo "[准备] 未找到可充当桩库的 DLL，第 9 项将 SKIP"
    fi
}

cmd_verify() {
    prepare
    log "Windows 运行时自检"
    winrun "${WINPY}" -c "import sys, platform; print('python', sys.version); print('platform', platform.system(), platform.release()); print('machine', platform.machine()); print('executable', sys.executable)" || true
    log "运行功能验证套件"
    local out_dir="${PROJECT_DIR}/docker/windows-sim"
    winrun "${WINPY}" "Z:\\work\\docker\\windows-sim\\verify_windows.py" \
        --expect win \
        --report "Z:\\work\\docker\\windows-sim\\verify_report.md" \
        --json   "Z:\\work\\docker\\windows-sim\\verify_report.json" \
        ${VERIFY_SKIP:+--skip "${VERIFY_SKIP}"}
    local rc=$?
    log "套件退出码: ${rc}"
    return ${rc}
}

cmd_check() {
    prepare
    winrun "${WINPY}" "Z:\\work\\tools\\check_env.py" || true
}

cmd_selftest() {
    prepare
    winrun "${WINPY}" "Z:\\work\\tools\\selftest.py" || true
}

cmd_py() {
    prepare
    winrun "${WINPY}" "$@"
}

cmd_script() {
    prepare
    local rel="$1"; shift
    winrun "${WINPY}" "Z:\\work\\${rel//\//\\}" "$@"
}

cmd_gui() {
    prepare
    log "启动 GUI（无显示器环境；用于验证窗口能否创建）"
    timeout 25 winrun "${WINPY}" "Z:\\work\\main.py" && echo "main.py 自行退出(0)" || echo "main.py 被超时终止（GUI 常驻属正常现象）"
}

case "${1:-verify}" in
    verify)   shift; cmd_verify "$@" ;;
    check)    shift; cmd_check "$@" ;;
    selftest) shift; cmd_selftest "$@" ;;
    py)       shift; cmd_py "$@" ;;
    script)   shift; cmd_script "$@" ;;
    gui)      shift; cmd_gui "$@" ;;
    shell)    exec bash ;;
    *)        echo "未知子命令: $1"; echo "可用: verify|check|selftest|py|script|gui|shell"; exit 2 ;;
esac
