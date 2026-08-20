#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 AR-HUD 23 事件 SOME/IP 通知 pcap（与 hud 程序发送的字节完全一致）
========================================================================
- 每个 (service, event) 一帧（--rounds 可多轮），UDP 源端口 = 注册表中的服务端口
- 载荷 = hud_data_types.make_sample(kind, counter)（大端序列化，counter 从 1 递增）
- SOME/IP 头：大端（service, method=event, length, request_id, ver 0x01, iface 0x01, type 0x02, ret 0）
- 可选噪声帧（其它服务/垃圾 UDP）验证解码过滤

用法：
  python3 make_hud_pcap.py testdata/test_arhud_hud_23events.pcap --rounds 1 [--noise]

依赖：scapy
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hud_data_types import HUD_EVENTS, make_sample

MSG_TYPE_NOTIFICATION = 0x02
CLIENT_ID_DEFAULT = 0x1443   # 文档应用 ID


def someip_notification(service: int, event: int, payload: bytes,
                        client: int, session: int) -> bytes:
    length = 4 + len(payload)                 # RequestID(4) + payload
    request_id = ((client & 0xFFFF) << 16) | (session & 0xFFFF)
    header = struct.pack(">HHIIBBBB", service, event, length, request_id,
                         0x01, 0x01, MSG_TYPE_NOTIFICATION, 0x00)
    return header + payload


def main():
    ap = argparse.ArgumentParser(description="生成 AR-HUD 23 事件 SOME/IP pcap")
    ap.add_argument("output", help="输出 pcap 路径")
    ap.add_argument("--rounds", type=int, default=1, help="每事件帧数（默认 1）")
    ap.add_argument("--client", type=lambda s: int(s, 0), default=CLIENT_ID_DEFAULT)
    ap.add_argument("--dst-port", type=int, default=40000)
    ap.add_argument("--noise", action="store_true", help="混入干扰帧")
    args = ap.parse_args()

    from scapy.all import Ether, IP, UDP, wrpcap

    frames = []
    summary = []
    counter = 0
    for r in range(args.rounds):
        for svc, inst, event, name, group, port, kind in HUD_EVENTS:
            counter += 1
            payload = make_sample(kind, counter)
            raw = someip_notification(svc, event, payload,
                                      client=args.client, session=counter)
            pkt = Ether() / IP(src="192.168.195.11", dst="192.168.195.11") \
                / UDP(sport=port, dport=args.dst_port + (counter % 100)) / raw
            frames.append(pkt)
            summary.append(
                f"svc=0x{svc:04X} event=0x{event:04X} {name:34s} "
                f"port={port} payload={len(payload):4d}B counter={counter}")

    if args.noise:
        # 其它服务 0xFFFF（SD 风格，应被过滤）
        raw = someip_notification(0xFFFF, 0x8100, b"\x00" * 16,
                                  client=args.client, session=0xFFFF)
        frames.append(Ether() / IP(src="192.168.195.11", dst="224.0.2.4")
                      / UDP(sport=30490, dport=30490) / raw)
        summary.append("噪声: svc=0xFFFF（应被过滤）")
        # 垃圾 UDP
        frames.append(Ether() / IP(src="192.168.195.11", dst="192.168.195.11")
                      / UDP(sport=9999, dport=39999) / b"garbage-not-someip!")
        summary.append("噪声: 垃圾 UDP（应被过滤）")

    wrpcap(args.output, frames)
    print(f"已生成: {args.output}  ({len(frames)} 帧, {len(HUD_EVENTS) * args.rounds} 条通知)")
    for line in summary:
        print("  " + line)


if __name__ == "__main__":
    main()
