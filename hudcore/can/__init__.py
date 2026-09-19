# -*- coding: utf-8 -*-
"""
hudcore.can —— CAN 驱动抽象层
=============================
  backend   驱动库探测与加载（Windows DLL / Linux .so，含同目录依赖预加载）

用法：
    from hudcore.can import load_zlg_library
    dll = load_zlg_library()     # 跨平台统一加载 ZLG 驱动库
"""

from .backend import (
    preload_sibling_libraries,
    load_zlg_library,
    find_zlg_library,
    describe_library_status,
    is_library_available,
    library_api_kind,
    library_load_error,
    LIB_CANDIDATES,
)

__all__ = [
    "load_zlg_library", "find_zlg_library",
    "describe_library_status", "is_library_available", "library_api_kind",
    "library_load_error", "LIB_CANDIDATES", "preload_sibling_libraries",
]
