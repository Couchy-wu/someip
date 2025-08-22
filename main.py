import tkinter as tk
import os
from tkinter import ttk
from file_updater import FileUpdater
from file_handler import handle_file_upload
from delete_handler import delete_test_case
from view_case_handler import ViewCaseHandler

# 创建主窗口
root = tk.Tk()
root.title("主窗口")
root.geometry("600x400")

# 初始化文件更新器
file_updater = FileUpdater()
selected_file = tk.StringVar()

# 初始化查看用例处理器
view_case_handler = ViewCaseHandler(selected_file)

# 创建“上传测试用例”按钮
upload_button = tk.Button(
    root,
    text="上传测试用例",
    command=handle_file_upload,
    width=15,
    height=2
)
upload_button.grid(row=0, column=0, padx=20, pady=20)

# 创建“删除测试用例”按钮
delete_button = tk.Button(
    root,
    text="删除测试用例",
    command=delete_test_case,
    width=15,
    height=2
)
delete_button.grid(row=0, column=1, padx=20, pady=20)

# 创建下拉菜单
file_menu = ttk.OptionMenu(root, selected_file, *[])
file_menu.grid(row=1, column=0, padx=20, pady=20)

# 初始化下拉菜单
file_updater.initialize_menu(selected_file, file_menu)

# 更新按钮命令
upload_button.config(command=lambda: file_updater.on_upload(selected_file, file_menu))
delete_button.config(command=lambda: file_updater.on_delete(selected_file, file_menu))

# 创建“查看用例”按钮
view_button = tk.Button(
    root,
    text="查看用例",
    command=view_case_handler.open_selected_file,  # 调用模块方法
    width=15,
    height=2
)
view_button.grid(row=1, column=1, padx=20, pady=20)

# 运行主循环
root.mainloop()