#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_replay.py —— 指定 pcap 文件回放（C++ 库后台线程，自动 SOME/IP-TP 重组）
演示：Python 调用 C++ 库的回放接口，指定 pcap 路径、循环、间隔。

运行：python3 demo_replay.py [pcap路径] [本机IP]
"""
import sys
import time

sys.path.insert(0, __file__ and __import__("os").path.dirname(__file__))
from arhud_py import ArHudServer


def main():
    pcap = sys.argv[1] if len(sys.argv) > 1 else "out.pcap"
    unicast = sys.argv[2] if len(sys.argv) > 2 else None

    srv = ArHudServer(unicast=unicast)
    srv.start()
    print("[demo] 服务端已启动，开始回放 pcap: %s" % pcap, flush=True)

    rc = srv.replay(pcap, loop=True, interval_ms=10)
    if rc != 0:
        print(f"[demo] replay_start 返回 {rc}（pcap 解析失败或未启动）")
        srv.close()
        sys.exit(1)

    try:
        last = 0
        while True:
            sent = srv.replay_sent()
            if sent != last:
                print(f"[demo] 已回放 {sent} 条", flush=True)
                last = sent
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\n[demo] 停止回放")
        srv.replay_stop()
    finally:
        srv.close()


if __name__ == "__main__":
    main()
