# -*- coding: utf-8 -*-
"""can_core —— CAN 设备基础设施（ZLG 驱动绑定 + 设备/通道收发）

driver.py   ZLG 驱动 Python 绑定（结构体、常量、库加载：Windows DLL / Linux .so）
  device.py   设备与通道操作（打开/关闭、周期发送、接收线程、信号级收发）

依赖约束：上层（gui_handlers / can_gui / main）可依赖本包；
          本包不反向依赖界面层（保持可测试、可复用）。
说明：本文件只声明包边界与职责，不在导入时引入重依赖（无副作用）。
"""

# 公共 API：CAN 设备操作的常用入口（显式导出，避免使用者依赖内部模块路径）
from .driver import (  # noqa: F401
    ZCAN, ZCAN_USBCANFD_200U, ZCAN_TYPE_CAN, ZCAN_TYPE_CANFD, ZCAN_STATUS_OK,
)
from .device import (  # noqa: F401
    Initialize_Canfd_Device, Close_Canfd_Device, Send_Can_Signal,
    Send_Can_Or_Canfd, wait_for_check_signal_received,
    extract_bits_from_data, calculate_bit_length,
)
from .can_state import CanState, state  # noqa: F401

__all__ = [
    # 驱动与设备操作
    "ZCAN", "ZCAN_USBCANFD_200U", "ZCAN_TYPE_CAN", "ZCAN_TYPE_CANFD",
    "ZCAN_STATUS_OK", "Initialize_Canfd_Device", "Close_Canfd_Device",
    "Send_Can_Signal", "Send_Can_Or_Canfd", "wait_for_check_signal_received",
    # 位工具
    "extract_bits_from_data", "calculate_bit_length",
    # 共享状态（原 received_messages / thread_flag 裸全局已收敛到 state）
    "state", "CanState",
    # 子模块
    "driver", "device", "can_state", "receive", "transmit", "bit_utils",
]
from . import bit_utils, can_state, driver, receive, transmit  # noqa: E402,F401
