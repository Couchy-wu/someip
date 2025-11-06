import os
import json
from tkinter import ttk
from GuiFunction.file_handler import handle_file_upload, refresh_json_file
from GuiFunction.delete_handler import delete_test_case

class FileUpdater:
    # 初始化方法，设置目标文件夹和JSON文件的路径，用于存储测试用例列表
    def __init__(self, target_folder="TestcaseCollection", json_filename="test_cases.json"):
        self.target_folder = target_folder
        self.json_file = os.path.join(target_folder, json_filename)

    # 刷新下拉菜单内容
    def refresh_file_list(self, menu_var, option_menu):
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                file_list = json.load(f)
            menu = option_menu['menu']
            menu.delete(0, 'end')
            if file_list:
                for file in file_list:
                    menu.add_command(label=file, command=lambda f=file: menu_var.set(f))
                menu_var.set(file_list[0])
            else:
                menu.add_command(label="无文件", command=lambda: menu_var.set("无文件"))
                menu_var.set("无文件")
        except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
            print(f"读取文件时发生错误：{e}")
            menu = option_menu['menu']
            menu.delete(0, 'end')
            menu.add_command(label="无文件", command=lambda: menu_var.set("无文件"))
            menu_var.set("无文件")

    # 上传后处理
    def on_upload(self, menu_var, option_menu):
        """
        1. 调用 handle_file_upload() 完成文件复制；
        2. 若复制成功，调用一次 refresh_json_file() 进行解析；
        3. 最后刷新下拉菜单。
        """
        uploaded_file = handle_file_upload()          # 只会返回文件名，或 None
        if uploaded_file:
            # 只在这里调用一次解析
            refresh_json_file(uploaded_file)          # 处理单个上传的文件
        # 不管成功与否，都尝试刷新下拉列表（若列表为空会显示 “无文件”）
        self.refresh_file_list(menu_var, option_menu)

    # 删除后处理
    def on_delete(self, menu_var, option_menu):
        delete_test_case()
        refresh_json_file()  # 仅更新文件列表，不处理其他文件
        self.refresh_file_list(menu_var, option_menu)

    # 初始化下拉菜单
    def initialize_menu(self, menu_var, option_menu):
        self.refresh_file_list(menu_var, option_menu)