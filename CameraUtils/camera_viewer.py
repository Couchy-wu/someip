# -*- coding: utf-8 -*-
# camera_viewer.py
"""
摄像头打开程序（Windows 专用，直接设置曝光，无验证）
"""
import os
import cv2
import numpy as np
import sys
import traceback
import threading
import time
import platform
from dataclasses import dataclass
import datetime
import inspect

# ----------------------------------------------------------------------
# 数据结构
# ----------------------------------------------------------------------
@dataclass
class TimedFrame:
    """包含图像数据及捕获时间戳的容器。"""
    img: np.ndarray          # BGR 图像（原始分辨率）
    timestamp: float         # Unix epoch 秒（float，精度 µs）
    cam_index: int = -1
    exposure: float = None

# ----------------------------------------------------------------------
# 1️⃣ 摄像头打开 & 参数设置
# ----------------------------------------------------------------------
def try_open_camera(indices=(0, 1),
                    target_width=1280,
                    target_height=720,
                    target_fps=30):
    """
    按顺序尝试打开摄像头并强制设置分辨率、帧率、像素格式。
    返回 (cap, index)。
    """
    for i in indices:
        cap = cv2.VideoCapture(i, cv2.CAP_MSMF)  # Windows 使用 MSMF
        if cap.isOpened():
            print(f"[INFO] 成功打开摄像头，请等待几秒钟...")
            fourcc = cv2.VideoWriter_fourcc(*'NV12')  # 1：JPEG 压缩，有损（MJPG） 2：未压缩 YUV（YUY2）3：YUV 4:2:0 半平面（NV12）
            cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
            cap.set(cv2.CAP_PROP_FPS, target_fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 4)

            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            print(f"[INFO] 实际分辨率: {w}x{h}, FPS: {fps:.2f}")
            return cap, i
        cap.release()
    print("[ERROR] 所有摄像头打开失败")
    return cv2.VideoCapture(), None

def get_camera_resolution(cap):
    """读取摄像头的分辨率，返回 (w, h)。"""
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if w > 0 and h > 0:
        return w, h
    ret, frame = cap.read()
    if ret and frame is not None:
        h, w = frame.shape[:2]
        return w, h
    return 1280, 720

# ----------------------------------------------------------------------
# 2️⃣ 图像处理工具
# ----------------------------------------------------------------------
def resize_with_aspect_ratio(frame, target_width, target_height, interpolation=cv2.INTER_LINEAR):
    """等比缩放 + 黑边填充"""
    h, w = frame.shape[:2]
    target_ratio = target_width / target_height
    img_ratio = w / h
    if img_ratio > target_ratio:
        new_w = target_width
        new_h = int(target_width / img_ratio)
    else:
        new_h = target_height
        new_w = int(target_height * img_ratio)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=interpolation)
    result = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    y_offset = (target_height - new_h) // 2
    x_offset = (target_width - new_w) // 2
    result[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
    return result

def rotate_image_180(frame: np.ndarray) -> np.ndarray:
    return cv2.rotate(frame, cv2.ROTATE_180)

def draw_centered_text(img, text, color=(0, 255, 0), font=cv2.FONT_HERSHEY_SIMPLEX, scale=0.8, thickness=2):
    (w, h), _ = cv2.getTextSize(text, font, scale, thickness)
    H, W = img.shape[:2]
    x = (W - w) // 2
    y = (H + h) // 2
    cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)

def take_screenshot(frame, save_path="Resources/Picture"):
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    existing = [f for f in os.listdir(save_path) if f.startswith("screenshot_") and f.endswith(".png")]
    numbers = []
    for f in existing:
        try:
            numbers.append(int(f.replace("screenshot_", "").replace(".png", "")))
        except:
            pass
    next_num = max(numbers) + 1 if numbers else 1
    filepath = os.path.join(save_path, f"screenshot_{next_num}.png")
    if cv2.imwrite(filepath, frame):
        print(f"[INFO] 截图已保存: {filepath}")
    else:
        print(f"[WARN] 截图保存失败: {filepath}")

# ★ MOD: 直接设置曝光，不验证、不等待、不打印中间过程
def set_exposure(cap, exposure_val, verbose=True):
    """
    直接尝试设置曝光值，不进行任何验证或反馈。
    """
    if not cap.isOpened():
        return False

    # 关闭自动曝光
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Windows MSMF 手动模式

    # 直接设置曝光值（不关心是否成功）
    cap.set(cv2.CAP_PROP_EXPOSURE, float(exposure_val))

    if verbose:
        print(f"[INFO] 已尝试设置曝光值为 {exposure_val}")
    return True  # 假设成功

# ----------------------------------------------------------------------
# 3️⃣ 摄像头封装（线程化）
# ----------------------------------------------------------------------
class CameraViewer:
    def __init__(self,
                 display_callback=None,     # 回调函数 ，用于在捕获到每一帧图像后，把图像数据传递给外部处理函数
                 is_standalone=False,       # 是否是独立程序
                 screenshot_path="Resources/Picture",
                 exposure=-4,               # 曝光值
                 draw_timestamp=False,      # 绘制时间戳文字
                 enable_timestamp=True):    # 启用时间戳功能
        self.display_callback = display_callback
        self.is_standalone = is_standalone
        self.screenshot_path = screenshot_path
        self.exposure = exposure
        self.draw_timestamp = draw_timestamp
        self.enable_timestamp = enable_timestamp

        self._callback_wants_timestamp = False
        if callable(display_callback):
            sig = inspect.signature(display_callback)
            params = list(sig.parameters.values())
            if len(params) >= 2:
                self._callback_wants_timestamp = True

        self.CAMERA_INDICES = (0, 1)
        self.CAPTURE_TARGET_WIDTH = 1280
        self.CAPTURE_TARGET_HEIGHT = 720
        self.DISPLAY_WINDOW_WIDTH = 640
        self.DISPLAY_WINDOW_HEIGHT = 360
        self.OUTPUT_WIDTH = 640
        self.OUTPUT_HEIGHT = 360
        self.TARGET_FPS = 30
        self.FRAME_DELAY_MS = 1

        self._stop_event = threading.Event()
        self._thread = None
        self.cap = None
        self.cam_index = None
        self.capture_w = 1280
        self.capture_h = 720

    def _init_camera(self):
        self.cap, self.cam_index = try_open_camera(
            indices=self.CAMERA_INDICES,
            target_width=self.CAPTURE_TARGET_WIDTH,
            target_height=self.CAPTURE_TARGET_HEIGHT,
            target_fps=self.TARGET_FPS,
        )

        if self.cam_index is not None and self.cap.isOpened():
            resolution = get_camera_resolution(self.cap)
            if resolution:
                self.capture_w, self.capture_h = resolution
        else:
            print("[WARN] 使用默认分辨率 1280x720")

        # 直接设置曝光（不验证）
        if self.exposure is not None and self.cap.isOpened():
            set_exposure(self.cap, self.exposure, verbose=True)

    def _run_loop(self):
        win_name = "Camera"
        if self.display_callback is None:
            cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(win_name, self.DISPLAY_WINDOW_WIDTH, self.DISPLAY_WINDOW_HEIGHT)

        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 4)

        fps_counter = 0
        fps_timer = time.time()

        try:
            while not self._stop_event.is_set():
                loop_start = time.time()

                if self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if not ret or frame is None:
                        frame = np.zeros((self.capture_h, self.capture_w, 3), dtype=np.uint8)
                else:
                    frame = np.zeros((self.capture_h, self.capture_w, 3), dtype=np.uint8)

                frame = cv2.flip(frame, 1)  # 镜像

                ts = time.time()
                timed_frame = TimedFrame(img=frame, timestamp=ts, cam_index=self.cam_index)

                if self.enable_timestamp:
                    draw_timestamp_on_frame(frame, ts)

                if self.cam_index is None:
                    draw_centered_text(frame, "Camera Not Found", color=(0, 0, 255), scale=2, thickness=6)

                display_frame = resize_with_aspect_ratio(
                    frame,
                    self.OUTPUT_WIDTH if self.display_callback else self.DISPLAY_WINDOW_WIDTH,
                    self.OUTPUT_HEIGHT if self.display_callback else self.DISPLAY_WINDOW_HEIGHT,
                )

                if self.display_callback is None:
                    cv2.imshow(win_name, display_frame)
                    key = cv2.waitKey(self.FRAME_DELAY_MS) & 0xFF
                    if self.is_standalone and key == ord('s'):
                        take_screenshot(frame, self.screenshot_path)
                    if cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) < 1 or key == 27:
                        break
                else:
                    rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    try:
                        if self._callback_wants_timestamp and self.enable_timestamp:
                            self.display_callback(rgb, timed_frame.timestamp)
                        else:
                            self.display_callback(rgb)
                    except Exception as e:
                        print(f"[ERROR] display_callback error: {e}")
                        traceback.print_exc()

                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    # print(f"[INFO] FPS: {fps_counter}")   # 真实的帧数！
                    fps_counter = 0
                    fps_timer = time.time()

                elapsed = time.time() - loop_start
                sleep_time = max(0.0, (1.0 / self.TARGET_FPS) - elapsed)
                time.sleep(sleep_time)

        finally:
            if self.cap:
                self.cap.release()
            if self.display_callback is None:
                cv2.destroyAllWindows()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._init_camera()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None

    def run(self):
        self.start()
        if self._thread:
            self._thread.join()

# ----------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------
def mirror_flip(frame: np.ndarray) -> np.ndarray:
    return cv2.flip(frame, 1)

def draw_timestamp_on_frame(frame: np.ndarray, ts: float):
    dt = datetime.datetime.fromtimestamp(ts)
    ts_str = dt.strftime("%H:%M:%S.%f")[:-3]
    cv2.putText(frame, ts_str, (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

# ----------------------------------------------------------------------
# 入口函数
# ----------------------------------------------------------------------
def main(display_callback=None):
    viewer = CameraViewer(
        display_callback=display_callback,
        is_standalone=True,
        exposure=-4,  # 可调整
        enable_timestamp=False
    )
    viewer.run()

# 备注：如果曝光时间较高，受限于物理因素，摄像头帧速会达不到30fps

if __name__ == "__main__":
    main()