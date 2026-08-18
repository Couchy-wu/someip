#!/usr/bin/env bash
# 容器内集成测试：两个独立进程，走真实 vsomeip UDS 路由管理器
# 链路: server.py(offer + notify) ──▶ client.py(subscribe + 反序列化)
set -euo pipefail

echo "=== 集成测试: 真实 vsomeip 两进程收发 ==="
echo "Python: $(python3 --version)  $(which python3)"

# 独立工作目录（避免污染挂载的源码目录；同一容器内 /tmp 共享，UDS 注册正常）
rm -rf /tmp/arhud-run && mkdir -p /tmp/arhud-run
cp -r /app/* /tmp/arhud-run/ 2>/dev/null || true
cd /tmp/arhud-run
rm -f /tmp/vsomeip-* vsomeip.json

# ---- 1) 启动服务端（内置示例数据；发送 10 条，间隔 0.5s）----
# 注意: 事件组订阅要求 SD 开启（vsomeip 限制）；容器内两个进程同主机，多播回环可正常收发
echo "--- 启动服务端 ---"
ARHUD_SD=true ARHUD_SEND_COUNT=10 ARHUD_INTERVAL=0.5 python3 server.py > server.log 2>&1 &
SERVER_PID=$!
sleep 3   # 等服务端成为路由管理器宿主并完成 offer

# ---- 2) 启动客户端（收到 3 条事件即退出，30s 超时保护）----
echo "--- 启动客户端 ---"
set +e
ARHUD_SD=true ARHUD_EXIT_AFTER=3 timeout 30 python3 client.py > client.log 2>&1
CLIENT_RC=$?
set -e
echo "客户端退出码: $CLIENT_RC"

# ---- 3) 收尾 ----
kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true

echo
echo "==================== 服务端日志 (server.log) ===================="
cat server.log
echo
echo "==================== 客户端日志 (client.log) ===================="
cat client.log
echo "================================================================="

# ---- 4) 断言 ----
FAIL=0
grep -q "收到事件" client.log || { echo "FAIL: 客户端未收到任何事件"; FAIL=1; }
[ "$CLIENT_RC" -eq 0 ] || { echo "FAIL: 客户端异常退出 (rc=$CLIENT_RC)"; FAIL=1; }
grep -q "反序列化失败" client.log && { echo "FAIL: 存在反序列化失败"; FAIL=1; }

if [ "$FAIL" -eq 0 ]; then
    echo
    echo "PASS: 客户端成功通过 vsomeip 收到并解析事件 ✔"
    exit 0
else
    echo
    echo "FAIL: 集成测试未通过 ✘"
    exit 1
fi
