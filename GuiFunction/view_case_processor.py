import os
import platform
import subprocess
import tkinter.messagebox as messagebox
import shutil

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

        try:
            system = platform.system()
            if system == "Windows":
                # 方法1：尝试用记事本打开
                notepad_path = shutil.which("notepad")
                if notepad_path:
                    subprocess.run([notepad_path, log_path], check=True)
                else:
                    # 备用：使用系统默认程序打开
                    os.startfile(log_path)
            elif system == "Linux":
                subprocess.run(['xdg-open', log_path], check=True)
            elif system == "Darwin":  # macOS
                subprocess.run(['open', log_path], check=True)
            else:
                messagebox.showerror("错误", f"不支持的系统: {system}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开日志文件：\n{e}")
