# -*- coding: utf-8 -*-
"""tests/test_someip_ui_rules.py —— SOME/IP 回放窗口的**按钮规则表**（someip_gui.ui_rules）

为什么单独一个文件：规则是 ``UiState -> bool`` 的纯函数，本就不需要 Tk / 显示器，
而 ``tests/test_someip_gui.py`` 在没有 DISPLAY 时会整模块跳过（GUI 用例必须如此）。
把纯函数断言搬到这里后，**无头 CI（Linux 容器不带 Xvfb、Windows 套件）也能覆盖
"哪个状态点亮哪个按钮"**，不会再被"没有显示器"跳过。

覆盖：
  · 规则表键集合 = 全部按钮键，且正确区分"需要库可用"与"不依赖库"两组；
  · 库不可用 → 动作按钮全灰，而「重新检测库/导出服务表/保存配置」仍可点（否则点不回来）；
  · 生命周期：未打开 → 已打开 → 已启动 → 回放中 → 关闭后的可用性；
  · busy（打开中/启动中/发送中/停止关闭中）期间动作按钮全灰；
  · 状态栏合成：库不可用时带红字原因（首行、限长），可用时给出阶段与计数。
"""
from __future__ import annotations

from hudcore.ui import BUSY_ACT, BUSY_CLOSE, BUSY_EXECUTE, BUSY_INIT, BUSY_NONE, BUSY_PROBE
from hudcore.ui import UiState
from someip_gui import ui_rules as R


def _state(*, library_ok: bool = True, busy: str = BUSY_NONE, **flags: bool) -> UiState:
    return UiState(busy=busy, library_ok=library_ok,
                   flags={k: v for k, v in flags.items()})


def _on(state: UiState, key: str) -> bool:
    """该状态下这个按钮是否可点（规则表的判定结果）。"""
    return bool(R.RULES[key](state))


# ---------------------------------------------------------------- 规则表结构
def test_rule_table_covers_every_button_key():
    assert set(R.RULES) == set(R.ALL_KEYS)
    assert len(R.ALL_KEYS) == 10
    assert set(R.ALL_KEYS) == set(R.LIBRARY_ACTION_KEYS) | set(R.LIBRARY_FREE_KEYS)
    assert not set(R.LIBRARY_ACTION_KEYS) & set(R.LIBRARY_FREE_KEYS)
    # busy 映射表要覆盖全部动作（动作方法用 BUSY_BY_ACTION 进入"忙"状态）
    assert set(R.BUSY_BY_ACTION) == {"open", "start", "stop", "close", "replay", "send",
                                     "recheck"}


# ---------------------------------------------------------------- 库可用性
def test_library_unavailable_disables_actions_but_keeps_recovery_buttons():
    state = _state(library_ok=False)
    for key in R.LIBRARY_ACTION_KEYS:
        assert _on(state, key) is False, f"库不可用时 {key} 应置灰"
    for key in R.LIBRARY_FREE_KEYS:
        assert _on(state, key) is True, f"{key} 不依赖库，否则库一丢就再也点不回来"


# ---------------------------------------------------------------- 生命周期
def test_lifecycle_open_start_stop_close():
    unopened = _state()
    assert _on(unopened, R.KEY_OPEN) is True
    for key in (R.KEY_START, R.KEY_STOP, R.KEY_CLOSE):
        assert _on(unopened, key) is False

    opened = _state(opened=True)
    assert _on(opened, R.KEY_START) is True
    assert _on(opened, R.KEY_STOP) is False and _on(opened, R.KEY_CLOSE) is True
    assert _on(opened, R.KEY_OPEN) is False, "实例已存在 → 打开置灰（重复打开无意义）"

    started = _state(opened=True, started=True)
    assert _on(started, R.KEY_START) is False and _on(started, R.KEY_STOP) is True
    assert _on(started, R.KEY_CLOSE) is True, "已启动也能直接关闭（controller 会一并停回放）"


def test_replay_rules_are_mutually_exclusive():
    idle = _state(opened=True, started=True)
    assert _on(idle, R.KEY_REPLAY_START) is True and _on(idle, R.KEY_REPLAY_STOP) is False

    playing = _state(opened=True, started=True, replaying=True)
    assert _on(playing, R.KEY_REPLAY_START) is False and _on(playing, R.KEY_REPLAY_STOP) is True

    # 「开始回放」未打开实例时仍可用（会自动先开服务，既有便利行为）
    assert _on(_state(), R.KEY_REPLAY_START) is True
    assert _on(_state(), R.KEY_SEND) is True


def test_busy_blocks_actions_and_leaves_idle_again():
    for busy in (BUSY_INIT, BUSY_ACT, BUSY_CLOSE, BUSY_EXECUTE, BUSY_PROBE):
        state = _state(busy=busy, opened=True, started=True, replaying=True)
        for key in (R.KEY_OPEN, R.KEY_START, R.KEY_STOP, R.KEY_CLOSE,
                    R.KEY_REPLAY_START, R.KEY_SEND):
            assert _on(state, key) is False, f"{busy} 期间 {key} 应置灰"
    # 动作结束 → 恢复
    done = _state(opened=True, started=True, replaying=True)
    assert _on(done, R.KEY_STOP) is True and _on(done, R.KEY_REPLAY_STOP) is True


# ---------------------------------------------------------------- 状态栏文案
def test_phase_text_tracks_lifecycle_and_busy():
    assert R.phase_text(_state()) == "未打开"
    assert R.phase_text(_state(opened=True)) == "已打开"
    assert R.phase_text(_state(opened=True, started=True)) == "已启动"
    assert R.phase_text(_state(opened=True, started=True, replaying=True)) == "回放中"
    # BUSY_ACT 同时用于"启动服务"与"发送该事件"，按生命周期标志区分
    assert R.phase_text(_state(busy=BUSY_INIT)) == "打开中"
    assert R.phase_text(_state(busy=BUSY_ACT, opened=True)) == "启动中"
    assert R.phase_text(_state(busy=BUSY_ACT, opened=True, started=True)) == "发送中"
    assert R.phase_text(_state(busy=BUSY_CLOSE)) == "停止/关闭中"
    assert R.phase_text(_state(busy=BUSY_EXECUTE)) == "回放启停中"
    assert R.phase_text(_state(busy=BUSY_PROBE)) == "检测库中"


def test_one_line_reason_keeps_first_line_and_truncates():
    assert R.one_line_reason("") == ""
    assert R.one_line_reason("\n\n  第一行结论  \n第二行是操作步骤") == "第一行结论"
    long = "x" * 200
    out = R.one_line_reason(long, limit=10)
    assert len(out) == 10 and out.endswith("…")


def test_compose_status_available_unavailable_and_refresh_stable():
    ok = R.compose_status(_state(opened=True, started=True, replaying=True),
                          sent=1234, services=11, events=23)
    assert ok == "库就绪｜阶段：回放中｜回放中（已发 1234）｜服务 11/事件 23"
    assert R.compose_status(_state(opened=True, started=True), sent=0, services=11,
                            events=23) == "库就绪｜阶段：已启动｜未回放（已发 0）｜服务 11/事件 23"

    bad = R.compose_status(_state(library_ok=False), reason="未找到 SOME/IP 服务端库\n下一步…")
    assert "不可用" in bad and "原因：未找到 SOME/IP 服务端库" in bad and "阶段：未打开" in bad
    assert "下一步" not in bad, "原因只取首行（完整提示仍在日志区）"
