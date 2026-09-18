import tkinter as tk
from tkinter import ttk

# 模块功能：进度条

class ProgressBar:
    def __init__(self, root):
        self.root = root
        self.progress_window = None
        self.progress_bar = None
        self.current_progress = 0

    def create_progress_bar(self, title, max_value):
        # 如果已有进度条窗口，先关闭
        self.close_progress_bar()
        
        self.progress_window = tk.Toplevel(self.root)
        self.progress_window.title(title)
        self.progress_window.geometry("300x100")
        self.progress_window.resizable(False, False)
        
        self.progress_bar = ttk.Progressbar(
            self.progress_window,
            orient="horizontal",
            length=250,
            mode="determinate",
            maximum=max_value
        )
        self.progress_bar.pack(pady=20)
        self.current_progress = 0
        self.progress_bar["value"] = 0

    def update_progress(self, value):
        if self.progress_window is None or not self.progress_window.winfo_exists():
            return
        self.current_progress = value
        self.progress_bar["value"] = self.current_progress
        self.progress_window.update_idletasks()

    def close_progress_bar(self):
        if self.progress_window and self.progress_window.winfo_exists():
            self.progress_window.destroy()
        self.progress_window = None

        self.progress_bar = None
        self.current_progress = 0