import os
import cv2
from tkinter import *
from tkinter import filedialog, messagebox
from PIL import Image
import numpy as np
from natsort import natsorted  # 使用自然排序

# 全局变量：保存选中的文件夹路径
image_folder = ""
output_video = "output.mp4"
fps = 30  # 可调节帧率

# 选择文件夹
def select_folder():
    global image_folder
    image_folder = filedialog.askdirectory()
    if image_folder:
        label_folder.config(text=f"已选择: {image_folder}")
        print(f"选择的文件夹: {image_folder}")
    else:
        label_folder.config(text="未选择文件夹")

# 将图片转换为MP4
def convert_to_mp4():
    if not image_folder:
        messagebox.showwarning("警告", "请先选择一个包含图片的文件夹！")
        return

    # 获取所有支持的图片文件，并使用自然排序
    files = [f for f in os.listdir(image_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff'))]
    if not files:
        messagebox.showwarning("警告", "该文件夹中没有找到图片文件！")
        return

    # 使用自然排序：1, 2, ..., 10, 11 而不是 1, 10, 2
    files = natsorted(files)

    # 读取第一张图以获取尺寸
    first_image_path = os.path.join(image_folder, files[0])
    try:
        with Image.open(first_image_path) as img:
            frame_size = (img.width, img.height)
    except Exception as e:
        messagebox.showerror("错误", f"无法读取第一张图片: {e}")
        return

    # 定义视频写入对象
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, fps, frame_size)

    # 遍历图片并写入视频
    failed_images = []
    for file in files:
        file_path = os.path.join(image_folder, file)
        try:
            with Image.open(file_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                out.write(frame)
        except Exception as e:
            failed_images.append(file)
            print(f"无法处理图片 {file}: {e}")

    # 释放资源
    out.release()
    cv2.destroyAllWindows()

    # 提示完成
    if failed_images:
        message = f"视频已生成: {output_video}\n但以下图片处理失败:\n" + "\n".join(failed_images)
        messagebox.showwarning("完成（部分失败）", message)
    else:
        messagebox.showinfo("成功", f"视频已保存为: {os.path.abspath(output_video)}")

# 创建GUI界面
root = Tk()
root.title("图片转MP4工具（正确排序版）")
root.geometry("500x300")

# 标题
Label(root, text="图片转MP4工具", font=("微软雅黑", 16)).pack(pady=10)

# 上传按钮
Button(root, text="上传文件夹", width=20, height=2, command=select_folder).pack(pady=10)

# 显示路径
label_folder = Label(root, text="未选择文件夹", fg="gray")
label_folder.pack(pady=5)

# 转换按钮
Button(root, text="转换为MP4", width=20, height=2, bg="green", fg="white", command=convert_to_mp4).pack(pady=20)

# 说明
Label(root, text="支持格式: .png, .jpg, .jpeg, .bmp, .tiff\n按文件名数字大小排序（1,2,3...）\n输出视频: output.mp4", 
      fg="blue").pack(pady=5)

# 运行主循环
root.mainloop()
