import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil

# 功能：图片重命名
# 如何使用：
# 1.选择一个存放图片的文件夹，图片名称为纯数字，且从小到大
# 2.点击运行，会把图片名称重命名。从1开始逐渐递增


def rename_images():
    # 获取代码所在的文件夹路径
    script_folder = os.path.dirname(os.path.abspath(__file__))
    print(f"脚本所在文件夹：{script_folder}")

    # 选择文件夹
    folder_selected = filedialog.askdirectory()
    if not folder_selected:
        return

    # 打印所选文件夹的路径
    print(f"已选择文件夹：{folder_selected}")

    # 获取文件夹的名称
    folder_name = os.path.basename(folder_selected)
    # print(f"文件夹名称：{folder_name}")

    # 创建新文件夹名称：文件夹名称 + _re_name 后缀
    new_folder_name = f"{folder_name}_re_name"
    new_folder = os.path.join(script_folder, new_folder_name)
    print(f"新文件夹路径：{new_folder}")

    # 获取文件夹中的所有文件
    files = os.listdir(folder_selected)
    # 过滤出图片文件（假设图片文件扩展名是 .jpg、.png 等）
    image_files = [f for f in files if os.path.isfile(os.path.join(folder_selected, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]

    # 按文件名数字顺序排序
    image_files.sort(key=lambda x: int(x.split('.')[0]))

    # 创建新文件夹
    if not os.path.exists(new_folder):
        os.makedirs(new_folder)
        print(f"创建新文件夹：{new_folder}")
    else:
        # 如果文件夹存在，清空其中的内容
        print(f"清空中文件夹：{new_folder}")
        for f in os.listdir(new_folder):
            file_path = os.path.join(new_folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

    # 重命名并复制图片
    for index, filename in enumerate(image_files, 1):
        old_path = os.path.join(folder_selected, filename)
        # 提取文件扩展名
        file_ext = filename.split('.')[-1]
        new_name = f"{index}.{file_ext}"
        new_path = os.path.join(new_folder, new_name)
        # 复制文件
        shutil.copy2(old_path, new_path)
        # print(f"复制文件：{old_path} -> {new_path}")

    messagebox.showinfo("完成", "图片重命名完成！")

# 创建GUI窗口
root = tk.Tk()
root.title("图片重命名工具")
root.geometry("400x100")

# 添加选择文件夹按钮
select_button = tk.Button(root, text="选择文件夹", command=rename_images)
select_button.pack(pady=20)

root.mainloop()