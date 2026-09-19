# -*- coding: utf-8 -*-
"""hudcore.someip.backend —— SOME/IP 服务端库的探测与加载（跨平台）

搜索顺序（先命中先用）：
    1. 环境变量 HUD_SOMEIP_LIB / ARHUD_LIB_PATH（完整文件路径，便于现场临时替换）
    2. 环境变量 HUD_SOMEIP_LIB_DIR（所在目录）
    3. 项目内 drivers/someip/<平台>/      （随项目分发的库）
    4. 项目内 vendor/arhud_someip/<平台>/ （备用位置）
    5. 项目根目录
    6. 系统库路径（LD_LIBRARY_PATH / 系统目录，由动态加载器自行查找）

加载器选择：
    Windows → ctypes.WinDLL（stdcall；本库导出为 C 接口，x64 下与 CDLL 等价）
    Linux   → ctypes.CDLL

注意（现状）：Windows 侧 **暂无 DLL 产物**（需要 MSVC 编译，见 docs/SOMEIP_REPLAY.md），
因此 Windows 上会走"找不到库 → 返回 None + 修复提示"的路径，界面会显示明确的
不可用提示而不是崩溃。
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Optional

from ..platform.paths import paths
from ..platform.system import IS_WINDOWS, lib_suffix

# 库文件名候选（按平台生成，保留多种命名以便兼容不同构建产物）
LIB_CANDIDATES: tuple[str, ...] = (
    f"libarhud_server{lib_suffix}",
    f"arhud_server{lib_suffix}",
)

# 环境变量（两个都支持：HUD_* 为本项目约定，ARHUD_* 为原 someip 工程约定）
_ENV_FILE = ("HUD_SOMEIP_LIB", "ARHUD_LIB_PATH")
_ENV_DIR = ("HUD_SOMEIP_LIB_DIR", "ARHUD_LIB_DIR")

# 已缓存的加载结果（避免重复 dlopen）
_CACHE: dict[str, object] = {}


def _search_dirs() -> list[Path]:
    """按优先级列出搜索目录（不存在的会被过滤掉）。"""
    dirs: list[Path] = []
    for env in _ENV_DIR:
        v = os.environ.get(env)
        if v:
            dirs.append(Path(v))
    dirs += [
        paths.drivers_dir / "someip",                  # drivers/<平台>/someip/
        paths.project_root / "vendor" / "arhud_someip" / paths.platform_dir_name,
        paths.project_root / "vendor" / "arhud_someip",
        paths.project_root,
    ]
    return [d for d in dirs if d]


def find_someip_library() -> Optional[Path]:
    """返回可用的库文件路径；找不到返回 None。"""
    # 1) 环境变量直接指定文件
    for env in _ENV_FILE:
        v = os.environ.get(env)
        if v:
            p = Path(v).expanduser()
            if p.is_file():
                return p
    # 2) 目录搜索
    for d in _search_dirs():
        if not d.is_dir():
            continue
        for name in LIB_CANDIDATES:
            p = d / name
            if p.is_file():
                return p
    return None


def load_someip_library(path: Optional[Path | str] = None):
    """加载 SOME/IP 服务端库并返回句柄；未找到时返回 None（不抛异常）。

    :param path: 显式指定库文件（覆盖自动探测）
    """
    key = str(path) if path else "<auto>"
    if key in _CACHE:
        return _CACHE[key]

    target = Path(path) if path else find_someip_library()
    if target is None or not Path(target).is_file():
        _CACHE[key] = None
        return None

    try:
        if IS_WINDOWS:
            handle = ctypes.WinDLL(str(target))
        else:
            handle = ctypes.CDLL(str(target))
    except OSError as exc:                      # 依赖缺失 / 架构不符
        print(f"[SOME/IP] 库加载失败：{target}\n         {exc}\n"
              f"         提示：Linux 需把 libsomeip*.so 与 libarhud_server.so 放在同一目录，"
              f"并设置 LD_LIBRARY_PATH；Windows 需提供 libarhud_server.dll")
        _CACHE[key] = None
        return None

    _CACHE[key] = handle
    return handle


def is_library_available() -> bool:
    """库是否已就绪（可加载）。"""
    return load_someip_library() is not None


def describe_library_status() -> str:
    """人类可读的库状态描述（用于界面状态栏/自检输出）。"""
    lib = find_someip_library()
    if lib is None:
        return _not_found_hint()
    handle = load_someip_library()
    if handle is None:
        return f"SOME/IP 库已找到但加载失败：{lib}"
    return f"SOME/IP 库就绪：{lib}"


def _not_found_hint() -> str:
    """找不到库时的中文修复提示（区分平台，Windows 说明暂无产物）。"""
    names = " / ".join(LIB_CANDIDATES)
    where = "drivers/someip/windows/" if IS_WINDOWS else "drivers/someip/linux/"
    lines = [f"未找到 SOME/IP 服务端库（{names}）"]
    if IS_WINDOWS:
        lines += [
            f"  1) 把 libarhud_server.dll 放到 {where}（或设置 HUD_SOMEIP_LIB=<完整路径>）",
            "  2) 当前仓库**暂无 Windows DLL 产物**：需用 MSVC 编译 arhud_python_server",
            "     （编译方式见 docs/SOMEIP_REPLAY.md「Windows 支持」一节）",
            "  3) 临时替代：在 Ubuntu 上运行本功能，或用 WSL/容器承载 SOME/IP 回放",
        ]
    else:
        lines += [
            f"  1) 把 libarhud_server.so 与 libsomeip*.so 放到 {where}"
            f"（或设置 HUD_SOMEIP_LIB=<完整路径>）",
            "  2) 运行前设置 LD_LIBRARY_PATH 指向同一目录（SP 版 libsomeip 由插件方式加载）",
            "  3) 就地编译：arhud_python_server/src 下 `make libarhud_server.so`",
        ]
    return "\n".join(lines)


def platforms_note() -> str:
    """在界面上展示的简短说明（当前平台库是否具备）。"""
    if IS_WINDOWS and find_someip_library() is None:
        return "Windows 暂缺 libarhud_server.dll（留占位，稍后补上）"
    if sys.platform.startswith("linux") and find_someip_library() is None:
        return "未发现 libarhud_server.so（请按提示放置或编译）"
    return describe_library_status()
