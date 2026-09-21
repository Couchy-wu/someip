# -*- coding: utf-8 -*-
"""someip_gui.replay_window —— SOME/IP 回放窗口（主类）

窗口布局（1120×780，左右两大分区 + ①~⑤ 编号区块）：

    ┌──────────────────────────────────────────────────────────────────────────────┐
    │ 工具栏（单行）：[打开服务][启动服务][停止服务][关闭服务] │ [重新检测库][导出服务表] │
    │                    状态：库就绪｜阶段：已启动｜…      [保存配置]                │
    ├───────────────────────────────┬──────────────────────────────────────────────┤
    │ ① 网络与 SD 配置               │ ③ pcap 回放控制                               │
    │ ② 服务 / 事件（勾选=注册）      │ ④ 单条发送（结构化字段）                       │
    │                               │ ⑤ 操作与报文日志                               │
    └───────────────────────────────┴──────────────────────────────────────────────┘

职责：
    · 组装布局（由 panel_config / panel_control 两个 Mixin 提供）
    · 持有 `ReplayController`，把界面动作翻译为控制器调用，并统一异常提示
    · **唯一的界面状态刷新入口** `_apply_ui_state()`：把 `controller.state` + 忙标志
      合成 `UiState`，交给规则表（`someip_gui.ui_rules.RULES`）统一刷新所有按钮，
      并合成状态栏文本；动作结束与定时刷新（800ms）都只调它。
      动作方法里不再出现任何 `btn.configure(state=...)`。
    · 关闭时安全释放：停回放 → 停服务 → 销毁实例 → 保存配置

库不可用时（例如 Windows 尚无 DLL）：窗口照常打开，状态栏**保持红字并附原因**
（不再被 `controller.summary()` 冲掉），动作按钮置灰，日志区给出修复提示；
用户可用"重新检测库"按钮重试（该按钮不随库不可用而置灰）。
"""
from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import messagebox, ttk

from hudcore.someip import describe_library_status, is_library_available
from hudcore.ui import Theme, UiState
from hudcore.ui.state import BUSY_NONE, ButtonGroup

from someip_core import (
    ReplayConfig, ReplayController, SomeipUnavailable, active_table, export_service_table,
    set_table,
)
from someip_core.models import summarize

from . import ui_rules as rules
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

        # ---- 界面状态：一个 ButtonGroup + 一个忙标志（busy 用 BUSY_* 常量）----
        # 所有按钮（工具栏 / 回放 / 发送）都登记进同一个组，可用性只由规则表决定。
        self.buttons = ButtonGroup("someip_replay")
        self._ui_busy = BUSY_NONE
        self._refresh_job = None
        self._closing = False
        self._unavailable_notified = False      # "库不可用"弹窗只提示一次（其余仅记日志）

        self._build_toolbar()
        self._build_body()
        self._start_refresh()                   # 立刻按状态刷新一次 + 排定 800ms 定时刷新

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.log("SOME/IP 回放窗口已打开")
        self.log(f"服务定义：{summarize()}")
        if not is_library_available():
            # 库不可用：日志区给出完整修复提示（状态栏只放一行原因）
            self.log(describe_library_status())
        self._apply_ui_state()

    # ---------------------------------------------------------------- 布局
    def _build_toolbar(self) -> None:
        """工具栏：**单行 pack 布局**（与界面优化前一致，用户明确要求回退）。

        摆放顺序（全部 ``pack``，因此工具栏内部不存在 grid 格子冲突）：
            左：打开服务 / 启动服务 / 停止服务 / 关闭服务 → 竖分隔线 → 重新检测库 / 导出服务表
            右：保存配置 、 状态栏

        与界面优化版的区别：不再用 :class:`ActionBar` 与 Theme 配色，按钮恢复为原生
        ``ttk.Button``；但**可用性仍然只由规则表决定** —— 每个按钮都登记进窗口的
        ``self.buttons``（``ButtonGroup``），刷新仍是 ``_apply_ui_state()`` 一个入口。
        """
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
        self.btn_export = ttk.Button(bar, text="导出服务表", width=11,
                                     command=self.on_export_table)
        self.btn_export.pack(side="left", padx=4)

        self.btn_save_config = ttk.Button(bar, text="保存配置", width=9,
                                          command=self.on_save_config)
        self.btn_save_config.pack(side="right")

        # 状态栏（与按钮同一行的右端）。单行工具栏里位置由 pack 固定，
        # 但状态栏文本（compose_status 合成，库不可用时更长）在 1120px 宽的窗口下
        # 会被裁掉一截 —— 这里只把 `anchor` 设为 "w"，保证**从头开始**显示
        # （先看到"库不可用 + 原因"这个结论；尾部重复的阶段/计数优先被裁掉）。
        # 位置、尺寸、pack 顺序都与界面优化前一致，完整提示始终在⑤日志区。
        self.lbl_status = ttk.Label(bar, text="", foreground=Theme.PRIMARY, anchor="w")
        self.lbl_status.pack(side="right", padx=10)

        # 全部按钮登记进同一个状态机（位置用 pack 固定，可用性仍由规则表统一决定）
        for key, widget in (
            (rules.KEY_OPEN, self.btn_open),
            (rules.KEY_START, self.btn_start),
            (rules.KEY_STOP, self.btn_stop),
            (rules.KEY_CLOSE, self.btn_close),
            (rules.KEY_RECHECK, self.btn_recheck),
            (rules.KEY_EXPORT, self.btn_export),
            (rules.KEY_SAVE_CONFIG, self.btn_save_config),
        ):
            self.buttons.add(key, widget, rules.RULES[key])

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

    # ---------------------------------------------------------------- 状态机
    def _ui_state(self) -> UiState:
        """把"控制器状态 + 忙标志 + 库可用性"合成一个 :class:`UiState` 快照。

        库可用性用本模块的 ``is_library_available``（而非 controller 里的缓存值），
        这样"重新检测库"后界面能立刻反映最新探测结果（测试也在此处打桩）。
        """
        st = self.controller.state
        return UiState(
            busy=self._ui_busy,
            library_ok=bool(is_library_available()),
            flags={"opened": st.opened, "started": st.started, "replaying": st.replaying},
        )

    def _apply_ui_state(self) -> None:
        """**唯一**的界面状态刷新入口：规则表刷按钮 + 合成状态栏。

        调用时机：窗口初始化、每个动作结束（``_busy`` 退出时）、定时刷新。
        动作方法里不再各自 ``btn.configure(state=...)``。
        """
        if self._closing:
            return
        try:
            state = self._ui_state()
            self.buttons.apply(state)                 # 规则表 → 所有按钮可用性
            self._set_status(state)
        except tk.TclError:                           # 窗口正在销毁
            pass

    def _set_status(self, state: UiState) -> None:
        """状态栏：一行"阶段 + 库状态 + 计数"；库不可用保持红字并附原因。"""
        st = self.controller.state
        reason = "" if state.library_ok else self._library_reason()
        self.lbl_status.configure(
            text=rules.compose_status(state, sent=st.replay_sent,
                                      services=st.registered_services,
                                      events=st.registered_events, reason=reason),
            foreground=Theme.SUCCESS if state.library_ok else Theme.DANGER)
        self.lbl_replay_stat.configure(text=f"已发送 {st.replay_sent} 条")

    def _library_reason(self) -> str:
        """库不可用的原因（一行；完整修复提示见日志区/`describe_library_status()`）。

        优先用真实探测结果（"已找到但加载失败"这类原因要如实显示）；
        若探测结果自相矛盾（例如测试里打桩了库可用性），退回稳定的修复提示首行。
        """
        try:
            text = describe_library_status()
        except Exception:                             # noqa: BLE001 - 提示本身失败不影响界面
            text = ""
        if not text or "就绪" in text:
            text = self.controller.library_hint()
        return rules.one_line_reason(text)

    @contextlib.contextmanager
    def _busy(self, flag: str):
        """把一次动作标记为"进行中"（busy 用 ``BUSY_*`` 常量），结束自动恢复并刷新界面。

        动作都是同步调用，busy 主要用于：(1) 规则表在动作期间禁用相关按钮，
        避免自动链路（如"开始回放"里自动开服务）被重复点击；(2) 状态栏显示当前步骤。
        嵌套调用（send → open → start）会记住并恢复外层的 busy。
        """
        previous = self._ui_busy
        self._ui_busy = flag
        self._apply_ui_state()
        try:
            yield
        finally:
            self._ui_busy = previous
            self._apply_ui_state()

    # ---------------------------------------------------------------- 兼容入口
    def _apply_library_state(self) -> None:
        """（兼容旧名字）按库可用性刷新界面 —— 等价于 :meth:`_apply_ui_state`。"""
        self._apply_ui_state()

    def on_recheck_library(self) -> None:
        with self._busy(rules.BUSY_BY_ACTION["recheck"]):
            self.log("重新检测 SOME/IP 库…")
            self.log(describe_library_status())

    def on_export_table(self) -> None:
        try:
            path = export_service_table()
            self.log(f"服务/事件表已导出：{path}")
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.window)

    # ---------------------------------------------------------------- 服务动作
    def on_open(self) -> None:
        """打开服务端实例（创建 + 注册服务/事件）。"""
        with self._busy(rules.BUSY_BY_ACTION["open"]):
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
        with self._busy(rules.BUSY_BY_ACTION["start"]):
            try:
                self.controller.start()
            except SomeipUnavailable as exc:
                self._handle_unavailable(exc)
            except Exception as exc:                              # noqa: BLE001
                self._handle_error("启动服务失败", exc)

    def on_stop(self) -> None:
        with self._busy(rules.BUSY_BY_ACTION["stop"]):
            try:
                self.controller.stop()
            except Exception as exc:                              # noqa: BLE001
                self._handle_error("停止服务失败", exc)

    def on_close_session(self) -> None:
        with self._busy(rules.BUSY_BY_ACTION["close"]):
            try:
                self.controller.close()
            except Exception as exc:                              # noqa: BLE001
                self._handle_error("关闭服务失败", exc)

    # ---------------------------------------------------------------- 回放/发送
    def on_replay_start(self) -> None:
        """开始回放（未打开/未启动时按既有便利行为自动先开服务）。"""
        with self._busy(rules.BUSY_BY_ACTION["replay"]):
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
        with self._busy(rules.BUSY_BY_ACTION["replay"]):
            try:
                self.controller.stop_replay()
            except Exception as exc:                              # noqa: BLE001
                self._handle_error("停止回放失败", exc)

    def on_send_struct(self) -> None:
        """把界面字段交给控制器序列化并发送（未打开时按既有便利行为自动先开服务）。"""
        try:
            fields = self.field_table.values()
        except ValueError as exc:
            messagebox.showwarning("字段值不合法", str(exc), parent=self.window)
            return
        with self._busy(rules.BUSY_BY_ACTION["send"]):
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

    def _tick(self) -> None:
        """定时刷新的一次"心跳"：读回放计数 → 统一刷新（按钮 + 状态栏）。

        状态栏文本在这里**重新合成**（而不是用裸 `controller.summary()` 覆盖），
        因此库不可用时的红字与原因不会被刷掉。
        """
        if self._closing:
            return
        try:
            self.controller.refresh_sent()
        except Exception:                                     # noqa: BLE001
            pass
        self._apply_ui_state()

    def _start_refresh(self) -> None:
        """启动 800ms 定时刷新（窗口关闭时会取消）。"""
        if self._closing:
            return
        self._tick()
        self._refresh_job = self.window.after(_REFRESH_MS, self._start_refresh)

    # ---------------------------------------------------------------- 异常提示
    def _handle_unavailable(self, exc: Exception) -> None:
        """库不可用：日志必记；弹窗只提示一次（避免连续点击时反复弹窗阻塞操作）。"""
        self.log(f"库不可用：{exc}")
        if not self._unavailable_notified:
            self._unavailable_notified = True
            messagebox.showwarning("SOME/IP 库不可用", str(exc), parent=self.window)
        self._apply_ui_state()

    def _handle_error(self, title: str, exc: Exception) -> None:
        self.log(f"{title}：{exc}")
        messagebox.showerror(title, str(exc), parent=self.window)

    # ---------------------------------------------------------------- 关闭
    def on_closing(self) -> None:
        """关闭窗口，固定顺序：**停回放 → 关服务 → 保存配置 → 销毁窗口**。

        `controller.close()` 内部先 `replay_stop` 再 `destroy`；每一步都各自兜异常，
        保证前一步失败不会挡住后面的清理与配置落盘。
        """
        self._closing = True
        if self._refresh_job:
            try:
                self.window.after_cancel(self._refresh_job)
            except tk.TclError:
                pass
            self._refresh_job = None
        try:
            self._sync_config_from_ui()
        except Exception:                                     # noqa: BLE001
            pass
        try:
            self.controller.close()                           # 停回放 → 销毁实例
        except Exception:                                     # noqa: BLE001
            pass
        try:
            self.config.save()
        except Exception:                                     # noqa: BLE001
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass
