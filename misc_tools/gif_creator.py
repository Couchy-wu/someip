import os
import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image

# 功能：多张图片合成一个gif
# 如何使用：
# 1.将图片放在一个文件夹中
# 2.图片名称修改为1,2,3...逐渐增加
# 3.直接运行此代码即可生成一个GUI，直接继续操作即可

# 备注1：可以配合图片重命名程序使用（image_batch_rename.py）
# 备注2：警告不影响功能，只是颜色显示可能略有偏差。（其实基本没有影响）


# 定义生成GIF的函数
def gif_creator(image_folder, output_gif, duration=100, loop=0):
    image_files = [f for f in os.listdir(image_folder) if f.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
    image_files.sort(key=lambda x: int(os.path.splitext(x)[0]))
    
    images = []
    for image_file in image_files:
        image_path = os.path.join(image_folder, image_file)
        image = Image.open(image_path)
        images.append(image)

    if images:
        images[0].save(
            output_gif,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=loop,
            format='GIF'
        )
        print(f"GIF已生成: {output_gif}")
    else:
        print("未找到图片文件，无法生成GIF。")

# GUI操作函数
def select_folder():
    folder_path = filedialog.askdirectory()
    if folder_path:
        # 弹出名称输入框
        user_input = simpledialog.askstring("输入名称", "请输入GIF文件名（无需输入后缀）：", parent=root)
        
        if user_input:
            # 自动添加后缀
            output_gif = f"{user_input}.gif"
            # 检查名称是否合法（简单过滤非法字符）
            if not any(char in r'\/:*?"<>|' for char in user_input):
                gif_creator(folder_path, output_gif)
                print("GIF生成完成！")
            else:
                print("文件名包含非法字符，请重新输入。")

def main():
    """启动图片转 GIF 小工具（GUI）。

    注意：GUI 构造必须放在函数里 —— 早期版本在模块级直接 `tk.Tk()` 并
    `mainloop()`，导致 `import misc_tools.gif_creator` 会永久阻塞
    （自动化测试/被其他模块引用时表现为"卡死"）。
    """
    root = tk.Tk()
    root.title("图片转GIF工具")
    root.geometry("400x200")

    # 添加按钮
    select_button = tk.Button(
        root,
        text="选择图片文件夹并生成GIF",
        command=select_folder,
        font=("Arial", 12),
        width=30,
        bg="#4A90E2",              # 按钮背景色
        fg="white" ,               # 按钮文字颜色    
        relief=tk.FLAT,            # 使按钮看起来更平滑
        bd=0,                      # 移除默认边框
        highlightthickness=2,      # 增加点击/聚焦效果
        activebackground="#005fa3" # 点击时的背景色
    )
    select_button.pack(pady=40)

    # 启动GUI主循环
    root.mainloop()

if __name__ == "__main__":
    main()
