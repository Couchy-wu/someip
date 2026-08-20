#!/usr/bin/env bash
# C++ 服务端验证（20 服务版）：单应用(min_svc_multi) 提供全部 20 个服务
# 验证两个客户端都能消费：
#   a) C++ 单应用客户端 min_cli_multi（纯 C++：服务端 1 应用 + 客户端 1 应用）
#   b) Python 20 应用客户端 client_multi.py（跨语言：C++ 服务端 ↔ Python 客户端）
set -euo pipefail

echo "=== 编译 C++ 单应用服务端/客户端 ==="
g++ -std=c++14 -I/usr/local/include /tests/min_svc_multi.cpp \
    -L/usr/local/lib -lvsomeip3 -o /tmp/min_svc_multi || { echo "服务端编译失败"; exit 1; }
g++ -std=c++14 -I/usr/local/include /tests/min_cli_multi.cpp \
    -L/usr/local/lib -lvsomeip3 -o /tmp/min_cli_multi || { echo "客户端编译失败"; exit 1; }

rm -rf /tmp/cppsvc && mkdir -p /tmp/cppsvc && cp -r /app/* /tmp/cppsvc/
cd /tmp/cppsvc
rm -f /tmp/vsomeip-* vsomeip.json

# ---- 服务端配置：1 个应用提供 20 个服务 ----
cat > vsomeip.json <<'JSON'
{"unicast":"127.0.0.1","logging":{"level":"info","console":"true"},
 "applications":[{"name":"min_svc_multi","id":"0x4000"}],
 "services":[
   {"service":"0x0100","instance":"0x0001","unreliable":51402},
   {"service":"0x0101","instance":"0x0001","unreliable":51403},
   {"service":"0x0102","instance":"0x0001","unreliable":51404},
   {"service":"0x0103","instance":"0x0001","unreliable":51405},
   {"service":"0x0104","instance":"0x0001","unreliable":51406},
   {"service":"0x0105","instance":"0x0001","unreliable":51407},
   {"service":"0x0106","instance":"0x0001","unreliable":51408},
   {"service":"0x0107","instance":"0x0001","unreliable":51409},
   {"service":"0x0108","instance":"0x0001","unreliable":51410},
   {"service":"0x0109","instance":"0x0001","unreliable":51411},
   {"service":"0x010A","instance":"0x0001","unreliable":51412},
   {"service":"0x010B","instance":"0x0001","unreliable":51413},
   {"service":"0x010C","instance":"0x0001","unreliable":51414},
   {"service":"0x010D","instance":"0x0001","unreliable":51415},
   {"service":"0x010E","instance":"0x0001","unreliable":51416},
   {"service":"0x010F","instance":"0x0001","unreliable":51417},
   {"service":"0x0110","instance":"0x0001","unreliable":51418},
   {"service":"0x0111","instance":"0x0001","unreliable":51419},
   {"service":"0x0112","instance":"0x0001","unreliable":51420},
   {"service":"0x0113","instance":"0x0001","unreliable":51421}
 ],
 "routing":"min_svc_multi","service-discovery":{"enable":"true"}}
JSON

FAIL=0

# ---- a) C++ 单应用客户端 min_cli_multi ----
echo "=== a) C++ 单应用服务端 ↔ C++ 单应用客户端 ==="
/tmp/min_svc_multi > svc.log 2>&1 &
SPID=$!
sleep 4

cat > cli_vsomeip.json <<'JSON'
{"unicast":"127.0.0.1","logging":{"level":"info","console":"true"},
 "applications":[{"name":"min_cli_multi","id":"0x3000"}],
 "routing":"min_svc_multi","service-discovery":{"enable":"true"}}
JSON
cp cli_vsomeip.json vsomeip.json
set +e
timeout -k 3 45 /tmp/min_cli_multi > cli.log 2>&1
CLI_RC=$?
set -e
echo "C++ 客户端 rc=$CLI_RC"
rm -f /tmp/min_cli_done.marker
grep -aE "DONE|TIMEOUT|已收齐 20/20" cli.log | tail -3
if grep -aq "已收齐 20/20" cli.log || [ -f /tmp/min_cli_done.marker ]; then
    echo "  [OK] C++ 单应用客户端收齐 20/20"
else
    echo "  [FAIL] C++ 单应用客户端未收齐"; FAIL=1
fi
kill -9 "$SPID" 2>/dev/null || true
sleep 1

# ---- b) Python 20 应用客户端 client_multi.py ----
echo "=== b) C++ 单应用服务端 ↔ Python 20 应用客户端 ==="
rm -f /tmp/vsomeip-* vsomeip.json
/tmp/min_svc_multi > svc.log 2>&1 &
SPID=$!
sleep 4
# 后台运行 + 轮询日志证据（客户端在高负载下可能延迟退出，以"已收齐 20/20"为准）
ARHUD_SD=true ARHUD_SERVICES=20 ARHUD_ROUTING_HOST=min_svc_multi \
    ARHUD_EXIT_ALL=1 timeout -k 3 60 python3 client_multi.py > py_cli.log 2>&1 &
CPID=$!
OK=0
for i in $(seq 1 60); do
    grep -aq "已收齐 20/20" py_cli.log 2>/dev/null && { OK=1; break; }
    sleep 1
done
kill -9 "$SPID" "$CPID" 2>/dev/null || true
wait "$CPID" 2>/dev/null || true
sleep 0.5
echo "Python 客户端 已收齐证据: $([ "$OK" -eq 1 ] && echo YES || echo NO)"
grep -a "已收齐 20/20" py_cli.log | tail -3
if [ "$OK" -eq 1 ]; then
    echo "  [OK] Python 20 应用客户端收齐 20/20（跨语言消费单应用 C++ 服务端）"
else
    echo "  [FAIL] Python 客户端未收齐"; FAIL=1
fi

if [ "$FAIL" -eq 0 ]; then
    echo
    echo "PASS: 服务端单应用提供 20 个服务可行 ✔（C++ 与 Python 客户端均可消费）"
    exit 0
else
    echo
    echo "FAIL ✘"
    exit 1
fi
