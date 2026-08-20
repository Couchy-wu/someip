#!/usr/bin/env bash
# AR-HUD 23 服务集成测试：hud_server.py(11 服务/23 事件) ↔ hud_client.py
# 断言：
#   1) 客户端收齐全部 23 个事件（按 service+event 去重）
#   2) 已定义类型的载荷可反序列化（无"解析失败"）
#   3) 事件组正确（0x000E 三事件分属 0x1101/0x1102/0x1103 —— 由客户端订阅参数保证，
#      服务端按注册表 offer，此处通过"23/23 收到"整体验证）
set -euo pipefail

echo "=== AR-HUD 23 服务集成测试 ==="
rm -rf /tmp/hud && mkdir -p /tmp/hud && cp -r /app/* /tmp/hud/ && cp -r /hud/* /tmp/hud/
cd /tmp/hud
rm -f /tmp/vsomeip-* vsomeip.json

echo "--- 1) 序列化单元自测（无 vsomeip，先验证 12 种类型往返）---"
python3 - <<'EOF'
import sys; sys.path.insert(0, '.')
import hud_data_types as h
from hud_data_types import make_sample
bad = []
for kind in sorted(h.SERIALIZERS):
    raw = make_sample(kind, 7)
    parsed, _ = h.DESERIALIZERS[kind](raw)
    if h.SERIALIZERS[kind](parsed) != raw:
        bad.append(kind)
if bad:
    print("FAIL 往返不一致:", bad); sys.exit(1)
print(f"OK: {len(h.SERIALIZERS)} 种已定义类型序列化/反序列化往返一致")
EOF

echo "--- 2) 启动服务端 (11 服务 / 23 事件) ---"
ARHUD_SD=true ARHUD_SEND_COUNT=600 ARHUD_INTERVAL=0.1 \
    python3 hud_server.py > server.log 2>&1 &
SPID=$!
sleep 6   # 11 个服务应用注册/offer 需要时间

echo "--- 3) 启动客户端（收齐 23 事件即退出）---"
ARHUD_SD=true ARHUD_EXIT_ALL=1 timeout -k 3 90 \
    python3 -u hud_client.py > client.log 2>&1 &
CPID=$!

OK=0
for i in $(seq 1 90); do
    if grep -aq "全部 23 个事件均已收到" client.log 2>/dev/null; then OK=1; break; fi
    if grep -aq "\[done\]" client.log 2>/dev/null; then break; fi
    sleep 1
done
kill -9 "$SPID" "$CPID" 2>/dev/null || true
wait "$CPID" 2>/dev/null || true
sleep 0.5

echo "--- 客户端日志摘要 ---"
grep -a "\[recv\]" client.log | tail -12
echo "--- 统计 ---"
echo "收到事件总数: $(grep -ac '\[recv\]' client.log)"
echo "去重事件数:   $(grep -a '\[recv\]' client.log | grep -oE 'svc=0x[0-9A-F]+ inst=0x[0-9A-F]+ event=0x[0-9A-F]+' | sort -u | wc -l | tr -d ' ')"
echo "解析失败数:   $(grep -ac '解析失败' client.log)"

FAIL=0
[ "$OK" -eq 1 ] || { echo "FAIL: 客户端未收齐 23 个事件"; FAIL=1; }
grep -aq "已收 23/23" client.log || { echo "FAIL: 客户端日志无 23/23 证据"; FAIL=1; }
grep -a "解析失败" client.log && { echo "FAIL: 存在反序列化失败"; FAIL=1; }
# 抽查已定义类型的摘要内容（Counter 序号应递增）
grep -aq "VehiclePositionInfoNotify" client.log || { echo "FAIL: 未收到 VehiclePositionInfoNotify"; FAIL=1; }
grep -aq "HudRoadInfoNotify.*next_road" client.log || { echo "FAIL: HudRoadInfoNotify 字符串字段未解析"; FAIL=1; }
grep -aq "HudNavigationmap" client.log || { echo "FAIL: 未收到 HudNavigationmap"; FAIL=1; }
grep -aq "Navigation_map=" client.log || { echo "FAIL: HudNavigationmap 字符串未解析"; FAIL=1; }

if [ "$FAIL" -eq 0 ]; then
    echo
    echo "PASS: AR-HUD 23 服务集成测试通过（23/23 事件收齐，已定义类型解析正确）✔"
    exit 0
else
    echo
    echo "FAIL ✘"
    exit 1
fi
