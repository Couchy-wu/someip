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
PYTHON_VERSION_INFO: tuple[int, ...] = tuple(sys.version_info[:3])   # 例如 (3, 13, 0)

# ---- Python 版本支持策略 ----
# 3.10（Ubuntu 22.04 自带）~ 3.13（Windows 最新稳定版）为验证过的区间；
# 更低版本缺少本项目使用的语法（X | Y 类型联合、from __future__ 之外的特性），
# 更高版本按"尽力支持"处理。
PYTHON_MIN: tuple[int, int] = (3, 10)
PYTHON_MAX_TESTED: tuple[int, int] = (3, 13)

IS_PY310_PLUS: bool = PYTHON_VERSION_INFO[:2] >= (3, 10)
IS_PY312_PLUS: bool = PYTHON_VERSION_INFO[:2] >= (3, 12)
IS_PY313_PLUS: bool = PYTHON_VERSION_INFO[:2] >= (3, 13)
IS_PY314_PLUS: bool = PYTHON_VERSION_INFO[:2] >= (3, 14)

# 版本相关注意事项（自检 / 启动日志用）
VERSION_NOTES: dict[tuple[int, int], str] = {
    (3, 13): ("Python 3.13 需要 paddlepaddle>=3.2.1（首个提供 cp313 wheel 的版本）；"
              "torch>=2.6 / numpy>=2.1 / opencv-python>=4.10 等其余依赖均已有 cp313 wheel，"
              "详见 docs/PYTHON_COMPATIBILITY.md"),
    (3, 14): ("Python 3.14 尚未验证：paddlepaddle / torch 等可能尚无 wheel，"
              "建议使用 3.10 ~ 3.13"),
}


def python_status() -> tuple[str, str]:
    """返回 (等级, 说明)，等级为 "ok" / "warn" / "error"。

    供 tools/check_env.py 与启动自检复用，避免多处重复判断版本。
    """
    ver = PYTHON_VERSION_INFO[:2]
    lo = f"{PYTHON_MIN[0]}.{PYTHON_MIN[1]}"
    hi = f"{PYTHON_MAX_TESTED[0]}.{PYTHON_MAX_TESTED[1]}"
    if ver < PYTHON_MIN:
        return "error", (f"Python {PYTHON_VERSION} 过低（最低 {lo}），"
                         f"请升级到 Python {lo} ~ {hi}")
    if ver > PYTHON_MAX_TESTED:
        return "warn", VERSION_NOTES.get(
            ver, f"Python {PYTHON_VERSION} 高于已验证区间（{lo} ~ {hi}），按尽力支持")
    note = VERSION_NOTES.get(ver)
    return "ok", (note or f"Python {PYTHON_VERSION} 在支持区间内（{lo} ~ {hi}）")


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
