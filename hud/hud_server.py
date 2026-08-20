#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AR-HUD 23 服务 SOME/IP 服务端（vsomeip_py）
============================================
按 new_describe.md 提供 11 个服务（23 个事件）：
  - 端口/实例按附录A修正表（0x010A 特殊：instance=0x0001, 端口 52001；其余 instance=service_id, 端口 51400-51409）
  - 0x000E 的 3 个事件分属事件组 0x1101/0x1102/0x1103
  - 路由管理器宿主 = 第一个应用 arhud01（客户端 routing=arhud01 指向它）
  - 载荷 = hud_data_types 按大端序列化的样例数据（已定义类型）/ 若干字节（Opaque 类型）

运行：python3 hud_server.py
环境变量：ARHUD_UNICAST（默认自动探测）ARHUD_SD(true) ARHUD_INTERVAL(0.2) ARHUD_SEND_COUNT(0=无限)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vsomeip_example")))
from hud_data_types import HUD_EVENTS, make_sample, services_map
try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP
try:
    from get_local_ip import get_local_ip
except ImportError:
    get_local_ip = lambda: os.environ.get("ARHUD_UNICAST", "127.0.0.1")

SD_ENABLE = os.environ.get("ARHUD_SD", "true")
SEND_INTERVAL_S = float(os.environ.get("ARHUD_INTERVAL", "0.2"))
SEND_COUNT = int(os.environ.get("ARHUD_SEND_COUNT", "0"))
SERVER_ID_BASE = int(os.environ.get("ARHUD_SERVER_ID_BASE", "0x1443"), 0)  # 第一个=0x1443(文档应用ID)


def main():
    svc_map = services_map()   # {service: {instance, port, events:[(event,name,group,kind)]}}
    unicast = get_local_ip()
    print(f"AR-HUD 23 服务 Server (vsomeip_py)  unicast={unicast}  sd={SD_ENABLE}")
    print(f"服务数: {len(svc_map)}  事件数: {len(HUD_EVENTS)}")

    configuration = vSOMEIP.configuration()
    configuration["unicast"] = unicast
    app_names = []
    for i, svc in enumerate(svc_map):
        name = "arhud01" if i == 0 else f"arhud01_{i}"   # 第一个 = arhud01（路由宿主）
        app_names.append(name)
        configuration["applications"].append({"name": name, "id": SERVER_ID_BASE + i})
        cfg = svc_map[svc]
        configuration["services"].append({
            "service": svc, "instance": cfg["instance"], "unreliable": cfg["port"]})
    configuration["service-discovery"]["enable"] = SD_ENABLE

    apps = []
    for i, svc in enumerate(svc_map):
        cfg = svc_map[svc]
        apps.append(vSOMEIP(app_names[i], svc, cfg["instance"],
                            configuration=configuration, force=True))
    for app in apps:
        app.create()
    for app in apps:
        app.offer()
    for app in apps:
        app.start()
    for i, svc in enumerate(svc_map):
        cfg = svc_map[svc]
        for event, name, group, kind in cfg["events"]:
            apps[i].offer(events=[event], group=group)
            print(f"  offer: svc=0x{svc:04X} inst=0x{cfg['instance']:04X} "
                  f"event=0x{event:04X} group=0x{group:04X} port={cfg['port']} {name}")

    print(f"[Server] 启动完成，开始发送 23 个事件（Ctrl+C 退出）")
    counter = 0
    try:
        while True:
            for i, svc in enumerate(svc_map):
                cfg = svc_map[svc]
                for event, name, group, kind in cfg["events"]:
                    counter += 1
                    if SEND_COUNT and counter > SEND_COUNT:
                        print(f"[Server] 已发送 {SEND_COUNT} 条，退出")
                        return
                    payload = bytearray(make_sample(kind, counter))
                    apps[i].notify(event, payload)
                    if SEND_COUNT == 0 or counter <= 5:
                        print(f"  [send] #{counter} svc=0x{svc:04X} event=0x{event:04X} "
                              f"{name} payload={len(payload)}B")
                    time.sleep(SEND_INTERVAL_S / max(1, len(cfg["events"])))
    except KeyboardInterrupt:
        print("\n[Server] 正在退出...")
    finally:
        for app in apps:
            try:
                app.stop()
            except Exception:
                pass
        print("[Server] 已停止")


if __name__ == "__main__":
    main()
