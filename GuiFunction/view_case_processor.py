import os
import platform
import subprocess
import tkinter.messagebox as messagebox
import shutil
import threading  # 新增：用于异步执行

# 模块功能：查看对应的测试用例解析出来的日志文件

class LogViewer:
    def __init__(self, selected_file, test_case_folder="TestcaseCollection"):
        self.selected_file = selected_file
        self.test_case_folder = test_case_folder

    def view_log(self):
        selected = self.selected_file.get()
        if not selected or selected == "无文件":
            messagebox.showwarning("警告", "请先选择一个文件")
            return

        # 提取文件名 base（如：001.xlsx → 001）
        base_name = os.path.splitext(selected)[0]  # 去掉 .xlsx

        # 构造日志文件名：base_name + _data.log
        log_filename = f"{base_name}_data.log"
        log_path = os.path.join(self.test_case_folder, log_filename)

        if not os.path.exists(log_path):
            messagebox.showerror("错误", f"日志文件不存在：\n{log_path}")
            return

        # 在新线程中打开日志文件，避免阻塞 GUI 主线程
        thread = threading.Thread(target=self._open_log_in_thread, args=(log_path,), daemon=True)
        thread.start()

    def _open_log_in_thread(self, log_path):
        """跨平台打开日志文件（编辑器探测 → 系统默认程序回退）"""
        try:
            # Windows: notepad++/notepad ；Ubuntu: gedit/kate/xdg-open ；macOS: 交给 open
            from hudcore.platform.executables import open_in_text_editor
            if not open_in_text_editor(log_path):
                self._show_error(f"无法打开日志文件：{log_path}\n"
                                 f"Ubuntu 可安装编辑器：sudo apt install -y gedit")
        except Exception as e:
            self._show_error(f"无法打开日志文件：\n{e}")

    def _show_error(self, message):
        # 使用 after 投递到主线程执行 GUI 操作
        self.selected_file.master.after(0, lambda: messagebox.showerror("错误", message))
