#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArHud SOME/IP 服务端 —— Windows 版（基于 vsomeip_py）
=====================================================
对应 windows_problem.txt 的场景：服务端提供 3 个服务：
    Service 0x000A (Instance 0x000A, Port 51400) - 车辆位置信息
    Service 0x000B (Instance 0x000B, Port 51401) - RTK/IMU 信息
    Service 0x000C (Instance 0x000C, Port 51402) - 障碍物/车道线
每个服务提供事件 0x8001（事件组 ARHUD_EVENT_GROUP），周期 notify。

相对 windows_problem.txt 的关键修复（与 Ubuntu 同源 + Windows 特有）：
  1. 路由管理器宿主：第一个应用名 arhud_server 自动成为 RM 宿主，
     客户端必须配置 routing="arhud_server"（原配置 routing="arhud01" 无此应用 → 无宿主 → DEREGISTERED 循环）
  2. vSOMEIP 构造函数第 2 参数 = 【服务 ID】(0x000A)，不是客户端 ID；
     客户端 ID 放在配置 applications[].id（arhud_server=0x1201, ...）
  3. unicast 用 get_local_ip()（多网卡环境可设 ARHUD_UNICAST=10.13.90.164 显式指定）
  4. 服务发现保持开启（vsomeip 事件组订阅要求 SD）
  5. Windows 必须使用 justinlhudson/vsomeip 分支编译的 vsomeip_py
     （Windows 上本地路由是 127.0.0.1 TCP，不是 UDS）

运行：python3 vsomeip_server_windows.py
环境变量：ARHUD_UNICAST=10.13.90.164  ARHUD_SD=true/false  ARHUD_INTERVAL=0.2  ARHUD_SEND_COUNT=0
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from get_local_ip import get_local_ip

try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:  # 兼容某些 fork（模块名 vsomeip）
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP

# ---------- 可调常量（环境变量可覆盖） ----------
SERVICES = int(os.environ.get("ARHUD_SERVICES", "3"))     # 服务个数
SERVICE_IDS = [int(x, 0) for x in os.environ.get(
    "ARHUD_SERVICE_IDS", "0x000A,0x000B,0x000C").split(",") if x.strip()]
SERVER_APP_NAMES = os.environ.get(
    "ARHUD_SERVER_NAMES", "arhud_server,arhud_server_b,arhud_server_c").split(",")
SERVER_ID_BASE = int(os.environ.get("ARHUD_SERVER_ID_BASE", "0x1200"), 0)  # 各应用客户端 ID 基址
INSTANCE_IDS = [int(x, 0) for x in os.environ.get(
    "ARHUD_INSTANCE_IDS", "0x000A,0x000B,0x000C").split(",") if x.strip()]
EVENT_ID = int(os.environ.get("ARHUD_EVENT_ID", "0x8001"), 0)
EVENT_GROUP = int(os.environ.get("ARHUD_EVENT_GROUP", "0x1101"), 0)  # 与客户端订阅一致即可
SERVICE_PORT_BASE = int(os.environ.get("ARHUD_PORT_BASE", "51400"))
SD_ENABLE = os.environ.get("ARHUD_SD", "true")
SEND_INTERVAL_S = float(os.environ.get("ARHUD_INTERVAL", "0.2"))
SEND_COUNT = int(os.environ.get("ARHUD_SEND_COUNT", "0"))  # 总发送条数上限，0=无限


def main():
    unicast = get_local_ip()
    print(f"ArHud SOME/IP Server (Windows)  unicast={unicast}  sd={SD_ENABLE}")
    for i, svc in enumerate(SERVICE_IDS):
        print(f"  提供服务: 0x{svc:X} (Instance=0x{INSTANCE_IDS[i]:X}, Port={SERVICE_PORT_BASE + i})")

    configuration = vSOMEIP.configuration()  # 官方模板起步，补齐全部必需键
    configuration["unicast"] = unicast
    for i, svc in enumerate(SERVICE_IDS):
        configuration["applications"].append(
            {"name": SERVER_APP_NAMES[i], "id": SERVER_ID_BASE + i})
        configuration["services"].append({
            "service": svc,
            "instance": INSTANCE_IDS[i],
            "unreliable": SERVICE_PORT_BASE + i,
        })
    # 注意键名是 "enable"（不是 "enabled"！后者会被 vsomeip 忽略）
    configuration["service-discovery"]["enable"] = SD_ENABLE

    # 先统一构造（共享类级配置），再统一 create/offer/start
    apps = [vSOMEIP(SERVER_APP_NAMES[i], SERVICE_IDS[i], INSTANCE_IDS[i],
                    configuration=configuration, force=True)
            for i in range(len(SERVICE_IDS))]
    for app in apps:
        app.create()
    for app in apps:
        app.offer()                                      # offer_service
    for app in apps:
        app.start()
    for i, app in enumerate(apps):
        app.offer(events=[EVENT_ID], group=EVENT_GROUP)  # offer_event

    print(f"[Server] 启动服务... 事件 0x{EVENT_ID:04X} 组 0x{EVENT_GROUP:04X}（Ctrl+C 退出）")
    print(f"[Server] 开始发送事件通知...")

    counter = 0
    try:
        while True:
            for i, app in enumerate(apps):
                counter += 1
                if SEND_COUNT and counter > SEND_COUNT:
                    print(f"[Server] 已发送 {SEND_COUNT} 条，退出")
                    return
                payload = bytearray(f"svc_{i}_data_{counter}".encode())
                print(f"[Server] 已通知 Service=0x{SERVICE_IDS[i]:x}, "
                      f"Event=0x{EVENT_ID:04X}, Counter={counter}")
                app.notify(EVENT_ID, payload)
                time.sleep(SEND_INTERVAL_S)
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
