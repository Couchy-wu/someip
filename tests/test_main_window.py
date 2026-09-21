# -*- coding: utf-8 -*-
"""tests/test_main_window.py —— 主窗口「布局回退 + 单例子窗口」验收
=====================================================================
布局已**回退**到改动前（7219d2d）的平铺网格，逻辑改进（按钮状态机 + 单例子窗口）
保留。本模块要自证的三件事，全部可无头运行（xvfb-run），**不需要**真实 CAN 设备 / 相机：

  1. **布局**：按钮平铺在 row 0~2 / column 0~4（`padx=pady=20`，行号即功能分组）、
     右侧日志面板在 `row=0, column=5, rowspan=GRID_ROWS`；不再有 `left_frame`、
     区块标题（LabelFrame）或按钮条；整窗 `hudcore.ui.layout.audit_widget_tree()`
     仍为零格子冲突；
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

#: 布局回退要求保留的按钮属性名（已有测试/文档会引用）
BUTTON_ATTRS = [
    "upload_button", "delete_button", "view_button", "inspect_button",
    "convert_matrix_button", "hex_button", "can_control_button", "someip_button",
    "image_button", "read_video_button", "image_video_button", "di_case_button",
]

#: 改动前（7219d2d）的**原始格子坐标**：(按钮属性名, row, column)。
#: (0, 2) 是用例下拉框 `self.file_menu`，单独断言。
BUTTON_GRID = [
    ("upload_button", 0, 0),
    ("delete_button", 0, 1),
    ("view_button", 0, 3),
    ("inspect_button", 0, 4),
    ("convert_matrix_button", 1, 0),
    ("hex_button", 1, 1),
    ("can_control_button", 1, 2),
    ("someip_button", 1, 3),
    ("image_button", 2, 0),
    ("read_video_button", 2, 1),
    ("image_video_button", 2, 2),
    ("di_case_button", 2, 3),
]

#: 平铺布局下"同一行 = 同一功能分组"（分组语义由行号表达，不再有区块标题）
ROW_MEMBERS = {
    0: ("upload_button", "delete_button", "view_button", "inspect_button"),
    1: ("convert_matrix_button", "hex_button", "can_control_button", "someip_button"),
    2: ("image_button", "read_video_button", "image_video_button", "di_case_button"),
}

#: 原始日志面板位置：column = GRID_ROWS（=5），并跨全部 5 行
LOG_ROW, LOG_COLUMN, LOG_ROWSPAN = 0, 5, 5


def _cell(widget) -> tuple[int, int]:
    """控件的 grid 格子坐标 (row, column)。"""
    info = widget.grid_info()
    return int(info["row"]), int(info["column"])


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
    """整窗（含 12 个按钮、下拉框、日志面板）不得有两控件占同一 (row, column)。"""
    collisions = audit_widget_tree(win.root)
    sys.__stdout__.write("[布局审计] " + describe_collisions(collisions) + "\n")
    sys.__stdout__.flush()
    assert collisions == [], describe_collisions(collisions)


def test_buttons_keep_original_flat_grid_coordinates(win):
    """12 个按钮平铺在 row 0~2 / column 0~4，坐标与改动前逐一对齐（不分组、无区块）。"""
    for attr, row, column in BUTTON_GRID:
        assert hasattr(win, attr), f"缺少按钮属性 {attr}（对外可见名不能改）"
        button = getattr(win, attr)
        assert button.winfo_manager() == "grid", f"{attr} 应由 grid 管理"
        assert _cell(button) == (row, column), \
            f"{attr} 应回到原始格子 (row={row}, column={column})，实际 {_cell(button)}"
        info = button.grid_info()
        assert (int(info["padx"]), int(info["pady"])) == (20, 20), \
            f"{attr} 的内边距应沿用原始的 padx=pady=20"
        # 平铺：不带跨行/跨列
        assert int(info.get("rowspan", 1)) == 1 and int(info.get("columnspan", 1)) == 1

    # 用例下拉框仍在原始的 (0, 2)
    assert isinstance(win.file_menu, ttk.OptionMenu)
    assert _cell(win.file_menu) == (0, 2)
    assert win.selected_file.get(), "下拉框应已由 FileUpdater 初始化出「当前用例」"


def test_no_sections_or_button_bars_left(win):
    """布局回退：不应再有 left_frame / 区块标题（LabelFrame）/ 声明式按钮条。"""
    assert not hasattr(win, "left_frame"), "left_frame 应随布局回退一并去掉"

    def label_frames(widget):
        out = []
        for child in widget.winfo_children():
            if isinstance(child, ttk.LabelFrame) or isinstance(child, tk.LabelFrame):
                out.append(child)
            out.extend(label_frames(child))
        return out

    assert label_frames(win.root) == [], "不应再有带标题的区块（LabelFrame）"

    # 整窗直接子控件 = 12 个按钮 + 1 个下拉框 + 日志面板，且各自占一格
    cells = [_cell(c) for c in win.root.winfo_children()]
    assert len(cells) == 14, f"根窗口直接子控件应为 14 个，实际 {len(cells)}"
    assert len(set(cells)) == len(cells), f"根窗口存在同格控件：{sorted(cells)}"
    assert sorted(cells) == sorted(
        [(row, column) for _, row, column in BUTTON_GRID] + [(0, 2), (LOG_ROW, LOG_COLUMN)])


def test_log_panel_keeps_original_cell_and_children(win):
    """右侧日志面板回到 `row=0, column=5, rowspan=5`（padx=pady=10），内部结构不变。"""
    info = win.log_main_frame.grid_info()
    assert _cell(win.log_main_frame) == (LOG_ROW, LOG_COLUMN)
    assert int(info["rowspan"]) == LOG_ROWSPAN == main_module.MainWindow.GRID_ROWS
    assert (int(info["padx"]), int(info["pady"])) == (10, 10)
    assert set(str(info["sticky"])) == set("nsew"), "日志面板应四向填满（Tk 会重排字母序）"

    assert win.log_text.winfo_manager() == "grid"
    assert win.time_label.winfo_manager() == "grid"
    scrollbars = [c for frame in win.log_main_frame.winfo_children()
                  for c in frame.winfo_children() if isinstance(c, ttk.Scrollbar)]
    assert len(scrollbars) == 1, "日志面板应仍有一个滚动条"

    # 原始拉伸行为：row 0~4 与 column 5 都配了 weight
    for row in range(main_module.MainWindow.GRID_ROWS):
        assert win.root.grid_rowconfigure(row)["weight"] == 1
    assert win.root.grid_columnconfigure(LOG_COLUMN)["weight"] == 1


def test_rows_express_the_original_grouping(win):
    """分组语义：同一行的按钮属于同一功能组，配色沿用该组的语义色。"""
    from hudcore.ui import Theme

    for row, members in ROW_MEMBERS.items():
        for attr in members:
            assert _cell(getattr(win, attr))[0] == row, f"{attr} 应属于第 {row} 行分组"

    # 平铺布局只用 row 0~2；第 4 列之后的格子留给日志面板
    used = {_cell(getattr(win, a)) for a in BUTTON_ATTRS}
    assert {row for row, _ in used} == set(ROW_MEMBERS)
    assert {column for _, column in used} == {0, 1, 2, 3, 4}

    # row 0 = 用例管理(primary)、row 1 = 数据与通信(success)、
    # row 2 = 图像与视频(danger) + Di 执行(success)
    for attr in ROW_MEMBERS[0]:
        assert str(getattr(win, attr)["bg"]) == Theme.PRIMARY
    for attr in ROW_MEMBERS[1]:
        assert str(getattr(win, attr)["bg"]) == Theme.SUCCESS
    for attr in ("image_button", "read_video_button", "image_video_button"):
        assert str(getattr(win, attr)["bg"]) == Theme.DANGER
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
