# -*- coding: utf-8 -*-
"""hudcore.ui.state —— 界面按钮状态机（与 Tk 解耦，可单测）
==========================================================
界面最容易写坏的地方是**按钮的可用性**：原实现把 ``btn.config(state=...)``
散落在初始化成功/关闭设备/开始测试/测试结束等多个回调里，于是出现

  · 同一个按钮在不同路径下规则不一致（关了设备后"开始测试"又变可点）；
  · 想加一个按钮就要在 5 个地方补一行；
  · 只能靠真机点界面验证，写不了单测。

本模块把这件事收敛成**一个状态源 + 一张规则表**：

    state = UiState(busy=BUSY_NONE, flags={"device_open": True, "testing": False})
    buttons.apply(state)          # 按规则表刷新所有已登记按钮；返回发生变化的项

  · :class:`UiState` 是不可变纯数据（不依赖 Tk），规则是 ``state -> bool`` 的纯函数，
    因此"哪个状态该点亮哪个按钮"可以直接用单测覆盖；
  · :class:`ButtonGroup` 负责把布尔结果落到控件（``configure(state=...)``），
    并记录最近一次快照，便于自检与排障；
  · 控件只需要提供 ``configure``/``config``，测试里可用假控件替换。

设计约束：本模块**不 import tkinter**，也不创建任何控件。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, Mapping, Optional

__all__ = [
    "BUSY_NONE", "BUSY_PROBE", "BUSY_INIT", "BUSY_CLOSE", "BUSY_TEST", "BUSY_SCAN",
    "BUSY_EXECUTE", "BUSY_ACT",
    "UiState", "ButtonGroup", "Rule",
]

# ---------------------------------------------------------------- 忙标志
# 同一时刻只允许一个"占用设备/串行"的动作，用字符串而不是多个布尔量表达，
# 这样"同一时间只跑一件事"的约束天然成立（switch_busy 覆盖而不是叠加）。
BUSY_NONE = ""
BUSY_PROBE = "probe"           # 检测设备
BUSY_INIT = "init"             # 初始化设备
BUSY_CLOSE = "close"           # 关闭设备
BUSY_TEST = "test"             # 自动化测试运行中
BUSY_SCAN = "scan"             # 扫描/解析用例
BUSY_EXECUTE = "execute"       # 批量执行用例
BUSY_ACT = "act"               # 其它一次性动作（发送/开窗等）

#: 规则函数：给定状态，返回该按钮是否可用
Rule = Callable[["UiState"], bool]


@dataclass(frozen=True)
class UiState:
    """界面状态快照（不可变）。

    :param busy: 当前占用的串行动作（见 ``BUSY_*``），``""`` 表示空闲
    :param library_ok: 依赖的运行时库是否可用（如 SOME/IP 库、CAN 驱动）
    :param flags: 业务自定义标志（``device_open`` / ``testing`` / ``opened`` …）
    """

    busy: str = BUSY_NONE
    library_ok: bool = True
    flags: Mapping[str, bool] = field(default_factory=dict)

    # ---- 查询 ----
    @property
    def idle(self) -> bool:
        """是否空闲（没有任何串行动作在跑）。"""
        return not self.busy

    def flag(self, name: str, default: bool = False) -> bool:
        return bool(self.flags.get(name, default))

    def busy_is(self, *names: str) -> bool:
        """当前忙标志是否属于给定集合（空集表示"空闲"）。"""
        if not names:
            return self.idle
        return self.busy in names

    # ---- 变更（返回新对象）----
    def with_busy(self, busy: str) -> "UiState":
        return replace(self, busy=busy)

    def with_flags(self, **flags: bool) -> "UiState":
        merged: Dict[str, bool] = dict(self.flags)
        merged.update(flags)
        return replace(self, flags=merged)

    def cleared(self) -> "UiState":
        """清空忙标志（动作结束）。"""
        return self.with_busy(BUSY_NONE)

    def describe(self) -> str:
        """一行摘要（状态栏/日志用）。"""
        parts = [f"busy={self.busy or '-'}"]
        if not self.library_ok:
            parts.append("库不可用")
        on = sorted(k for k, v in self.flags.items() if v)
        if on:
            parts.append("标志：" + ",".join(on))
        return "｜".join(parts)


class _Entry:
    __slots__ = ("widget", "rule", "key")

    def __init__(self, key: str, widget, rule: Optional[Rule]) -> None:
        self.key = key
        self.widget = widget
        self.rule = rule


class ButtonGroup:
    """一组按钮 + 一张规则表：``apply(state)`` 统一刷新可用性。

    用法::

        btn = ButtonGroup()
        btn.add("init", self.init_btn, lambda s: s.idle and not s.flag("device_open"))
        btn.apply(self._state())          # 之后只需改状态，不用再逐个 config
    """

    def __init__(self, name: str = "buttons",
                 on_change: Optional[Callable[[Dict[str, str]], None]] = None) -> None:
        self.name = name
        self._entries: Dict[str, _Entry] = {}
        self._on_change = on_change
        self.snapshot: Dict[str, str] = {}          # key -> "normal"/"disabled"（最近一次）

    # ---- 登记 ----
    def add(self, key: str, widget, rule: Optional[Rule] = None) -> object:
        """登记按钮；``rule`` 为空表示"始终可用"。返回控件本身便于链式写法。"""
        self._entries[key] = _Entry(key, widget, rule)
        return widget

    def keys(self) -> tuple[str, ...]:
        return tuple(self._entries)

    def widget(self, key: str):
        return self._entries[key].widget

    def has(self, key: str) -> bool:
        return key in self._entries

    def forget(self, key: str) -> None:
        self._entries.pop(key, None)
        self.snapshot.pop(key, None)

    # ---- 应用 ----
    def apply(self, state: UiState) -> Dict[str, str]:
        """按状态刷新所有按钮，返回本次**发生变化的** ``{key: 新状态}``。

        控件已销毁（窗口关闭）时忽略该控件，不让状态刷新增把界面拖崩。
        """
        changes: Dict[str, str] = {}
        for key, entry in self._entries.items():
            try:
                enabled = True if entry.rule is None else bool(entry.rule(state))
            except Exception:                       # noqa: BLE001 - 规则写错不该崩界面
                enabled = False
            want = "normal" if enabled else "disabled"
            if self.snapshot.get(key) == want:
                continue
            if _set_widget_state(entry.widget, want):
                self.snapshot[key] = want
                changes[key] = want
        if changes and self._on_change is not None:
            try:
                self._on_change(changes)
            except Exception:                       # noqa: BLE001
                pass
        return changes

    def force(self, state: str, *keys: str) -> None:
        """应急开关：绕过规则表直接设置（慎用；正常路径请改状态后 ``apply()``）。"""
        want = "normal" if state == "normal" else "disabled"
        for key in keys:
            entry = self._entries.get(key)
            if entry is not None and _set_widget_state(entry.widget, want):
                self.snapshot[key] = want

    def enabled_keys(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.snapshot.items() if v == "normal")

    def disabled_keys(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.snapshot.items() if v == "disabled")

    def __contains__(self, key: object) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)


def _set_widget_state(widget, state: str) -> bool:
    """给控件设置 state；支持 ``configure``（ttk/tk 均有）与 ``config``（tk 别名）。"""
    for setter in ("configure", "config"):
        fn = getattr(widget, setter, None)
        if fn is None:
            continue
        try:
            fn(state=state)
            return True
        except Exception:                            # noqa: BLE001 - 控件已销毁等
            return False
    return False
