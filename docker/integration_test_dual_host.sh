#!/usr/bin/env bash
# 双机（双容器 / 双网络命名空间）通信测试
# ==================================================
# 验证 vsomeip 双机通信：A 容器跑服务端（自持 RM），B 容器跑客户端（本机 RM 宿主=arhud_client_0），
# 通过 SD 多播发现 + 网络 UDP 数据通道，B 机收到 A 机全部 23 个事件。
#
# 双机关键配置（与单机的区别）：
#   1. unicast = 本机真实 IP（get_local_ip 自动探测，含默认网关/无外网回退；或 ARHUD_UNICAST 指定）
#   2. 客户端 routing 必须指向【本机】RM 宿主：
#        B 机没有服务端 → 客户端第一个应用 arhud_client_0 自己当 B 机 RM 宿主
#        （不能指向 A 机的 arhud01！本地通道连不到对端）
#   3. service-discovery.enable=true；多播 224.0.2.4:30490 在网络可达；防火墙放行 UDP
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NET="arhud-net-$$"
A="arhud-dual-a"; B="arhud-dual-b"

cleanup() {
    docker rm -f "$A" "$B" >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== 双机通信测试 (A=服务端 / B=客户端, 独立网络命名空间) ==="

docker network create --driver bridge "$NET" >/dev/null

docker run --rm -d --name "$A" --network "$NET" \
    -v "$ROOT/hud:/hud:ro" -v "$ROOT/vsomeip_example:/app:ro" -v "$ROOT/windows:/win:ro" \
    arhud-vsomeip-test sleep 900 >/dev/null
docker run --rm -d --name "$B" --network "$NET" \
    -v "$ROOT/hud:/hud:ro" -v "$ROOT/vsomeip_example:/app:ro" -v "$ROOT/windows:/win:ro" \
    arhud-vsomeip-test sleep 900 >/dev/null

AIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$A")
BIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$B")
echo "A(服务端)=$AIP  B(客户端)=$BIP"

echo "--- A: 启动服务端（自动探测 unicast）---"
docker exec -d "$A" bash -c 'rm -rf /tmp/r && mkdir /tmp/r && cp -r /hud/* /app/* /win/get_local_ip.py /tmp/r/ && cd /tmp/r && rm -f /tmp/vsomeip-* && ARHUD_SD=true ARHUD_INTERVAL=0.2 python3 -u hud_server.py > server.log 2>&1'
sleep 8

echo "--- B: 启动客户端（routing=arhud_client_0 = B 机本机 RM 宿主）---"
docker exec -d "$B" bash -c 'rm -rf /tmp/r && mkdir /tmp/r && cp -r /hud/* /app/* /win/get_local_ip.py /tmp/r/ && cd /tmp/r && rm -f /tmp/vsomeip-* && ARHUD_SD=true ARHUD_ROUTING_HOST=arhud_client_0 ARHUD_EXIT_ALL=1 python3 -u hud_client.py > client.log 2>&1'

OK=0
for i in $(seq 1 90); do
    docker exec "$B" bash -c 'grep -aq "已收 23/23" /tmp/r/client.log 2>/dev/null' && { OK=1; break; }
    docker exec "$B" bash -c 'grep -aq "\[done\]" /tmp/r/client.log 2>/dev/null' && break
    sleep 1
done

echo "--- A 服务端日志（关键）---"
docker exec "$A" bash -c 'grep -aE "unicast=|\[Host\]|routes unicast" /tmp/r/server.log | head -3'
echo "--- B 客户端日志（关键）---"
docker exec "$B" bash -c 'grep -aE "unicast=|\[Host\]|is registered|ON_AVAILABLE|SUBSCRIBE ACK|已收 23/23|\[done\]" /tmp/r/client.log | head -12'
echo "--- 统计 ---"
echo "B 接收总数: $(docker exec "$B" bash -c 'grep -ac "\[recv\]" /tmp/r/client.log')"
echo "B 去重事件数: $(docker exec "$B" bash -c 'grep -a "\[recv\]" /tmp/r/client.log | grep -oE "svc=0x[0-9A-F]+ inst=0x[0-9A-F]+ event=0x[0-9A-F]+" | sort -u | wc -l | tr -d " "')"

FAIL=0
[ "$OK" -eq 1 ] || { echo "FAIL: B 机客户端未收齐 23 事件"; FAIL=1; }
[ -n "$AIP" ] && [ "$AIP" != "$BIP" ] || { echo "FAIL: 双机 IP 未区分"; FAIL=1; }
docker exec "$B" bash -c 'grep -aq "已收 23/23" /tmp/r/client.log' || { echo "FAIL: 无 23/23 证据"; FAIL=1; }
docker exec "$A" bash -c 'grep -aq "unicast=172" /tmp/r/server.log' || { echo "FAIL: 服务端 unicast 非网络 IP"; FAIL=1; }

if [ "$FAIL" -eq 0 ]; then
    echo
    echo "PASS: 双机通信成功（A=$AIP 服务端 → B=$BIP 客户端收齐 23/23 事件）✔"
    exit 0
else
    echo
    echo "FAIL ✘"
    exit 1
fi
