# -*- coding: utf-8 -*-
"""
视频抽帧工具（仅使用 os / os.path）
功能：
    1. 通过 Tkinter 选取视频文件；
    2. 支持自定义抽帧帧率（FPS）或抽取全部帧；
    3. 可选 GPU（CUDA）加速（需要 CUDA 版 ffmpeg）；
    4. 进度条实时显示（占位实现，可自行替换）；
    5. 完整日志（debug.log）；
    6. 兼容中文路径（所有路径均使用原生字符串，不再依赖 pathlib）。
依赖：
    pip install ffmpeg-python opencv-python
"""
import os
import sys
import re
import logging
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import ffmpeg               # <-- ffmpeg‑python
import cv2
from datetime import datetime
from GuiFunction.progress_bar import ProgressBar
# -------------------------------------------------
# 1️⃣ 项目根目录（父文件夹）
# -------------------------------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# -------------------------------------------------
# 2️⃣ 日志初始化（控制台 + 文件）
# -------------------------------------------------
def setup_logging():
    log_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "debug.log"))
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    fileh = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    fileh.setFormatter(fmt)
    logger.addHandler(console)
    logger.addHandler(fileh)
    logging.debug("日志已初始化 → %s", log_file)

setup_logging()

# -------------------------------------------------
# 3️⃣ 把 ffmpeg.exe 的完整路径交给 ffmpeg‑python（可选）
# -------------------------------------------------
def set_ffmpeg_executable(ffmpeg_path: str):
    """兼容 0.11+ 与旧版 (<0.11)"""
    if not os.path.isfile(ffmpeg_path):
        raise FileNotFoundError(f"ffmpeg.exe 不在这里：{ffmpeg_path}")
    try:
        ffmpeg.set_executable(ffmpeg_path)   # 0.12+ 官方 API
        logging.debug("使用 ffmpeg.set_executable 设置可执行文件")
    except AttributeError:                     # 兼容 <0.12
        ffmpeg._run.ffmpeg_path = ffmpeg_path
        logging.debug("使用内部属性 _run.ffmpeg_path 设置可执行文件")
    # 打印确认
    try:
        logging.debug("ffmpeg.get_executable() -> %s", ffmpeg.get_executable())
    except Exception:
        logging.debug("内部属性 ffmpeg._run.ffmpeg_path -> %s",
                      ffmpeg._run.ffmpeg_path)

# -------------------------------------------------
# 4️⃣ 简易进度条  已有自己的 ProgressBar，只要改成对应的导入即可
# -------------------------------------------------


# -------------------------------------------------
# 5️⃣ 主类：VideoProcessor（负责 UI 与 ffmpeg 调用）
# -------------------------------------------------
class VideoProcessor:
    def __init__(self, root):
        self.root = root
        self.progress = ProgressBar(root)

    # -------------------------------------------------
    # ① UI 入口：按钮回调
    # -------------------------------------------------
    def process_video(self):
        # ---- 1）选取视频文件（支持中文路径） ----
        video_path = filedialog.askopenfilename(
            title="请选择视频文件",
            filetypes=[("MP4 视频", "*.mp4"), ("所有文件", "*.*")]
        )
        if not video_path:
            return
        video_path = os.path.abspath(video_path)

        # ---- 2）输出文件夹（同目录下自动创建） ----
        video_name = os.path.basename(video_path)                # e.g. ARHUD.mp4
        folder_base = os.path.splitext(video_name)[0]            # ARHUD
        out_dir = os.path.join(os.path.dirname(video_path),
                               f"{folder_base}_frames")
        if os.path.isdir(out_dir):
            # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # out_dir = os.path.join(os.path.dirname(video_path),
            #                        f"{folder_base}_frames_{timestamp}")  #每次生成不同文件夹
            out_dir = os.path.join(os.path.dirname(video_path),
                                   f"{folder_base}_frames")
        os.makedirs(out_dir, exist_ok=True)

        # ---- 3）抽帧帧率（可空） ----
        fps_str = simpledialog.askstring(
            "抽帧帧率",
            "请输入抽帧帧率（FPS），留空则抽取全部帧",
            parent=self.root)
        fps = float(fps_str) if fps_str and fps_str.strip() else None

        # ---- 4）是否使用 GPU（CUDA） ----
        use_gpu = messagebox.askyesno("GPU 加速", "是否使用 GPU（CUDA）加速？")

        # ---- 5）ffmpeg.exe 的完整路径（若已在 PATH 可留空） ----
        ffmpeg_path = os.path.abspath(
            os.path.join(ROOT, "ffmpeg", "bin", "ffmpeg.exe"))
        if not os.path.isfile(ffmpeg_path):
            # 让用户手动挑选
            ffmpeg_path = filedialog.askopenfilename(
                title="请选择 ffmpeg.exe（若已在系统 PATH 可直接点“取消”）",
                filetypes=[("ffmpeg 可执行文件", "ffmpeg.exe")]
            )
            if not ffmpeg_path:               # 用户点了“取消”
                ffmpeg_path = None            # 使用系统 PATH
            else:
                ffmpeg_path = os.path.abspath(ffmpeg_path)

        # ---- 6）启动子线程进行抽帧 ----
        threading.Thread(
            target=self._run_ffmpeg_thread,
            args=(video_path, out_dir, fps, use_gpu, ffmpeg_path),
            daemon=True
        ).start()

    # -------------------------------------------------
    # ② 子线程：真正的 ffmpeg 调用与进度解析
    # -------------------------------------------------
    def _run_ffmpeg_thread(self,
                           video_path: str,
                           out_dir: str,
                           fps: float | None,
                           use_gpu: bool,
                           ffmpeg_path: str | None):
        try:
            # ---------- (1) 读取总帧数 ----------
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            logging.debug("视频总帧数 = %d", total_frames)

            # ---------- (2) 估算要写入的帧数 ----------
            if fps is not None:
                cap = cv2.VideoCapture(video_path)
                orig_fps = cap.get(cv2.CAP_PROP_FPS)
                cap.release()
                if orig_fps > 0:
                    expected = int(total_frames * fps / orig_fps + 0.5)
                else:
                    expected = total_frames
            else:
                expected = total_frames

            # 创建进度条（在主线程中）
            self.root.after(0,
                            self.progress.create_progress_bar,
                            "抽帧进度", expected)

            # ---------- (3) （可选）把路径写进全局 ----------
            if ffmpeg_path:
                set_ffmpeg_executable(ffmpeg_path)   # 兼容旧版，非必须

            # ---------- (4) 构造 ffmpeg 流 ----------
            input_kwargs = {}
            if use_gpu:
                input_kwargs["hwaccel"] = "cuda"
                input_kwargs["hwaccel_output_format"] = "cuda"

            stream = ffmpeg.input(video_path, **input_kwargs)
            if fps is not None:
                stream = stream.filter('fps', fps=fps)

            pattern = os.path.join(out_dir, "frame_%04d.png")
            stream = (
                stream
                .output(pattern,
                        vsync=0,
                        compression_level=6)
                .overwrite_output()
            )

            # ---------- (5) 打印编译后的命令（调试） ----------
            cmd_list = stream.compile()
            logging.debug("即将执行的 ffmpeg 命令: %s", " ".join(cmd_list))

            # ---------- (6) 运行（关键：使用 cmd=） ----------
            # 只有 ffmpeg‑python >= 0.12 才支持 cmd=，请确保已升级
            proc = stream.run_async(
                cmd=ffmpeg_path,          # <-- 把完整路径交给 subprocess
                pipe_stdout=True,
                pipe_stderr=True,
            )

            # ---------- (7) 读取进度 ----------
            frame_re = re.compile(r'frame=\s*(\d+)')
            while True:
                raw = proc.stderr.readline()
                if not raw:
                    break
                line = raw.decode(errors='ignore')
                m = frame_re.search(line)
                if m:
                    cur = int(m.group(1))
                    self.root.after(0,
                                    self.progress.update_progress,
                                    cur)

            proc.wait()

            # ---------- (8) 收尾 ----------
            self.root.after(0, self.progress.close_progress_bar)
            self.root.after(
                0,
                messagebox.showinfo,
                "抽帧完成",
                f"抽帧已完成，保存至:\n{out_dir}\n估计抽取帧数: {expected}"
            )
            logging.info("抽帧完成 → %s", out_dir)

        except ffmpeg.Error as e:
            err_msg = e.stderr.decode(errors='ignore')
            logging.error("ffmpeg 错误: %s", err_msg)
            self.root.after(0,
                            messagebox.showerror,
                            "ffmpeg 错误",
                            f"ffmpeg 运行失败:\n{err_msg}")

        except Exception as exc:
            logging.exception("未知错误")
            self.root.after(0,
                            messagebox.showerror,
                            "错误",
                            str(exc))

        finally:
            self.root.after(0, self.progress.close_progress_bar)

# -------------------------------------------------
# 7️⃣ 主窗口入口
# -------------------------------------------------
if __name__ == "__main__":
    # 防止 IDE / 调试器的 cwd 与脚本所在目录不一致
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    root = tk.Tk()
    root.title("视频抽帧（ffmpeg + GUI）")
    root.geometry("380x180")
    vp = VideoProcessor(root)

    btn = tk.Button(root,
                    text="选择视频并抽帧",
                    command=vp.process_video,
                    width=20,
                    height=2,
                    bg="#4CAF50",
                    fg="white",
                    font=("Microsoft YaHei", 10))
    btn.pack(pady=45)

    root.mainloop()