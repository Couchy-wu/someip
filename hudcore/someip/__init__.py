# -*- coding: utf-8 -*-
"""hudcore.someip —— SOME/IP 服务端库的探测与加载

与 `hudcore.can` 同一设计思路：把"库在哪、用哪个加载器"这件事收敛到平台层，
业务代码只调用 `load_someip_library()`。

用法：
    from hudcore.someip import load_someip_library, is_library_available
    lib = load_someip_library()          # 跨平台统一（Windows DLL / Linux .so）

库文件说明：
    Linux   : libarhud_server.so（依赖同目录的 libsomeip*.so，运行时需 LD_LIBRARY_PATH）
    Windows : libarhud_server.dll（**暂无产物**，见 docs/SOMEIP_REPLAY.md：当前留占位，
              加载失败时给出明确提示而不是崩溃）
"""

from .backend import (  # noqa: F401
    LIB_CANDIDATES,
    describe_library_status,
    find_someip_library,
    is_library_available,
    load_someip_library,
)

__all__ = [
    "LIB_CANDIDATES", "find_someip_library", "load_someip_library",
    "describe_library_status", "is_library_available",
]
