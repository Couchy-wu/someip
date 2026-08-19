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
echo "[1/5] 构建镜像 (编译 vsomeip 3.4.10 + vsomeip_py，首次约 5-15 分钟)..."
docker build -t "$IMAGE" -f "$ROOT/docker/Dockerfile" "$ROOT"

# ---- 2) 解码管线回归测试（pcap 生成/解码/序列化往返，不依赖 vsomeip 运行时）----
echo
echo "[2/5] 解码管线回归测试 (test_pipeline.py)..."
docker run --rm -v "$ROOT/vsomeip_example:/app:ro" -w /app "$IMAGE" python3 test_pipeline.py

# ---- 3) 真实 vsomeip 两进程收发集成测试 ----
echo
echo "[3/5] vsomeip 真实收发集成测试 (server.py + client.py)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/docker/integration_test.sh:/tests/integration_test.sh:ro" \
    -w /app \
    "$IMAGE" bash /tests/integration_test.sh

# ---- 4) 20 服务集成测试 ----
echo
echo "[4/5] 20 服务集成测试 (server_multi.py + client_multi.py)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/docker/integration_test_multi.sh:/tests/integration_test_multi.sh:ro" \
    -w /app \
    "$IMAGE" bash /tests/integration_test_multi.sh

# ---- 5) C++ 单应用订阅 20 服务验证 ----
echo
echo "[5/5] C++ 单应用订阅 20 服务验证 (min_cli_multi ↔ server_multi.py)..."
docker run --rm \
    -v "$ROOT/vsomeip_example:/app:ro" \
    -v "$ROOT/docker/cpp_client_test_multi.sh:/tests/cpp_client_test_multi.sh:ro" \
    -v "$ROOT/docker/min_cli_multi.cpp:/tests/min_cli_multi.cpp:ro" \
    -w /app \
    "$IMAGE" bash /tests/cpp_client_test_multi.sh

echo
echo "============================================================"
echo " 全部测试完成 ✔"
echo "============================================================"
