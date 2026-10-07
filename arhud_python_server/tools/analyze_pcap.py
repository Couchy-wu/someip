#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_pcap.py —— 独立 pcap 体检工具（纯 Python，不依赖 C++ 库/第三方包）
============================================================================
用途：回放/发布某个 pcap 之前，先看清里面到底有什么；回放后再核对条数。
它是 C++ 解析器（src/arhud_pcap.cpp）的**独立对照实现**：同样做
Ethernet/VLAN/IPv4/UDP + SOME/IP(type 0x02) + SOME/IP-TP(type 0x22) 解析，
同样的"分片去重 + 按偏移重组 + 缺口整条丢弃"规则，用于交叉验证。

输出内容：
  · 文件头（字节序/版本/snaplen/linktype）、包数、时间跨度
  · 每个 (service, event)：通知条数、TP 重组条数、载荷长度范围、是否在服务表里
  · TP 分片总数、重组完成数、重复分片数、缺口丢弃数
  · 事件覆盖率：不在服务表里的事件（回放时发不出去）

用法：
  python3 tools/analyze_pcap.py <pcap|目录> [更多...]
  python3 tools/analyze_pcap.py --profile old|old-capture|bplus <pcap|目录>
  python3 tools/analyze_pcap.py --json report.json <pcap|目录>
  python3 tools/analyze_pcap.py --quiet <pcap>      # 只打印汇总行
"""
import argparse
import glob
import json
import os
import struct
import sys
from collections import defaultdict

SOMEIP_HEADER = 16
TP_HEADER = 4


def service_table(profile):
    """与 src/arhud_services.h 保持一致：profile → {(service,event): (name, group)}"""
    old = {
        0x000A: [(0x8001, "VehiclePositionInfoNotify", 0x1101)],
        0x000B: [(0x8001, "RTKInfoNotify", 0x1101), (0x8002, "IMUInfoNotify", 0x1101)],
        0x000C: [(0x8001, "ObstacleInfoNotify", 0x1101), (0x8002, "LaneLineDataNotify", 0x1101),
                 (0x8003, "NewLaneLineDataNotify", 0x1101)],
        0x000D: [(0x8001, "ChangeLaneDataNotify", 0x1101), (0x8002, "PilotStatusNofity", 0x1101),
                 (0x8003, "PilotAlarmAndNoticeInfoNotify", 0x1101), (0x8004, "BroadcastInfoNotify", 0x1101),
                 (0x8005, "NewBroadcastInfoNotify", 0x1101)],
        0x000E: [(0x8001, "PlanningLineInfoNotify", 0x1101), (0x8002, "newPlanningLineInfo", 0x1102),
                 (0x8003, "drivingAreaIdentification", 0x1103)],
        0x010A: [(0x8001, "HudRoadInfo_EG", 0x1101), (0x8002, "HudMappathInfo_EG", 0x1101),
                 (0x8003, "HudNavigationmap", 0x1101), (0x8004, "OverseasHudRoadInfoNotify", 0x1101)],
        0x0007: [(0x8001, "NavigationStatus_LinkInfoNotify", 0x1101)],
        0x0017: [(0x8003, "NewParkingRealTimeDataNotify", 0x1101)],
        0x002B: [(0x8001, "NavigationHDLink2Info", 0x1101)],
        0x8202: [(0x8002, "sdTraffiIncident", 0x1101)],
        0x0018: [(0x8001, "hpaMapDataNotify", 0x1101)],
    }
    bplus = {
        0x001A: [(0x8001, "vehiclePositionInfoNotify", 0x1101), (0x8002, "rtkNotify", 0x1102),
                 (0x8003, "imuNotify", 0x1103)],
        0x001B: [(0x8001, "obstacleNotify", 0x1101), (0x8002, "laneLineDataNotify", 0x1101),
                 (0x8003, "changeLaneDataNotify", 0x1101), (0x8004, "pilotStatusNotify", 0x1102),
                 (0x8005, "pilotAlarmAndNoticeNotify", 0x1102), (0x8006, "broadcastNotify", 0x1102),
                 (0x8007, "planningLineNotify", 0x1101), (0x8008, "drivingAreaIdentification_notify", 0x1101),
                 (0x8009, "parkingDataNotify", 0x1103), (0x800A, "hpaMapDataNotify", 0x1103),
                 (0x800B, "commonObstaclesInMapDataNotify", 0x1103), (0x800C, "notifyMediaHPAPath", 0x1104),
                 (0x800D, "drivingJourneyDataNotify", 0x1105)],
        0x001C: [(0x8001, "navigationPathMatchStatusNotify", 0x1101),
                 (0x8002, "naviPathUserSelectStsConfirmNotify", 0x1102),
                 (0x8003, "navigationPathMatchP2PStatusNotify", 0x1104)],
        0x001D: [(0x8001, "sWSaleablecheckStatusNotify", 0x1101)],
        0x8000: [(0x8001, "naviGlobalInfoNotify", 0x1101), (0x8002, "naviPositionInfoNotify", 0x1102),
                 (0x8003, "naviRouteInfoNotify", 0x1103), (0x8004, "naviPathInfoNotify", 0x1103),
                 (0x8005, "aheadIntersectionsLanesInfoNotify", 0x1104), (0x8006, "mixForkInfolistNotify", 0x1104),
                 (0x8007, "naviGuideInfoNotify", 0x1105), (0x8008, "nextCrossLaneInfoNotify", 0x1105),
                 (0x8009, "facilityInfoNotify", 0x1105), (0x800A, "cameraInMapInfoNotify", 0x1105),
                 (0x800B, "naviHighwayGuideInfoNotify", 0x1105), (0x800C, "naviTrafficLightNotify", 0x1106),
                 (0x800D, "trafficJamNotify", 0x1106), (0x800E, "trafficEventInfoNotify", 0x1106)],
        0x010A: [(0x8001, "HudRoadInfoNotify", 0x1101), (0x8002, "HudMappathInfoNotify", 0x1101),
                 (0x8003, "HudNavigationmap", 0x1101), (0x8004, "OverseasHudRoadInfoNotify", 0x1101)],
    }
    extra = {  # old-capture：抓包实测但参考配置里没有的事件（组按同服务既有事件取 0x1101）
        0x0007: [(0x8003, "ext_0007_8003", 0x1101), (0x8004, "ext_0007_8004", 0x1101)],
        0x0017: [(0x8002, "ext_0017_8002", 0x1101)],
        0x8202: [(0x8001, "ext_8202_8001", 0x1101), (0x8006, "ext_8202_8006", 0x1101),
                 (0x8007, "ext_8202_8007", 0x1101), (0x8008, "ext_8202_8008", 0x1101),
                 (0x8009, "ext_8202_8009", 0x1101), (0x800A, "ext_8202_800A", 0x1101),
                 (0x800B, "ext_8202_800B", 0x1101)],
    }
    if profile == "bplus":
        table = bplus
    elif profile == "old-capture":
        table = {k: list(v) for k, v in old.items()}
        for svc, rows in extra.items():
            table.setdefault(svc, []).extend(rows)
    else:
        table = old
    names = {}
    for svc, evs in table.items():
        for ev, name, group in evs:
            names[(svc, ev)] = (name, group)
    return names


def expand(path):
    if os.path.isfile(path):
        return [path]
    files = sorted(glob.glob(os.path.join(path, "*.pcap")))
    return [f for f in files if os.path.basename(f) == "out.pcap"] + \
           [f for f in files if os.path.basename(f) != "out.pcap"]


def analyze(path, profile="old"):
    names = service_table(profile)
    size = os.path.getsize(path)
    rep = {
        "file": path, "bytes": size, "packets": 0, "bytes_udp": 0,
        "sd": 0, "non_udp": 0, "tcp": 0, "skipped": 0,
        "notifications": 0, "tp_fragments": 0, "tp_messages": 0,
        "tp_duplicates": 0, "tp_dropped": 0, "clamped": 0,
        "first_ts": None, "last_ts": None, "truncated": False,
        "per_event": defaultdict(lambda: {"notify": 0, "tp": 0, "min": None, "max": 0}),
    }
    with open(path, "rb") as f:
        head = f.read(24)
        if len(head) < 24:
            raise SystemExit("文件太小，不是 pcap: %s" % path)
        magic = head[:4]
        if magic == b"\xd4\xc3\xb2\xa1":
            order = "<"
        elif magic == b"\xa1\xb2\xc3\xd4":
            order = ">"
        else:
            raise SystemExit("不支持的 pcap magic: %r（pcapng 请先转换）" % magic)
        _vmaj, _vmin, _tz, _sig, snaplen, linktype = struct.unpack(order + "HHiIII", head[4:24])
        vmaj, vmin = _vmaj, _vmin
        rep.update(byte_order="little" if order == "<" else "big",
                   version="%d.%d" % (vmaj, vmin), snaplen=snaplen, linktype=linktype)

        groups = {}           # key -> 重组状态
        last_completed = {}   # key -> [(off,len,more)] 上一条完成消息的分片签名

        def new_group():
            return {"next": 0, "buf": bytearray(), "pending": {}, "sigs": [],
                    "offsets": set(), "finished": False}

        def record(svc, ev, tp, length):
            e = rep["per_event"][(svc, ev)]
            e["tp" if tp else "notify"] += 1
            if e["min"] is None or length < e["min"]:
                e["min"] = length
            if length > e["max"]:
                e["max"] = length

        while True:
            rh = f.read(16)
            if len(rh) < 16:
                break
            ts_sec, ts_frac, incl, orig = struct.unpack(order + "IIII", rh)
            pkt = f.read(incl)
            if len(pkt) < incl:
                rep["truncated"] = True
                break
            rep["packets"] += 1
            if incl < orig:
                rep["clamped"] += 1
            ts = ts_sec + ts_frac / 1e6
            if rep["first_ts"] is None:
                rep["first_ts"] = ts
            rep["last_ts"] = ts

            if len(pkt) < 14:
                rep["non_udp"] += 1
                continue
            et = struct.unpack(">H", pkt[12:14])[0]
            off = 14
            while et in (0x8100, 0x88A8, 0x9100):
                if len(pkt) < off + 4:
                    break
                et = struct.unpack(">H", pkt[off + 2:off + 4])[0]
                off += 4
            if et != 0x0800 or len(pkt) < off + 20:
                rep["non_udp"] += 1
                continue
            if (pkt[off] >> 4) != 4:
                rep["non_udp"] += 1
                continue
            proto = pkt[off + 9]
            if proto == 6:
                rep["tcp"] += 1
                continue
            if proto != 17:
                rep["non_udp"] += 1
                continue
            ihl = (pkt[off] & 0x0F) * 4
            pay = off + ihl
            if len(pkt) < pay + 8:
                rep["non_udp"] += 1
                continue
            udp_len = struct.unpack(">H", pkt[pay + 4:pay + 6])[0]
            end = min(pay + max(udp_len, 8), len(pkt))
            body = pkt[pay + 8:end]
            rep["bytes_udp"] += len(body)
            if len(body) < SOMEIP_HEADER:
                rep["skipped"] += 1
                continue
            svc, meth = struct.unpack(">HH", body[0:4])
            length = struct.unpack(">I", body[4:8])[0]
            sess = struct.unpack(">H", body[10:12])[0]
            ver = body[12]
            mtype = body[14]
            if svc == 0xFFFF and meth == 0x8100:
                rep["sd"] += 1
                continue
            if ver != 0x01:
                rep["skipped"] += 1
                continue

            if mtype == 0x02:
                plen = max(length - 8, 0)
                avail = len(body) - SOMEIP_HEADER
                if plen > avail:
                    plen = avail
                    rep["clamped"] += 1
                rep["notifications"] += 1
                record(svc, meth, False, plen)
            elif mtype == 0x22:
                if len(body) < SOMEIP_HEADER + TP_HEADER:
                    rep["skipped"] += 1
                    continue
                raw = struct.unpack(">I", body[SOMEIP_HEADER:SOMEIP_HEADER + 4])[0]
                toff = raw & 0xFFFFFFFE
                more = bool(raw & 1)
                frag = body[SOMEIP_HEADER + TP_HEADER:]
                rep["tp_fragments"] += 1
                key = (svc, meth, sess)
                g = groups.get(key)
                if g is None:
                    g = groups[key] = new_group()
                # 1) 同一偏移重复分片 → 丢弃（抓包被复制/重复投递）
                if toff in g["offsets"]:
                    rep["tp_duplicates"] += 1
                    continue
                # 2) 上一条已完成消息的重复尾巴 → 丢弃
                if not g["buf"] and not g["pending"] and not g["sigs"] and toff != 0:
                    if (toff, len(frag), more) in last_completed.get(key, []):
                        rep["tp_duplicates"] += 1
                        continue
                # 3) 新消息从 0 开始而上一条没拼完 → 丢上一条（绝不发布半截）
                if toff == 0 and (g["buf"] or g["pending"]):
                    rep["tp_dropped"] += 1
                    g = groups[key] = new_group()
                g["offsets"].add(toff)
                g["pending"][toff] = frag
                g["sigs"].append((toff, len(frag), more))
                if not more:
                    g["finished"] = True
                while g["pending"]:
                    o = min(g["pending"])
                    if o != g["next"]:
                        break
                    d = g["pending"].pop(o)
                    g["buf"] += d
                    g["next"] += len(d)
                if g["finished"] and not g["pending"]:
                    rep["tp_messages"] += 1
                    record(svc, meth, True, len(g["buf"]))
                    last_completed[key] = g["sigs"]
                    del groups[key]
            else:
                rep["skipped"] += 1

        for g in groups.values():          # 文件尾没收完的 → 丢弃
            if g["buf"] or g["pending"]:
                rep["tp_dropped"] += 1

    rep["per_event"] = dict(rep["per_event"])
    rep["unknown"] = sorted(k for k in rep["per_event"] if k not in names)
    return rep


def report_text(r, profile):
    names = service_table(profile)
    out = []
    out.append("=" * 84)
    out.append("文件        : %s" % r["file"])
    out.append("大小        : %.1f MB  (pcap %s / %s, snaplen=%d, linktype=%d)"
               % (r["bytes"] / 1048576.0, r["byte_order"], r["version"], r["snaplen"], r["linktype"]))
    out.append("报文        : %d 包（UDP 载荷 %.1f MB；SD %d；TCP %d；其它 %d）"
               % (r["packets"], r["bytes_udp"] / 1048576.0, r["sd"], r["tcp"],
                  r["non_udp"] + r["skipped"]))
    if r["first_ts"] is not None:
        out.append("时间跨度    : %.3f → %.3f（%.1f 秒）"
                   % (r["first_ts"], r["last_ts"], r["last_ts"] - r["first_ts"]))
    out.append("消息        : 通知 %d + TP 重组 %d = %d 条"
               % (r["notifications"], r["tp_messages"], r["notifications"] + r["tp_messages"]))
    out.append("TP 分片     : %d 片 → 重组 %d 条；重复分片去重 %d 片；缺口/截断丢弃 %d 条"
               % (r["tp_fragments"], r["tp_messages"], r["tp_duplicates"], r["tp_dropped"]))
    if r["truncated"]:
        out.append("!! 文件在读取中途截断（最后一个包不完整）")
    out.append("-" * 84)
    out.append("%-13s %-38s %8s %8s   %s" % ("事件", "名称", "通知", "TP", "载荷长度"))
    total = 0
    for (svc, ev), e in sorted(r["per_event"].items()):
        total += e["notify"] + e["tp"]
        name, _group = names.get((svc, ev), ("<不在服务表>", 0))
        mark = " " if (svc, ev) in names else "?"
        out.append("%s %04X:%-7X %-38s %8d %8d   %s..%s"
                   % (mark, svc, ev, name[:38], e["notify"], e["tp"], e["min"], e["max"]))
    out.append("  合计 %d 条" % total)
    if r["unknown"]:
        out.append("-" * 84)
        out.append("!! %d 个事件不在 %s 表里（--profile old-capture 可覆盖）：%s"
                   % (len(r["unknown"]), profile,
                      ", ".join("0x%04X:0x%04X" % k for k in r["unknown"])))
    else:
        out.append("覆盖率: 全部事件都在 %s 表里（回放时都能发布出去）" % profile)
    out.append("=" * 84)
    return "\n".join(out)


def json_safe(r):
    out = dict(r)
    out["per_event"] = {"%04X:%04X" % k: v for k, v in r["per_event"].items()}
    out["unknown"] = ["%04X:%04X" % k for k in r["unknown"]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="pcap 文件或目录")
    ap.add_argument("--profile", default="old", choices=["old", "old-capture", "bplus"])
    ap.add_argument("--json", default=None, help="把结果写入 JSON")
    ap.add_argument("--quiet", action="store_true", help="只打印汇总行")
    args = ap.parse_args()

    files = []
    for p in args.paths:
        files.extend(expand(p))
    if not files:
        print("没有找到 pcap", file=sys.stderr)
        return 1
    all_rep = []
    for f in files:
        r = analyze(f, args.profile)
        all_rep.append(json_safe(r))
        if args.quiet:
            print("%-28s 消息=%-7d (通知 %-6d + TP %-5d)  重复分片=%-5d 缺口丢弃=%-3d 未覆盖=%d"
                  % (os.path.basename(f), r["notifications"] + r["tp_messages"],
                     r["notifications"], r["tp_messages"], r["tp_duplicates"],
                     r["tp_dropped"], len(r["unknown"])))
        else:
            print(report_text(r, args.profile))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(all_rep, f, indent=2, ensure_ascii=False)
        print("JSON 报告已写入 %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
