#!/usr/bin/env bash
# =====================================================================
# install_python.sh —— 在 Wine 容器内安装 Windows 版 CPython
# =====================================================================
# 为什么需要"两条路"：
#   python.org 的安装器是 WiX Burn 引导包，正常走静默安装（/quiet）即可；
#   但在 Wine 下偶发失败（引导包 GUI/权限细节）。因此这里做两级回退：
#     1) 静默安装：      py.exe /quiet InstallAllUsers=1 PrependPath=1 Include_tcltk=1
#     2) 解包后离线安装：py.exe /layout <dir> 解出 MSI，再用 msiexec /a 逐个展开
#   任一路成功即返回，最终统一校验 python.exe 与 tkinter 是否可用。
#
# 参数：$1 = 版本号（默认 3.13.7）
# 环境：WINEPREFIX 必须已初始化；xvfb-run 可用
# =====================================================================
set -uo pipefail

PY_VER="${1:-3.13.7}"
PY_DIR_WIN='C:\Python313'
PY_DIR_UNIX="${WINEPREFIX}/drive_c/Python313"
INSTALLER="/tmp/python-${PY_VER}-amd64.exe"
URL="https://www.python.org/ftp/python/${PY_VER}/python-${PY_VER}-amd64.exe"

win() { xvfb-run -a --server-args="-screen 0 1024x768x24" wine "$@"; }

echo "== 下载 Windows CPython ${PY_VER} =="
for i in 1 2 3 4; do
    if curl -fsSL --retry 3 --retry-delay 2 --connect-timeout 20 -o "${INSTALLER}" "${URL}"; then
        break
    fi
    echo "  下载失败，第 ${i} 次重试…"
    sleep 3
done
[ -s "${INSTALLER}" ] || { echo "[错误] 安装器下载失败: ${URL}" >&2; exit 1; }
ls -la "${INSTALLER}"

# ---------------------------------------------------------------- 路径 1：静默安装
echo "== 尝试路径 1：静默安装 =="
win "${INSTALLER}" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_tcltk=1 \
    TargetDir="${PY_DIR_WIN}" || echo "  （静默安装返回非 0，稍后校验实际结果）"

if [ ! -f "${PY_DIR_UNIX}/python.exe" ]; then
    echo "== 路径 1 未产出 python.exe，尝试路径 2：解包 + msiexec 展开 =="
    LAYOUT_UNIX="${WINEPREFIX}/drive_c/pylayout"
    win "${INSTALLER}" /layout 'C:\pylayout' /quiet || true
    if [ -d "${LAYOUT_UNIX}" ]; then
        echo "  解包内容："; ls -1 "${LAYOUT_UNIX}" | head -20
        # 按依赖顺序展开：core → exe → lib → tcltk → pip → dev
        for msi in core exe lib tcltk pip dev ucrt; do
            f=$(ls "${LAYOUT_UNIX}"/${msi}*.msi 2>/dev/null | head -1)
            if [ -n "${f}" ]; then
                base=$(basename "${f}")
                echo "  msiexec /a ${base}"
                win msiexec /a "C:\\pylayout\\${base}" /qn TARGETDIR="${PY_DIR_WIN}" || \
                    echo "    （${base} 展开返回非 0，继续）"
            fi
        done
    else
        echo "[错误] /layout 也未产出 MSI" >&2
    fi

    # msiexec /a 会展开成 TARGETDIR 下的子目录结构，做一次归一化
    if [ ! -f "${PY_DIR_UNIX}/python.exe" ]; then
        found=$(find "${WINEPREFIX}/drive_c" -maxdepth 4 -iname "python.exe" 2>/dev/null | head -1)
        if [ -n "${found}" ]; then
            echo "  在 ${found} 找到 python.exe，移动到 ${PY_DIR_UNIX}"
            mkdir -p "${PY_DIR_UNIX}"
            cp -a "$(dirname "${found}")/." "${PY_DIR_UNIX}/" 2>/dev/null || true
        fi
    fi
fi

# ---------------------------------------------------------------- 校验
echo "== 校验安装结果 =="
if [ ! -f "${PY_DIR_UNIX}/python.exe" ]; then
    echo "[错误] Windows CPython 安装失败：未找到 ${PY_DIR_UNIX}/python.exe" >&2
    echo "       容器内可手动排查： xvfb-run -a wine ${INSTALLER}" >&2
    exit 1
fi

win "${PY_DIR_WIN}\\python.exe" -V
echo "== tkinter 可用性 =="
win "${PY_DIR_WIN}\\python.exe" -c "import tkinter, sys; print('tkinter OK', tkinter.TkVersion, 'python', sys.version.split()[0])" \
    || echo "[警告] tkinter 不可用（GUI 相关验证项会标记 SKIP/FAIL）"

echo "== 安装完成：${PY_DIR_UNIX} =="
