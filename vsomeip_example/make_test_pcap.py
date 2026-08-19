#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成用于完整测试的 SOME/IP 通知 pcap 文件
==========================================
生成的 pcap 包含：
  - 指定服务/事件的 SOME/IP NOTIFICATION 报文（UDP 单帧），
    载荷 = NewLaneLineDataNotify 序列化字节（timestamp 字段 = 0x1000 + 全局包序号，
    用于测试时断言"客户端收到的内容与 pcap 一致"）
  - 可选"噪声"报文（其它服务的 SOME/IP、同服务其它事件、垃圾 UDP），
    用于验证解码器的过滤逻辑（严格 SOME/IP 模式只取 本服务+本事件+NOTIFICATION）

用法：
  # 单服务（Ubuntu 程序场景：服务 0x000C / 事件 0x8003）
  python3 make_test_pcap.py arhud_ub.pcap --service 0x000C --event 0x8003 --count 6 --noise

  # 多服务（Windows 程序场景：0x000A/0x000B/0x000C，事件 0x8001）
  python3 make_test_pcap.py arhud_win.pcap --services 0x000A,0x000B,0x000C --event 0x8001 --count 3 --noise

依赖：scapy（pip install scapy）
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arhud_data_types import (LaneLineData, LaneLinePoint, LaneLineType,
                              NewLaneLineDataNotify)

MSG_TYPE_NOTIFICATION = 0x02
PROTOCOL_VERSION = 0x01
INTERFACE_VERSION = 0x01


def someip_notification(service: int, event: int, payload: bytes,
                        client: int = 0x1003, session: int = 0x0001) -> bytes:
    """构造一条 SOME/IP NOTIFICATION 报文（16 字节头 + 载荷）"""
    length = 4 + len(payload)                      # RequestID(4) + payload
    request_id = ((client & 0xFFFF) << 16) | (session & 0xFFFF)
    header = struct.pack(">HHIIBBBB", service, event, length, request_id,
                         PROTOCOL_VERSION, INTERFACE_VERSION,
                         MSG_TYPE_NOTIFICATION, 0x00)
    return header + payload


def make_arhud_payload(marker: int) -> bytes:
    """构造 ArHud 载荷：timestamp = 0x1000 + marker，车道数据随 marker 变化"""
    notify = NewLaneLineDataNotify(
        version=1,
        timestamp=0x1000 + marker,
        lane_count=2,
        lanes=[
            LaneLineData(lane_type=LaneLineType.SOLID, lane_id=(marker % 2) + 1,
                         quality=0.90 + marker * 0.01, confidence=0.98,
                         points=[LaneLinePoint(0.0, 0.0, 0.0),
                                 LaneLinePoint(1.0, 2.0, 0.0),
                                 LaneLinePoint(2.0, 4.0, 0.0)]),
            LaneLineData(lane_type=LaneLineType.DASHED, lane_id=(marker % 2) + 2,
                         quality=0.85, confidence=0.91,
                         points=[LaneLinePoint(0.0, 3.5, 0.0),
                                 LaneLinePoint(1.0, 5.5, 0.0)]),
        ],
    )
    return notify.to_bytes()


def build_pcap(path: str, frames, summary_lines) -> None:
    from scapy.all import Ether, IP, UDP, wrpcap
    wrpcap(path, frames)
    print(f"已生成: {path}  ({len(frames)} 帧)")
    for line in summary_lines:
        print("  " + line)


def main():
    ap = argparse.ArgumentParser(description="生成 ArHud SOME/IP 通知测试 pcap")
    ap.add_argument("output", help="输出 pcap 路径")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--service", type=lambda s: int(s, 0), help="单个服务 ID")
    g.add_argument("--services", type=str, help="多个服务 ID，逗号分隔")
    ap.add_argument("--event", type=lambda s: int(s, 0), default=0x8003)
    ap.add_argument("--instance", type=lambda s: int(s, 0), default=0x000C)
    ap.add_argument("--count", type=int, default=6, help="每个服务的通知条数")
    ap.add_argument("--client", type=lambda s: int(s, 0), default=0x1003)
    ap.add_argument("--src-port", type=int, default=51402)
    ap.add_argument("--dst-port", type=int, default=40000)
    ap.add_argument("--noise", action="store_true", help="混入干扰报文（其它服务/事件/垃圾 UDP）")
    args = ap.parse_args()

    services = [args.service] if args.service is not None else \
        [int(x, 0) for x in args.services.split(",") if x.strip()]
    event = args.event

    from scapy.all import Ether, IP, UDP
    frames = []
    summary = []
    marker = 0  # 全局包序号（timestamp 用）

    # 1) 各服务的通知报文
    for si, svc in enumerate(services):
        for i in range(args.count):
            payload = make_arhud_payload(marker)
            raw = someip_notification(svc, event, payload,
                                      client=args.client, session=marker + 1)
            pkt = Ether() / IP(src="10.13.90.164", dst="10.13.90.164") \
                / UDP(sport=args.src_port, dport=args.dst_port + i) / raw
            frames.append(pkt)
            summary.append(
                f"通知: svc=0x{svc:04X} event=0x{event:04X} "
                f"payload={len(payload)}B timestamp=0x{0x1000 + marker:04X}")
            marker += 1

    # 2) 噪声报文（验证解码器过滤）
    if args.noise:
        # 2a) 其它服务（0xFFFF SD 风格）
        other_svc = 0xFFFF if 0xFFFF not in services else 0xFFFF - 1
        raw = someip_notification(other_svc, 0x8100, b"\x00" * 20)
        frames.append(Ether() / IP(src="10.13.90.164", dst="10.13.90.164")
                      / UDP(sport=args.src_port, dport=39999) / raw)
        summary.append(f"噪声: 其它服务 svc=0x{other_svc:04X}（应被过滤）")
        # 2b) 同服务其它事件
        other_event = event + 1
        raw = someip_notification(services[0], other_event, b"\x01" * 20)
        frames.append(Ether() / IP(src="10.13.90.164", dst="10.13.90.164")
                      / UDP(sport=args.src_port, dport=39998) / raw)
        summary.append(f"噪声: 其它事件 event=0x{other_event:04X}（应被过滤）")
        # 2c) 垃圾 UDP
        frames.append(Ether() / IP(src="10.13.90.164", dst="10.13.90.164")
                      / UDP(sport=9999, dport=39997) / b"garbage-not-someip-data!")
        summary.append("噪声: 垃圾 UDP（应被过滤）")

    build_pcap(args.output, frames, summary)


if __name__ == "__main__":
    main()
