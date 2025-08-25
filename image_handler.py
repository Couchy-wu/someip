import cv2
import tkinter as tk
from tkinter import filedialog, Toplevel
from PIL import Image, ImageTk

class ImageHandler:
    def __init__(self, root):
        self.root = root

    def open_image(self):
        # 打开文件选择对话框
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )
        if not file_path:
            print("未选择图片")
            return

        # 读取图片
        image = cv2.imread(file_path)
        if image is None:
            print("无法读取图片")
            return

        # 转换为 RGB 格式
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image)

        # 创建新窗口
        top = Toplevel(self.root)
        top.title("图片预览")

        # 将 PIL 图像转换为 Tkinter PhotoImage
        imgtk = ImageTk.PhotoImage(image=pil_image)

        # 显示图片
        label = tk.Label(top, image=imgtk)
        label.pack(padx=10, pady=10)

        # 保持图像引用，防止被垃圾回收
        label.image = imgtk