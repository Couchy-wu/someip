#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AR-HUD 23 服务 SOME/IP 客户端（vsomeip_py）
============================================
按 new_describe.md 订阅 23 个事件（11 个服务，每个服务一个 vsomeip 应用）：
  - routing = "arhud01"（服务端第一个应用，路由管理器宿主）
  - 每个事件的 event_group 按其注册表（0x000E 三事件分属 0x1101/0x1102/0x1103）
  - 已定义类型：反序列化并按字段摘要打印；Opaque 类型：hex 展示
  - ARHUD_EXIT_ALL=1：收齐全部 23 个事件后退出（集成测试用）

运行：python3 hud_client.py
环境变量：ARHUD_UNICAST  ARHUD_SD  ARHUD_ROUTING_HOST(默认 arhud01)  ARHUD_EXIT_ALL
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vsomeip_example")))
from hud_data_types import (HUD_EVENTS, DESERIALIZERS, event_info,
                            kind_of, summarize, services_map)
try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP
try:
    from get_local_ip import get_local_ip
except ImportError:
    get_local_ip = lambda: os.environ.get("ARHUD_UNICAST", "127.0.0.1")

ROUTING_HOST = os.environ.get("ARHUD_ROUTING_HOST", "arhud01")
SD_ENABLE = os.environ.get("ARHUD_SD", "true")
CLIENT_ID_BASE = int(os.environ.get("ARHUD_CLIENT_ID_BASE", "0x2000"), 0)
EXIT_ALL = os.environ.get("ARHUD_EXIT_ALL", "") == "1"
EXIT_AFTER = int(os.environ.get("ARHUD_EXIT_AFTER", "0"))

_lock = threading.Lock()
_total = 0
_received = set()          # (service, event) 已收到的事件集合


def make_callback(service: int):
    def callback(msg_type, sid, iid, eid, data, request_id):
        global _total
        info = event_info(sid, eid)
        name = info["name"] if info else f"unknown_0x{eid:04X}"
        kind = info["kind"] if info else "Opaque"
        with _lock:
            _total += 1
            _received.add((sid, eid))
            total = _total
            got = len(_received)
        line = f"[recv] #{total} svc=0x{sid:04X} inst=0x{iid:04X} event=0x{eid:04X} {name} len={len(data)} 已收 {got}/23"
        detail = ""
        if kind in DESERIALIZERS:
            try:
                parsed, _ = DESERIALIZERS[kind](bytes(data))
                detail = "  " + summarize(kind, parsed)
            except Exception as e:
                detail = f"  [解析失败: {e}]"
        else:
            detail = f"  HEX={bytes(data)[:24].hex().upper()}"
        print(line + detail, flush=True)
        return None
    return callback


def main():
    svc_map = services_map()
    unicast = get_local_ip()
    print(f"AR-HUD 23 服务 Client (vsomeip_py)  unicast={unicast}  "
          f"routing={ROUTING_HOST}  sd={SD_ENABLE}")
    print(f"订阅 {len(HUD_EVENTS)} 个事件 / {len(svc_map)} 个服务")

    configuration = vSOMEIP.configuration()
    configuration["unicast"] = unicast
    svc_ids = list(svc_map.keys())
    for i, svc in enumerate(svc_ids):
        configuration["applications"].append(
            {"name": f"arhud_client_{i}", "id": CLIENT_ID_BASE + i})
        cfg = svc_map[svc]
        configuration["clients"].append(
            {"service": svc, "instance": cfg["instance"], "unreliable": cfg["port"]})
    configuration["routing"] = ROUTING_HOST      # 关键：指向服务端第一个应用
    configuration["service-discovery"]["enable"] = SD_ENABLE
    # 多播组统一用 new_describe.md 规定的 224.0.2.4（与 C++ 客户端一致；双机两端必须同组）
    configuration["service-discovery"]["multicast"] = "224.0.2.4"

    apps = []
    for i, svc in enumerate(svc_ids):
        cfg = svc_map[svc]
        apps.append(vSOMEIP(f"arhud_client_{i}", svc, cfg["instance"],
                            configuration=configuration, force=True))
    for i, svc in enumerate(svc_ids):
        cfg = svc_map[svc]
        apps[i].create()
        for event, name, group, kind in cfg["events"]:
            apps[i].on_event(event, make_callback(svc), group=group)
        apps[i].register()
    for app in apps:
        app.start()

    print(f"[Client] 已启动，订阅 {len(HUD_EVENTS)} 个事件 ...（Ctrl+C 退出）")
    try:
        while True:
            with _lock:
                if EXIT_AFTER and _total >= EXIT_AFTER:
                    print(f"[done] 已收到 {_total} 条事件，退出（ARHUD_EXIT_AFTER）", flush=True)
                    break
                if EXIT_ALL and len(_received) >= len(HUD_EVENTS):
                    print(f"[done] 全部 {len(HUD_EVENTS)} 个事件均已收到，退出（ARHUD_EXIT_ALL）",
                          flush=True)
                    break
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[Client] 正在退出...")
    finally:
        for app in apps:
            try:
                app.stop()
            except Exception:
                pass
        print("[Client] 已停止")


if __name__ == "__main__":
    main()
