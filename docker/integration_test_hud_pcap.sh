#!/usr/bin/env bash
# AR-HUD pcap 全链路测试：生成 23 事件 pcap → hud_server(回放) → hud_client(接收)
# 并把【服务端发送结果】与【客户端接收结果】完整打印
set -euo pipefail

echo "=============================================="
echo " AR-HUD pcap 全链路测试（服务端发送 / 客户端接收）"
echo "=============================================="

rm -rf /tmp/hudpcap && mkdir -p /tmp/hudpcap && cp -r /hud/* /tmp/hudpcap/
cd /tmp/hudpcap
rm -f /tmp/vsomeip-* vsomeip.json

echo "--- 1) 生成 23 事件 pcap（载荷 = hud_data_types 序列化字节）---"
python3 make_hud_pcap.py /tmp/arhud_hud.pcap --rounds 1 | sed -n "1,6p"
echo "  ..."
grep -c "svc=0x" /tmp/arhud_hud.pcap 2>/dev/null || true

echo
echo "--- 2) 启动服务端（ARHUD_PCAP 回放，持续发送，测试结束再停）---"
ARHUD_SD=true ARHUD_PCAP=/tmp/arhud_hud.pcap ARHUD_EXAMPLE_DIR=/app \
    ARHUD_SEND_COUNT=0 ARHUD_INTERVAL=0.08 \
    python3 -u hud_server.py > server.log 2>&1 &
SPID=$!
sleep 6

echo "--- 3) 启动客户端（收齐 23 事件即退出）---"
ARHUD_SD=true ARHUD_EXIT_ALL=1 timeout -k 3 90 \
    python3 -u hud_client.py > client.log 2>&1 &
CPID=$!
OK=0
for i in $(seq 1 90); do
    grep -aq "全部 23 个事件均已收到" client.log 2>/dev/null && { OK=1; break; }
    grep -aq "\\[done\\]" client.log 2>/dev/null && break
    sleep 1
done
kill -9 "$SPID" "$CPID" 2>/dev/null || true
wait "$CPID" 2>/dev/null || true
sleep 0.5

echo
echo "==================== 服务端发送结果（前 46 条） ===================="
grep -am 46 -a "\[send\]" server.log || true
echo
echo "==================== 客户端接收结果 ===================="
grep -am 30 -aE "\[recv\].*(已收 (23|2[0-2])/23|\[done\])" client.log || true

echo
echo "--- 统计 ---"
echo "服务端发送条数: $(grep -ac '\[send\]' server.log)"
echo "客户端接收总数: $(grep -ac '\[recv\]' client.log)"
echo "去重事件数:   $(grep -a '\[recv\]' client.log | grep -oE 'svc=0x[0-9A-F]+ inst=0x[0-9A-F]+ event=0x[0-9A-F]+' | sort -u | wc -l | tr -d ' ')"
echo "解析失败数:   $(grep -ac '解析失败' client.log)"

FAIL=0
[ "$OK" -eq 1 ] && grep -aq "已收 23/23" client.log \
    || { echo "FAIL: 客户端未收齐 23 个事件"; FAIL=1; }
grep -a "解析失败" client.log && { echo "FAIL: 存在反序列化失败"; FAIL=1; }
# 内容与 pcap 一致（rounds=1 时 counter 从 1 递增：VehiclePosition=1, RTK=2, IMU=3, ...）
grep -aq "VehiclePositionInfoNotify.*Counter=1" client.log \
    || { echo "FAIL: VehiclePosition 内容与 pcap 不一致(Counter=1)"; FAIL=1; }
grep -aq "LaneLineDataNotify.*lines=3" client.log \
    || { echo "FAIL: LaneLine 动态数组内容不一致(lines=3)"; FAIL=1; }
grep -aq "HudRoadInfoNotify.*next_road='G6 Expressway'" client.log \
    || { echo "FAIL: HudRoad 字符串内容不一致"; FAIL=1; }

if [ "$FAIL" -eq 0 ]; then
    echo
    echo "PASS: AR-HUD pcap 全链路测试通过（服务端回放 pcap 字节，客户端解析内容一致）✔"
    exit 0
else
    echo
    echo "FAIL ✘"
    exit 1
fi
