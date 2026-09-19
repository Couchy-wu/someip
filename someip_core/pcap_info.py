# -*- coding: utf-8 -*-
"""someip_core.pcap_info —— pcap 解析（SOME/IP-TP 分片重组）

用途：在界面上展示"这份 pcap 里有哪些服务/事件、各多少条、载荷大小范围"，
并在真正回放前做一次可行性检查（文件是否存在、是否有可回放的通知）。

解析规则（与原 C++ 服务端 hud_pcap_huifang_server.cpp / pcap_replay_tp.py 对齐）：
    · Ethernet(14B) / VLAN 0x8100(18B) / 0x88A8(22B) / IPv4 / UDP
    · SOME/IP 头 16B：service / method(event) / length / client / session /
      version / interface_version / message_type / return_code
    · message_type 0x02 = Notification → 直接取载荷（length - 8）
    · message_type 0x22 = SOME/IP-TP 分片 → 4 字节 TP 头
      （bit0 = MoreSegments，bits1..31 = **字节偏移**），按 (service, method, session) 重组
    · 跳过 SOME/IP-SD（service=0xFFFF, method=0x8100）

注意：真正的回放由 C++ 库完成（它在内部做同样的 TP 重组）；
本模块只做"展示与预检"，不参与实际发包，因此可用纯 Python 在任意平台运行。
"""
from __future__ import annotations

import struct
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# pcap 全局头 magic（含大小端两种、微秒/纳秒两种）
_PCAP_MAGICS = {
    b"\xd4\xc3\xb2\xa1": "<", b"\xa1\xb2\xc3\xd4": ">",
    b"\x4d\x3c\xb2\xa1": "<", b"\xa1\xb2\x3c\x4d": ">",
}


@dataclass
class EventStat:
    """单个 (service, event) 的统计。"""

    service: int
    event: int
    count: int = 0
    min_len: int = 0
    max_len: int = 0
    tp_segments: int = 0

    @property
    def key(self) -> str:
        return f"0x{self.service:04X}:0x{self.event:04X}"

    def describe(self) -> str:
        return (f"{self.key}  {self.count} 条  载荷 {self.min_len}~{self.max_len} 字节"
                + (f"  (TP 分片 {self.tp_segments})" if self.tp_segments else ""))


@dataclass
class PcapSummary:
    """一份 pcap 的解析结果摘要。"""

    path: str
    total_packets: int = 0
    sd_packets: int = 0
    plain_notifications: int = 0
    tp_segments: int = 0
    others: int = 0
    events: dict[tuple[int, int], EventStat] = field(default_factory=dict)
    # {(service, event): [payload, ...]}（TP 已重组；供需要自行处理载荷的场景使用）
    payloads: dict[tuple[int, int], list[bytes]] = field(default_factory=dict)
    error: str | None = None

    @property
    def replayable(self) -> int:
        """可回放的通知条数（TP 重组后按事件计）。"""
        return sum(st.count for st in self.events.values())

    def describe(self) -> str:
        if self.error:
            return f"pcap 解析失败：{self.error}"
        return (f"总包 {self.total_packets}｜SD {self.sd_packets}｜通知 {self.plain_notifications}"
                f"｜TP 分片 {self.tp_segments}｜其他 {self.others}"
                f"｜可回放事件 {len(self.events)} 种 / {self.replayable} 条")


def decode_pcap(pcap_file: str | Path, verbose: bool = False) -> dict[tuple[int, int], list[bytes]]:
    """解析 pcap → {(service, event): [payload, ...]}（TP 已重组）。

    解析失败（文件不存在/格式不符）时返回空 dict，详细原因见 parse_summary()。
    """
    return parse_summary(pcap_file, verbose=verbose).payloads


def parse_summary(pcap_file: str | Path, verbose: bool = False) -> PcapSummary:
    """解析 pcap 并返回摘要（含每个事件的载荷列表，见 .payloads）。"""
    path = Path(pcap_file)
    summary = PcapSummary(path=str(path))
    if not path.is_file():
        summary.error = f"文件不存在：{path}"
        return summary

    payloads: dict[tuple[int, int], list[bytes]] = defaultdict(list)
    tp_parts: dict[tuple[int, int, int], list[tuple[int, int, bytes]]] = defaultdict(list)

    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            endian = _PCAP_MAGICS.get(magic)
            if endian is None:
                summary.error = f"不是标准 pcap 文件（magic={magic!r}）"
                return summary
            f.read(20)                       # 全局头剩余部分（24 - 4）
            while True:
                rec = f.read(16)
                if len(rec) < 16:
                    break
                _sec, _usec, incl_len, _orig = struct.unpack(endian + "IIII", rec)
                data = f.read(incl_len)
                if len(data) < incl_len:
                    break
                summary.total_packets += 1
                _parse_one(data, summary, payloads, tp_parts)
    except OSError as exc:
        summary.error = f"读取失败：{exc}"
        return summary

    # ---------------- TP 分片重组（按 offset 排序拼接） ----------------
    for (svc, evt, _sess), parts in tp_parts.items():
        parts.sort(key=lambda p: p[0])
        buf = b"".join(seg for _off, _more, seg in parts)
        if buf:
            payloads[(svc, evt)].append(buf)

    # ---------------- 统计 ----------------
    for (svc, evt), pls in payloads.items():
        sizes = [len(p) for p in pls]
        summary.events[(svc, evt)] = EventStat(
            service=svc, event=evt, count=len(pls),
            min_len=min(sizes), max_len=max(sizes),
            tp_segments=sum(1 for k in tp_parts if k[0] == svc and k[1] == evt))
    summary.payloads = dict(payloads)

    if verbose:
        print(f"[pcap] {summary.describe()}")
        for st in sorted(summary.events.values(), key=lambda s: (s.service, s.event)):
            print(f"[pcap]   {st.describe()}")
    return summary


def _parse_one(data: bytes, summary: PcapSummary,
               payloads: dict, tp_parts: dict) -> None:
    """解析单个以太网帧（就地更新统计与载荷表）。"""
    off = 14
    if len(data) >= 14:
        ethertype = struct.unpack(">H", data[12:14])[0]
        if ethertype == 0x8100:
            off = 18
        elif ethertype == 0x88A8:
            off = 22
    if len(data) < off + 20 or (data[off] >> 4) != 4 or data[off + 9] != 17:
        summary.others += 1
        return
    ihl = (data[off] & 0x0F) * 4
    payload = data[off + ihl + 8:]           # 跳过 UDP 头（8 字节）
    if len(payload) < 16:
        summary.others += 1
        return

    svc, method, length, _client, session, ver, _iver, mtype, _rc = \
        struct.unpack(">HHIHHBBBB", payload[:16])
    if svc == 0xFFFF and method == 0x8100:   # SOME/IP-SD
        summary.sd_packets += 1
        return
    if ver != 0x01:
        summary.others += 1
        return

    if mtype == 0x02:                        # Notification
        plen = max(0, length - 8)
        payloads[(svc, method)].append(payload[16:16 + plen])
        summary.plain_notifications += 1
    elif mtype == 0x22:                      # SOME/IP-TP 分片
        tp_raw = struct.unpack(">I", payload[16:20])[0]
        more = tp_raw & 0x1
        offset = tp_raw & 0xFFFFFFFE
        tp_parts[(svc, method, session)].append((offset, more, payload[20:]))
        summary.tp_segments += 1
    else:
        summary.others += 1
