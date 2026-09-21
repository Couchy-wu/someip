# -*- coding: utf-8 -*-
"""tests/test_main_window.py —— 主窗口「布局分组 + 单例子窗口」验收
=====================================================================
本次界面重构（main.py）要自证的三件事，全部可无头运行（xvfb-run），
**不需要**真实 CAN 设备 / 相机：

  1. **布局**：整窗 `hudcore.ui.layout.audit_widget_tree()` 零格子冲突 ——
     左侧功能区（`left_frame`）在 column 0、右侧日志面板（`log_main_frame`）在 column 1，
     区块/按钮的行列由 `SectionStack` + `ActionBar` 自动分配；
  2. **单例**：三个入口（`open_can_gui` / `open_someip_replay` / `open_di_cases`）
     连续调用两次不会建出第二个窗口，已打开期间入口按钮 `disabled`；
  3. **恢复**：窗口关闭（WM_DELETE_WINDOW 统一回调）**或**被直接 `destroy()` 之后，
     按钮都回到 `normal`；开窗失败（异常）也不会把按钮永久灰掉。

实现注意：`MainWindow.__init__` 会把 `sys.stdout` 换成 `TextRedirector`，
因此 teardown 必须恢复 `sys.stdout` 并调用 `on_closing()`（取消时钟 after 回调、销毁窗口）；
布局审计结果用 `sys.__stdout__` 打印，避免被重定向进日志文本框。
"""
from __future__ import annotations

import sys
import tkinter as tk
from dataclasses import replace
from tkinter import ttk

import pytest

import main as main_module
from hudcore.ui.layout import audit_widget_tree, describe_collisions

from tests import gui_support                     # noqa: E402

gui_support.require_display()                     # 无图形环境整模块跳过（Windows 本机不跳）

#: (kind, 打开方法, 关闭方法, 按钮属性名, 窗口属性名, 状态标志)
SINGLETONS = [
    ("can", "open_can_gui", "_on_can_window_close",
     "can_control_button", "_can_window", "can_window_open"),
    ("someip", "open_someip_replay", "_on_someip_window_close",
     "someip_button", "_someip_window", "someip_window_open"),
    ("di", "open_di_cases", "_on_di_window_close",
     "di_case_button", "_di_window", "di_window_open"),
]

#: 重构要求保留的按钮属性名（已有测试/文档会引用）
BUTTON_ATTRS = [
    "upload_button", "delete_button", "view_button", "inspect_button",
    "convert_matrix_button", "hex_button", "can_control_button", "someip_button",
    "image_button", "read_video_button", "image_video_button", "di_case_button",
]


def _section_titles(win) -> list[str]:
    """左侧功能区里的区块标题（自上而下的顺序）。"""
    return [w.cget("text") for w in win.left_frame.winfo_children()
            if isinstance(w, ttk.LabelFrame)]


def _state_of(widget) -> str:
    return str(widget["state"])


@pytest.fixture(autouse=True)
def _isolate_someip_config(tmp_path, monkeypatch):
    """本模块会打开**真实**的 SOME/IP 子窗口，它在关闭时会保存配置 ——
    必须写到临时目录，否则会污染仓库里的 data/someip/replay_config.json
    （实测会把 service_table / pcap 路径等键写进去）。
    """
    from someip_core import config as config_mod

    target = tmp_path / "replay_config.json"
    monkeypatch.setattr(config_mod, "config_path", lambda: target)
    yield target


@pytest.fixture
def win():
    """建主窗口（隐藏）并在 teardown 里恢复 stdout + 关窗。"""
    original_stdout = sys.stdout
    window = main_module.MainWindow()
    window.root.withdraw()
    window.root.update_idletasks()
    try:
        yield window
    finally:
        window.on_closing()
        sys.stdout = original_stdout            # 双保险：on_closing 已还原，这里兜底


# ---------------------------------------------------------------- ① 布局
def test_no_grid_collisions_in_whole_window(win):
    """整窗（含各区块、按钮条、日志面板）不得有两控件占同一 (row, column)。"""
    collisions = audit_widget_tree(win.root)
    sys.__stdout__.write("[布局审计] " + describe_collisions(collisions) + "\n")
    sys.__stdout__.flush()
    assert collisions == [], describe_collisions(collisions)


def test_left_sections_and_right_log_panel_are_separate_columns(win):
    """左侧功能区与右侧日志面板分列（不共用列，也不会互相盖住）。"""
    assert int(win.left_frame.grid_info()["column"]) == win.LEFT_COLUMN == 0
    assert int(win.log_main_frame.grid_info()["column"]) == win.LOG_COLUMN == 1
    # 两列都只占第 0 行（左侧区块在 left_frame 内部自上而下排，不再手写整窗 row）
    assert int(win.left_frame.grid_info()["row"]) == 0
    assert int(win.log_main_frame.grid_info()["row"]) == 0
    # 日志面板仍是 self.log_text + ttk.Scrollbar + self.time_label
    assert win.log_text.winfo_manager() == "grid"
    assert win.time_label.winfo_manager() == "grid"
    scrollbars = [c for frame in win.log_main_frame.winfo_children()
                  for c in frame.winfo_children() if isinstance(c, ttk.Scrollbar)]
    assert len(scrollbars) == 1, "日志面板应仍有一个滚动条"


def test_sections_group_buttons_by_purpose(win):
    """四个带标题的区块按语义分组，且按钮属性名与历史一致。"""
    assert _section_titles(win) == ["① 测试用例管理", "② 数据与通信工具",
                                    "③ 图像与视频", "④ 测试用例执行"]
    for attr in BUTTON_ATTRS:
        assert hasattr(win, attr), f"缺少按钮属性 {attr}（对外可见名不能改）"

    # 用例下拉框保留 FileUpdater 的绑定：self.file_menu / self.selected_file
    assert isinstance(win.file_menu, ttk.OptionMenu)
    assert win.selected_file.get(), "下拉框应已由 FileUpdater 初始化出「当前用例」"
    assert win.file_menu.winfo_manager() == "grid"


def test_button_colors_come_from_theme(win):
    """按钮配色走 Theme（用例管理=primary，数据通信=success，图像视频=danger）。"""
    from hudcore.ui import Theme

    assert str(win.upload_button["bg"]) == Theme.PRIMARY
    assert str(win.can_control_button["bg"]) == Theme.SUCCESS
    assert str(win.someip_button["bg"]) == Theme.SUCCESS
    assert str(win.image_button["bg"]) == Theme.DANGER
    assert str(win.di_case_button["bg"]) == Theme.SUCCESS


# ---------------------------------------------------------------- ② 单例
@pytest.mark.parametrize("kind,open_attr,close_attr,button_attr,window_attr,flag",
                         SINGLETONS, ids=[c[0] for c in SINGLETONS])
def test_singleton_open_twice_creates_one_window(win, monkeypatch, kind, open_attr,
                                                 close_attr, button_attr, window_attr, flag):
    """连点两次只建一个窗口；已打开期间按钮置灰；关闭后恢复 normal。"""
    created: list[tk.Toplevel] = []

    def fake_opener():
        top = tk.Toplevel(win.root)
        top.withdraw()
        created.append(top)
        return top

    spec = win._windows[kind]
    monkeypatch.setattr(win, "_windows",
                        {**win._windows, kind: replace(spec, opener=fake_opener)})
    button = getattr(win, button_attr)
    tops_before = len([c for c in win.root.winfo_children() if isinstance(c, tk.Toplevel)])

    first = getattr(win, open_attr)()
    second = getattr(win, open_attr)()
    assert first is second, "第二次点击必须聚焦已有窗口"
    assert len(created) == 1, "不得建出第二个窗口"
    tops_after = len([c for c in win.root.winfo_children() if isinstance(c, tk.Toplevel)])
    assert tops_after == tops_before + 1, "连点两次只应多出一个 Toplevel"
    assert _state_of(button) == "disabled", "窗口打开期间入口按钮应置灰"
    assert getattr(win, window_attr) is first
    assert win._ui_state.flag(flag) is True

    # 关闭（等价于 WM_DELETE_WINDOW）
    getattr(win, close_attr)()
    assert not first.winfo_exists()
    assert _state_of(button) == "normal", "关闭后按钮必须恢复"
    assert getattr(win, window_attr) is None
    assert win._ui_state.flag(flag) is False


@pytest.mark.parametrize("kind,open_attr,close_attr,button_attr,window_attr,flag",
                         SINGLETONS, ids=[c[0] for c in SINGLETONS])
def test_singleton_recovers_when_window_destroyed_directly(win, monkeypatch, kind, open_attr,
                                                           close_attr, button_attr,
                                                           window_attr, flag):
    """用户/子窗口直接 destroy()（不走 WM_DELETE_WINDOW）时按钮也要恢复。"""
    created: list[tk.Toplevel] = []

    def fake_opener():
        top = tk.Toplevel(win.root)
        top.withdraw()
        created.append(top)
        return top

    spec = win._windows[kind]
    monkeypatch.setattr(win, "_windows",
                        {**win._windows, kind: replace(spec, opener=fake_opener)})
    button = getattr(win, button_attr)

    first = getattr(win, open_attr)()
    assert _state_of(button) == "disabled"
    first.destroy()
    win.root.update()                     # 让 <Destroy> 事件派发到兜底回调
    assert _state_of(button) == "normal", "直接销毁后按钮仍是灰的（本次重构要修的问题）"
    assert getattr(win, window_attr) is None
    assert win._ui_state.flag(flag) is False

    # 关掉之后可以正常再开一个（不会被"孤儿窗口"卡住）
    second = getattr(win, open_attr)()
    assert second is not first
    assert len(created) == 2
    getattr(win, close_attr)()
    assert _state_of(button) == "normal"


def test_failed_open_keeps_button_clickable(win, monkeypatch):
    """开窗失败（依赖库缺失、opener 返回 None 等）不允许把按钮永久灰掉。"""
    def boom():
        raise RuntimeError("模拟依赖库缺失")

    def returns_none():
        return None

    spec = win._windows["can"]
    monkeypatch.setattr(win, "_windows",
                        {**win._windows, "can": replace(spec, opener=returns_none)})
    with pytest.raises(RuntimeError):
        win.open_can_gui()
    assert _state_of(win.can_control_button) == "normal", "opener 返回 None 时也应恢复按钮"
    assert win._can_window is None

    monkeypatch.setattr(win, "_windows",
                        {**win._windows, "can": replace(spec, opener=boom)})
    with pytest.raises(RuntimeError):
        win.open_can_gui()
    assert _state_of(win.can_control_button) == "normal"
    assert win._can_window is None


# ---------------------------------------------------------------- ③ 真实窗口
def test_real_someip_window_singleton(win):
    """SOME/IP 回放：真实窗口（无库时窗口照常打开、动作置灰）。"""
    first = win.open_someip_replay()
    assert win.open_someip_replay() is first
    assert _state_of(win.someip_button) == "disabled"
    win._on_someip_window_close()
    assert not first.winfo_exists()
    assert _state_of(win.someip_button) == "normal"


def test_real_di_window_singleton_calls_stop_before_destroy(win):
    """Di 窗口：关闭时必须先 `di_app.stop()` 再 destroy（顺序不能丢）。"""
    calls: list[str] = []
    first = win.open_di_cases()
    assert win.open_di_cases() is first
    assert _state_of(win.di_case_button) == "disabled"

    app = first.di_app
    real_stop = app.stop

    def spy_stop():
        calls.append("stop" if first.winfo_exists() else "stop-after-destroy")
        real_stop()

    app.stop = spy_stop
    win._on_di_window_close()
    assert calls == ["stop"], f"stop() 必须先于 destroy()：{calls}"
    assert not first.winfo_exists()
    assert _state_of(win.di_case_button) == "normal"


def test_real_can_window_singleton(win):
    """CAN 测试：真实窗口。can_gui 侧若暂时无法构建（其布局模块在并行重构中），
    这里跳过并给出原因 —— main.py 的单例/置灰逻辑已由上面的桩用例覆盖。"""
    try:
        first = win.open_can_gui()
    except Exception as exc:                          # noqa: BLE001
        assert _state_of(win.can_control_button) == "normal", "构建失败也必须恢复按钮"
        pytest.skip(f"CAN 界面当前无法在无头环境构建（can_gui 侧问题，非 main.py）：{exc!r}")

    assert win.open_can_gui() is first
    assert _state_of(win.can_control_button) == "disabled"
    first.destroy()                                   # 不触达 CANFDGUI.on_closing（那会弹窗）
    win.root.update()
    assert _state_of(win.can_control_button) == "normal"


# ---------------------------------------------------------------- 保留行为
def test_stdout_redirect_clock_and_closing_are_preserved():
    """TextRedirector / 时钟 / on_closing 行为保持不变。

    说明 1：pytest 的 fd 捕获会在"fixture 阶段"与"测试正文"之间把 `sys.stdout`
    重新装回自己的 `EncodedFile`（fixture 里建的窗口因此看不到自己刚设的重定向），
    所以这里在正文里显式再调一次 `_redirect_stdout()`（与 `__init__` 同一行代码）
    再断言，避免把 pytest 的捕获机制误判成 main.py 的问题。
    说明 2：本用例会**销毁根窗口**，故不共用模块级实例，自己建一个用完即关。
    """
    import time

    from hudcore.ui import TextRedirector

    original_stdout = sys.stdout
    win = main_module.MainWindow()
    win.root.withdraw()
    win.root.update_idletasks()
    try:
        _assert_redirect_clock_and_closing(win, TextRedirector, time)
    finally:
        try:
            win.on_closing()
        except tk.TclError:
            pass
        sys.stdout = original_stdout


def _assert_redirect_clock_and_closing(win, TextRedirector, time) -> None:
    assert isinstance(win._log_redirector, TextRedirector)
    assert win._log_redirector.widget is win.log_text

    win._redirect_stdout()
    assert sys.stdout is win._log_redirector, "__init__ 里应把 stdout 换成 TextRedirector"

    print("重定向自检")                                # 入队，由主线程轮询写入日志框
    deadline = time.time() + 3.0
    while time.time() < deadline and "重定向自检" not in win.log_text.get("1.0", "end"):
        win.root.update()
        time.sleep(0.05)
    assert "重定向自检" in win.log_text.get("1.0", "end"), "print 应出现在日志文本框里"

    assert win.time_label.cget("text").startswith("当前时间: ")
    assert win._time_after_id is not None

    win.on_closing()
    assert sys.stdout is not win._log_redirector, "on_closing 必须还原 sys.stdout"
    win.on_closing()                                  # 幂等：再关一次不应抛异常
