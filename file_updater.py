import os
import json
from tkinter import ttk
from file_handler import handle_file_upload, refresh_json_file
from delete_handler import delete_test_case

# 模块功能：实现测试用例集下拉菜单相关功能

class FileUpdater:
    def __init__(self, target_folder="测试用例集", json_filename="test_cases.json"):
        self.target_folder = target_folder
        self.json_file = os.path.join(target_folder, json_filename)

    # 函数功能：刷新文件列表，并更新下拉菜单内容    
    def refresh_file_list(self, menu_var, option_menu):
        """
        :menu_var: tkinter.StringVar变量，用于存储选中的文件
        :option_menu: ttk.OptionMenu对象，需要更新的下拉菜单
        """
        try:
            # 读取JSON文件
            with open(self.json_file, 'r', encoding='utf-8') as f:
                file_list = json.load(f)
                
            # 更新下拉菜单
            menu = option_menu['menu']
            menu.delete(0, 'end')
            
            if file_list:
                for file in file_list:
                    menu.add_command(label=file, command=lambda f=file: menu_var.set(f))
                menu_var.set(file_list[0])
            else:
                menu.add_command(label="无文件", command=lambda: menu_var.set("无文件"))
                menu_var.set("无文件")
                
        except FileNotFoundError:
            print(f"文件未找到：{self.json_file}")
            menu = option_menu['menu']
            menu.delete(0, 'end')
            menu.add_command(label="无文件", command=lambda: menu_var.set("无文件"))
            menu_var.set("无文件")
            
        except json.JSONDecodeError:
            print(f"JSON文件格式错误：{self.json_file}")
            menu = option_menu['menu']
            menu.delete(0, 'end')
            menu.add_command(label="无文件", command=lambda: menu_var.set("无文件"))
            menu_var.set("无文件")
            
        except Exception as e:
            print(f"读取文件时发生错误：{e}")
            menu = option_menu['menu']
            menu.delete(0, 'end')
            menu.add_command(label="无文件", command=lambda: menu_var.set("无文件"))
            menu_var.set("无文件")
    
    #函数功能：处理上传操作后刷新文件列表
    def on_upload(self, menu_var, option_menu):
        # 调用上传处理函数
        handle_file_upload()
        # 刷新JSON文件
        refresh_json_file()
        # 刷新下拉菜单
        self.refresh_file_list(menu_var, option_menu)
    
    # 函数功能：处理删除操作后刷新文件列表
    def on_delete(self, menu_var, option_menu):
        # 谓调删除处理函数
        delete_test_case()
        # 刷新JSON文件
        refresh_json_file()
        # 刷新下拉菜单
        self.refresh_file_list(menu_var, option_menu)
    
    # 函数功能：初始化下拉菜单
    def initialize_menu(self, menu_var, option_menu):
        """
        :menu_var: tkinter.StringVar变量，用于存储选中的文件
        :ption_menu: ttk.OptionMenu对象，需要更新的下拉菜单
        """
        self.refresh_file_list(menu_var, option_menu)