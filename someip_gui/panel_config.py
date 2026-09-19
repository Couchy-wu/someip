# -*- coding: utf-8 -*-
"""someip_gui.panel_config —— 左侧配置面板（Mixin）

布局（窗口左半部分，自上而下）：
    ① 网络与 SD 配置：单播地址（含自动探测）、network 名、vsomeip 配置路径、自动启动开关
    ② 服务 / 事件表：Treeview 列出 11 服务 / 23 事件，**勾选即注册**；
       提供"全选 / 反选 / 仅结构化可发送类型"等快捷操作与搜索过滤

设计：以 Mixin 提供布局与交互，由 `SomeipReplayWindow` 组合；
面板只负责"收集用户意图"，具体动作在控制面板/控制器里执行。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from hudcore.platform.executables import open_with_default_app
from hudcore.ui import Theme

from someip_core import all_events, services
from someip_core.api import default_ip


class ConfigPanelMixin:
    """左侧配置面板（网络配置 + 服务事件勾选）。"""

    # ---------------------------------------------------------------- 布局
    def _build_config_panel(self, parent: ttk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # ---------------- ① 网络与 SD 配置 ----------------
        net = ttk.LabelFrame(parent, text="① 网络与 SD 配置")
        net.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
        net.grid_columnconfigure(1, weight=1)

        ttk.Label(net, text="单播地址").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self.var_unicast = tk.StringVar(value=self.config.unicast or "")
        row_u = ttk.Frame(net)
        row_u.grid(row=0, column=1, columnspan=2, sticky="ew", padx=6, pady=3)
        row_u.grid_columnconfigure(0, weight=1)
        ttk.Entry(row_u, textvariable=self.var_unicast).grid(row=0, column=0, sticky="ew")
        ttk.Button(row_u, text="自动探测", width=9,
                   command=self._on_detect_ip).grid(row=0, column=1, padx=(4, 0))
        ttk.Label(net, text=f"（留空则库内自动探测，本机探测结果：{default_ip()}）",
                  foreground=Theme.FG_DARK).grid(row=1, column=1, columnspan=2,
                                                 sticky="w", padx=6)

        ttk.Label(net, text="network").grid(row=2, column=0, sticky="w", padx=6, pady=3)
        self.var_network = tk.StringVar(value=self.config.network)
        ttk.Entry(net, textvariable=self.var_network, width=18).grid(
            row=2, column=1, sticky="w", padx=6, pady=3)
        ttk.Label(net, text="（与 vsomeip 配置中的 network 名一致）",
                  foreground=Theme.FG_DARK).grid(row=2, column=2, sticky="w")

        ttk.Label(net, text="vsomeip 配置").grid(row=3, column=0, sticky="w", padx=6, pady=3)
        row_c = ttk.Frame(net)
        row_c.grid(row=3, column=1, columnspan=2, sticky="ew", padx=6, pady=3)
        row_c.grid_columnconfigure(0, weight=1)
        self.var_config_path = tk.StringVar(value=self.config.config_path)
        ttk.Entry(row_c, textvariable=self.var_config_path).grid(row=0, column=0, sticky="ew")
        ttk.Button(row_c, text="浏览…", width=7,
                   command=self._on_pick_config).grid(row=0, column=1, padx=(4, 0))
        ttk.Label(net, text="（留空=用库内置默认配置；固定配置客户端场景需指向对应 json）",
                  foreground=Theme.FG_DARK).grid(row=4, column=1, columnspan=2,
                                                 sticky="w", padx=6)

        self.var_auto_start = tk.BooleanVar(value=self.config.auto_start)
        ttk.Checkbutton(net, text="打开服务时自动启动（offer + SD）",
                        variable=self.var_auto_start).grid(
            row=5, column=1, columnspan=2, sticky="w", padx=6, pady=(3, 6))

        # ---------------- ② 服务 / 事件表 ----------------
        box = ttk.LabelFrame(parent, text="② 服务 / 事件（勾选 = 注册）")
        box.grid(row=1, column=0, sticky="nsew", padx=6, pady=(2, 6))
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(1, weight=1)

        bar = ttk.Frame(box)
        bar.grid(row=0, column=0, sticky="ew", padx=4, pady=3)
        ttk.Button(bar, text="全选", width=6, command=lambda: self._select_all(True)).pack(side="left")
        ttk.Button(bar, text="全不选", width=7,
                   command=lambda: self._select_all(False)).pack(side="left", padx=3)
        ttk.Button(bar, text="仅结构化类型", width=12,
                   command=self._select_struct_only).pack(side="left", padx=3)
        ttk.Label(bar, text="过滤").pack(side="left", padx=(10, 2))
        self.var_filter = tk.StringVar()
        ttk.Entry(bar, textvariable=self.var_filter, width=12).pack(side="left")
        self.var_filter.trace_add("write", lambda *_: self._refresh_event_tree())

        cols = ("on", "svc", "evt", "name", "kind", "port", "tp")
        self.event_tree = ttk.Treeview(box, columns=cols, show="headings",
                                       height=14, selectmode="browse")
        for col, text, width, anchor in (
                ("on", "注册", 44, "center"), ("svc", "服务", 62, "center"),
                ("evt", "事件", 62, "center"), ("name", "名称", 210, "w"),
                ("kind", "类型", 108, "w"), ("port", "端口", 54, "center"),
                ("tp", "TP", 40, "center")):
            self.event_tree.heading(col, text=text)
            self.event_tree.column(col, width=width, anchor=anchor, stretch=(col == "name"))
        self.event_tree.grid(row=1, column=0, sticky="nsew", padx=4)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.event_tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.event_tree.configure(yscrollcommand=sb.set)
        self.event_tree.bind("<Button-1>", self._on_tree_click)
        self.event_tree.bind("<space>", lambda e: self._toggle_selected_event())

        self.event_hint = ttk.Label(
            box, foreground=Theme.FG_DARK,
            text="提示：点击“注册”列或按空格切换勾选；勾选的服务会在“启动服务”时一并注册")
        self.event_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 4))

        self._refresh_event_tree()

    # ---------------------------------------------------------------- 事件表交互
    def _refresh_event_tree(self) -> None:
        """重建事件表（按过滤条件）。"""
        keyword = (self.var_filter.get() if hasattr(self, "var_filter") else "").strip().lower()
        self.event_tree.delete(*self.event_tree.get_children())
        selected = set(self.config.selected or [])
        for svc in services():
            for ev in svc.events:
                if keyword and keyword not in ev.name.lower() \
                        and keyword not in ev.key.lower() \
                        and keyword not in ev.kind.lower():
                    continue
                checked = "☑" if (not selected or svc.key in selected) else "☐"
                self.event_tree.insert(
                    "", "end", iid=ev.key,
                    values=(checked, f"0x{svc.service:04X}", f"0x{ev.event:04X}",
                            ev.name, ev.kind, ev.port, "是" if ev.need_tp else ""))

    def _on_tree_click(self, event) -> None:                    # noqa: ANN001
        """点击"注册"列切换勾选状态。"""
        if self.event_tree.identify_region(event.x, event.y) != "cell":
            return
        if self.event_tree.identify_column(event.x) != "#1":
            return
        iid = self.event_tree.identify_row(event.y)
        if iid:
            self._toggle_event(iid)

    def _toggle_selected_event(self) -> None:
        for iid in self.event_tree.selection():
            self._toggle_event(iid)

    def _toggle_event(self, iid: str) -> None:
        """切换某事件的"注册"标记（按服务粒度记录，与库的注册接口一致）。"""
        item = self.event_tree.item(iid)
        vals = list(item["values"])
        vals[0] = "☐" if str(vals[0]) == "☑" else "☑"
        self.event_tree.item(iid, values=vals)
        self._sync_selection_from_tree()

    def _select_all(self, state: bool) -> None:
        mark = "☑" if state else "☐"
        for iid in self.event_tree.get_children():
            vals = list(self.event_tree.item(iid)["values"])
            vals[0] = mark
            self.event_tree.item(iid, values=vals)
        self._sync_selection_from_tree()

    def _select_struct_only(self) -> None:
        """只勾选支持结构化发送的服务（便于手动构造报文）。"""
        from someip_core import find_event
        for iid in self.event_tree.get_children():
            svc = int(str(self.event_tree.item(iid)["values"][1]), 16)
            evt = int(str(self.event_tree.item(iid)["values"][2]), 16)
            ev = find_event(svc, evt)
            vals = list(self.event_tree.item(iid)["values"])
            vals[0] = "☑" if (ev and ev.struct_sendable) else "☐"
            self.event_tree.item(iid, values=vals)
        self._sync_selection_from_tree()

    def _sync_selection_from_tree(self) -> None:
        """把勾选结果汇总为 config.selected（服务号列表；全选时清空表示"全部"）。"""
        per_service: dict[str, bool] = {}
        for iid in self.event_tree.get_children():
            svc = str(self.event_tree.item(iid)["values"][1])
            checked = str(self.event_tree.item(iid)["values"][0]) == "☑"
            per_service[svc] = per_service.get(svc, True) and checked
        chosen = [s for s, all_on in per_service.items() if all_on]
        total_services = len({f"0x{s.service:04X}" for s in services()})
        self.config.selected = [] if len(chosen) == total_services else chosen
        self._on_selection_changed(len(chosen), total_services)

    def _on_selection_changed(self, chosen: int, total: int) -> None:
        """勾选变化时的提示（子类可覆盖）。"""
        if hasattr(self, "event_hint"):
            n_events = sum(1 for iid in self.event_tree.get_children()
                           if str(self.event_tree.item(iid)["values"][0]) == "☑")
            self.event_hint.configure(
                text=f"已勾选 {chosen}/{total} 个服务、共 {n_events} 个事件；"
                     f"点击“注册”列或按空格切换；勾选结果会随“启动服务”一并注册")

    # ---------------------------------------------------------------- 文件选择
    def _on_detect_ip(self) -> None:
        self.var_unicast.set(default_ip())
        self.log(f"已探测本机 IP：{default_ip()}")

    def _on_pick_config(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 vsomeip 配置 json",
            filetypes=[("JSON", "*.json"), ("全部文件", "*.*")])
        if path:
            self.var_config_path.set(path)
            self.log(f"已选择配置：{path}")

    def _open_data_dir(self) -> None:
        """打开数据目录（pcap/配置/服务表都放这里，便于现场取用）。"""
        from someip_core.config import data_dir
        try:
            open_with_default_app(str(data_dir()))
        except Exception as exc:                              # noqa: BLE001
            self.log(f"打开数据目录失败：{exc}")
