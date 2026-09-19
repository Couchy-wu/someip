# -*- coding: utf-8 -*-
"""tests/test_someip_gui.py —— SOME/IP 回放界面测试（无显示器时自动跳过）

覆盖：
  · 窗口能被创建，布局要素齐全（事件表 23 行、状态栏、动作按钮）
  · 字段表按 ctypes 结构体自动生成（含 VehiclePosition 专用接口）
  · 勾选交互（全选/全不选/仅结构化类型）与配置同步
  · **库不可用时的降级**：动作按钮置灰、提示只弹一次、调用不崩溃、可安全关闭
  · 关闭时保存配置并释放资源

说明：GUI 测试需要显示环境；容器内由 Xvfb 提供（DISPLAY=:99）。
无 DISPLAY 时整体跳过，不影响其它测试。
"""
from __future__ import annotations

import os

import pytest

tk = pytest.importorskip("tkinter")

if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    pytest.skip("无显示环境（需 Xvfb/桌面），跳过 GUI 测试", allow_module_level=True)


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
