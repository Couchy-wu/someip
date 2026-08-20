#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本机"主 IP"获取 —— Windows / Linux 通用
========================================
优先级（从可靠到兜底）：
  1) 环境变量 ARHUD_UNICAST（最可靠：Windows 多网卡环境强烈建议显式指定，如 10.13.90.164）
  2) UDP connect 到外部地址（8.8.8.8:80 / 1.1.1.1:53 / 223.5.5.5:53）取本机源地址
     —— 与 windows_problem.txt 中的修复思路一致，但 UDP connect 不真正发包，更快更安全
  3) 遍历主机名解析出的 IPv4，跳过回环与常见虚拟网卡网段（VMware/VirtualBox/VMnet）
  4) 兜底 127.0.0.1

vsomeip 的 unicast 必须是与对端可路由的真实网卡地址：
  - Windows 多网卡（以太网 + VMware + 回环）时，socket.gethostbyname(hostname) 可能返回
    127.0.0.1 或 VMware 地址，导致服务端/客户端"看不见"对方 —— 用本模块规避。
"""

import os
import socket

# 常见虚拟网卡网段（VMware / VirtualBox / Hyper-V 等），多网卡环境优先跳过
VIRTUAL_PREFIXES = (
    "192.168.137.",   # VMware NAT (host-only 常见)
    "192.168.126.",   # VMware
    "192.168.56.",    # VirtualBox host-only
    "192.168.99.",    # Docker Toolbox
    "169.254.",       # APIPA / 未连接
)

# 探测用外部地址（只 connect 不发包，任何可达即返回对应源地址）
PROBE_TARGETS = [
    ("8.8.8.8", 80),
    ("1.1.1.1", 53),
    ("223.5.5.5", 53),   # 阿里 DNS（国内网络）
    ("114.114.114.114", 53),
]
# 不依赖外网的探测：非路由地址/保留地址（UDP connect 不真正发包，
# 只要存在默认路由即可选出本机源 IP；局域网/容器/断网环境也能用）
LOCAL_PROBE_TARGETS = [
    ("192.0.2.1", 9),     # TEST-NET-1（RFC 5737）
    ("10.255.255.255", 1),
]


def _default_gateway():
    """解析 /proc/net/route 的默认网关（Linux）；Windows 返回 None（用上面探测替代）"""
    try:
        with open("/proc/net/route", "r") as f:
            for line in f.readlines()[1:]:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "00000000":  # Destination 0.0.0.0
                    ip = ".".join(str(int(parts[2][i:i + 2], 16)) for i in (6, 4, 2, 0))
                    return ip
    except OSError:
        pass
    return None


def _udp_connect_ip(target):
    """UDP connect 到 target，返回本机源 IP；失败返回 None（不真正发送数据）"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(1.0)
            s.connect(target)
            ip = s.getsockname()[0]
            return ip if ip and not ip.startswith("127.") else None
        finally:
            s.close()
    except OSError:
        return None


def is_virtual_ip(ip: str) -> bool:
    """判断 IP 是否属于常见虚拟网卡网段"""
    return ip.startswith(VIRTUAL_PREFIXES)


def list_candidate_ips() -> list:
    """列出本机候选 IPv4（含回环），用于诊断输出"""
    ips = set()
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ":" not in ip:  # 只要 IPv4
                ips.add(ip)
    except OSError:
        pass
    try:
        ips.add(socket.gethostbyname(socket.gethostname()))
    except OSError:
        pass
    # 顺序稳定，便于展示
    return sorted(ips)


def get_local_ip() -> str:
    """返回推荐的本机 unicast IP（详见模块 docstring 的优先级）"""
    # 1) 环境变量显式指定（Windows 多网卡首选）
    env = os.environ.get("ARHUD_UNICAST")
    if env:
        return env.strip()

    # 2) UDP connect 探测外部地址
    for target in PROBE_TARGETS:
        ip = _udp_connect_ip(target)
        if ip and not is_virtual_ip(ip):
            return ip
        if ip:
            return ip  # 非回环即接受（即使像虚拟网段也优于 127.0.0.1）

    # 2.5) 默认网关（不依赖外网）：经网关发包源地址即本机主 IP
    gw = _default_gateway()
    if gw:
        ip = _udp_connect_ip((gw, 53))
        if ip:
            return ip
    # 2.6) 非路由地址探测（存在默认路由即可，断网/局域网/容器通用）
    for target in LOCAL_PROBE_TARGETS:
        ip = _udp_connect_ip(target)
        if ip:
            return ip

    # 3) 主机名解析 + 过滤
    for ip in list_candidate_ips():
        if ip.startswith("127.") or is_virtual_ip(ip):
            continue
        return ip

    # 4) 兜底
    return "127.0.0.1"


if __name__ == "__main__":
    print("候选 IP:", ", ".join(list_candidate_ips()) or "(无)")
    print("推荐 unicast:", get_local_ip())
