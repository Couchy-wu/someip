import tkinter as tk
from new_window import create_new_window

def click_button(root):
    create_new_window(root)

# 创建主窗口
root = tk.Tk()
root.title("主窗口")
root.geometry("300x200")

# 创建按钮
button = tk.Button(
    root,
    text="点击我",
    command=lambda: click_button(root),
    width=10,
    height=2
)
button.pack(pady=50)

# 运行主循环
root.mainloop()