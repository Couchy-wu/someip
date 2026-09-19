# -*- coding: utf-8 -*-
"""someip_gui.field_table —— 结构化发送的字段编辑器（可复用控件）

功能：按 ctypes 结构体的 `_fields_` 定义**自动生成**一行一个字段的编辑表，
      用户填值后由 `values()` 收集为 dict，交给 `someip_core.api` 序列化发送。

为什么自动生成：SOME/IP 报文结构有 9 种、字段最多的（VehiclePosition）有 38 个，
手写界面既冗长又容易与 C++ 结构体脱节；直接读 ctypes 结构体可保证"界面字段 == 协议字段"。

类型处理：
    c_uint8/16/32/64      → 整数（默认 0）
    c_double / c_float    → 浮点（默认 0.0）
    c_char * N            → 字符串（以 UTF-8 编码后写入定长数组）
    Checksum              → 只读展示（由 C++ 库自动计算 CRC32，无需填写）
    VehiclePosition       → 字段同样来自 ctypes 结构体（其载荷由库内专用接口序列化）
"""
from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import ttk

from hudcore.ui import Theme

from someip_core.api import EDITABLE_CLASSES


def _field_kind(cls: type[ctypes.Structure], name: str):
    """返回 (显示类型, 是否只读, 定长字符串长度)"""
    ftype = dict(cls._fields_)[name]                 # type: ignore[attr-defined]
    if ftype in (ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint64):
        return "整数", False, 0
    if ftype in (ctypes.c_int8, ctypes.c_int16, ctypes.c_int32, ctypes.c_int64):
        return "整数", False, 0
    if ftype in (ctypes.c_float, ctypes.c_double):
        return "浮点", False, 0
    if issubclass(ftype, ctypes.Array) and ftype._type_ is ctypes.c_char:   # type: ignore[attr-defined]
        return f"字符串({ftype._length_})", False, int(ftype._length_)      # type: ignore[attr-defined]
    return "其他", False, 0


class FieldTable(ttk.Frame):
    """结构体字段编辑表（滚动区 + 每字段一个输入框）。"""

    def __init__(self, master, kind: str, on_log=None, **kw) -> None:
        super().__init__(master, **kw)
        self.kind = kind
        self._entries: dict[str, tuple[tk.Entry, str, int]] = {}
        self._on_log = on_log or (lambda m: None)

        # 滚动区（字段多时可用）
        self.canvas = tk.Canvas(self, highlightthickness=0, height=220)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._on_wheel, add="+")

        self.build(kind)

    # ---------------- 构建 ----------------
    def build(self, kind: str) -> None:
        """按类型重建字段表。"""
        for child in self.inner.winfo_children():
            child.destroy()
        self._entries.clear()
        self.kind = kind

        cls = EDITABLE_CLASSES.get(kind)
        if cls is None:
            ttk.Label(self.inner,
                      text=f"{kind} 不支持结构化赋值（请用原始字节发送或 pcap 回放）",
                      foreground=Theme.DANGER).grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return

        ttk.Label(self.inner, text="字段", font=Theme.font_tuple(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=6, pady=(6, 2))
        ttk.Label(self.inner, text="值", font=Theme.font_tuple(weight="bold")).grid(
            row=0, column=1, sticky="w", padx=6, pady=(6, 2))
        ttk.Label(self.inner, text="类型", font=Theme.font_tuple(weight="bold")).grid(
            row=0, column=2, sticky="w", padx=6, pady=(6, 2))

        row = 1
        for name, _ftype in cls._fields_:
            label, readonly, strlen = _field_kind(cls, name)
            ttk.Label(self.inner, text=name, style="FieldLabel.TLabel").grid(row=row, column=0, sticky="w", padx=6, pady=1)
            entry = ttk.Entry(self.inner, width=28)
            entry.grid(row=row, column=1, sticky="ew", padx=6, pady=1)
            ttk.Label(self.inner, text=label, foreground=Theme.FG_DARK).grid(
                row=row, column=2, sticky="w", padx=6, pady=1)
            if name == "Checksum":
                entry.insert(0, "0")
                entry.configure(state="readonly")
            elif label == "整数":
                entry.insert(0, "0")
            elif label == "浮点":
                entry.insert(0, "0.0")
            self._entries[name] = (entry, label, strlen)
            row += 1

        self.inner.grid_columnconfigure(1, weight=1)
        self.canvas.yview_moveto(0)

    # ---------------- 取值 ----------------
    def values(self) -> dict:
        """收集界面上的字段值（按类型转换；空值跳过，交给 C++ 侧默认）。"""
        out: dict = {}
        for name, (entry, label, _strlen) in self._entries.items():
            if name == "Checksum":
                continue                                  # 由库自动计算
            raw = entry.get().strip()
            if raw == "":
                continue
            try:
                if label == "整数":
                    out[name] = int(raw, 0)
                elif label == "浮点":
                    out[name] = float(raw)
                else:
                    out[name] = raw                       # 字符串 → 库侧编码
            except ValueError:
                raise ValueError(f"字段 {name} 的值 {raw!r} 与类型 {label} 不匹配")
        return out

    def clear(self) -> None:
        """把可编辑字段重置为类型默认值（整数 0 / 浮点 0.0 / 字符串空）。"""
        for name, (entry, label, _strlen) in self._entries.items():
            if str(entry.cget("state")) == "readonly":
                continue
            entry.delete(0, "end")
            entry.insert(0, "0" if label == "整数" else ("0.0" if label == "浮点" else ""))

    def apply_defaults(self, defaults: dict) -> None:
        """用给定默认值填充字段（便于"发送示例报文"）。"""
        for name, value in defaults.items():
            item = self._entries.get(name)
            if not item:
                continue
            entry, _label, _strlen = item
            if str(entry.cget("state")) == "readonly":
                continue
            entry.delete(0, "end")
            entry.insert(0, str(value))

    # ---------------- 事件 ----------------
    def _on_wheel(self, event) -> None:                       # noqa: ANN001
        """仅在鼠标位于本控件上时滚动（避免影响其它区域）。"""
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return
        if widget is None:
            return
        w = widget
        while w is not None:
            if w is self:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return
            w = getattr(w, "master", None)
