# -*- coding: utf-8 -*-
"""hudcore.ui.layout —— 布局工具与"格子冲突"自检
=================================================
界面布局最容易出的问题是**单元格冲突**：两个控件被 ``grid`` 到同一个
``(row, column)``，Tk 不报错，只是让它们叠在一起（谁大谁盖住谁），

  · 肉眼看是"按钮被输入框压住 / 标签不见了"，很难定位；
  · 改布局时又会重复引入（例如新按钮随手挑了 ``row=0, column=3``）。

本模块提供两件事：

1. :class:`SectionStack` —— 在容器里**按顺序**堆区块/控件，行号自动分配，
   从写法规避冲突（不再手写 ``row=``）；配套 :class:`ActionBar` （见 action_bar.py）
   管一行里的按钮；
2. :func:`audit_widget_tree` —— 遍历控件树，列出所有"同一格子被多个控件占用"的地方，
   让布局问题变成**可断言的测试**（见 ``tests/test_ui_layout.py``）。

设计约束：本模块不创建窗口、不读业务数据；只做布局与检查。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

__all__ = ["Cell", "Collision", "grid_occupancy", "grid_collisions",
           "audit_widget_tree", "describe_collisions", "section_frame"]


@dataclass(frozen=True, order=True)
class Cell:
    """grid 里的一个单元格。"""

    row: int
    column: int


@dataclass(frozen=True)
class Collision:
    """一次单元格冲突：同一个格子被多个控件占用。"""

    parent: str
    cell: Cell
    occupants: Tuple[str, ...]

    def describe(self) -> str:
        names = " / ".join(self.occupants)
        return (f"{self.parent} 的 (row={self.cell.row}, column={self.cell.column}) "
                f"被 {len(self.occupants)} 个控件占用：{names}")


# ---------------------------------------------------------------- 基本工具
def widget_name(widget) -> str:
    """尽量给出可读的控件标识（类名 + 文本/变量名）。"""
    cls = type(widget).__name__
    text = ""
    try:
        text = str(widget.cget("text") or "")
    except Exception:                                # noqa: BLE001 - 有些控件没有 text
        text = ""
    if not text:
        try:
            tb = widget.cget("textvariable")
            text = str(tb or "")
        except Exception:                            # noqa: BLE001
            text = ""
    return f"{cls}('{text}')" if text else cls


def _grid_info(widget) -> Dict[str, int] | None:
    """控件的 grid 占位信息（row/column/rowspan/columnspan）；非 grid 管理返回 None。"""
    try:
        if widget.winfo_manager() != "grid":
            return None
    except Exception:                                # noqa: BLE001 - 控件已销毁
        return None
    try:
        info = widget.grid_info()
    except Exception:                                # noqa: BLE001
        return None
    if not info:
        return None
    out: Dict[str, int] = {}
    for key, default in (("row", 0), ("column", 0), ("rowspan", 1), ("columnspan", 1)):
        try:
            out[key] = int(info.get(key, default) or default)
        except Exception:                            # noqa: BLE001
            out[key] = default
    return out


def grid_occupancy(parent, *, recursive: bool = False) -> Dict[Cell, List[object]]:
    """统计 ``parent`` 内由 grid 管理的控件占用的格子。

    :param recursive: True 时连子容器的内容一起统计（键里的 parent 信息会丢失，
                      需要定位到具体容器请用 :func:`grid_collisions`）
    """
    occupancy: Dict[Cell, List[object]] = {}
    for child in _children(parent):
        info = _grid_info(child)
        if info is None:
            continue
        for r in range(info["row"], info["row"] + max(1, info["rowspan"])):
            for c in range(info["column"], info["column"] + max(1, info["columnspan"])):
                occupancy.setdefault(Cell(r, c), []).append(child)
        if recursive:
            for cell, widgets in grid_occupancy(child, recursive=True).items():
                occupancy.setdefault(cell, []).extend(widgets)
    return occupancy


def grid_collisions(parent) -> List[Collision]:
    """列出 ``parent`` 直接子控件之间的格子冲突（每个容器分别判定）。"""
    out: List[Collision] = []
    by_cell: Dict[Cell, List[object]] = {}
    for child in _children(parent):
        info = _grid_info(child)
        if info is None:
            continue
        for r in range(info["row"], info["row"] + max(1, info["rowspan"])):
            for c in range(info["column"], info["column"] + max(1, info["columnspan"])):
                by_cell.setdefault(Cell(r, c), []).append(child)
    for cell in sorted(by_cell):
        widgets = by_cell[cell]
        if len(widgets) > 1:
            out.append(Collision(parent=widget_name(parent), cell=cell,
                                 occupants=tuple(widget_name(w) for w in widgets)))
    return out


def audit_widget_tree(root, *, max_depth: int = 12) -> List[Collision]:
    """递归检查整棵控件树的 grid 格子冲突（界面测试的断言入口）。"""
    out: List[Collision] = []
    stack: List[Tuple[object, int]] = [(root, 0)]
    while stack:
        widget, depth = stack.pop()
        out.extend(grid_collisions(widget))
        if depth >= max_depth:
            continue
        for child in _children(widget):
            stack.append((child, depth + 1))
    return out


def describe_collisions(collisions: Iterable[Collision]) -> str:
    """把冲突列表转成多行文本（日志/断言消息用）。"""
    items = list(collisions)
    if not items:
        return "未发现 grid 格子冲突"
    return "\n".join(f"· {c.describe()}" for c in items)


def _children(widget) -> List[object]:
    try:
        return list(widget.winfo_children())
    except Exception:                                # noqa: BLE001 - 控件已销毁
        return []


# ---------------------------------------------------------------- 顺序布局
def section_frame(parent, title: str, *, use_ttk: bool = True, row: int = 0,
                  column: int = 0, columnspan: int = 1, padx: int = 6, pady: int = 4,
                  sticky: str = "ew"):
    """创建并放置一个带标题的区块（LabelFrame），返回容器供内部自由 grid。

    与 :class:`hudcore.ui.action_bar.SectionStack` 搭配使用；单独用时需自己给 row。
    """
    import tkinter as tk
    from tkinter import ttk

    frame = ttk.LabelFrame(parent, text=title) if use_ttk else tk.LabelFrame(parent, text=title)
    frame.grid(row=row, column=column, columnspan=columnspan, padx=padx, pady=pady, sticky=sticky)
    return frame
