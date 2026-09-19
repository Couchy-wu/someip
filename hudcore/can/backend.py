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


# 本项目驱动（can_core/driver.py）调用的是 **ZCAN 接口**（ZCAN_OpenDevice 等），
# 与 Windows 版 zlgcan.dll 一致。Linux 上 ZLG 公开提供的 libusbcanfd.so 是 **VCI 接口**
# （VCI_OpenDevice 等），二者不兼容 —— 因此这里按"是否导出 ZCAN_OpenDevice"排序，
# 并在只找到 VCI 库时给出明确提示（见 describe_library_status / _vci_only_hint）。
_ZCAN_ENTRY = "ZCAN_OpenDevice"


_LAST_LOAD_ERROR: str = ""


def library_load_error() -> str:
    """最近一次接口探测时的 dlopen 错误（空字符串表示无错误）。"""
    return _LAST_LOAD_ERROR


def library_api_kind(lib_path: Path | str) -> str:
    """返回库的接口类型："zcan" / "vci" / "unknown" / "error"。

    实现：dlopen 后按导出符号判断（Linux CDLL 把符号暴露为属性，Windows 同理）。
    "error" 表示库本身能定位但**加载失败**（多为缺少依赖，如 libusb-1.0.so），
    具体原因见 `library_load_error()`。
    """
    global _LAST_LOAD_ERROR
    _LAST_LOAD_ERROR = ""
    path = str(lib_path)
    loader = ctypes.WinDLL if IS_WINDOWS else ctypes.CDLL
    try:
        handle = loader(path)
    except OSError as exc:
        _LAST_LOAD_ERROR = str(exc)
        return "error"
    if hasattr(handle, _ZCAN_ENTRY):
        return "zcan"
    if hasattr(handle, "VCI_OpenDevice"):
        return "vci"
    return "unknown"


def _vci_only_hint(lib_path: Path | str) -> str:
    return (
        f"检测到 {lib_path} 是 **VCI 接口**（VCI_OpenDevice 等），"
        f"而本项目驱动需要 **ZCAN 接口**（{_ZCAN_ENTRY} 等，与 Windows 版 zlgcan.dll 一致）。\n"
        "  可选处理：\n"
        "   1) 使用 ZLG 官方 Linux SDK 中的 libzlgcan.so（ZCAN 统一接口）放到\n"
        "      thirdparty/zlg_can/<平台>-<架构>/ 下；\n"
        "   2) 或为本项目补充 VCI 适配层（把 VCI_* 映射到项目驱动所需的接口）；\n"
        "   3) 纯 VCI 场景也可直接用 python-can 的 zlg 后端（pip install zlgcan python-can）。"
    )


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

    # 第三方运行时库统一收纳位置（优先，含按架构区分）
    zlg = paths.thirdparty_dir / "zlg_can"
    dirs.append(zlg / paths.platform_arch_dir_name)   # thirdparty/zlg_can/<平台>-<架构>/
    dirs.append(zlg / paths.platform_dir_name)        # thirdparty/zlg_can/<平台>/
    dirs.append(zlg)                                  # thirdparty/zlg_can/

    dirs.append(paths.drivers_dir)        # drivers/<platform>/（旧位置，兼容）
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

    # 2) 目录 × 候选名：优先返回导出 ZCAN 接口的库；只找到 VCI 库时也返回，
    #    但记录接口类型（调用方可据此给出"接口不匹配"的明确提示）。
    fallback_vci: Optional[Path] = None
    fallback_broken: Optional[Path] = None
    for d in _search_dirs():
        for name in _candidates():
            p = d / name
            if not p.is_file():
                continue
            kind = library_api_kind(p)
            _last_probe_log.append(f"[dir] {p} -> 命中（接口={kind}）")
            if kind in ("zcan", "unknown"):
                return p
            if kind == "vci":
                fallback_vci = fallback_vci or p
            else:                       # error：文件在但加载不了（多为缺依赖）
                fallback_broken = fallback_broken or p
                _last_probe_log.append(
                    f"[warn] {p.name} 加载失败：{library_load_error()}"
                    f"（可设 LD_LIBRARY_PATH 指向该目录后重试）")
        _last_probe_log.append(f"[dir] {d} -> 未找到 {'/'.join(_candidates())}")
    if fallback_vci is not None:
        _last_probe_log.append(f"[warn] 只找到 VCI 接口库：{fallback_vci}")
        return fallback_vci
    if fallback_broken is not None:     # 最后兜底：让调用方拿到路径以便展示真实原因
        _last_probe_log.append(f"[warn] 仅找到加载失败的库：{fallback_broken}")
        return fallback_broken

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
    kind = library_api_kind(found) if found else "unknown"
    lines = [f"平台: {paths.platform_dir_name}({paths.platform_arch_dir_name})"
             f"  候选: {', '.join(_candidates())}"]
    lines += [f"  {l}" for l in _last_probe_log]
    if not found:
        lines.append("结论: 未找到驱动库")
    elif kind == "error":
        lines.append(f"结论: 已找到 {found}，但加载失败")
        lines.append(f"  原因: {library_load_error()}")
        lines.append(f"  排查: {_missing_dependency_hint()}")
    elif kind == "vci":
        lines.append(f"结论: 已找到 {found}（接口=VCI，与本项目驱动不匹配）")
        lines.append("  " + _vci_only_hint(found).replace("\n", "\n  "))
    else:
        lines.append(f"结论: 已找到 {found}（接口={kind}）")
    return "\n".join(lines)


def is_library_available() -> bool:
    """驱动库是否就绪（不抛异常的检测）"""
    try:
        return find_zlg_library() is not None
    except Exception:
        return False
