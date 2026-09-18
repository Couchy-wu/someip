# -*- coding: utf-8 -*-
"""
hudcore.ui.theme —— 统一 UI 主题（跨平台字体 + 配色）
=====================================================
把原先散落在 main.py / 各 GUI 模块里的字体名、颜色值集中管理：

  · 字体：走 hudcore.platform.fonts 的回退链（Windows 微软雅黑 / Ubuntu Noto Sans CJK 等）
  · 颜色：主色/危险色/成功色 + 各自 hover 色
  · 控件样式：primary_button() / danger_button() / success_button() 直接展开给 Tk 控件

用法：
    from hudcore.ui.theme import Theme
    tk.Button(root, text="上传测试用例", **Theme.primary_button(width=15, height=2))
"""
from __future__ import annotations

from typing import Any, Dict

from ..platform.fonts import get_ui_font, get_ui_font_name, get_ui_font_tuple


class Theme:
    """颜色与字体常量（类属性，可被业务覆盖）"""

    # ---- 配色 ----
    PRIMARY = "#4A90E2"          # 主操作（蓝）
    PRIMARY_HOVER = "#357ABD"
    DANGER = "#D9534F"           # 图像/视频类操作（红）
    DANGER_HOVER = "#C9302C"
    SUCCESS = "#5CB85C"          # 数据/工具类操作（绿）
    SUCCESS_HOVER = "#4CAE4C"
    BG_LIGHT = "#F0F0F0"
    FG_DARK = "#000000"
    FG_WHITE = "#FFFFFF"
    LOG_BG = "#FFFFFF"

    # ---- 字体 ----
    @staticmethod
    def font_name() -> str:
        """当前平台可用的界面字体名"""
        return get_ui_font_name()

    @staticmethod
    def font(size: int = 10, weight: str = "normal", root=None):
        """tkinter.font.Font 对象"""
        return get_ui_font(size=size, weight=weight, root=root)

    @staticmethod
    def font_tuple(size: int = 10, weight: str = "normal") -> tuple:
        """(family, size, weight)，可直接用于 font= 参数"""
        return get_ui_font_tuple(size=size, weight=weight)

    # ---- 控件样式工厂 ----
    @classmethod
    def _button(cls, bg: str, hover: str, **kw: Any) -> Dict[str, Any]:
        style: Dict[str, Any] = {
            "bg": bg,
            "fg": cls.FG_WHITE,
            "activebackground": hover,
            "font": cls.font_tuple(10, "normal"),
            "width": 15,
            "height": 2,
        }
        style.update(kw)
        return style

    @classmethod
    def primary_button(cls, **kw: Any) -> Dict[str, Any]:
        """主操作按钮（蓝）"""
        return cls._button(cls.PRIMARY, cls.PRIMARY_HOVER, **kw)

    @classmethod
    def danger_button(cls, **kw: Any) -> Dict[str, Any]:
        """图像/视频类按钮（红）"""
        return cls._button(cls.DANGER, cls.DANGER_HOVER, **kw)

    @classmethod
    def success_button(cls, **kw: Any) -> Dict[str, Any]:
        """数据/工具类按钮（绿）"""
        return cls._button(cls.SUCCESS, cls.SUCCESS_HOVER, **kw)

    # ---- 文本控件 ----
    @classmethod
    def log_text_style(cls, **kw: Any) -> Dict[str, Any]:
        """日志文本框样式"""
        style: Dict[str, Any] = {
            "wrap": "word",
            "bg": cls.LOG_BG,
            "fg": cls.FG_DARK,
            "insertbackground": "black",
            "font": cls.font_tuple(10, "normal"),
            "height": 20,
            "width": 35,
        }
        style.update(kw)
        return style

    @classmethod
    def label_style(cls, bold: bool = False, **kw: Any) -> Dict[str, Any]:
        """标签样式"""
        style: Dict[str, Any] = {
            "font": cls.font_tuple(10, "bold" if bold else "normal"),
            "bg": cls.BG_LIGHT,
            "fg": cls.FG_DARK,
            "anchor": "w",
            "relief": "flat",
            "height": 1,
        }
        style.update(kw)
        return style
