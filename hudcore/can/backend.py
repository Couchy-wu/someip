# -*- coding: utf-8 -*-
"""
hudcore.can —— CAN 驱动抽象层
=============================
把"ZLG CAN 设备驱动库"的加载与调用约定抽出来，实现 Windows / Linux 同一套用法：

  Windows : zlgcan.dll        （stdcall 调用约定 → windll/WinDLL）
  Linux   : libusbcanfd.so / libzlgcan.so（cdecl → CDLL），需 ZLG 官方 Linux 驱动

库文件搜索顺序（可用环境变量 HUD_ZLG_LIB / HUD_ZLG_LIB_DIR 覆盖）：
  1. 环境变量 HUD_ZLG_LIB 指定的完整路径
  2. drivers/<platform>/（项目内按平台存放）
  3. 项目根目录（兼容历史的 ./zlgcan.dll）
  4. 系统库路径（PATH / LD_LIBRARY_PATH / ldconfig 可见）/opt/zlgcan、/usr/local/lib 等

用法：
    from hudcore.can import load_zlg_library, describe_library_status
    dll = load_zlg_library()          # 返回 ctypes 库对象（已加载）
    print(describe_library_status())  # 排障用：打印探测过程与结果
"""
from __future__ import annotations

import ctypes
import os
import platform as _pyplatform
from pathlib import Path
from typing import Optional

from ..platform.system import IS_WINDOWS, IS_LINUX, IS_MACOS
from ..platform.paths import paths

# ---- 各平台候选库文件名（按优先级）----
LIB_CANDIDATES: dict[str, list[str]] = {
    "windows": ["zlgcan.dll", "zlgcan_x64.dll"],
    # ZLG Linux 驱动：新版统一库 libzlgcan.so；旧版按设备分库 libusbcanfd.so
    "linux": ["libzlgcan.so", "libusbcanfd.so", "libusbcan.so", "libcanfd.so"],
    "macos": ["libzlgcan.dylib"],
}

# ---- 系统库搜索目录（Linux）----
EXTRA_SYSTEM_DIRS = [
    Path("/usr/lib"), Path("/usr/local/lib"), Path("/usr/lib/x86_64-linux-gnu"),
    Path("/usr/lib/aarch64-linux-gnu"), Path("/opt/zlgcan"), Path("/opt/zlgcan/lib"),
    Path("/lib"), Path("/usr/lib64"),
]

_last_probe_log: list[str] = []


def _candidates() -> list[str]:
    if IS_WINDOWS:
        return LIB_CANDIDATES["windows"]
    if IS_MACOS:
        return LIB_CANDIDATES["macos"]
    return LIB_CANDIDATES["linux"]


def _search_dirs() -> list[Path]:
    """库搜索目录（项目内优先 → 系统目录）"""
    dirs: list[Path] = []
    env_dir = os.environ.get("HUD_ZLG_LIB_DIR")
    if env_dir:
        dirs.append(Path(env_dir).expanduser())

    dirs.append(paths.drivers_dir)        # drivers/<platform>/
    dirs.append(paths.drivers_all_dir)    # drivers/
    dirs.append(paths.project_root)       # 兼容历史：项目根下的 zlgcan.dll
    dirs.append(Path(paths.project_root) / "libs")

    # LD_LIBRARY_PATH / PATH 中的目录
    for var in ("LD_LIBRARY_PATH", "PATH", "DYLD_LIBRARY_PATH"):
        for d in os.environ.get(var, "").split(os.pathsep):
            if d:
                dirs.append(Path(d))

    if IS_LINUX:
        dirs += EXTRA_SYSTEM_DIRS

    seen, out = set(), []
    for d in dirs:
        try:
            key = str(d)
            if key not in seen and d.exists():
                seen.add(key)
                out.append(d)
        except OSError:
            continue
    return out


def find_zlg_library() -> Optional[Path]:
    """
    探测 ZLG 驱动库文件。返回首个命中的路径，找不到返回 None。
    探测过程记录在 `_last_probe_log`（供 describe_library_status 展示）。
    """
    global _last_probe_log
    _last_probe_log = []

    # 1) 环境变量指定完整路径
    env_path = os.environ.get("HUD_ZLG_LIB")
    if env_path:
        p = Path(env_path).expanduser()
        _last_probe_log.append(f"[env] HUD_ZLG_LIB={env_path} -> {'命中' if p.is_file() else '不存在'}")
        if p.is_file():
            return p

    # 2) 目录 × 候选名
    for d in _search_dirs():
        for name in _candidates():
            p = d / name
            if p.is_file():
                _last_probe_log.append(f"[dir] {d}/{name} -> 命中")
                return p
        _last_probe_log.append(f"[dir] {d} -> 未找到 {'/'.join(_candidates())}")

    # 3) 交给系统加载器（ldconfig / PATH 可见的情况）
    for name in _candidates():
        try:
            ctypes.util.find_library(name.replace("lib", "").replace(".so", "").replace(".dll", ""))
        except Exception:
            pass
    _last_probe_log.append("[system] 未在搜索目录中找到驱动库")
    return None


def load_zlg_library(path: Optional[Path | str] = None):
    """
    加载 ZLG CAN 驱动库并返回 ctypes 库对象。

    - Windows：使用 **WinDLL**（stdcall，与原 `windll.LoadLibrary` 行为一致）
    - Linux  ：使用 **CDLL**（cdecl，ZLG Linux 驱动约定）
    - 传入 path 时按该路径加载；否则自动探测

    :raises FileNotFoundError: 未找到驱动库（附带平台安装提示）
    :raises OSError: 库存在但加载失败（通常是缺少系统依赖，如 libusb）
    """
    lib_path = Path(path) if path else find_zlg_library()
    if not lib_path or not Path(lib_path).is_file():
        raise FileNotFoundError(_not_found_hint())

    loader = ctypes.WinDLL if IS_WINDOWS else ctypes.CDLL
    try:
        return loader(str(lib_path))
    except OSError as e:
        raise OSError(
            f"驱动库加载失败: {lib_path}\n"
            f"  原因: {e}\n"
            f"  排查: {_missing_dependency_hint()}"
        ) from e


def _not_found_hint() -> str:
    names = " / ".join(_candidates())
    if IS_WINDOWS:
        return (f"未找到 ZLG CAN 驱动库（{names}）。\n"
                f"  请将 zlgcan.dll 放到 {paths.drivers_dir} 或项目根目录，\n"
                f"  或设置环境变量 HUD_ZLG_LIB=<dll完整路径>。")
    return (f"未找到 ZLG CAN 驱动库（{names}）。\n"
            f"  Ubuntu 安装步骤：\n"
            f"    1) 从 ZLG 官网下载「USBCANFD Linux 驱动/SDK」\n"
            f"    2) 将 libzlgcan.so 放到 {paths.drivers_dir}（或 /usr/local/lib）\n"
            f"    3) 或设置环境变量 HUD_ZLG_LIB=<so完整路径>\n"
            f"    4) 依赖：sudo apt install -y libusb-1.0-0 libusb-1.0-0-dev\n"
            f"    5) 设备权限：sudo cp <SDK>/99-*  /etc/udev/rules.d/ && sudo udevadm control --reload")


def _missing_dependency_hint() -> str:
    if IS_LINUX:
        return "sudo apt install -y libusb-1.0-0（并用 ldd <so> 检查缺失依赖）"
    return "确认已安装 VC++ 运行库，并检查 dll 是否为 64 位"


def describe_library_status() -> str:
    """返回驱动库探测状态文本（自检/日志用）"""
    found = find_zlg_library()
    lines = [f"平台: {paths.platform_dir_name}  候选: {', '.join(_candidates())}"]
    lines += [f"  {l}" for l in _last_probe_log]
    lines.append(f"结论: {'已找到 -> ' + str(found) if found else '未找到驱动库'}")
    return "\n".join(lines)


def is_library_available() -> bool:
    """驱动库是否就绪（不抛异常的检测）"""
    try:
        return find_zlg_library() is not None
    except Exception:
        return False
