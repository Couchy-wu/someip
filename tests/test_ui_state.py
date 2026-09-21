# -*- coding: utf-8 -*-
"""tests/test_ui_state.py —— 界面按钮状态机（hudcore.ui.state）

这些用例**不需要显示器**：状态与规则都是纯数据/纯函数，
控件用假对象替换即可验证"哪个状态该点亮哪个按钮"。

覆盖：
  · UiState 的不可变语义（with_busy/with_flags/cleared/flag/busy_is/describe）
  · ButtonGroup 按规则表刷新、只报告"发生变化"的项、规则抛异常时按不可用处理、
    控件已销毁时不崩、force() 的应急语义
  · CAN 界面的规则表（can_gui.gui_layout.RULES）逐条语义
"""
from __future__ import annotations

import pytest

from hudcore.ui import (
    BUSY_CLOSE, BUSY_INIT, BUSY_NONE, BUSY_PROBE, BUSY_TEST, ButtonGroup, UiState,
)


class _FakeButton:
    """最小控件替身：只支持 configure(state=...) / config(state=...)。"""

    def __init__(self, fail: bool = False):
        self.states: list[str] = []
        self.fail = fail

    def configure(self, **kwargs):
        if self.fail:
            raise RuntimeError("控件已销毁")
        if "state" in kwargs:
            self.states.append(str(kwargs["state"]))

    config = configure

    @property
    def state(self) -> str:
        return self.states[-1] if self.states else "normal"


# ---------------------------------------------------------------- UiState
def test_state_is_immutable_and_derives_new_states():
    base = UiState()
    busy = base.with_busy(BUSY_PROBE)
    flags = base.with_flags(device_open=True)

    assert base.busy == BUSY_NONE and base.idle
    assert busy.busy == BUSY_PROBE and not busy.idle
    assert flags.flag("device_open") is True
    assert base.flag("device_open") is False, "原状态不能被改动"
    assert busy.flags == {} and flags.busy == BUSY_NONE


def test_state_flag_default_and_busy_is():
    state = UiState(busy=BUSY_INIT, flags={"testing": True})
    assert state.flag("testing") is True
    assert state.flag("missing") is False
    assert state.flag("missing", default=True) is True
    assert state.busy_is(BUSY_INIT, BUSY_CLOSE) is True
    assert state.busy_is(BUSY_PROBE) is False
    assert UiState().busy_is() is True, "空集合表示空闲"


def test_state_cleared_and_describe():
    state = UiState(busy=BUSY_TEST, library_ok=False, flags={"testing": True})
    assert state.cleared().busy == BUSY_NONE
    text = state.describe()
    assert "testing" in text and "busy=test" in text and "库不可用" in text


# ---------------------------------------------------------------- ButtonGroup
def test_button_group_applies_rules_and_reports_only_changes():
    group = ButtonGroup("t")
    ok = _FakeButton()
    group.add("a", ok, lambda s: s.idle)
    group.add("b", _FakeButton(), lambda s: s.flag("device_open"))
    group.add("c", _FakeButton())                      # 规则为空 = 始终可用

    first = group.apply(UiState())
    assert first == {"a": "normal", "b": "disabled", "c": "normal"}
    assert group.enabled_keys() == ("a", "c") and group.disabled_keys() == ("b",)

    again = group.apply(UiState())
    assert again == {}, "状态没变就不该重复 configure（减少无谓重绘）"

    changed = group.apply(UiState(busy=BUSY_INIT, flags={"device_open": True}))
    assert changed == {"a": "disabled", "b": "normal"}
    assert ok.states == ["normal", "disabled"]


def test_rule_exception_treated_as_disabled():
    group = ButtonGroup("t")
    btn = _FakeButton()

    def boom(_state):
        raise ValueError("规则写错")

    group.add("x", btn, boom)
    assert group.apply(UiState()) == {"x": "disabled"}
    assert btn.state == "disabled", "规则异常时应保守地置灰，而不是崩界面"


def test_destroyed_widget_does_not_break_apply():
    group = ButtonGroup("t")
    group.add("dead", _FakeButton(fail=True), lambda s: True)
    assert group.apply(UiState()) == {}, "控件已销毁 → 跳过，不影响其它控件"
    assert group.snapshot == {}


def test_force_overrides_rules_and_registry_queries():
    group = ButtonGroup("t")
    btn = _FakeButton()
    group.add("a", btn, lambda s: True)

    group.force("disabled", "a")
    assert btn.state == "disabled" and group.disabled_keys() == ("a",)
    group.force("normal", "a")
    assert btn.state == "normal"
    group.force("disabled", "not-registered")          # 未登记 → 静默忽略

    assert group.has("a") and "a" in group and len(group) == 1
    assert group.keys() == ("a",) and group.widget("a") is btn
    group.forget("a")
    assert len(group) == 0 and group.snapshot == {}


def test_group_on_change_callback_receives_changes():
    seen: list[dict] = []
    group = ButtonGroup("t", on_change=seen.append)
    group.add("a", _FakeButton(), lambda s: s.idle)
    group.apply(UiState(busy=BUSY_INIT))
    assert seen == [{"a": "disabled"}]


def test_group_on_change_callback_exception_is_swallowed():
    def boom(_changes):
        raise RuntimeError("回调炸了")

    group = ButtonGroup("t", on_change=boom)
    group.add("a", _FakeButton(), lambda s: s.idle)
    assert group.apply(UiState()) == {"a": "normal"}, "回调异常不该影响状态刷新"


# ---------------------------------------------------------------- CAN 规则表
@pytest.fixture()
def rules():
    from can_gui.gui_layout import RULES
    return RULES


def _state(**flags):
    return UiState(flags=flags)


def test_can_rules_before_and_after_device_open(rules):
    closed = _state(device_open=False)
    opened = _state(device_open=True)

    assert rules["probe"](closed) is True and rules["init"](closed) is True
    assert rules["close"](closed) is False
    for key in ("on_signal", "off_signal", "test"):
        assert rules[key](closed) is False, f"{key} 在没有设备时不该可点"
    assert rules["sub"](closed) is True, "设备管理不依赖设备状态"

    assert rules["close"](opened) is True
    assert rules["probe"](opened) is False, "设备已打开时不该再初始化"
    for key in ("on_signal", "off_signal", "test"):
        assert rules[key](opened) is True


def test_can_rules_during_testing(rules):
    testing = _state(device_open=True, testing=True)
    idle = _state(device_open=True, testing=False)

    assert rules["test"](testing) is False and rules["test"](idle) is True
    assert rules["pause"](testing) is True and rules["pause"](idle) is False
    assert rules["stop"](testing) is True and rules["stop"](idle) is False
    for key in ("on_signal", "off_signal", "repeat", "rounds", "platform", "exposure",
                "rotate", "perspective", "opt_image_test", "opt_capture", "opt_mirror",
                "opt_transform", "transform_kind"):
        assert rules[key](testing) is False, f"测试运行中 {key} 应被锁住"
        assert rules[key](idle) is True


def test_can_rules_blocked_while_busy(rules):
    busy = UiState(busy=BUSY_PROBE, flags={"device_open": True})
    assert rules["close"](busy) is False and rules["sub"](busy) is False
    assert rules["pause"](UiState(busy=BUSY_CLOSE, flags={"testing": True})) is True, \
        "测试中的暂停按钮与一次性动作无关"
