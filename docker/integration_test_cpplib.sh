#!/usr/bin/env bash
# C++ 服务端库（libarhud_server.so）⇄ Python 调用 ⇄ 真实客户端 集成测试
# =========================================================================
# A 容器 = 本机：编译 C++ 库 → Python(ctypes) 调用：
#   demo_struct.py（结构化赋值发送）+ demo_replay.py（指定 pcap 回放）
# B 容器 = 板子：RM 宿主（C++ 服务端二进制模拟中间件）+ 原版客户端（固定配置）
# 验证：客户端收到 ①结构化数据 ②pcap 回放数据 ③51KB TP 大消息
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NET="ljcpp-$$"
A="ljcpp-a-$$"; B="ljcpp-b-$$"
PCAP="$ROOT/to_longjie_demo_20250625/build/out.pcap"
IMAGE="${IMAGE:-arhud-vsomeip-test}"
DURATION="${DURATION:-50}"

[ -f "$PCAP" ] || { echo "缺少 pcap: $PCAP"; exit 1; }

cleanup() {
    docker rm -f "$A" "$B" >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== C++ 库服务端 ⇄ Python 调用 ⇄ 真实客户端 测试 ==="
docker network create --driver bridge "$NET" >/dev/null

docker run --rm -d --name "$A" --network "$NET" \
    -v "$ROOT/hud_cpp_lib:/ljlib:ro" -v "$ROOT/to_longjie_demo_20250625/build:/cb:ro" \
    "$IMAGE" sleep 900 >/dev/null
docker run --rm -d --name "$B" --network "$NET" \
    -v "$ROOT/to_longjie_demo_20250625/build:/cb:ro" \
    -v "$ROOT/to_longjie_demo_20250625/libs/lib_bst_t517:/clibs:ro" \
    -v "$ROOT/longjie_py:/ljcfg:ro" \
    "$IMAGE" sleep 900 >/dev/null

AIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$A")
BIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$B")
echo "A(C++库服务端)=$AIP  B(板子)=$BIP"

echo "--- A: 编译 C++ 库 ---"
docker exec "$A" bash -c "rm -rf /tmp/build && mkdir -p /tmp/build && cp /ljlib/* /tmp/build/ && cd /tmp/build && make > mk.log 2>&1"
docker exec "$A" bash -c "test -f /tmp/build/libarhud_server.so" || { echo "FAIL: 编译失败"; docker exec "$A" bash -c 'tail -5 /tmp/build/mk.log'; exit 1; }

echo "--- B: RM 宿主（模拟板子中间件）+ 原版客户端 ---"
docker exec "$B" bash -c "mkdir -p /lj/rm && cp /cb/hud_pcap_huifang_server /lj/rm/ && chmod +x /lj/rm/hud_pcap_huifang_server"
docker exec "$B" bash -c "python3 - <<PYEOF
import json
cfg = json.load(open('/ljcfg/someip_arhud01_rm_host.json'))
cfg['unicast'] = '$BIP'
json.dump(cfg, open('/lj/rm/someip_arhud01_pcap_server.json','w'), indent=2)
PYEOF"
docker exec "$B" bash -c "cp /ljcfg/rm_host_silent.pcap /lj/rm/out.pcap"
docker exec -d "$B" bash -c "cd /lj/rm && rm -f /tmp/arhud01* /tmp/*.lck && LD_LIBRARY_PATH=/clibs ./hud_pcap_huifang_server > rm.log 2>&1"
sleep 8
docker exec "$B" bash -c "cp /cb/hud_huifang_client /lj/ && chmod +x /lj/hud_huifang_client"
docker exec "$B" bash -c "python3 - <<PYEOF
import json
cfg = json.load(open('/cb/someip_arhud01.json'))
cfg['unicast'] = '$BIP'
json.dump(cfg, open('/lj/someip_arhud01.json','w'), indent=2)
PYEOF"
docker exec -d "$B" bash -c "cd /lj && LD_LIBRARY_PATH=/clibs ./hud_huifang_client > client.log 2>&1"
echo "等待客户端订阅稳定（15 秒，51KB TP 大消息需要订阅就绪）..."
sleep 15

echo "--- A: ①结构化赋值发送（demo_struct.py，8 秒） ---"
docker exec -d "$A" bash -c "cd /tmp/build && timeout 8 python3 -u demo_struct.py $AIP > struct.log 2>&1"
sleep 12

echo "--- A: ②指定 pcap 回放（demo_replay.py，$DURATION 秒） ---"
docker exec -d "$A" bash -c "cd /tmp/build && python3 -u demo_replay.py /cb/out.pcap $AIP > replay.log 2>&1"

OK=0
for i in $(seq 1 $((DURATION + 10))); do
    # 等待 51KB TP 大消息（0x000C:8003）到达客户端 —— 证明 pcap 回放 + TP 分片全链路通
    BIG_N=$(docker exec "$B" bash -c 'grep -a "收<--" /lj/client.log | grep -ac "000C.*8003"' 2>/dev/null | tr -d '[:space:]' || echo 0)
    if [ "${BIG_N:-0}" -ge 5 ] 2>/dev/null; then OK=1; break; fi
    sleep 1
done

echo "--- 统计 ---"
echo "A 回放进度: $(docker exec "$A" bash -c 'grep -a "已回放" /tmp/build/replay.log | tail -1' 2>/dev/null)"
echo "A TP 丢弃数(应为0): $(docker exec "$A" bash -c 'grep -ac "Dropping to big message" /tmp/build/replay.log' 2>/dev/null || echo 0)"
TOTAL=$(docker exec "$B" bash -c 'grep -ac "收<--" /lj/client.log' 2>/dev/null || echo 0)
BIG=$(docker exec "$B" bash -c 'grep -a "收<--" /lj/client.log | grep -ac "000C.*8003"' 2>/dev/null || echo 0)
echo "客户端总接收: $TOTAL  51KB 大消息(0x000C:8003): $BIG"

echo "--- B 客户端汇总（SIGINT） ---"
docker exec "$B" bash -c "pkill -INT -f 'hud_huifang_[c]lient' 2>/dev/null; sleep 2; grep -a -A25 'Total_count' /lj/client.log | tail -26 | grep -E 'Total_count|\(0x'" 2>/dev/null | head -12

[ "$OK" = "1" ] && [ "${BIG:-0}" -ge 5 ] && echo "PASS: 客户端收到结构化数据 + pcap 回放 + TP 大消息" \
    || { echo "FAIL: 客户端未收到足够数据"; exit 1; }
