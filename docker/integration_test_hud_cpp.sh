#!/usr/bin/env bash
# AR-HUD C++ 客户端集成测试：Python 服务端(hud_server.py) ↔ C++ 客户端(hud_client.cpp)
# 断言：客户端收齐 23/23 事件，已定义类型解析正确，无反序列化失败
set -euo pipefail

echo "=== AR-HUD C++ 客户端集成测试 (Python 服务端 ↔ C++ vsomeip 客户端) ==="

echo "--- 1) 编译 C++ 客户端 ---"
g++ -std=c++14 -O2 -I/usr/local/include /hudcpp/hud_client.cpp \
    /hudcpp/hud_data_types.cpp -L/usr/local/lib -lvsomeip3 -o /tmp/hud_client \
    || { echo "编译失败"; exit 1; }
echo "编译 OK"

rm -rf /tmp/hudcpp_run && mkdir -p /tmp/hudcpp_run && cp -r /hud/* /tmp/hudcpp_run/
cp /hudcpp/vsomeip_client.json /tmp/hudcpp_run/vsomeip.json
cd /tmp/hudcpp_run
rm -f /tmp/vsomeip-* /tmp/hud_cpp_done.marker

echo "--- 2) 启动 Python 服务端 ---"
ARHUD_SD=true ARHUD_INTERVAL=0.1 python3 -u hud_server.py > server.log 2>&1 &
SPID=$!
sleep 6

echo "--- 3) 启动 C++ 客户端（后台 + 轮询收齐证据）---"
timeout -k 3 90 /tmp/hud_client > client.log 2>&1 &
CPID=$!
OK=0
for i in $(seq 1 90); do
    [ -f /tmp/hud_cpp_done.marker ] && { OK=1; break; }
    grep -aq "已收 23/23" client.log 2>/dev/null && { OK=1; break; }
    grep -aq "\[done\]" client.log 2>/dev/null && break
    sleep 1
done
kill -9 "$SPID" "$CPID" 2>/dev/null || true
wait "$CPID" 2>/dev/null || true
echo "收齐证据: $([ "$OK" -eq 1 ] && echo YES || echo NO)"

echo "--- C++ 客户端日志（摘要）---"
grep -am 12 -aE "\[recv\]|\[done\]|自测" client.log || true

echo "--- 统计 ---"
echo "接收总数: $(grep -ac '\[recv\]' client.log)"
echo "去重事件数: $(grep -a '\[recv\]' client.log | grep -oE 'svc=0x[0-9A-F]+ inst=0x[0-9A-F]+ event=0x[0-9A-F]+' | sort -u | wc -l | tr -d ' ')"
echo "解析失败数: $(grep -ac '解析失败' client.log)"

FAIL=0
[ "$OK" -eq 1 ] || { echo "FAIL: C++ 客户端未收齐 23 个事件"; FAIL=1; }
grep -aq "已收 23/23" client.log || { echo "FAIL: 客户端日志无 23/23 证据"; FAIL=1; }
grep -a "解析失败" client.log && { echo "FAIL: 存在反序列化失败"; FAIL=1; }
grep -aq "VehiclePositionInfoNotify.*Counter=[0-9]" client.log \
    || { echo "FAIL: VehiclePosition 未解析"; FAIL=1; }
grep -aq "HudRoadInfoNotify.*next_road='G6 Expressway'" client.log \
    || { echo "FAIL: HudRoad 字符串未解析"; FAIL=1; }
grep -aq "大端编解码自测通过" client.log || { echo "FAIL: 编解码自测未通过"; FAIL=1; }

if [ "$FAIL" -eq 0 ]; then
    echo
    echo "PASS: C++ vsomeip 客户端收齐 23/23 事件，跨语言兼容 Python 服务端 ✔"
    exit 0
else
    echo
    echo "FAIL ✘"
    exit 1
fi
