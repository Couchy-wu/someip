#!/usr/bin/env python3
"""
ArHud SOME/IP Server - Python 修正版
基于 COVESA vsomeip_py 官方用法 (https://github.com/COVESA/vsomeip_py)

与原始 arhud_server.py 的关键差异（详见同目录 SOLUTION.md）：
1. 配置以官方模板 vSOMEIP.configuration() 为基准增量修改，补齐全部必需键；
   注意 service-discovery 的键名是 "enable" 而不是 "enabled"。
2. app.offer() 提供实例；事件用 app.offer(events=[EVENT_ID], group=G)（列表形式，
   原代码 app.offer(EVENT_ID) 传 int 会 TypeError）。
3. 遵循官方示例启动顺序：create() -> offer() -> start() -> offer(events=[...])。
4. app.notify() 的 data 应为【事件载荷】：load_pcap_data 去掉 SOME/IP 头后回放，
   而不是把带 SOME/IP 头的原始报文整体塞进载荷。
5. vSOMEIP(..., force=True) 自动清理残留锁文件。

运行前提：本机构建安装好 COVESA vsomeip C++ 库与 vsomeip_py。
"""

import time
import os
import struct

try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:  # 兼容某些 fork（模块名 vsomeip）
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP

# 服务配置
APPLICATION_NAME = "arhud_server"
SERVICE_ID = 0x000C
INSTANCE_ID = 0x000C
EVENT_ID = 0x8003      # NewLaneLineDataNotify
EVENT_GROUP = 0x01     # 事件组，须与客户端 on_event(..., group=...) 一致
SERVER_ID = 0x1201
SERVICE_PORT = 51402

# PCAP 文件路径
PCAP_FILE = "/home/ethan/SOMEIP/demo/tools/ArHud/out.pcap"


def load_pcap_data(pcap_file: str) -> list:
    """加载 PCAP 中的 SOME/IP 通知报文，去掉 SOME/IP 头，只保留事件载荷。

    SOME/IP 头(16 字节)：MessageID(4) Length(4) RequestID(4)
                         ProtoVer(1) IfaceVer(1) MsgType(1) RetCode(1)
    事件通知的 MsgType = 0x02 (NOTIFICATION)。
    """
    try:
        from scapy.all import rdpcap, IP, UDP
    except ImportError:
        print("scapy 未安装，请先: pip install scapy")
        return []

    try:
        packets = rdpcap(pcap_file)
    except Exception as e:
        print(f"Error loading PCAP: {e}")
        return []

    payloads = []
    for i, pkt in enumerate(packets):
        if IP in pkt and UDP in pkt:
            payload = bytes(pkt[UDP].payload)
            if len(payload) < 16:
                continue
            service_id = struct.unpack(">H", payload[0:2])[0]
            method_id = struct.unpack(">H", payload[2:4])[0]
            msg_type = payload[12]
            if service_id == SERVICE_ID and method_id == EVENT_ID and msg_type == 0x02:
                payloads.append(payload[16:])  # 事件载荷
                print(f"PCAP #{len(payloads)}: service=0x{service_id:04X} event=0x{method_id:04X} body={len(payload)-16}B")

    print(f"Loaded {len(payloads)} SOME/IP notifications from PCAP")
    return payloads


def main():
    print("ArHud SOME/IP Server - Python (fixed)")
    print(f"Service ID: 0x{SERVICE_ID:04X}, Event ID: 0x{EVENT_ID:04X}, Group: 0x{EVENT_GROUP:04X}")

    pcap_data = []
    if os.path.exists(PCAP_FILE):
        pcap_data = load_pcap_data(PCAP_FILE)
    else:
        print(f"Warning: PCAP file not found: {PCAP_FILE}")

    # 以官方模板为基准（模板含全部必需键），只做增量修改
    configuration = vSOMEIP.configuration()
    configuration["unicast"] = "127.0.0.1"
    configuration["applications"].append({"name": APPLICATION_NAME, "id": SERVER_ID})
    configuration["services"].append({
        "service": SERVICE_ID,
        "instance": INSTANCE_ID,
        "unreliable": SERVICE_PORT,
    })
    # 注意键名是 "enable"（原报告写成 "enabled"，该键被 vsomeip 忽略）
    configuration["service-discovery"]["enable"] = "true"

    print("正在创建应用...")
    app = vSOMEIP(APPLICATION_NAME, SERVER_ID, INSTANCE_ID,
                  configuration=configuration, force=True)
    app.create()

    # 提供实例
    print(f"提供服务: Service = 0x{SERVICE_ID:04X}, Instance = 0x{INSTANCE_ID:04X}")
    app.offer()

    print("启动应用...")
    app.start()

    # 提供事件（官方示例在 start() 之后 offer 事件）
    print(f"注册事件: Event = 0x{EVENT_ID:04X}, Group = 0x{EVENT_GROUP:04X}")
    app.offer(events=[EVENT_ID], group=EVENT_GROUP)

    print("服务端已启动，开始回放 PCAP 数据...")
    packet_num = 0
    try:
        while True:
            if pcap_data:
                for data in pcap_data:
                    packet_num += 1
                    print(f"notify #{packet_num}: event=0x{EVENT_ID:04X}, data len={len(data)}")
                    app.notify(EVENT_ID, bytearray(data))
                    time.sleep(0.1)  # 100ms 间隔
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        app.stop()
        print("服务端已停止")


if __name__ == "__main__":
    main()
