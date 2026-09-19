# -*- coding: utf-8 -*-
"""can_core.driver_factory —— 按驱动库**实际导出的接口形态**挑选后端

同一个项目要在三种驱动形态下都能跑：

| 场景                        | 驱动库                        | 接口形态     | 后端                      |
|-----------------------------|-------------------------------|--------------|---------------------------|
| Windows 现场（既有）        | `zlgcan.dll`                  | ZCAN         | `driver.ZCAN`（直连）     |
| Linux + 官方 ZCAN 版驱动    | `libzlgcan.so`                | ZCAN         | `driver.ZCAN`（直连）     |
| Linux + 公开 VCI 版驱动     | `libusbcanfd.so` / `...800u.so` | VCI        | `vci_adapter.VciCanDriver`|
| Linux + 800U（两套都导出）  | `libusbcanfd800u.so`          | ZCAN + VCI   | 视 `ZCAN_SetValue` 是否齐备 |

判定原则：**业务层需要的方法一个都不能少**才算"可用"。
公开的 `libusbcanfd800u.so` 虽有 `ZCAN_*`，但没有业务层用来配波特率的 `ZCAN_SetValue`，
因此仍走 VCI 适配层（否则会出现"能打开设备、波特率配不上"的隐性故障）。
"""
from __future__ import annotations

from hudcore import logging_setup

from . import vci_driver as vd
from .driver import ZCAN
from .vci_adapter import VciCanDriver

_LOGGER = "candata"

# 业务层（receive.py / transmit.py）真正调用的 ZCAN 方法，缺一不可
REQUIRED_ZCAN: tuple[str, ...] = (
    "ZCAN_OpenDevice", "ZCAN_CloseDevice", "ZCAN_InitCAN", "ZCAN_StartCAN",
    "ZCAN_Transmit", "ZCAN_Receive", "ZCAN_GetReceiveNum", "ZCAN_SetValue",
    "ZCAN_GetDeviceInf",
)

# CANFD 设备还需要这些
CANFD_ZCAN: tuple[str, ...] = ("ZCAN_TransmitFD", "ZCAN_ReceiveFD")


def missing_zcan(lib, names: tuple[str, ...] = REQUIRED_ZCAN) -> list[str]:
    """库中缺失的 ZCAN 函数名。"""
    return [n for n in names if not hasattr(lib, n)]


def driver_kind(lib) -> str:
    """根据已加载的库判断接口形态。

    :return: `"zcan"` / `"vci"` / `"zcan+vci"` / `"unknown"`
    """
    if lib is None:
        return "unknown"
    has_zcan = not missing_zcan(lib)
    has_vci = not vd.missing_symbols(lib)
    if has_zcan and has_vci:
        return "zcan+vci"
    if has_zcan:
        return "zcan"
    if has_vci:
        return "vci"
    return "unknown"


def open_can_driver(library_path=None):
    """返回可直接使用的 CAN 驱动对象（方法面与 `driver.ZCAN` 一致）。

    :param library_path: 显式指定驱动库路径（None 时走 `hudcore.can` 的探测链）
    :raises OSError: 库能加载但两套接口都不完整（给出缺哪些符号，便于定位版本问题）
    """
    probe = ZCAN(library_path)                     # 只用于拿到已加载的库对象
    lib = probe.loaded_library
    if lib is None:
        return probe                               # 库都没加载上：保持既有报错行为（打印提示）

    kind = driver_kind(lib)
    if kind in ("zcan", "zcan+vci"):
        logging_setup.info(_LOGGER, f"CAN 驱动接口形态：{kind} → 使用 ZCAN 直连后端")
        return probe

    if kind == "vci":
        logging_setup.info(_LOGGER, "CAN 驱动接口形态：vci（Linux 公开驱动）"
                                    " → 使用 VCI 适配层（can_core.vci_adapter）")
        return VciCanDriver(lib=lib)

    # 形态不完整但至少有 ZCAN 入口：沿用旧行为（ZCAN 直连，调用缺的函数时才报错）。
    # 这样对"接口比我们已知的更多/更少"的驱动变体保持宽容，不会因为判定更严而让现场不可用。
    if hasattr(lib, "ZCAN_OpenDevice"):
        logging_setup.warning(_LOGGER,
                              f"CAN 驱动接口形态不完整（缺 ZCAN: "
                              f"{', '.join(missing_zcan(lib)) or '无'}）→ 仍按 ZCAN 直连使用，"
                              f"调用缺失函数时会报错")
        return probe

    # 两套都不完整：报清楚缺什么，而不是让业务层在调用时才炸
    raise OSError(
        "CAN 驱动库加载成功，但接口形态无法识别：\n"
        f"  · 缺少 ZCAN 函数：{', '.join(missing_zcan(lib)) or '无'}\n"
        f"  · 缺少 VCI 函数：{', '.join(vd.missing_symbols(lib)) or '无'}\n"
        "  Windows 请使用 ZLG 官方 zlgcan.dll；Linux 请使用 libusbcanfd.so（USBCANFD 系列）"
        "或 ZCAN 版 libzlgcan.so；也可用 HUD_ZLG_LIB 指定库路径"
    )


def describe_driver_status() -> str:
    """人类可读的后端状态（用于自检/排障输出）。"""
    from hudcore.can import describe_library_status, find_zlg_library, load_zlg_library

    lib_path = find_zlg_library()
    if lib_path is None:
        return describe_library_status()
    lib = load_zlg_library()
    kind = driver_kind(lib)
    line = f"CAN 驱动：{lib_path}\n  接口形态：{kind}"
    if kind == "vci":
        line += "\n  后端：VCI 适配层（业务代码无需改动；波特率由适配层换算成 ZCAN_INIT 时序）"
    elif kind == "zcan+vci":
        line += "\n  后端：ZCAN 直连（该库同时导出 VCI）"
    elif kind == "zcan":
        line += "\n  后端：ZCAN 直连"
    else:
        line += (f"\n  警告：接口形态无法识别（缺 ZCAN: {', '.join(missing_zcan(lib)) or '无'}；"
                 f"缺 VCI: {', '.join(vd.missing_symbols(lib)) or '无'}）")
    return line


__all__ = [
    "open_can_driver", "driver_kind", "describe_driver_status",
    "missing_zcan", "REQUIRED_ZCAN", "CANFD_ZCAN",
]
