#!/usr/bin/env bash
# to_longjie 固定配置客户端 ⇄ Python 服务端 双机测试（客户端配置完全不改）
# ==========================================================================
# 场景（客户端 someip_arhud01.json 已烧录在板子上，无法修改）：
#   B 容器 = 板子：RM 宿主（C++ 服务端 hud_pcap_huifang_server + 空 services 配置
#           + 静默 pcap）+ 原版客户端（routing=arhud01，经 UDS 连本地 RM）
#   A 容器 = PC：Python 服务端（vsomeip_py）
# 原理：客户端订阅 → 本地 RM(UDS) → SD 多播 → Python 服务端 → 事件回传 RM → 客户端
#
# 关键点（实测）：
#   1. RM 宿主必须用 SP 分支进程（C++ 服务端二进制即可）：标准 3.4.10 的 UDS 协议
#      与 SP 分支不兼容，客户端注册会超时
#   2. RM 宿主配置 services 必须为空（否则本地 offer 遮蔽远程 Python 服务端）
#   3. RM 宿主 pcap 必须只含 SD 包（解析器跳过、不发送；时间戳提供喘息，避免空循环）
#   4. 启动顺序：Python 服务端 → RM 宿主 → 等 8s → 客户端（客户端注册握手机敏）
#   5. 结果：16/17 个 pcap 事件 + 生成事件全部收到；0x000E:8001(组0x0000) 无法远程投递
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NET="ljfix-$$"
A="ljfix-srv-$$"; B="ljfix-brd-$$"
CLIENT_CFG="$ROOT/to_longjie_demo_20250625/build/someip_arhud01.json"
PCAP="$ROOT/to_longjie_demo_20250625/build/out.pcap"
RM_HOST_BIN="$ROOT/to_longjie_demo_20250625/build/hud_pcap_huifang_server"
RM_HOST_CFG="$ROOT/longjie_py/someip_arhud01_rm_host.json"
RM_HOST_PCAP="$ROOT/longjie_py/rm_host_silent.pcap"
IMAGE="${IMAGE:-arhud-vsomeip-test}"
FILL="${FILL:-1}"
DURATION="${DURATION:-70}"

[ -x "$RM_HOST_BIN" ] || { echo "缺少 RM 宿主二进制: $RM_HOST_BIN"; exit 1; }
[ -f "$CLIENT_CFG" ] || { echo "缺少客户端配置: $CLIENT_CFG"; exit 1; }
[ -f "$RM_HOST_CFG" ] || { echo "缺少 RM 宿主配置: $RM_HOST_CFG"; exit 1; }
[ -f "$RM_HOST_PCAP" ] || { echo "缺少静默 pcap: $RM_HOST_PCAP"; exit 1; }
[ -f "$PCAP" ] || { echo "缺少 pcap: $PCAP"; exit 1; }

cleanup() {
    docker rm -f "$A" "$B" >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== 固定配置客户端 ⇄ Python 服务端 测试（客户端配置不改） ==="
docker network create --driver bridge "$NET" >/dev/null

docker run --rm -d --name "$A" --network "$NET" \
    -v "$ROOT/longjie_py:/lj:ro" -v "$ROOT/hud:/hud:ro" \
    -v "$ROOT/to_longjie_demo_20250625/build:/cb:ro" \
    "$IMAGE" sleep 900 >/dev/null
docker run --rm -d --name "$B" --network "$NET" \
    -v "$ROOT/to_longjie_demo_20250625/build:/cb:ro" \
    -v "$ROOT/to_longjie_demo_20250625/libs/lib_bst_t517:/clibs:ro" \
    -v "$ROOT/longjie_py:/ljcfg:ro" \
    "$IMAGE" sleep 900 >/dev/null

AIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$A")
BIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$B")
echo "A(Python服务端)=$AIP  B(板子: RM宿主+固定客户端)=$BIP"

echo "--- A: Python 服务端 ---"
docker exec "$A" bash -c "rm -rf /tmp/r && mkdir -p /tmp/r && cp -r /lj/* /hud/hud_data_types.py /tmp/r/ && cp /cb/out.pcap /tmp/r/out.pcap"
docker exec -d "$A" bash -c "cd /tmp/r && rm -f /tmp/arhud01* /tmp/*.lck /tmp/vsomeip-* && ARHUD_UNICAST=$AIP ARHUD_FILL_MISSING=$FILL python3 -u hud_server_longjie.py > server.log 2>&1"
sleep 10
docker exec "$A" bash -c "grep -aE '\[Server\]' /tmp/r/server.log | head -1"

echo "--- B: RM 宿主（C++ 服务端二进制 + 空 services + 静默 pcap） ---"
docker exec "$B" bash -c "mkdir -p /lj/rm"
docker exec "$B" bash -c "cp /cb/hud_pcap_huifang_server /lj/rm/ && chmod +x /lj/rm/hud_pcap_huifang_server"
docker exec "$B" bash -c "python3 - <<PYEOF
import json
cfg = json.load(open('/ljcfg/someip_arhud01_rm_host.json'))
cfg['unicast'] = '$BIP'
json.dump(cfg, open('/lj/rm/someip_arhud01_pcap_server.json','w'), indent=2)
print('rm host cfg: services=', len(cfg['services']))
PYEOF"
docker exec "$B" bash -c "cp /ljcfg/rm_host_silent.pcap /lj/rm/out.pcap"
docker exec -d "$B" bash -c "cd /lj/rm && rm -f /tmp/arhud01* /tmp/*.lck && LD_LIBRARY_PATH=/clibs ./hud_pcap_huifang_server > rm.log 2>&1"
sleep 8

echo "--- B: 原版客户端（配置只改 unicast，routing=arhud01 不变） ---"
docker exec "$B" bash -c "cp /cb/hud_huifang_client /lj/ && chmod +x /lj/hud_huifang_client"
docker exec "$B" bash -c "python3 - <<PYEOF
import json
cfg = json.load(open('/cb/someip_arhud01.json'))
cfg['unicast'] = '$BIP'
json.dump(cfg, open('/lj/someip_arhud01.json','w'), indent=2)
print('client: routing=%s network=%s (未修改)' % (cfg['routing'], cfg['network']))
PYEOF"
docker exec -d "$B" bash -c "cd /lj && LD_LIBRARY_PATH=/clibs ./hud_huifang_client > client.log 2>&1"

OK=0
for i in $(seq 1 $((DURATION + 10))); do
    N=$(docker exec "$B" bash -c 'grep -ac "收<--" /lj/client.log 2>/dev/null' 2>/dev/null | tr -d '[:space:]' || echo 0)
    if [ "${N:-0}" -ge 50 ] 2>/dev/null; then OK=1; break; fi
    sleep 1
done

echo "--- B 客户端统计（SIGINT 汇总表） ---"
docker exec "$B" bash -c "pkill -INT -f 'hud_huifang_[c]lient' 2>/dev/null; sleep 2; grep -a 'Total_count' /lj/client.log | tail -1"
docker exec "$B" bash -c "grep -a -A25 'Total_count' /lj/client.log | tail -25 | grep -E '\(0x'"
echo "--- A 服务端订阅 ---"
docker exec "$A" bash -c "grep -ac 'REMOTE SUBSCRIBE' /tmp/r/server.log | xargs echo 'REMOTE SUBSCRIBE 数:'"
echo "--- B RM 宿主发送数(应为0, 静默 pcap) ---"
docker exec "$B" bash -c "grep -ac '发-->' /lj/rm/rm.log | xargs echo 'RM宿主发送数:'"

TOTAL=$(docker exec "$B" bash -c "grep -a 'Total_count' /lj/client.log | grep -oE '[0-9]+' | tail -1" 2>/dev/null || echo 0)
echo "客户端 收<-- 行数: $(docker exec "$B" bash -c 'grep -ac "收<--" /lj/client.log' 2>/dev/null || echo 0)"
echo "=== 客户端总接收: $TOTAL ==="
[ "$OK" = "1" ] && echo "PASS: 固定配置客户端收到事件数据" || { echo "FAIL: 客户端未收到数据"; exit 1; }
