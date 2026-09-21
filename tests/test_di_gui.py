# -*- coding: utf-8 -*-
"""tests/test_di_gui.py —— Di 用例窗口（gui_handlers.di_case_window）

覆盖：窗口与页签结构、扫描统计、报告预览填充、执行（体检模式）后报告落到预览页签、
导出写 .md + .json、清空；以及本次重构新增的
**按钮状态机**（规则表纯函数 + 状态→控件可用性 + 扫描/执行期间的真实置灰）
与**中止链路**（停止事件 → `should_stop` → 报告 `aborted`；legacy 格式禁用执行）。
不需要 CAN 设备（无设备时自动退回体检模式）。

布局约定（本次"布局回退"后固化，见 `test_layout_*` 系列）：
界面是**改动前的那套 pack 摆放** —— 格式开关 LabelFrame + 目录行 + 动作行 +
汇总行 + 输出区，没有 SectionStack/ActionBar、也没有带标题的区块；
全部控件走 `pack`（**没有 grid**），因此整窗 `audit_widget_tree` 必须为空。
「停止执行」是动作行里「执行」之后的新增按钮（状态机的逻辑保留）。
"""
from __future__ import annotations

import gc
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")                     # 无显示环境（无 tkinter）时跳过
from tkinter import ttk                                 # noqa: E402

from gui_handlers import di_case_window as win_mod      # noqa: E402

from tests import gui_support                     # noqa: E402

gui_support.require_display()                     # 无图形环境整模块跳过（Windows 本机不跳）
from can_data_tools import case_format                  # noqa: E402
from hudcore.ui.layout import audit_widget_tree, describe_collisions  # noqa: E402
from hudcore.ui.state import BUSY_EXECUTE, BUSY_NONE, BUSY_SCAN  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = PROJECT_ROOT / "TestcaseCollection" / "Di_testcases"


def _state_of(widget) -> str:
    """控件当前的 state（tk / ttk 都是 'normal' / 'disabled'）。"""
    return str(widget.cget("state"))


@pytest.fixture()
def window(monkeypatch):
    """建窗口并把模态弹窗替换成记录器（无人值守）。

    格式开关按本窗口的用途固定成 Di：legacy 下「执行」按设计是禁用的（见
    `test_legacy_format_disables_execute_with_explanation`），
    其余用例关心的是执行链路本身。`_active` 由 monkeypatch 自动还原。
    """
    if not CASE_DIR.is_dir():
        pytest.skip("未找到 Di 用例目录")
    monkeypatch.setattr(case_format, "_active", case_format.DI)
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
        # 窗口里的 Tk 变量（StringVar/BooleanVar…）若在解释器销毁后才被 GC，
        # 其 __del__ 会抛 "main thread is not in main loop"（pytest 报 unraisable 警告）。
        # 因此在 root 还活着时主动释放引用并回收，保持闸门输出干净。
        app = getattr(win, "di_app", None)
        if app is not None:
            del app
        del win
        gc.collect()
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


def _packed(parent, kinds=(tk.Button, tk.Checkbutton)):
    """按 **实际 pack 顺序**取容器里的按钮类控件（`pack_slaves` 顺序即摆放顺序）。"""
    return [w for w in parent.pack_slaves() if isinstance(w, kinds)]


def _texts(parent, kinds=(tk.Button, tk.Checkbutton)) -> list[str]:
    return [str(w.cget("text")) for w in _packed(parent, kinds)]


# ---------------------------------------------------------------- 布局（pack 回退后）
def test_layout_has_no_grid_collisions(window):
    """回退后的布局一律 pack：整窗不存在 grid 格子，审计必然为空。"""
    win, _calls = window
    win.update_idletasks()

    collisions = audit_widget_tree(win)
    assert collisions == [], describe_collisions(collisions)

    # 真·零 grid：任何一层控件都不该由 grid 管理（有 grid 才谈得上"格子冲突"）
    grid_managed = []

    def walk(widget):
        for child in widget.winfo_children():
            if child.winfo_manager() == "grid":
                grid_managed.append(type(child).__name__)
            walk(child)

    walk(win)
    assert grid_managed == [], f"这些控件仍在用 grid：{grid_managed}"


def test_layout_format_switch_labelframe(window):
    """格式开关仍是带标题的 LabelFrame，Radiobutton 逐项 pack 并登记进状态机。"""
    win, _calls = window
    app = win.di_app
    win.update_idletasks()

    box = app.frame_format
    assert isinstance(box, tk.LabelFrame), "格式开关必须是 LabelFrame（改动前的容器）"
    assert box.master is win
    assert str(box.cget("text")) == "用例格式开关（旧链路保持不变，仅切换解析入口）"
    assert box.pack_info()["fill"] == "x", "格式开关应横向填满"

    radios = [w for w in box.pack_slaves() if isinstance(w, tk.Radiobutton)]
    assert len(radios) == len(case_format.available_formats())
    for radio in radios:
        assert radio.pack_info()["anchor"] == "w", "Radiobutton 逐项靠左 pack"
    # 环境变量说明行也在 LabelFrame 内
    notes = [w for w in box.pack_slaves() if isinstance(w, tk.Label)]
    assert notes and str(notes[0].cget("textvariable")) == str(app.var_format_note)


def test_layout_dir_row(window):
    """目录行：标签 + 宽度 58 的输入框 + 「浏览…」，全部 pack(side=LEFT)。"""
    win, _calls = window
    app = win.di_app
    win.update_idletasks()

    row = app.frame_dir
    assert row.pack_info()["fill"] == "x"

    labels = [w for w in row.pack_slaves() if isinstance(w, tk.Label)]
    assert [str(w.cget("text")) for w in labels] == ["用例目录:"]

    widgets = row.pack_slaves()
    assert widgets[1] is app.entry_dir and str(app.entry_dir.cget("width")) == "58"
    assert widgets[2] is app.btn_browse and str(app.btn_browse.cget("text")) == "浏览…"
    for widget in widgets:
        assert widget.pack_info()["side"] == "left", "目录行所有控件都靠左 pack"


def test_layout_action_row_order_and_texts(window):
    """动作行顺序与文案（「停止执行」紧跟「执行」之后），全部一行内靠左 pack。"""
    win, _calls = window
    app = win.di_app
    win.update_idletasks()

    row = app.frame_actions
    assert _texts(row) == ["扫描统计", "执行（需 CAN 设备）", "停止执行",
                           "只跑可全自动用例", "导出报告（Markdown + JSON）", "清空"]
    for widget in _packed(row):
        assert widget.pack_info()["side"] == "left"

    # 控件对象与状态机登记的一致（按钮不是"另建了一套"）
    assert _packed(row) == [app.btn_scan, app.btn_execute, app.btn_stop,
                            app.chk_only_auto, app.btn_export, app.btn_clear]
    texts = _texts(row)
    assert texts.index("停止执行") == texts.index("执行（需 CAN 设备）") + 1, \
        "「停止执行」必须紧跟「执行」之后"
    assert sorted(app.buttons.keys()) == sorted(
        ["format:legacy", "format:di", "format:auto", "dir", "browse", "scan",
         "execute", "stop", "only_auto", "export", "clear"]), \
        f"状态机登记的控件集合变了：{sorted(app.buttons.keys())}"


def test_layout_action_row_is_one_line_with_hint_below(window):
    """动作行的 6 个按钮在同一行，状态说明行在它们下面。

    **只断言结构（pack 语义），不断言像素**：`side="left"` 的控件在同一个 Frame 里
    永远不会换行，`side="bottom"` 的说明行必定占在它们下方 —— 这正是设计意图。
    早先这里用 `winfo_y()`/`winfo_height()` 断言"同一行"，在 Wine（Windows 字体
    度量不同）下会误报失败，属字体/DPI 相关的脆弱断言，已去掉。
    """
    win, _calls = window
    app = win.di_app

    row = app.frame_actions
    names = [str(w) for w in row.pack_slaves()]
    buttons = [w for w in row.pack_slaves() if isinstance(w, tk.Button)]
    hints = [w for w in row.pack_slaves() if isinstance(w, tk.Label) and
             str(w.cget("textvariable")) == str(app.var_execute_hint)]
    assert len(hints) == 1, "说明行必须存在（状态机要能说明为什么可点/不可点）"
    hint = hints[0]

    texts = [str(b.cget("text")) for b in buttons]
    assert "停止执行" in texts and texts.index("停止执行") == texts.index("执行（需 CAN 设备）") + 1, \
        f"「停止执行」应紧跟「执行（需 CAN 设备）」：{texts}"
    assert all(str(b.pack_info()["side"]) == "left" for b in buttons), \
        "动作行里的按钮都必须 side=left，否则会换行"
    assert str(hint.pack_info()["side"]) == "bottom", \
        "说明行按 BOTTOM 占位（先占位再放按钮，按钮才留在同一行）"
    assert names.index(str(hint)) < names.index(str(buttons[0])), \
        "说明行应比按钮先 pack（否则会把按钮挤到下一行）"
def test_layout_summary_and_output_area(window):
    """汇总行直接挂根窗口并横向填满；输出区是 expand 的 Notebook（两个页签）。"""
    win, _calls = window
    app = win.di_app
    win.update_idletasks()

    summary = [w for w in win.pack_slaves() if isinstance(w, tk.Label) and
               str(w.cget("textvariable")) == str(app.var_summary)]
    assert len(summary) == 1, "汇总行应直接挂在根窗口上（改动前的摆放）"
    assert summary[0].pack_info()["fill"] == "x"

    notebook = app.notebook
    assert isinstance(notebook, ttk.Notebook)
    assert notebook.pack_info()["fill"] == "both" and str(notebook.pack_info()["expand"]) == "1"
    assert notebook.master is app.frame_output

    tabs = [notebook.tab(i, "text") for i in range(notebook.index("end"))]
    assert tabs == ["执行日志", "报告预览（Markdown）"]

    # 日志/预览各带一个右侧滚动条，且预览有初始文案
    for tab in notebook.winfo_children():
        kinds = [type(w).__name__ for w in tab.pack_slaves()]
        assert kinds == ["Scrollbar", "Text"], f"页签内应是 滚动条 + 文本：{kinds}"
    assert app.preview.get("1.0", "end-1c").startswith("（执行后这里显示 Markdown 报告")


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
    """没有执行结果时「导出报告」是禁用的（程序调用也只提示，不写文件、不崩）。"""
    win, calls = window
    app = win.di_app
    assert app._report is None
    assert _state_of(app.btn_export) == "disabled", "空闲且无报告 → 导出应禁用"
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


# ---------------------------------------------------------------- 按钮状态机
def test_button_rules_are_pure_functions():
    """规则表是 `state -> bool` 的纯函数：不建窗口就能断言"哪个状态点亮哪个按钮"。"""
    from hudcore.ui.state import UiState

    rules = win_mod.BUTTON_RULES
    idle = UiState()
    with_report = idle.with_flags(has_report=True)
    legacy = idle.with_flags(legacy_format=True)

    assert rules["scan"](idle) and rules["execute"](idle) and rules["clear"](idle)
    assert not rules["export"](idle), "空闲且无报告 → 导出禁用"
    assert rules["export"](with_report)
    assert not rules["stop"](idle), "没在执行 → 停止禁用"

    # 扫描/执行中：扫描/执行/导出/清空/目录/勾选/格式 一律禁用
    for busy in (BUSY_SCAN, BUSY_EXECUTE):
        state = with_report.with_busy(busy)
        for key in ("scan", "execute", "export", "clear", "dir", "browse",
                    "only_auto", "format"):
            assert not rules[key](state), f"{busy} 中「{key}」应禁用"

    running = idle.with_busy(BUSY_EXECUTE)
    assert rules["stop"](running), "执行中 → 停止可用"
    assert not rules["stop"](running.with_flags(stopping=True)), "已请求停止 → 停止置灰"

    assert not rules["execute"](legacy), "legacy 格式 → 执行禁用"
    assert rules["scan"](legacy), "legacy 格式 → 扫描保留（只用来看分布）"

    assert "legacy" in win_mod.execute_hint(legacy)
    assert "正在停止" in win_mod.execute_hint(running.with_flags(stopping=True))
    assert "尚未扫描" in win_mod.execute_hint(idle)


def test_button_states_follow_the_state_machine(window):
    """状态 → 控件可用性：由 ButtonGroup.apply(state) 统一刷新（含停止按钮的置灰）。"""
    win, _calls = window
    app = win.di_app
    win.update_idletasks()

    # 空闲 + 无报告（格式为 di）：能扫能执行，导出与停止灰着
    assert _state_of(app.btn_scan) == "normal"
    assert _state_of(app.btn_execute) == "normal"
    assert _state_of(app.btn_export) == "disabled"
    assert _state_of(app.btn_stop) == "disabled"

    # 扫描中：除了停止（本来也不可用）其余动作全部禁用
    app._set_state(busy=BUSY_SCAN)
    for widget in (app.btn_scan, app.btn_execute, app.btn_export, app.btn_clear,
                   app.btn_browse, app.entry_dir, app.chk_only_auto,
                   app.buttons.widget("format:di")):
        assert _state_of(widget) == "disabled", f"{widget} 在扫描中应禁用"
    assert _state_of(app.btn_stop) == "disabled"

    # 执行中 + 已有报告：停止可用，扫描/执行/导出仍禁用
    app._set_state(busy=BUSY_EXECUTE, has_report=True)
    assert _state_of(app.btn_stop) == "normal", "执行中「停止执行」必须可用"
    assert _state_of(app.btn_scan) == "disabled"
    assert _state_of(app.btn_execute) == "disabled"
    assert _state_of(app.btn_export) == "disabled"

    # 点「停止执行」：真的置上停止事件 + 自身置灰 + 给出"正在停止…"
    app.stop_execution()
    assert app._stop_event.is_set(), "点「停止」必须置上停止事件（这是执行器真正读的信号）"
    assert _state_of(app.btn_stop) == "disabled"
    assert "正在停止" in app.var_execute_hint.get()

    # 后台线程结束、回主线程刷状态：空闲 + 有报告 → 导出可用
    app._set_state(busy=BUSY_NONE, stopping=False)
    assert _state_of(app.btn_export) == "normal", "空闲且有报告 → 导出可用"
    assert _state_of(app.btn_stop) == "disabled"
    assert app.state.idle and not app.state.flag("stopping")


def test_scan_disables_actions_until_finished(window, monkeypatch):
    """真扫描：命令返回时按钮已禁用（忙标志在线程启动前置上），结束后自动恢复。"""
    win, _calls = window
    app = win.di_app
    original = win_mod.parser.load_cases
    monkeypatch.setattr(win_mod.parser, "load_cases",
                        lambda target, *a, **k: original(target, *a, **k)[:5])

    app.scan()
    assert app.state.busy == BUSY_SCAN, "启动扫描后状态应立刻是 BUSY_SCAN"
    assert _state_of(app.btn_execute) == "disabled", "扫描中「执行」应禁用"
    assert _state_of(app.btn_scan) == "disabled"
    assert _state_of(app.btn_export) == "disabled"

    assert _pump(win, app, lambda: app.var_summary.get().startswith("用例")), \
        f"扫描未完成，汇总={app.var_summary.get()!r}"
    # 约定：状态类消息先于 summary 入队 → 汇总已刷新时忙标志必然已经回落到空闲
    assert app.state.idle, "扫描结束后应回到空闲"
    assert app.state.flag("has_cases")
    assert _state_of(app.btn_execute) == "normal"
    assert _state_of(app.btn_scan) == "normal"
    assert _state_of(app.btn_export) == "disabled", "只扫描过、还没执行 → 导出仍禁用"


# ---------------------------------------------------------------- 中止链路
def test_stop_execution_aborts_run_and_marks_report(window, monkeypatch):
    """中止链路：窗口的停止事件 → run_cases(should_stop) → 报告 aborted → 预览标注。"""
    win, _calls = window
    app = win.di_app
    original = win_mod.parser.load_cases
    monkeypatch.setattr(win_mod.parser, "load_cases",
                        lambda target, *a, **k: original(target, *a, **k)[:8])
    monkeypatch.setattr(win_mod.DiCaseWindow, "_prepare_senders",
                        lambda self: (None, None, None, "[测试] 未接设备 → 体检模式"))

    seen: dict[str, object] = {}
    real_run = win_mod.runner.DiCaseRunner.run_cases

    def _abort_immediately(self, cases, **kwargs):
        """接住窗口传进来的 should_stop，并强制"一上来就收到停止请求"走中止分支。"""
        seen["should_stop"] = kwargs.get("should_stop")
        kwargs.pop("should_stop", None)
        return real_run(self, cases, should_stop=lambda: True, **kwargs)

    monkeypatch.setattr(win_mod.runner.DiCaseRunner, "run_cases", _abort_immediately)

    app.scan()
    # 等扫描真正结束（状态回到空闲）再执行：忙标志就是"上一次任务还在跑"的唯一判据
    assert _pump(win, app, lambda: app.state.idle and bool(app._cases)), "扫描未取到用例"
    app.execute()

    assert _pump(win, app, lambda: "被用户中止" in app.preview.get("1.0", "end-1c")), \
        f"中止报告未进预览：{app.preview.get('1.0', '3.0')!r}"
    report = app._report
    assert report is not None and report.aborted, "中止必须体现在报告上"
    assert report.aborted_cases == 8, "一条都没跑 → 全部记为未执行"
    assert report.results == []
    assert report.summary["aborted_cases"] == 8 and report.summary["aborted"] is True
    assert report.summary["verdict"] == "PASS", "aborted 不计入失败"
    assert "aborted" in app.preview.get("1.0", "end-1c")
    assert "已中止" in app.var_summary.get()

    assert callable(seen["should_stop"]), "窗口必须把 should_stop 交给执行器"
    app._stop_event.set()
    assert seen["should_stop"]() is True, "传进去的应是绑在窗口停止事件上的活回调"
    app._stop_event.clear()

    # 结束后回空闲态：导出可用、停止不可用（后台线程结束由主线程刷回来）
    assert app.state.idle and not app.state.flag("stopping")
    assert _state_of(app.btn_export) == "normal"
    assert _state_of(app.btn_stop) == "disabled"


def test_legacy_format_disables_execute_with_explanation(monkeypatch):
    """legacy 格式 → 「执行」禁用并给出说明；扫描保留；程序调用也拦住（只提示）。"""
    monkeypatch.setattr(case_format, "_active", case_format.LEGACY)
    calls: list[tuple] = []
    monkeypatch.setattr(win_mod.messagebox, "showwarning",
                        lambda *a, **k: calls.append(("warn", a[:1])))
    monkeypatch.setattr(win_mod.messagebox, "askyesno",
                        lambda *a, **k: pytest.fail("legacy 下不应弹出执行确认框"))

    root = tk.Tk()
    root.withdraw()
    win = win_mod.open_di_case_window(root)
    try:
        app = win.di_app
        win.update_idletasks()
        assert app.var_format.get() == case_format.LEGACY
        assert _state_of(app.btn_execute) == "disabled", "legacy → 执行禁用"
        assert _state_of(app.btn_scan) == "normal", "legacy → 扫描保留"
        assert "legacy" in app.var_execute_hint.get(), "必须说明为什么不可执行"

        app.execute()
        assert [kind for kind, _ in calls] == ["warn"], "程序调用也要给说明，而不是静默返回"

        # 切回 di → 执行恢复可用（同一套状态机，没有第二处 config）
        app.var_format.set(case_format.DI)
        app._on_switch()
        assert _state_of(app.btn_execute) == "normal"
        assert "legacy" not in app.var_execute_hint.get()
    finally:
        # 既有顺序：先 stop 再 destroy（Windows 验证套件依赖）
        app.stop()
        win.destroy()
        root.destroy()
