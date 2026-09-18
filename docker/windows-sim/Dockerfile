# syntax=docker/dockerfile:1
# =====================================================================
# HudAutoTest —— Windows 环境验证镜像（在 Linux 容器内构造 Windows 运行时）
# =====================================================================
# 为什么这样设计：
#   Docker 无法运行 Windows 内核，所以在容器内用 **Wine**（Windows API 兼容层）
#   承载 **Windows 版 CPython 3.13**，再用 Xvfb 提供虚拟显示，得到一个真实的
#   Windows 语义运行时：
#     · platform.system() == "Windows"、sys.platform == "win32"
#     · ctypes.WinDLL / LoadLibrary、os.startfile、PATH 用 ";" 分隔、盘符路径
#     · 安装的是 python.org 的 **win_amd64 官方构建**（含 tkinter / tcl-tk）
#     · pip 安装的是 **Windows wheel**（win_amd64），与现场部署一致
#
# 架构说明：Apple Silicon 宿主上用 --platform=linux/amd64（Rosetta 加速），
#           容器内 uname -m == x86_64，Wine 直接运行 Windows x64 二进制。
#
# 构建：
#   docker build --platform=linux/amd64 -f Dockerfile -t hudautotest-win:py313 .
#   （或直接 ./build.sh）
# =====================================================================
FROM --platform=linux/amd64 ubuntu:22.04

ARG PY_VER=3.13.7
# 国内网络下建议使用镜像源（构建时可用 --build-arg 覆盖）
ARG APT_MIRROR=http://mirrors.aliyun.com/ubuntu
ARG PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/
ARG WITH_MINGW=0
ARG DEBIAN_FRONTEND=noninteractive

ENV DEBIAN_FRONTEND=noninteractive \
    WINEPREFIX=/wine \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    DISPLAY=:99 \
    LANG=C.UTF-8 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1

# ---------------------------------------------------------------- 1. 换源 + 基础依赖
# 说明：
#   · 只装 amd64（不加 i386 架构），因此不下载 i386 包索引，体积/时间减半；
#     Wine 6.x 的 amd64 版本足以运行 64 位 Windows 程序（本用例的 CPython 即 x64）。
#   · MinGW 仅用于交叉编译 CAN 驱动桩库；如网络受限可保持默认 0，
#     此时入口脚本会自动用 Windows Python 自带的 python313.dll 充当桩库
#     （同样验证「探测 → WinDLL 加载 → 调用导出」链路）。
RUN set -eux; \
    sed -i "s|http://archive.ubuntu.com/ubuntu|${APT_MIRROR}|g; \
            s|http://security.ubuntu.com/ubuntu|${APT_MIRROR}|g" /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl wget gnupg xz-utils unzip p7zip-full \
        xvfb xauth x11-utils \
        wine64 wine \
        fonts-wqy-microhei fontconfig \
        libgl1 libglib2.0-0 libusb-1.0-0 \
        procps file less; \
    if [ "${WITH_MINGW}" = "1" ]; then \
        apt-get install -y --no-install-recommends gcc-mingw-w64-x86-64; \
    fi; \
    rm -rf /var/lib/apt/lists/*; \
    wine --version

# ---------------------------------------------------------------- 3. 初始化 Wine 前缀（报告为 Win10）
RUN xvfb-run -a wineboot --init >/dev/null 2>&1 || true; \
    xvfb-run -a wine reg add "HKCU\\Software\\Wine" /v Version /d win10 /f >/dev/null 2>&1 || true; \
    ls -la "${WINEPREFIX}/drive_c" | head -5

# ---------------------------------------------------------------- 4. 安装 Windows CPython
COPY install_python.sh /opt/install_python.sh
RUN chmod +x /opt/install_python.sh && /opt/install_python.sh "${PY_VER}"

# ---------------------------------------------------------------- 5. 轻量依赖（Windows wheel）
# 覆盖 GUI 主链路与无硬件依赖功能；torch / paddleocr 等重依赖不预装：
#   · 验证套件对重依赖缺失按"优雅降级"判定（OCR/YOLO 属可选功能）
#   · 需要时在容器内用 `run_verify.sh py -m pip install ...` 追加安装
RUN set -e; \
    WINPY="${WINEPREFIX}/drive_c/Python313/python.exe"; \
    xvfb-run -a wine "${WINPY}" -m pip install --upgrade pip --disable-pip-version-check -i "${PIP_INDEX}"; \
    xvfb-run -a wine "${WINPY}" -m pip install --disable-pip-version-check -i "${PIP_INDEX}" \
        numpy pandas openpyxl pillow opencv-python pyyaml requests psutil; \
    xvfb-run -a wine "${WINPY}" -m pip list

# ---------------------------------------------------------------- 6. CAN 驱动桩库
# WITH_MINGW=1 时用 MinGW 交叉编译带 ZCAN_* 导出的 zlgcan.dll；
# 否则跳过（入口脚本会回退用 python313.dll 充当桩库）。
COPY stub_zlgcan.c /opt/stub/stub_zlgcan.c
RUN if [ "${WITH_MINGW}" = "1" ]; then \
        x86_64-w64-mingw32-gcc -shared -O2 -o /opt/stub/zlgcan.dll /opt/stub/stub_zlgcan.c; \
        file /opt/stub/zlgcan.dll; \
        x86_64-w64-mingw32-objdump -p /opt/stub/zlgcan.dll | grep -E "ZCAN_|VCI_|zlgcan_stub" | head -8; \
    else \
        echo "跳过 MinGW 桩库（WITH_MINGW=0）：将使用 python313.dll 作为回退桩库"; \
    fi

# ---------------------------------------------------------------- 7. 入口
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["verify"]
