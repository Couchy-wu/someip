#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows 环境自诊断脚本 —— 运行前先跑它，定位 DEREGISTERED 循环/收不到数据的问题
================================================================================
检查项：
  1. 本机网卡与 IP（含 ipconfig 输出，确认哪个 IP 是主网络）
  2. 推荐的 unicast（get_local_ip），支持 ARHUD_UNICAST 覆盖
  3. 【关键】routing 配置一致性：routing 指向的应用名必须真实存在于 applications 中
     —— 若 routing 指向不存在的应用名（如原配置的 "arhud01"），
        没有任何进程会成为路由管理器宿主 → 客户端反复 DEREGISTERED
  4. 构造函数第 2 参数 = 服务 ID（不是客户端 ID）的提醒
  5. 纯 UDP 通路检查（调用 udp_loopback_check 验证 51400..51402 端口可达）

运行：python3 diagnose_windows.py
"""

import os
import socket
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from get_local_ip import get_local_ip, list_candidate_ips, is_virtual_ip


def run_ipconfig():
    """Windows: 打印 ipconfig 摘要（网卡/IP/网关）"""
    if not sys.platform.startswith("win"):
        print("[info] 非 Windows，跳过 ipconfig（可用 ifconfig/ip addr 查看）")
        return
    try:
        out = subprocess.run(["ipconfig"], capture_output=True, text=True,
                             timeout=15, encoding="gbk", errors="replace").stdout
        # 只保留 适配器/IPv4/网关 行，减少噪音
        for line in out.splitlines():
            s = line.strip()
            if s and (s.startswith("适配器") or s.startswith("以太网")
                      or "IPv4" in s or "IPv6" in s or "默认网关" in s
                      or "Ethernet" in s or "adapter" in s or "Gateway" in s):
                print("   ", s)
    except Exception as e:
        print(f"[warn] ipconfig 执行失败: {e}")


def check_routing_config():
    """校验 routing 指向的应用名是否存在于 applications"""
    print("\n[3] 路由管理器宿主(routing)配置检查:")
    # 读取运行目录 vsomeip.json（若存在）作为线索
    cfg_path = "vsomeip.json"
    apps = []
    routing = None
    if os.path.exists(cfg_path):
        try:
            import json
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            apps = [a.get("name") for a in cfg.get("applications", [])]
            routing = cfg.get("routing")
            print(f"    vsomeip.json: applications={apps}  routing={routing!r}")
        except Exception as e:
            print(f"    vsomeip.json 解析失败: {e}")
    else:
        print(f"    {cfg_path} 不存在（代码用模板生成配置，routing 由代码决定）")
        print("    服务端: 第一个含 services 的应用自动成为宿主（如 arhud_server）")
        print("    客户端: 必须显式 routing=<服务端第一个应用名>")

    if routing:
        if routing in apps:
            print(f"    [OK] routing={routing!r} 存在于 applications ✓")
        else:
            print(f"    [FAIL] routing={routing!r} 不是任何应用名！"
                  f"（applications={apps}）")
            print("    -> 没有任何进程会成为路由管理器宿主 -> 客户端反复 DEREGISTERED。")
            print(f"    修复: 服务端把 routing 设为自己（如 arhud_server），"
                  f"客户端 routing 设为服务端应用名。")
    return routing, apps


def check_constructor_ids():
    """提醒构造函数第 2 参数 = 服务 ID"""
    print("\n[4] vSOMEIP 构造函数参数检查:")
    print("    第 2 个参数 = 服务 ID（offer/register/on_event 用它）")
    print("    客户端 ID 放在配置 applications[].id —— 两者可以不同")
    print("    反例: vSOMEIP('arhud_client', 0x1003, ...) -> 会去订阅服务 0x1003（不存在）")


def main():
    print("=" * 64)
    print(" ArHud SOME/IP Windows 环境自诊断")
    print("=" * 64)

    print("\n[1] 本机网卡与 IP（ipconfig）:")
    run_ipconfig()

    print("\n[2] 候选 IP 与推荐 unicast:")
    for ip in list_candidate_ips():
        tag = "虚拟网卡?" if is_virtual_ip(ip) else ""
        print(f"    {ip} {tag}")
    env = os.environ.get("ARHUD_UNICAST")
    if env:
        print(f"    ARHUD_UNICAST 已设置: {env}")
    print(f"    推荐 unicast: {get_local_ip()}")
    if not env:
        print("    （多网卡环境建议显式设置 ARHUD_UNICAST=<以太网IP>）")

    check_routing_config()
    check_constructor_ids()

    print("\n[5] 纯 UDP 通路检查:")
    from udp_loopback_check import udp_check
    udp_check()

    print("\n" + "=" * 64)
    print(" 诊断完成。若 [3] 出现 FAIL，先修复 routing 配置再运行客户端。")
    print("=" * 64)


if __name__ == "__main__":
    main()
