# -*- coding: utf-8 -*-
"""tests.gui_support —— GUI 用例的公共前置检查（无图形环境时整模块跳过）

为什么需要它：

  · Tk 在 Linux/macOS 上必须有显示服务（容器里由 Xvfb 提供），没有就会
    `_tkinter.TclError: no display name and no $DISPLAY environment variable`
    ——这不是"测试失败"，而是"环境不具备"，应当 SKIP 而不是 ERROR；
  · **Windows 本机不需要 DISPLAY**（Tk 走 Win32），所以不能简单地按
    "有没有 DISPLAY 环境变量"判断，否则在真实 Windows 机器上会把界面用例全部跳过
    （在 Wine 验证容器里 DISPLAY 由 Xvfb 提供，不受影响）。

用法（放在测试模块的 import 段，`import pytest` 之后）：

    from tests import gui_support
    tk = pytest.importorskip("tkinter")
    gui_support.require_display()
"""
from __future__ import annotations

import os
import sys

__all__ = ["display_available", "require_display"]


def display_available() -> bool:
    """当前环境能否创建 Tk 窗口（Windows 本机恒为 True，无需 DISPLAY）。"""
    if sys.platform.startswith("win"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def require_display(reason: str = "无显示环境（需 Xvfb/桌面），跳过 GUI 测试") -> None:
    """无图形环境时整模块跳过（只在模块导入期调用）。"""
    if display_available():
        return
    import pytest

    pytest.skip(reason, allow_module_level=True)
