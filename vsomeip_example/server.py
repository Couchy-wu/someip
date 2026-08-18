#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArHud SOME/IP 服务端（基于 vsomeip_py，标准 vsomeip 服务）
==========================================================
完整链路：pcap 解码 → 反序列化 → 序列化 → app.notify() 发送事件

- 本服务端是标准 vsomeip 服务：任何 vsomeip 客户端（包括你项目里
  已经写好的 C++ 客户端）都可以订阅并收到事件 0x8003。
- 事件载荷 = NewLaneLineDataNotify.to_bytes()，即 C++ 结构体
  stNewLanelineDataNotify 的内存布局（大端）。
- 没有 pcap 文件时自动使用内置示例数据，保证链路可跑通。

运行：python3 server.py [out.pcap]
"""

import os
import sys
import time

from arhud_data_types import NewLaneLineDataNotify, make_sample_notify
from pcap_decoder import DecodedEvent, decode_pcap

try:
    from vsomeip_py.vsomeip import vSOMEIP
except ImportError:  # 兼容某些 fork（模块名 vsomeip）
    import vsomeip
    vSOMEIP = vsomeip.vSOMEIP

# ---------- 与真实客户端对齐的关键常量（必须与客户端完全一致） ----------
APPLICATION_NAME = "arhud_server"
SERVER_ID = 0x1201          # 本应用 client id（路由管理器在哪个进程无所谓，服务端先启动即可）
SERVICE_ID = 0x000C
INSTANCE_ID = 0x000C
EVENT_ID = 0x8003           # NewLaneLineDataNotify
EVENT_GROUP = 0x01          # 事件组，必须等于客户端 subscribe 的事件组
SERVICE_PORT = 51402        # 服务 UDP 端口

# 回放节奏（可用环境变量覆盖，便于自动化测试）
SEND_INTERVAL_S = float(os.environ.get("ARHUD_INTERVAL", "0.1"))  # 每条事件之间的间隔
LOOP_DELAY_S = 1.0          # 整轮回放完成后的间隔
SD_ENABLE = os.environ.get("ARHUD_SD", "true")                     # 服务发现开关
SEND_COUNT = int(os.environ.get("ARHUD_SEND_COUNT", "0"))          # 发送条数上限，0=无限


def prepare_payloads(pcap_file: str):
    """
    第 1 步：解码 pcap → [(payload_bytes, NewLaneLineDataNotify|None), ...]
    - pcap 存在：解码 → 反序列化成功则【重新序列化】（保证发送干净、规范的结构体字节）；
      反序列化失败的报文跳过并提示。
    - pcap 不存在：使用内置示例数据，保证链路可跑通。
    纯逻辑，不依赖 vsomeip，可独立单测。
    """
    payloads = []  # [(bytes, NewLaneLineDataNotify|None)]
    if os.path.exists(pcap_file):
        events = decode_pcap(pcap_file)
        print(f"[decode] 解码出 {len(events)} 条事件")
        for ev in events[:3]:
            print("  -", ev)
        for ev in events:
            if ev.notify is not None:
                # 反序列化成功：重新序列化（保证发送的是干净、规范的结构体字节）
                payloads.append((ev.notify.to_bytes(), ev.notify))
            else:
                print(f"  [skip] pkt#{ev.index} 反序列化失败({ev.error})，已跳过")
    else:
        print(f"[decode] pcap 不存在({pcap_file})，使用内置示例数据演示")
        sample = make_sample_notify()
        payloads.append((sample.to_bytes(), sample))

    if not payloads:
        print("[error] 没有可发送的数据，退出")
        return []
    print(f"[ready] 共 {len(payloads)} 条数据待回放")
    return payloads


def main():
    pcap_file = os.environ.get("ARHUD_PCAP") or (sys.argv[1] if len(sys.argv) > 1 else "out.pcap")
    print(f"ArHud SOME/IP Server (vsomeip_py)  service=0x{SERVICE_ID:04X} "
          f"event=0x{EVENT_ID:04X} group=0x{EVENT_GROUP:04X}  sd={SD_ENABLE}")

    # ---------- 1) pcap 解码 + 反序列化 ----------
    payloads = prepare_payloads(pcap_file)
    if not payloads:
        return

    # ---------- 2) 创建 vsomeip 应用 ----------
    # 以官方模板为基准（模板含全部必需键），只做增量修改
    configuration = vSOMEIP.configuration()
    configuration["unicast"] = "127.0.0.1"
    # 注意: applications[].id 是【客户端 ID】(0x1201)；构造函数第 2 个参数是【服务 ID】(0x000C)。
    # vsomeip_py 的 vSOMEIP(name, id, instance) 中 id 是服务 ID（offer/request 用它），
    # 客户端 ID 由配置 applications[].id 决定。两者可以不同！
    configuration["applications"].append({"name": APPLICATION_NAME, "id": SERVER_ID})
    configuration["services"].append({
        "service": SERVICE_ID,
        "instance": INSTANCE_ID,
        "unreliable": SERVICE_PORT,
    })
    # 注意键名是 "enable"（不是 "enabled"！后者会被 vsomeip 忽略）
    configuration["service-discovery"]["enable"] = SD_ENABLE

    app = vSOMEIP(APPLICATION_NAME, SERVICE_ID, INSTANCE_ID,
                  configuration=configuration, force=True)
    app.create()

    # ---------- 3) 提供服务与事件 ----------
    app.offer()                                  # offer_service
    app.start()                                  # 启动 io 线程
    app.offer(events=[EVENT_ID], group=EVENT_GROUP)  # offer_event（官方示例在 start 之后）

    print("服务端已就绪，等待客户端订阅...（Ctrl+C 退出）\n")

    # ---------- 4) 循环回放 ----------
    packet_num = 0
    try:
        while True:
            for payload, notify in payloads:
                packet_num += 1
                print(f"[send] #{packet_num} event=0x{EVENT_ID:04X} "
                      f"payload={len(payload)}B  {payload.hex().upper()}")
                if notify is not None:
                    print("       " + str(notify).replace("\n", "\n       "))
                app.notify(EVENT_ID, bytearray(payload))
                if SEND_COUNT and packet_num >= SEND_COUNT:
                    print(f"[done] 已发送 {packet_num} 条，退出（ARHUD_SEND_COUNT 限制）")
                    return
                time.sleep(SEND_INTERVAL_S)
            time.sleep(LOOP_DELAY_S)
    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        app.stop()
        print("服务端已停止")


if __name__ == "__main__":
    main()
