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
FROM --platform=linux/amd64 ubuntu:22.04 AS base

ARG PY_VER=3.13.15
# 国内网络下建议使用镜像源（构建时可用 --build-arg 覆盖）
ARG APT_MIRROR=http://mirrors.aliyun.com/ubuntu
ARG PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/
ARG WITH_MINGW=0
# PY_SOURCE: standalone（默认，免安装器）| installer（python.org 安装器）
ARG PY_SOURCE=standalone
ARG DEBIAN_FRONTEND=noninteractive

ENV DEBIAN_FRONTEND=noninteractive \
    WINEPREFIX=/wine \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    DISPLAY=:99 \
    LANG=C.UTF-8 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1 \
    WINEPATH="C:\\Python313;C:\\Python313\\Scripts"

# ---------------------------------------------------------------- 1. 换源 + 基础依赖
# 说明：
#   · 只装 amd64（不加 i386 架构），因此不下载 i386 包索引，体积/时间减半；
#     Wine 6.x 的 amd64 版本足以运行 64 位 Windows 程序（本用例的 CPython 即 x64）。
#   · MinGW 仅用于交叉编译 CAN 驱动桩库；如网络受限可保持默认 0，
#     此时入口脚本会自动用 Windows Python 自带的 python313.dll 充当桩库
#     （同样验证「探测 → WinDLL 加载 → 调用导出」链路）。
RUN set -eux; \
    echo 'Acquire::Retries "10"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' \
        > /etc/apt/apt.conf.d/99-retries; \
    sed -i "s|http://archive.ubuntu.com/ubuntu|${APT_MIRROR}|g; \
            s|http://security.ubuntu.com/ubuntu|${APT_MIRROR}|g" /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl wget gnupg xz-utils unzip p7zip-full \
        xvfb xauth x11-utils \
        fonts-wqy-microhei fontconfig \
        libgl1 libglib2.0-0 libusb-1.0-0 \
        procps file less python3-pip; \
    rm -rf /var/lib/apt/lists/*

# Wine 依赖包较大（libwine 约 84MB + libllvm15 等），弱网/容器 DNS 抖动时
# 单次下载常中断。这里做两件事：
#   1) 多镜像故障转移：某个镜像解析/下载失败时自动换下一个；
#   2) 每轮重试前重新 apt-get update，并开启 Acquire::Retries。
# 只要有一轮成功即通过；全部失败则构建报错（便于定位而不是静默降级）。
ARG APT_FALLBACK_MIRRORS="mirrors.aliyun.com mirrors.tuna.tsinghua.edu.cn mirrors.ustc.edu.cn archive.ubuntu.com mirrors.cloud.tencent.com"
RUN set -eux; \
    ok=0; \
    for m in ${APT_FALLBACK_MIRRORS}; do \
        echo "=== 使用镜像 ${m} 尝试安装 Wine ==="; \
        sed -i "s|http://[^ ]*/ubuntu|http://${m}/ubuntu|g" /etc/apt/sources.list; \
        apt-get update -qq || { echo "  apt update 失败，换镜像"; continue; }; \
        if apt-get install -y --no-install-recommends wine64 wine; then \
            ok=1; echo "Wine 安装成功（镜像 ${m}）"; break; \
        fi; \
        apt-get install -y --no-install-recommends -f || true; \
    done; \
    [ "${ok}" = "1" ] || { echo "所有镜像均失败"; exit 1; }; \
    command -v wine64; wine64 --version; \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------- 3. 初始化 Wine 前缀（报告为 Win10）
FROM base AS winebase
RUN set -eux; \
    export DISPLAY=:99; \
    Xvfb :99 -screen 0 1280x800x24 >/tmp/xvfb.log 2>&1 & \
    for i in $(seq 1 30); do [ -S /tmp/.X11-unix/X99 ] && break; sleep 0.5; done; \
    timeout 300 wineboot --init >/dev/null 2>&1 || true; \
    timeout 180 wine reg add "HKCU\\Software\\Wine" /v Version /d win10 /f >/dev/null 2>&1 || true; \
    ls -la "${WINEPREFIX}/drive_c" | head -5

# ---------------------------------------------------------------- 3.5 阶段性镜像（调试用）
# 需要反复调试 Windows Python 安装方式时：
#   docker build --target winebase -t hudautotest-winebase .
# 然后 docker run -it hudautotest-winebase shell 进容器手工验证，
# 成功后再把命令固化到 install_python.sh（避免每次全量重建）。
# ---------------------------------------------------------------- 4. Wine + Windows CPython（可独立构建用于调试）
#   调试用法：docker build --target winepy -t hudautotest-winepy .
#   得到"Wine + Windows 版 CPython"镜像，可在其中反复试验 pip/GUI，
#   无需每次重跑 apt + Wine 安装。
FROM winebase AS winepy
# 注意：多阶段构建中 ARG 不跨 stage 继承，每个使用它的 stage 都要重新声明
# （否则会出现 "PIP_INDEX: parameter not set" 之类的构建失败）。
ARG PY_VER=3.13.15
ARG PY_SOURCE=standalone
ARG PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/
ARG WITH_MINGW=0
COPY install_python.sh /opt/install_python.sh
RUN chmod +x /opt/install_python.sh && PY_SOURCE="${PY_SOURCE}" /opt/install_python.sh "${PY_VER}"


# ---------------------------------------------------------------- 5. 依赖安装 + 原生 UCRT（Windows wheel）
# 覆盖 GUI 主链路与无硬件依赖功能；torch / paddleocr 等重依赖不预装：
#   · 验证套件对重依赖缺失按"优雅降级"判定（OCR/YOLO 属可选功能）
FROM winepy AS pysim
ARG PY_VER=3.13.15
ARG PY_SOURCE=standalone
ARG PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/
ARG WITH_MINGW=0
# Windows 程序（numpy/pandas/opencv 等 MSVC 构建）依赖 **UCRT**：
#   Wine 6 自带的 ucrtbase 缺少 fetestexcept 等实现，导入 numpy 会直接
#   `unimplemented function api-ms-win-crt-runtime-l1-1-0.dll.fetestexcept` 而崩溃。
#   解法：装入 **原生 UCRT**（conda-forge 的 ucrt 包，含 ucrtbase.dll 与
#   api-ms-win-crt-*.dll 全套转发器），并用 WINEDLLOVERRIDES 让 Wine 优先用原生版。
#   实测装入后 numpy 2.x 可正常计算（求和/行列式均正确）。
ARG UCRT_URL=https://conda.anaconda.org/conda-forge/win-64/ucrt-10.0.22621.0-h57928b3_0.tar.bz2
RUN set -eux; \
    curl -fsSL --retry 5 --retry-all-errors -o /tmp/ucrt.tar.bz2 "${UCRT_URL}"; \
    mkdir -p /tmp/ucrt; \
    python3 -c "import tarfile; tarfile.open('/tmp/ucrt.tar.bz2').extractall('/tmp/ucrt')"; \
    SYS="${WINEPREFIX}/drive_c/windows/system32"; \
    cp -f /tmp/ucrt/api-ms-win-crt-*.dll "${SYS}/"; \
    cp -f /tmp/ucrt/ucrtbase.dll "${SYS}/"; \
    ls "${SYS}" | grep -c '^api-ms-win-crt-'; \
    OVR=$(ls /tmp/ucrt/api-ms-win-crt-*.dll | xargs -n1 basename \
          | sed 's/$/=n/' | paste -sd';'); \
    printf 'export WINEDLLOVERRIDES="%s;ucrtbase=n"\n' "${OVR}" > /opt/ucrt_overrides.env; \
    echo "--- 覆盖项数量: $(tr ';' '\n' < /opt/ucrt_overrides.env | wc -l) ---"

# 说明（Wine 下 pip 的坑与解法）：
#   实测 Wine 6 + Windows CPython 3.13：`ssl.SSLContext(PROTOCOL_TLS_*)` 直接抛
#   `[SSL] unknown error (_ssl.c:3138)`（OpenSSL 上下文无法初始化），导致 pip
#   任何网络操作都失败（pip 26 还会先建 truststore 上下文）。
#   因此**不在 Wine 里跑 pip**，改为：用容器自带的 Linux pip 以
#   `--platform win_amd64 --only-binary=:all:` 下载并解压 **Windows wheel** 到
#   Wine 的 site-packages —— pip 会正确处理 .data/purelib/platlib 布局，
#   与在 Windows 上用 pip 安装效果一致，且完全不需要 Wine 的 TLS 能力。
RUN set -eux; \
    SP="${WINEPREFIX}/drive_c/Python313/Lib/site-packages"; \
    PKGS="numpy pandas openpyxl pillow opencv-python pyyaml requests psutil \
          pyperclip watchdog ffmpeg-python tqdm natsort"; \
    python3 -m pip install --upgrade pip --disable-pip-version-check -i "${PIP_INDEX}"; \
    python3 -m pip install --disable-pip-version-check -i "${PIP_INDEX}" \
        --target "${SP}" \
        --platform win_amd64 --python-version 3.13 --implementation cp --abi cp313 \
        --only-binary=:all: --upgrade ${PKGS}; \
    echo "--- 已装入 site-packages 的顶层条目 ---"; \
    ls "${SP}" | head -30

# ---------------------------------------------------------------- 5.5 依赖自检（在 Wine 的 Windows Python 中真实导入）
# 用独立脚本文件而不是 heredoc —— 传统 builder 不支持 RUN 内 heredoc。
COPY check_deps.py /opt/check_deps.py
RUN set -eux; \
    . /opt/ucrt_overrides.env; \
    export DISPLAY=:99; \
    Xvfb :99 -screen 0 1280x800x24 >/tmp/xvfb.log 2>&1 & \
    for i in $(seq 1 30); do [ -S /tmp/.X11-unix/X99 ] && break; sleep 0.5; done; \
    timeout 300 wine "C:\\Python313\\python.exe" 'Z:\\opt\\check_deps.py'

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
