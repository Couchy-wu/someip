#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
to_longjie_demo_20250625/out.pcap 解析器（含 SOME/IP-TP 分片重组）
=================================================================
与 C++ 服务端 hud_pcap_huifang_server.cpp 的解析逻辑对齐：
  - Ethernet(14B) / VLAN 0x8100(18B) / IPv4 / UDP
  - SOME/IP 头 16B；message_type 0x02 = Notification
  - message_type 0x22 = SOME/IP-TP 分片：4 字节 TP 头（bit0=MoreSegments，bits1-31=字节偏移）
    按 (service, method, session) 重组为完整载荷
  - 跳过 SOME/IP-SD（service=0xFFFF, method=0x8100）
  - 载荷 = SOME/IP 头之后的部分（0x02: len-8；TP 重组后为完整消息载荷）

输出: {(service_id, event_id): [payload_bytes, ...]}，按出现顺序
"""
import os
import struct
from collections import defaultdict


def decode_pcap_replay(pcap_file: str, verbose: bool = True):
    """解析 pcap，返回 {(svc, event): [payload,...]}（TP 已重组）"""
    replay = defaultdict(list)      # (svc, event) -> [payload, ...]
    tp_parts = defaultdict(list)    # (svc, event, session) -> [(offset, more, seg_payload)]
    n_sd = n_other = n_plain = n_tp = 0

    with open(pcap_file, "rb") as f:
        magic = f.read(4)
        endian = ">" if magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d") else "<"
        f.seek(0)
        f.read(24)  # global header
        while True:
            rh = f.read(16)
            if len(rh) < 16:
                break
            _sec, _usec, incl_len, _orig = struct.unpack(endian + "IIII", rh)
            data = f.read(incl_len)
            if len(data) < incl_len:
                break

            # Ethernet + optional VLAN
            off = 14
            if len(data) >= 14:
                et = struct.unpack(">H", data[12:14])[0]
                if et == 0x8100:
                    off = 18
                elif et == 0x88A8:
                    off = 22
            if len(data) < off + 20 or (data[off] >> 4) != 4 or data[off + 9] != 17:
                n_other += 1
                continue
            ihl = (data[off] & 0x0F) * 4
            pay = data[off + ihl + 8:]          # after UDP header
            if len(pay) < 16:
                n_other += 1
                continue
            svc, meth, ln, _cl, sess, ver, iver, mtype, rc = \
                struct.unpack(">HHIHHBBBB", pay[:16])
            if svc == 0xFFFF and meth == 0x8100:
                n_sd += 1
                continue
            if ver != 0x01:
                n_other += 1
                continue

            if mtype == 0x02:                    # Notification
                plen = ln - 8
                replay[(svc, meth)].append(pay[16:16 + plen])
                n_plain += 1
            elif mtype == 0x22:                  # SOME/IP-TP segment
                tpoff_raw = struct.unpack(">I", pay[16:20])[0]
                more = tpoff_raw & 0x1
                offset = tpoff_raw & 0xFFFFFFFE
                tp_parts[(svc, meth, sess)].append((offset, more, pay[20:]))
                n_tp += 1
            else:
                n_other += 1

    # 重组 TP 分片
    for key, parts in tp_parts.items():
        svc, meth, _sess = key
        parts.sort(key=lambda p: p[0])
        buf = b""
        for _off, _more, seg in parts:
            buf += seg
        if buf:
            replay[(svc, meth)].append(buf)

    if verbose:
        total = n_sd + n_other + n_plain + n_tp
        print(f"[pcap] {pcap_file}: 总包 {total} | SD {n_sd} | Notification {n_plain} "
              f"| TP分片 {n_tp} (重组 {len(tp_parts)} 条) | 其他 {n_other}")
        for (svc, meth), pls in sorted(replay.items()):
            sizes = [len(p) for p in pls]
            print(f"[pcap]   0x{svc:04X},0x{meth:04X}: {len(pls)} 条  "
                  f"len={min(sizes)}..{max(sizes)} 字节")
    return dict(replay)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "out.pcap"
    r = decode_pcap_replay(path)
    print(f"共 {sum(len(v) for v in r.values())} 条通知载荷")
