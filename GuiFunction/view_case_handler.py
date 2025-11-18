import os
import subprocess
import tkinter.messagebox as tk
import platform
import shutil

# 模块功能：开Excel表格文件

class ViewCaseHandler:
    def __init__(self, selected_file, test_case_folder="TestcaseCollection"):
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
            system = platform.system()
            if system == 'Windows':
                # 查找WPS的安装路径
                file_root_path = os.getcwd()
                abs_file_path = os.path.abspath(os.path.join(file_root_path, file_path))
                # 查找 et.exe
                wps_path = None
                wps_folder = r'C:\Program Files (x86)\Kingsoft\WPS Office'
                for root, dirs, files in os.walk(wps_folder):
                    if 'et.exe' in files:
                        wps_path = os.path.join(root, 'et.exe')
                        break  # 找到就退出
                if wps_path:
                    # 使用 Popen 异步启动，不阻塞 GUI
                    subprocess.Popen([wps_path, abs_file_path])
                else:
                    # 如果找不到WPS，尝试查找Excel
                    excel_path = shutil.which('excel')
                    if excel_path:
                        subprocess.Popen([excel_path, abs_file_path])
                    else:
                        tk.showerror("错误", "未找到WPS和Excel程序，请安装WPS或Excel")
                        return
            elif system == 'Linux':
                subprocess.Popen(['libreoffice', file_path])
            elif system == 'Darwin':
                subprocess.Popen(['open', file_path])
            else:
                tk.showerror("错误", f"不支持的系统: {system}")
                return
        except Exception as e:
            tk.showerror("错误", f"无法打开文件：{e}")