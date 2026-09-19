#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/fetch_thirdparty_libs.py —— 第三方运行时库的联网获取助手
==============================================================
项目只把**源码/框架/模型**随仓库分发；**运行时库**（二进制）由部署方按平台获取。
本脚本把"获取"这一步自动化，避免手工到处找库。

支持的获取项：

    zlg       ZLG CAN 的 **Linux** 驱动库（libusbcanfd.so / libusbcan.so / libzuds.so …）
              来源：公开镜像仓库 jesses2025smith/rust-can 的 `zlg-lib` 分支
                    https://github.com/jesses2025smith/rust-can/tree/zlg-lib
              目的：thirdparty/zlg_can/<平台>-<架构>/
              注意：该分支附带的是 **VCI 接口**；本项目驱动走 **ZCAN 接口**，
                    二者不匹配（详见 thirdparty/zlg_can/README.md）。
                    Windows 版驱动（zlgcan.dll, ZCAN 接口）已在仓库中，无需下载。

    someip    SOME/IP 服务端库需要**就地编译**（无公开产物），脚本只打印编译与放置步骤。

用法：
    python tools/fetch_thirdparty_libs.py --list
    python tools/fetch_thirdparty_libs.py zlg                 # 下载并放置到默认位置
    python tools/fetch_thirdparty_libs.py someip              # 打印编译指引
    python tools/fetch_thirdparty_libs.py zlg --dry-run       # 只看会做什么
    python tools/fetch_thirdparty_libs.py zlg --arch x86_64   # 指定架构（默认本机）

依赖：仅标准库（网络访问 GitHub）。
"""
from __future__ import annotations

import argparse
import io
import platform
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ZLG_BRANCH_TARBALL = "https://codeload.github.com/jesses2025smith/rust-can/tar.gz/refs/heads/zlg-lib"
ZLG_SOURCE_PAGE = "https://github.com/jesses2025smith/rust-can/tree/zlg-lib"
ZLG_SUBDIR = "thirdparty/zlg_can"


def _normalize(m: str) -> str:
    """把常见别名归一化：arm64/aarch64 → aarch64；amd64/x64 → x86_64。"""
    m = (m or "").lower()
    if m in ("arm64", "aarch64"):
        return "aarch64"
    if m in ("x86_64", "amd64", "x64"):
        return "x86_64"
    return m or "unknown"


def arch_name(explicit: str | None = None) -> str:
    """归一化架构名（与 hudcore.platform.system.arch_name 一致）。

    注意：显式传入的值同样要归一化 —— `--arch arm64` 与 `--arch aarch64`
    应指向同一目录，否则会把库放错位置。
    """
    if explicit:
        return _normalize(explicit)
    try:
        from hudcore.platform.system import arch_name as _a
        return _a()
    except Exception:                                   # 独立运行时的回退
        return _normalize(platform.machine())


def platform_dir_name() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return sys.platform


def fetch_zlg(arch: str | None, dry: bool) -> int:
    """下载 ZLG Linux 库并放到 thirdparty/zlg_can/<平台>-<架构>/。"""
    arch = arch_name(arch)
    dest = ROOT / ZLG_SUBDIR / f"{platform_dir_name()}-{arch}"
    print(f"== 获取 ZLG Linux 驱动库 ==")
    print(f"   来源: {ZLG_SOURCE_PAGE}")
    print(f"   目标: {dest}")
    if platform_dir_name() != "linux":
        print("   [!] 当前平台不是 Linux：ZLG 的 Windows 驱动已在仓库中（zlgcan.dll / thirdparty/zlg），")
        print("       仍继续下载 Linux 库以便打包给目标机使用。")

    if dry:
        print("   --dry-run：不实际下载")
        return 0

    print("   下载分支压缩包 …")
    try:
        with urllib.request.urlopen(ZLG_BRANCH_TARBALL, timeout=180) as resp:
            data = resp.read()
    except Exception as exc:                            # noqa: BLE001
        print(f"   [错误] 下载失败：{exc}")
        print("   可手动下载后解包，把 library/linux/<架构>/*.so 放到上述目标目录。")
        return 1
    print(f"   已下载 {len(data) / 1024 / 1024:.1f} MB，解包 …")

    dest.mkdir(parents=True, exist_ok=True)
    include = ROOT / ZLG_SUBDIR / "include"
    copied = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            rel = member.name.split("/", 1)[-1]           # 去掉顶层目录
            if rel == f"library/linux/{arch}/" or not rel.startswith(f"library/linux/{arch}/"):
                continue
            if not member.name.endswith(".so"):
                continue
            with tf.extractfile(member) as fh, open(dest / Path(member.name).name, "wb") as out:
                shutil.copyfileobj(fh, out)
            copied += 1
        # 头文件与位速率配置（便于二次开发/对照）
        for member in tf.getmembers():
            if not member.isfile():
                continue
            rel = member.name.split("/", 1)[-1]
            if rel.startswith("library/linux/header/") and rel.endswith(".h"):
                target = include / rel.replace("library/linux/header/", "")
                target.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(member) as fh, open(target, "wb") as out:
                    shutil.copyfileobj(fh, out)
            elif rel == "library/bitrate.cfg.yaml":
                with tf.extractfile(member) as fh, open(ROOT / ZLG_SUBDIR / "bitrate.cfg.yaml", "wb") as out:
                    shutil.copyfileobj(fh, out)
    print(f"   已放置 {copied} 个 .so（含头文件与 bitrate.cfg.yaml）")
    print("   校验：")
    try:
        from hudcore.can import find_zlg_library, library_api_kind, describe_library_status
        lib = find_zlg_library()
        kind = library_api_kind(lib) if lib else "n/a"
        print(f"     find_zlg_library() -> {lib}")
        print(f"     接口类型 -> {kind}")
        if kind == "vci":
            print("     [注意] 该库为 VCI 接口，本项目驱动需要 ZCAN 接口（详见 thirdparty/zlg_can/README.md）")
        elif kind == "error":
            print("     [提示] 加载失败通常是缺少依赖，可设 LD_LIBRARY_PATH 指向该目录后重试")
    except Exception as exc:                            # noqa: BLE001
        print(f"     （校验跳过：{exc}）")
    return 0


def show_someip() -> int:
    """SOME/IP 库没有公开产物，只能就地编译 —— 打印指引。"""
    print("== SOME/IP 服务端库：需就地编译 ==")
    print("   源码：someip 工程的 arhud_python_server/src（C++，链接 vsomeip SP 分支库）")
    print("   步骤：")
    print("     cd <someip>/arhud_python_server/src")
    print("     make libarhud_server.so ARCH=aarch64 SP_LIBS=<SP库目录>   # 或 ARCH=x86_64")
    print("   放置（与 libsomeip*.so 同目录）：")
    print(f"     {ROOT}/thirdparty/arhud_someip/linux-<架构>/")
    print("   运行：LD_LIBRARY_PATH=thirdparty/arhud_someip/linux-<架构> python main.py")
    print("   说明：Windows 版需要 MSVC 编译 libarhud_server.dll（当前暂无产物，界面会给出提示）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="第三方运行时库获取助手")
    ap.add_argument("target", nargs="?", choices=["zlg", "someip", "all"], default=None)
    ap.add_argument("--arch", help="目标架构（默认本机）：aarch64 / x86_64")
    ap.add_argument("--dry-run", action="store_true", help="只显示将要做的事")
    ap.add_argument("--list", action="store_true", help="列出可获取项")
    args = ap.parse_args()

    if args.list or args.target is None:
        print("可获取项：")
        print("  zlg     ZLG CAN 的 Linux 驱动库（公开镜像，VCI 接口）→ thirdparty/zlg_can/<平台>-<架构>/")
        print("  someip  SOME/IP 服务端库（需就地编译，脚本打印步骤）")
        print(f"\n用法：python {Path(__file__).name} zlg [--arch x86_64] [--dry-run]")
        return 0

    rc = 0
    if args.target in ("zlg", "all"):
        rc |= fetch_zlg(args.arch, args.dry_run)
    if args.target in ("someip", "all"):
        rc |= show_someip()
    return rc


if __name__ == "__main__":
    sys.exit(main())
