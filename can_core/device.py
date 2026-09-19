# -*- coding: utf-8 -*-
"""can_core.device —— CAN 设备操作的公共门面（对外接口保持稳定）

拆分说明
--------
原 `device.py`（1100 余行过程式模块）把设备接入、报文收发、位处理与全局状态
混在一起。现按关注点拆分为：

    can_core/can_state.py   共享运行状态（线程开关、接收缓存、锁、驱动实例，单例）
    can_core/bit_utils.py  位/字节工具（纯函数，无设备依赖）
    can_core/receive.py    设备/通道建立与接收（接收线程、信号等待、初始化/关闭）
    can_core/transmit.py   报文发送与周期发送（单帧/信号级/自动发送）
    can_core/device.py     ← 本文件：门面，统一对外导出上述能力

对外兼容性：既有调用方
    from can_core import device
    device.Send_Can_Signal(...) / device.Initialize_Canfd_Device(...) / device.extract_bits_from_data(...)
全部保持不变。

支持的设备：USBCANFD-100U mini / USBCANFD-100U/200U/400U/800U
"""
from __future__ import annotations

# ---- 位处理（纯函数） ----
from .bit_utils import calculate_bit_length, extract_bits_from_data
# ---- 设备接入与接收 ----
from .receive import (
    Close_Canfd_Device,
    Initialize_Canfd_Device,
    Read_Device_Info,
    Set_Device_Name,
    USBCANFD_Start,
    check_signal_received,
    receive_thread,
    wait_for_check_signal_by_bit_enum,
    wait_for_check_signal_received,
)
# ---- 共享状态 ----
from .can_state import CanState, state
# ---- 报文发送 ----
from .transmit import (
    Auto_Send_Can,
    Auto_Send_Can_Or_Canfd,
    Auto_Send_Canfd,
    Clear_Auto_Can_Send,
    Enable_Auto_Can_Send,
    Remove_Auto_Send_By_Index,
    Send_Can,
    Send_Can_Or_Canfd,
    Send_Can_Signal,
    Send_Can_With_Dynamic_Interval,
    Send_Canfd,
)

__all__ = [
    # 位处理
    "extract_bits_from_data", "calculate_bit_length",
    # 状态
    "state", "CanState",
    # 设备接入与接收
    "Read_Device_Info", "Set_Device_Name", "receive_thread", "check_signal_received",
    "wait_for_check_signal_received", "wait_for_check_signal_by_bit_enum",
    "USBCANFD_Start", "Initialize_Canfd_Device", "Close_Canfd_Device",
    # 报文发送
    "Send_Can", "Send_Canfd", "Clear_Auto_Can_Send", "Enable_Auto_Can_Send",
    "Auto_Send_Can", "Auto_Send_Canfd", "Send_Can_Or_Canfd", "Auto_Send_Can_Or_Canfd",
    "Remove_Auto_Send_By_Index", "Send_Can_With_Dynamic_Interval", "Send_Can_Signal",
]
