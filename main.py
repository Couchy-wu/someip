# -*- coding: utf-8 -*-
"""
HudAutoTest 主程序入口
======================
GUI 主窗口：测试用例管理 / CAN 测试 / SOME/IP 回放 / 图像视频处理 / Di 用例执行。

界面结构（v3 重构：左侧功能区**分组** + 右侧日志面板）：

    ┌ 左列：功能区（SectionStack 自动发行号）──────────────┐ ┌ 右列：日志面板 ─┐
    │ ① 测试用例管理   上传 / 删除 / 查看用例 / 查看解析     │ │ 当前时间        │
    │     当前用例 ▾（ttk.OptionMenu，选择"当前用例"）      │ │ 日志文本框      │
    │ ② 数据与通信工具 转换信号矩阵 / can数据生成器 /        │ │ + 滚动条        │
    │                 can测试 / SOME/IP 回放              │ │                 │
    │ ③ 图像与视频     打开图片 / 提取视频帧 / 播放图片视频   │ │                 │
    │ ④ 测试用例执行   Di 测试用例                        │ │                 │
    └────────────────────────────────────────────────────┘ └─────────────────┘

本次重构解决的三个问题：
  1. **布局**：原来 13 个按钮手写 ``grid`` 到 row 0~2 / column 0~4（``GRID_ROWS = 5``
     里还有 2 行是空的却照样参与 weight 拉伸），语义上看不出"哪几个按钮是一类"。
     现在左侧用 :class:`~hudcore.ui.action_bar.SectionStack` 自上而下放带标题的区块、
     区块内用 :class:`~hudcore.ui.action_bar.ActionBar` 排按钮（超出自动换行），
     右列只放日志面板 —— 全窗没有任何手写 ``row=``，也就不会出现两个控件占同一格
     （用 ``hudcore.ui.layout.audit_widget_tree()`` 可断言为零冲突）。
  2. **子窗口逻辑**：三个子窗口（CAN 测试 / SOME/IP 回放 / Di 测试用例）原来各写了一份
     "单例 + 按钮置灰/恢复 + 关闭回调"，写法还不一致（有的判断 ``winfo_exists``、
     有的把清理写在窗口自身、Di 的清理写在 main 里），于是会出现"窗口已关但按钮还是灰的"。
     现在收敛成一张声明表 :class:`_WindowSpec` + :meth:`MainWindow._open_singleton` /
     :meth:`MainWindow._close_singleton`：已打开则聚焦、打开时置灰、关闭（含
     ``WM_DELETE_WINDOW`` 与用户直接 ``destroy()``）后恢复。
  3. **样式**：字体/配色一律走 :class:`~hudcore.ui.theme.Theme`，不再硬编码字体名与颜色；
     按钮配色按语义分组（用例管理=primary、数据通信=success、图像视频=danger、Di=success）。

运行：
    python main.py
"""
from __future__ import annotations

import queue  # noqa: F401  (保持向后兼容：原 main.py 曾导出 queue)
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont  # noqa: F401  (兼容旧引用)
from tkinter import ttk
from typing import Callable, Dict, Optional

import gui_handlers.image_sequence_player  # noqa: F401
import gui_handlers.signal_matrix_to_csv  # noqa: F401
import gui_handlers.can_data_generator  # noqa: F401
from gui_handlers.testcase_menu import FileUpdater
from gui_handlers.testcase_open_table import ViewCaseHandler
from gui_handlers.testcase_view_log import LogViewer
from gui_handlers.image_open import ImageHandler
from gui_handlers.video_extract_frames import VideoProcessor
from can_gui.can_send_receive_gui import CANFDGUI

import someip_gui
import gui_handlers.di_case_window
from hudcore.platform import describe_platform, paths
from hudcore.platform.executables import get_ffmpeg, get_office_app, get_text_editor
from hudcore.ui import ActionBar, ButtonGroup, SectionStack, TextRedirector, Theme, UiState
from hudcore.ui.state import Rule

# 兼容别名：原 main.py 在此定义了 TextRedirector，保留导入路径
__all__ = ["MainWindow", "TextRedirector", "main"]


# ---------------------------------------------------------------- 小工具
def _window_alive(widget) -> bool:
    """控件/窗口是否仍然存在（已销毁或为 ``None`` 都算"不存在"）。"""
    try:
        return bool(widget.winfo_exists())
    except Exception:                                # noqa: BLE001 - TclError/AttributeError
        return False


def _focus_window(win) -> None:
    """把已打开的子窗口带到前台（最小化/被遮挡时也能回到用户面前）。"""
    for action in ("deiconify", "lift", "focus_force"):
        try:
            getattr(win, action)()
        except Exception:                            # noqa: BLE001 - 窗口已销毁
            pass


def _enable_when_window_closed(flag: str) -> Rule:
    """规则工厂：该子窗口**没打开**时按钮可用（打开期间置灰，避免重复开窗）。"""
    return lambda state: not state.flag(flag)


@dataclass(frozen=True)
class _WindowSpec:
    """一个"单例子窗口"的声明（`_open_singleton` / `_close_singleton` 的数据来源）。

    :param kind: 标识（``"can"`` / ``"someip"`` / ``"di"``），只用于排障与日志
    :param window_attr: 对外可见的窗口属性名（``"_can_window"`` 等，保持历史名称）
    :param button_attr: 入口按钮属性名（由规则表统一置灰/恢复）
    :param flag: :class:`UiState` 里代表"该窗口已打开"的标志名
    :param opener: 建窗函数（返回 Toplevel）
    :param cleanup: 关闭前的清理（例：Di 窗口先 ``di_app.stop()`` 再 destroy）
    :param force_destroy: 清理后窗口仍存活时，是否由主窗口强制 ``destroy()``。
        CAN 界面在"设备未关闭"时会弹提示并**拒绝退出**，此时必须保持原样
        （既不拆窗口也不恢复按钮），故置 False；另两个窗口的清理函数内部已 destroy，
        True 只作兜底。
    """

    kind: str
    window_attr: str
    button_attr: str
    flag: str
    opener: Callable[[], tk.Toplevel]
    cleanup: Optional[Callable[[tk.Toplevel], None]] = None
    force_destroy: bool = True


class MainWindow:
    """HudAutoTest 主窗口"""

    WINDOW_TITLE = "主窗口"
    WINDOW_GEOMETRY = "1300x600"

    #: 列分工：0 = 左侧功能区（可拉伸），1 = 右侧日志面板（固定最小宽度）
    LEFT_COLUMN = 0
    LOG_COLUMN = 1
    LOG_MIN_WIDTH = 340

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(self.WINDOW_TITLE)
        self.root.geometry(self.WINDOW_GEOMETRY)

        self._log_redirector = None
        self._can_window = None
        self._someip_window = None
        self._di_window = None
        self._time_after_id = None

        # 界面状态源 + 规则表（按钮可用性的唯一决定者，见 hudcore.ui.state）
        self._ui_state = UiState()
        self._buttons = ButtonGroup("main_window")
        self._windows: Dict[str, _WindowSpec] = {}

        self._init_handlers()
        self._init_window_specs()
        self._build_log_panel()
        self._redirect_stdout()
        self._start_clock()
        self._build_buttons()
        self._configure_grid()
        self._bind_close()

        self._print_platform_info()

    # ------------------------------------------------------------------ 状态
    def _init_handlers(self) -> None:
        """初始化各功能处理器（原全局实例）"""
        self.selected_file = tk.StringVar()
        self.testcase_menu = FileUpdater()
        self.testcase_open_table = ViewCaseHandler(self.selected_file)
        self.log_viewer = LogViewer(self.selected_file)
        self.image_open = ImageHandler(self.root)
        self.video_extract_frames = VideoProcessor(self.root)  # 传入主窗口

    def _init_window_specs(self) -> None:
        """登记三个单例子窗口：``{kind: _WindowSpec}``（三个入口共用一套开关逻辑）。"""
        self._windows = {
            "can": _WindowSpec(
                kind="can",
                window_attr="_can_window",
                button_attr="can_control_button",
                flag="can_window_open",
                opener=self._create_can_window,
                cleanup=self._cleanup_can_window,
                force_destroy=False,     # 设备未关闭时 CAN 界面会拒绝退出（保持原行为）
            ),
            "someip": _WindowSpec(
                kind="someip",
                window_attr="_someip_window",
                button_attr="someip_button",
                flag="someip_window_open",
                opener=self._create_someip_window,
                cleanup=self._cleanup_someip_window,
            ),
            "di": _WindowSpec(
                kind="di",
                window_attr="_di_window",
                button_attr="di_case_button",
                flag="di_window_open",
                opener=self._create_di_window,
                cleanup=self._cleanup_di_window,
            ),
        }

    def _apply_ui_state(self) -> None:
        """按当前状态刷新所有已登记控件的可用性。"""
        self._buttons.apply(self._ui_state)

    def _set_flags(self, **flags: bool) -> None:
        """更新界面状态源并刷新控件（改动按钮可用性的**唯一**入口）。"""
        self._ui_state = self._ui_state.with_flags(**flags)
        self._apply_ui_state()

    # ------------------------------------------------------------ 日志面板
    def _build_log_panel(self) -> None:
        """右侧日志面板：时间标签 + 文本框 + 滚动条（整块占右列，与左列不同 column）"""
        root = self.root
        self.log_main_frame = tk.Frame(root)
        self.log_main_frame.grid(row=0, column=self.LOG_COLUMN, sticky="nsew",
                                 padx=(4, 10), pady=10)
        self.log_main_frame.grid_rowconfigure(1, weight=1)
        self.log_main_frame.grid_columnconfigure(0, weight=1)

        self.time_label = tk.Label(self.log_main_frame, text="", **Theme.label_style(bold=True))
        self.time_label.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))

        log_frame = tk.Frame(self.log_main_frame)
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, **Theme.log_text_style())
        self.log_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.config(yscrollcommand=scrollbar.set)

    def _redirect_stdout(self) -> None:
        """把 stdout 重定向到日志文本框（线程安全）"""
        self._log_redirector = TextRedirector(self.log_text, self.root)
        sys.stdout = self._log_redirector

    # ---------------------------------------------------------------- 时钟
    def _start_clock(self) -> None:
        from datetime import datetime

        def tick():
            self.time_label.config(text=f"当前时间: {datetime.now().strftime('%H:%M:%S')}")
            self._time_after_id = self.root.after(1000, tick)

        tick()

    # ---------------------------------------------------------------- 布局
    def _configure_grid(self) -> None:
        """只给真正用到的行列配权重（原 ``GRID_ROWS = 5`` 有 2 行是空的却仍参与拉伸）。"""
        root = self.root
        root.grid_rowconfigure(0, weight=1)                        # 只有一行：左功能区 + 右日志
        root.grid_columnconfigure(self.LEFT_COLUMN, weight=1)      # 左列可拉伸
        root.grid_columnconfigure(self.LOG_COLUMN, weight=0,       # 右列日志面板宽度稳定
                                  minsize=self.LOG_MIN_WIDTH)

    # ---------------------------------------------------------------- 按钮
    def _build_buttons(self) -> None:
        """构建左侧功能区：四个带标题的区块 + 区块内声明式按钮条。

        行号由 :class:`SectionStack` / :class:`ActionBar` 自动分配，这里不出现手写
        ``row=``/``column=``，因此不可能与别的控件抢格子。
        """
        root = self.root

        self.left_frame = tk.Frame(root)
        self.left_frame.grid(row=0, column=self.LEFT_COLUMN, sticky="nsew",
                             padx=(8, 4), pady=8)
        self.left_frame.grid_columnconfigure(0, weight=1)

        stack = SectionStack(self.left_frame, column=0, padx=4, pady=4,
                             use_ttk=False, sticky="ew")

        self._build_testcase_section(stack)     # ① 测试用例管理
        self._build_tools_section(stack)        # ② 数据与通信工具
        self._build_media_section(stack)        # ③ 图像与视频
        self._build_execute_section(stack)      # ④ 测试用例执行

        # 末尾留一行空白填充：窗口变高时区块保持自上而下紧凑排列，多余高度落到最下面
        self.left_frame.grid_rowconfigure(stack.next_row, weight=1)

        self._apply_ui_state()                  # 建立按钮状态快照（规则表首轮生效）

    # ---------------- ① 测试用例管理 ----------------
    def _build_testcase_section(self, stack: SectionStack) -> None:
        """① 测试用例管理：上传 / 删除 / 查看用例 / 查看解析 + 用例下拉框。

        按钮配色 = primary（蓝，用例读写是主操作）。
        """
        section = stack.section("① 测试用例管理")

        # 用例下拉框放区块第二行：仍交给 ActionBar 排布（不手写 row/column）
        picker = ActionBar(section, row=1, column=0, columns=4, group=self._buttons)
        picker.add_widget("case_label",
                          tk.Label(section, text="当前用例：", **Theme.field_label()))
        self.file_menu = ttk.OptionMenu(section, self.selected_file, *[])
        picker.add_widget("file_menu", self.file_menu)
        # 下拉框内容仍由 FileUpdater 维护（绑定行为不变）
        self.testcase_menu.initialize_menu(self.selected_file, self.file_menu)

        bar = ActionBar(section, row=0, column=0, columns=4, group=self._buttons)
        self.upload_button = bar.add(
            "upload", "上传测试用例",
            lambda: self.testcase_menu.on_upload(self.selected_file, self.file_menu),
            kind="primary")
        self.delete_button = bar.add(
            "delete", "删除测试用例",
            lambda: self.testcase_menu.on_delete(self.selected_file, self.file_menu),
            kind="primary")
        self.view_button = bar.add("view", "查看用例",
                                   self.testcase_open_table.open_selected_file,
                                   kind="primary")
        self.inspect_button = bar.add("inspect", "查看解析", self.log_viewer.view_log,
                                     kind="primary")

        hint = ActionBar(section, row=2, column=0, columns=1, group=self._buttons)
        hint.add_widget("case_hint", tk.Label(
            section, text="下拉框选择「当前用例」；上传/删除后列表会自动刷新。",
            **Theme.hint_label()))

    # ---------------- ② 数据与通信工具 ----------------
    def _build_tools_section(self, stack: SectionStack) -> None:
        """② 数据与通信工具：转换信号矩阵 / can数据生成器 / can测试 / SOME/IP 回放。

        按钮配色 = success（绿，数据处理与通信类工具）；
        can测试、SOME/IP 回放是**单例窗口**，窗口打开期间由规则表置灰。
        """
        section = stack.section("② 数据与通信工具")
        bar = ActionBar(section, row=0, column=0, columns=4, group=self._buttons)

        self.convert_matrix_button = bar.add("convert_matrix", "转换信号矩阵",
                                             self.open_matrix_converter, kind="success")
        self.hex_button = bar.add(
            "hex", "can数据生成器",
            lambda: gui_handlers.can_data_generator.open_binhex_converter(self.root),
            kind="success")
        self.can_control_button = bar.add(
            "can_gui", "can测试", self.open_can_gui, kind="success",
            enabled_when=_enable_when_window_closed("can_window_open"))
        self.someip_button = bar.add(
            "someip", "SOME/IP 回放", self.open_someip_replay, kind="success",
            enabled_when=_enable_when_window_closed("someip_window_open"))

    # ---------------- ③ 图像与视频 ----------------
    def _build_media_section(self, stack: SectionStack) -> None:
        """③ 图像与视频：打开图片 / 提取视频帧 / 播放图片视频。

        按钮配色 = danger（红，沿用原实现里图像类按钮的语义色）。
        """
        section = stack.section("③ 图像与视频")
        bar = ActionBar(section, row=0, column=0, columns=3, group=self._buttons)

        self.image_button = bar.add("image", "打开图片", self.image_open.open_image,
                                    kind="danger")
        self.read_video_button = bar.add("read_video", "提取视频帧",
                                         self.video_extract_frames.process_video,
                                         kind="danger")
        self.image_video_button = bar.add(
            "image_video", "播放图片视频",
            gui_handlers.image_sequence_player.play_image_sequence, kind="danger")

    # ---------------- ④ 测试用例执行 ----------------
    def _build_execute_section(self, stack: SectionStack) -> None:
        """④ 测试用例执行：Di 测试用例（新格式：CAN + SOME/IP + 标贴校验）。

        按钮配色 = success（绿，与"执行测试"的成功语义一致）；
        Di 窗口也是单例窗口，打开期间置灰。
        """
        section = stack.section("④ 测试用例执行")
        bar = ActionBar(section, row=0, column=0, columns=4, group=self._buttons)

        self.di_case_button = bar.add(
            "di_case", "Di 测试用例", self.open_di_cases, kind="success",
            enabled_when=_enable_when_window_closed("di_window_open"))

    def open_matrix_converter(self) -> None:
        """打开"信号矩阵 转 CSV 工具"窗口（一次性工具窗，可同时开多个）"""
        win = tk.Toplevel(self.root)
        win.title("信号矩阵 转 CSV 工具")
        win.geometry("500x200")
        win.transient(self.root)
        win.grab_set()
        win.focus_force()
        gui_handlers.signal_matrix_to_csv.XlsmToCsvConverter(win, skip_first_row=False)

    # ------------------------------------------------------------ 单例子窗口
    def _open_singleton(self, kind: str) -> Optional[tk.Toplevel]:
        """打开/聚焦单例子窗口（三个子窗口共用这一条实现）。

        行为约定：
          · 已打开 → 聚焦并直接返回（不会建出第二个窗口）；
          · 未打开 → 建窗、接上 ``WM_DELETE_WINDOW`` 与 ``<Destroy>`` 兜底，
            并把状态标志置 True（规则表据此把入口按钮置灰）；
          · 建窗失败（如依赖库缺失）→ 标志回滚，按钮立即恢复可点，
            绝不允许"按钮永久灰掉"。
        """
        spec = self._windows[kind]
        win = getattr(self, spec.window_attr, None)
        if win is not None:
            if _window_alive(win):
                _focus_window(win)
                return win
            self._forget_singleton(kind, win)        # 已被直接销毁：先收敛状态再重建

        self._set_flags(**{spec.flag: True})         # "窗口已打开" → 按钮置灰
        try:
            win = spec.opener()
        except Exception:
            self._set_flags(**{spec.flag: False})    # 开窗失败：按钮恢复
            raise

        setattr(self, spec.window_attr, win)
        if not _window_alive(win):                   # opener 返回 None / 窗口刚建就被销毁
            self._forget_singleton(kind, win)        # 收敛状态，绝不留"永久灰"的按钮
            raise RuntimeError(f"{kind}：子窗口创建失败（opener 返回 {win!r}）")
        try:
            win.protocol("WM_DELETE_WINDOW", lambda k=kind: self._close_singleton(k))
            # 兜底：用户/子窗口自身直接 destroy()（不走 WM_DELETE_WINDOW）时恢复按钮。
            # <Destroy> 会从子控件冒泡到顶层窗口的绑定上，故用 event.widget 过滤。
            win.bind("<Destroy>",
                     lambda event, k=kind: self._on_singleton_destroyed(k, event), add="+")
        except tk.TclError:
            pass                                     # 窗口刚建就被销毁：交给 <Destroy> 兜底
        return win

    def _close_singleton(self, kind: str) -> None:
        """关闭单例子窗口（三个 ``WM_DELETE_WINDOW`` 回调共用）：

        先做该窗口自己的清理（Di：``di_app.stop()`` → destroy；CAN/SOME/IP：各自的
        ``on_closing()``），再按需兜底 destroy，最后把按钮恢复。窗口仍在（如 CAN 因
        设备未关闭而拒绝退出）时状态保持"已打开"，与实际界面一致。
        """
        spec = self._windows[kind]
        win = getattr(self, spec.window_attr, None)
        try:
            if win is not None:
                if spec.cleanup is not None:
                    spec.cleanup(win)
                if spec.force_destroy and _window_alive(win):
                    win.destroy()
        except tk.TclError:
            pass                                     # 控件/窗口已销毁：按"已关闭"处理
        finally:
            if not _window_alive(win):
                self._forget_singleton(kind, win)

    def _forget_singleton(self, kind: str, win=None) -> None:
        """清空窗口属性并恢复入口按钮（``win`` 给定时只在"当前记录的仍是它"时才清）。"""
        spec = self._windows[kind]
        current = getattr(self, spec.window_attr, None)
        if win is not None and current is not None and current is not win:
            return                                   # 已换成新窗口：不要误伤
        setattr(self, spec.window_attr, None)
        self._set_flags(**{spec.flag: False})

    def _on_singleton_destroyed(self, kind: str, event=None) -> None:
        """``<Destroy>`` 兜底回调：窗口被直接销毁时把按钮恢复（幂等）。"""
        spec = self._windows[kind]
        win = getattr(self, spec.window_attr, None)
        if win is None:
            return
        if event is not None and getattr(event, "widget", None) is not win:
            return                                   # 子控件的 Destroy 事件，忽略
        self._forget_singleton(kind, win)

    # ---------------- 单例子窗口：建窗与清理 ----------------
    def _create_can_window(self) -> tk.Toplevel:
        win = tk.Toplevel(self.root)
        win.title("CAN信号自动收发程序")
        win.geometry("800x600")
        win.can_gui = CANFDGUI(win, selected_file=self.selected_file)
        return win

    @staticmethod
    def _cleanup_can_window(win) -> None:
        """交给 CAN 界面自身的清理逻辑（设备/相机/线程 + 销毁窗口）。"""
        gui = getattr(win, "can_gui", None)
        if gui is not None and hasattr(gui, "on_closing"):
            gui.on_closing()
        elif _window_alive(win):
            win.destroy()

    def _create_someip_window(self) -> tk.Toplevel:
        return someip_gui.open_replay_window(self.root, selected_file=self.selected_file)

    @staticmethod
    def _cleanup_someip_window(win) -> None:
        """交给 SOME/IP 窗口自身清理（停回放 → 停服务 → 销毁实例 → 保存配置）。"""
        app = getattr(win, "someip_app", None)
        if app is not None:
            app.on_closing()                         # 内含资源释放与窗口销毁
        elif _window_alive(win):
            win.destroy()

    def _create_di_window(self) -> tk.Toplevel:
        return gui_handlers.di_case_window.open_di_case_window(self.root)

    @staticmethod
    def _cleanup_di_window(win) -> None:
        """Di 窗口：先 ``di_app.stop()`` 停掉轮询，再由 ``_close_singleton`` destroy。"""
        app = getattr(win, "di_app", None)
        if app is not None:
            app.stop()

    # ------------------------------------------------------------ 对外入口
    def open_can_gui(self) -> Optional[tk.Toplevel]:
        """打开 CAN 信号自动收发子窗口（单例：已打开则聚焦，入口按钮置灰）"""
        return self._open_singleton("can")

    def _on_can_window_close(self) -> None:
        """CAN 子窗口关闭回调（统一走 `_close_singleton`）"""
        self._close_singleton("can")

    def open_someip_replay(self) -> Optional[tk.Toplevel]:
        """打开 SOME/IP 回放子窗口（单例；关闭时恢复按钮）"""
        return self._open_singleton("someip")

    def _on_someip_window_close(self) -> None:
        """SOME/IP 子窗口关闭回调（统一走 `_close_singleton`）"""
        self._close_singleton("someip")

    def open_di_cases(self) -> Optional[tk.Toplevel]:
        """打开 Di 测试用例窗口（单例；关闭时恢复按钮）"""
        return self._open_singleton("di")

    def _on_di_window_close(self) -> None:
        """Di 窗口关闭回调（统一走 `_close_singleton`；先 stop() 再 destroy）"""
        self._close_singleton("di")

    # ------------------------------------------------------------ 生命周期
    def _bind_close(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self) -> None:
        """窗口关闭清理"""
        if self._log_redirector is not None:
            self._log_redirector.stop_polling()
            if sys.stdout is self._log_redirector:
                sys.stdout = sys.__stdout__
        if self._time_after_id is not None:
            try:
                self.root.after_cancel(self._time_after_id)
            except tk.TclError:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        self.root.mainloop()

    # ------------------------------------------------------------ 自检信息
    def _print_platform_info(self) -> None:
        """打印平台自检（字体、外部程序、驱动库）——现场排障很有用"""
        print(f"[环境] {describe_platform()}")
        print(f"[环境] 项目根目录: {paths.project_root}")
        print(f"[环境] 界面字体: {Theme.font_name()}")
        for label, path in (("ffmpeg", get_ffmpeg()),
                            ("表格应用", get_office_app()),
                            ("文本编辑器", get_text_editor())):
            print(f"[环境] {label}: {path if path else '未找到（相关功能会回退/提示）'}")
        try:
            from hudcore.can import describe_library_status
            print("[环境] CAN 驱动库探测：")
            print(describe_library_status())
        except Exception as e:  # pragma: no cover
            print(f"[环境] CAN 驱动库探测失败: {e}")


def main() -> None:
    MainWindow().run()


if __name__ == "__main__":
    main()
