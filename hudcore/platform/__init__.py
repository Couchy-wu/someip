# -*- coding: utf-8 -*-
"""
hudcore.platform —— 平台抽象层
==============================
统一 Windows / Linux / macOS 的差异：OS 探测、路径、外部可执行程序、字体。

模块：
  system        —— OS 常量与运行时信息
  paths         —— 项目路径 / 用户目录 / 输出目录（自动创建）
  executables   —— 外部程序探测（ffmpeg、Office、文本编辑器、终端）
  fonts         —— Tk 界面字体（跨平台回退链）
"""

from .system import (
    IS_WINDOWS, IS_LINUX, IS_MACOS, OS_NAME, PYTHON_VERSION,
    exe_suffix, lib_suffix, pathsep, describe as describe_platform,
)
from .paths import paths, Paths          # 实例优先：from hudcore.platform import paths
from . import executables                # noqa: F401  （模块：hudcore.platform.executables.*）
from . import fonts                      # noqa: F401  （模块：hudcore.platform.fonts.*）
from .executables import (
    find_executable, open_with_default_app, open_in_text_editor,
    get_ffmpeg, get_office_app, get_terminal,
)
from .fonts import (get_ui_font, get_ui_font_name, list_available_fonts,
                    get_cjk_font_path, load_pil_font)

__all__ = [
    "IS_WINDOWS", "IS_LINUX", "IS_MACOS", "OS_NAME", "PYTHON_VERSION",
    "exe_suffix", "lib_suffix", "pathsep", "describe_platform",
    "paths", "Paths", "executables", "fonts",
    "find_executable", "open_with_default_app", "open_in_text_editor",
    "get_ffmpeg", "get_office_app", "get_terminal",
    "get_ui_font", "get_ui_font_name", "list_available_fonts",
    "get_cjk_font_path", "load_pil_font",
]
