#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArHud SOME/IP 服务端 —— 20 服务版（基于 vsomeip_py）
=====================================================
服务端提供 ARHUD_SERVICES(默认 20) 个服务：
    Service ID:  SERVICE_ID_BASE + i   (0x0100..0x0113)
    Instance ID: 0x0001
    每个服务提供事件 0x8003（事件组 0x01），周期 notify，
    载荷为 NewLaneLineDataNotify 序列化字节，其中 timestamp 字段携带服务序号(0..19)，
    便于客户端区分数据来自哪个服务。

实现要点（与单服务版一致的多应用模式）：
    - 每个服务一个 vsomeip 应用实例（唯一应用名 arhud_svc_i、唯一客户端 ID 0x1200+i）
    - 先统一构造（共享类级配置，vsomeip.json 含全部 20 个应用），再统一 create/start
    - 第一个应用 arhud_svc_0 自动成为路由管理器宿主，其余 19 个以代理模式注册到它
    - 构造函数第 2 参数是【服务 ID】(SERVICE_ID_BASE+i)；客户端 ID 由配置 applications[].id 决定

运行：python3 server_multi.py
"""

import os
import time

from arhud_data_types import (LaneLineData, LaneLinePoint, LaneLineType,
                              NewLaneLineDataNotify)

try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:  # 兼容某些 fork（模块名 vsomeip）
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP

# ---------- 可调常量（环境变量可覆盖，便于自动化测试） ----------
SERVICES = int(os.environ.get("ARHUD_SERVICES", "20"))   # 服务个数
SERVICE_ID_BASE = 0x0100                                 # 服务 ID 起始（0x0100..0x0100+SERVICES-1）
SERVER_ID_BASE = 0x1200                                  # 各服务应用的客户端 ID（0x1200+i）
INSTANCE_ID = 0x0001
EVENT_ID = 0x8003                                        # NewLaneLineDataNotify
EVENT_GROUP = 0x01
SERVICE_PORT_BASE = 51402                                # 每个服务一个 UDP 端口（51402+i）
SD_ENABLE = os.environ.get("ARHUD_SD", "true")           # 服务发现开关
SEND_INTERVAL_S = float(os.environ.get("ARHUD_INTERVAL", "0.2"))
SEND_COUNT = int(os.environ.get("ARHUD_SEND_COUNT", "0"))  # 总发送条数上限，0=无限


def make_payload(service_index: int) -> bytes:
    """构造某服务的载荷：timestamp 字段 = 服务序号，便于客户端区分"""
    notify = NewLaneLineDataNotify(
        version=1,
        timestamp=service_index,
        lane_count=2,
        lanes=[
            LaneLineData(lane_type=LaneLineType.SOLID, lane_id=1,
                         quality=0.95, confidence=0.98,
                         points=[LaneLinePoint(0.0, 0.0, 0.0),
                                 LaneLinePoint(1.0, 2.0, 0.0),
                                 LaneLinePoint(2.0, 4.0, 0.0)]),
            LaneLineData(lane_type=LaneLineType.DASHED, lane_id=2,
                         quality=0.88, confidence=0.91,
                         points=[LaneLinePoint(0.0, 3.5, 0.0),
                                 LaneLinePoint(1.0, 5.5, 0.0)]),
        ],
    )
    return notify.to_bytes()


def main():
    print(f"ArHud SOME/IP Server x{SERVICES} (vsomeip_py)  "
          f"services=0x{SERVICE_ID_BASE:04X}..0x{SERVICE_ID_BASE + SERVICES - 1:04X}  "
          f"event=0x{EVENT_ID:04X} group=0x{EVENT_GROUP:04X}  sd={SD_ENABLE}")

    # ---------- 配置（共享类级配置：包含全部 20 个应用与 20 个服务） ----------
    configuration = vSOMEIP.configuration()
    configuration["unicast"] = "127.0.0.1"
    for i in range(SERVICES):
        configuration["applications"].append(
            {"name": f"arhud_svc_{i}", "id": SERVER_ID_BASE + i})
        configuration["services"].append({
            "service": SERVICE_ID_BASE + i,
            "instance": INSTANCE_ID,
            "unreliable": SERVICE_PORT_BASE + i,
        })
    # 注意键名是 "enable"（不是 "enabled"！后者会被 vsomeip 忽略）
    configuration["service-discovery"]["enable"] = SD_ENABLE

    # ---------- 先统一构造（force=True 清锁需在 create 之前，避免误删已建应用的锁） ----------
    apps = [vSOMEIP(f"arhud_svc_{i}", SERVICE_ID_BASE + i, INSTANCE_ID,
                    configuration=configuration, force=True)
            for i in range(SERVICES)]

    # ---------- 再统一 create / offer / start ----------
    for app in apps:
        app.create()
    for app in apps:
        app.offer()                                      # offer_service
    for app in apps:
        app.start()
    for app in apps:
        app.offer(events=[EVENT_ID], group=EVENT_GROUP)  # offer_event

    print(f"服务端就绪: {SERVICES} 个服务, 事件 0x{EVENT_ID:04X}（Ctrl+C 退出）\n")

    payloads = [make_payload(i) for i in range(SERVICES)]
    packet_num = 0
    try:
        while True:
            for i, app in enumerate(apps):
                packet_num += 1
                if SEND_COUNT and packet_num > SEND_COUNT:
                    print(f"[done] 已发送 {SEND_COUNT} 条，退出")
                    return
                print(f"[send] #{packet_num} svc={i} (0x{SERVICE_ID_BASE + i:04X}) "
                      f"event=0x{EVENT_ID:04X} payload={len(payloads[i])}B  "
                      f"ts={i}")
                app.notify(EVENT_ID, bytearray(payloads[i]))
                time.sleep(SEND_INTERVAL_S)
    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        for app in apps:
            try:
                app.stop()
            except Exception:
                pass
        print("服务端已停止")


if __name__ == "__main__":
    main()
