# ArHud SOME/IP 完整测试环境
# ============================================================
# 目标环境: Ubuntu 22.04 + Python 3.10 + COVESA vsomeip 3.4.10 + vsomeip_py
#
# 构建:   docker build -f docker/Dockerfile -t arhud-vsomeip-test .
# 运行:   bash docker/run_tests.sh            （一键: 解码管线测试 + 真实 vsomeip 收发集成测试）
#
# 说明:
#   - vsomeip 固定 3.4.10（已核对 vsomeip_py 的 C++ 扩展用到的全部 API 在该版本存在）
#   - 容器内测试用两个独立进程跑 server.py / client.py，走真实 UDS 路由管理器注册
#   - 容器内默认关闭服务发现(ARHUD_SD=false)，使用本地静态路由，不依赖多播

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    TZ=UTC

# ---------- 1) 基础依赖 ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        ca-certificates \
        python3 \
        python3-dev \
        python3-pip \
        python3-setuptools \
        libboost-system-dev \
        libboost-thread-dev \
        libboost-log-dev \
        libboost-filesystem-dev \
        libboost-program-options-dev \
    && rm -rf /var/lib/apt/lists/*

# ---------- 2) 编译安装 vsomeip C++ 库 (3.4.10) ----------
RUN git clone --depth 1 --branch 3.4.10 https://github.com/COVESA/vsomeip.git /opt/vsomeip \
    && mkdir -p /opt/vsomeip/build \
    && cd /opt/vsomeip/build \
    && cmake -DCMAKE_INSTALL_PREFIX=/usr/local \
             -DENABLE_EXAMPLES=OFF \
             -DENABLE_TESTS=OFF \
             -DENABLE_SIGNAL_HANDLING=ON \
             -DENABLE_DLT=OFF \
             -DENABLE_MULTIPLE_ROUTING_MANAGERS=OFF \
             .. \
    && make -j"$(nproc)" \
    && make install \
    && ldconfig

# ---------- 3) 编译安装 vsomeip_py (Python 绑定) ----------
RUN git clone --depth 1 https://github.com/COVESA/vsomeip_py.git /opt/vsomeip_py_src \
    && pip3 install --no-cache-dir /opt/vsomeip_py_src \
    && rm -rf /opt/vsomeip_py_src

# ---------- 4) 其余 Python 依赖 ----------
RUN pip3 install --no-cache-dir scapy

# ---------- 5) 示例代码（运行时可被 -v 挂载覆盖） ----------
WORKDIR /app
COPY vsomeip_example/*.py /app/

# 校验安装结果
RUN python3 -c "import scapy; print('scapy', scapy.__version__)" \
 && python3 -c "from vsomeip_py.vsomeip import vSOMEIP; print('vsomeip_py OK')"

CMD ["bash"]
