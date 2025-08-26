import cv2
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from GuiFunction.progress_bar import ProgressBar  # 导入新模块

# 模块功能：读取视频，并将视频以每秒5帧截取成图片

class VideoProcessor:
    def __init__(self, root):
        self.root = root
        self.progress_bar = ProgressBar(root)  # 初始化进度条

    def process_video(self):
        # 打开文件选择对话框
        file_path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=(("视频文件", "*.mp4"), ("所有文件", "*.*"))
        )
        if not file_path:
            return

        # 获取视频文件名和路径
        video_name = os.path.basename(file_path)
        folder_name = os.path.splitext(video_name)[0]
        save_folder = os.path.join(os.path.dirname(file_path), folder_name)

        # 检查文件夹是否已存在
        if os.path.exists(save_folder):
            messagebox.showwarning("警告", "目标文件夹已存在，无法继续处理！")
            return

        # 创建保存文件夹
        os.makedirs(save_folder)

        # 打开视频文件
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            messagebox.showerror("错误", "无法打开视频文件！")
            return

        # 获取视频的总帧数和帧率
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        # 创建进度条
        self.progress_bar.create_progress_bar("视频处理进度", total_frames)

        # 计算每帧间隔（每秒5帧）
        frame_interval = int(fps / 5)

        frame_count = 0
        image_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                image_count += 1
                image_path = os.path.join(save_folder, f"{image_count}.png")
                cv2.imwrite(image_path, frame)

            # 更新进度条
            self.progress_bar.update_progress(frame_count + 1)

            frame_count += 1

        # 关闭进度条
        self.progress_bar.close_progress_bar()

        cap.release()

        messagebox.showinfo("提示", f"视频处理完成，已保存到 {save_folder}")