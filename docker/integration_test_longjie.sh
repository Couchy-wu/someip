#!/usr/bin/env bash
# to_longjie 真实客户端 ⇄ Python 服务端 双机(双容器)集成测试
# ==============================================================
# 场景：A 容器跑 Python 服务端（vsomeip_py, 标准 vsomeip 3.4.10），
#       B 容器跑板子编译好的真实 C++ 客户端（hud_huifang_client, aarch64, SP 分支库）
# 验证：客户端经 SD 多播(224.0.2.4:30490)发现服务 → 逐事件订阅(major=1) → 收到服务端数据
#
# 关键点（均为实测结论）：
#   1. 服务端 offer 必须 major=1（客户端配置 major="1"）
#   2. 客户端 routing 必须改为自身(arhud02) → 自托管 RM 走网络模式（SP 分支与标准 3.4.10
#      的 UDS 协议不兼容，同机托管 RM 不可行；跨机必须双 RM + 网络 SD）
#   3. 客户端配置 0x000E 必须拆分（SP 包装器只读顶层 event_group，否则组=0x0000 被 NACK）
#   4. 服务端 0x000C:8002/8003 需显式 someip-tp（标准 vsomeip 超 1400B 必须 TP，SP 分支自动）
#   5. 容器必须直接建在自定义 bridge 网络上（多播可达），不能默认网桥+后接网络
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NET="ljnet-$$"
A="lj-server-$$"; B="lj-client-$$"
CLIENT_CFG="$ROOT/to_longjie_demo_20250625/build/someip_arhud01.json"
PCAP="$ROOT/to_longjie_demo_20250625/build/out.pcap"
ZIP="$ROOT/to_longjie_demo_20250625.zip"
IMAGE="${IMAGE:-arhud-vsomeip-test}"
FILL="${FILL:-1}"          # 1=缺失事件生成数据(19/23)；0=仅回放 pcap(11/23)
DURATION="${DURATION:-40}" # 客户端运行秒数

[ -f "$CLIENT_CFG" ] || { echo "缺少客户端配置: $CLIENT_CFG"; exit 1; }
[ -f "$PCAP" ] || { echo "缺少 pcap: $PCAP"; exit 1; }
[ -f "$ZIP" ] || { echo "缺少工程 zip: $ZIP"; exit 1; }

cleanup() {
    docker rm -f "$A" "$B" >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== to_longjie 真实客户端 ⇄ Python 服务端 测试 (fill=$FILL) ==="
docker network create --driver bridge "$NET" >/dev/null

# 客户端二进制按镜像架构选择：aarch64 用 build/ + lib_bst_t517；x86_64 用 x86 客户端 + 从 zip 解压 x86 库
ARCH=$(docker run --rm --entrypoint uname "$IMAGE" -m 2>/dev/null | tr -d '[:space:]')
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    CLIENT_BIN="$ROOT/to_longjie_demo_20250625/build/hud_huifang_client"
    LIBS_SRC="$ROOT/to_longjie_demo_20250625/libs/lib_bst_t517"
    [ -x "$CLIENT_BIN" ] || { echo "缺少 aarch64 客户端二进制: $CLIENT_BIN"; exit 1; }
else
    CLIENT_BIN="$ROOT/to_longjie_demo_20250625/build/hud_huifang_client_x86"
    TMPX="$(mktemp -d)"
    unzip -o -q "$ZIP" -d "$TMPX" 'to_longjie_demo_20250625/libs/lib_x86/*' 2>/dev/null || unzip -o -q "$ZIP" -d "$TMPX" '*/lib_x86/*' 2>/dev/null
    LIBS_SRC="$(find "$TMPX" -type d -name lib_x86 | head -1)"
    [ -x "$CLIENT_BIN" ] || { echo "缺少 x86 客户端二进制: $CLIENT_BIN"; exit 1; }
    [ -n "$LIBS_SRC" ] || { echo "zip 中未找到 x86 库"; exit 1; }
fi
echo "镜像架构: $ARCH  客户端: $(basename "$CLIENT_BIN")  库: $LIBS_SRC"

docker run --rm -d --name "$A" --network "$NET" \
    -v "$ROOT/longjie_py:/lj:ro" -v "$ROOT/hud:/hud:ro" \
    -v "$ROOT/to_longjie_demo_20250625/build:/cb:ro" \
    "$IMAGE" sleep 900 >/dev/null
docker run --rm -d --name "$B" --network "$NET" \
    -v "$ROOT/to_longjie_demo_20250625/build:/cb:ro" \
    -v "$LIBS_SRC:/clibs:ro" \
    "$IMAGE" sleep 900 >/dev/null

AIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$A")
BIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$B")
echo "A(服务端)=$AIP  B(客户端)=$BIP"

echo "--- A: 启动 Python 服务端 ---"
docker exec "$A" bash -c "rm -rf /tmp/r && mkdir -p /tmp/r && cp -r /lj/* /hud/hud_data_types.py /tmp/r/ && cp /cb/out.pcap /tmp/r/out.pcap"
docker exec -d "$A" bash -c "cd /tmp/r && rm -f /tmp/arhud01* /tmp/*.lck /tmp/vsomeip-* && ARHUD_UNICAST=$AIP ARHUD_FILL_MISSING=$FILL python3 -u hud_server_longjie.py > server.log 2>&1"
sleep 10
docker exec "$A" bash -c "grep -aE '\[Server\]|offer: svc=0x000A' /tmp/r/server.log | head -2"

echo "--- B: 准备客户端（$(basename "$CLIENT_BIN") + SP 库 + 修正配置） ---"
docker exec "$B" bash -c "mkdir -p /tmp/c/libs && cp /cb/$(basename "$CLIENT_BIN") /tmp/c/hud_huifang_client && cp /clibs/* /tmp/c/libs/ && chmod +x /tmp/c/hud_huifang_client"
docker exec "$B" bash -c "cd /tmp/c && python3 - <<PYEOF
import json
cfg = json.load(open('/cb/someip_arhud01.json'))
cfg['unicast'] = '$BIP'
cfg['routing'] = 'arhud02'                       # 自托管 RM（跨机必须）
new_clients = [c for c in cfg['clients'] if c['service'] != '0x000E']
names = {'0x8001':'PlanningLineInfoNotify','0x8002':'newPlanningLineInfo','0x8003':'drivingAreaIdentification'}
for ev, grp in [('0x8001','0x1101'),('0x8002','0x1102'),('0x8003','0x1103')]:
    new_clients.append({'service':'0x000E','instance':'0x000E','major':'1','minor':'0',
        'events':[{'name':names[ev],'event':ev}],'event_group':grp,'unreliable':['52006']})
cfg['clients'] = new_clients
json.dump(cfg, open('someip_arhud01.json','w'), indent=4)
print('client unicast', cfg['unicast'], 'routing', cfg['routing'], 'clients', len(cfg['clients']))
PYEOF"

echo "--- B: 启动真实客户端（$DURATION 秒） ---"
docker exec -d "$B" bash -c "cd /tmp/c && LD_LIBRARY_PATH=/tmp/c/libs ./hud_huifang_client > client.log 2>&1"

OK=0
for i in $(seq 1 $((DURATION + 10))); do
    N=$(docker exec "$B" bash -c 'grep -ac "收<--" /tmp/c/client.log 2>/dev/null' 2>/dev/null | tr -d '[:space:]' || echo 0)
    if [ "${N:-0}" -ge 30 ] 2>/dev/null; then OK=1; break; fi
    sleep 1
done

echo "--- B 客户端统计（SIGINT 汇总表） ---"
docker exec "$B" bash -c "pkill -INT -f 'hud_huifang_[c]lient'; sleep 2; tail -30 /tmp/c/client.log | grep -E 'Total_count|\(0x'"
echo "--- 服务端日志（订阅接受情况） ---"
docker exec "$A" bash -c "grep -ac 'REMOTE SUBSCRIBE' /tmp/r/server.log | xargs echo 'REMOTE SUBSCRIBE 数:'; grep -ac 'Dropping to big message' /tmp/r/server.log | xargs echo 'TP 丢弃数(应为0):'"

TOTAL=$(docker exec "$B" bash -c "grep -a 'Total_count' /tmp/c/client.log | grep -oE '[0-9]+' | head -1" 2>/dev/null || echo 0)
echo "=== 客户端总接收: ${TOTAL:-0} ==="
[ "$OK" = "1" ] && echo "PASS: 客户端收到事件数据" || { echo "FAIL: 客户端未收到数据"; exit 1; }
