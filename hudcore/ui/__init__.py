# -*- coding: utf-8 -*-
"""
hudcore.ui —— UI 通用层（跨平台）
=================================
  theme            颜色 / 字体 / 尺寸常量与控件样式工厂
  state            界面按钮状态机（UiState + ButtonGroup，与 Tk 解耦、可单测）
  action_bar       声明式按钮条（ActionBar）与顺序布局（SectionStack）
  layout           布局工具 + "grid 格子冲突"自检（audit_widget_tree）
  text_redirector  print 输出重定向到 Tk Text（线程安全）

界面统一的写法（新代码请照这个来）：

    from hudcore.ui import ActionBar, SectionStack, Theme, UiState

    stack = SectionStack(parent)                 # 行号自动分配，不手写 row
    dev = stack.section("① 设备连接")
    bar = stack.action_bar(columns=3)
    bar.add("init", "初始化设备", self.start_init,
            enabled_when=lambda s: s.idle and not s.flag("device_open"))
    bar.apply(UiState())                         # 用状态刷新可用性

约定：
  · 不要在业务模块里硬编码字体名/颜色 —— 用 Theme；
  · 不要各写各的 ``btn.config(state=...)`` —— 用状态机 + 规则表；
  · 新增/改动布局后跑 ``python -m pytest tests/test_ui_layout.py -q`` 检查格子冲突。
"""

from .theme import Theme
from .state import (
    BUSY_ACT, BUSY_CLOSE, BUSY_EXECUTE, BUSY_INIT, BUSY_NONE, BUSY_PROBE, BUSY_SCAN,
    BUSY_TEST, ButtonGroup, UiState,
)
from .layout import (
    Cell, Collision, audit_widget_tree, describe_collisions, grid_collisions,
    grid_occupancy, section_frame,
)
from .action_bar import ActionBar, SectionStack

try:
    from .text_redirector import TextRedirector
except Exception:  # tkinter 缺失（无 GUI 环境）时仍可使用其余部分
    TextRedirector = None  # type: ignore

__all__ = [
    "Theme",
    "UiState", "ButtonGroup",
    "BUSY_NONE", "BUSY_PROBE", "BUSY_INIT", "BUSY_CLOSE", "BUSY_TEST", "BUSY_SCAN",
    "BUSY_EXECUTE", "BUSY_ACT",
    "ActionBar", "SectionStack",
    "Cell", "Collision", "audit_widget_tree", "describe_collisions",
    "grid_collisions", "grid_occupancy", "section_frame",
    "TextRedirector",
]
