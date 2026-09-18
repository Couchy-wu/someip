# -*- coding: utf-8 -*-
"""
HudAutoTest 主程序入口
======================
GUI 主窗口：测试用例管理 / CAN 测试 / 图像视频处理 / 工具入口。

重构说明（v2）：
  · 原全局脚本改为 MainWindow 类，UI 构建拆分为独立方法，便于维护与测试；
  · 平台相关（字体、日志重定向）走 hudcore，Windows / Ubuntu 22.04 通用；
  · 启动时打印平台自检信息（字体、驱动库状态），便于现场排障。

运行：
    python main.py
"""
from __future__ import annotations

import queue  # noqa: F401  (保持向后兼容：原 main.py 曾导出 queue)
import sys
import tkinter as tk
from tkinter import font as tkfont  # noqa: F401  (兼容旧引用)
from tkinter import ttk

import gui_handlers.image_sequence_player  # noqa: F401
import gui_handlers.signal_matrix_to_csv  # noqa: F401
import gui_handlers.can_data_generator  # noqa: F401
from gui_handlers.testcase_menu import FileUpdater
from gui_handlers.testcase_upload import handle_file_upload
from gui_handlers.testcase_delete import delete_test_case
from gui_handlers.testcase_open_table import ViewCaseHandler
from gui_handlers.testcase_view_log import LogViewer
from gui_handlers.image_open import ImageHandler
from gui_handlers.video_extract_frames import VideoProcessor
from can_gui.can_send_receive_gui import CANFDGUI

from hudcore.platform import describe_platform, paths
from hudcore.platform.executables import get_ffmpeg, get_office_app, get_text_editor
from hudcore.ui import TextRedirector, Theme

# 兼容别名：原 main.py 在此定义了 TextRedirector，保留导入路径
__all__ = ["MainWindow", "TextRedirector", "main"]


class MainWindow:
    """HudAutoTest 主窗口"""

    WINDOW_TITLE = "主窗口"
    WINDOW_GEOMETRY = "1300x600"
    GRID_ROWS = 5  # 参与拉伸的行数（与原实现一致）

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(self.WINDOW_TITLE)
        self.root.geometry(self.WINDOW_GEOMETRY)

        self._log_redirector = None
        self._can_window = None
        self._time_after_id = None

        self._init_handlers()
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

    # ------------------------------------------------------------ 日志面板
    def _build_log_panel(self) -> None:
        """右侧日志面板：时间标签 + 文本框 + 滚动条"""
        root = self.root
        self.log_main_frame = tk.Frame(root)
        self.log_main_frame.grid(row=0, column=5, rowspan=self.GRID_ROWS,
                                 padx=10, pady=10, sticky="nsew")
        self.log_main_frame.grid_rowconfigure(1, weight=1)
        self.log_main_frame.grid_columnconfigure(0, weight=1)

        self.time_label = tk.Label(
            self.log_main_frame, text="", anchor="w", height=1,
            **{k: v for k, v in Theme.label_style(bold=True).items() if k != "anchor"})
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
        for i in range(self.GRID_ROWS):
            self.root.grid_rowconfigure(i, weight=1)
        self.root.grid_columnconfigure(self.GRID_ROWS, weight=1)

    # ---------------------------------------------------------------- 按钮
    def _build_buttons(self) -> None:
        """构建主界面按钮（行/列坐标与原实现保持一致）"""
        root = self.root

        # 第 0 行：测试用例管理
        self.upload_button = tk.Button(root, text="上传测试用例",
                                       command=handle_file_upload,
                                       **Theme.primary_button())
        self.upload_button.grid(row=0, column=0, padx=20, pady=20)

        self.delete_button = tk.Button(root, text="删除测试用例",
                                       command=delete_test_case,
                                       **Theme.primary_button())
        self.delete_button.grid(row=0, column=1, padx=20, pady=20)

        self.file_menu = ttk.OptionMenu(root, self.selected_file, *[])
        self.file_menu.grid(row=0, column=2, padx=20, pady=20)
        self.testcase_menu.initialize_menu(self.selected_file, self.file_menu)

        # 上传/删除按钮改为走 FileUpdater（保持原行为）
        self.upload_button.config(
            command=lambda: self.testcase_menu.on_upload(self.selected_file, self.file_menu))
        self.delete_button.config(
            command=lambda: self.testcase_menu.on_delete(self.selected_file, self.file_menu))

        self.view_button = tk.Button(root, text="查看用例",
                                     command=self.testcase_open_table.open_selected_file,
                                     **Theme.primary_button())
        self.view_button.grid(row=0, column=3, padx=20, pady=20)

        self.inspect_button = tk.Button(root, text="查看解析",
                                        command=self.log_viewer.view_log,
                                        **Theme.primary_button())
        self.inspect_button.grid(row=0, column=4, padx=20, pady=20)

        # 第 1 行：工具类
        self.convert_matrix_button = tk.Button(root, text="转换信号矩阵",
                                               command=self.open_matrix_converter,
                                               **Theme.success_button())
        self.convert_matrix_button.grid(row=1, column=0, padx=20, pady=20)

        self.hex_button = tk.Button(root, text="can数据生成器",
                                    command=lambda: gui_handlers.can_data_generator.open_binhex_converter(root),
                                    **Theme.success_button())
        self.hex_button.grid(row=1, column=1, padx=20, pady=20)

        self.can_control_button = tk.Button(root, text="can测试",
                                            command=self.open_can_gui,
                                            **Theme.success_button())
        self.can_control_button.grid(row=1, column=2, padx=20, pady=20)

        # 第 2 行：图像/视频类
        self.image_button = tk.Button(root, text="打开图片",
                                      command=self.image_open.open_image,
                                      **Theme.danger_button())
        self.image_button.grid(row=2, column=0, padx=20, pady=20)

        self.read_video_button = tk.Button(root, text="提取视频帧",
                                           command=self.video_extract_frames.process_video,
                                           **Theme.danger_button())
        self.read_video_button.grid(row=2, column=1, padx=20, pady=20)

        self.image_video_button = tk.Button(root, text="播放图片视频",
                                            command=gui_handlers.image_sequence_player.play_image_sequence,
                                            **Theme.danger_button())
        self.image_video_button.grid(row=2, column=2, padx=20, pady=20)

    # ------------------------------------------------------------ 子窗口
    def open_matrix_converter(self) -> None:
        """打开"信号矩阵 转 CSV 工具"窗口"""
        win = tk.Toplevel(self.root)
        win.title("信号矩阵 转 CSV 工具")
        win.geometry("500x200")
        win.transient(self.root)
        win.grab_set()
        win.focus_force()
        gui_handlers.signal_matrix_to_csv.XlsmToCsvConverter(win, skip_first_row=False)

    def open_can_gui(self) -> None:
        """打开 CAN 信号自动收发子窗口"""
        if self._can_window is not None:
            try:
                if self._can_window.winfo_exists():
                    self._can_window.focus()
                    return
            except tk.TclError:
                self._can_window = None

        self.can_control_button.config(state=tk.DISABLED)

        win = tk.Toplevel(self.root)
        win.title("CAN信号自动收发程序")
        win.geometry("800x600")
        win.can_gui = CANFDGUI(win, selected_file=self.selected_file)
        win.protocol("WM_DELETE_WINDOW", self._on_can_window_close)
        self._can_window = win

    def _on_can_window_close(self) -> None:
        """CAN 子窗口关闭回调：交给 GUI 自身清理逻辑"""
        win = self._can_window
        if not win:
            return
        gui = getattr(win, "can_gui", None)
        if gui and hasattr(gui, "on_closing"):
            gui.on_closing()
            if not win.winfo_exists():
                self._can_window = None
                self.can_control_button.config(state=tk.NORMAL)
        else:
            win.destroy()
            self._can_window = None
            self.can_control_button.config(state=tk.NORMAL)

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
