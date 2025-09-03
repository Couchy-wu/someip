import cv2
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from GuiFunction.progress_bar import ProgressBar
import threading

# 模块功能：读取视频，并将视频以每秒FPS_CONSTANT帧截取成图片
class VideoProcessor:
    FPS_CONSTANT = 30  # 每秒截取的帧数

    def __init__(self, root):
        self.root = root
        self.progress_bar = ProgressBar(root)

    def process_video(self):
        messagebox.showwarning("提示", "提示：文件名称不要有中文")

        # 打开文件选择对话框
        file_path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=(("视频文件", "*.mp4"), ("所有文件", "*.*"))
        )
        if not file_path:
            print("未选择视频")
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

        # 检查 fps 是否为零
        if fps <= 0:
            messagebox.showerror("错误", "视频的帧率无效，请检查视频文件！")
            cap.release()
            return

        # 创建进度条
        self.progress_bar.create_progress_bar("视频处理进度", total_frames)
        frame_interval = max(1, int(fps / self.FPS_CONSTANT))

        # 启动子线程处理视频
        thread = threading.Thread(
            target=self._process_video_in_thread,
            args=(file_path, save_folder, total_frames, frame_interval, cap)
        )
        thread.start()

    def _process_video_in_thread(self, file_path, save_folder, total_frames, frame_interval, cap):
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

            # 使用 after 方法在主线程更新进度条
            self.root.after(0, self.progress_bar.update_progress, frame_count + 1)
            frame_count += 1

        cap.release()
        self.root.after(0, self.progress_bar.close_progress_bar)
        self.root.after(0, messagebox.showinfo, "提示", f"视频处理完成，已保存到 {save_folder}")