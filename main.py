import tkinter as tk
from file_handler import handle_file_upload
from delete_handler import delete_test_case

# 创建主窗口
root = tk.Tk()
root.title("主窗口")
root.geometry("600x400")

# 创建“点击我”按钮
button = tk.Button(
    root,
    text="点击我",
    command=lambda: handle_file_upload(),
    width=10,
    height=2
)
button.pack(pady=20)

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

# 运行主循环
root.mainloop()