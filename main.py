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
import queue

class TextRedirector:
    """
    将任何线程的 print 输出安全地转发到 Tkinter Text 小部件。
    通过内部 queue + root.after 实现在主线程中写入，避免跨线程直接操作 UI。
    """
    def __init__(self, widget, root, poll_interval: int = 50):
        self.widget = widget          # tk.Text 实例
        self.root   = root            # 主窗口 (tk.Tk)
        self._queue = queue.Queue()   # 线程安全的 FIFO
        self._poll_interval = poll_interval
        self._start_poll()            # 启动轮询任务
    def write(self, string: str):
        """所有线程都会调用此方法，只负责把字符串放入队列。"""
        if string:                     # 过滤空字符串
            self._queue.put(string)
    def flush(self):
        """保持文件对象接口兼容，实际不需要实现。"""
        pass
    # 私有：在主线程周期性取出队列内容并写入 Text
    def _start_poll(self):
        """使用 root.after 循环轮询队列并写入 Text。"""
        self._flush_queue()
        self.root.after(self._poll_interval, self._start_poll)
    def _flush_queue(self):
        """一次性写出队列中所有待打印的字符串。"""
        try:
            while True:                       # 直至队列为空抛异常
                line = self._queue.get_nowait()
                self.widget.insert(tk.END, line)
                self.widget.see(tk.END)      # 自动滚动到底部
        except queue.Empty:
            pass


# 创建主窗口
root = tk.Tk()
root.title("主窗口")
root.geometry("1300x600") 

# 初始化文件更新器
file_updater = FileUpdater()
selected_file = tk.StringVar()

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

# 创建右侧主容器（包含时间标签 + 日志框）
log_main_frame = tk.Frame(root)
log_main_frame.grid(row=0, column=5, rowspan=5, padx=10, pady=10, sticky="nsew")

# 使内部组件可随窗口拉伸
log_main_frame.grid_rowconfigure(1, weight=1)  # 第1行（日志框）占主要空间
log_main_frame.grid_columnconfigure(0, weight=1)

# 1. 创建时间显示标签
time_label = tk.Label(
    log_main_frame,
    text="",
    font=tkfont.Font(family="微软雅黑", size=10, weight="bold"),
    bg="#F0F0F0",        # 浅灰色背景，美观清晰
    fg="#000000",        # 黑色文字
    anchor="w",          # 文字左对齐
    relief="flat",       # 边框风格（可选）
    height=1
)
time_label.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))
# sticky="ew" → 水平拉伸；pady=(0,5) → 下方留空，与日志框分离

# 2. 创建日志文本框的容器（frame）
log_frame = tk.Frame(log_main_frame)
log_frame.grid(row=1, column=0, sticky="nsew")
log_frame.grid_rowconfigure(0, weight=1)
log_frame.grid_columnconfigure(0, weight=1)

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
log_text.grid(row=0, column=0, sticky="nsew")

# 创建垂直滚动条
scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
scrollbar.grid(row=0, column=1, sticky="ns")

# 关联文本框与滚动条
log_text.config(yscrollcommand=scrollbar.set)

# 重定向 stdout 到文本框
import sys
sys.stdout = TextRedirector(log_text, root)
# 如需同时捕获 stderr 也可以这样做（可选）：
# sys.stderr = TextRedirector(log_text, root)

# ====== 实时更新时间函数 ======
def update_time():
    from datetime import datetime
    current_time = datetime.now().strftime("%H:%M:%S")
    time_label.config(text=f"当前时间: {current_time}")
    root.after(1000, update_time)  # 每隔1000毫秒（1秒）调用一次自己

# 启动时间刷新
update_time()

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
    if not can_window_instance:
        return

    # 取得保存在 Toplevel 上的 CANFDGUI 实例
    gui = getattr(can_window_instance, "can_gui", None)

    if gui and hasattr(gui, "on_closing"):
        # 交给 GUI 自己的关闭逻辑处理
        gui.on_closing()

        # 如果 GUI 已经自行销毁了窗口（即 on_closing 调用了 destroy），
        # winfo_exists() 会返回 False，此时需要清理全局变量并恢复按钮状态
        if not can_window_instance.winfo_exists():
            can_window_instance = None
            can_control_button.config(state=tk.NORMAL)
    else:
        # 防御性写法：没有 GUI 实例时直接销毁窗口
        can_window_instance.destroy()
        can_window_instance = None
        can_control_button.config(state=tk.NORMAL)

def open_can_gui():
    """点击主界面 “can测试” 按钮时打开 CANFD 控制子窗口。"""
    global can_window_instance

    # 已有窗口存在则聚焦并直接返回
    if can_window_instance is not None:
        try:
            if can_window_instance.winfo_exists():
                can_window_instance.focus()
                return
        except tk.TclError:
            can_window_instance = None   # 窗口可能已异常销毁

    # 禁用打开按钮，防止重复打开
    can_control_button.config(state=tk.DISABLED)

    # 创建子窗口（Toplevel）
    new_window = tk.Toplevel(root)
    new_window.title("CAN信号自动收发程序")
    new_window.geometry("800x600")

    # 实例化 CANFD GUI，并把对象挂到 Toplevel 上，供关闭回调使用
    can_gui = CANFDGUI(new_window, selected_file=selected_file)
    new_window.can_gui = can_gui   # <-- 关键：保存实例

    # 保存全局引用，以便关闭时能找到窗口
    can_window_instance = new_window

    # 把关闭协议指向统一的回调
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