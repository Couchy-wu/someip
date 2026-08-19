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

# 后台运行 + 轮询日志证据（客户端退出时包装器 C++ 清理可能 abort(134)，以收到证据为准）
ARHUD_SD=true ARHUD_EXIT_ALL=1 timeout -k 3 25 \
    python3 -u vsomeip_client_windows.py > client.log 2>&1 &
CPID=$!
OK=0
for i in $(seq 1 25); do
    grep -aq "已收齐 3/3" client.log 2>/dev/null && { OK=1; break; }
    sleep 1
done
kill -9 "$SPID" "$CPID" 2>/dev/null || true
wait "$CPID" 2>/dev/null || true
sleep 0.5
echo "client 已收齐 3 服务证据: $([ "$OK" -eq 1 ] && echo YES || echo NO)"
grep -a "已收齐" client.log | tail -3

if [ "$OK" -eq 1 ]; then
    echo
    echo "PASS: windows/ 修复代码跨平台跑通 ✔"
    exit 0
else
    echo
    echo "FAIL: windows/ 代码未跑通 ✘"
    exit 1
fi
