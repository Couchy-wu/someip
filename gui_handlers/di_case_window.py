# -*- coding: utf-8 -*-
"""gui_handlers.di_case_window —— Di 测试用例窗口（扫描/执行/停止/报告/导出）

界面结构（**pack 自上而下堆叠**，即"界面优化"之前的那套摆放）：

    ┌ LabelFrame「用例格式开关（旧链路保持不变，仅切换解析入口）」
    │   ( ) legacy —— …   (•) di —— …   ( ) auto —— …
    │   环境变量 HUD_TESTCASE_FORMAT 也可指定；当前：…
    ├ 目录行（tk.Frame）：用例目录: [TestcaseCollection/Di_testcases   ] [浏览…]
    ├ 动作行（tk.Frame）：[扫描统计] [执行（需 CAN 设备）] [停止执行]
    │                     [只跑可全自动用例] [导出报告（Markdown + JSON）] [清空]
    │                     说明：随状态变化的一行提示（为什么可点 / 为什么不可点）
    ├ 汇总行：用例 497 个｜支持度 auto 170 / partial 327｜…
    └ 输出区（tk.Frame + Notebook）：执行日志 / 报告预览（Markdown，执行完自动切到该页签）

布局约定：本窗口全部用 ``pack``（**没有 grid**），因此不存在"两个控件占同一格"的问题；
`tests/test_di_gui.py` 会断言整窗 ``audit_widget_tree(root) == []``。

三条贯穿全窗口的约定（本次重构的核心逻辑，**布局回退后原样保留**）：

1. **状态机**：`self.state`（`hudcore.ui.state.UiState`）是界面可用性的**唯一**来源。
   所有按钮/勾选框/输入框都登记在 `self.buttons`（`ButtonGroup`）里，规则是模块级的
   纯函数（见 `BUTTON_RULES`），改状态只走 :meth:`DiCaseWindow._set_state` →
   `buttons.apply(state)`，界面里不再有第二处 ``config(state=...)``。

   ==================  ==========================================================
   状态                可用性
   ==================  ==========================================================
   空闲                扫描 / 执行(非 legacy) / 清空 / 勾选 / 改目录 / 改格式
   扫描中 BUSY_SCAN    上述全部禁用，导出与停止也禁用
   执行中 BUSY_EXECUTE 扫描/执行/导出/清空/改目录禁用；**停止执行**可用
   正在停止            「停止执行」也置灰（已请求，等当前用例跑完）
   无报告              导出报告禁用（空闲且有报告才可用）
   legacy 格式         执行禁用并给出说明（本窗口只跑 Di 格式；扫描仍可用来看分布）
   ==================  ==========================================================

2. **停止链路**：`self._stop_event`（`threading.Event`）→ `DiCaseRunner.run_cases(should_stop=…)`
   在**用例之间**检查；命中即跳出循环，报告标记 `aborted`（剩余用例未执行、不计入失败）。

3. **线程**：后台线程只算不画 —— 结果一律 ``put`` 进 `self._queue`，主线程
   :meth:`_poll_queue` 每 200ms 搬运一次；工作线程不碰 Tk 控件、不读 Tk 变量。
   回传只有 :meth:`DiCaseWindow._dispatch` 一个出口，它保证**先把状态类消息
   （``flags`` + ``busy``）入队，再发内容消息（``summary``/``text``/``preview``）**：
   因此界面读到文案时按钮状态必然已经生效，任务也不会"忘了把界面从忙里放出来"。

其他既有约定（不改）：旧链路 `gui_handlers/can_testcase_parser.py` 完全不参与；
执行前的 `_prepare_senders()` 仍先做子进程设备探测（Linux 未插卡时底层 VCI 会段错误），
拿不到设备就退回体检模式；`stop()` 可重复调用，关闭窗口时必须先 `stop()` 再 `destroy()`。
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from hudcore import logging_setup
from hudcore.platform.paths import paths
from hudcore.ui.state import (
    BUSY_EXECUTE,
    BUSY_NONE,
    BUSY_SCAN,
    ButtonGroup,
    Rule,
    UiState,
)
from hudcore.ui.theme import Theme

from can_data_tools import case_format
from can_data_tools import di_case_parser as parser
from can_data_tools import di_case_runner as runner
from can_data_tools.label_verify import LabelVerifier, LabelVerifierError

LOGGER_NAME = "di_case"

# ---------------------------------------------------------------- 状态标志名
FLAG_HAS_CASES = "has_cases"           # 已扫描到用例
FLAG_SCANNED = "scanned"              # 至少完成过一次扫描（用于区分"没扫过"和"扫了但没用例"）
FLAG_HAS_REPORT = "has_report"         # 已有可导出的执行报告
FLAG_LEGACY_FORMAT = "legacy_format"   # 格式开关处于 legacy（本窗口只跑 Di 格式）
FLAG_STOPPING = "stopping"             # 已请求停止，等执行器在用例之间退出


# ---------------------------------------------------------------- 状态规则表（纯函数）
def can_browse(state: UiState) -> bool:
    """浏览/改用例目录：只在完全空闲时可点（跑到一半换目录会让结果与目录对不上）。"""
    return state.idle


def can_scan(state: UiState) -> bool:
    """扫描统计：空闲即可（不碰设备；legacy 下也保留 —— 它只展示 Di 目录的输入分布）。"""
    return state.idle


def can_execute(state: UiState) -> bool:
    """执行：空闲 **且** 不是 legacy 格式。

    legacy 下本窗口没有对应的解析链路（旧格式走 `gui_handlers/can_testcase_parser.py`），
    因此禁用并给出说明，而不是让用户点了之后拿到一个"体检"结果。
    """
    return state.idle and not state.flag(FLAG_LEGACY_FORMAT)


def can_stop(state: UiState) -> bool:
    """停止执行：正在执行且尚未请求停止时可点（已请求就置灰，避免重复点）。"""
    return state.busy_is(BUSY_EXECUTE) and not state.flag(FLAG_STOPPING)


def can_export(state: UiState) -> bool:
    """导出报告：空闲**且**已有报告（没执行过就禁用，不再靠点了之后弹提示）。"""
    return state.idle and state.flag(FLAG_HAS_REPORT)


def can_clear(state: UiState) -> bool:
    """清空输出：空闲即可（执行中清日志会把正在回传的进度也清掉）。"""
    return state.idle


def can_toggle_only_auto(state: UiState) -> bool:
    """勾选"只跑可全自动用例"：空闲即可（执行中改勾选对本次执行没有意义）。"""
    return state.idle


def can_switch_format(state: UiState) -> bool:
    """改格式开关：空闲即可（执行中改格式会与正在跑的结果打架）。"""
    return state.idle


#: 控件 key → 规则：登记进 `ButtonGroup` 时统一从这里取，测试也可直接断言规则表
BUTTON_RULES: dict[str, Rule] = {
    "format": can_switch_format,
    "dir": can_browse,
    "browse": can_browse,
    "scan": can_scan,
    "execute": can_execute,
    "stop": can_stop,
    "only_auto": can_toggle_only_auto,
    "export": can_export,
    "clear": can_clear,
}

#: legacy 下「执行」为什么不可用（说明文案，按钮提示与程序调用共用）
LEGACY_EXECUTE_HINT = (
    "当前格式开关是 legacy（旧格式）：本窗口只跑 Di 格式用例，所以「执行」不可用 —— "
    "请把格式切到 di（或 auto 按文件识别）后再执行。"
    "「扫描统计」仍然可用，它只解析 Di 目录、展示输入分布，不会下发任何输入。"
)


def execute_hint(state: UiState, case_count: int = 0) -> str:
    """「执行」按钮下方的一行说明（纯函数：同一状态 → 同一句话，便于单测）。

    :param state: 当前界面状态
    :param case_count: 已载入的用例数（仅用于措辞，不参与可用性判断）
    """
    if state.flag(FLAG_LEGACY_FORMAT):
        return LEGACY_EXECUTE_HINT
    if state.busy_is(BUSY_EXECUTE):
        if state.flag(FLAG_STOPPING):
            return "正在停止…（当前用例跑完即退出循环，剩余用例不再执行）"
        return (f"执行中（已载入 {case_count} 条）…点「停止执行」可随时中止："
                "中止后报告标记 aborted，剩余用例不再执行。")
    if state.busy_is(BUSY_SCAN):
        return "扫描中…（只解析与统计，不碰设备）"
    if state.flag(FLAG_HAS_REPORT):
        return "执行完成：报告已生成，「导出报告」可落成 .md + .json 两个文件。"
    if state.flag(FLAG_HAS_CASES):
        return (f"已载入 {case_count} 条用例：点「执行」开始下发"
                "（无 CAN 设备时自动退回体检模式，只合成不下发）。")
    if state.flag(FLAG_SCANNED):
        return "扫描完成：该目录没有解析到 Di 用例，请检查「用例目录」是否是 Di 用例 JSON。"
    return "尚未扫描：先点「扫描统计」解析用例目录（不碰设备）。"


def _format_note() -> str:
    """格式开关下面的一行说明（环境变量 + 当前生效来源）。"""
    return f"环境变量 {case_format.ENV_VAR} 也可指定；当前：{case_format.describe()}"


class DiCaseWindow:
    """Di 用例窗口（可独立实例化，也可由 main.py 以 Toplevel 打开）。"""

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._cases: list[parser.DiCase] = []
        self._report: runner.RunReport | None = None
        self._poll_id: str | None = None
        self._closed = False
        self._stop_event = threading.Event()      # 「停止执行」→ set；执行器在用例之间检查

        # 界面状态源（单一）：改它 → 刷按钮，别处不再逐个 config(state=...)
        self.state = UiState(busy=BUSY_NONE, flags={
            FLAG_HAS_CASES: False,
            FLAG_SCANNED: False,
            FLAG_HAS_REPORT: False,
            FLAG_LEGACY_FORMAT: case_format.active_format() == case_format.LEGACY,
            FLAG_STOPPING: False,
        })
        self.buttons = ButtonGroup(name="di_case_window")

        root.title("Di 测试用例（CAN + SOME/IP + 标贴校验）")
        root.geometry("1120x720")

        self._build_ui()
        self._refresh_buttons()                   # 开窗即按规则表落一次可用性
        self._poll_queue()

    # ------------------------------------------------------------ 界面
    def _build_ui(self) -> None:
        """按 pack 顺序往下堆：格式开关 → 目录行/动作行 → 汇总行 → 输出区。

        布局是**回退后**的形态：控件一律 `pack`，没有 SectionStack/ActionBar、
        也没有带标题的区块。因此整窗不存在 grid 格子，`audit_widget_tree` 必然为空
        （断言见 `tests/test_di_gui.py::test_layout_has_no_grid_collisions`）。
        """
        self._build_switch()
        self._build_toolbar()
        self._build_output()

    def _build_switch(self) -> None:
        """用例格式开关：LabelFrame + Radiobutton 逐项 + 环境变量说明。"""
        box = tk.LabelFrame(self.root, text="用例格式开关（旧链路保持不变，仅切换解析入口）")
        box.pack(fill=tk.X, padx=8, pady=6)
        self.frame_format = box                    # 供测试/排障定位（不参与业务）

        formats = case_format.available_formats()
        self.var_format = tk.StringVar(value=case_format.active_format())
        for value, desc in formats.items():
            radio = tk.Radiobutton(box, text=f"{value} —— {desc}", value=value,
                                   variable=self.var_format, command=self._on_switch,
                                   **Theme.check_button())
            radio.pack(anchor=tk.W, padx=6, pady=1)
            self.buttons.add(f"format:{value}", radio, BUTTON_RULES["format"])
        self.var_format_note = tk.StringVar(value=_format_note())
        tk.Label(box, textvariable=self.var_format_note,
                 **Theme.hint_label()).pack(anchor=tk.W, padx=6, pady=(2, 4))

    def _build_toolbar(self) -> None:
        """目录行 + 动作行（扫描/执行/停止/只跑自动/导出/清空）+ 汇总行。"""
        bar = tk.Frame(self.root)
        bar.pack(fill=tk.X, padx=8)
        self.frame_dir = bar                       # 供测试/排障定位（不参与业务）

        tk.Label(bar, text="用例目录:", **Theme.field_label()).pack(side=tk.LEFT)
        self.var_dir = tk.StringVar(value=str(paths.project_root / parser.DEFAULT_CASE_DIR))
        self.entry_dir = tk.Entry(bar, textvariable=self.var_dir, width=58,
                                  font=Theme.font_tuple(10))
        self.entry_dir.pack(side=tk.LEFT, padx=4)
        self.buttons.add("dir", self.entry_dir, BUTTON_RULES["dir"])

        self.btn_browse = tk.Button(bar, text="浏览…", command=self._choose_dir,
                                    **Theme.info_button(width=10, height=1))
        self.btn_browse.pack(side=tk.LEFT)
        self.buttons.add("browse", self.btn_browse, BUTTON_RULES["browse"])

        actions = tk.Frame(self.root)
        actions.pack(fill=tk.X, padx=8, pady=4)
        self.frame_actions = actions               # 供测试断言按钮的摆放顺序

        # 状态说明行：先按 BOTTOM 占位，后面的按钮才留在同一行里。
        # （pack 的 side=LEFT 不会自动换行：顺序反了，说明会挤到按钮右边而不是下面。）
        self.var_execute_hint = tk.StringVar(value=execute_hint(self.state))
        tk.Label(actions, textvariable=self.var_execute_hint, wraplength=1040,
                 **Theme.hint_label()).pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=(2, 0))

        self.btn_scan = tk.Button(actions, text="扫描统计", command=self.scan,
                                  **Theme.info_button(width=12, height=1))
        self.btn_scan.pack(side=tk.LEFT, padx=2)
        self.buttons.add("scan", self.btn_scan, BUTTON_RULES["scan"])

        self.btn_execute = tk.Button(actions, text="执行（需 CAN 设备）", command=self.execute,
                                     **Theme.primary_button(width=22, height=1))
        self.btn_execute.pack(side=tk.LEFT, padx=2)
        self.buttons.add("execute", self.btn_execute, BUTTON_RULES["execute"])

        # 「停止执行」紧跟「执行」之后（真正的停止：事件 → 执行器在用例之间退出）
        self.btn_stop = tk.Button(actions, text="停止执行", command=self.stop_execution,
                                  **Theme.danger_button(width=12, height=1))
        self.btn_stop.pack(side=tk.LEFT, padx=2)
        self.buttons.add("stop", self.btn_stop, BUTTON_RULES["stop"])

        self.var_only_auto = tk.BooleanVar(value=False)
        self.chk_only_auto = tk.Checkbutton(actions, text="只跑可全自动用例",
                                            variable=self.var_only_auto,
                                            **Theme.check_button())
        self.chk_only_auto.pack(side=tk.LEFT, padx=8)
        self.buttons.add("only_auto", self.chk_only_auto, BUTTON_RULES["only_auto"])

        self.btn_export = tk.Button(actions, text="导出报告（Markdown + JSON）",
                                    command=self.export_report,
                                    **Theme.success_button(width=26, height=1))
        self.btn_export.pack(side=tk.LEFT, padx=2)
        self.buttons.add("export", self.btn_export, BUTTON_RULES["export"])

        self.btn_clear = tk.Button(actions, text="清空", command=self._clear_output,
                                   **Theme.neutral_button(width=10, height=1))
        self.btn_clear.pack(side=tk.LEFT, padx=2)
        self.buttons.add("clear", self.btn_clear, BUTTON_RULES["clear"])

        self.var_summary = tk.StringVar(value="（尚未扫描）")
        tk.Label(self.root, textvariable=self.var_summary, anchor=tk.W, justify=tk.LEFT,
                 font=Theme.font_tuple(10)).pack(fill=tk.X, padx=8)

    def _build_output(self) -> None:
        """输出区：执行日志 + 报告预览（Markdown，执行完自动切页签）。"""
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.frame_output = frame                  # 供测试/排障定位（不参与业务）

        self.notebook = ttk.Notebook(frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        log_tab = tk.Frame(self.notebook)
        self.notebook.add(log_tab, text="执行日志")
        self.text = tk.Text(log_tab, **{**Theme.log_text_style(),
                                        "wrap": tk.NONE, "height": 20})
        log_yscroll = tk.Scrollbar(log_tab, command=self.text.yview)
        self.text.configure(yscrollcommand=log_yscroll.set)
        log_yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        preview_tab = tk.Frame(self.notebook)
        self.notebook.add(preview_tab, text="报告预览（Markdown）")
        self.preview = tk.Text(preview_tab, **{**Theme.log_text_style(),
                                               "wrap": tk.NONE, "height": 20})
        preview_yscroll = tk.Scrollbar(preview_tab, command=self.preview.yview)
        self.preview.configure(yscrollcommand=preview_yscroll.set)
        preview_yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preview.insert(tk.END, "（执行后这里显示 Markdown 报告；"
                                    "也可用“导出报告”写成 .md/.json 两个文件）")

    # ------------------------------------------------------------ 状态机
    def _set_state(self, busy: str | None = None, **flags: bool) -> None:
        """改状态 → 统一刷新控件（界面里**唯一**改可用性的入口）。"""
        state = self.state
        if busy is not None:
            state = state.with_busy(busy)
        if flags:
            state = state.with_flags(**flags)
        self.state = state
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        """按规则表刷新所有按钮/勾选框/输入框，并更新「执行」说明文字。"""
        self.buttons.apply(self.state)
        self.var_execute_hint.set(execute_hint(self.state, len(self._cases)))

    # ------------------------------------------------------------ 交互
    def _on_switch(self) -> None:
        """格式开关变化：写回 `case_format` 并同步状态机（legacy → 执行禁用）。"""
        value = case_format.set_format(self.var_format.get())
        self.var_format_note.set(_format_note())
        self._set_state(**{FLAG_LEGACY_FORMAT: value == case_format.LEGACY})
        self._append(f"格式开关 → {value}（环境变量 {case_format.ENV_VAR} 可覆盖）")

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.var_dir.get() or str(paths.project_root))
        if chosen:
            self.var_dir.set(chosen)

    def scan(self) -> None:
        """解析并统计（不碰设备）。

        注意：Tk 变量只能在主线程读（后台线程读会抛 "main thread is not in main loop"），
        因此这里先取值再交给工作线程。
        """
        if not self._start_worker(self._do_scan, BUSY_SCAN, Path(self.var_dir.get())):
            return
        self._append("开始扫描用例目录…（只解析与统计，不碰设备）")

    def execute(self) -> None:
        """真执行：CAN 输入下发 + 画面标贴校验（无设备时退回体检）。"""
        if self.state.flag(FLAG_LEGACY_FORMAT):
            messagebox.showwarning("执行不可用（legacy 格式）", LEGACY_EXECUTE_HINT)
            return
        if not self._cases:
            self.scan()
            return
        if not messagebox.askyesno("确认执行",
                                   f"将对 {len(self._cases)} 条用例下发 CAN 报文（需已连接设备）。\n"
                                   "继续执行？"):
            return
        self._stop_event.clear()                  # 新一轮执行 → 清掉上一次的停止请求
        # 主线程先取 Tk 变量值，避免工作线程访问界面对象
        if self._start_worker(self._do_execute, BUSY_EXECUTE, bool(self.var_only_auto.get())):
            self._append(f"开始执行（已载入 {len(self._cases)} 条，点「停止执行」可随时中止）…")

    def stop_execution(self) -> None:
        """点「停止执行」：请求中止批量执行（真能停 —— 执行器在用例之间检查）。

        单条用例内部不打断（避免设备停在半下发状态），所以文案是"正在停止…"；
        后台线程结束后由主线程把按钮状态刷回来（busy=NONE + stopping=False）。
        """
        if not self.state.busy_is(BUSY_EXECUTE) or self.state.flag(FLAG_STOPPING):
            return
        self._stop_event.set()
        self._set_state(busy=BUSY_EXECUTE, **{FLAG_STOPPING: True})
        self._append("[停止] 已请求中止：当前用例结束后退出循环，剩余用例不再执行。")

    def export_report(self) -> None:
        """导出报告（按钮由状态机控制；这里保留兜底提示，程序调用也不会崩）。"""
        if self._report is None:
            messagebox.showinfo("导出报告", "还没有执行结果，请先扫描/执行。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".md",
                                            initialfile="di_run_report.md")
        if not path:
            return
        md_path = Path(path)
        written = self._report.write_reports(md_path, md_path.with_suffix(".json"))
        messagebox.showinfo("导出报告",
                            f"已写入：\n{written}\n{md_path.with_suffix('.json')}")

    # ------------------------------------------------------------ 后台任务
    def _start_worker(self, target, busy: str, *args) -> bool:
        """启动后台任务（既有模式：线程 + queue）。

        忙标志在这里置上，并且**以状态机为准**判断"上一次任务是否还在跑"——
        不再各处 `self._worker.is_alive()`：忙标志在起线程前置上、由任务最后一条状态消息
        清掉，所以既不会漏拦重复点击，也不会因为线程收尾比消息慢而误报"请稍候"。
        """
        if not self.state.idle:
            messagebox.showinfo("请稍候", "上一次任务还在执行中，请等它结束或点「停止执行」。")
            return False
        self._set_state(busy=busy, **{FLAG_STOPPING: False})
        self._worker = threading.Thread(target=target, args=args, daemon=True)
        self._worker.start()
        return True

    def _dispatch(self, *, flags: dict | None = None,
                  messages: "list[tuple[str, object]]" = ()) -> None:
        """工作线程往界面回传的**唯一**出口（状态消息先入队，再发内容消息）。

        内容消息一律在任务末尾一次性发出，且 `busy` 清空消息排在它们前面，于是：
        界面看到 `summary`/`preview` 时，状态已经回到"任务已结束"；
        任何异常路径只要走到这里，按钮就不会一直灰着。
        """
        if flags:
            self._post("flags", dict(flags))
        self._post("busy", BUSY_NONE)
        for kind, payload in messages:
            self._post(kind, payload)

    def _do_scan(self, target: Path) -> None:
        """扫描（工作线程）：先算完，再走 `_dispatch` 回传（异常也要把界面放出来）。"""
        try:
            flags, messages = self._scan_messages(target)
        except Exception as exc:                       # noqa: BLE001 - 界面线程不能因异常崩掉
            flags = {FLAG_HAS_CASES: False, FLAG_SCANNED: True}
            messages = [("text", f"[错误] 扫描失败：{exc}")]
        self._dispatch(flags=flags, messages=messages)

    def _scan_messages(self, target: Path) -> "tuple[dict, list[tuple[str, object]]]":
        """扫描的纯计算部分：返回 (状态标志, 待回传消息)。"""
        cases = parser.load_cases(target)
        self._cases = cases
        stats = parser.summarize(cases)
        from someip_core import active_table, available_tables, registrable
        table = active_table()
        table_info = available_tables()[table]
        messages: "list[tuple[str, object]]" = [
            ("summary",
             f"用例 {stats['cases']} 个｜支持度 {stats['support']}｜"
             f"SOME/IP 服务表 {table}"
             f"（{'可注册' if registrable(table) else '库侧暂不可注册'}，"
             f"{table_info['services']} 服务/{table_info['events']} 事件）｜"
             f"CAN {stats['can_entries']} 条 / SOME/IP 字段 {stats['someip_field_entries']} / "
             f"链路 {stats['someip_link_entries']} / mem {stats['mem_entries']}｜"
             f"期望显示 {stats['expect_visible']} 条、期望隐藏 {stats['expect_hidden']} 条"),
            ("text", f"目录：{target}"),
        ]
        if not cases:
            messages.append(("text", "[提示] 该目录没有解析到 Di 用例（检查目录是否为 Di 用例 JSON）"))
        messages.append(("text", "标签（前 12）：" + "、".join(
            f"{k}×{v}" for k, v in list(stats["labels"].items())[:12])))
        if stats["someip_links"]:
            messages.append(("text", "SOME/IP 链路输入：" + "、".join(
                f"{k}×{v}" for k, v in stats["someip_links"].items())))
        if stats["anomalies"]:
            messages.append(("text", f"格式特征：{stats['anomalies']}"))
        # 顺带报告标贴参考图覆盖情况
        try:
            coverage = LabelVerifier().coverage(
                [c.expected.primary_label for c in cases] +
                [c.expected.negative_label for c in cases])
            messages.append(("text",
                             f"标贴参考图覆盖：{coverage['covered']}/{coverage['labels']} 可校验；"
                             f"无参考图 {coverage['uncovered']} 个（会记为 unverifiable）：" +
                             "、".join(coverage["uncovered_list"][:15]) + "…"))
        except LabelVerifierError as exc:
            messages.append(("text", f"[警告] 标贴校验器不可用：{exc}"))
        return {FLAG_HAS_CASES: bool(cases), FLAG_SCANNED: True}, messages

    def _do_execute(self, only_auto: bool = False) -> None:
        """执行（工作线程）：真下发/体检 + 标贴校验；中止由 `should_stop` 传进执行器。

        异常兜底：无论哪一步炸了，都要把界面从"忙"里放出来（否则按钮一直灰着）。
        """
        try:
            flags, messages = self._execute_messages(only_auto)
        except Exception as exc:                       # noqa: BLE001
            logging_setup.error(LOGGER_NAME, f"执行任务异常：{exc}")
            flags = {FLAG_STOPPING: False}
            messages = [("text", f"[错误] 执行异常：{exc}")]
        self._dispatch(flags=flags, messages=messages)

    def _execute_messages(self, only_auto: bool = False) -> "tuple[dict, list[tuple[str, object]]]":
        """执行的纯计算部分：返回 (状态标志, 待回传消息)。"""
        cases = [c for c in self._cases]
        if only_auto:
            cases = [c for c in cases if parser.classify(c).level == "auto"]
        if not cases:
            return ({FLAG_STOPPING: False},
                    [("text", "[提示] 没有可执行的用例（试试取消“只跑可全自动用例”）")])

        can_sender, someip, closer, note = self._prepare_senders()
        messages: "list[tuple[str, object]]" = []
        if note:
            messages.append(("text", note))

        dry_run = can_sender is None
        exec_runner = runner.DiCaseRunner(
            can_sender=can_sender, someip_controller=someip,
            frame_provider=self._frame_provider(), verifier=self._safe_verifier(),
            dry_run=dry_run, wait_scale=1.0,
            on_log=lambda m: self._post("text", "  " + m))
        messages.append(("text", f"开始执行（{'体检模式' if dry_run else '真下发'}）…"))
        report: runner.RunReport | None = None
        try:
            # 停止链路：事件在用例之间被检查（工作线程只读 Event，不碰 Tk）
            report = exec_runner.run_cases(cases, should_stop=self._stop_event.is_set)
        except Exception as exc:                       # noqa: BLE001 - 执行失败也要收尾
            logging_setup.error(LOGGER_NAME, f"批量执行异常：{exc}")
            messages.append(("text", f"[错误] 执行失败：{exc}"))
        finally:
            if closer:
                closer()
            if exec_runner.someip_controller is not None:
                exec_runner.someip_controller.close()
        if report is None:
            return {FLAG_STOPPING: False}, messages

        self._report = report
        summary = report.summary
        messages.append(("summary", f"执行{'已中止' if report.aborted else '完成'}："
                                    f"{summary['status']}｜画面校验 {summary['frame_status']}"))
        if report.aborted:
            messages.append(("text", "[中止] " + report.abort_note()))
        messages.append(("text", report.describe(limit=40)))
        # 报告预览：Markdown 原文（评审可直接复制；导出按钮会落成 .md/.json）
        messages.append(("preview", report.render_markdown()))
        return {FLAG_HAS_REPORT: True, FLAG_STOPPING: False}, messages

    def _prepare_senders(self):
        """准备 CAN / SOME/IP 下发实现；拿不到就退回体检模式并说明原因。

        注意：先做**子进程探测** —— Linux 上未插卡时底层 VCI 驱动会段错误，
        直接在主进程里调 `Initialize_Canfd_Device()` 会把整个上位机带走。
        """
        note = ""
        can_sender = None
        try:
            from can_core import device_probe
            probe = device_probe.probe_can_device()
            if not probe.available:
                return None, None, None, ("[提示] " + probe.describe() +
                                          " → 本次只做体检（不实际下发）")
        except Exception as exc:                    # noqa: BLE001 - 探测本身失败也退回体检
            note = f"[提示] 设备探测异常（{exc}）→ 本次只做体检（不实际下发）"
            return None, None, None, note
        try:
            from can_core import device
            dev, handles, threads = device.Initialize_Canfd_Device()
            if dev and handles:
                can_sender = runner.DeviceCanSender(handles[0])

                def closer():
                    try:
                        device.Close_Canfd_Device(dev, handles, threads)
                    except Exception as exc:           # noqa: BLE001
                        logging_setup.warning(LOGGER_NAME, f"关闭 CAN 设备异常：{exc}")
                return can_sender, None, closer, note
            note = "[提示] CAN 设备未就绪 → 本次只做体检（不实际下发）"
        except Exception as exc:                        # noqa: BLE001
            note = f"[提示] CAN 设备初始化失败（{exc}）→ 本次只做体检（不实际下发）"
        return None, None, None, note

    @staticmethod
    def _frame_provider():
        """画面来源：优先相机；不可用时返回 None（标贴会记为 unverifiable）。"""
        try:
            from camera_tools.camera_preview import try_open_camera
        except Exception:                               # noqa: BLE001 - 无 cv2 等依赖
            return None

        def _grab():
            cap, index = try_open_camera(indices=(0,))
            if index is None:
                return None
            try:
                ret, frame = cap.read()
                return frame if ret else None
            finally:
                cap.release()
        return _grab

    @staticmethod
    def _safe_verifier():
        try:
            return LabelVerifier()
        except LabelVerifierError:
            return None

    # ------------------------------------------------------------ 输出
    def _poll_queue(self) -> None:
        """定时把后台线程的结果搬到界面（窗口关闭后必须停止，否则会打到已销毁的控件）。"""
        if self._closed:
            return
        try:
            while True:
                try:
                    kind, message = self._queue.get_nowait()
                except queue.Empty:
                    break
                self._handle_message(kind, message)
        except tk.TclError:                      # 控件已销毁（窗口正在关闭）
            return
        try:
            self._poll_id = self.root.after(200, self._poll_queue)
        except tk.TclError:
            self._poll_id = None

    def _handle_message(self, kind: str, message: object) -> None:
        """一条队列消息 → 一次界面操作（**只有主线程**会走到这里）。"""
        if kind == "summary":
            self.var_summary.set(str(message))
        elif kind == "preview":
            self._show_preview(str(message))
        elif kind == "busy":
            busy = str(message)
            # 不在执行中就不该停在"正在停止…"
            self._set_state(busy=busy, **({FLAG_STOPPING: False} if busy == BUSY_NONE else {}))
        elif kind == "flags":
            flags = message if isinstance(message, dict) else {}
            self._set_state(**{str(k): bool(v) for k, v in flags.items()})
        else:
            self._append(str(message))

    def stop(self) -> None:
        """停止轮询与后台任务（关闭窗口时调用；可重复调用）。

        · 先置 `_closed`，`_poll_queue` 不再排下一轮（否则会打到已销毁的控件）；
        · 顺带 set 掉停止事件：万一还有批量执行在跑，它会尽快收尾（不再跑后面的用例）。
        """
        self._closed = True
        self._stop_event.set()
        if self._worker is not None and self._worker.is_alive():
            logging_setup.info(LOGGER_NAME,
                               "窗口关闭时后台任务仍在运行：已请求中止，任务在当前用例结束后自行收尾")
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None

    def _post(self, kind: str, message: object) -> None:
        self._queue.put((kind, message))

    def _append(self, message: str) -> None:
        self.text.insert(tk.END, message + "\n")
        self.text.see(tk.END)

    def _show_preview(self, markdown: str) -> None:
        """把 Markdown 报告填进预览页签（并自动切到该页签，省得手动点）。"""
        self.preview.delete("1.0", tk.END)
        self.preview.insert(tk.END, markdown)
        self.preview.see("1.0")
        try:
            self.notebook.select(1)
        except tk.TclError:                      # pragma: no cover - 页签不存在时忽略
            pass

    def _set_text(self, value: str) -> None:
        self.text.delete("1.0", tk.END)
        if value:
            self.text.insert(tk.END, value)

    def _clear_output(self) -> None:
        """清空日志与报告预览（`self._report` 保留：清屏不等于丢掉已执行的结果）。"""
        self._set_text("")
        self.preview.delete("1.0", tk.END)


def open_di_case_window(root: tk.Misc) -> tk.Toplevel:
    """按主界面需求打开独立窗口（与 someip_gui.open_replay_window 用法一致）。"""
    win = tk.Toplevel(root)
    win.transient(root)
    app = DiCaseWindow(win)
    setattr(win, "di_app", app)                          # 便于测试与关闭回调取用

    def _on_close() -> None:
        app.stop()
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    return win


__all__ = ["DiCaseWindow", "open_di_case_window"]
