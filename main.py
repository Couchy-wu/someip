import tkinter as tk
import os
import json
from tkinter import ttk
from file_handler import handle_file_upload, refresh_json_file
from delete_handler import delete_test_case

# 创建主窗口
root = tk.Tk()
root.title("主窗口")
root.geometry("600x400")

# 创建变量来存储当前选中的文件
selected_file = tk.StringVar()

def load_file_list():
    target_folder = os.path.join(os.getcwd(), "测试用例集")
    json_file = os.path.join(target_folder, "test_cases.json")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            file_list = json.load(f)
    except FileNotFoundError:
        file_list = []
    
    # 更新下拉菜单的选项
    menu = file_menu['menu']
    menu.delete(0, 'end')
    for file in file_list:
        menu.add_command(label=file, command=tk._setit(selected_file, file))
    
    # 设置默认值
    if file_list:
        selected_file.set(file_list[0])
    else:
        selected_file.set("无文件")


# 创建“上传测试用例”按钮
upload_button = tk.Button(
    root,
    text="上传测试用例",
    command=handle_file_upload,
    width=15,
    height=2
)
upload_button.pack(pady=20)

# 创建“删除测试用例”按钮
delete_button = tk.Button(
    root,
    text="删除测试用例",
    command=delete_test_case,
    width=15,
    height=2
)
delete_button.pack(pady=20)

# 创建下拉菜单
file_menu = ttk.OptionMenu(root, selected_file, *[])
file_menu.pack(pady=20)

# 初始化加载文件列表
load_file_list()

# 在上传和删除操作后刷新文件列表
def on_upload():
    handle_file_upload()
    refresh_json_file()
    load_file_list()

def on_delete():
    delete_test_case()
    refresh_json_file()
    load_file_list()

# 更新按钮命令
upload_button.config(command=on_upload)
delete_button.config(command=on_delete)

# 运行主循环
root.mainloop()