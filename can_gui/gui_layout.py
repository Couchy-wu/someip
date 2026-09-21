# -*- coding: utf-8 -*-
"""can_gui.gui_layout —— CAN 界面布局与按钮状态机（Mixin）

本次优化把原来散在 ``CANFDGUI.__init__`` 里的 200 多行"控件 + grid 坐标 + 手写
``config(state=...)``"收敛到本模块，解决三类问题：

1. **格子冲突**：原实现里 `平台` 标签与「检测设备」按钮都在 ``row=0, column=3``，
   `曝光值` 下拉框与摄像头画面都在 ``row=1, column=4``，`工况` 标签与 `平台` 下拉框都在
   ``row=0, column=4`` —— Tk 不报错，只是互相盖住。现在左右两块各用一列、
   区块内用 :class:`~hudcore.ui.action_bar.SectionStack` 自动分配行号，写不出冲突；
   ``hudcore.ui.layout.audit_widget_tree()`` 可断言为零冲突（见 tests/test_can_gui_layout.py）。

2. **按钮可用性**：原来 ``init_btn/close_btn/send_btn/off_btn/test_btn`` 的
   ``state=normal|disabled`` 散落在 ``_post_init`` / ``_post_close`` / ``start_testing`` /
   ``_post_test_finish`` 等 6 处，规则彼此不一致（例如"设备已关闭"时测试结束又会把
   「开始测试」点亮）。现在只有**一个状态源** :class:`~hudcore.ui.state.UiState`
   和一张规则表 :data:`RULES`，动作里只改状态，可用性由 ``_apply_ui_state()`` 统一刷新。

3. **样式**：字体不再硬编码「微软雅黑」（Ubuntu 上没有该字体），配色走 Theme。

界面分区（左控制 / 右画面）：

    ┌ ① 设备连接   检测设备 / 初始化设备 / 关闭设备 / 设备管理 ─┐ ┌ 工况显示条 ─┐
    │ ② 供电控制   ON 档电 / OFF 档电                          │ │ 摄像头画面 │
    │ ③ 自动化测试 开始测试 / 暂停测试 / 强制终止测试            │ │ 变换后画面 │
    │ ④ 平台与图像 平台 / 曝光值 / 四项勾选                     │ └───────────┘
    │ ⑤ 图像变换   变换类型 / 图像旋转 / 透视变换校正            │
    └──────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from hudcore.ui import (
    BUSY_CLOSE, BUSY_INIT, BUSY_NONE, BUSY_PROBE, ButtonGroup,
    SectionStack, Theme, UiState,
)
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
        """构建整个界面（只建控件，不启动线程、不碰设备）。"""
        root = self.root
        self.buttons = ButtonGroup("can_gui", on_change=self._on_button_change)

        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)      # 左：控制区
        root.grid_columnconfigure(1, weight=1)      # 右：画面区

        left = ttk.Frame(root)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=6)
        left.grid_columnconfigure(0, weight=1)
        right = ttk.Frame(root)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=6)
        right.grid_columnconfigure(0, weight=1)

        stack = SectionStack(left, column=0, padx=4, pady=4, use_ttk=False, sticky="ew")
        self._build_device_section(stack)
        self._build_power_section(stack)
        self._build_test_section(stack)
        self._build_options_section(stack)
        self._build_transform_section(stack)

        self._build_preview_panel(right)
        self._apply_ui_state()

    # ---------------- ① 设备连接 ----------------
    def _build_device_section(self, stack: SectionStack) -> None:
        section = stack.section("① 设备连接")
        inner = SectionStack(section, padx=4, pady=3, use_ttk=False, sticky="w")
        bar = inner.action_bar(columns=4, group=self.buttons)

        self.probe_btn = bar.add("probe", "检测设备", self.start_probe, kind="info",
                                 enabled_when=RULES["probe"],
                                 tooltip="子进程探测底层驱动与设备（未插卡时不会带走上位机）")
        self.init_btn = bar.add("init", "初始化设备", self.start_init, kind="primary",
                                enabled_when=RULES["init"])
        self.close_btn = bar.add("close", "关闭设备", self.start_close, kind="danger",
                                 enabled_when=RULES["close"])
        self.sub_btn = bar.add("sub", "设备管理", self.open_subwindow, kind="success",
                               enabled_when=RULES["sub"])

        self.device_hint = tk.Label(section, text="", **Theme.hint_label(wraplength=420))
        inner.grid(self.device_hint, sticky="w")

    # ---------------- ② 供电控制 ----------------
    def _build_power_section(self, stack: SectionStack) -> None:
        section = stack.section("② 供电控制")
        inner = SectionStack(section, padx=4, pady=3, use_ttk=False, sticky="w")
        bar = inner.action_bar(columns=2, group=self.buttons)
        self.send_btn = bar.add("on_signal", "ON档电", self.start_send_on_signal, kind="warn",
                                enabled_when=RULES["on_signal"])
        self.off_btn = bar.add("off_signal", "OFF档电", self.start_send_off_signal, kind="warn",
                               enabled_when=RULES["off_signal"])
        inner.note("需先「初始化设备」；档位电报文按 50ms 周期循环发送。")

    # ---------------- ③ 自动化测试 ----------------
    def _build_test_section(self, stack: SectionStack) -> None:
        section = stack.section("③ 自动化测试")
        inner = SectionStack(section, padx=4, pady=3, use_ttk=False, sticky="w")
        bar = inner.action_bar(columns=3, group=self.buttons)
        self.test_btn = bar.add("test", "开始测试", self.start_testing, kind="success",
                                enabled_when=RULES["test"])
        self.toggle_pause_resume_btn = bar.add("pause", "暂停测试", self.toggle_pause_resume,
                                               kind="warn", enabled_when=RULES["pause"])
        self.stop_btn = bar.add("stop", "强制终止测试", self.stop_testing, kind="danger",
                                enabled_when=RULES["stop"])

        self.repeat_entry = self._make_count_entry(section, self.repeat_var)
        self.rounds_entry = self._make_count_entry(section, self.rounds_var)
        inner.form_row(("用例重复测试次数:", self.repeat_entry),
                       ("用例完整测试轮数:", self.rounds_entry))
        self.buttons.add("repeat", self.repeat_entry, RULES["repeat"])
        self.buttons.add("rounds", self.rounds_entry, RULES["rounds"])

    def _make_count_entry(self, parent, variable) -> tk.Entry:
        """正整数输入框（校验函数在 gui_test_flow，布局单测模式下可能不存在）。"""
        entry = tk.Entry(parent, textvariable=variable, width=10,
                         font=Theme.font_tuple(10), justify="center")
        validator = getattr(self, "_validate_positive_integer", None)
        if validator is not None:
            entry.configure(validate="key",
                           validatecommand=(self.root.register(validator), "%P"))
        return entry

    # ---------------- ④ 平台与图像选项 ----------------
    def _build_options_section(self, stack: SectionStack) -> None:
        section = stack.section("④ 平台与图像选项")
        inner = SectionStack(section, padx=4, pady=3, use_ttk=False, sticky="w")

        self.platform_cb = ttk.Combobox(section, textvariable=self.platform_var,
                                        values=list(self.platform_resolutions.keys()),
                                        state="readonly", width=12,
                                        font=Theme.font_tuple(10))
        self.platform_cb.bind("<<ComboboxSelected>>", self._on_platform_change)
        self.exposure_cb = ttk.Combobox(section, textvariable=self.exposure_var,
                                        values=[0, -1, -2, -3, -4, -5, -6, -7, -8, -9],
                                        state="readonly", width=8,
                                        font=Theme.font_tuple(10))
        self.exposure_cb.bind("<<ComboboxSelected>>", self._on_exposure_change)
        inner.form_row(("平台:", self.platform_cb), ("曝光值:", self.exposure_cb))
        self.buttons.add("platform", self.platform_cb, RULES["platform"])
        self.buttons.add("exposure", self.exposure_cb, RULES["exposure"])

        self.image_test_cb = tk.Checkbutton(section, text="开启图像测试",
                                            variable=self.image_test_var, onvalue=1, offvalue=0,
                                            command=self._on_option_changed,
                                            **Theme.check_button())
        self.capture_cb = tk.Checkbutton(section, text="开启图像采集模式",
                                         variable=self.image_capture_var, onvalue=1, offvalue=0,
                                         command=self._on_option_changed,
                                         **Theme.check_button())
        self.mirror_cb = tk.Checkbutton(section, text="开启镜面反转",
                                        variable=self.mirror_enable_var, onvalue=1, offvalue=0,
                                        command=self._on_option_changed,
                                        **Theme.check_button())
        self.transform_cb = tk.Checkbutton(section, text="开启图像变换",
                                           variable=self.transform_enable_var, onvalue=1,
                                           offvalue=0, command=self._on_option_changed,
                                           **Theme.check_button())
        inner.row(self.image_test_cb, self.capture_cb)
        inner.row(self.mirror_cb, self.transform_cb)

        # 勾选框纳入状态机（测试运行中禁止改动）
        for key, widget in (("opt_image_test", self.image_test_cb),
                            ("opt_capture", self.capture_cb),
                            ("opt_mirror", self.mirror_cb),
                            ("opt_transform", self.transform_cb)):
            self.buttons.add(key, widget, RULES[key])
        inner.note("图像测试/采集/变换会影响标贴校验结果，测试运行中不可改动。")

    # ---------------- ⑤ 图像变换 ----------------
    def _build_transform_section(self, stack: SectionStack) -> None:
        section = stack.section("⑤ 图像变换")
        inner = SectionStack(section, padx=4, pady=3, use_ttk=False, sticky="w")
        self.transform_cb_box = ttk.Combobox(section, textvariable=self.transform_option_var,
                                            values=["变换A", "变换B", "变换C", "变换D"],
                                            state="readonly", width=12,
                                            font=Theme.font_tuple(10))
        self.transform_cb_box.bind("<<ComboboxSelected>>", self._on_option_changed)
        inner.form_row(("变换类型:", self.transform_cb_box))
        bar = inner.action_bar(columns=2, group=self.buttons, pady=(2, 4))
        self.rotate_btn = bar.add("rotate", "图像旋转", self.toggle_rotate, kind="info",
                                  enabled_when=RULES["rotate"])
        self.perspective_btn = bar.add("perspective", "透视变换校正",
                                       self.start_perspective_correction, kind="success",
                                       enabled_when=RULES["perspective"])
        self.buttons.add("transform_kind", self.transform_cb_box, RULES["transform_kind"])

    # ---------------- 右侧画面 ----------------
    def _build_preview_panel(self, right: ttk.Frame) -> None:
        self.state_label = tk.Label(right, text="当前工况: 等待",
                                    **Theme.state_banner(width=56))
        self.state_label.grid(row=0, column=0, sticky="ew")

        self.video_label = tk.Label(right, bg="black")
        self.video_label.grid(row=1, column=0, pady=(6, 3))
        no_cam_img = self._make_no_camera_image(text="Camera is Not Open")
        self._no_cam_placeholder = ImageTk.PhotoImage(no_cam_img, master=self.root)
        self.video_label.configure(image=self._no_cam_placeholder)
        self.video_label.image = self._no_cam_placeholder      # 防止被 GC

        self.video_label2 = tk.Label(right, bg="black")
        self.video_label2.grid(row=2, column=0, pady=(3, 6))
        no_cam_img2 = self._make_no_camera_image(text="Not activated transformation")
        self._no_cam_placeholder2 = ImageTk.PhotoImage(no_cam_img2, master=self.root)
        self.video_label2.configure(image=self._no_cam_placeholder2)
        self.video_label2.image = self._no_cam_placeholder2

        tk.Label(right, text="上方：摄像头原始画面；下方：变换后画面（勾选「开启图像变换」后显示）",
                 **Theme.hint_label(wraplength=640)).grid(row=3, column=0, sticky="w")

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
        self._sync_device_hint(state)
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

    def _sync_device_hint(self, state: UiState) -> None:
        """设备状态提示（原来只在弹窗里说，现在界面上常驻一行）。"""
        label = getattr(self, "device_hint", None)
        if label is None:
            return
        if state.busy_is(BUSY_PROBE):
            text = "设备状态：正在检测（子进程探测，未插卡也不会带走上位机）…"
        elif state.busy_is(BUSY_INIT):
            text = "设备状态：正在初始化…"
        elif state.busy_is(BUSY_CLOSE):
            text = "设备状态：正在关闭…"
        elif state.flag("device_open"):
            text = "设备状态：已初始化（句柄就绪，可发送档位电 / 开始测试）"
        else:
            text = "设备状态：未初始化 —— 建议先「检测设备」确认硬件在位，再「初始化设备」"
        try:
            if str(label.cget("text")) != text:
                label.configure(text=text)
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
