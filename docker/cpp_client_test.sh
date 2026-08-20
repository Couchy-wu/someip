#!/usr/bin/env bash
# C++ 客户端兼容性验证：最小 C++ 客户端(min_cli) 连接 Python 服务端，断言收到 availability=true
# 在容器内运行：/app=示例代码, /tests/min_cli.cpp=C++ 客户端源码
set -euo pipefail

echo "=== 编译最小 C++ 客户端 ==="
g++ -std=c++14 -I/usr/local/include /tests/min_cli.cpp \
    -L/usr/local/lib -lvsomeip3 -o /tmp/min_cli || { echo "编译失败"; exit 1; }

rm -rf /tmp/cpptest && mkdir -p /tmp/cpptest && cp -r /app/* /tmp/cpptest/
cd /tmp/cpptest
rm -f /tmp/vsomeip-* vsomeip.json

echo "=== 启动 Python 服务端 ==="
ARHUD_SD=false ARHUD_SEND_COUNT=30 ARHUD_INTERVAL=0.3 python3 server.py > server.log 2>&1 &
SPID=$!
sleep 3

cat > vsomeip.json <<'JSON'
{"unicast":"127.0.0.1","logging":{"level":"info","console":"true"},
 "applications":[{"name":"min_cli","id":"0x2000"}],
 "routing":"arhud_server","service-discovery":{"enable":"false"}}
JSON

echo "=== 运行 C++ 客户端 (10s) ==="
timeout -k 3 10 /tmp/min_cli > cli.log 2>&1 || true
kill -9 "$SPID" 2>/dev/null || true
sleep 0.5

echo "--- cli.log ---"
grep -m 10 -aE "AVAILABILITY|registered|error|Error" cli.log || true

if grep -q "AVAILABILITY: c.c = true" cli.log; then
    echo
    echo "PASS: C++ 客户端收到服务可用性(availability=true)，与服务端兼容 ✔"
    exit 0
else
    echo
    echo "FAIL: C++ 客户端未收到 availability=true ✘"
    exit 1
fi
