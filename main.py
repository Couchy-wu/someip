import tkinter as tk
import os
from tkinter import ttk
from tkinter import font as tkfont
from GuiFunction.file_updater import FileUpdater
from GuiFunction.file_handler import handle_file_upload
from GuiFunction.delete_handler import delete_test_case
from GuiFunction.view_case_handler import ViewCaseHandler
from GuiFunction.view_case_processor import LogViewer
from GuiFunction.image_handler import ImageHandler
from GuiFunction.video_processor import VideoProcessor
import GuiFunction.image_player  # 导入 image_player 模块
import GuiFunction.matrix_to_csv
import GuiFunction.binhex_gui
from OtherGui.test_can_gui import CANFDGUI

# 重定向输出类
class TextRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, string):
        self.widget.insert(tk.END, string)
        self.widget.see(tk.END)  # 自动滚动到底部
        self.widget.update_idletasks()  # 强制刷新

    def flush(self):
        pass  # 兼容性方法，标准输出需要


# 创建主窗口
root = tk.Tk()
root.title("主窗口")
root.geometry("1300x600") 

# 初始化文件更新器
file_updater = FileUpdater()
selected_file = tk.StringVar()

# 初始化查看用例处理器
view_case_handler = ViewCaseHandler(selected_file)

# 初始化查看用例处理器
view_case_handler = ViewCaseHandler(selected_file)

# 初始化测试用例解析出来的日志的查看器
log_viewer = LogViewer(selected_file)

# 初始化 ImageHandler
image_handler = ImageHandler(root)

# 初始化 VideoProcessor
video_processor = VideoProcessor(root)  # 传入主窗口

# 自定义字体
bold_font = tkfont.Font(family="微软雅黑", size=10, weight="normal")

# 创建右侧文本框
log_frame = tk.Frame(root)
log_frame.grid(row=0, column=5, rowspan=5, padx=10, pady=10, sticky="nsew")     # 第row+1行，第column+1列，跨越rowspan行，

# 创建文本框
log_text = tk.Text(
    log_frame,
    wrap=tk.WORD,
    bg="#FFFFFF",          # 背景
    fg="#000000",          # 文字
    insertbackground="black",  # 光标颜色
    font=tkfont.Font(family="微软雅黑", size=10, weight="normal"),      # 字体
    height=20,
    width=35
)
log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# 创建垂直滚动条
scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# 关联文本框与滚动条
log_text.config(yscrollcommand=scrollbar.set)

# 重定向 stdout
import sys
sys.stdout = TextRedirector(log_text)

# 配置行列权重（确保文本框和滚动条随窗口缩放）
grid_rowconfigure_number = 5
for i in range(grid_rowconfigure_number):
    root.grid_rowconfigure(i, weight=1)
root.grid_columnconfigure(grid_rowconfigure_number, weight=1)

# 创建“上传测试用例”按钮
upload_button = tk.Button(
    root,
    text="上传测试用例",
    bg="#4A90E2",    # 蓝色背景
    font=bold_font,
    fg="white",      # 白色文字
    activebackground="#357ABD",  # 按下时背景色
    command=handle_file_upload,
    width=15,
    height=2
)
upload_button.grid(row=0, column=0, padx=20, pady=20) 

# 创建“删除测试用例”按钮
delete_button = tk.Button(
    root,
    text="删除测试用例",
    bg="#4A90E2",    # 蓝色背景
    font=bold_font,
    fg="white",      # 白色文字
    activebackground="#357ABD",  # 按下时背景色
    command=delete_test_case,
    width=15,
    height=2
)
delete_button.grid(row=0, column=1, padx=20, pady=20)

# 创建下拉菜单
file_menu = ttk.OptionMenu(root, selected_file, *[])
file_menu.grid(row=0, column=2, padx=20, pady=20)

# 初始化下拉菜单
file_updater.initialize_menu(selected_file, file_menu)

# 更新按钮命令
upload_button.config(command=lambda: file_updater.on_upload(selected_file, file_menu))
delete_button.config(command=lambda: file_updater.on_delete(selected_file, file_menu))

# 创建“查看用例”按钮
view_button = tk.Button(
    root,
    text="查看用例",
    bg="#4A90E2",    # 蓝色背景
    font=bold_font,
    fg="white",      # 白色文字
    activebackground="#357ABD",  # 按下时背景色
    command=view_case_handler.open_selected_file,
    width=15,
    height=2
)
view_button.grid(row=0, column=3, padx=20, pady=20)

# 创建“查看解析”按钮
inspect_button = tk.Button(
    root,
    text="查看解析",
    bg="#4A90E2",
    font=bold_font,
    fg="white",
    activebackground="#357ABD",
    command=log_viewer.view_log,
    width=15,
    height=2
)
inspect_button.grid(row=0, column=4, padx=20, pady=20)

# 添加“打开图片”按钮
image_button = tk.Button(
    root,
    text="打开图片",
    font=bold_font,
    bg="#D9534F",
    fg="white",
    activebackground="#C9302C",
    command=image_handler.open_image,
    width=15,
    height=2
)
image_button.grid(row=2, column=0, padx=20, pady=20)

# 添加“提取视频帧”按钮
read_video_button = tk.Button(
    root,
    text="提取视频帧",
    font=bold_font,
    bg="#D9534F",
    fg="white",
    activebackground="#C9302C",
    command=video_processor.process_video,
    width=15,
    height=2
)
read_video_button.grid(row=2, column=1, padx=20, pady=20)

# 添加“播放图片视频”按钮
image_video_button = tk.Button(
    root,
    text="播放图片视频",
    font=bold_font,
    bg="#D9534F",
    fg="white",
    activebackground="#C9302C",
    command=GuiFunction.image_player.play_image_sequence,
    width=15,
    height=2
)
image_video_button.grid(row=2, column=2, padx=20, pady=20)

# 添加“转换信号矩阵”按钮
convert_matrix_button = tk.Button(
    root,
    text="转换信号矩阵",
    font=bold_font,
    bg="#5CB85C",
    fg="white",
    activebackground="#4CAE4C",
    command=lambda: open_matrix_converter(),
    width=15,
    height=2
)
convert_matrix_button.grid(row=1, column=0, padx=20, pady=20)

def open_matrix_converter():
    converter_window = tk.Toplevel(root)
    converter_window.title("信号矩阵 转 CSV 工具")
    converter_window.geometry("500x200")
    converter_window.transient(root)  # 设置为临时窗口
    converter_window.grab_set()       # 模态锁定
    converter_window.focus_force()
    GuiFunction.matrix_to_csv.XlsmToCsvConverter(converter_window, skip_first_row=False)  #  True → 跳过第一行

# 添加“can数据生成器”按钮
hex_button = tk.Button(
    root,
    text="can数据生成器",
    bg="#5CB85C",
    fg="white",
    font=bold_font,
    activebackground="#4CAE4C",
    command=lambda: GuiFunction.binhex_gui.open_binhex_converter(root),
    width=15,
    height=2
)
hex_button.grid(row=1, column=1, padx=20, pady=20)  

# 添加“can测试”按钮，点击后调用test_can_gui.py
can_window_instance = None      # 全局变量：用于存储子窗口实例
def on_can_window_close():
    """子窗口关闭时的回调"""
    global can_window_instance
    if can_window_instance:
        can_window_instance.destroy()
    can_window_instance = None
    # 恢复按钮状态
    can_control_button.config(state=tk.NORMAL)

def open_can_gui():
    global can_window_instance
    # 如果窗口已存在，聚焦并返回
    if can_window_instance is not None:
        try:
            if can_window_instance.winfo_exists():
                can_window_instance.focus()
                return
        except tk.TclError:
            can_window_instance = None # 窗口可能被异常销毁
    # 禁用按钮
    can_control_button.config(state=tk.DISABLED)
    # 创建新窗口
    new_window = tk.Toplevel(root)
    new_window.title("CAN信号自动收发程序")
    new_window.geometry("800x600")
    # 赋值给全局变量，以便关闭时能找到
    can_window_instance = new_window
    # 实例化 GUI，并传入 selected_file
    CANFDGUI(new_window, selected_file=selected_file)
    # 设置关闭协议
    new_window.protocol("WM_DELETE_WINDOW", on_can_window_close)

can_control_button = tk.Button(
    root,
    text="can测试",
    bg="#5CB85C",
    fg="white",
    font=bold_font,
    activebackground="#4CAE4C",
    command=open_can_gui,
    width=15,
    height=2
)
can_control_button.grid(row=1, column=2, padx=20, pady=20)


# 运行主循环
root.mainloop()