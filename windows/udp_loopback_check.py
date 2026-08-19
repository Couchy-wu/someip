#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯 UDP 通路检查 —— 不依赖 vsomeip，验证本机 UDP 端口与网络通路
================================================================
用途：在 Windows 上区分"网络问题"还是"vsomeip 配置问题"：
  - 若本检查 PASS，说明本机 UDP 51400..51402 可通、防火墙放行，
    DEREGISTERED/收不到数据 → vsomeip 配置问题（见 diagnose_windows.py / SOLUTION_WINDOWS.md）
  - 若本检查 FAIL，先解决网络/防火墙（Windows 防火墙需放行 UDP 入站）

运行：python3 udp_loopback_check.py [目标IP]
默认目标：ARHUD_UNICAST 或自动获取的本机主 IP（10.13.90.164 这类）
"""

import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from get_local_ip import get_local_ip

PORTS = [51400, 51401, 51402]   # 与服务端端口一致，可改


def _receiver(port, results):
    """在指定端口接收一个 UDP 包"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", port))
        s.settimeout(5)
        data, addr = s.recvfrom(1024)
        results[port] = (data, addr)
    except socket.timeout:
        results[port] = None
    except OSError as e:
        results[port] = ("ERR", str(e))
    finally:
        s.close()


def udp_check(target_ip: str = None):
    """对每个端口: 起接收线程 -> 从 target_ip 发包 -> 验证回包"""
    ip = target_ip or os.environ.get("ARHUD_UNICAST") or get_local_ip()
    print(f"    目标 IP: {ip}")
    ok = True
    for port in PORTS:
        results = {}
        t = threading.Thread(target=_receiver, args=(port, results), daemon=True)
        t.start()
        time.sleep(0.2)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(3)
            s.sendto(b"SOMEIP-LOOPBACK-CHECK", (ip, port))
            s.close()
        except OSError as e:
            print(f"    [FAIL] 发送到 {ip}:{port} 失败: {e}")
            ok = False
            t.join(timeout=6)
            continue
        t.join(timeout=6)
        got = results.get(port)
        if got and got[0] not in ("ERR", None):
            print(f"    [OK] {ip}:{port} 回环可达, 收到 {len(got[0])}B 来自 {got[1]}")
        else:
            print(f"    [FAIL] {ip}:{port} 未收到回包（防火墙可能拦截 UDP 入站）")
            ok = False
    print(f"    -> {'全部端口可达 ✓' if ok else '存在不可达端口（先解决网络/防火墙）'}")
    return ok


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(0 if udp_check(target) else 1)
