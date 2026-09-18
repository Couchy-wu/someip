# -*- coding: utf-8 -*-
"""
hudcore —— HudAutoTest 核心公共层（平台无关 / 跨平台适配）
==========================================================
设计目标：
  1. **模块化**：把平台相关、可复用的能力从业务代码里抽出来，业务只调用统一接口；
  2. **通用性**：Windows / Ubuntu 22.04(及主流 Linux) / macOS 同一套调用方式；
  3. **零破坏**：原有模块（main.py / can_control.py / gui_handlers/* 等）保持可用，
     只需把平台相关的几行替换为 hudcore 调用。

子包：
  hudcore.platform     平台探测、路径、外部程序、字体
  hudcore.can          CAN 驱动后端抽象（ZLG Windows DLL / Linux .so）
  hudcore.ui           UI 通用工具（跨平台字体、DPI 等）

快速使用：
    from hudcore.platform import IS_WINDOWS, IS_LINUX, paths, find_executable, get_ui_font
    from hudcore.can import load_zlg_library, ZCANBackend
"""

__version__ = "1.0.0"

from . import platform  # noqa: F401
from . import can       # noqa: F401
