import os
import subprocess
import tkinter.messagebox as tk
import platform  # 用于更准确的系统判断

class ViewCaseHandler:
    def __init__(self, selected_file, test_case_folder="测试用例集"):
        self.selected_file = selected_file
        self.test_case_folder = test_case_folder

    def open_selected_file(self):
        selected = self.selected_file.get()
        if not selected or selected == "无文件":
            tk.showwarning("警告", "请先选择一个文件")
            return

        file_path = os.path.join(self.test_case_folder, selected)

        if not os.path.exists(file_path):
            tk.showerror("错误", f"文件 {selected} 不存在")
            return

        try:
            system = platform.system()  # 获取系统类型，如 'Linux', 'Darwin', 'Windows'

            if system == 'Windows':
                os.startfile(file_path)
            elif system == 'Linux':
                subprocess.run(['xdg-open', file_path], check=True)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', file_path], check=True)
            else:
                tk.showerror("错误", f"不支持的系统: {system}")

        except Exception as e:
            tk.showerror("错误", f"无法打开文件：{e}")