#!/usr/bin/env bash
# 跨平台校验：windows/ 目录的修复代码在容器(Linux)中跑通
# 目的：windows_problem.txt 的修复（routing=arhud_server 等）与平台无关，
#       先在此验证修复有效，再上真机 Windows。同时校验 get_local_ip / udp 通路工具。
set -euo pipefail

echo "=== 跨平台校验: windows/ 代码 ==="

echo "--- 1) get_local_ip / udp_loopback_check / diagnose ---"
cd /win
python3 get_local_ip.py
python3 udp_loopback_check.py 127.0.0.1 > /dev/null && echo "udp_loopback_check OK"

rm -rf /tmp/wincheck && mkdir -p /tmp/wincheck && cp -r /win/* /tmp/wincheck/
cd /tmp/wincheck
rm -f /tmp/vsomeip-* vsomeip.json

echo "--- 2) 服务端(3 服务) + 客户端(收齐 3 服务) ---"
ARHUD_SD=true ARHUD_SEND_COUNT=40 ARHUD_INTERVAL=0.2 \
    python3 vsomeip_server_windows.py > server.log 2>&1 &
SPID=$!
sleep 4

set +e
ARHUD_SD=true ARHUD_EXIT_ALL=1 timeout -k 3 25 \
    python3 vsomeip_client_windows.py > client.log 2>&1
CLI_RC=$?
set -e
kill -9 "$SPID" 2>/dev/null || true
sleep 0.5
echo "client rc=$CLI_RC"
grep -E "\[Client\]" client.log | grep "已收齐" | tail -3

if [ "$CLI_RC" -eq 0 ] && grep -q "3 个服务均已收到事件" client.log; then
    echo
    echo "PASS: windows/ 修复代码跨平台跑通 ✔"
    exit 0
else
    echo
    echo "FAIL: windows/ 代码未跑通 ✘"
    exit 1
fi
