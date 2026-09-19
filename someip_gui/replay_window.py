# -*- coding: utf-8 -*-
"""someip_gui.replay_window —— SOME/IP 回放窗口（主类）

窗口布局（1100×780）：

    ┌──────────────────────────────────────────────────────────────────────┐
    │ 工具栏：[打开服务][启动服务][停止][关闭服务] 状态: 库就绪｜已启动｜…  [保存配置] │
    ├───────────────────────────────┬──────────────────────────────────────┤
    │ ① 网络与 SD 配置               │ ③ pcap 回放控制                       │
    │ ② 服务 / 事件（勾选=注册）      │ ④ 单条发送（结构化字段）               │
    │                               │ ⑤ 操作与报文日志                       │
    └───────────────────────────────┴──────────────────────────────────────┘

职责：
    · 组装布局（由 panel_config / panel_control 两个 Mixin 提供）
    · 持有 `ReplayController`，把界面动作翻译为控制器调用，并统一异常提示
    · 定时刷新状态（已发送条数、库状态）
    · 关闭时安全释放：停回放 → 停服务 → 销毁实例 → 保存配置

库不可用时（例如 Windows 尚无 DLL）：窗口照常打开，状态栏显示不可用原因，
服务/发送相关按钮置灰，并在日志区给出修复提示；用户可用"重新检测库"按钮重试。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from hudcore.someip import describe_library_status, is_library_available
from hudcore.ui import Theme

from someip_core import (
    ReplayConfig, ReplayController, SomeipUnavailable, active_table, export_service_table,
    set_table,
)
from someip_core.models import summarize

from .panel_config import ConfigPanelMixin
from .panel_control import ControlPanelMixin

_REFRESH_MS = 800


class SomeipReplayWindow(ConfigPanelMixin, ControlPanelMixin):
    """SOME/IP 回放与发送窗口。"""

    def __init__(self, master: tk.Misc, selected_file=None) -> None:
        self.window = tk.Toplevel(master)
        self.window.title("SOME/IP 回放（arhud 服务端）")
        self.window.geometry("1120x780")
        self.window.minsize(980, 640)
        self.selected_file = selected_file

        self.config = ReplayConfig.load().normalized()
        # 服务表代（old / bplus）需在构建界面之前生效，事件树与默认配置都依赖它
        set_table(self.config.service_table)
        self.controller = ReplayController(on_log=self.log)
        self._refresh_job = None
        self._closing = False
        self._unavailable_notified = False      # "库不可用"弹窗只提示一次（其余仅记日志）

        self._build_toolbar()
        self._build_body()
        self._start_refresh()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.log("SOME/IP 回放窗口已打开")
        self.log(f"服务定义：{summarize()}")
        self._apply_library_state()

    # ---------------------------------------------------------------- 布局
    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.window)
        bar.pack(side="top", fill="x", padx=6, pady=(6, 2))

        self.btn_open = ttk.Button(bar, text="打开服务", width=10, command=self.on_open)
        self.btn_open.pack(side="left")
        self.btn_start = ttk.Button(bar, text="启动服务", width=10, command=self.on_start)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(bar, text="停止服务", width=10, command=self.on_stop)
        self.btn_stop.pack(side="left", padx=4)
        self.btn_close = ttk.Button(bar, text="关闭服务", width=10, command=self.on_close_session)
        self.btn_close.pack(side="left", padx=4)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)

        self.btn_recheck = ttk.Button(bar, text="重新检测库", width=11,
                                      command=self.on_recheck_library)
        self.btn_recheck.pack(side="left")
        ttk.Button(bar, text="导出服务表", width=11,
                   command=self.on_export_table).pack(side="left", padx=4)

        ttk.Button(bar, text="保存配置", width=9,
                   command=self.on_save_config).pack(side="right")

        self.lbl_status = ttk.Label(bar, text="", foreground=Theme.PRIMARY)
        self.lbl_status.pack(side="right", padx=10)

    def _build_body(self) -> None:
        body = ttk.Frame(self.window)
        body.pack(side="top", fill="both", expand=True)

        left = ttk.Frame(body, width=470)
        left.pack(side="left", fill="both", expand=True, padx=(6, 3))
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(3, 6))

        self._build_config_panel(left)          # ①②
        self._build_control_panel(right)        # ③④⑤

    # ---------------------------------------------------------------- 日志
    def log(self, msg: str) -> None:
        """向日志区追加一行（带时间戳）。

        线程安全：Tk 只允许在创建它的线程里操作控件 —— 因此
          · 主线程调用：直接写入（界面立刻可见，也便于自动化测试断言）
          · 工作线程调用（如 C++ 库回调）：用 after(0) 投递到主线程
        """
        import datetime
        import threading
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {msg}\n"

        def append() -> None:
            if self._closing or not self.window.winfo_exists():
                return
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        if threading.current_thread() is threading.main_thread():
            try:
                append()
            except tk.TclError:
                pass
            return
        try:
            self.window.after(0, append)
        except tk.TclError:
            pass

    # ---------------------------------------------------------------- 库状态
    def _apply_library_state(self) -> None:
        """按库可用性启用/禁用动作按钮，并在日志里给出提示。"""
        ok = is_library_available()
        for btn in (self.btn_open, self.btn_start, self.btn_stop, self.btn_close,
                    self.btn_replay_start, self.btn_replay_stop, self.btn_send):
            btn.configure(state="normal" if ok else "disabled")
        self.lbl_status.configure(
            text=("SOME/IP 库就绪" if ok else "SOME/IP 库不可用（动作已置灰）"),
            foreground=Theme.SUCCESS if ok else Theme.DANGER)
        if not ok:
            self.log(describe_library_status())

    def on_recheck_library(self) -> None:
        self.log("重新检测 SOME/IP 库…")
        self._apply_library_state()

    def on_export_table(self) -> None:
        try:
            path = export_service_table()
            self.log(f"服务/事件表已导出：{path}")
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.window)

    # ---------------------------------------------------------------- 服务动作
    def on_open(self) -> None:
        """打开服务端实例（创建 + 注册服务/事件）。"""
        try:
            self._sync_config_from_ui()
            self.controller.open(self.config.unicast or None,
                                 self.config.config_path or None)
            only = None
            if self.config.selected:
                n_svc, n_evt = self.controller.register(selected_services=self.config.selected)
                self.log(f"按勾选注册：{n_svc} 服务 / {n_evt} 事件")
            else:
                n_svc, n_evt = self.controller.register(only)
                self.log(f"注册全部：{n_svc} 服务 / {n_evt} 事件")
            if self.var_auto_start.get():
                self.on_start()
        except SomeipUnavailable as exc:
            self._handle_unavailable(exc)
        except Exception as exc:                              # noqa: BLE001
            self._handle_error("打开服务失败", exc)

    def on_start(self) -> None:
        try:
            self.controller.start()
        except SomeipUnavailable as exc:
            self._handle_unavailable(exc)
        except Exception as exc:                              # noqa: BLE001
            self._handle_error("启动服务失败", exc)

    def on_stop(self) -> None:
        try:
            self.controller.stop()
        except Exception as exc:                              # noqa: BLE001
            self._handle_error("停止服务失败", exc)

    def on_close_session(self) -> None:
        try:
            self.controller.close()
        except Exception as exc:                              # noqa: BLE001
            self._handle_error("关闭服务失败", exc)

    # ---------------------------------------------------------------- 回放/发送
    def on_replay_start(self) -> None:
        try:
            self._sync_config_from_ui()
            if not self.controller.state.opened:
                self.log("尚未打开服务，自动执行“打开服务 + 启动服务”")
                self.on_open()
            if not self.controller.state.started:
                self.on_start()
            self.controller.play_pcap(self.config.pcap_path, self.config.loop,
                                      self.config.interval_ms)
        except SomeipUnavailable as exc:
            self._handle_unavailable(exc)
        except FileNotFoundError as exc:
            messagebox.showwarning("未找到 pcap", str(exc), parent=self.window)
            self.log(str(exc))
        except Exception as exc:                              # noqa: BLE001
            self._handle_error("开始回放失败", exc)

    def on_replay_stop(self) -> None:
        try:
            self.controller.stop_replay()
        except Exception as exc:                              # noqa: BLE001
            self._handle_error("停止回放失败", exc)

    def on_send_struct(self) -> None:
        """把界面字段交给控制器序列化并发送。"""
        try:
            fields = self.field_table.values()
        except ValueError as exc:
            messagebox.showwarning("字段值不合法", str(exc), parent=self.window)
            return
        try:
            if not self.controller.state.opened:
                self.on_open()
            if not self.controller.state.started:
                self.on_start()
            self.controller.send_struct(self.var_kind.get(), **fields)
        except SomeipUnavailable as exc:
            self._handle_unavailable(exc)
        except Exception as exc:                              # noqa: BLE001
            self._handle_error("发送失败", exc)

    # ---------------------------------------------------------------- 配置/状态
    def _sync_config_from_ui(self) -> None:
        """界面 → 配置对象（保存与执行都用同一份）。"""
        self.config.unicast = self.var_unicast.get().strip()
        self.config.network = self.var_network.get().strip() or "arhud01"
        self.config.config_path = self.var_config_path.get().strip()
        self.config.pcap_path = self.var_pcap.get().strip()
        self.config.loop = bool(self.var_loop.get())
        self.config.auto_start = bool(self.var_auto_start.get())
        self.config.last_event_kind = self.var_kind.get()
        self.config.service_table = active_table()
        try:
            self.config.interval_ms = int(self.var_interval.get() or 0)
        except ValueError:
            self.config.interval_ms = 0
        self.config.normalized()

    def on_save_config(self) -> None:
        try:
            self._sync_config_from_ui()
            path = self.config.save()
            self.log(f"配置已保存：{path}")
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.window)

    def _start_refresh(self) -> None:
        """定时刷新：已发送条数 + 状态栏。"""
        if self._closing:
            return
        try:
            sent = self.controller.refresh_sent()
            self.lbl_replay_stat.configure(text=f"已发送 {sent} 条")
            self.lbl_status.configure(text=self.controller.summary(),
                                      foreground=Theme.SUCCESS
                                      if self.controller.state.library_ok else Theme.DANGER)
        except Exception:                                     # noqa: BLE001
            pass
        self._refresh_job = self.window.after(_REFRESH_MS, self._start_refresh)

    # ---------------------------------------------------------------- 异常提示
    def _handle_unavailable(self, exc: Exception) -> None:
        """库不可用：日志必记；弹窗只提示一次（避免连续点击时反复弹窗阻塞操作）。"""
        self.log(f"库不可用：{exc}")
        if not self._unavailable_notified:
            self._unavailable_notified = True
            messagebox.showwarning("SOME/IP 库不可用", str(exc), parent=self.window)
        self._apply_library_state()

    def _handle_error(self, title: str, exc: Exception) -> None:
        self.log(f"{title}：{exc}")
        messagebox.showerror(title, str(exc), parent=self.window)

    # ---------------------------------------------------------------- 关闭
    def on_closing(self) -> None:
        """关闭窗口：先停回放/服务，再销毁实例并保存配置。"""
        self._closing = True
        if self._refresh_job:
            try:
                self.window.after_cancel(self._refresh_job)
            except tk.TclError:
                pass
            self._refresh_job = None
        try:
            self._sync_config_from_ui()
            self.config.save()
        except Exception:                                     # noqa: BLE001
            pass
        try:
            self.controller.close()
        except Exception:                                     # noqa: BLE001
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass
