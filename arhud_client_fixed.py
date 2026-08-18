#!/usr/bin/env python3
"""
ArHud SOME/IP Client - Python 修正版
基于 COVESA vsomeip_py 官方用法 (https://github.com/COVESA/vsomeip_py)

与原始 arhud_client.py 的关键差异（详见同目录 SOLUTION.md）：
1. 配置以官方模板 vSOMEIP.configuration() 为基准增量修改，补齐全部必需键
   （unicast / netmask / applications / services / clients / service-discovery）。
2. 用 app.register() 请求服务 —— 原代码 app.request(SERVICE_ID) 是"发送请求报文"，
   不是"请求服务"，会导致客户端从不向路由管理器请求该服务，收不到可用性与事件。
3. 事件组 group 显式与服务端一致（0x01，也可两端都用默认 0xFFFF）。
4. vSOMEIP(..., force=True) 自动清理残留的 /tmp/vsomeip-*.lck 锁文件。
5. 建议客户端与服务端在【不同目录】下启动，避免共用/互相覆盖同一个 vsomeip.json。

运行前提：本机构建安装好 COVESA vsomeip C++ 库（libvsomeip3 / libvsomeip3-cfg）与 vsomeip_py。
"""

import time

try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:  # 兼容某些 fork（模块名 vsomeip）
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP

# 服务配置
APPLICATION_NAME = "arhud_client"
SERVICE_ID = 0x000C
INSTANCE_ID = 0x000C
EVENT_ID = 0x8003      # NewLaneLineDataNotify
EVENT_GROUP = 0x01     # 事件组，须与服务端 offer(events=[...], group=...) 一致
CLIENT_ID = 0x1003
SERVICE_PORT = 51402


def event_callback(msg_type, service_id, instance_id, event_id, data, request_id):
    """事件回调函数（事件不产生响应，返回 None）"""
    print(f"\n{'='*60}")
    print("收到事件数据!")
    print(f"  Service ID:    0x{service_id:04X}")
    print(f"  Instance ID:   0x{instance_id:04X}")
    print(f"  Event ID:      0x{event_id:04X}")
    print(f"  Message Type:  {msg_type}")
    print(f"  Request ID:    0x{request_id:04X}")
    print(f"  Data length:   {len(data)} bytes")
    print("  " + bytes(data).hex().upper())
    print(f"{'='*60}\n")
    return None


def main():
    print("ArHud SOME/IP Client - Python (fixed)")
    print(f"Service ID: 0x{SERVICE_ID:04X}, Event ID: 0x{EVENT_ID:04X}, Group: 0x{EVENT_GROUP:04X}")

    # 以官方模板为基准（模板含全部必需键），只做增量修改
    configuration = vSOMEIP.configuration()
    configuration["unicast"] = "127.0.0.1"
    configuration["applications"].append({"name": APPLICATION_NAME, "id": CLIENT_ID})
    configuration["clients"].append({
        "service": SERVICE_ID,
        "instance": INSTANCE_ID,
        "unreliable": SERVICE_PORT,
    })
    # 注意键名是 "enable"（原报告写成 "enabled"，该键被 vsomeip 忽略，服务发现从未被关闭）
    configuration["service-discovery"]["enable"] = "true"

    print("正在创建应用...")
    app = vSOMEIP(APPLICATION_NAME, CLIENT_ID, INSTANCE_ID,
                  configuration=configuration, force=True)
    app.create()

    # 注册事件（内部执行 request_event + subscribe 到事件组 EVENT_GROUP）
    print(f"注册事件: Event = 0x{EVENT_ID:04X}, Group = 0x{EVENT_GROUP:04X}")
    app.on_event(EVENT_ID, event_callback, group=EVENT_GROUP)

    # 请求服务（关键！不是 app.request()）
    print(f"请求服务: Service = 0x{SERVICE_ID:04X}, Instance = 0x{INSTANCE_ID:04X}")
    app.register()

    print("启动应用...")
    app.start()

    print("客户端已启动，按 Ctrl+C 退出")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        app.stop()
        print("客户端已停止")


if __name__ == "__main__":
    main()
