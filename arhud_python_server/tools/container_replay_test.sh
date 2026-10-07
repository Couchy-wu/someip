#!/usr/bin/env bash
# container_replay_test.sh —— 在容器里编译 libarhud_server.so 并用**真实 SP 协议栈**回放 pcap
# ==============================================================================
# 为什么要在容器里跑：libsomeip 只有 Linux 的 .so（arm64/x86_64），macOS 上无法链接；
# 容器里编出来的是真正部署用的那个库，链路 = 解析 → TP 重组 → 回放引擎 → SP 栈发布。
#
# 用法：
#   tools/container_replay_test.sh <pcap目录> [镜像]
#   IMAGE=arhud-vsomeip-test:latest tools/container_replay_test.sh /path/to/old
#   ARCH=x86_64 PLATFORM=linux/amd64 tools/container_replay_test.sh /path/to/old
#
# 默认用本机架构（Docker Desktop on Apple Silicon = linux/arm64 → 链接 libs/arm64，原生速度）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PCAP_DIR="${1:?用法: container_replay_test.sh <pcap目录> [镜像]}"
IMAGE="${2:-${IMAGE:-arhud-vsomeip-test:latest}}"
ARCH="${ARCH:-aarch64}"
case "$ARCH" in
  aarch64|arm64) LIBDIR="arm64" ;;
  x86_64|amd64)  LIBDIR="x86_64" ;;
  *) echo "未知架构 $ARCH（用 aarch64 / x86_64）" >&2; exit 2 ;;
esac
PLATFORM="${PLATFORM:-}"
PROFILE="${PROFILE:-old-capture}"
SPEED="${SPEED:-50}"

PLATFORM_ARG=()
[ -n "$PLATFORM" ] && PLATFORM_ARG=(--platform "$PLATFORM")

echo "== 镜像=$IMAGE 架构=$ARCH(libs/$LIBDIR) pcap目录=$PCAP_DIR profile=$PROFILE 倍速=$SPEED"
docker run --rm ${PLATFORM_ARG[@]+"${PLATFORM_ARG[@]}"} \
  -v "$ROOT":/work:ro -v "$PCAP_DIR":/pcaps:ro \
  "$IMAGE" bash -lc "
set -e
rm -rf /build && mkdir -p /build && cp -r /work/src /work/python /build/
cd /build/src && make libarhud_server.so SP_LIBS=/work/libs/$LIBDIR 2>&1 | grep -E 'error|warning' || true
cp /work/libs/$LIBDIR/*.so /build/src/
echo '--- 产物 ---'; ls -l /build/src/libarhud_server.so
IP=\$(hostname -I | awk '{print \$1}')
echo '--- 容器 IP='\$IP' ---'
cd /build
export ARHUD_LIB_PATH=/build/src/libarhud_server.so
export LD_LIBRARY_PATH=/build/src
echo '=== ① dry-run 之外的真实回放：目录整体（按抓包节奏，加速 $SPEED 倍） ==='
python3 python/demo_replay.py /pcaps \$IP --once --profile $PROFILE --timing capture --speed $SPEED \
  --report-json /tmp/report.json 2>&1 | grep -E '^\[demo\]|^\[报告\]|^\[体检\]'
echo '=== ② 报告 JSON 摘要 ==='
python3 - <<'EOF'
import json
r = json.load(open('/tmp/report.json'))
print({k: r[k] for k in ('files','loops','parsed','sent','failed','unregistered','tp_dropped','tp_duplicates','packets','elapsed_s')})
assert r['parsed'] == r['sent'] + r['failed'], 'parsed != sent + failed'
print('OK: 解析 %d 条全部经过发送接口，失败 %d 条' % (r['parsed'], r['failed']))
EOF
"
