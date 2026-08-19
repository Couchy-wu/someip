#!/usr/bin/env bash
# 集成测试：20 服务版（server_multi.py + client_multi.py）
# 断言：客户端收齐全部 20 个服务的事件且无反序列化失败
set -euo pipefail

echo "=== 集成测试: 20 服务 两进程收发 ==="

rm -rf /tmp/multi && mkdir -p /tmp/multi && cp -r /app/* /tmp/multi/
cd /tmp/multi
rm -f /tmp/vsomeip-* vsomeip.json

echo "--- 启动 20 服务服务端 ---"
ARHUD_SD=true ARHUD_SERVICES=20 ARHUD_SEND_COUNT=80 ARHUD_INTERVAL=0.2 \
    python3 server_multi.py > server.log 2>&1 &
SPID=$!
sleep 6   # 20 个服务应用启动/注册/offer 需要更长时间

echo "--- 启动客户端（收齐 20 个服务即退出，60s 超时保护）---"
set +e
ARHUD_SD=true ARHUD_SERVICES=20 ARHUD_EXIT_ALL=1 timeout -k 3 60 \
    python3 client_multi.py > client.log 2>&1
CLIENT_RC=$?
set -e
echo "客户端退出码: $CLIENT_RC"

kill -9 "$SPID" 2>/dev/null || true
wait "$SPID" 2>/dev/null || true

echo
echo "==================== 客户端日志(摘要) ===================="
grep -E "\[recv\]|\[done\]|反序列化失败" client.log | head -30
echo
echo "==================== 服务端日志(摘要) ===================="
grep -E "就绪|\[send\]|error|Error" server.log | head -8

# ---- 断言 ----
FAIL=0
grep -q "20 个服务均已收到事件" client.log \
    || { echo "FAIL: 客户端未收齐全部 20 个服务的事件"; FAIL=1; }
grep -q "反序列化失败" client.log \
    && { echo "FAIL: 存在反序列化失败"; FAIL=1; }

if [ "$FAIL" -eq 0 ]; then
    echo
    echo "PASS: 客户端收到全部 20 个服务的事件并成功反序列化 ✔"
    exit 0
else
    echo
    echo "FAIL: 20 服务集成测试未通过 ✘"
    exit 1
fi
