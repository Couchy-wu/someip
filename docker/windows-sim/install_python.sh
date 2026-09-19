#!/usr/bin/env bash
# =====================================================================
# install_python.sh —— 在 Wine 容器内准备 Windows 版 CPython
# =====================================================================
# 为什么默认不用 python.org 的安装器（.exe）？
#   实测（Ubuntu 22.04 + Wine 6.0.3，amd64 容器）：
#     · python-3.13.x-amd64.exe 是 WiX Burn 引导包，静默安装在 Wine 下返回非 0，
#       且 /layout 也不产出 MSI（引导包依赖的 UCRT/COM 细节 Wine 未完全实现）；
#       补装 vcrun2022（真实 UCRT + vcruntime140）后依然失败。
#     · 因此改用 **python-build-standalone**（Astral/IndyGreg 维护的 CPython
#       独立构建）Windows x86_64 包：解压即用，自带 **tkinter / tcl-tk / pip**，
#       无需安装器 —— 实测在 Wine 6 下可直接 `python.exe -V`。
#
# 两条路径（用环境变量 PY_SOURCE 选择）：
#   PY_SOURCE=standalone （默认，推荐）：下载 install_only.tar.gz 解压到 C:\Python313
#   PY_SOURCE=installer           ：python.org 安装器 /quiet 静默安装
#                                   （Wine 版本较新时可尝试；失败会自动回退）
#
# 参数：$1 = 版本号（默认 3.13.15）
# 环境：WINEPREFIX 已初始化；xvfb-run / curl / tar 可用
# =====================================================================
set -uo pipefail

PY_VER="${1:-3.13.15}"
PY_SOURCE="${PY_SOURCE:-standalone}"
PY_DIR_WIN='C:\Python313'
PY_DIR_UNIX="${WINEPREFIX}/drive_c/Python313"
PBS_TAG="${PBS_TAG:-20260901}"          # python-build-standalone 发布标签

# 说明（踩坑记录）：
#   ① `wine python.exe -c "..."` 在本环境会挂起 —— 需要执行代码时写成 .py 文件；
#   ② `xvfb-run -a` 同样会挂起（自动选号 + 残留锁），改为**自己起一个 Xvfb**
#      并固定 DISPLAY，实测稳定；
#   ③ 所有 wine 调用都套 timeout，避免任何一步永久阻塞。
WIN_TIMEOUT="${WIN_TIMEOUT:-300}"
DISPLAY_NUM="${DISPLAY_NUM:-:99}"

ensure_display() {
    export DISPLAY="${DISPLAY_NUM}"
    if [ -S "/tmp/.X11-unix/X${DISPLAY_NUM#:}" ]; then return 0; fi
    rm -f "/tmp/.X${DISPLAY_NUM#:}-lock" 2>/dev/null || true
    Xvfb "${DISPLAY_NUM}" -screen 0 1280x800x24 >/tmp/xvfb.log 2>&1 &
    for _ in $(seq 1 30); do
        [ -S "/tmp/.X11-unix/X${DISPLAY_NUM#:}" ] && return 0
        sleep 0.5
    done
    echo "[警告] Xvfb 启动超时，后续 GUI 相关校验可能失败" >&2
    return 1
}

win() { ensure_display >/dev/null 2>&1 || true; timeout "${WIN_TIMEOUT}" wine "$@" </dev/null; }

# 以"脚本文件"方式在 Windows Python 中执行一段代码（避免 -c 挂起）
win_py_code() {
    local code="$1"
    printf '%s\n' "${code}" > /tmp/_wincheck.py
    win "${PY_DIR_WIN}\\python.exe" 'Z:\\tmp\\_wincheck.py'
}

echo "==================================================================="
echo " 准备 Windows 版 CPython ${PY_VER}（方式: ${PY_SOURCE}）"
echo " 目标: ${PY_DIR_UNIX}"
echo "==================================================================="

# ---------------------------------------------------------------- 路径 A：独立构建（默认）
install_standalone() {
    local url="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/cpython-${PY_VER}+${PBS_TAG}-x86_64-pc-windows-msvc-install_only.tar.gz"
    local tgz="/tmp/python-standalone.tar.gz"

    echo "== 下载 python-build-standalone: ${url}"
    for i in 1 2 3 4 5; do
        if curl -fL --retry 5 --retry-all-errors --connect-timeout 20 \
                -o "${tgz}" "${url}"; then break; fi
        echo "  下载失败，第 ${i} 次重试…"; sleep 3
    done
    [ -s "${tgz}" ] || { echo "[错误] 下载失败: ${url}" >&2; return 1; }
    ls -la "${tgz}"

    echo "== 解压到 ${PY_DIR_UNIX}"
    rm -rf /tmp/pyx "${PY_DIR_UNIX}"
    mkdir -p /tmp/pyx
    tar -xzf "${tgz}" -C /tmp/pyx || return 1
    if [ -d /tmp/pyx/python ]; then
        cp -a /tmp/pyx/python "${PY_DIR_UNIX}" || return 1
    else
        echo "[错误] 压缩包结构异常，未找到 python/ 目录" >&2
        ls -la /tmp/pyx; return 1
    fi
    ls "${PY_DIR_UNIX}" | head -12
    return 0
}

# ---------------------------------------------------------------- 路径 B：python.org 安装器
install_official_installer() {
    local exe="/tmp/python-${PY_VER}-amd64.exe"
    local url="https://www.python.org/ftp/python/${PY_VER}/python-${PY_VER}-amd64.exe"

    echo "== 下载 python.org 安装器: ${url}"
    for i in 1 2 3 4 5; do
        if curl -fL --retry 3 --connect-timeout 20 -o "${exe}" "${url}"; then break; fi
        echo "  下载失败，第 ${i} 次重试…"; sleep 3
    done
    [ -s "${exe}" ] || { echo "[错误] 安装器下载失败" >&2; return 1; }

    echo "== 静默安装（AllUsers=0 → 用户目录，避免权限问题）"
    win "${exe}" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 \
        Include_tcltk=1 TargetDir="${PY_DIR_WIN}" || \
        echo "  （静默安装返回非 0，继续校验实际结果）"
    [ -f "${PY_DIR_UNIX}/python.exe" ] && return 0

    echo "== 静默安装未产出 python.exe，尝试 /layout + msiexec 展开"
    local layout_unix="${WINEPREFIX}/drive_c/pylayout"
    win "${exe}" /layout 'C:\pylayout' /quiet || true
    if [ -d "${layout_unix}" ]; then
        for msi in core exe lib tcltk pip dev ucrt; do
            f=$(ls "${layout_unix}"/${msi}*.msi 2>/dev/null | head -1)
            if [ -n "${f}" ]; then
                echo "  msiexec /a $(basename "${f}")"
                win msiexec /a "C:\\pylayout\\$(basename "${f}")" /qn \
                    TARGETDIR="${PY_DIR_WIN}" || true
            fi
        done
    fi
    [ -f "${PY_DIR_UNIX}/python.exe" ] && return 0
    # 兜底：全盘找 python.exe 再归位
    local found
    found=$(find "${WINEPREFIX}/drive_c" -maxdepth 4 -iname "python.exe" 2>/dev/null | head -1)
    if [ -n "${found}" ]; then
        echo "  在 ${found} 找到 python.exe，复制到 ${PY_DIR_UNIX}"
        mkdir -p "${PY_DIR_UNIX}"
        cp -a "$(dirname "${found}")/." "${PY_DIR_UNIX}/" 2>/dev/null || true
    fi
    [ -f "${PY_DIR_UNIX}/python.exe" ]
}

# ---------------------------------------------------------------- 执行 + 校验
ok=0
if [ "${PY_SOURCE}" = "installer" ]; then
    install_official_installer && ok=1
    if [ "${ok}" = "0" ]; then
        echo "== 安装器方式失败 → 回退 standalone =="
        install_standalone && ok=1
    fi
else
    install_standalone && ok=1
    if [ "${ok}" = "0" ]; then
        echo "== standalone 失败 → 回退 python.org 安装器 =="
        install_official_installer && ok=1
    fi
fi

if [ "${ok}" != "1" ] || [ ! -f "${PY_DIR_UNIX}/python.exe" ]; then
    echo "[错误] Windows CPython 准备失败：未找到 ${PY_DIR_UNIX}/python.exe" >&2
    exit 1
fi

echo "== 版本与能力校验（脚本文件方式，带超时）=="
win "${PY_DIR_WIN}\\python.exe" -V || echo "[警告] python -V 超时/失败"
cat > /tmp/_wincheck.py <<'PYEOF'
import sys, platform
print("platform :", platform.system(), platform.machine())
print("version  :", sys.version.split()[0])
try:
    import tkinter
    print("tkinter  : OK", tkinter.TkVersion)
except Exception as exc:
    print("tkinter  : FAIL", exc)
try:
    import pip
    print("pip      : OK", pip.__version__)
except Exception as exc:
    print("pip      : FAIL", exc)
PYEOF
win "${PY_DIR_WIN}\\python.exe" 'Z:\\tmp\\_wincheck.py' || echo "[警告] 能力校验超时"
echo "== 完成：${PY_DIR_UNIX} =="
