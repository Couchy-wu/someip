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
            # 跨平台打开：由 hudcore 统一探测表格应用
            #   Windows: WPS(et.exe) → Excel ；Ubuntu: libreoffice/soffice → xdg-open ；macOS: open
            from hudcore.platform.executables import open_in_office_app
            abs_file_path = os.path.abspath(file_path)
            if not open_in_office_app(abs_file_path):
                tk.showerror(
                    "错误",
                    "未找到可用的表格程序。\n"
                    "  Windows: 请安装 WPS 或 Excel\n"
                    "  Ubuntu : sudo apt install -y libreoffice-calc（或 libreoffice）"
                )
        except Exception as e:
            tk.showerror("错误", f"无法打开文件：{e}")