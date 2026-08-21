#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
to_longjie_demo_20250625 真实客户端专用 Python 服务端
======================================================
目标：让板端编译好的 C++ 客户端 (hud_huifang_client, SP栈/SomeipCom) 正确订阅并收到数据。

与 C++ 服务端 (hud_pcap_huifang_server) 行为对齐的关键点：
  1. 11 个服务 / 23 个事件，offer 版本 major=1（客户端配置 "major":"1" 按 1.0 请求/订阅）
  2. 路由管理器宿主 = arhud01（客户端配置 routing="arhud01" 经 UDS 连它；跨机时客户端改 routing=自身）
  3. 服务端口按附录A修正表：51400-51409 / 0x010A→52001；0x010A instance=0x0001，其余 instance=service_id
  4. 0x000E 三事件分属 0x1101/0x1102/0x1103；另在 eventgroup 0x0000 也 offer（固定配置的
     SP 客户端用组 0 订阅 0x000E，见 README 三.5 节）
  5. SD: 224.0.2.4:30490, enable=true
  6. max-payload-size-unreliable=3000000 + 0x010A someip-tp(0x8001/0x8003)：大帧走 SOME/IP-TP
  7. 载荷来源：out.pcap 回放（含 SOME/IP-TP 重组，与 C++ 服务端一致）；pcap 缺失的事件可选项生成
  8. 生成载荷自动计算 Checksum = CRC32(payload[4:])（与 pcap 实测语义一致）

两种部署模式：
  A. 客户端配置可改（推荐）→ 客户端 routing=arhud02 自托管 RM，跨机网络模式（README 四章）
  B. 客户端配置固定（板端烧录）→ 板子保留 SP 分支 RM 宿主（C++服务端+空services+静默pcap），
     Python 服务端跨机；客户端 UDS→本地RM→SD→本服务端（README 三.5 节）

运行:  python3 hud_server_longjie.py
环境变量:
  ARHUD_PCAP           pcap 路径（默认自动探测 ../to_longjie_demo_20250625/build/out.pcap）
  ARHUD_UNICAST        指定本机 IP（默认自动探测）
  ARHUD_SD             true/false 服务发现开关（默认 true）
  ARHUD_FILL_MISSING   1=对 pcap 缺失且已定义类型的事件生成数据发送（默认 1；0=仅忠实回放 pcap）
  ARHUD_MAX_DELAY      单条发送最大间隔秒（默认 0.5，加速回放）
  ARHUD_SEND_COUNT     0=无限循环
"""
import os
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "hud")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "vsomeip_example")))

from hud_data_types import HUD_EVENTS, services_map, make_sample, SERIALIZERS

try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP

try:
    from get_local_ip import get_local_ip
except ImportError:
    def get_local_ip():
        return os.environ.get("ARHUD_UNICAST") or "127.0.0.1"

SD_ENABLE = os.environ.get("ARHUD_SD", "true").lower() == "true"
FILL_MISSING = os.environ.get("ARHUD_FILL_MISSING", "1") == "1"
MAX_DELAY = float(os.environ.get("ARHUD_MAX_DELAY", "0.5"))
SEND_COUNT = int(os.environ.get("ARHUD_SEND_COUNT", "0"))
SERVER_ID_BASE = int(os.environ.get("ARHUD_SERVER_ID_BASE", "0x1443"), 0)

# 生成载荷时补 Checksum = CRC32(payload[4:])（与 pcap 实测语义一致）
def build_sample(kind: str, counter: int) -> bytes:
    import struct
    raw = bytes(make_sample(kind, counter))
    if len(raw) >= 4:
        crc = zlib.crc32(raw[4:]) & 0xFFFFFFFF
        raw = struct.pack(">I", crc) + raw[4:]
    return raw


def discover_pcap():
    candidates = [
        os.environ.get("ARHUD_PCAP", ""),
        os.path.join(HERE, "out.pcap"),
        os.path.abspath(os.path.join(HERE, "..", "to_longjie_demo_20250625", "build", "out.pcap")),
        os.path.abspath(os.path.join(HERE, "..", "to_longjie_demo_20250625", "out.pcap")),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def main():
    svc_map = services_map()
    unicast = get_local_ip()
    print(f"[Server] to_longjie 23 事件 Python 服务端  unicast={unicast}  sd={SD_ENABLE}  "
          f"fill_missing={FILL_MISSING}", flush=True)

    configuration = vSOMEIP.configuration()
    configuration["unicast"] = unicast
    configuration["network"] = "arhud01"      # 与板端配置一致：UDS socket 为 /tmp/arhud01-*
    app_names = []
    for i, svc in enumerate(svc_map):
        name = "arhud01" if i == 0 else f"arhud01_{i}"
        app_names.append(name)
        configuration["applications"].append({"name": name, "id": SERVER_ID_BASE + i})
        cfg = svc_map[svc]
        entry = {"service": svc, "instance": cfg["instance"],
                 "unreliable": cfg["port"], "major": "1", "minor": "0"}
        if svc == 0x010A:
            entry["someip-tp"] = {"service-to-client": ["0x8001", "0x8003"]}
        elif svc == 0x000C:
            # 0x000C:8002/8003 载荷超过 VSOMEIP_MAX_UDP_MESSAGE_SIZE(1400)，
            # 标准 vsomeip 必须显式开启 someip-tp 才会分片（SP 分支自动分片，标准版不会）
            entry["someip-tp"] = {"service-to-client": ["0x8002", "0x8003"]}
        configuration["services"].append(entry)
    configuration["service-discovery"]["enable"] = SD_ENABLE
    configuration["service-discovery"]["multicast"] = "224.0.2.4"
    configuration["max-payload-size-unreliable"] = "3000000"

    apps = []
    for i, svc in enumerate(svc_map):
        cfg = svc_map[svc]
        apps.append(vSOMEIP(app_names[i], svc, cfg["instance"],
                            version=(1, 0), configuration=configuration, force=True))
    for app in apps:
        app.create()
    for i, app in enumerate(apps):
        app.offer()          # offer_service(service, instance, major=1, minor=0)
        svc = list(svc_map)[i]
        cfg = svc_map[svc]
        for event, name, group, kind in cfg["events"]:
            app.offer(events=[event], group=group)
            if svc == 0x000E:
                # 客户端配置固定时(板端烧录, 无法改 0x000E 拆分)，SP 包装器会以 eventgroup
                # 0x0000 订阅 0x000E 事件 → 服务端额外在组 0x0000 提供这三个事件
                app.offer(events=[event], group=0x0000)
            print(f"  offer: svc=0x{svc:04X} inst=0x{cfg['instance']:04X} "
                  f"event=0x{event:04X} group=0x{group:04X} port={cfg['port']} {name}",
                  flush=True)
    for app in apps:
        app.start()

    # 载荷计划
    pcap_file = discover_pcap()
    replay = {}
    if pcap_file:
        from pcap_replay_tp import decode_pcap_replay
        replay = decode_pcap_replay(pcap_file)
        print(f"[Server] 回放 pcap: {pcap_file}", flush=True)
    else:
        print("[Server] 未找到 pcap，将仅发送生成数据", flush=True)

    # 每个事件的载荷池: pcap 优先，缺失事件按需生成
    pools = {}
    for svc, inst, event, name, group, port, kind in HUD_EVENTS:
        key = (svc, event)
        if key in replay and replay[key]:
            pools[key] = [bytearray(p) for p in replay[key]]
        elif FILL_MISSING and kind != "Opaque" and kind in SERIALIZERS:
            pools[key] = [bytearray(build_sample(kind, n)) for n in range(1, 4)]
        else:
            pools[key] = []   # 不发送（与 C++ 服务端一致：pcap 没有的就不发）

    sent = 0
    idx = 0
    app_by_svc = {svc: apps[i] for i, svc in enumerate(svc_map)}
    try:
        while True:
            for svc, inst, event, name, group, port, kind in HUD_EVENTS:
                pool = pools[(svc, event)]
                if not pool:
                    continue
                payload = pool[idx % len(pool)]
                app_by_svc[svc].notify(event, payload)
                sent += 1
                print(f"[send] #{sent} svc=0x{svc:04X} event=0x{event:04X} "
                      f"{name:34s} len={len(payload):5d}B hex={bytes(payload)[:12].hex().upper()}",
                      flush=True)
                if SEND_COUNT and sent >= SEND_COUNT:
                    print(f"[Server] 已发送 {SEND_COUNT} 条，退出", flush=True)
                    return
            idx += 1
            time.sleep(MAX_DELAY)
    except KeyboardInterrupt:
        print("\n[Server] 正在退出...", flush=True)
    finally:
        for app in apps:
            try:
                app.stop()
            except Exception:
                pass
        print("[Server] 已停止", flush=True)


if __name__ == "__main__":
    main()
