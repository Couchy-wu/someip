# -*- coding: utf-8 -*-
"""tests/test_someip_gui.py —— SOME/IP 回放界面测试（无显示器时自动跳过）

覆盖：
  · 窗口能被创建，布局要素齐全（事件表 23 行、状态栏、动作按钮）
  · **整窗无 grid 格子冲突**（hudcore.ui.layout.audit_widget_tree）
  · **按钮规则表 + 状态流转**：库不可用全灰 → 打开后可启动 → 启动后可停止/关闭 →
    回放中"开始灰/停止亮" → 关闭后回到未打开态；busy 期间相关按钮置灰
  · **状态栏不被 800ms 定时刷新冲掉**（库不可用保持红字 + 原因）
  · 字段表按 ctypes 结构体自动生成（含 VehiclePosition 专用接口）
  · 勾选交互（全选/全不选/仅结构化类型）与配置同步
  · **库不可用时的降级**：动作按钮置灰、提示只弹一次、调用不崩溃、可安全关闭
  · 关闭时保存配置并释放资源

说明：GUI 测试需要显示环境；容器内由 Xvfb 提供（DISPLAY=:99）。
无 DISPLAY 时整体跳过，不影响其它测试。
"""
from __future__ import annotations

import time

import pytest

tk = pytest.importorskip("tkinter")

from tests import gui_support                     # noqa: E402

gui_support.require_display()                     # 无图形环境整模块跳过（Windows 本机不跳）


class _FakeButton:
    """假按钮：只需 ``configure(state=...)``，用于脱离 Tk 单测规则表。"""

    def __init__(self) -> None:
        self.state = "normal"

    def configure(self, **kw):                       # noqa: ANN003
        self.state = kw.get("state", self.state)

    def config(self, **kw):                          # noqa: ANN003
        self.configure(**kw)


def _fake_group():
    """按规则表登记全部按钮键，返回 (group, {key: 假按钮})。"""
    from hudcore.ui import ButtonGroup
    from someip_gui import ui_rules as R

    group = ButtonGroup("fake")
    widgets = {}
    for key in R.ALL_KEYS:
        widgets[key] = _FakeButton()
        group.add(key, widgets[key], R.RULES[key])
    return group, widgets


def _apply(group, *, library_ok=True, opened=False, started=False, replaying=False, busy=""):
    from hudcore.ui import UiState
    group.apply(UiState(busy=busy, library_ok=library_ok,
                        flags={"opened": opened, "started": started, "replaying": replaying}))
    return dict(group.snapshot)


def _fmt(snapshot) -> str:
    return "，".join(f"{k}={v}" for k, v in sorted(snapshot.items()))


class _FakeLib:
    """最小假库：只实现 `ReplayController` 实际用到的接口（不碰 ctypes/真实库）。

    每次调用都记录 ``(方法名, busy, opened, started, replaying)``，
    用来断言"动作进行期间 busy 已置位、状态栏能显示当前步骤"。
    """

    def __init__(self, calls, probe) -> None:
        self.calls = calls
        self.probe = probe                 # 返回 (busy, opened, started, replaying)
        self.created = 0
        self.started = 0
        self.destroyed = 0
        self.replays = 0

    def _note(self, name: str) -> None:
        self.calls.append((name,) + tuple(self.probe()))

    # ---- 会话 ----
    def create(self, unicast, config_path):
        self._note("create")
        self.created += 1
        return 1

    def add_service(self, handle, service, instance, port):
        self._note("add_service")
        return 0

    def add_event(self, handle, service, instance, event, group):
        self._note("add_event")
        return 0

    def start(self, handle):
        self._note("start")
        self.started += 1
        return 0

    def stop(self, handle):
        self._note("stop")
        return 0

    def destroy(self, handle):
        self._note("destroy")
        self.destroyed += 1
        return 0

    # ---- 回放/发送 ----
    def replay_start(self, handle, path, loop, interval):
        self._note("replay_start")
        self.replays += 1
        return 0

    def replay_stop(self, handle):
        self._note("replay_stop")
        return 0

    def replay_sent(self, handle):
        return 42

    def serialize(self, handle, kind, fields):
        self._note("serialize")
        return b"\x01\x02\x03\x04"

    def notify_raw(self, handle, service, event, data):
        self._note("notify_raw")
        return 0


@pytest.fixture(autouse=True)
def _isolate_replay_config(tmp_path, monkeypatch):
    """窗口关闭时会保存配置 —— 测试必须写临时文件，不能污染 data/someip/replay_config.json。

    （曾经踩过：跑完 GUI 测试后，仓库里的 pcap 路径被改成了容器路径 /work/…）
    """
    from someip_core import config as config_mod

    target = tmp_path / "replay_config.json"
    monkeypatch.setattr(config_mod, "config_path", lambda: target)
    yield target


@pytest.fixture()
def window(monkeypatch):
    """创建窗口并把模态弹窗打桩（无人值守下不可阻塞）。"""
    from tkinter import messagebox
    from someip_gui import open_replay_window

    warns: list = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: warns.append(a[:1]))
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: warns.append(a[:1]))

    root = tk.Tk()
    root.withdraw()
    win = open_replay_window(root)
    win.update_idletasks()
    yield win, warns
    try:
        app = getattr(win, "someip_app", None)
        if app is not None and not app._closing:
            app.on_closing()
    except Exception:                                            # noqa: BLE001
        pass
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_window_layout_and_event_table(window):
    from someip_core import all_events
    win, _warns = window
    app = win.someip_app
    assert win.winfo_exists()
    assert len(app.event_tree.get_children()) == len(all_events()) == 23
    # 表头列齐全
    cols = app.event_tree["columns"]
    assert set(cols) >= {"on", "svc", "evt", "name", "kind", "port", "tp"}
    # 状态栏与工具栏按钮存在
    assert app.lbl_status.cget("text")
    for btn in (app.btn_open, app.btn_start, app.btn_stop, app.btn_close,
                app.btn_replay_start, app.btn_replay_stop, app.btn_send):
        assert btn.winfo_exists()


def test_field_table_generated_from_structs(window):
    win, _warns = window
    app = win.someip_app
    expected_min = {"RTK": 20, "IMU": 10, "PilotStatus": 5, "Broadcast": 4,
                    "VehiclePosition": 30, "HudNavmap": 2}
    for kind, minimum in expected_min.items():
        app.var_kind.set(kind)
        app._on_kind_changed()
        n = len(app.field_table._entries)
        assert n >= minimum, f"{kind} 字段数异常：{n}（应 ≥ {minimum}）"
    # Checksum 只读（由库自动计算 CRC32）
    app.var_kind.set("RTK")
    app._on_kind_changed()
    entry = app.field_table._entries["Checksum"][0]
    assert str(entry.cget("state")) == "readonly"
    # 清零与示例值
    app.field_table.clear()
    cleared = app.field_table.values()
    assert cleared, "清零后仍应回读字段（值为默认 0/0.0/空）"
    assert set(cleared.values()) <= {0, 0.0, ""}, f"清零后应全为默认值：{cleared}"
    app._on_fill_sample()
    vals = app.field_table.values()
    assert vals.get("Counter") == 1 and vals.get("satellite_num") == 18


def test_selection_interactions(window):
    win, _warns = window
    app = win.someip_app
    app._select_all(False)
    assert app.config.selected == []
    marks = {str(app.event_tree.item(i)["values"][0]) for i in app.event_tree.get_children()}
    assert marks == {"☐"}
    app._select_struct_only()
    marks = {str(app.event_tree.item(i)["values"][0]) for i in app.event_tree.get_children()}
    assert "☑" in marks and "☐" in marks, "仅结构化类型应只勾选部分事件"
    app._select_all(True)
    marks = {str(app.event_tree.item(i)["values"][0]) for i in app.event_tree.get_children()}
    assert marks == {"☑"}


def test_degraded_when_library_missing(window, monkeypatch):
    """库不可用（Windows 现状）：动作置灰、提示一次、调用不崩、可关闭。

    注意：必须同时阻断 `api.open_library()` —— 否则在"已经放好真实库"的机器上，
    本用例会真的去创建 vsomeip 应用（可能直接 abort 掉整个 pytest 进程），
    这既不是本用例的目的，也会让测试结果不可信。
    """
    import hudcore.someip as hs
    import someip_core.api as api_mod
    win, warns = window
    app = win.someip_app
    monkeypatch.setattr(api_mod, "open_library", lambda: None)
    monkeypatch.setattr(hs, "is_library_available", lambda: False)
    monkeypatch.setattr("someip_gui.replay_window.is_library_available", lambda: False)
    app._apply_library_state()
    assert str(app.btn_replay_start.cget("state")) == "disabled"
    assert "不可用" in str(app.lbl_status.cget("text"))

    app.on_replay_start()
    app.on_replay_start()
    assert len(warns) <= 1, "库不可用提示应只弹一次（其余仅记日志）"
    assert int(app.log_text.index("end-1c").split(".")[0]) >= 2, "操作应写入日志"
    app.on_closing()
    app._closing = False


def test_config_persisted_on_close(window, tmp_path, monkeypatch):
    import someip_core.config as cfg_mod
    target = tmp_path / "replay_config.json"
    original_save = cfg_mod.ReplayConfig.save          # 存原函数，避免打桩自我递归
    monkeypatch.setattr(cfg_mod.ReplayConfig, "save",
                        lambda self, path=None: original_save(self, target))
    win, _warns = window
    app = win.someip_app
    app.var_unicast.set("192.168.9.9")
    app.var_loop.set(False)
    app.on_closing()
    app._closing = False
    assert target.is_file()
    saved = cfg_mod.ReplayConfig.load(target)
    assert saved.unicast == "192.168.9.9" and saved.loop is False


# ---------------------------------------------------------------------------
# 按钮规则表（纯函数）已移到 tests/test_someip_ui_rules.py —— 那里没有
# DISPLAY 守卫，无头 CI 也能覆盖；本文件保留需要真实窗口的用例。
# ---------------------------------------------------------------------------
def test_no_grid_collisions(window):
    """整窗不允许两个控件占用同一个 (row, column)（含 field_table 内部的 grid）。"""
    from hudcore.ui.layout import audit_widget_tree, describe_collisions

    win, _warns = window
    collisions = audit_widget_tree(win)
    print("格子冲突审计：", describe_collisions(collisions))
    assert collisions == [], describe_collisions(collisions)


def test_button_rules_follow_controller_state(window, monkeypatch):
    """界面侧状态流转：改 controller.state → `_apply_ui_state()` → 控件实际可用性。"""
    from hudcore.ui import BUSY_INIT, Theme
    from someip_gui import ui_rules as R

    win, _warns = window
    app = win.someip_app

    def snapshot(note: str):
        app._apply_ui_state()
        state = app._ui_state()
        print(f"{note}｜阶段={R.phase_text(state)}｜状态栏={app.lbl_status.cget('text')}")
        print("   ", _fmt(app.buttons.snapshot))
        return dict(app.buttons.snapshot)

    for key in R.ALL_KEYS:
        assert key in app.buttons, f"{key} 未登记进状态机"

    def ctl(**kw):
        for name, value in kw.items():
            setattr(app.controller.state, name, value)

    # ① 库不可用（Windows 现状）→ 动作按钮全灰；状态栏红字 + 原因
    monkeypatch.setattr("someip_gui.replay_window.is_library_available", lambda: False)
    snap = snapshot("① 库不可用")
    for key in R.LIBRARY_ACTION_KEYS:
        assert snap[key] == "disabled"
    text = str(app.lbl_status.cget("text"))
    assert "不可用" in text and "原因：" in text, text
    fg = str(app.lbl_status.cget("foreground")).lower()
    print("   状态栏前景色：", fg)
    assert fg == Theme.DANGER.lower(), f"库不可用应为红字，实际 {fg}"

    # ② 库可用、未打开
    monkeypatch.setattr("someip_gui.replay_window.is_library_available", lambda: True)
    ctl(opened=False, started=False, replaying=False)
    snap = snapshot("② 未打开")
    assert snap[R.KEY_OPEN] == "normal" and snap[R.KEY_START] == "disabled"
    assert snap[R.KEY_REPLAY_START] == "normal" and snap[R.KEY_SEND] == "normal"

    # ③ 已打开未启动
    ctl(opened=True)
    snap = snapshot("③ 已打开")
    assert snap[R.KEY_START] == "normal" and snap[R.KEY_STOP] == "disabled"
    assert snap[R.KEY_CLOSE] == "normal" and snap[R.KEY_OPEN] == "disabled"

    # ④ 已启动
    ctl(started=True)
    snap = snapshot("④ 已启动")
    assert snap[R.KEY_STOP] == "normal" and snap[R.KEY_START] == "disabled"
    assert snap[R.KEY_CLOSE] == "normal"

    # ⑤ busy（打开中）：相关按钮置灰，动作结束自动恢复
    with app._busy(BUSY_INIT):
        snap = snapshot("⑤ busy=打开中")
        for key in (R.KEY_OPEN, R.KEY_START, R.KEY_STOP, R.KEY_CLOSE,
                    R.KEY_REPLAY_START, R.KEY_SEND):
            assert snap[key] == "disabled", f"打开中 {key} 应置灰"
    snap = snapshot("⑤ 打开完成")
    assert snap[R.KEY_STOP] == "normal" and snap[R.KEY_REPLAY_START] == "normal"

    # ⑥ 回放中：开始回放灰 / 停止回放亮
    ctl(replaying=True)
    snap = snapshot("⑥ 回放中")
    assert snap[R.KEY_REPLAY_START] == "disabled" and snap[R.KEY_REPLAY_STOP] == "normal"

    # ⑦ 关闭服务后回到未打开态
    ctl(opened=False, started=False, replaying=False)
    snap = snapshot("⑦ 关闭后")
    assert snap[R.KEY_OPEN] == "normal" and snap[R.KEY_START] == "disabled"
    assert snap[R.KEY_STOP] == "disabled" and snap[R.KEY_CLOSE] == "disabled"
    assert snap[R.KEY_REPLAY_STOP] == "disabled"

    # 控件本身的 state 也真的变了（不是只改了快照）
    assert str(app.btn_stop.cget("state")) == "disabled"
    assert str(app.btn_open.cget("state")) == "normal"
    assert str(app.btn_replay_start.cget("state")) == "normal"


def test_status_bar_survives_timed_refresh(window, monkeypatch):
    """库不可用时的红字提示不能被 800ms 定时刷新（controller.summary）冲掉。"""
    from hudcore.ui import Theme

    win, _warns = window
    app = win.someip_app
    monkeypatch.setattr("someip_gui.replay_window.is_library_available", lambda: False)
    app._apply_ui_state()
    first = str(app.lbl_status.cget("text"))
    assert "不可用" in first and "原因：" in first, first

    # 手动跑一次心跳，再让事件循环真正跑过 800ms 定时器
    app._tick()
    assert str(app.lbl_status.cget("text")) == first, "定时刷新不该改写库不可用提示"

    deadline = time.time() + 1.2
    ticks = 0
    while time.time() < deadline:
        win.update()
        ticks += 1
        time.sleep(0.02)
    after = str(app.lbl_status.cget("text"))
    print(f"定时刷新 {ticks} 次后状态栏：{after}")
    assert after == first, f"800ms 刷新后状态栏被冲掉：{after!r}"
    assert "库就绪" not in after
    assert str(app.lbl_status.cget("foreground")).lower() == Theme.DANGER.lower()

    # 恢复库可用 → 状态栏回到"库就绪｜阶段：…"
    monkeypatch.setattr("someip_gui.replay_window.is_library_available", lambda: True)
    app._apply_ui_state()
    ok_text = str(app.lbl_status.cget("text"))
    print("库恢复后状态栏：", ok_text)
    assert ok_text.startswith("库就绪｜阶段：") and "不" not in ok_text.split("｜")[0]


def test_real_actions_drive_state_machine_with_fake_library(window, monkeypatch, tmp_path):
    """用假库跑真实动作链：动作方法只改状态/调 controller，按钮由规则表自动刷新。

    同时验证既有便利行为未变：未打开实例时「开始回放」「发送该事件」会自动先开服务。
    """
    from pathlib import Path

    import someip_core.config as cfg_mod
    from hudcore.ui import BUSY_ACT, BUSY_EXECUTE, BUSY_INIT
    from hudcore.ui.state import BUSY_NONE
    from someip_core import ReplayController
    from someip_gui import ui_rules as R

    win, warns = window
    app = win.someip_app
    monkeypatch.setattr("someip_gui.replay_window.is_library_available", lambda: True)
    # 配置落盘改到临时目录：本用例会改 pcap 路径，别污染仓库里的 replay_config.json
    original_save = cfg_mod.ReplayConfig.save
    monkeypatch.setattr(cfg_mod.ReplayConfig, "save",
                        lambda self, path=None: original_save(self, tmp_path / "cfg.json"))

    calls: list = []

    def probe():
        st = app.controller.state
        return (app._ui_busy, st.opened, st.started, st.replaying)

    lib = _FakeLib(calls, probe)
    app.controller = ReplayController(on_log=app.log, lib=lib)   # 注入假库（不碰真实库）
    sample = Path(__file__).resolve().parents[1] / "data/someip/sample/out_sample.pcap"
    assert sample.is_file(), sample
    app.var_pcap.set(str(sample))
    app.var_kind.set("RTK")

    # ---- 开始回放：未打开实例 → 自动"打开服务 + 启动服务" ----
    app.on_replay_start()
    by_name = {name: busy for name, busy, *_ in calls}
    print("库调用期间的 busy：", by_name)
    assert lib.created == 1, "未打开时应自动打开服务（既有便利行为）"
    assert lib.replays == 1 and app.controller.state.replaying
    assert by_name["create"] == BUSY_INIT, "打开服务期间 busy 应为 BUSY_INIT"
    assert by_name["replay_start"] == BUSY_EXECUTE, "回放期间 busy 应为 BUSY_EXECUTE"
    assert app._ui_busy == BUSY_NONE, "动作结束后 busy 应自动清空"
    snap = app.buttons.snapshot
    print("回放中快照：", _fmt(snap))
    assert (snap[R.KEY_REPLAY_START], snap[R.KEY_REPLAY_STOP]) == ("disabled", "normal")
    assert snap[R.KEY_STOP] == "normal" and snap[R.KEY_OPEN] == "disabled"
    assert snap[R.KEY_CLOSE] == "normal"

    # ---- 发送单条：结构化字段 → 库 serialize + notify_raw（busy=BUSY_ACT）----
    app.on_send_struct()
    by_name = {name: busy for name, busy, *_ in calls}
    assert by_name["notify_raw"] == BUSY_ACT
    assert app._ui_busy == BUSY_NONE
    assert "已发送 RTK" in app.log_text.get("1.0", "end")

    # ---- 定时刷新读回放计数 → 状态栏合成一行 ----
    app._tick()
    status = str(app.lbl_status.cget("text"))
    print("状态栏：", status)
    assert "阶段：回放中" in status and "已发 42" in status
    assert str(app.lbl_replay_stat.cget("text")) == "已发送 42 条"

    # ---- 停止回放 → 停止服务 → 关闭服务：状态逐步回退 ----
    app.on_replay_stop()
    snap = app.buttons.snapshot
    print("停止回放后：", _fmt(snap))
    assert (snap[R.KEY_REPLAY_START], snap[R.KEY_REPLAY_STOP]) == ("normal", "disabled")
    assert snap[R.KEY_STOP] == "normal"

    app.on_stop()
    snap = app.buttons.snapshot
    print("停止服务后：", _fmt(snap))
    assert (snap[R.KEY_START], snap[R.KEY_STOP]) == ("normal", "disabled")
    assert snap[R.KEY_CLOSE] == "normal"

    app.on_close_session()
    snap = app.buttons.snapshot
    print("关闭服务后：", _fmt(snap))
    assert (snap[R.KEY_OPEN], snap[R.KEY_START], snap[R.KEY_STOP], snap[R.KEY_CLOSE]) == (
        "normal", "disabled", "disabled", "disabled")
    assert lib.destroyed == 1 and app._ui_busy == BUSY_NONE

    # ---- 库不可用时不弹窗打扰（本用例全程无弹窗）----
    assert warns == []
    app.on_closing()                                  # 收尾（避免 fixture teardown 再写真实配置）


def test_on_closing_releases_and_returns_idle(window, monkeypatch, tmp_path):
    """on_closing()：停回放 → 关服务 → 保存配置 → 销毁窗口（假库验证调用顺序）。"""
    import someip_core.config as cfg_mod

    from hudcore.ui.state import BUSY_NONE
    from someip_core import ReplayController

    target = tmp_path / "replay_config.json"
    original_save = cfg_mod.ReplayConfig.save          # 存原函数，避免打桩自我递归
    monkeypatch.setattr(cfg_mod.ReplayConfig, "save",
                        lambda self, path=None: original_save(self, target))

    win, _warns = window
    app = win.someip_app
    monkeypatch.setattr("someip_gui.replay_window.is_library_available", lambda: True)
    calls: list = []
    lib = _FakeLib(calls, lambda: (app._ui_busy, True, True, True))
    app.controller = ReplayController(on_log=app.log, lib=lib)
    app.controller.state.opened = True
    app.controller.state.started = True
    app.controller.state.replaying = True
    app.controller._handle = 1                       # 让 close() 走到库调用
    app.on_closing()
    names = [name for name, *_ in calls]
    print("关闭时的库调用：", names)
    assert names[:2] == ["replay_stop", "destroy"], "应先停回放再销毁实例"
    assert app.controller.state.opened is False and app.controller.state.replaying is False
    assert app._ui_busy == BUSY_NONE
    assert target.is_file(), "关闭时应保存配置"
    try:
        assert not win.winfo_exists(), "关闭后窗口应被销毁"
    except tk.TclError:                              # 已销毁的控件查询可能抛 TclError
        pass

