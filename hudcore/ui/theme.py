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
    DANGER = "#D9534F"           # 危险/终止类操作（红）
    DANGER_HOVER = "#C9302C"
    SUCCESS = "#5CB85C"          # 数据/工具类操作（绿）
    SUCCESS_HOVER = "#4CAE4C"
    INFO = "#5BC0DE"             # 查询/探测类操作（浅蓝）
    INFO_HOVER = "#31B0D5"
    WARN = "#F0AD4E"             # 暂停/临时操作（橙）
    WARN_HOVER = "#EB983A"
    NEUTRAL = "#6C757D"          # 中性操作（灰）
    NEUTRAL_HOVER = "#5A6268"
    STATE_BG = "#222222"         # 工况显示条：黑底绿字
    STATE_FG = "#00FF00"
    HINT_FG = "#555555"          # 说明文字
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

    @classmethod
    def info_button(cls, **kw: Any) -> Dict[str, Any]:
        """查询/探测类按钮（浅蓝）"""
        return cls._button(cls.INFO, cls.INFO_HOVER, **kw)

    @classmethod
    def warn_button(cls, **kw: Any) -> Dict[str, Any]:
        """暂停/临时操作按钮（橙）"""
        return cls._button(cls.WARN, cls.WARN_HOVER, **kw)

    @classmethod
    def neutral_button(cls, **kw: Any) -> Dict[str, Any]:
        """中性操作按钮（灰）"""
        return cls._button(cls.NEUTRAL, cls.NEUTRAL_HOVER, **kw)

    # ---- 常用小控件样式 ----
    @classmethod
    def hint_label(cls, **kw: Any) -> Dict[str, Any]:
        """说明文字（小号灰字，用于区块内提示）"""
        style: Dict[str, Any] = {
            "font": cls.font_tuple(9, "normal"),
            "fg": cls.HINT_FG,
            "anchor": "w",
            "justify": "left",
        }
        style.update(kw)
        return style

    @classmethod
    def field_label(cls, **kw: Any) -> Dict[str, Any]:
        """表单左侧标签（字段名）"""
        style: Dict[str, Any] = {
            "font": cls.font_tuple(10, "normal"),
            "anchor": "w",
        }
        style.update(kw)
        return style

    @classmethod
    def check_button(cls, **kw: Any) -> Dict[str, Any]:
        """勾选框统一样式（跨平台字体，不再硬编码字体名）"""
        style: Dict[str, Any] = {
            "font": cls.font_tuple(10, "normal"),
            "anchor": "w",
        }
        style.update(kw)
        return style

    @classmethod
    def state_banner(cls, **kw: Any) -> Dict[str, Any]:
        """工况显示条样式（黑底绿字、左对齐）"""
        style: Dict[str, Any] = {
            "font": cls.font_tuple(11, "bold"),
            "bg": cls.STATE_BG,
            "fg": cls.STATE_FG,
            "anchor": "w",
            "padx": 8,
            "pady": 3,
        }
        style.update(kw)
        return style

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
