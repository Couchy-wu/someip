import os
import subprocess
import tkinter.messagebox as tk
import platform
import shutil

# 模块功能：以只读的形式打开Excel表格文件

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
                file_path = os.path.join(file_root_path,file_path)
                # windows系统用wps打开似乎需要绝对路径？
                wps_path = shutil.which('wps')
                if wps_path == None :
                    wps_path = r'C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.20324\office6\et.exe'
                if wps_path:
                    # 使用WPS打开文件
                    subprocess.run([wps_path, file_path], check=True)
                else:
                    # 如果找不到WPS，尝试查找Excel
                    excel_path = shutil.which('excel')
                    if excel_path:
                        # 使用Excel的只读模式参数（/r）
                        subprocess.run([excel_path, '/r', file_path], check=True)
                    else:
                        tk.showerror("错误", "未找到WPS和Excel程序，请安装WPS或Excel")
                        return
            elif system == 'Linux':
                # 使用LibreOffice以只读模式打开文件
                try:
                    subprocess.run(['libreoffice', '--view', file_path], check=True)
                except FileNotFoundError:
                    tk.showerror("错误", "请安装LibreOffice以查看文件")
                    return
            elif system == 'Darwin':
                # macOS目前无法直接以只读模式打开Excel文件，可以考虑其他方法
                # 这里暂时使用默认打开
                subprocess.run(['open', file_path], check=True)
            else:
                tk.showerror("错误", f"不支持的系统: {system}")
                return
        except Exception as e:
            tk.showerror("错误", f"无法打开文件：{e}")