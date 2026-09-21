# -*- coding: utf-8 -*-
"""hudcore.ui.action_bar —— 声明式按钮条与顺序布局
====================================================
把"界面里到处手写 ``tk.Button(...); btn.grid(row=?, column=?)``"收敛为**一处声明**：

    bar = ActionBar(parent, row=1, columns=3)          # 一行最多 3 个，超出自动换行
    bar.add("probe", "检测设备", self.start_probe, kind="info",
            enabled_when=lambda s: s.idle and not s.flag("device_open"))
    bar.add("init", "初始化设备", self.start_init,
            enabled_when=lambda s: s.idle and not s.flag("device_open"))
    ...
    bar.apply(self._state())        # 只改状态，可用性由规则表统一决定

好处（也是这次界面优化的目标）：
  · 按钮的**位置**由 ActionBar 自动排（写不出格子冲突，见 hudcore.ui.layout 的审计）；
  · 按钮的**可用性**由规则表统一决定（见 hudcore.ui.state），不会各处漏改；
  · 样式走 :class:`hudcore.ui.theme.Theme`（跨平台字体，不再硬编码「微软雅黑」）；
  · 测试里只建一条 ActionBar 就能验证排布与规则，不需要整个窗口。

:class:`SectionStack` 负责"往下依次放区块"，行号自动分配，配合使用即可整窗不写 row。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .state import ButtonGroup, Rule, UiState

__all__ = ["ActionBar", "SectionStack"]

#: 按钮配色种类 → Theme 里的样式工厂
_KINDS = ("primary", "success", "danger", "info", "warn", "neutral")


def _style_for(kind: str, **kw: Any) -> Dict[str, Any]:
    """把种类名翻译成 Tk 按钮样式（字体/配色统一来自 Theme）。"""
    from .theme import Theme

    if kind == "success":
        return Theme.success_button(**kw)
    if kind == "danger":
        return Theme.danger_button(**kw)
    if kind == "info":
        return Theme.info_button(**kw)
    if kind == "warn":
        return Theme.warn_button(**kw)
    if kind == "neutral":
        return Theme.neutral_button(**kw)
    return Theme.primary_button(**kw)


class ActionBar:
    """一行（或自动换行成多行）按钮条，内部登记到 :class:`ButtonGroup`。

    :param columns: 每行最多放几个按钮，超出自动换到下一行（不会与别的控件撞格）
    :param use_ttk: True 时用 ``ttk.Button``（原生外观，忽略配色种类）
    :param group: 复用外部 ButtonGroup（多个按钮条共用一个状态源）
    """

    def __init__(self, parent, *, row: int = 0, column: int = 0, columnspan: int = 1,
                 columns: int = 4, sticky: str = "w", padx: int = 4, pady: int = 3,
                 use_ttk: bool = False, group: Optional[ButtonGroup] = None,
                 on_change: Optional[Callable[[Dict[str, str]], None]] = None) -> None:
        self.parent = parent
        self.row = row
        self.column = column
        self.columnspan = columnspan
        self.columns = max(1, int(columns))
        self.sticky = sticky
        self.padx = padx
        self.pady = pady
        self.use_ttk = use_ttk
        self.group = group if group is not None else ButtonGroup(
            name=f"bar@{row},{column}", on_change=on_change)
        self._widgets: List[object] = []
        self._slot = 0                       # 已放置控件数（决定行内列号）

    # ---------------------------------------------------------------- 登记
    def add(self, key: str, text: str, command: Callable[[], Any], *,
            kind: str = "primary", width: int = 10, height: int = 1,
            enabled_when: Optional[Rule] = None, tooltip: str = "",
            state: str = "normal", **kwargs: Any):
        """创建一个按钮并放入按钮条；返回控件对象。"""
        if kind not in _KINDS:
            raise ValueError(f"未知按钮种类：{kind}（可选：{'/'.join(_KINDS)}）")
        import tkinter as tk
        from tkinter import ttk

        if self.use_ttk:
            widget = ttk.Button(self.parent, text=text, width=width, command=command,
                                state=state, **kwargs)
        else:
            style = _style_for(kind, width=width, height=height)
            style.update(kwargs)
            style["text"] = text
            style["command"] = command
            style["state"] = state
            widget = tk.Button(self.parent, **style)
        setattr(widget, "hud_tooltip", tooltip)      # 便于排障与测试查看
        self._place(widget)
        self.group.add(key, widget, enabled_when)
        return widget

    def add_widget(self, key: str, widget, *, enabled_when: Optional[Rule] = None,
                   place: bool = True):
        """把已有控件（勾选框/下拉框/输入框）纳入按钮条与状态管理。

        ``place=False`` 用于"控件由调用方自己 grid，但可用性交给按钮条统一管"。
        """
        if place:
            self._place(widget)
        self.group.add(key, widget, enabled_when)
        return widget

    def apply(self, state: UiState) -> Dict[str, str]:
        """按状态刷新本按钮条内所有控件（返回发生变化的项）。"""
        return self.group.apply(state)

    # ---------------------------------------------------------------- 查询
    def widget(self, key: str):
        return self.group.widget(key)

    def keys(self) -> tuple[str, ...]:
        return self.group.keys()

    def rows_used(self) -> int:
        """本按钮条占用的行数（调试/测试断言用）。"""
        return (self._slot - 1) // self.columns + 1 if self._slot else 0

    def widgets(self) -> tuple:
        return tuple(self._widgets)

    def __getitem__(self, key: str):
        return self.group.widget(key)

    def __contains__(self, key: object) -> bool:
        return key in self.group

    def __len__(self) -> int:
        return len(self._widgets)

    # ---------------------------------------------------------------- 内部
    def _place(self, widget) -> None:
        """按已放置数量算出行/列（自动换行，天然不冲突）。"""
        index = self._slot
        self._slot += 1
        row = self.row + index // self.columns
        col = self.column + index % self.columns
        widget.grid(row=row, column=col, padx=self.padx, pady=self.pady, sticky=self.sticky)
        self._widgets.append(widget)


class SectionStack:
    """在一个容器里自上而下放置区块/按钮条，**行号自动递增**。

    用法::

        stack = SectionStack(parent)
        dev = stack.section("① 设备连接")          # 返回 LabelFrame，内部随意 grid
        bar = stack.action_bar(columns=3)         # 紧接其后的一条按钮条
        stack.note("提示：未插卡时…")                # 一行说明文字

    整窗不再出现手写 ``row=``，也就不会有两个控件抢同一格。
    """

    def __init__(self, parent, *, column: int = 0, padx: int = 6, pady: int = 4,
                 use_ttk: bool = True, sticky: str = "ew") -> None:
        self.parent = parent
        self.column = column
        self.padx = padx
        self.pady = pady
        self.use_ttk = use_ttk
        self.sticky = sticky
        self._row = 0
        self._blocks: List[object] = []
        self._pending_bar: Optional[ActionBar] = None   # 待结算行数的按钮条

    # ---- 行号 ----
    @property
    def next_row(self) -> int:
        self._flush()
        return self._row

    def _flush(self) -> None:
        """把上一条按钮条**实际占用**的行数并入行号。

        按钮条创建时还不知道会有几个按钮（`action_bar()` 之后才 `add()`），
        而按钮多于 ``columns`` 时会在块内换行占多行 —— 若只按 1 行结算，
        下一个区块就会盖到按钮条的第二行上（实测会撞格）。
        因此在"下一次放置"时才结算，写布局的人不必自己数按钮个数。
        """
        bar = self._pending_bar
        if bar is None:
            return
        self._pending_bar = None
        self._row = max(self._row, bar.row + max(1, bar.rows_used()))

    def grid(self, widget, *, columnspan: int = 1, sticky: Optional[str] = None,
             padx: Optional[int] = None, pady: Optional[int] = None,
             row: Optional[int] = None):
        """把一个控件放到下一行（指定 ``row`` 可覆盖，用于并列排布）。"""
        if row is None:
            self._flush()
        use_row = self._row if row is None else row
        widget.grid(row=use_row, column=self.column, columnspan=columnspan,
                    padx=self.padx if padx is None else padx,
                    pady=self.pady if pady is None else pady,
                    sticky=self.sticky if sticky is None else sticky)
        self._row = max(self._row, use_row) + 1
        self._blocks.append(widget)
        return widget

    # ---- 常用块 ----
    def section(self, title: str, *, columnspan: int = 1, sticky: str = "ew",
                pady: Optional[int] = None):
        """带标题的区块（ttk.LabelFrame），内部由调用方自己 grid。"""
        from tkinter import ttk
        frame = ttk.LabelFrame(self.parent, text=title)
        return self.grid(frame, columnspan=columnspan, sticky=sticky, pady=pady)

    def action_bar(self, *, columns: int = 4, sticky: str = "w", padx: int = 4,
                   pady: int = 3, group: Optional[ButtonGroup] = None,
                   on_change: Optional[Callable[[Dict[str, str]], None]] = None) -> ActionBar:
        """紧跟其后的一条按钮条（按钮多于 ``columns`` 时在块内自动换行）。

        行号由 :meth:`_flush` 在"下一次放置"时按实际占用行数结算，
        所以调用方**不需要**保证 ``columns >= 按钮个数``。
        """
        self._flush()
        bar = ActionBar(self.parent, row=self._row, column=self.column, columns=columns,
                        sticky=sticky, padx=padx, pady=pady, use_ttk=self.use_ttk,
                        group=group, on_change=on_change)
        self._pending_bar = bar
        self._blocks.append(bar)
        return bar

    def row(self, *widgets, sticky: str = "w", pady: Optional[int] = None):
        """把若干控件并排放在当前行（各占一列，列号自动递增）。"""
        self._flush()
        use_pady = self.pady if pady is None else pady
        for index, widget in enumerate(widgets):
            widget.grid(row=self._row, column=self.column + index,
                        padx=self.padx, pady=use_pady, sticky=sticky)
            self._blocks.append(widget)
        self._row += 1
        return widgets

    def form_row(self, *pairs, pady: Optional[int] = None):
        """一行表单：成对的 (标签文字, 控件)，标签在左、控件在右，各占两列。

            stack.form_row(("平台", self.platform_cb), ("曝光值", self.exposure_cb))
        """
        import tkinter as tk
        from .theme import Theme
        self._flush()
        use_pady = self.pady if pady is None else pady
        column = self.column
        for label_text, widget in pairs:
            tk.Label(self.parent, text=label_text, **Theme.field_label()).grid(
                row=self._row, column=column, padx=(0, 4), pady=use_pady, sticky="w")
            widget.grid(row=self._row, column=column + 1, padx=(0, 14), pady=use_pady,
                        sticky="w")
            column += 2
        self._row += 1
        return pairs

    def note(self, text: str, *, columnspan: int = 1, sticky: str = "w"):
        """一行说明文字（小号灰字，样式来自 Theme）。"""
        import tkinter as tk
        from .theme import Theme
        label = tk.Label(self.parent, text=text, **Theme.hint_label())
        return self.grid(label, columnspan=columnspan, sticky=sticky)
