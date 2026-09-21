# -*- coding: utf-8 -*-
"""can_gui.can_send_receive_gui —— CAN 信号自动收发界面（主类）

本模块只做**组装**，具体职责分给四个 Mixin：

    LayoutMixin     界面布局 + 按钮状态机      → can_gui/gui_layout.py
    CameraMixin     相机采集与图像处理          → can_gui/gui_camera.py
    TestFlowMixin   设备收发与测试流程编排      → can_gui/gui_test_flow.py
    ConfigMixin     配置读写与设备管理子窗口     → can_gui/gui_config.py

组装顺序（也是阅读顺序）：
    1. 建窗口、记录传入的用例选择器；
    2. ``_init_ui_state()`` 建立界面状态变量（不碰设备、不起线程）；
    3. ``_build_ui()`` 建界面（控件坐标沿用改造前的既有摆放，见 gui_layout 模块文档）；
    4. 启动两个常驻后台线程（相机采集、图标校验）；
    5. 拦截窗口关闭（必须先关闭设备，避免 CAN 资源泄漏）。

按钮可用性不在这里逐条 config：所有按钮在 gui_layout 的规则表里声明，
动作只改 :class:`hudcore.ui.state.UiState`（busy / testing / device_open），
由 ``_apply_ui_state()`` 统一刷新。
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk

from can_gui.gui_layout import LayoutMixin          # noqa: E402  —— 界面与按钮状态
from can_gui.gui_camera import CameraMixin          # noqa: E402  —— 相机与图像处理
from can_gui.gui_test_flow import TestFlowMixin     # noqa: E402  —— 测试流程与设备收发
from can_gui.gui_config import ConfigMixin          # noqa: E402  —— 配置与子窗口

#: 判断是否被 import 调用（独立运行时可据此做额外处理）
IS_STANDALONE = __name__ == "__main__"


class CANFDGUI(LayoutMixin, CameraMixin, TestFlowMixin, ConfigMixin):
    """CAN 信号自动收发界面（主类）。"""

    def __init__(self, root, selected_file=None):
        self.root = root
        self.root.title("CANFD 设备控制")
        self.root.geometry("1500x800")     # 与改造前一致

        # 用例选择器：被 main.py 调用时复用主窗口的 StringVar，独立运行时自建
        self.selected_file = (tk.StringVar(value="无文件") if selected_file is None
                              else selected_file)

        # ---------- 常驻线程的开关与队列（相机、图标校验）----------
        self._verification_queue = queue.Queue()          # 每帧变换后的图像
        self._stop_verification = threading.Event()       # 关闭 GUI 时停止校验线程
        self._verification_thread = threading.Thread(
            target=self._verification_worker,
            daemon=True,
        )

        # ---------- 状态变量（ui 层）----------
        self._init_ui_state()

        # ---------- 界面 ----------
        self._build_ui()

        # ---------- 常驻后台线程 ----------
        self._verification_thread.start()                 # 图标校验线程
        self._camera_thread = threading.Thread(
            target=self._run_camera_viewer, daemon=True
        )
        self._camera_thread.start()                       # 相机采集线程（始终运行）

        # 拦截窗口关闭事件：必须先关闭设备
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
