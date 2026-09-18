# -*- coding: utf-8 -*-
"""
hudcore.ui.text_redirector —— print 输出重定向到 Tk Text（线程安全）
====================================================================
从 main.py 抽取并通用化：任何线程的 print 都通过内部 queue 投递，
再由 Tk 主线程（root.after 轮询）写入 Text 控件，避免跨线程操作 UI。

用法：
    import sys
    from hudcore.ui import TextRedirector
    redirector = TextRedirector(log_text, root)
    sys.stdout = redirector
    ...
    redirector.stop_polling()     # 关闭窗口前调用
"""
from __future__ import annotations

import queue
from typing import Any

try:                      # tkinter 为可选依赖：无 GUI 环境（服务器/CI）也能导入本模块
    import tkinter as tk
except ImportError:       # pragma: no cover
    tk = None  # type: ignore


class TextRedirector:
    """把 print 输出安全转发到 Tkinter Text 小部件"""

    def __init__(self, widget: Any, root: Any, poll_interval: int = 50):
        """
        :param widget: tk.Text 实例
        :param root: 主窗口（tk.Tk / tk.Toplevel），用于 after 轮询
        :param poll_interval: 轮询间隔（毫秒）
        """
        if tk is None:
            raise RuntimeError("TextRedirector 需要 tkinter（Ubuntu: sudo apt install -y python3-tk）")
        self.widget = widget
        self.root = root
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._poll_interval = poll_interval
        self._after_id = None
        self._start_poll()

    # ---- 文件对象接口 ----
    def write(self, string: str) -> None:
        """任意线程调用：仅入队"""
        if string:
            self._queue.put(string)

    def flush(self) -> None:
        """兼容文件对象接口"""
        pass

    def isatty(self) -> bool:
        return False

    # ---- 内部：主线程轮询队列 ----
    def _start_poll(self) -> None:
        self._flush_queue()
        try:
            self._after_id = self.root.after(self._poll_interval, self._start_poll)
        except tk.TclError:
            # 窗口已销毁
            self._after_id = None

    def _flush_queue(self) -> None:
        try:
            while True:
                line = self._queue.get_nowait()
                self.widget.insert(tk.END, line)
                self.widget.see(tk.END)
        except queue.Empty:
            pass
        except tk.TclError:
            # 控件已销毁，丢弃剩余输出
            pass

    def stop_polling(self) -> None:
        """停止轮询（窗口关闭前调用，避免 after 回调报错）"""
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
