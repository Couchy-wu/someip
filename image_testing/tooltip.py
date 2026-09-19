# -*- coding: utf-8 -*-
"""image_testing.tooltip —— 通用悬浮提示控件

从 sample_image_generator.py 拆出：一个与业务无关的小部件，
其它界面（图标管理器、用例表格等）也可直接复用。
"""
import tkinter as tk


class Tooltip:
    """工具提示类：为任意 Tkinter 控件添加鼠标悬停提示"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        # 绑定事件：鼠标进入、离开、点击时显示/隐藏提示
        widget.bind("<Enter>", self.showtip)
        widget.bind("<Leave>", self.hidetip)
        widget.bind("<ButtonPress>", self.hidetip)
    def showtip(self, event=None):
        """显示提示框"""
        # 获取控件位置
        x, y, cx, cy = self.widget.bbox("insert")
        # 计算提示框位置（控件右下方）
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        # 创建无边框顶层窗口
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # 无窗口边框
        tw.wm_geometry("+%d+%d" % (x, y))  # 定位
        # 创建提示文本标签
        label = tk.Label(tw, text=self.text, justify="left",
                        background="#ffffe0", relief="solid", borderwidth=1,
                        font=("微软雅黑", 9))
        label.pack(ipadx=1)
    def hidetip(self, event=None):
        """隐藏提示框"""
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None
