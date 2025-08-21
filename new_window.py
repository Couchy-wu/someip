import tkinter as tk

#模块功能：创建一个新的窗口

def create_new_window(root):
    # 创建新窗口
    new_window = tk.Toplevel(root)
    new_window.title("新窗口")
    new_window.geometry("200x100")

    # 创建文本框并插入内容
    text_box = tk.Entry(new_window)
    text_box.insert(0, "OK")
    text_box.pack(pady=20)
    text_box.config(state='readonly')