#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArHud SOME/IP 客户端（基于 vsomeip_py）：订阅事件 0x8003 并反序列化
==================================================================
完整链路：订阅 → 收到事件载荷 → 反序列化 → 打印结构体内容

- 本客户端用于自测/演示。你项目里已写好的客户端（C++/其它语言）无需任何改动，
  只要服务/实例/事件/事件组/端口与 server.py 一致即可收到同样的数据。
- 事件回调中 data 是事件载荷（NewLaneLineDataNotify 序列化字节）。

运行：python3 client.py
"""

import os
import time

from arhud_data_types import NewLaneLineDataNotify

try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:  # 兼容某些 fork（模块名 vsomeip）
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP

# ---------- 与 server.py 对齐的关键常量 ----------
APPLICATION_NAME = "arhud_client"
CLIENT_ID = 0x1003
SERVICE_ID = 0x000C
INSTANCE_ID = 0x000C
EVENT_ID = 0x8003           # NewLaneLineDataNotify
EVENT_GROUP = 0x01          # 必须等于服务端 offer 的事件组
SERVICE_PORT = 51402

# 路由管理器宿主：必须等于服务端的 APPLICATION_NAME！
# vsomeip 中客户端必须显式声明 routing host，否则每个应用都会自建路由管理器
# （多进程场景下客户端、服务端各自为政 → 收不到事件）。
# 注意: vsomeip_py 只在"services 非空"时自动设置 routing，客户端必须手动补上。
ROUTING_HOST = "arhud_server"

# 可用环境变量覆盖（便于自动化测试）
SD_ENABLE = os.environ.get("ARHUD_SD", "true")              # 服务发现开关
EXIT_AFTER = int(os.environ.get("ARHUD_EXIT_AFTER", "0"))   # 收到 N 条事件后退出，0=不退出
_received_count = 0


def event_callback(msg_type, service_id, instance_id, event_id, data, request_id):
    """vsomeip 事件回调：data 为事件载荷字节"""
    global _received_count
    _received_count += 1
    print(f"\n{'='*68}")
    print(f"收到事件: service=0x{service_id:04X} instance=0x{instance_id:04X} "
          f"event=0x{event_id:04X} msg_type={msg_type} len={len(data)}")
    print("HEX: " + bytes(data).hex().upper())
    try:
        notify = NewLaneLineDataNotify.from_bytes(bytes(data))
        print("解析结果:")
        print(str(notify))
    except Exception as e:
        print(f"反序列化失败: {e}")
    print("=" * 68)
    return None  # 事件不产生响应


def main():
    print(f"ArHud SOME/IP Client (vsomeip_py)  service=0x{SERVICE_ID:04X} "
          f"event=0x{EVENT_ID:04X} group=0x{EVENT_GROUP:04X}  sd={SD_ENABLE}")

    configuration = vSOMEIP.configuration()
    configuration["unicast"] = "127.0.0.1"
    # 注意: applications[].id 是【客户端 ID】(0x1003)；构造函数第 2 个参数是【服务 ID】(0x000C)。
    # vsomeip_py 的 vSOMEIP(name, id, instance) 中 id 是服务 ID（on_event/register 用它），
    # 客户端 ID 由配置 applications[].id 决定。两者可以不同！
    configuration["applications"].append({"name": APPLICATION_NAME, "id": CLIENT_ID})
    configuration["clients"].append({
        "service": SERVICE_ID,
        "instance": INSTANCE_ID,
        "unreliable": SERVICE_PORT,
    })
    # 关键：显式声明路由管理器宿主（否则本进程会自建 RM，收不到服务端事件）
    configuration["routing"] = ROUTING_HOST
    # 注意键名是 "enable"（不是 "enabled"！后者会被 vsomeip 忽略）
    configuration["service-discovery"]["enable"] = SD_ENABLE

    app = vSOMEIP(APPLICATION_NAME, SERVICE_ID, INSTANCE_ID,
                  configuration=configuration, force=True)
    app.create()

    # 注册事件（内部执行 request_event + subscribe 到事件组 EVENT_GROUP）
    app.on_event(EVENT_ID, event_callback, group=EVENT_GROUP)

    # 请求服务（关键：不是 app.request()）
    app.register()

    app.start()
    print(f"客户端已启动，订阅 event 0x8003 ...（Ctrl+C 退出；ARHUD_EXIT_AFTER={EXIT_AFTER}）")

    try:
        while True:
            if EXIT_AFTER and _received_count >= EXIT_AFTER:
                print(f"[done] 已收到 {_received_count} 条事件，退出（ARHUD_EXIT_AFTER 限制）")
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        app.stop()
        print("客户端已停止")


if __name__ == "__main__":
    main()
