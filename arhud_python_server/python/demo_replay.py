#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_replay.py —— 回放 + 发布 pcap（支持"目录 / 多个 pcap / 按抓包原始节奏"）
=============================================================================
与参考实现 to_longjie_demo_20250625/hud_pcap_huifang_server.cpp 的行为对齐：
  · 读 pcap → 解析 SOME/IP → TP 重组 → SPServerSendNotify 发布
  · 按抓包记录的包间隔回放（timing=capture），也可固定间隔（timing=interval）
  · 目录用法对齐参考实现的"读 <目录>/out.pcap"：目录下 out.pcap 优先，其余按名字排序

运行：
  # 目录（推荐）：old 目录下 out.pcap / output3.pcap / outputblanket.pcap 依次回放
  python3 demo_replay.py /Users/wunengfa/Desktop/someip/lipeng20260228/old

  # 单个文件
  python3 demo_replay.py /path/out.pcap 192.168.1.10

  # 常用选项
  --profile auto|old|old-capture|bplus   服务表（auto=按 pcap 自动挑，默认 auto）
  --timing capture|interval              节奏（默认 capture=按抓包时间戳）
  --speed 2.0                            倍速（capture 模式）
  --interval-ms 10                       interval 模式每条间隔
  --once / --loops N                     只跑一轮 / 跑 N 轮（默认无限循环）
  --delay 20                             起播前等待秒数（等板端订阅稳定，真机建议 15~25）
  --analyze                              回放前打印事件覆盖情况
  --list                                 只列出目录里的 pcap
  --report-json FILE                     结束后把回放报告（JSON）写入文件

演练（没有协议栈/不想发包时，用演练版库跑同一套逻辑）：
  g++ -std=c++14 -O2 -shared -fPIC -I src src/arhud_pcap.cpp src/arhud_replay.cpp \\
      src/arhud_types.cpp tools/dryrun_server.cpp -o /tmp/dryrun/libarhud_server.so -lz
  ARHUD_LIB_PATH=/tmp/dryrun/libarhud_server.so python3 demo_replay.py <pcap或目录> --once
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arhud_py import ArHudServer, find_pcaps, pcap_events, profile_events  # noqa: E402


def print_coverage(paths, profile):
    """回放前体检：pcap 里有哪些事件、当前服务表覆不覆盖得住"""
    used = set(pcap_events(paths))
    table = set(profile_events(profile))
    missing = sorted(used - table)
    print("[体检] pcap 事件 %d 个，profile=%s 表内 %d 个，未覆盖 %d 个"
          % (len(used), profile, len(table), len(missing)))
    if missing:
        print("[体检] !! 未覆盖（回放时发不出去，换 --profile old-capture 试试）：%s"
              % ", ".join("0x%04X:0x%04X" % m for m in missing))
    return used, missing


def print_report(rep):
    print("\n[报告] 文件 %(files)s 个 / 轮数 %(loops)s / 解析 %(parsed)s 条 / "
          "发布成功 %(sent)s 条 / 失败 %(failed)s 条 / 表外事件 %(unregistered)s 条" % rep)
    print("[报告] pcap 记录 %(packets)s 条，TP 残缺丢弃 %(tp_dropped)s 条，"
          "重复分片去重 %(tp_duplicates)s 片，耗时 %(elapsed_s).2f 秒" % rep)
    events = sorted(rep.get("events", []), key=lambda e: (-e["attempted"], e["service"], e["event"]))
    if events:
        print("[报告] 逐事件发布情况（前 40 个）：")
        print("        service:event   attempted      sent  unregistered")
        for e in events[:40]:
            print("        %04X:%-9X %9d %9d %13d"
                  % (e["service"], e["event"], e["attempted"], e["sent"], e["unregistered"]))


def main():
    ap = argparse.ArgumentParser(description="回放并发布 pcap（支持目录/多文件/按抓包节奏）",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="pcap 文件或目录")
    ap.add_argument("unicast", nargs="?", default=None, help="本机 IP（缺省自动探测）")
    ap.add_argument("--profile", default="auto",
                    choices=["auto", "old", "old-capture", "bplus"])
    ap.add_argument("--timing", default="capture", choices=["capture", "interval"])
    ap.add_argument("--speed", type=float, default=1.0, help="capture 模式倍速（2=两倍速）")
    ap.add_argument("--interval-ms", type=int, default=10, help="interval 模式每条间隔毫秒")
    ap.add_argument("--loops", type=int, default=0, help="轮数，0=无限（配合 --timing capture 的默认行为）")
    ap.add_argument("--once", action="store_true", help="只跑一轮")
    ap.add_argument("--delay", type=float, default=0.0, help="起播前等待秒数（等客户端订阅）")
    ap.add_argument("--analyze", action="store_true", help="回放前打印事件覆盖情况")
    ap.add_argument("--list", action="store_true", help="只列出目录里的 pcap")
    ap.add_argument("--report-json", default=None, help="回放报告写入的 JSON 文件")
    args = ap.parse_args()

    try:
        paths = find_pcaps(args.path)
    except FileNotFoundError:
        print("[demo] 路径不存在: %s" % args.path)
        return 1
    if not paths:
        print("[demo] 目录下没有 pcap: %s" % args.path)
        return 1
    print("[demo] 待回放 %d 个 pcap：" % len(paths))
    for p in paths:
        print("        %s (%.1f MB)" % (p, os.path.getsize(p) / 1048576.0))
    if args.list:
        return 0

    # 选表：auto = 挑一个能覆盖住所有 pcap 事件的最小的表
    if args.profile == "auto":
        profile, missing = ArHudServer.best_profile_for_pcaps(paths)
        print("[demo] --profile auto → 选表 %s（未覆盖 %d 个事件）" % (profile, len(missing)))
        if missing:
            print("[demo] !! 没有哪个表能全覆盖，缺：%s"
                  % ", ".join("0x%04X:0x%04X" % m for m in sorted(missing)))
    else:
        profile = args.profile
    if args.analyze:
        print_coverage(paths, profile)

    srv = ArHudServer(unicast=args.unicast, profile=profile)
    srv.start()
    print("[demo] 服务端已启动：profile=%s，服务/事件数见库自报" % profile)

    if args.delay > 0:
        print("[demo] 等待 %.1f 秒（让客户端完成订阅）..." % args.delay)
        time.sleep(args.delay)

    loops = 1 if args.once else args.loops
    rc = srv.replay(paths, loop=(args.once is False and args.loops != 1),
                    timing=args.timing, speed=args.speed,
                    interval_ms=args.interval_ms, max_loops=loops,
                    start_delay_ms=0)
    if rc != 0:
        print("[demo] replay_start 返回 %d（pcap 解析失败或未启动）" % rc)
        srv.close()
        return 1
    mode = "%s speed=%.2f" % (args.timing, args.speed) if args.timing == "capture" \
        else "%s interval=%dms" % (args.timing, args.interval_ms)
    print("[demo] 开始回放/发布：%s%s" % (mode, "（无限循环，Ctrl+C 停止）" if not args.once and args.loops == 0 else ""))

    last = 0
    try:
        while True:
            st = srv.replay_status()
            if st["parsed"] != last:
                print("[demo] 已发布 %d 条（成功 %d / 表外 %d）"
                      % (st["parsed"], st["sent"], st["unregistered"]), flush=True)
                last = st["parsed"]
            if not st["running"]:
                break            # 单轮/限轮跑完
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\n[demo] 收到 Ctrl+C，停止回放")
        srv.replay_stop()

    rep = srv.replay_report()
    print_report(rep)
    if args.report_json:
        with open(args.report_json, "w") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
        print("[demo] 报告已写入 %s" % args.report_json)
    srv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
