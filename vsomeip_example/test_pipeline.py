#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端回归测试：pcap 生成 → 解码 → 反序列化 → 重新序列化 → 服务端数据准备
==========================================================================
不依赖 vsomeip 运行时（vsomeip 部分用桩模块替换），可在任意机器上运行：

    pip install scapy
    python3 test_pipeline.py

覆盖：
  1. arhud_data_types 序列化/反序列化字节级往返
  2. pcap 严格 SOME/IP 解码（只取 本服务+本事件+NOTIFICATION，过滤其它流量）
  3. pcap raw 模式回退（裸结构体载荷）
  4. server.prepare_payloads：解码 → 反序列化 → 重新序列化（服务端真正发送的字节）
"""

import os
import struct
import sys
import tempfile

# ---------- 用桩模块替换 vsomeip，仅用于让 server.py 可导入 ----------
import types

_STUB = types.ModuleType("vsomeip_py.vsomeip")

class _StubVSomeIP:
    @staticmethod
    def configuration():
        return {
            "unicast": "127.0.0.1",
            "applications": [],
            "services": [],
            "clients": [],
            "service-discovery": {"enable": "true"},
        }

_STUB.vSOMEIP = _StubVSomeIP
_PKG = types.ModuleType("vsomeip_py")
_PKG.__path__ = []
sys.modules["vsomeip_py"] = _PKG
sys.modules["vsomeip_py.vsomeip"] = _STUB

from arhud_data_types import (LaneLineData, LaneLinePoint, LaneLineType,
                              NewLaneLineDataNotify, make_sample_notify)
import endian
from pcap_decoder import (MSG_TYPE_NOTIFICATION, SERVICE_ID, EVENT_ID,
                          SomeIpMessage, decode_pcap, decode_udp_payloads)
import server


# ===================== 工具 =====================

def someip_notification(service, method, payload, client_id=0x1003, session=0x0001):
    """构造一条 SOME/IP NOTIFICATION 报文（UDP 载荷）"""
    header = struct.pack(">HHIIBBBB", service, method, 4 + len(payload),
                         (client_id << 16) | session,
                         0x01, 0x01, MSG_TYPE_NOTIFICATION, 0x00)
    return header + payload


def make_lanes(n_points1=3, n_points2=2):
    """构造两份车道线数据"""
    return [
        LaneLineData(lane_type=LaneLineType.SOLID, lane_id=1,
                     quality=0.95, confidence=0.98,
                     points=[LaneLinePoint(0.0, 0.0, 0.0),
                             LaneLinePoint(1.0, 2.0, 0.0),
                             LaneLinePoint(2.0, 4.0, 0.0)][:n_points1]),
        LaneLineData(lane_type=LaneLineType.DASHED, lane_id=2,
                     quality=0.88, confidence=0.91,
                     points=[LaneLinePoint(0.0, 3.5, 0.0),
                             LaneLinePoint(1.0, 5.5, 0.0)][:n_points2]),
    ]


def build_pcap(path, packets):
    """packets: [(ip_src, ip_dst, udp_payload)] -> 写入 pcap"""
    from scapy.all import Ether, IP, UDP, wrpcap
    frames = []
    for i, (src, dst, payload) in enumerate(packets):
        frames.append(Ether() / IP(src=src, dst=dst) / UDP(sport=40000 + i, dport=51402) / payload)
    wrpcap(path, frames)


# ===================== 用例 =====================

def test_round_trip():
    n = make_sample_notify()
    buf = n.to_bytes()
    n2 = NewLaneLineDataNotify.from_bytes(buf)
    assert n2.to_bytes() == buf, "round-trip 字节不一致"
    print(f"[PASS] 1. 序列化/反序列化往返一致 ({len(buf)}B)")


def test_endianness():
    """字节序：大端(网络序)序列化与主机端序无关 —— 字节精确断言在任何主机上都必须成立"""
    # 端序工具自测（机器端序识别 + 大端编解码固定字节）
    msg = endian.self_test()
    assert "大端(网络序)编解码自测通过" in msg

    # struct '>' 显式大端：固定字节（无论本机是小端还是大端，输出必须完全一致）
    assert endian.pack_u16(0x0102) == b"\x01\x02"
    assert endian.pack_u32(0x01020304) == b"\x01\x02\x03\x04"
    assert endian.pack_u64(0x0102030405060708) == bytes(range(1, 9))
    assert endian.unpack_u16(b"\x12\x34") == 0x1234
    assert endian.unpack_u32(b"\xDE\xAD\xBE\xEF") == 0xDEADBEEF

    # ArHud 结构体大端布局：version=0x0001, timestamp=0x11223344 在字节 0..5 中可见
    n = make_sample_notify()
    buf = n.to_bytes()
    assert buf[0] == 0x00 and buf[1] == 0x01, "version 应为大端 0x0001"
    assert buf[2:6] == b"\x11\x22\x33\x44", "timestamp 应为大端 0x11223344"

    # 往返一致（任意端序主机）
    assert NewLaneLineDataNotify.from_bytes(buf).to_bytes() == buf
    print(f"[PASS] 5. 字节序: 大端(网络序)输出与主机端序无关 (本机: {endian.detect_endian()})")


def test_strict_decode(tmp):
    # 5 条本服务事件 + 2 条其它服务通知 + 1 条垃圾 UDP
    events_data = []
    for i in range(5):
        n = NewLaneLineDataNotify(version=1, timestamp=0x1000 + i, lane_count=2,
                                  lanes=make_lanes(3, 2))
        events_data.append(n)
    packets = [("10.0.0.1", "10.0.0.2",
                someip_notification(SERVICE_ID, EVENT_ID, n.to_bytes(), session=i + 1))
               for i, n in enumerate(events_data)]
    packets += [("10.0.0.1", "10.0.0.2",
                 someip_notification(0x9999, 0x9999, b"\x00" * 20))]
    packets += [("10.0.0.1", "10.0.0.2",
                 someip_notification(0x000C, 0x9001, b"\x01" * 30))]  # 同服务其它方法
    packets += [("10.0.0.3", "10.0.0.4", b"garbage-not-someip-xxxxxx")]
    pcap = os.path.join(tmp, "test_strict.pcap")
    build_pcap(pcap, packets)

    events = decode_pcap(pcap)
    assert len(events) == 5, f"期望 5 条，实际 {len(events)}"
    for ev, n in zip(events, events_data):
        assert ev.source == "someip"
        assert ev.notify is not None
        assert ev.notify.to_bytes() == n.to_bytes(), "解码后重新序列化字节不一致"
    print("[PASS] 2. pcap 严格 SOME/IP 解码: 5/5 条命中，其它服务/方法/垃圾流量被过滤")


def test_raw_fallback(tmp):
    payloads = [make_sample_notify().to_bytes(),
                NewLaneLineDataNotify(version=1, timestamp=0x2222, lane_count=1,
                                      lanes=make_lanes(1, 0)).to_bytes(),
                NewLaneLineDataNotify(version=1, timestamp=0x3333, lane_count=2,
                                      lanes=make_lanes(2, 2)).to_bytes()]
    packets = [("10.0.0.1", "10.0.0.2", p) for p in payloads]
    packets.append(("10.0.0.1", "10.0.0.2", b"this-is-not-arhud-data-please-skip"))
    pcap = os.path.join(tmp, "test_raw.pcap")
    build_pcap(pcap, packets)

    events = decode_pcap(pcap)
    assert len(events) == 3, f"raw 回退期望 3 条，实际 {len(events)}"
    assert all(e.source == "raw" and e.notify is not None for e in events)
    assert events[0].notify.to_bytes() == payloads[0]
    print("[PASS] 3. pcap raw 模式回退: 3/3 条裸结构体命中，垃圾数据被跳过")


def test_prepare_payloads(tmp):
    # 有 pcap：解码 → 反序列化 → 重新序列化
    n = NewLaneLineDataNotify(version=1, timestamp=0xABCD, lane_count=2, lanes=make_lanes(3, 2))
    pcap = os.path.join(tmp, "test_prepare.pcap")
    build_pcap(pcap, [("10.0.0.1", "10.0.0.2",
                       someip_notification(SERVICE_ID, EVENT_ID, n.to_bytes()))])
    payloads = server.prepare_payloads(pcap)
    assert len(payloads) == 1
    out_bytes, notify = payloads[0]
    assert out_bytes == n.to_bytes(), "服务端发送的字节与原始序列化不一致"
    assert notify.to_bytes() == out_bytes
    print(f"[PASS] 4a. server.prepare_payloads(pcap): 1 条，发送 {len(out_bytes)}B，字节一致")

    # 无 pcap：内置示例数据兜底
    payloads2 = server.prepare_payloads(os.path.join(tmp, "no-such-file.pcap"))
    assert len(payloads2) == 1 and payloads2[0][1] is not None
    print(f"[PASS] 4b. server.prepare_payloads(无pcap): 内置示例兜底 {len(payloads2[0][0])}B")


def main():
    print("=" * 70)
    print("ArHud SOME/IP 示例 端到端回归测试")
    print("=" * 70)
    tmp = tempfile.mkdtemp(prefix="arhud_test_")
    try:
        test_round_trip()
        test_strict_decode(tmp)
        test_raw_fallback(tmp)
        test_prepare_payloads(tmp)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + "=" * 70)
    print("全部测试通过 ✔")
    print("=" * 70)


if __name__ == "__main__":
    main()
