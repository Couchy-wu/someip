# -*- coding: utf-8 -*-
"""scripts.someip_replay_check —— SOME/IP 回放端到端检查（Linux 容器/现场均可跑）

一条命令验证"更新后的 SOME/IP 程序"是否正常：

    1) 库探测      libarhud_server.so 是否就绪、配套 libsomeip*.so 是否被自动预加载
    2) 建实例      用指定（或随仓库分发的）vsomeip 配置创建服务端
    3) 注册/启动   按当前服务表代注册服务与事件
    4) 单条发送    结构化发送一帧 RTK（校验序列化长度）
    5) pcap 回放   本地解析条数 与 库内已发送条数 是否一致
    6) 服务表      old / bplus 两代的规模与"能否注册"

用法（项目根目录执行）：

    python -m scripts.someip_replay_check                     # 用随仓库配置 + 自带 pcap
    python -m scripts.someip_replay_check --pcap x.pcap --loop
    python -m scripts.someip_replay_check --config data/someip/config/someip_arhud01_pcap_server_B+.json
    python -m scripts.someip_replay_check --table bplus       # 查看 bplus 代（预期：不可注册）

退出码：0=全部通过；1=有检查项失败；2=环境不具备（缺库/缺 pcap）。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from hudcore import logging_setup
from hudcore.platform.paths import paths
from hudcore.someip import describe_library_status, is_library_available

from someip_core import (
    ReplayConfig, ReplayController, active_table, available_tables, describe_tables,
    registrable, set_table, shipped_config_path,
)

LOGGER_NAME = "someip"

# 默认 pcap：优先用仓库里自带的样例，其次用现场的 out.pcap
_DEFAULT_PCAP_CANDIDATES = (
    "data/someip/sample/out_sample.pcap",        # 仓库自带小样例（参考实现 out.pcap 的前 400 包）
    "data/someip/sample/out.pcap",
    "data/to_longjie_demo_20250625/build/out.pcap",
    "out.pcap",
)


def _default_pcap() -> Path | None:
    for rel in _DEFAULT_PCAP_CANDIDATES:
        p = paths.project_root / rel
        if p.is_file():
            return p
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SOME/IP 回放端到端检查")
    ap.add_argument("--pcap", default=None, help="回放的 pcap（默认用仓库自带样例）")
    ap.add_argument("--config", default=None, help="vsomeip 配置（默认用当前代随仓库配置）")
    ap.add_argument("--table", default=None, choices=["old", "bplus"], help="服务表代")
    ap.add_argument("--unicast", default=None, help="本机单播地址（默认由配置决定）")
    ap.add_argument("--loop", action="store_true", help="循环回放")
    ap.add_argument("--interval-ms", type=int, default=5, help="回放节流间隔")
    ap.add_argument("--timeout", type=float, default=60.0, help="等回放完成的最长秒数")
    args = ap.parse_args(argv)

    if args.table:
        set_table(args.table)
    table = active_table()
    info = available_tables()[table]

    failures: list[str] = []
    print("=== SOME/IP 回放检查 ===")
    print(describe_tables())

    # 1) 库
    print(f"\n[1/5] 库探测：{describe_library_status()}")
    if not is_library_available():
        print("[失败] SOME/IP 服务端库不可用（Windows 侧暂无 DLL；Linux 需 libarhud_server.so）")
        return 2
    print("      ✓ 库可用")

    # 2) 配置
    config = Path(args.config) if args.config else shipped_config_path(table)
    if args.config and not Path(args.config).is_file():
        print(f"[失败] 指定的配置不存在：{args.config}")
        return 2
    print(f"[2/5] vsomeip 配置：{config if config else '(库内置默认)'}"
          f"{'' if args.config else '（随仓库分发）'}")
    if config is None:
        failures.append("未找到随仓库分发的配置，将回退库内置默认")

    # 3) 服务表
    print(f"[3/5] 服务表：{table}｜{info['services']} 服务/{info['events']} 事件｜"
          f"{'可注册' if registrable(table) else '⚠ 库侧暂不可注册'}")
    if not registrable(table):
        failures.append(f"{table} 代服务暂不可由回放库注册")

    # 4) 建实例 → 注册 → 启动 → 单条发送
    table_info = dict(info)
    table_info["sample_event"] = (0x001A, 0x8001) if table == "bplus" else (0x000A, 0x8001)
    info = table_info
    ctl = ReplayController(on_log=lambda m: logging_setup.info(LOGGER_NAME, m))
    rc = 2
    try:
        ctl.open(unicast=args.unicast, config_path=str(config) if config else None)
        n_svc, n_evt = ctl.register()
        ctl.start()
        expect = (info["services"], info["events"])
        print(f"[4/5] 创建/注册/启动：{n_svc} 服务/{n_evt} 事件（该代预期 {expect[0]}/{expect[1]}）")
        if (n_svc, n_evt) == expect:
            print(f"      ✓ 与 {table} 代服务表一致")
        else:
            failures.append(f"注册规模与 {table} 代服务表不符：{n_svc}/{n_evt}，应为 {expect[0]}/{expect[1]}")

        # 结构化发送：old 代发 RTK（已知结构体，长度 194）；bplus 代发其自身的服务/事件
        if table == "old":
            svc, evt, size = ctl.send_struct("RTK", Counter=7, longitude=116.4, latitude=39.9)
            print(f"      RTK 单条 → 0x{svc:04X}:0x{evt:04X} {size} 字节")
            if size != 194:
                failures.append(f"RTK 序列化长度异常：{size}（应 194）")
        else:
            svc, evt = info["sample_event"]
            # send_raw 返回载荷长度；发送失败会抛异常（被外层捕获记为失败）
            size = ctl.send_raw(svc, evt, bytes(8))
            print(f"      原始发送 → 0x{svc:04X}:0x{evt:04X} 8 字节，返回 {size}（载荷长度）")
            if size != 8:
                failures.append(f"bplus 代服务发送异常：返回 {size}")

        # 5) pcap 回放
        pcap = Path(args.pcap) if args.pcap else _default_pcap()
        if pcap is None or not pcap.is_file():
            print("[5/5] pcap 回放：跳过（未找到 pcap；可用 --pcap 指定）")
        else:
            parsed = ctl.play_pcap(pcap, loop=args.loop, interval_ms=args.interval_ms)
            deadline, sent = time.time() + args.timeout, 0
            while time.time() < deadline:
                sent = ctl.refresh_sent()
                if not args.loop and sent >= parsed:
                    break
                if args.loop and sent > 0:
                    break
                time.sleep(0.5)
            print(f"[5/5] pcap 回放：{pcap.name}｜本地解析 {parsed} 条｜库内已发送 {sent} 条")
            if parsed <= 0:
                failures.append("该 pcap 解析不出可回放的通知（换一个 pcap）")
            elif not args.loop and sent < parsed:
                failures.append(f"回放未完成：已发 {sent}/{parsed}")
            else:
                print("      ✓ 回放与本地解析一致")
    except Exception as exc:                                   # noqa: BLE001
        print(f"[失败] 执行异常：{exc}")
        failures.append(str(exc))
    finally:
        try:
            ctl.stop_replay()
            ctl.close()
        except Exception:                                      # noqa: BLE001
            pass

    print("\n=== 结论 ===")
    if failures:
        for f in failures:
            print(f"  ✗ {f}")
        rc = 1
    else:
        print("  ✓ 全部检查通过")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
