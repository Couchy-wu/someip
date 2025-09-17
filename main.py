import tkinter as tk
import os
from tkinter import ttk
from GuiFunction.file_updater import FileUpdater
from GuiFunction.file_handler import handle_file_upload
from GuiFunction.delete_handler import delete_test_case
from GuiFunction.view_case_handler import ViewCaseHandler
from GuiFunction.image_handler import ImageHandler
from GuiFunction.video_processor import VideoProcessor
import GuiFunction.image_player  # 导入 image_player 模块
import GuiFunction.matrix_to_csv
import GuiFunction.binhex_gui

# 创建主窗口
root = tk.Tk()
root.title("主窗口")
root.geometry("800x600")

# 初始化文件更新器
file_updater = FileUpdater()
selected_file = tk.StringVar()

# 初始化查看用例处理器
view_case_handler = ViewCaseHandler(selected_file)

# 初始化 ImageHandler
image_handler = ImageHandler(root)

# 初始化 VideoProcessor
video_processor = VideoProcessor(root)  # 传入主窗口

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
    command=view_case_handler.open_selected_file,
    width=15,
    height=2
)
view_button.grid(row=1, column=1, padx=20, pady=20)

# 添加“打开图片”按钮
image_button = tk.Button(
    root,
    text="打开图片",
    command=image_handler.open_image,
    width=15,
    height=2
)
image_button.grid(row=2, column=0, padx=20, pady=20)

# 添加“读取视频”按钮
video_button = tk.Button(
    root,
    text="读取视频",
    command=video_processor.process_video,
    width=15,
    height=2
)
video_button.grid(row=2, column=1, padx=20, pady=20)

# 添加“播放图片视频”按钮
image_video_button = tk.Button(
    root,
    text="播放图片视频",
    command=GuiFunction.image_player.play_image_sequence,
    width=15,
    height=2
)
image_video_button.grid(row=3, column=0, columnspan=2, padx=20, pady=20)

# 添加“转换信号矩阵”按钮
convert_matrix_button = tk.Button(
    root,
    text="转换信号矩阵",
    command=lambda: open_matrix_converter(),
    width=15,
    height=2
)
convert_matrix_button.grid(row=0, column=2, columnspan=2, padx=20, pady=20)

def open_matrix_converter():
    converter_window = tk.Toplevel(root)
    converter_window.title("信号矩阵 转 CSV 工具")
    converter_window.geometry("500x200")
    converter_window.transient(root)  # 设置为临时窗口
    converter_window.grab_set()       # 模态锁定
    converter_window.focus_force()
    GuiFunction.matrix_to_csv.XlsmToCsvConverter(converter_window)

# 添加“生成16进制数据”按钮
hex_button = tk.Button(
    root,
    text="标准帧can数据生成器",
    command=lambda: GuiFunction.binhex_gui.open_binhex_converter(root),
    width=20,
    height=2
)
hex_button.grid(row=1, column=2, padx=20, pady=20)  


# 运行主循环
root.mainloop()