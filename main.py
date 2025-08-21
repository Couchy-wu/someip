import tkinter as tk

def click_button():
    # 创建新窗口
    new_window = tk.Toplevel(root)
    new_window.title("新窗口")
    new_window.geometry("200x100")  # 设置窗口大小

    # 创建文本框并插入内容
    text_box = tk.Entry(new_window)
    text_box.insert(0, "OK")  # 在文本框中插入"OK"
    text_box.pack(pady=20)  # 布局文本框

    # 设置文本框为只读（可选）
    text_box.config(state='readonly')

# 创建主窗口
root = tk.Tk()
root.title("主窗口")
root.geometry("300x200")

# 创建按钮
button = tk.Button(
    root, 
    text="点击我", 
    command=click_button, 
    width=10, 
    height=2
)
button.pack(pady=50)  # 布局按钮，上下留空50像素

# 运行主循环
root.mainloop()