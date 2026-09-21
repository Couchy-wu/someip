# -*- coding: utf-8 -*-
"""tests/test_can_gui_layout.py —— CAN 界面布局与按钮状态（can_gui/gui_layout.py）

只建界面、不起相机/校验线程、不碰 CAN 设备（`CANFDGUI._build_layout_only`），
因此可以在容器/CI 里稳定跑。覆盖：

  · **零格子冲突**：原实现里「平台」标签与「检测设备」按钮、「曝光值」与摄像头画面
    各占同一格（互相盖住），现在由 SectionStack/ActionBar 自动排布；
  · 初始按钮状态：未初始化时「关闭设备/ON/OFF 档电/开始测试/暂停/终止」都不可点；
  · 状态流转：初始化成功 → 可发送/可测试；测试中 → 暂停/终止可用、输入框与选项锁定；
    关闭设备后即使测试结束也不会把「开始测试」错误点亮（原实现的 bug）；
  · 暂停按钮文案随状态切换（暂停/继续）。

需要显示器（Xvfb）；无 DISPLAY 时跳过。
"""
from __future__ import annotations


import pytest

tk = pytest.importorskip("tkinter")

from tests import gui_support                     # noqa: E402

gui_support.require_display()                     # 无图形环境整模块跳过（Windows 本机不跳）

from hudcore.ui import BUSY_INIT, BUSY_NONE, audit_widget_tree, describe_collisions  # noqa: E402


@pytest.fixture()
def gui():
    """只建界面的 CAN GUI（不起线程、不碰设备）。"""
    from can_gui.can_send_receive_gui import CANFDGUI

    root = tk.Tk()
    root.withdraw()
    obj = CANFDGUI._build_layout_only(root)
    root.update_idletasks()
    try:
        yield obj
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def _state_of(widget) -> str:
    return str(widget.cget("state"))


# ---------------------------------------------------------------- 布局
def test_no_grid_collisions(gui):
    collisions = audit_widget_tree(gui.root)
    assert collisions == [], describe_collisions(collisions)


def test_all_expected_widgets_exist(gui):
    for name in ("probe_btn", "init_btn", "close_btn", "sub_btn", "send_btn", "off_btn",
                 "test_btn", "toggle_pause_resume_btn", "stop_btn", "rotate_btn",
                 "perspective_btn", "video_label", "video_label2", "state_label",
                 "repeat_entry", "rounds_entry", "platform_cb", "exposure_cb",
                 "device_hint", "buttons"):
        assert hasattr(gui, name), f"缺少控件/属性：{name}"
    assert gui.video_label.image is not None, "画面占位图不能被 GC 掉"


def test_sections_are_grouped(gui):
    """控制区应当分成 5 个带标题的区块（原来是一堆按钮平铺在主窗口上）。"""
    from tkinter import ttk

    section_titles = []

    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.LabelFrame):
                section_titles.append(str(child.cget("text")))
            walk(child)

    walk(gui.root)
    assert len(section_titles) >= 5, f"区块太少：{section_titles}"
    for expected in ("设备连接", "供电控制", "自动化测试", "平台与图像选项", "图像变换"):
        assert any(expected in t for t in section_titles), f"缺少区块：{expected}"


# ---------------------------------------------------------------- 按钮状态
def test_initial_button_states(gui):
    assert _state_of(gui.probe_btn) == "normal"
    assert _state_of(gui.init_btn) == "normal"
    assert _state_of(gui.sub_btn) == "normal"
    for name in ("close_btn", "send_btn", "off_btn", "test_btn",
                 "toggle_pause_resume_btn", "stop_btn"):
        btn = getattr(gui, name)
        assert _state_of(btn) == "disabled", f"未初始化设备时 {name} 不该可点"
    assert _state_of(gui.repeat_entry) == "disabled"
    assert "未初始化" in str(gui.device_hint.cget("text"))


def test_device_open_enables_actions(gui):
    gui.device_handle = 12345                 # 模拟初始化成功
    gui._apply_ui_state()

    assert _state_of(gui.close_btn) == "normal"
    for name in ("send_btn", "off_btn", "test_btn"):
        assert _state_of(getattr(gui, name)) == "normal"
    assert _state_of(gui.probe_btn) == "disabled", "设备已打开时不该再初始化"
    assert _state_of(gui.repeat_entry) == "normal"
    assert "已初始化" in str(gui.device_hint.cget("text"))


def test_testing_locks_options_and_enables_pause_stop(gui):
    gui.device_handle = 12345
    gui._apply_ui_state()
    gui._set_testing(True)

    assert _state_of(gui.test_btn) == "disabled"
    assert _state_of(gui.toggle_pause_resume_btn) == "normal"
    assert _state_of(gui.stop_btn) == "normal"
    for name in ("send_btn", "off_btn", "repeat_entry", "rounds_entry",
                 "platform_cb", "exposure_cb", "image_test_cb", "transform_cb_box"):
        assert _state_of(getattr(gui, name)) == "disabled", f"测试中 {name} 应被锁住"

    gui._set_testing(False)
    assert _state_of(gui.test_btn) == "normal"
    assert _state_of(gui.stop_btn) == "disabled"
    assert _state_of(gui.repeat_entry) == "normal"


def test_pause_button_text_follows_state(gui):
    gui.device_handle = 12345
    gui._set_testing(True)
    assert str(gui.toggle_pause_resume_btn.cget("text")) == "暂停测试"
    gui.set_paused(True)
    assert str(gui.toggle_pause_resume_btn.cget("text")) == "继续测试"
    gui.set_paused(False)
    assert str(gui.toggle_pause_resume_btn.cget("text")) == "暂停测试"


def test_busy_state_blocks_everything(gui):
    gui._set_busy(BUSY_INIT)
    assert gui._ui_state().busy == BUSY_INIT
    for name in ("probe_btn", "init_btn", "close_btn", "sub_btn", "test_btn"):
        assert _state_of(getattr(gui, name)) == "disabled", f"{name} 忙碌时应置灰"
    assert "正在初始化" in str(gui.device_hint.cget("text"))

    gui._clear_busy()
    assert gui._ui_state().busy == BUSY_NONE
    assert _state_of(gui.probe_btn) == "normal" and _state_of(gui.init_btn) == "normal"


def test_subwindow_button_follows_state_machine(gui):
    """点「设备管理」→ 子窗口打开且按钮置灰；关闭后按钮恢复（不靠手写 config）。"""
    assert _state_of(gui.sub_btn) == "normal"
    gui.sub_btn.invoke()                        # 真点按钮
    assert gui.sub_window is not None and gui.sub_window.winfo_exists()
    assert _state_of(gui.sub_btn) == "disabled"

    gui._on_subwindow_close()
    assert gui.sub_window is None
    assert _state_of(gui.sub_btn) == "normal"


def test_test_finish_does_not_revive_start_button_without_device(gui):
    """原实现 bug：测试结束会把「开始测试」点亮，即使设备已经关掉。"""
    gui.device_handle = 12345
    gui._set_testing(True)
    gui.device_handle = None                  # 测试期间用户关闭了设备
    gui._post_test_finish(success=False)

    assert _state_of(gui.test_btn) == "disabled"
    assert _state_of(gui.send_btn) == "disabled"
    assert _state_of(gui.init_btn) == "normal"
