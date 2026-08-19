#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArHud SOME/IP 客户端 —— 20 服务版（基于 vsomeip_py）
=====================================================
订阅 ARHUD_SERVICES(默认 20) 个服务的事件 0x8003 并反序列化。
每个服务一个客户端应用实例（唯一应用名 arhud_cli_i、唯一客户端 ID 0x2000+i）。

- 事件回调中 service_id 即数据来源服务；payload 的 timestamp 字段携带服务序号，可交叉验证
- ARHUD_EXIT_ALL=1：收齐全部 SERVICES 个服务的事件后自动退出（供集成测试用）
- ARHUD_EXIT_AFTER=N：收到 N 条事件后自动退出

运行：python3 client_multi.py
"""

import os
import time
import threading

from arhud_data_types import NewLaneLineDataNotify

try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:  # 兼容某些 fork（模块名 vsomeip）
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP

# ---------- 可调常量（环境变量可覆盖） ----------
SERVICES = int(os.environ.get("ARHUD_SERVICES", "20"))
SERVICE_ID_BASE = 0x0100
CLIENT_ID_BASE = 0x2000                                 # 各客户端应用的客户端 ID（0x2000+i）
INSTANCE_ID = 0x0001
EVENT_ID = 0x8003
EVENT_GROUP = 0x01
SERVICE_PORT_BASE = 51402
ROUTING_HOST = "arhud_svc_0"                            # 路由管理器宿主 = 服务端第一个应用
SD_ENABLE = os.environ.get("ARHUD_SD", "true")
EXIT_AFTER = int(os.environ.get("ARHUD_EXIT_AFTER", "0"))
EXIT_ALL = os.environ.get("ARHUD_EXIT_ALL", "") == "1"  # 收齐全部服务后退出

# 跨 io 线程共享的接收统计
_lock = threading.Lock()
_total = 0                 # 总接收事件数
_received_services = set()  # 已收到事件的服务序号集合


def make_callback(service_index: int):
    """为第 service_index 个服务生成事件回调"""
    def callback(msg_type, service_id, instance_id, event_id, data, request_id):
        global _total
        with _lock:
            _total += 1
            _received_services.add(service_index)
            total = _total
            got = sorted(_received_services)
        print(f"\n[recv] #{total} 来自服务 {service_index} (0x{service_id:04X}) "
              f"event=0x{event_id:04X} len={len(data)}  已收齐 {len(got)}/{SERVICES}")
        try:
            notify = NewLaneLineDataNotify.from_bytes(bytes(data))
            print(f"       反序列化 OK: version={notify.version} "
                  f"timestamp(服务序号)={notify.timestamp} lane_count={notify.lane_count}")
            for lane in notify.lanes[:2]:
                print(f"       {lane}")
        except Exception as e:
            print(f"       反序列化失败: {e}")
        return None
    return callback


def main():
    print(f"ArHud SOME/IP Client x{SERVICES} (vsomeip_py)  "
          f"services=0x{SERVICE_ID_BASE:04X}..0x{SERVICE_ID_BASE + SERVICES - 1:04X}  "
          f"event=0x{EVENT_ID:04X} group=0x{EVENT_GROUP:04X}  sd={SD_ENABLE}")

    configuration = vSOMEIP.configuration()
    configuration["unicast"] = "127.0.0.1"
    for i in range(SERVICES):
        configuration["applications"].append(
            {"name": f"arhud_cli_{i}", "id": CLIENT_ID_BASE + i})
        configuration["clients"].append({
            "service": SERVICE_ID_BASE + i,
            "instance": INSTANCE_ID,
            "unreliable": SERVICE_PORT_BASE + i,
        })
    # 关键：显式声明路由管理器宿主（否则每个进程/应用会自建 RM，收不到事件）
    configuration["routing"] = ROUTING_HOST
    # 注意键名是 "enable"（不是 "enabled"！）
    configuration["service-discovery"]["enable"] = SD_ENABLE

    apps = [vSOMEIP(f"arhud_cli_{i}", SERVICE_ID_BASE + i, INSTANCE_ID,
                    configuration=configuration, force=True)
            for i in range(SERVICES)]

    for i, app in enumerate(apps):
        app.create()
        app.on_event(EVENT_ID, make_callback(i), group=EVENT_GROUP)  # 订阅
        app.register()                                               # 请求服务

    for app in apps:
        app.start()

    print(f"客户端已启动，订阅 {SERVICES} 个服务的事件 0x{EVENT_ID:04X} ...（Ctrl+C 退出）")
    try:
        while True:
            with _lock:
                if EXIT_AFTER and _total >= EXIT_AFTER:
                    print(f"\n[done] 已收到 {_total} 条事件，退出（ARHUD_EXIT_AFTER）")
                    break
                if EXIT_ALL and len(_received_services) >= SERVICES:
                    print(f"\n[done] {SERVICES} 个服务均已收到事件，退出（ARHUD_EXIT_ALL）")
                    break
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        for app in apps:
            try:
                app.stop()
            except Exception:
                pass
        print("客户端已停止")


if __name__ == "__main__":
    main()
