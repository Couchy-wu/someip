#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArHud SOME/IP 客户端 —— Windows 版（基于 vsomeip_py）
=====================================================
订阅 windows_problem.txt 场景中的 3 个服务（0x000A/0x000B/0x000C）的事件 0x8001，
收齐全部服务后打印收到的数据。

相对 windows_problem.txt 的关键修复（与 Ubuntu 同源 + Windows 特有）：
  1. 【根因】路由管理器宿主配置错误：
     原配置 "routing": "arhud01" —— applications 里没有叫 arhud01 的应用
     → 没有任何进程成为 RM 宿主 → 客户端反复 DEREGISTERED。
     修复：客户端配置 routing = 服务端第一个应用名 "arhud_server"。
  2. vSOMEIP 构造函数第 2 参数 = 【服务 ID】(0x000A)，不是客户端 ID；
     客户端 ID 放在配置 applications[].id（arhud_client=0x1003, ...）。
  3. 用 app.register()（请求服务订阅），不是 app.request()（发送请求报文）。
  4. unicast 用 get_local_ip()；多网卡可设 ARHUD_UNICAST=10.13.90.164。
  5. 服务发现保持开启（事件组订阅要求 SD）。

运行：python3 vsomeip_client_windows.py
环境变量：ARHUD_UNICAST=10.13.90.164  ARHUD_SD=true/false  ARHUD_EXIT_ALL=1(收齐退出)
"""

import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from get_local_ip import get_local_ip

try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:  # 兼容某些 fork（模块名 vsomeip）
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP

# ---------- 可调常量（环境变量可覆盖） ----------
SERVICE_IDS = [int(x, 0) for x in os.environ.get(
    "ARHUD_SERVICE_IDS", "0x000A,0x000B,0x000C").split(",") if x.strip()]
CLIENT_APP_NAMES = os.environ.get(
    "ARHUD_CLIENT_NAMES", "arhud_client,arhud_client_b,arhud_client_c").split(",")
CLIENT_ID_BASE = int(os.environ.get("ARHUD_CLIENT_ID_BASE", "0x1000"), 0)  # 各客户端应用客户端 ID 基址
INSTANCE_IDS = [int(x, 0) for x in os.environ.get(
    "ARHUD_INSTANCE_IDS", "0x000A,0x000B,0x000C").split(",") if x.strip()]
EVENT_ID = int(os.environ.get("ARHUD_EVENT_ID", "0x8001"), 0)
EVENT_GROUP = int(os.environ.get("ARHUD_EVENT_GROUP", "0x1101"), 0)
SERVICE_PORT_BASE = int(os.environ.get("ARHUD_PORT_BASE", "51400"))
ROUTING_HOST = os.environ.get("ARHUD_ROUTING_HOST", "arhud_server")  # = 服务端第一个应用名！
SD_ENABLE = os.environ.get("ARHUD_SD", "true")
EXIT_ALL = os.environ.get("ARHUD_EXIT_ALL", "") == "1"   # 收齐全部服务后退出
EXIT_AFTER = int(os.environ.get("ARHUD_EXIT_AFTER", "0"))  # 收到 N 条后退出

_lock = threading.Lock()
_total = 0
_received_services = set()


def make_callback(service_index: int, service_id: int):
    def callback(msg_type, sid, iid, eid, data, request_id):
        global _total
        with _lock:
            _total += 1
            _received_services.add(service_index)
            total = _total
            got = sorted(_received_services)
        print(f"[Client] 收到 Service=0x{sid:x} Event=0x{eid:04X} "
              f"len={len(data)} data={bytes(data)[:48]!r}  已收齐 {len(got)}/{len(SERVICE_IDS)}")
        return None
    return callback


def main():
    unicast = get_local_ip()
    print(f"ArHud SOME/IP Client (Windows)  应用名={CLIENT_APP_NAMES[0]} "
          f"unicast={unicast}  routing={ROUTING_HOST}  sd={SD_ENABLE}")
    print(f"本机IP: {unicast}")
    print(f"服务发现: 224.0.2.4:30490")

    configuration = vSOMEIP.configuration()  # 官方模板起步，补齐全部必需键
    configuration["unicast"] = unicast
    for i, svc in enumerate(SERVICE_IDS):
        configuration["applications"].append(
            {"name": CLIENT_APP_NAMES[i], "id": CLIENT_ID_BASE + i})
        configuration["clients"].append({
            "service": svc,
            "instance": INSTANCE_IDS[i],
            "unreliable": SERVICE_PORT_BASE + i,
        })
    # 【根因修复】显式声明路由管理器宿主 = 服务端第一个应用名
    configuration["routing"] = ROUTING_HOST
    configuration["service-discovery"]["enable"] = SD_ENABLE

    apps = [vSOMEIP(CLIENT_APP_NAMES[i], SERVICE_IDS[i], INSTANCE_IDS[i],
                    configuration=configuration, force=True)
            for i in range(len(SERVICE_IDS))]
    for i, app in enumerate(apps):
        app.create()
        app.on_event(EVENT_ID, make_callback(i, SERVICE_IDS[i]), group=EVENT_GROUP)  # 订阅事件
        app.register()  # 【修复】请求服务订阅（不是 app.request()）
    for app in apps:
        app.start()

    print(f"[Client] 已启动，订阅 {len(SERVICE_IDS)} 个服务的事件 0x{EVENT_ID:04X}...")
    try:
        while True:
            with _lock:
                if EXIT_AFTER and _total >= EXIT_AFTER:
                    print(f"[Client] 已收到 {_total} 条，退出")
                    break
                if EXIT_ALL and len(_received_services) >= len(SERVICE_IDS):
                    print(f"[Client] {len(SERVICE_IDS)} 个服务均已收到事件，退出")
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
