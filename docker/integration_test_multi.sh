#!/usr/bin/env bash
# 集成测试：20 服务版（server_multi.py + client_multi.py）
# 断言：客户端收齐全部 20 个服务的事件且无反序列化失败
set -euo pipefail

echo "=== 集成测试: 20 服务 两进程收发 ==="

rm -rf /tmp/multi && mkdir -p /tmp/multi && cp -r /app/* /tmp/multi/
cd /tmp/multi
rm -f /tmp/vsomeip-* vsomeip.json

echo "--- 启动 20 服务服务端 ---"
ARHUD_SD=true ARHUD_SERVICES=20 ARHUD_SEND_COUNT=500 ARHUD_INTERVAL=0.2 \
    python3 server_multi.py > server.log 2>&1 &
SPID=$!
sleep 8   # 20 个服务应用启动/注册/offer 需要更长时间（CI 慢速环境留足余量）

echo "--- 启动客户端（后台 + 轮询收齐证据，规避 GIL 高负载下退出延迟）---"
ARHUD_SD=true ARHUD_SERVICES=20 ARHUD_EXIT_ALL=1 timeout -k 3 90 \
    python3 -u client_multi.py > client.log 2>&1 &
CPID=$!
OK=0
for i in $(seq 1 90); do
    grep -aq "已收齐 20/20" client.log 2>/dev/null && { OK=1; break; }
    grep -aq "\[done\]" client.log 2>/dev/null && break
    sleep 1
done
kill -9 "$SPID" "$CPID" 2>/dev/null || true
wait "$CPID" 2>/dev/null || true
echo "客户端已收齐 20 服务证据: $([ "$OK" -eq 1 ] && echo YES || echo NO)"
sleep 0.5

echo
echo "==================== 客户端日志(摘要) ===================="
grep -m 30 -aE "\[recv\]|\[done\]|反序列化失败" client.log || true
echo
echo "==================== 服务端日志(摘要) ===================="
grep -m 8 -aE "就绪|\[send\]|error|Error" server.log || true

# ---- 断言 ----
FAIL=0
[ "$OK" -eq 1 ] && grep -aq "已收齐 20/20" client.log \
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
