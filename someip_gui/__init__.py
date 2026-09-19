# -*- coding: utf-8 -*-
"""someip_gui —— SOME/IP 回放界面（独立窗口）

布局（见 replay_window.py 头部示意图）：
    左：① 网络与 SD 配置   ② 服务/事件勾选（勾选=注册）
    右：③ pcap 回放控制    ④ 单条发送（结构化字段自动生成）
        ⑤ 操作与报文日志

模块划分：
    field_table.py   结构化发送的字段编辑器（按 ctypes 结构体自动生成）
    panel_config.py  左侧配置面板（ConfigPanelMixin）
    panel_control.py 右侧控制面板（ControlPanelMixin）
    replay_window.py 窗口主类（布局组装 + 生命周期 + 异常提示）

依赖约束：可依赖 someip_core（业务）与 hudcore（平台/UI）；不反向依赖 gui_handlers。

用法（main.py 中）：
    from someip_gui import open_replay_window
    win = open_replay_window(self.root)      # 返回 Toplevel（已绑定关闭清理）
"""
from __future__ import annotations

import tkinter as tk

from .replay_window import SomeipReplayWindow

__all__ = ["SomeipReplayWindow", "open_replay_window"]


def open_replay_window(master: tk.Misc, selected_file=None) -> tk.Toplevel:
    """打开 SOME/IP 回放窗口，返回 Toplevel。

    返回的 Toplevel 上挂了 `someip_app` 属性（窗口对象），
    调用方关闭窗口时应执行 `win.someip_app.on_closing()`，
    以保证"停回放 → 停服务 → 销毁实例 → 保存配置"的清理顺序。
    """
    app = SomeipReplayWindow(master, selected_file=selected_file)
    app.window.someip_app = app
    return app.window
