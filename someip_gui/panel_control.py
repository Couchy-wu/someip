# -*- coding: utf-8 -*-
"""someip_gui.panel_control —— 右侧控制面板（Mixin）

布局（窗口右半部分，自上而下）：
    ③ 回放控制：pcap 路径（浏览 / 解析摘要）、循环开关、节流间隔、
       开始/停止回放、已发送与解析条数统计
    ④ 单条发送：类型下拉 + 字段编辑表（由结构体自动生成）+ 发送按钮
    ⑤ 报文日志：只读文本框（时间戳 + 动作 + 结果），支持清空/导出

设计：与 can_gui 的相机/测试流程面板同一风格（Mixin 组合），
      面板只调用 `ReplayController`，不直接触碰 ctypes 库。

按钮可用性：③④ 的「开始回放 / 停止回放 / 发送该事件」登记进窗口的
`self.buttons`（ButtonGroup），规则来自 `someip_gui.ui_rules.RULES` ——
与工具栏同一个状态源，面板里**不写** `configure(state=...)`；
按钮位置由 `ActionBar` 自动分配（避免手写 grid 坐标撞格）。
"""
from __future__ import annotations

import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from hudcore.ui import ActionBar, Theme

from someip_core import parse_summary
from someip_core.api import STRUCT_TYPES

from . import ui_rules as rules
from .field_table import FieldTable


class ControlPanelMixin:
    """右侧控制面板（回放 + 单条发送 + 日志）。"""

    # ---------------------------------------------------------------- 布局
    def _build_control_panel(self, parent: ttk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        self._build_replay_box(parent)         # ③ 回放控制
        self._build_send_box(parent)           # ④ 单条发送
        self._build_log_box(parent)            # ⑤ 日志

    # ---------------- ③ 回放控制 ----------------
    def _build_replay_box(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="③ pcap 回放控制")
        box.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
        box.grid_columnconfigure(1, weight=1)

        ttk.Label(box, text="pcap 文件").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        row = ttk.Frame(box)
        row.grid(row=0, column=1, columnspan=3, sticky="ew", padx=6, pady=3)
        row.grid_columnconfigure(0, weight=1)
        self.var_pcap = tk.StringVar(value=self.config.pcap_path)
        ttk.Entry(row, textvariable=self.var_pcap).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="浏览…", width=7,
                   command=self._on_pick_pcap).grid(row=0, column=1, padx=(4, 0))
        ttk.Button(row, text="解析摘要", width=9,
                   command=self._on_parse_pcap).grid(row=0, column=2, padx=(4, 0))

        opts = ttk.Frame(box)
        opts.grid(row=1, column=1, columnspan=3, sticky="w", padx=6, pady=3)
        self.var_loop = tk.BooleanVar(value=self.config.loop)
        ttk.Checkbutton(opts, text="循环回放", variable=self.var_loop).pack(side="left")
        ttk.Label(opts, text="节流间隔(ms)").pack(side="left", padx=(14, 4))
        self.var_interval = tk.StringVar(value=str(self.config.interval_ms))
        ttk.Entry(opts, textvariable=self.var_interval, width=6).pack(side="left")
        ttk.Label(opts, text="（0=按 pcap 原始时序；>0 用于加速回放）",
                  foreground=Theme.FG_DARK).pack(side="left", padx=6)

        btns = ActionBar(box, row=2, column=1, columns=2, group=self.buttons)
        self.btn_replay_start = btns.add(
            rules.KEY_REPLAY_START, "开始回放", self.on_replay_start, kind="primary",
            width=11, height=1, enabled_when=rules.RULES[rules.KEY_REPLAY_START],
            tooltip="未打开/未启动服务时会自动先执行「打开 + 启动」")
        self.btn_replay_stop = btns.add(
            rules.KEY_REPLAY_STOP, "停止回放", self.on_replay_stop, kind="danger",
            width=11, height=1, enabled_when=rules.RULES[rules.KEY_REPLAY_STOP],
            tooltip="停止库内回放线程（服务保持启动）")
        self.lbl_replay_stat = ttk.Label(box, text="已发送 0 条", foreground=Theme.PRIMARY)
        self.lbl_replay_stat.grid(row=2, column=3, sticky="w", padx=12)
        self.lbl_pcap_info = ttk.Label(box, text="（未解析 pcap）", foreground=Theme.FG_DARK,
                                       wraplength=520, justify="left")
        self.lbl_pcap_info.grid(row=3, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 6))

    # ---------------- ④ 单条发送 ----------------
    def _build_send_box(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="④ 单条发送（结构化赋值 → C++ 序列化 → 发送）")
        box.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(2, weight=1)              # 字段表所在行可伸展

        # 第 1 行：类型下拉 + 字段辅助按钮（按钮由 ActionBar 排布并纳入状态机）
        bar = ttk.Frame(box)
        bar.grid(row=0, column=0, sticky="ew", padx=6, pady=3)
        ttk.Label(bar, text="数据类型").grid(row=0, column=0, sticky="w")
        self.var_kind = tk.StringVar(value=self.config.last_event_kind or STRUCT_TYPES[0])
        kind_menu = ttk.Combobox(bar, textvariable=self.var_kind, values=list(STRUCT_TYPES),
                                 width=14, state="readonly")
        kind_menu.grid(row=0, column=1, sticky="w", padx=6)
        kind_menu.bind("<<ComboboxSelected>>", lambda e: self._on_kind_changed())
        actions = ActionBar(bar, row=0, column=2, columns=2, group=self.buttons)
        actions.add("fill_sample", "载入示例值", self._on_fill_sample, kind="neutral",
                    width=9, height=1, tooltip="按类型填入一组有意义的示例值")
        actions.add("clear_fields", "清零字段", lambda: self.field_table.clear(),
                    kind="neutral", width=7, height=1, tooltip="把可编辑字段重置为默认值")

        # 第 2 行：主操作「发送该事件」独占一行 —— 右半区只有 ~470px 宽，
        # 与上面几个按钮挤在一行会把主操作顶到可视区之外（实测 x=471 > 453，按钮被裁掉）。
        send_row = ttk.Frame(box)
        send_row.grid(row=1, column=0, sticky="w", padx=6, pady=(0, 3))
        send_bar = ActionBar(send_row, row=0, column=0, columns=1, group=self.buttons)
        self.btn_send = send_bar.add(
            rules.KEY_SEND, "发送该事件", self.on_send_struct, kind="primary", width=11,
            height=1, enabled_when=rules.RULES[rules.KEY_SEND],
            tooltip="未打开/未启动服务时会自动先执行「打开 + 启动」")

        # 第 3 行：字段编辑表（滚动）
        self.field_table = FieldTable(box, self.var_kind.get(), on_log=self.log)
        self.field_table.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))

        # 第 4 行：目标 service/event 提示
        self.lbl_target = ttk.Label(box, foreground=Theme.FG_DARK, text=self._target_text())
        self.lbl_target.grid(row=3, column=0, sticky="w", padx=6, pady=(0, 6))

    # ---------------- ⑤ 日志 ----------------
    def _build_log_box(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="⑤ 操作与报文日志")
        box.grid(row=2, column=0, sticky="nsew", padx=6, pady=(4, 6))
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(1, weight=1)

        bar = ttk.Frame(box)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
        ttk.Button(bar, text="清空", width=7,
                   command=lambda: (self.log_text.configure(state="normal"),
                                    self.log_text.delete("1.0", "end"),
                                    self.log_text.configure(state="disabled"))).pack(side="left")
        ttk.Button(bar, text="导出日志", width=9,
                   command=self._on_export_log).pack(side="left", padx=4)
        ttk.Button(bar, text="打开数据目录", width=13,
                   command=self._open_data_dir).pack(side="left", padx=4)

        self.log_text = tk.Text(box, **Theme.log_text_style(height=8, width=60))
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=(6, 0), pady=(0, 6))
        self.log_text.configure(state="disabled")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.log_text.yview)
        sb.grid(row=1, column=1, sticky="ns", pady=(0, 6))
        self.log_text.configure(yscrollcommand=sb.set)

    # ---------------------------------------------------------------- 交互动作
    def _target_text(self) -> str:
        """显示当前类型对应的 (service, event)。"""
        from someip_core import KIND_SERVICE_EVENT
        kind = self.var_kind.get()
        pair = KIND_SERVICE_EVENT.get(kind)
        if not pair:
            return "该类型无需 service/event（原始字节发送）"
        return f"目标：0x{pair[0]:04X}:0x{pair[1]:04X}（Checksum 由库自动 CRC32 计算）"

    def _on_kind_changed(self) -> None:
        self.field_table.build(self.var_kind.get())
        self.lbl_target.configure(text=self._target_text())
        self.config.last_event_kind = self.var_kind.get()

    def _on_fill_sample(self) -> None:
        """按类型填入一组有意义的示例值（便于快速验证链路）。"""
        samples = {
            "RTK": {"Counter": 1, "rtk_status": 4, "longitude": 116.397, "latitude": 39.908,
                    "altitude": 45.0, "satellite_num": 18, "satellite_used": 15},
            "IMU": {"Counter": 1, "IMU_status": 1, "is_calibrated": 1,
                    "IMU_current_temperature": 32.5},
            "ChangeLane": {"Counter": 1, "ChangeLaneState": 1, "ChangeLaneDirection": 1,
                           "change_ratio": 0.5},
            "PilotStatus": {"Counter": 1, "ACCStatus": 1, "ICCStatus": 1,
                            "DNPStatus": 1, "TakeoverStatus": 1, "driving_time": 600},
            "PilotAlarm": {"Counter": 1, "PilotAlarmReason": 2, "alarm_distance": 120,
                           "alarm_stage": 1, "PilotNotice": 1, "notice_distance": 200},
            "Broadcast": {"Counter": 1, "driver_attention": 1, "large_vehicles": 0,
                          "dangerous_vehicle": 0, "pedestrians": 0},
            "HudMappath": {"Counter": 1, "is_on_the_path": 1, "road_angle": 15,
                           "road_slope": 0.5},
            "HudNavmap": {"Counter": 1, "Navigation_map": "NAV-DATA-SAMPLE"},
            "VehiclePosition": {"Counter": 1, "Longitude": 116.397, "Latitude": 39.908,
                                "Heading": 90.0, "VehicleSpeed": 60.0, "hd_lane_num": 3,
                                "HdStatus": 1, "pos_confidence": 0.9},
        }
        self.field_table.apply_defaults(samples.get(self.var_kind.get(), {}))
        self.log(f"已载入 {self.var_kind.get()} 示例值（可自行修改后发送）")

    def _on_pick_pcap(self) -> None:
        path = filedialog.askopenfilename(
            title="选择要回放的 pcap",
            filetypes=[("pcap", "*.pcap *.pcapng"), ("全部文件", "*.*")])
        if path:
            self.var_pcap.set(path)
            self.log(f"已选择 pcap：{path}")
            self._on_parse_pcap()

    def _on_parse_pcap(self) -> None:
        """解析 pcap 并把摘要显示在界面上（回放由 C++ 库执行，这里只做预检）。"""
        path = self.var_pcap.get().strip()
        if not path:
            messagebox.showwarning("提示", "请先选择 pcap 文件", parent=self.window)
            return
        summary = parse_summary(path)
        if summary.error:
            self.lbl_pcap_info.configure(text=f"⚠ {summary.error}")
            self.log(f"pcap 解析失败：{summary.error}")
            return
        lines = [summary.describe()]
        for key in sorted(summary.events):
            st = summary.events[key]
            from someip_core import find_event
            ev = find_event(*key)
            name = ev.name if ev else "（未在定义表中）"
            lines.append(f"    {st.describe()}  {name}")
        self.lbl_pcap_info.configure(text="\n".join(lines))
        self.log(f"pcap 摘要：{summary.describe()}")

    def _on_export_log(self) -> None:
        path = filedialog.asksaveasfilename(
            title="导出日志", defaultextension=".txt",
            initialfile=f"someip_replay_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_text.get("1.0", "end"))
            self.log(f"日志已导出：{path}")
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.window)
