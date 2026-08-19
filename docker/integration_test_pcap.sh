#!/usr/bin/env bash
# pcap 全链路测试：构造 pcap → Ubuntu 程序(server.py/client.py) → Windows 程序(vsomeip_*_windows.py)
# 内容断言：客户端收到的载荷 timestamp 与 pcap 内序列化数据一致（0x1000..0x1005 / 0x1000..0x1002）
set -euo pipefail

echo "=== pcap 全链路测试 (Ubuntu + Windows 程序) ==="
cd /app

# ---- 1) 构造测试 pcap（含噪声，验证解码过滤）----
python3 make_test_pcap.py /tmp/arhud_ub.pcap \
    --service 0x000C --event 0x8003 --count 6 --noise > /tmp/gen_ub.log 2>&1
python3 make_test_pcap.py /tmp/arhud_win.pcap \
    --services 0x000A,0x000B,0x000C --event 0x8001 --count 3 --noise > /tmp/gen_win.log 2>&1
echo "--- Ubuntu pcap 内容 ---"; cat /tmp/gen_ub.log
echo "--- Windows pcap 内容 ---"; cat /tmp/gen_win.log

FAIL=0

# ---- 2) Ubuntu 程序：server.py(读 pcap 回放) + client.py ----
echo
echo "=== Ubuntu 程序 ==="
rm -rf /tmp/ub && mkdir -p /tmp/ub && cp -r /app/* /tmp/ub/ && cd /tmp/ub
rm -f /tmp/vsomeip-* vsomeip.json
ARHUD_SD=true ARHUD_SEND_COUNT=200 ARHUD_INTERVAL=0.2 \
    python3 server.py /tmp/arhud_ub.pcap > server.log 2>&1 &
SPID=$!
sleep 3
set +e
ARHUD_SD=true ARHUD_EXIT_AFTER=6 timeout -k 3 45 \
    python3 client.py > client.log 2>&1
RC=$?
set -e
kill -9 "$SPID" 2>/dev/null || true
sleep 0.5
echo "ubuntu client rc=$RC"
grep -E "解码出|收到事件|timestamp=" server.log client.log | head -14

grep -q "解码出 6 条事件" server.log || { echo "FAIL: 服务端未从 pcap 解码出 6 条(噪声应被过滤)"; FAIL=1; }
[ "$RC" -eq 0 ] || { echo "FAIL: Ubuntu 客户端未收齐 (rc=$RC)"; FAIL=1; }
for t in 1000 1001 1002 1003 1004 1005; do
    grep -q "timestamp=0x0000$t" client.log || { echo "FAIL: 客户端缺少 timestamp=0x0000$t"; FAIL=1; }
done
grep -q "反序列化失败" client.log && { echo "FAIL: Ubuntu 客户端反序列化失败"; FAIL=1; }

# ---- 3) Windows 程序：vsomeip_server_windows.py(读 pcap 回放) + client ----
echo
echo "=== Windows 程序 ==="
rm -rf /tmp/winp && mkdir -p /tmp/winp && cp -r /win/* /tmp/winp/
cp /app/arhud_data_types.py /app/pcap_decoder.py /tmp/winp/  # pcap 解码依赖
cd /tmp/winp
rm -f /tmp/vsomeip-* vsomeip.json
ARHUD_SD=true ARHUD_PCAP=/tmp/arhud_win.pcap ARHUD_SEND_COUNT=120 ARHUD_INTERVAL=0.2 \
    python3 vsomeip_server_windows.py > server.log 2>&1 &
SPID=$!
sleep 4
set +e
ARHUD_SD=true ARHUD_EXIT_ALL=1 timeout -k 3 45 \
    python3 vsomeip_client_windows.py > client.log 2>&1
WRC=$?
set -e
kill -9 "$SPID" 2>/dev/null || true
sleep 0.5
echo "windows client rc=$WRC"
grep -E "\[pcap\]|\[Client\] 收到|解析: version" server.log client.log | head -14

grep -q "3 个服务均已收到事件" client.log || { echo "FAIL: Windows 客户端未收齐 3 服务"; FAIL=1; }
grep -q "解析: version=1 timestamp=0x0000100" client.log \
    || { echo "FAIL: Windows 客户端未解析出 pcap 内容(timestamp 0x1000..)"; FAIL=1; }

if [ "$FAIL" -eq 0 ]; then
    echo
    echo "PASS: pcap 全链路测试通过（Ubuntu + Windows 程序均从同一 pcap 回放并收到一致内容）✔"
    exit 0
else
    echo
    echo "FAIL: pcap 全链路测试未通过 ✘"
    exit 1
fi
