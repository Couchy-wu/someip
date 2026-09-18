# -*- coding: utf-8 -*-
"""
hudcore.platform.system —— OS 探测与平台常量
============================================
替代散落各处的 `platform.system() == "Windows"` 判断，集中一处便于维护。

用法：
    from hudcore.platform.system import IS_WINDOWS, IS_LINUX, exe_suffix
    if IS_WINDOWS: ...
"""
from __future__ import annotations

import platform
import sys

# ---- 平台标志 ----
OS_NAME: str = platform.system()          # "Windows" / "Linux" / "Darwin"
IS_WINDOWS: bool = OS_NAME == "Windows"
IS_LINUX: bool = OS_NAME == "Linux"
IS_MACOS: bool = OS_NAME == "Darwin"

IS_UBUNTU: bool = False
UBUNTU_VERSION: str = ""
if IS_LINUX:
    try:
        # Ubuntu 22.04 -> ("22.04", ...)
        with open("/etc/os-release", "r", encoding="utf-8", errors="ignore") as f:
            info = dict(
                line.strip().split("=", 1)
                for line in f
                if "=" in line and not line.strip().startswith("#")
            )
        _id = info.get("ID", "").strip('"')
        IS_UBUNTU = _id in ("ubuntu", "debian") or "ubuntu" in info.get("ID_LIKE", "")
        UBUNTU_VERSION = info.get("VERSION_ID", "").strip('"')
    except OSError:
        pass

PYTHON_VERSION: str = platform.python_version()

# ---- 命名约定 ----
exe_suffix: str = ".exe" if IS_WINDOWS else ""          # 可执行文件后缀
lib_suffix: str = ".dll" if IS_WINDOWS else ".so"       # 动态库后缀
pathsep: str = ";" if IS_WINDOWS else ":"               # PATH 分隔符


def describe() -> str:
    """返回人类可读的平台描述（用于启动日志/自检）。"""
    parts = [f"OS={OS_NAME}"]
    if IS_UBUNTU and UBUNTU_VERSION:
        parts.append(f"Ubuntu={UBUNTU_VERSION}")
    parts.append(f"Python={PYTHON_VERSION}")
    parts.append(f"arch={platform.machine()}")
    return " ".join(parts)


def supported() -> bool:
    """当前平台是否受支持（Windows / Linux 为正式支持；macOS 尽力支持）。"""
    return IS_WINDOWS or IS_LINUX or IS_MACOS
