# -*- coding: utf-8 -*-
"""
hudcore.can —— CAN 驱动抽象层
=============================
  backend   驱动库探测与加载（Windows DLL / Linux .so）

用法：
    from hudcore.can import load_zlg_library
    dll = load_zlg_library()     # 跨平台统一加载 ZLG 驱动库
"""

from .backend import (
    load_zlg_library,
    find_zlg_library,
    describe_library_status,
    is_library_available,
    LIB_CANDIDATES,
)

__all__ = [
    "load_zlg_library", "find_zlg_library",
    "describe_library_status", "is_library_available", "LIB_CANDIDATES",
]
