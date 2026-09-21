# -*- coding: utf-8 -*-
"""tests/test_ui_layout.py —— 布局工具与"格子冲突"自检（hudcore.ui.layout / action_bar）

价值：Tk 允许把多个控件 `grid` 到同一 `(row, column)`，不报错、只是互相盖住 ——
本次界面优化的起因之一就是 CAN 界面里「平台」标签与「检测设备」按钮、曝光下拉框与
摄像头画面各占了同一格。这里把"无格子冲突"变成**可断言**的测试。

覆盖：
  · ActionBar 自动排布（超过 columns 自动换行、不撞格）与状态登记；
  · SectionStack 顺序分配行号（区块/按钮条/表单行/说明行）；
  · 审计工具能**抓到**人造冲突，也能对正常窗口判定为"零冲突"；
  · 界面源码不再硬编码字体名（跨平台要求）。

需要显示器（容器里由 Xvfb 提供）；无 DISPLAY 时整模块跳过。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")

from tests import gui_support                     # noqa: E402

gui_support.require_display()                     # 无图形环境整模块跳过（Windows 本机不跳）

from hudcore.ui import (                                   # noqa: E402
    ActionBar, BUSY_INIT, SectionStack, Theme, UiState, audit_widget_tree,
    describe_collisions, grid_collisions,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def root():
    r = tk.Tk()
    r.withdraw()
    try:
        yield r
    finally:
        try:
            r.destroy()
        except tk.TclError:
            pass


def _cells(widgets) -> list[tuple[int, int]]:
    return [(int(w.grid_info()["row"]), int(w.grid_info()["column"])) for w in widgets]


# ---------------------------------------------------------------- ActionBar
def test_action_bar_wraps_and_never_collides(root):
    frame = tk.Frame(root)
    frame.pack()
    bar = ActionBar(frame, columns=3, use_ttk=False)
    for i in range(5):
        bar.add(f"b{i}", f"按钮{i}", lambda: None, kind="primary")
    bar.add_widget("entry", tk.Entry(frame), place=True)

    widgets = bar.widgets()
    assert len(widgets) == 6 and bar.rows_used() == 2
    assert _cells(widgets) == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
    assert len(set(_cells(widgets))) == 6, "每个控件必须独占一个格子"
    root.update_idletasks()
    assert audit_widget_tree(root) == [], describe_collisions(audit_widget_tree(root))


def test_action_bar_registers_rules_and_rejects_bad_kind(root):
    frame = tk.Frame(root)
    frame.pack()
    bar = ActionBar(frame, columns=2)
    bar.add("init", "初始化", lambda: None, kind="info",
            enabled_when=lambda s: s.idle and not s.flag("device_open"))
    bar.add("close", "关闭", lambda: None, kind="danger",
            enabled_when=lambda s: s.flag("device_open"))

    assert bar.apply(UiState()) == {"init": "normal", "close": "disabled"}
    changes = bar.apply(UiState(busy=BUSY_INIT, flags={"device_open": True}))
    assert changes == {"init": "disabled", "close": "normal"}, \
        "设备已打开 → 初始化置灰、关闭转为可用"
    assert bar.widget("init").cget("text") == "初始化"
    assert bar.group.name.startswith("bar@")

    with pytest.raises(ValueError):
        bar.add("bad", "x", lambda: None, kind="不存在的种类")


def test_action_bar_buttons_use_theme_styles(root):
    """配色/字体来自 Theme —— 不再硬编码字体名，Ubuntu 上也能正常显示。"""
    frame = tk.Frame(root)
    frame.pack()
    bar = ActionBar(frame, columns=1)
    btn = bar.add("probe", "检测设备", lambda: None, kind="info")
    assert str(btn.cget("background")).upper() == Theme.INFO.upper()
    assert str(btn.cget("activebackground")).upper() == Theme.INFO_HOVER.upper()
    assert Theme.font_name() in str(btn.cget("font")), "字体必须来自跨平台回退链"


# ---------------------------------------------------------------- SectionStack
def test_section_stack_assigns_sequential_rows(root):
    frame = tk.Frame(root)
    frame.pack()
    stack = SectionStack(frame, use_ttk=False)

    sec = stack.section("① 区块")
    bar = stack.action_bar(columns=2)
    bar.add("a", "按钮A", lambda: None)
    bar.add("b", "按钮B", lambda: None)
    stack.note("说明")
    stack.form_row(("字段", tk.Entry(frame)))

    rows = [int(w.grid_info()["row"]) for w in frame.winfo_children()]
    assert rows == [0, 1, 1, 2, 3, 3], "区块/按钮条/说明/表单行必须依次占不同行"
    assert stack.next_row == 4 and sec.winfo_manager() == "grid"
    root.update_idletasks()
    assert audit_widget_tree(root) == []


def test_form_row_places_label_and_widget_side_by_side(root):
    frame = tk.Frame(root)
    frame.pack()
    stack = SectionStack(frame, use_ttk=False)
    entry_a, entry_b = tk.Entry(frame), tk.Entry(frame)
    stack.form_row(("平台", entry_a), ("曝光值", entry_b))

    assert _cells([entry_a, entry_b]) == [(0, 1), (0, 3)]
    labels = [w for w in frame.winfo_children() if isinstance(w, tk.Label)]
    assert _cells(labels) == [(0, 0), (0, 2)]


# ---------------------------------------------------------------- 审计工具
def test_audit_detects_artificial_collision(root):
    frame = tk.Frame(root)
    frame.pack()
    tk.Label(frame, text="平台:").grid(row=0, column=3)
    tk.Button(frame, text="检测设备").grid(row=0, column=3)      # 故意撞格

    collisions = grid_collisions(frame)
    assert len(collisions) == 1
    assert collisions[0].cell.row == 0 and collisions[0].cell.column == 3
    assert len(collisions[0].occupants) == 2
    text = describe_collisions(collisions)
    assert "row=0" in text and "检测设备" in text and "平台" in text

    # 挪开后不再冲突
    frame.winfo_children()[1].grid(row=0, column=4)
    assert grid_collisions(frame) == []
    assert describe_collisions([]) == "未发现 grid 格子冲突"


def test_audit_reports_rowspan_collision(root):
    frame = tk.Frame(root)
    frame.pack()
    tk.Label(frame, text="画面").grid(row=0, column=0, rowspan=3)
    tk.Entry(frame).grid(row=2, column=0)                       # 落在 rowspan 覆盖范围内
    collisions = grid_collisions(frame)
    assert len(collisions) == 1 and collisions[0].cell.row == 2


# ---------------------------------------------------------------- 源码约定
def test_window_sources_do_not_hardcode_font_family():
    """界面的字体必须走 Theme（Windows 微软雅黑 / Ubuntu Noto Sans CJK 回退链）。"""
    targets = ["main.py", "gui_handlers/di_case_window.py"]
    for sub in ("can_gui", "someip_gui"):
        targets += [str(p.relative_to(PROJECT_ROOT)) for p in (PROJECT_ROOT / sub).glob("*.py")]
    pattern = re.compile(r"font\s*=\s*\(\s*[\"']")
    offenders = []
    for rel in targets:
        path = PROJECT_ROOT / rel
        if not path.is_file():
            continue
        for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if pattern.search(code):
                offenders.append(f"{rel}:{num}: {line.strip()}")
    assert not offenders, "硬编码字体名（应改用 Theme.font_tuple）：\n" + "\n".join(offenders)
