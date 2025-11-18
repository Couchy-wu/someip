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
        try:
            system = platform.system()
            if system == "Windows":
                # 方法1：尝试用记事本打开
                notepad_path = shutil.which("notepad")
                if notepad_path:
                    # 注意：使用 subprocess.Popen 而不是 run，避免等待
                    subprocess.Popen([notepad_path, log_path], close_fds=True)
                else:
                    # 备用：使用系统默认程序打开（非阻塞）
                    os.startfile(log_path)
            elif system == "Linux":
                subprocess.Popen(['xdg-open', log_path])
            elif system == "Darwin":  # macOS
                subprocess.Popen(['open', log_path])
            else:
                # 通过主线程显示错误（GUI操作必须在主线程）
                self._show_error(f"不支持的系统: {system}")
        except Exception as e:
            self._show_error(f"无法打开日志文件：\n{e}")

    def _show_error(self, message):
        # 使用 after 投递到主线程执行 GUI 操作
        self.selected_file.master.after(0, lambda: messagebox.showerror("错误", message))
