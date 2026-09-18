# -*- coding: utf-8 -*-
"""
hudcore.ui —— UI 通用层（跨平台）
=================================
  theme            颜色 / 字体 / 尺寸常量与控件样式工厂
  text_redirector  print 输出重定向到 Tk Text（线程安全）

用法：
    from hudcore.ui.theme import Theme
    from hudcore.ui import TextRedirector
    btn = tk.Button(root, text="上传测试用例", **Theme.primary_button())
"""

from .theme import Theme

try:
    from .text_redirector import TextRedirector
except Exception:  # tkinter 缺失（无 GUI 环境）时仍可使用 Theme
    TextRedirector = None  # type: ignore

__all__ = ["Theme", "TextRedirector"]
