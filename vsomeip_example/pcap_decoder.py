#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCAP 解码器：从 pcap 文件中提取 SOME/IP 事件通知并反序列化
=========================================================
流程：pcap → UDP payload → SOME/IP 头解析 → 事件载荷 → NewLaneLineDataNotify

SOME/IP 头（16 字节）：
    bytes  0-3   Message ID  = Service ID(2) + Method ID(2)
    bytes  4-7   Length      = Request ID(4) + Payload 的长度
    bytes  8-11  Request ID  = Client ID(2) + Session ID(2)
    byte   12    Protocol Version   (0x01)
    byte   13    Interface Version
    byte   14    Message Type       (0x02 = NOTIFICATION)
    byte   15    Return Code
    bytes 16+    Payload            （事件载荷，即 ArHud 序列化结构体）

用法：
    from pcap_decoder import decode_pcap
    events = decode_pcap("out.pcap")

    # 命令行：
    python3 pcap_decoder.py out.pcap            # 解码并打印统计
    python3 pcap_decoder.py out.pcap --dump 5   # 打印前 5 个 UDP 载荷的原始 HEX
"""

import argparse
import struct
from dataclasses import dataclass
from typing import List, Optional

from arhud_data_types import NewLaneLineDataNotify

# 与真实客户端（C++/Python）对齐的常量
SERVICE_ID = 0x000C
EVENT_ID = 0x8003          # NewLaneLineDataNotify
MSG_TYPE_NOTIFICATION = 0x02

# 反序列化 sanity 检查上限（防止把其它协议的报文误解析成 ArHud 数据）
MAX_LANE_COUNT = 64
MAX_POINT_COUNT = 256


class SomeIpMessage:
    """SOME/IP 报文（只解析头部 + 载荷）"""

    HEADER_SIZE = 16
    __slots__ = ("service_id", "method_id", "length", "request_id",
                 "protocol_version", "interface_version", "message_type",
                 "return_code", "payload", "raw")

    def __init__(self, service_id, method_id, length, request_id,
                 protocol_version, interface_version, message_type,
                 return_code, payload, raw):
        self.service_id = service_id
        self.method_id = method_id
        self.length = length
        self.request_id = request_id
        self.protocol_version = protocol_version
        self.interface_version = interface_version
        self.message_type = message_type
        self.return_code = return_code
        self.payload = payload
        self.raw = raw

    @classmethod
    def parse(cls, raw: bytes) -> Optional["SomeIpMessage"]:
        """尝试把一段字节解析为 SOME/IP 报文；格式不合法返回 None"""
        if len(raw) < cls.HEADER_SIZE:
            return None
        service_id, method_id = struct.unpack_from(">HH", raw, 0)
        (length,) = struct.unpack_from(">I", raw, 4)
        (request_id,) = struct.unpack_from(">I", raw, 8)
        protocol_version = raw[12]
        interface_version = raw[13]
        message_type = raw[14]
        return_code = raw[15]

        # Length 字段 = Request ID(4) + Payload 的长度
        payload_len = length - 4
        if payload_len < 0 or cls.HEADER_SIZE + payload_len > len(raw):
            return None
        payload = raw[cls.HEADER_SIZE:cls.HEADER_SIZE + payload_len]
        return cls(service_id, method_id, length, request_id,
                   protocol_version, interface_version, message_type,
                   return_code, payload, raw)

    def __str__(self) -> str:
        return (f"SOME/IP[svc=0x{self.service_id:04X} method=0x{self.method_id:04X} "
                f"type=0x{self.message_type:02X} len={len(self.payload)}]")


@dataclass
class DecodedEvent:
    """一条解码出的事件：原始载荷 + 可选的反序列化结果"""
    index: int                        # pcap 包序号
    payload: bytes                    # 事件载荷（SOME/IP payload 或 raw）
    notify: Optional[NewLaneLineDataNotify] = None   # 反序列化结果
    error: Optional[str] = None       # 反序列化失败原因
    source: str = "someip"            # "someip" | "raw"

    def __str__(self) -> str:
        head = f"pkt#{self.index} [{self.source}] payload={len(self.payload)}B"
        if self.notify is not None:
            return head + "\n    " + str(self.notify).replace("\n", "\n    ")
        return head + f" 解析失败: {self.error}"


def _deserialize(payload: bytes) -> tuple:
    """反序列化载荷；返回 (notify, error)。带 sanity 检查。"""
    try:
        notify = NewLaneLineDataNotify.from_bytes(payload)
        if notify.lane_count > MAX_LANE_COUNT:
            return None, f"lane_count={notify.lane_count} 超出合理范围"
        for lane in notify.lanes:
            if len(lane.points) > MAX_POINT_COUNT:
                return None, f"lane[{lane.lane_id}] point_count={len(lane.points)} 超出合理范围"
        return notify, None
    except (struct.error, IndexError) as e:
        return None, f"反序列化异常: {e}"


def decode_udp_payloads(udp_payloads: List[bytes],
                        service_id: int = SERVICE_ID,
                        event_id: int = EVENT_ID) -> List[DecodedEvent]:
    """
    从 UDP 载荷列表中解码 SOME/IP 事件通知（decode_pcap 的核心，独立出来便于单测）。

    策略：
      1) 严格模式：解析 SOME/IP 头，只接受 本服务 + 本事件 + NOTIFICATION 的报文；
      2) 若严格模式一条都没匹配到，退回 raw 模式：把每个 UDP 载荷直接当事件载荷尝试反序列化
         （用于 pcap 里是裸结构体、而非完整 SOME/IP 报文的情况）。
    """
    # ---- 严格模式 ----
    events: List[DecodedEvent] = []
    for i, raw in enumerate(udp_payloads):
        msg = SomeIpMessage.parse(raw)
        if (msg is not None and msg.message_type == MSG_TYPE_NOTIFICATION
                and msg.service_id == service_id and msg.method_id == event_id):
            ev = DecodedEvent(index=i, payload=msg.payload, source="someip")
            ev.notify, ev.error = _deserialize(msg.payload)
            events.append(ev)

    if events:
        print(f"[decode] 严格模式匹配到 {len(events)} 条事件通知")
        return events

    # ---- raw 模式（严格模式无结果时）----
    # 只对"根本不是 SOME/IP 报文"的载荷做裸解析；能解析成 SOME/IP 但
    # 服务/方法不匹配的，属于其它服务的流量，直接跳过。
    print("[decode] 严格 SOME/IP 未匹配，尝试把非 SOME/IP 的 UDP 载荷直接当事件载荷解析...")
    for i, raw in enumerate(udp_payloads):
        if SomeIpMessage.parse(raw) is not None:
            continue  # 是合法的 SOME/IP 报文（但服务/方法不匹配）→ 跳过
        ev = DecodedEvent(index=i, payload=raw, source="raw")
        ev.notify, ev.error = _deserialize(raw)
        if ev.notify is not None:
            events.append(ev)
        else:
            # 无法解析的报文记录但不进入结果（保持结果干净）
            if i < 3:
                print(f"  [skip] pkt#{i} 无法解析: {ev.error}  HEX={raw[:32].hex().upper()}")
    print(f"[decode] raw 模式解析出 {len(events)} 条")
    return events


def decode_pcap(pcap_file: str,
                service_id: int = SERVICE_ID,
                event_id: int = EVENT_ID) -> List[DecodedEvent]:
    """读取 pcap 并解码其中的 SOME/IP 事件通知（见 decode_udp_payloads）。"""
    try:
        from scapy.all import rdpcap, IP, UDP
    except ImportError:
        raise RuntimeError("需要 scapy：pip install scapy")

    packets = rdpcap(pcap_file)
    udp_payloads = [bytes(pkt[UDP].payload) for pkt in packets if IP in pkt and UDP in pkt]
    print(f"[pcap] {len(packets)} 包, 其中 {len(udp_payloads)} 个 UDP 载荷")
    return decode_udp_payloads(udp_payloads, service_id, event_id)


def dump_payloads(pcap_file: str, count: int) -> None:
    """打印前 count 个 UDP 载荷的原始字节，用于排查 pcap 的实际格式"""
    from scapy.all import rdpcap, IP, UDP
    packets = rdpcap(pcap_file)
    shown = 0
    for i, pkt in enumerate(packets):
        if IP in pkt and UDP in pkt:
            raw = bytes(pkt[UDP].payload)
            print(f"pkt#{i} UDP payload {len(raw)}B: {raw[:64].hex().upper()}")
            msg = SomeIpMessage.parse(raw)
            if msg is not None:
                print(f"    -> {msg}")
            shown += 1
            if shown >= count:
                break


def main():
    ap = argparse.ArgumentParser(description="解码 pcap 中的 ArHud SOME/IP 事件")
    ap.add_argument("pcap", help="pcap 文件路径")
    ap.add_argument("--dump", type=int, metavar="N", default=0,
                    help="打印前 N 个 UDP 载荷 HEX 后退出（排查格式用）")
    ap.add_argument("--service", type=lambda s: int(s, 0), default=SERVICE_ID)
    ap.add_argument("--event", type=lambda s: int(s, 0), default=EVENT_ID)
    args = ap.parse_args()

    if args.dump:
        dump_payloads(args.pcap, args.dump)
        return

    events = decode_pcap(args.pcap, args.service, args.event)
    print(f"\n共解码 {len(events)} 条事件:")
    for ev in events[:10]:
        print("  -", ev)
    if len(events) > 10:
        print(f"  ... 其余 {len(events) - 10} 条略")


if __name__ == "__main__":
    main()
