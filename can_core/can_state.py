# -*- coding: utf-8 -*-
"""can_core.can_state —— CAN 层的共享运行状态（单例）

模块名说明：本模块提供单例 `state`；若命名为 can_core/state.py，则包级导出的
`from can_core import state` 会因同名而拿到"对象"而非"模块"，容易误用，故改名 can_state。

为什么单独成模块：
  原 device.py 把线程开关、接收缓存、锁、驱动实例等全局变量与业务函数放在
  同一个文件里。拆分模块后，如果每个模块各自 `from device import thread_flag`，
  赋值（如关闭设备时置 False）只会改到自己模块里的那份拷贝，接收线程读到的
  仍是旧值 —— 这类"状态分裂"极难排查。
  因此把这些可变状态集中到一个单例对象，所有模块统一读写 `state.xxx`。

同时把 ZCAN 驱动实例改为**惰性创建**：原实现在导入 device.py 时就 `ZCAN()`，
  会立刻尝试加载驱动库并打印 "DLL couldn't be loaded!"（导入副作用）。
  现在只在真正需要时才实例化，导入阶段保持干净。
"""
from __future__ import annotations

import logging
import threading
from collections import deque

from hudcore import logging_setup

from .driver_factory import open_can_driver

# ------------------------------------------------------------------ 日志
# 与原实现保持一致：CAN 层使用名为 "candata" 的 logger，日志落在 <项目根>/logs/can
try:                                       # 优先使用 hudcore 统一路径
    from hudcore.platform.paths import paths
    LOG_PATH = str(paths.logs_dir / "can")
except Exception:                          # 独立拷贝使用时的回退
    LOG_PATH = "./logs/can"

logging_setup.setup_logger(logger_name="candata", log_dir=LOG_PATH,
                           log_prefix="candata", level=logging.INFO, clear_old=True)


class CanState:
    """CAN 层共享状态（进程内单例）。

    属性说明：
        thread_flag           接收线程运行标志（关闭设备时置 False）
        print_lock            打印串行化锁，避免多线程输出交错
        enable_merge_receive  合并接收标志（0 关闭）
        transmit_type         0-正常发送，2-自发自收
        received_messages     最近收到的报文缓存（最多 1000 条）
        received_messages_lock 缓存读写锁
        zcanlib               驱动库封装实例（惰性创建，见下方 property）
        handle                最近一次打开的设备句柄（由 Initialize_Canfd_Device 写入，
                              供 Set_Device_Name 等函数使用；原为模块级 global handle）
    """

    def __init__(self) -> None:
        self.handle = None
        self.thread_flag = True
        self.print_lock = threading.Lock()
        self.enable_merge_receive = 0
        self.transmit_type = 0
        self.received_messages: deque = deque(maxlen=1000)
        self.received_messages_lock = threading.Lock()
        self._zcanlib = None

    @property
    def zcanlib(self):
        """CAN 驱动实例：首次访问时才创建（避免导入期加载驱动库）。

        返回的对象由 `can_core.driver_factory.open_can_driver()` 按驱动库**实际导出的
        接口形态**决定：

            Windows `zlgcan.dll` / ZCAN 版 Linux 库 → `driver.ZCAN`（ZCAN 直连）
            Linux 公开 VCI 版库（libusbcanfd.so） → `vci_adapter.VciCanDriver`（VCI 适配）

        两者方法面一致，因此业务代码（receive.py / transmit.py）无需区分平台。
        """
        if self._zcanlib is None:
            self._zcanlib = open_can_driver()
        return self._zcanlib

    def reset_for_tests(self) -> None:
        """复位状态（供自动化测试使用；不触碰已创建的驱动实例）。"""
        self.handle = None
        self.thread_flag = True
        self.enable_merge_receive = 0
        self.transmit_type = 0
        self.received_messages.clear()


# 进程内单例：所有 CAN 模块统一使用 `from .state import state`
state = CanState()
