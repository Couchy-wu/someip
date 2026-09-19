# -*- coding: utf-8 -*-
"""gui_handlers.di_case_window —— Di 测试用例窗口（扫描/执行/报告）

界面结构：

    ┌ 用例格式： ( ) 旧格式   (•) Di 格式   ( ) 自动识别        ← **选择开关**
    │ 用例目录：[TestcaseCollection/Di_testcases        ] [浏览…]
    │ [扫描统计] [执行(需 CAN 设备)] [导出 JSON 报告] [清空]
    ├ 汇总：用例 497 个｜支持度 auto 170 / partial 327｜…
    └ 结果：逐条列出（失败/错误优先），后台线程执行、队列回传（不卡界面）

设计约束（与项目约定一致）：
  · 旧链路（`gui_handlers/can_testcase_parser.py`）**完全不改**，本窗口只做新格式；
  · 格式开关落在 `can_data_tools.case_format`，可被环境变量 `HUD_TESTCASE_FORMAT` 覆盖；
  · 执行走后台线程 + `queue`，主线程只负责刷新界面；
  · 没有 CAN 设备时"执行"会退回体检（dry-run）并给出提示，不会抛异常。
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from hudcore import logging_setup
from hudcore.platform.paths import paths

from can_data_tools import case_format
from can_data_tools import di_case_parser as parser
from can_data_tools import di_case_runner as runner
from can_data_tools.label_verify import LabelVerifier, LabelVerifierError

LOGGER_NAME = "di_case"


class DiCaseWindow:
    """Di 用例窗口（可独立实例化，也可由 main.py 以 Toplevel 打开）。"""

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._cases: list[parser.DiCase] = []
        self._report: runner.RunReport | None = None

        root.title("Di 测试用例（CAN + SOME/IP + 标贴校验）")
        root.geometry("1080x640")

        self._build_switch()
        self._build_toolbar()
        self._build_output()
        self._poll_queue()

    # ------------------------------------------------------------ 界面
    def _build_switch(self) -> None:
        box = tk.LabelFrame(self.root, text="用例格式开关（旧链路保持不变，仅切换解析入口）")
        box.pack(fill=tk.X, padx=8, pady=6)

        self.var_format = tk.StringVar(value=case_format.active_format())
        for value, desc in case_format.available_formats().items():
            tk.Radiobutton(box, text=f"{value} —— {desc}", value=value, variable=self.var_format,
                           command=self._on_switch).pack(anchor=tk.W, padx=6, pady=1)
        tk.Label(box, anchor=tk.W,
                 text=f"环境变量 {case_format.ENV_VAR} 也可指定；当前：{case_format.describe()}"
                 ).pack(anchor=tk.W, padx=6, pady=(2, 4))

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self.root)
        bar.pack(fill=tk.X, padx=8)

        tk.Label(bar, text="用例目录:").pack(side=tk.LEFT)
        self.var_dir = tk.StringVar(value=str(paths.project_root / parser.DEFAULT_CASE_DIR))
        tk.Entry(bar, textvariable=self.var_dir, width=58).pack(side=tk.LEFT, padx=4)
        tk.Button(bar, text="浏览…", command=self._choose_dir).pack(side=tk.LEFT)

        actions = tk.Frame(self.root)
        actions.pack(fill=tk.X, padx=8, pady=4)
        tk.Button(actions, text="扫描统计", command=self.scan).pack(side=tk.LEFT, padx=2)
        tk.Button(actions, text="执行（需 CAN 设备）", command=self.execute).pack(side=tk.LEFT, padx=2)
        self.var_only_auto = tk.BooleanVar(value=False)
        tk.Checkbutton(actions, text="只跑可全自动用例", variable=self.var_only_auto).pack(side=tk.LEFT, padx=8)
        tk.Button(actions, text="导出 JSON 报告", command=self.export_report).pack(side=tk.LEFT, padx=2)
        tk.Button(actions, text="清空", command=lambda: self._set_text("")).pack(side=tk.LEFT, padx=2)

        self.var_summary = tk.StringVar(value="（尚未扫描）")
        tk.Label(self.root, textvariable=self.var_summary, anchor=tk.W,
                 justify=tk.LEFT).pack(fill=tk.X, padx=8)

    def _build_output(self) -> None:
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.text = tk.Text(frame, wrap=tk.NONE, height=20)
        yscroll = tk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------ 交互
    def _on_switch(self) -> None:
        value = case_format.set_format(self.var_format.get())
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
        self._start_worker(self._do_scan, Path(self.var_dir.get()))

    def execute(self) -> None:
        """真执行：CAN 输入下发 + 画面标贴校验（无设备时退回体检）。"""
        if not self._cases:
            self.scan()
            return
        if not messagebox.askyesno("确认执行",
                                   f"将对 {len(self._cases)} 条用例下发 CAN 报文（需已连接设备）。\n"
                                   "继续执行？"):
            return
        # 主线程先取 Tk 变量值，避免工作线程访问界面对象
        self._start_worker(self._do_execute, bool(self.var_only_auto.get()))

    def export_report(self) -> None:
        if self._report is None:
            messagebox.showinfo("导出报告", "还没有执行结果，请先扫描/执行。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile="di_run_report.json")
        if not path:
            return
        written = self._report.dump(path)
        messagebox.showinfo("导出报告", f"已写入：{written}")

    # ------------------------------------------------------------ 后台任务
    def _start_worker(self, target, *args) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("请稍候", "上一次任务还在执行中。")
            return
        self._worker = threading.Thread(target=target, args=args, daemon=True)
        self._worker.start()

    def _do_scan(self, target: Path) -> None:
        try:
            cases = parser.load_cases(target)
            self._cases = cases
            stats = parser.summarize(cases)
            from someip_core import active_table, available_tables, registrable
            table = active_table()
            table_info = available_tables()[table]
            self._post("summary",
                       f"用例 {stats['cases']} 个｜支持度 {stats['support']}｜"
                       f"SOME/IP 服务表 {table}"
                       f"（{'可注册' if registrable(table) else '库侧暂不可注册'}，"
                       f"{table_info['services']} 服务/{table_info['events']} 事件）｜"
                       f"CAN {stats['can_entries']} 条 / SOME/IP 字段 {stats['someip_field_entries']} / "
                       f"链路 {stats['someip_link_entries']} / mem {stats['mem_entries']}｜"
                       f"期望显示 {stats['expect_visible']} 条、期望隐藏 {stats['expect_hidden']} 条")
            self._post("text", f"目录：{target}")
            self._post("text", "标签（前 12）：" + "、".join(
                f"{k}×{v}" for k, v in list(stats["labels"].items())[:12]))
            if stats["someip_links"]:
                self._post("text", "SOME/IP 链路输入：" + "、".join(
                    f"{k}×{v}" for k, v in stats["someip_links"].items()))
            if stats["anomalies"]:
                self._post("text", f"格式特征：{stats['anomalies']}")
            # 顺带报告标贴参考图覆盖情况
            try:
                coverage = LabelVerifier().coverage(
                    [c.expected.primary_label for c in cases] +
                    [c.expected.negative_label for c in cases])
                self._post("text", f"标贴参考图覆盖：{coverage['covered']}/{coverage['labels']} 可校验；"
                                   f"无参考图 {coverage['uncovered']} 个（会记为 unverifiable）：" +
                                   "、".join(coverage["uncovered_list"][:15]) + "…")
            except LabelVerifierError as exc:
                self._post("text", f"[警告] 标贴校验器不可用：{exc}")
        except Exception as exc:                       # noqa: BLE001 - 界面线程不能因异常崩掉
            self._post("text", f"[错误] 扫描失败：{exc}")

    def _do_execute(self, only_auto: bool = False) -> None:
        cases = [c for c in self._cases]
        if only_auto:
            cases = [c for c in cases if parser.classify(c).level == "auto"]
        if not cases:
            self._post("text", "[提示] 没有可执行的用例（试试取消“只跑可全自动用例”）")
            return

        can_sender, someip, closer, note = self._prepare_senders()
        if note:
            self._post("text", note)

        dry_run = can_sender is None
        exec_runner = runner.DiCaseRunner(
            can_sender=can_sender, someip_controller=someip,
            frame_provider=self._frame_provider(), verifier=self._safe_verifier(),
            dry_run=dry_run, wait_scale=1.0,
            on_log=lambda m: self._post("text", "  " + m))
        self._post("text", f"开始执行（{'体检模式' if dry_run else '真下发'}）…")
        report = exec_runner.run_cases(cases)
        self._report = report
        self._post("summary", f"执行完成：{report.summary['status']}｜"
                              f"画面校验 {report.summary['frame_status']}")
        self._post("text", report.describe(limit=40))
        if closer:
            closer()
        if exec_runner.someip_controller is not None:
            exec_runner.someip_controller.close()

    def _prepare_senders(self):
        """准备 CAN / SOME/IP 下发实现；拿不到就退回体检模式并说明原因。"""
        note = ""
        can_sender = None
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
        try:
            while True:
                kind, message = self._queue.get_nowait()
                if kind == "summary":
                    self.var_summary.set(message)
                else:
                    self._append(message)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_queue)

    def _post(self, kind: str, message: str) -> None:
        self._queue.put((kind, message))

    def _append(self, message: str) -> None:
        self.text.insert(tk.END, message + "\n")
        self.text.see(tk.END)

    def _set_text(self, value: str) -> None:
        self.text.delete("1.0", tk.END)
        if value:
            self.text.insert(tk.END, value)


def open_di_case_window(root: tk.Misc) -> tk.Toplevel:
    """按主界面需求打开独立窗口（与 someip_gui.open_replay_window 用法一致）。"""
    win = tk.Toplevel(root)
    win.transient(root)
    app = DiCaseWindow(win)
    setattr(win, "di_app", app)                          # 便于测试与关闭回调取用
    return win


__all__ = ["DiCaseWindow", "open_di_case_window"]
