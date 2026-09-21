# -*- coding: utf-8 -*-
"""can_gui.gui_layout —— CAN 界面布局与按钮状态机（Mixin）

本模块承担两件事，二者互不干扰：

1. **布局**：控件位置**沿用改造前的既有摆放**（与 `7219d2d` 一致）——
   全部控件直接 `grid` 到 root 上，摄像头画面在右侧第 4 列（1~5 行）、
   变换后画面在其下方（6~10 行），左侧 0~2 行是设备/供电/测试按钮，
   第 3~6 行是输入框、勾选框与下拉框。**不引入分组区块**。

   ⚠ 原摆放里有三处控件互相盖住（Tk 不报错，只是叠在一起），已按"最小改动"修正：
   `平台/曝光值` 两组「标签+下拉框」从右上角挪到第 4 行与第 6 行的空闲格
   （原为 `(0,3)/(0,4)` 与 `(1,3)/(1,4)`，会分别压住「检测设备」按钮、
   `工况` 标签与摄像头画面）。除这两组外，其余控件的格子坐标与原实现逐格一致。
   可用 `hudcore.ui.layout.audit_widget_tree()` 断言整窗零冲突。

2. **按钮状态机**：原来 `init_btn`/`close_btn`/`send_btn`/`off_btn`/`test_btn` 的
   `state=normal|disabled` 散落在 `_post_init`/`_post_close`/`start_testing`/
   `_post_test_finish` 等 6 处，规则彼此不一致（例如"设备已关闭"时测试结束又会把
   「开始测试」点亮）。现在只有**一个状态源** :class:`~hudcore.ui.state.UiState`
   和一张规则表 :data:`RULES`，动作里只改状态，可用性由 ``_apply_ui_state()`` 统一刷新。

按钮/勾选框/下拉框/输入框的**位置、尺寸、配色沿用原实现**；唯一变化是字体族不再硬编码
「微软雅黑」（Ubuntu 上没有该字体）——统一走 :class:`hudcore.ui.theme.Theme` 的跨平台回退链。
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from hudcore.ui import BUSY_NONE, ButtonGroup, Theme, UiState
from hudcore.ui.state import Rule

from PIL import ImageTk

# --------------------------------------------------------------------------- 规则表
# 纯函数：只依赖 UiState，不碰控件 —— 因此可以直接用单测覆盖（tests/test_can_gui_layout.py）


def rule_idle(state: UiState) -> bool:
    """空闲即可用（不占用设备的一次性动作，如「设备管理」）。"""
    return state.idle


def rule_connect(state: UiState) -> bool:
    """「检测设备」「初始化设备」：空闲且当前没有已打开的设备。"""
    return state.idle and not state.flag("device_open")


def rule_disconnect(state: UiState) -> bool:
    """「关闭设备」：空闲且设备已打开。"""
    return state.idle and state.flag("device_open")


def rule_power(state: UiState) -> bool:
    """「ON 档电」「OFF 档电」：设备已打开且当前没在跑自动化测试。"""
    return state.idle and state.flag("device_open") and not state.flag("testing")


def rule_run_test(state: UiState) -> bool:
    """「开始测试」：设备已打开、空闲、未在测试中。"""
    return state.idle and state.flag("device_open") and not state.flag("testing")


def rule_during_test(state: UiState) -> bool:
    """只在测试运行中可用（「暂停测试」「强制终止测试」）。"""
    return state.flag("testing")


def rule_subwindow(state: UiState) -> bool:
    """「设备管理」：空闲且子窗口未打开（打开期间置灰，避免重复开窗）。"""
    return state.idle and not state.flag("sub_window_open")


def rule_config(state: UiState) -> bool:
    """测试运行中禁止改动的选项（平台 / 曝光 / 图像选项 / 变换类型）。"""
    return state.idle and not state.flag("testing")


def rule_run_config(state: UiState) -> bool:
    """测试参数（重复次数 / 完整轮数）：设备已打开且当前未在测试中才可编辑。"""
    return state.idle and state.flag("device_open") and not state.flag("testing")


#: 按钮 key → 规则（ButtonGroup.apply(state) 依此刷新）
RULES: dict[str, Rule] = {
    "probe": rule_connect,
    "init": rule_connect,
    "close": rule_disconnect,
    "sub": rule_subwindow,
    "on_signal": rule_power,
    "off_signal": rule_power,
    "test": rule_run_test,
    "pause": rule_during_test,
    "stop": rule_during_test,
    "rotate": rule_config,
    "perspective": rule_config,
    "repeat": rule_run_config,
    "rounds": rule_run_config,
    "platform": rule_config,
    "exposure": rule_config,
    "opt_image_test": rule_config,
    "opt_capture": rule_config,
    "opt_mirror": rule_config,
    "opt_transform": rule_config,
    "transform_kind": rule_config,
}


class LayoutMixin:
    """CAN 界面的布局构建与按钮状态刷新（由 CANFDGUI 组合使用）。"""

    # ------------------------------------------------------------ 布局变量
    def _init_ui_state(self) -> None:
        """界面相关的状态变量（与控件一一对应；不启动任何线程/设备）。"""
        # 线程控制
        self._stop_camera_thread = False
        self._after_id = None

        # 按钮状态机（单一状态源）
        self._busy: str = BUSY_NONE                # 当前占用设备的串行动作
        self._testing: bool = False                # 自动化测试是否在跑
        self._paused: bool = False                 # 自动化测试是否已暂停

        # 用例重复次数 / 完整轮数
        self.repeat_var = tk.StringVar(value="1")
        self.rounds_var = tk.StringVar(value="1")

        # 设备句柄（初始化成功后写入；界面用 is not None 判断"已打开"）
        self.device_handle = None
        self.channel_handles = None
        self.receive_threads = None

        # 平台分辨率
        self.platform_resolutions = self._load_platform_resolutions()
        if self.platform_resolutions:
            first_platform = list(self.platform_resolutions.keys())[0]
            self.platform_var = tk.StringVar(value=first_platform)
            self.selected_resolution = self.platform_resolutions[first_platform]
        else:
            self.platform_var = tk.StringVar(value="")
            self.selected_resolution = None

        # 图像 / 变换选项
        self.transform_enable_var = tk.IntVar(value=1)
        self.transform_option_var = tk.StringVar(value="变换A")
        self.image_test_var = tk.IntVar(value=1)
        self.image_capture_var = tk.IntVar(value=1)
        self.mirror_enable_var = tk.IntVar(value=0)
        self.exposure_var = tk.IntVar(value=-4)
        self.rotate_flag = False

        # 图像预处理（在 GUI 中创建一次，供"变换"复用）
        from camera_tools.image_enhancement import ImageEnhancer
        self._enhancer = ImageEnhancer(enable_timing=False)

        # 显示帧率控制
        self._gui_frame_interval = 0.1
        self._last_gui_update_time = 0

        # 子窗口 / 最近一帧
        self.sub_window = None
        self._subwindow_open = False
        self.latest_frame = None

    # ------------------------------------------------------------ 构建界面
    def _build_ui(self) -> None:
        """构建整个界面（只建控件，不启动线程、不碰设备）。

        控件坐标与原实现一致（见模块文档），并统一登记进按钮状态机。
        """
        root = self.root
        self.buttons = ButtonGroup("can_gui", on_change=self._on_button_change)

        # ---------- 第一块视频显示：右上角摄像头显示区域（1~5 行）----------
        self.video_label = tk.Label(root, bg="black")
        self.video_label.grid(row=1, column=4, rowspan=5, padx=10, pady=5, sticky='e')
        root.grid_columnconfigure(4, weight=1)

        # 立即显示 "Camera is not open" 占位图（避免首次出现纯黑屏）
        no_cam_img = self._make_no_camera_image(text="Camera is Not Open")
        self._no_cam_placeholder = ImageTk.PhotoImage(no_cam_img, master=root)
        self.video_label.configure(image=self._no_cam_placeholder)
        self.video_label.image = self._no_cam_placeholder        # 防止被 GC

        # ---------- 第二块视频显示：变换后画面（6~10 行）----------
        self.video_label2 = tk.Label(root, bg="black")
        self.video_label2.grid(row=6, column=4, rowspan=5, padx=10, pady=5, sticky='e')
        no_cam_img2 = self._make_no_camera_image(text="Not activated transformation")
        self._no_cam_placeholder2 = ImageTk.PhotoImage(no_cam_img2, master=root)
        self.video_label2.configure(image=self._no_cam_placeholder2)
        self.video_label2.image = self._no_cam_placeholder2

        # ---------- 设备 / 供电 / 测试按钮（0~2 行，原坐标）----------
        self.init_btn = self._flat_button(0, 0, "初始化设备", self.start_init,
                                          bg="#4A90E2", hover="#357ABD",
                                          key="init", style="ew")
        self.close_btn = self._flat_button(0, 1, "关闭设备", self.start_close,
                                           bg="#D9534F", hover="#C9302C",
                                           key="close", style="ew")
        self.stop_btn = self._flat_button(0, 2, "强制终止测试", self.stop_testing,
                                          bg="#D9534F", hover="#C9302C",
                                          key="stop", style="ew")
        self.probe_btn = self._flat_button(0, 3, "检测设备", self.start_probe,
                                           bg="#5BC0DE", hover="#31B0D5",
                                           key="probe", style="ew",
                                           tooltip="子进程探测底层驱动与设备（未插卡时不会带走上位机）")
        self.send_btn = self._flat_button(1, 0, "ON档电", self.start_send_on_signal,
                                          bg="#CEA022", hover="#8D8119",
                                          key="on_signal", style="ew")
        self.off_btn = self._flat_button(1, 1, "OFF档电", self.start_send_off_signal,
                                         bg="#CEA022", hover="#8D8119",
                                         key="off_signal", style="ew")
        self.sub_btn = self._flat_button(1, 2, "设备管理", self.open_subwindow,
                                         bg="#5CB85C", hover="#4CAE4C",
                                         key="sub", style="ew")
        self.test_btn = self._flat_button(2, 0, "开始测试", self.start_testing,
                                          bg="#DB218E", hover="#5A1154",
                                          key="test", style="ew")
        self.toggle_pause_resume_btn = self._flat_button(
            2, 1, "暂停测试", self.toggle_pause_resume, bg="#F0AD4E", hover="#EB983A",
            key="pause", style="ew")
        self.rotate_btn = self._flat_button(2, 2, "图像旋转", self.toggle_rotate,
                                            bg="#5BC0DE", hover="#31B0D5",
                                            key="rotate", style="ew")
        self.perspective_btn = self._flat_button(3, 2, "透视变换校正",
                                                 self.start_perspective_correction,
                                                 bg="#3CC4A6", hover="#35D164",
                                                 key="perspective", style="ew")

        # ---------- 勾选框（5~6 行，原坐标）----------
        self.image_test_cb = self._flat_checkbutton(5, 0, "开启图像测试", self.image_test_var)
        self.mirror_cb = self._flat_checkbutton(5, 1, "开启镜面反转", self.mirror_enable_var)
        self.capture_cb = self._flat_checkbutton(5, 2, "开启图像采集模式", self.image_capture_var)
        self.transform_cb = self._flat_checkbutton(6, 0, "开启图像变换", self.transform_enable_var)

        # ---------- 变换类型（6 行 1 列，原坐标）----------
        self.transform_cb_box = ttk.Combobox(
            root, textvariable=self.transform_option_var,
            values=["变换A", "变换B", "变换C", "变换D"],
            state="readonly", width=12, font=Theme.font_tuple(10))
        self.transform_cb_box.grid(row=6, column=1, pady=5, padx=10, sticky='w')
        self.transform_cb_box.bind("<<ComboboxSelected>>", self._on_option_changed)

        # ---------- 平台 / 曝光值：原在右上角，与"检测设备"按钮、工况标签、
        #            摄像头画面三处重叠 → 挪到第 4、6 行的空闲格（最小改动）----------
        tk.Label(root, text="平台:", font=Theme.font_tuple(10)).grid(
            row=4, column=2, sticky='w', padx=5, pady=5)
        self.platform_cb = ttk.Combobox(
            root, textvariable=self.platform_var,
            values=list(self.platform_resolutions.keys()),
            state="readonly", width=8, font=Theme.font_tuple(10))
        self.platform_cb.grid(row=4, column=3, sticky='w', padx=5, pady=5)
        self.platform_cb.bind("<<ComboboxSelected>>", self._on_platform_change)

        tk.Label(root, text="曝光值:", font=Theme.font_tuple(10)).grid(
            row=6, column=2, sticky='w', padx=5, pady=5)
        self.exposure_cb = ttk.Combobox(
            root, textvariable=self.exposure_var,
            values=[0, -1, -2, -3, -4, -5, -6, -7, -8, -9],
            state="readonly", width=8, font=Theme.font_tuple(10))
        self.exposure_cb.grid(row=6, column=3, sticky='w', padx=5, pady=5)
        self.exposure_cb.bind("<<ComboboxSelected>>", self._on_exposure_change)

        # ---------- 工况显示条（0 行 4 列，原坐标）----------
        self.state_label = tk.Label(
            root, text="当前工况: 等待", font=Theme.font_tuple(12),
            bg=Theme.STATE_BG, fg=Theme.STATE_FG, anchor="w", width=64)
        self.state_label.grid(row=0, column=4, padx=10, pady=5, sticky='e')

        # ---------- 测试参数输入框（3~4 行，原坐标）----------
        tk.Label(root, text="用例重复测试次数:", font=Theme.font_tuple(10)).grid(
            row=3, column=0, sticky='w', padx=12, pady=5)
        self.repeat_entry = self._count_entry(self.repeat_var, row=3, column=1)
        tk.Label(root, text="用例完整测试轮数:", font=Theme.font_tuple(10)).grid(
            row=4, column=0, sticky='w', padx=12, pady=5)
        self.rounds_entry = self._count_entry(self.rounds_var, row=4, column=1)

        # ---------- 纳入按钮状态机（可用性由一个状态源 + 规则表决定）----------
        for key, widget in (
                ("repeat", self.repeat_entry), ("rounds", self.rounds_entry),
                ("platform", self.platform_cb), ("exposure", self.exposure_cb),
                ("opt_image_test", self.image_test_cb), ("opt_mirror", self.mirror_cb),
                ("opt_capture", self.capture_cb), ("opt_transform", self.transform_cb),
                ("transform_kind", self.transform_cb_box)):
            self.buttons.add(key, widget, RULES[key])

        self._apply_ui_state()

    # ------------------------------------------------------------ 小工厂
    def _flat_button(self, row: int, column: int, text: str, command, *, bg: str,
                     hover: str, key: str, style: str = "ew", tooltip: str = ""):
        """按原实现的坐标/配色建一个按钮，并登记进状态机。"""
        btn = tk.Button(root_of(self), text=text, font=Theme.font_tuple(12), bg=bg,
                        fg="white", activebackground=hover, width=10, height=1,
                        command=command)
        btn.grid(row=row, column=column, pady=5, padx=10, sticky=style)
        setattr(btn, "hud_tooltip", tooltip)
        self.buttons.add(key, btn, RULES[key])
        return btn

    def _flat_checkbutton(self, row: int, column: int, text: str, variable):
        """按原实现的坐标建一个勾选框（值变化时刷新状态）。"""
        cb = tk.Checkbutton(root_of(self), text=text, variable=variable, onvalue=1,
                            offvalue=0, font=Theme.font_tuple(10),
                            command=self._on_option_changed)
        cb.grid(row=row, column=column, sticky='w', padx=5, pady=5)
        return cb

    def _count_entry(self, variable, *, row: int, column: int):
        """正整数输入框（校验函数在 gui_test_flow，布局单测模式下可能不存在）。"""
        entry = tk.Entry(root_of(self), textvariable=variable, width=10,
                         font=Theme.font_tuple(10))
        entry.grid(row=row, column=column, sticky='w', padx=10, pady=5)
        validator = getattr(self, "_validate_positive_integer", None)
        if validator is not None:
            entry.configure(validate="key",
                            validatecommand=(self.root.register(validator), "%P"))
        return entry

    # ------------------------------------------------------------ 状态机
    def _ui_state(self) -> UiState:
        """把当前界面状态汇总成一个不可变快照（所有按钮可用性的唯一依据）。"""
        return UiState(
            busy=getattr(self, "_busy", BUSY_NONE),
            flags={
                "device_open": getattr(self, "device_handle", None) is not None,
                "testing": bool(getattr(self, "_testing", False)),
                "paused": bool(getattr(self, "_paused", False)),
                "sub_window_open": bool(getattr(self, "_subwindow_open", False)),
            },
        )

    def _apply_ui_state(self) -> dict[str, str]:
        """刷新按钮可用性与派生文案；返回本次发生变化的按钮。"""
        state = self._ui_state()
        group = getattr(self, "buttons", None)
        changes = group.apply(state) if group is not None else {}
        self._sync_pause_button(state)
        return changes

    def _set_busy(self, busy: str) -> None:
        """进入一次性动作（检测/初始化/关闭/发送），期间相关按钮自动置灰。"""
        self._busy = busy
        self._apply_ui_state()

    def _clear_busy(self) -> None:
        self._busy = BUSY_NONE
        self._apply_ui_state()

    def _set_testing(self, testing: bool, paused: bool = False) -> None:
        """切换"测试运行中"状态（暂停/终止按钮随之亮灭）。"""
        self._testing = bool(testing)
        self._paused = bool(paused) if testing else False
        self._apply_ui_state()

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        self._apply_ui_state()

    def _sync_pause_button(self, state: UiState) -> None:
        """暂停/继续是同一个按钮，文案随状态切换。"""
        btn = getattr(self, "toggle_pause_resume_btn", None)
        if btn is None:
            return
        text = "继续测试" if state.flag("paused") else "暂停测试"
        try:
            if str(btn.cget("text")) != text:
                btn.configure(text=text)
        except Exception:                                     # noqa: BLE001 - 控件已销毁
            pass

    def _on_option_changed(self, _event=None) -> None:          # noqa: ANN001
        """勾选框/下拉框变化：只做状态刷新（值本身由 Tk 变量持有）。"""
        self._apply_ui_state()

    def _on_button_change(self, changes: dict[str, str]) -> None:
        """按钮可用性变化时的排障日志（默认静默，HUD_UI_DEBUG=1 时打印）。"""
        if os.environ.get("HUD_UI_DEBUG"):
            print(f"[CAN][UI] 按钮状态变化: {changes}")

    # ------------------------------------------------------------ 测试辅助
    @classmethod
    def _build_layout_only(cls, root) -> "LayoutMixin":
        """只建界面（不启动相机/校验线程、不碰设备）——供布局审计测试使用。

        用法::

            obj = LayoutMixin._build_layout_only(tk.Tk())
            assert audit_widget_tree(obj.root) == []
        """
        obj = cls.__new__(cls)                                 # noqa: SLF001 - 跳过 __init__
        obj.root = root
        obj.selected_file = tk.StringVar(value="无文件")
        obj._init_ui_state()
        obj._build_ui()
        obj.root.title("CANFD 设备控制（布局模式）")
        return obj


def root_of(obj):
    """取界面根容器（供小工厂函数使用，保持调用处简洁）。"""
    return obj.root
