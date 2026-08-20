#!/usr/bin/env bash
# ArHud SOME/IP Docker 完整测试 —— 一键运行
# 用法: bash docker/run_tests.sh
# 前置: 本机装有 Docker 且守护进程已启动
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="arhud-vsomeip-test"

# Docker CLI/buildx 状态写到工作区内（避免污染 ~/.docker；在受限环境/沙箱中也更稳）
export DOCKER_CONFIG="$ROOT/.dockerconfig"
export BUILDX_CONFIG="$DOCKER_CONFIG/buildx"
mkdir -p "$DOCKER_CONFIG"

echo "============================================================"
echo " ArHud SOME/IP Docker 测试 (目标: Ubuntu 22.04 + Python 3.10)"
echo "============================================================"

# ---- 1) 构建镜像 ----
echo "[1/11] 构建镜像 (编译 vsomeip 3.4.10 + vsomeip_py，首次约 5-15 分钟)..."
docker build -t "$IMAGE" -f "$ROOT/docker/Dockerfile" "$ROOT"

# ---- 2) 解码管线回归测试（pcap 生成/解码/序列化往返，不依赖 vsomeip 运行时）----
echo
echo "[2/11] 解码管线回归测试 (test_pipeline.py)..."
docker run --rm -v "$ROOT/vsomeip_example:/app:ro" -w /app "$IMAGE" python3 test_pipeline.py

# ---- 3) 真实 vsomeip 两进程收发集成测试 ----
echo
echo "[3/11] vsomeip 真实收发集成测试 (server.py + client.py)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/docker/integration_test.sh:/tests/integration_test.sh:ro" \
    -w /app \
    "$IMAGE" bash /tests/integration_test.sh

# ---- 4) 20 服务集成测试 ----
echo
echo "[4/11] 20 服务集成测试 (server_multi.py + client_multi.py)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/docker/integration_test_multi.sh:/tests/integration_test_multi.sh:ro" \
    -w /app \
    "$IMAGE" bash /tests/integration_test_multi.sh

# ---- 5) C++ 单应用订阅 20 服务验证 ----
echo
echo "[5/11] C++ 单应用订阅 20 服务验证 (min_cli_multi ↔ server_multi.py)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/docker/cpp_client_test_multi.sh:/tests/cpp_client_test_multi.sh:ro" \
    -v "$ROOT/docker/min_cli_multi.cpp:/tests/min_cli_multi.cpp:ro" \
    -w /app \
    "$IMAGE" bash /tests/cpp_client_test_multi.sh

# ---- 6) Windows 修复代码跨平台校验 ----
echo
echo "[6/11] Windows 修复代码跨平台校验 (windows/ ↔ vsomeip)..."
docker run --rm \
    -v "$ROOT/windows:/win:ro" \
    -v "$ROOT/docker/cross_check_windows.sh:/tests/cross_check_windows.sh:ro" \
    -w /win \
    "$IMAGE" bash /tests/cross_check_windows.sh

# ---- 7) pcap 全链路测试（构造 pcap → Ubuntu + Windows 程序）----
echo
echo "[7/11] pcap 全链路测试 (构造 pcap → Ubuntu + Windows 程序)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/windows:/win:ro" \
    -v "$ROOT/docker/integration_test_pcap.sh:/tests/integration_test_pcap.sh:ro" \
    -w /app \
    "$IMAGE" bash /tests/integration_test_pcap.sh

# ---- 8) C++ 单应用服务端提供 20 服务验证 ----
echo
echo "[8/11] C++ 单应用服务端提供 20 服务验证 (min_svc_multi ↔ C++/Python 客户端)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/docker/cpp_server_test_multi.sh:/tests/cpp_server_test_multi.sh:ro" \
    -v "$ROOT/docker/min_svc_multi.cpp:/tests/min_svc_multi.cpp:ro" \
    -v "$ROOT/docker/min_cli_multi.cpp:/tests/min_cli_multi.cpp:ro" \
    -w /app \
    "$IMAGE" bash /tests/cpp_server_test_multi.sh

# ---- 9) AR-HUD 23 服务集成测试 ----
echo
echo "[9/11] AR-HUD 23 服务集成测试 (hud_server.py + hud_client.py)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/hud:/hud:ro" \
    -v "$ROOT/docker/integration_test_hud.sh:/tests/integration_test_hud.sh:ro" \
    -w /app \
    "$IMAGE" bash /tests/integration_test_hud.sh

# ---- 10) AR-HUD pcap 全链路测试（生成 pcap → 服务端回放 → 客户端接收）----
echo
echo "[10/11] AR-HUD pcap 全链路测试 (生成 23 事件 pcap → 回放 → 接收)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/hud:/hud:ro" \
    -v "$ROOT/docker/integration_test_hud_pcap.sh:/tests/integration_test_hud_pcap.sh:ro" \
    -w /hud \
    "$IMAGE" bash /tests/integration_test_hud_pcap.sh

# ---- 11) AR-HUD C++ 客户端集成测试 ----
echo
echo "[11/11] AR-HUD C++ 客户端集成测试 (Python 服务端 ↔ C++ vsomeip 客户端)..."
docker run --rm \
    -v "$ROOT/hud_cpp:/hudcpp:ro" \
    -v "$ROOT/hud:/hud:ro" \
    -v "$ROOT/docker/integration_test_hud_cpp.sh:/tests/integration_test_hud_cpp.sh:ro" \
    -w /hudcpp \
    "$IMAGE" bash /tests/integration_test_hud_cpp.sh

echo
echo "============================================================"
echo " 全部测试完成 ✔"
echo "============================================================"
