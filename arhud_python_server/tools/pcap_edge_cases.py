#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pcap_edge_cases.py —— 解析器边界用例（合成 pcap，不依赖真实抓包）
============================================================================
真实抓包覆盖不到的分支，这里用手工合成的 pcap 覆盖：
  · 小端/大端 pcap 文件头（记录头字节序跟随文件头）
  · 微秒 / 纳秒时间戳
  · 带 VLAN 标签（0x8100）的帧
  · SOME/IP-SD（0xFFFF:0x8100）跳过
  · pcapng 文件 → 明确报错并给出转换方法
  · 不支持的 linktype（101=RAW IP）→ 明确报错
  · Linux SLL（113）→ 能识别 linktype 并按 SLL 解析

用法：
  g++ -std=c++14 -O2 -I src src/arhud_pcap.cpp tools/pcap_selftest.cpp -o /tmp/pcap_selftest
  python3 tools/pcap_edge_cases.py /tmp/pcap_selftest
"""
import os
import struct
import subprocess
import sys
import tempfile


def someip_notify(svc=0x000A, ev=0x8001, payload=b"\xAA" * 20):
    return (struct.pack(">HHI", svc, ev, 8 + len(payload)) +
            struct.pack(">HH", 1, 1) + bytes([1, 0, 0x02, 0]) + payload)


def someip_sd():
    # SD：service=0xFFFF method=0x8100，应被跳过
    return (struct.pack(">HHI", 0xFFFF, 0x8100, 8 + 12) +
            struct.pack(">HH", 1, 1) + bytes([1, 0, 0x02, 0]) + b"\x00" * 12)


def build_pcap(order="<", linktype=1, vlan=False, nsec=False, body=None, ip_proto=17):
    eth = b"\x11" * 12
    if vlan:
        eth += struct.pack(">H", 0x8100) + struct.pack(">HH", 0x0001, 0x0800)
    else:
        eth += struct.pack(">H", 0x0800)
    payload = body if body is not None else someip_notify()
    udp = struct.pack(">HHHH", 51000, 51400, 8 + len(payload), 0) + payload
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 0, 0, 64, ip_proto, 0,
                     b"\x0a\x00\x00\x01", b"\x0a\x00\x00\x02")
    pkt = eth + ip + udp
    if nsec and order == "<":
        magic = b"\x4d\x3c\xb2\xa1"
    elif nsec:
        magic = b"\xa1\xb2\x3c\x4d"
    elif order == "<":
        magic = b"\xd4\xc3\xb2\xa1"
    else:
        magic = b"\xa1\xb2\xc3\xd4"
    hdr = magic + struct.pack(order + "HHiIII", 2, 4, 0, 0, 262144, linktype)
    ts = (1747926000, 123456789 if nsec else 123456)
    rec = struct.pack(order + "IIII", ts[0], ts[1], len(pkt), len(pkt)) + pkt
    return hdr + rec


def build_sll(order="<"):
    """Linux SLL(113)：16 字节头，协议在 14:16，之后直接是 IP"""
    payload = someip_notify()
    udp = struct.pack(">HHHH", 51000, 51400, 8 + len(payload), 0) + payload
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 0, 0, 64, 17, 0,
                     b"\x0a\x00\x00\x01", b"\x0a\x00\x00\x02")
    sll = struct.pack(">HHH", 0, 1, 6) + b"\x11" * 8 + struct.pack(">H", 0x0800)
    pkt = sll + ip + udp
    hdr = b"\xd4\xc3\xb2\xa1" + struct.pack(order + "HHiIII", 2, 4, 0, 0, 262144, 113)
    return hdr + struct.pack(order + "IIII", 1, 1, len(pkt), len(pkt)) + pkt


def run(tool, path):
    p = subprocess.run([tool, path], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main():
    tool = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pcap_selftest"
    if not os.path.exists(tool):
        print("找不到 %s（先编译 tools/pcap_selftest.cpp）" % tool)
        return 2
    tmp = tempfile.mkdtemp(prefix="arhud_pcap_edge_")
    cases = []   # (文件名, 内容, 期望: 'ok' 或 期望的关键字, 期望消息数)

    cases.append(("le.pcap", build_pcap("<"), "ok", 1))
    cases.append(("be.pcap", build_pcap(">"), "ok", 1))
    cases.append(("ns.pcap", build_pcap("<", nsec=True), "ok", 1))
    cases.append(("vlan.pcap", build_pcap("<", vlan=True), "ok", 1))
    cases.append(("sd_only.pcap", build_pcap("<", body=someip_sd()), "ok", 0))
    cases.append(("sll.pcap", build_sll(), "ok", 1))
    cases.append(("tcp.pcap", build_pcap("<", ip_proto=6), "ok", 0))
    cases.append(("pcapng.pcap", b"\x0a\x0d\x0d\x0a" + b"\x00" * 64, "pcapng", None))
    cases.append(("raw.pcap", build_pcap("<", linktype=101), "linktype", None))

    bad = 0
    for name, data, expect, nmsg in cases:
        path = os.path.join(tmp, name)
        with open(path, "wb") as f:
            f.write(data)
        rc, out = run(tool, path)
        if expect == "ok":
            ok = (rc == 0)
            if nmsg is not None:
                if nmsg == 0:
                    # 0 条时汇总行不打印（"TP消息=0" 里也含"消息="，故用行首匹配）
                    ok = ok and ("通知=0" in out) and ("\n   消息=" not in out)
                else:
                    ok = ok and ("   消息=%d " % nmsg) in out
            mark = "OK " if ok else "FAIL"
        else:
            ok = (rc != 0) and (expect in out)
            mark = "OK " if ok else "FAIL"
        if not ok:
            bad += 1
        detail = next((l.strip() for l in out.splitlines()
                       if l.strip().startswith("[FAIL]")), "")
        if not detail:
            detail = next((l.strip() for l in out.splitlines()
                           if l.strip().startswith("包=")), "")
        if not detail:
            detail = next((l.strip() for l in out.splitlines()
                           if l.strip().startswith("== ")), "")
        print("%s %-16s %s" % (mark, name, detail[:110]))
    print("== 边界用例：%d 个，失败 %d 个（临时目录 %s）" % (len(cases), bad, tmp))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
