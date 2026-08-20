#!/usr/bin/env bash
# C++ 客户端验证（20 服务版）：单应用(min_cli_multi) 订阅全部 20 个服务并收齐事件
# 证明 vsomeip 一个应用可订阅任意多个服务
set -euo pipefail

echo "=== 编译单应用 C++ 客户端 (min_cli_multi) ==="
g++ -std=c++14 -I/usr/local/include /tests/min_cli_multi.cpp \
    -L/usr/local/lib -lvsomeip3 -o /tmp/min_cli_multi || { echo "编译失败"; exit 1; }

rm -rf /tmp/cppmulti && mkdir -p /tmp/cppmulti && cp -r /app/* /tmp/cppmulti/
cd /tmp/cppmulti
rm -f /tmp/vsomeip-* vsomeip.json

echo "=== 启动 Python 20 服务服务端 ==="
ARHUD_SD=true ARHUD_SERVICES=20 ARHUD_SEND_COUNT=300 ARHUD_INTERVAL=0.2 \
    python3 server_multi.py > server.log 2>&1 &
SPID=$!
sleep 8

cat > vsomeip.json <<'JSON'
{"unicast":"127.0.0.1","logging":{"level":"info","console":"true"},
 "applications":[{"name":"min_cli_multi","id":"0x3000"}],
 "routing":"arhud_svc_0","service-discovery":{"enable":"true"}}
JSON

echo "=== 运行单应用 C++ 客户端 (30s) ==="
set +e
timeout -k 3 45 /tmp/min_cli_multi > cli.log 2>&1
CLI_RC=$?
set -e
kill -9 "$SPID" 2>/dev/null || true
sleep 0.5

echo "--- cli.log 摘要 ---"
grep -E "RECV|DONE|TIMEOUT|started" cli.log | tail -25

rm -f /tmp/min_cli_done.marker
if [ "$CLI_RC" -eq 0 ] && { grep -aq "已收齐 20/20" cli.log || [ -f /tmp/min_cli_done.marker ]; }; then
    echo
    echo "PASS: 单应用 C++ 客户端收齐全部 20 个服务的事件 ✔"
    exit 0
else
    echo
    echo "FAIL: 单应用客户端未收齐 20 个服务 ✘ (rc=$CLI_RC)"
    exit 1
fi
