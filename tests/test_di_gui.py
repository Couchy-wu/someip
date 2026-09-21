# -*- coding: utf-8 -*-
"""tests/test_di_gui.py —— Di 用例窗口（gui_handlers.di_case_window）

覆盖：窗口与页签结构、扫描统计、报告预览填充、执行（体检模式）后报告落到预览页签、
导出写 .md + .json、清空。不需要 CAN 设备（无设备时自动退回体检模式）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")                     # 无显示环境（无 tkinter）时跳过

from gui_handlers import di_case_window as win_mod      # noqa: E402
from can_data_tools import case_format                  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = PROJECT_ROOT / "TestcaseCollection" / "Di_testcases"


@pytest.fixture()
def window(monkeypatch):
    """建窗口并把模态弹窗替换成记录器（无人值守）。"""
    if not CASE_DIR.is_dir():
        pytest.skip("未找到 Di 用例目录")
    calls: list[tuple] = []
    monkeypatch.setattr(win_mod.messagebox, "showinfo",
                        lambda *a, **k: calls.append(("info", a[:1])))
    monkeypatch.setattr(win_mod.messagebox, "showwarning",
                        lambda *a, **k: calls.append(("warn", a[:1])))
    monkeypatch.setattr(win_mod.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(win_mod.filedialog, "asksaveasfilename",
                        lambda *a, **k: str(PROJECT_ROOT / "logs" / "di_gui_report.md"))
    root = tk.Tk()
    root.withdraw()
    win = win_mod.open_di_case_window(root)
    win.update_idletasks()
    try:
        yield win, calls
    finally:
        # 先停轮询再销毁：否则窗口的 after 回调会打到已销毁控件（Wine 下更明显）
        try:
            win.di_app.stop()
            win.update()
        except tk.TclError:
            pass
        try:
            win.destroy()
        except tk.TclError:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass


def _pump(win, app, predicate, timeout_s: float = 90.0):
    """等后台线程 + 队列轮询把结果反映到界面。"""
    import time
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        win.update()
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_window_has_two_tabs_and_switch(window):
    """页签：执行日志 + 报告预览；格式开关默认跟随 case_format。"""
    win, _calls = window
    app = win.di_app
    tabs = [app.notebook.tab(i, "text") for i in range(app.notebook.index("end"))]
    assert tabs == ["执行日志", "报告预览（Markdown）"]
    assert app.var_format.get() == case_format.active_format()
    assert app.var_dir.get().endswith("Di_testcases")


def test_scan_puts_case_dir_in_log(window):
    """扫描后日志里能看到用例目录与统计（后台线程 + 队列回传）。"""
    win, _calls = window
    app = win.di_app
    app.scan()
    assert _pump(win, app, lambda: app.var_summary.get().startswith("用例")), \
        f"扫描未完成，汇总={app.var_summary.get()!r}"
    assert "用例" in app.var_summary.get()
    assert "Di_testcases" in app.text.get("1.0", "end-1c")


def test_execute_fills_report_preview(window, monkeypatch):
    """执行（无 CAN 设备 → 体检模式）后，预览页签应出现 Markdown 报告。"""
    win, _calls = window
    app = win.di_app
    # 只取少量用例，避免测试里跑全量（注意 load_cases 的第一个位置参数是用例目标）
    original = win_mod.parser.load_cases

    def _first(target, *a, **k):
        return original(target, *a, **k)[:8]

    monkeypatch.setattr(win_mod.parser, "load_cases", _first)
    # 关键：不要真去初始化 CAN 设备（容器/无卡环境下底层库可能让进程硬崩），
    # 本用例只验证"无设备 → 体检模式 → 报告进预览"这条界面链路
    monkeypatch.setattr(win_mod.DiCaseWindow, "_prepare_senders",
                        lambda self: (None, None, None, "[测试] 未接设备 → 体检模式"))
    app.scan()
    assert _pump(win, app, lambda: bool(app._cases)), "扫描未取到用例"
    _pump(win, app, lambda: app.var_summary.get().startswith("用例"))

    app.execute()                                   # askyesno 已替换为 True
    assert _pump(win, app, lambda: app.preview.get("1.0", "2.0").startswith("# Di 测试用例执行报告")), \
        f"报告预览未填充：{app.preview.get('1.0', '2.0')!r}"
    text = app.preview.get("1.0", "end-1c")
    for section in ("## 执行环境", "## 统计", "## 逐项结果"):
        assert section in text, f"报告缺少章节：{section}"
    assert app.notebook.index("current") == 1, "应自动切到报告预览页签"


def test_export_writes_markdown_and_json(window, tmp_path, monkeypatch):
    """导出按钮一次写出 Markdown + JSON（同名不同后缀）。"""
    win, _calls = window
    app = win.di_app
    app._report = win_mod.runner.DiCaseRunner(dry_run=True).run_cases(
        win_mod.parser.load_cases(CASE_DIR)[:3])
    monkeypatch.setattr(win_mod.filedialog, "asksaveasfilename",
                        lambda *a, **k: str(tmp_path / "out.md"))
    app.export_report()
    win.update()
    assert (tmp_path / "out.md").is_file()
    assert (tmp_path / "out.json").is_file()


def test_export_without_run_shows_hint(window):
    """没有执行结果时点导出 → 只提示，不写文件、不崩。"""
    win, calls = window
    app = win.di_app
    assert app._report is None
    app.export_report()
    assert any(kind == "info" for kind, _ in calls)


def test_clear_output_resets_log_and_preview(window):
    win, _calls = window
    app = win.di_app
    app._append("一些日志")
    app._show_preview("# 报告")
    app._clear_output()
    win.update()
    assert app.text.get("1.0", "end-1c") == ""
    assert app.preview.get("1.0", "end-1c") == ""
