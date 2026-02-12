# -*- coding: utf-8 -*-
# camera_viewer.py
"""
摄像头打开程序（Windows 专用，直接设置曝光，无验证）
"""
import os
import cv2
import numpy as np
import sys, traceback, threading, time, platform, datetime, random
from dataclasses import dataclass
import queue

# 帮助函数
def _fmt_ts(ts: float) -> str:
    """
    把 Unix epoch 秒统一格式化为 “YYYY‑MM‑DD HH:MM:SS.mmm”
    （毫秒精度），用于日志打印。
    """
    dt = datetime.datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

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
    # 提前检查是否需要缩放，避免不必要的计算
    if w == target_width and h == target_height:
        return frame
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
    # 使用 UUID 避免竞争条件
    import uuid
    filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(save_path, filename)
    if cv2.imwrite(filepath, frame):
        print(f"[INFO] 截图已保存: {filepath}")
    else:
        print(f"[WARN] 截图保存失败: {filepath}")

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
    # 返回更真实的成功状态
    return cap.get(cv2.CAP_PROP_EXPOSURE) == float(exposure_val)

# ----------------------------------------------------------------------
# 3️⃣ 摄像头封装（线程化）
# ----------------------------------------------------------------------
class CameraViewer:
    """
    exposure=-4,               # 曝光值
    draw_timestamp=False,      # 绘制时间戳文字
    enable_timestamp=True,     # 启用时间戳功能
    simulate_error=False,      # 是否开启异常帧模拟
    error_probability=0.01     # 异常帧出现概率  
    target_fps=30              # 摄像头目标帧率   
    """
    def __init__(self,
                 display_callback=None,     # 回调函数 ，用于在捕获到每一帧图像后，把图像数据传递给外部处理函数
                 is_standalone=False,       # 是否是独立程序
                 screenshot_path="Resources/Picture",
                 exposure=-4,               # 曝光值
                 draw_timestamp=False,      # 绘制时间戳文字
                 enable_timestamp=True,     # 启用时间戳功能
                 simulate_error=False,      # 是否开启异常帧模拟
                 error_probability=0.01,    # 异常帧出现概率          
                 target_fps=30              # 摄像头目标帧率     
                ):   
        self.display_callback = display_callback
        self.is_standalone = is_standalone
        self.screenshot_path = screenshot_path
        self.exposure = exposure
        self.draw_timestamp = draw_timestamp
        self.enable_timestamp = enable_timestamp
        self._callback_wants_timestamp = enable_timestamp
        self.simulate_error = simulate_error          # 是否启用异常帧
        self.error_probability = error_probability    # 触发概率 (0~1)        
        self.CAMERA_INDICES = (0, 1)
        self.CAPTURE_TARGET_WIDTH = 1280
        self.CAPTURE_TARGET_HEIGHT = 720
        self.DISPLAY_WINDOW_WIDTH = 640
        self.DISPLAY_WINDOW_HEIGHT = 360
        self.OUTPUT_WIDTH = 640
        self.OUTPUT_HEIGHT = 360
        self.TARGET_FPS = target_fps
        self.FRAME_DELAY_MS = 1
        self._stop_event = threading.Event()
        self._thread = None
        self.cap = None
        self.cam_index = None
        self.capture_w = 1280
        self.capture_h = 720
        # 创建队列用于线程间通信
        self.frame_queue = queue.Queue(maxsize=2)  # 限制队列大小避免内存暴涨
        # 预分配黑帧避免重复创建
        self._black_frame = None

    def _init_camera(self):
        self.cap, self.cam_index = try_open_camera(
            indices=self.CAMERA_INDICES,
            target_width=self.CAPTURE_TARGET_WIDTH,
            target_height=self.CAPTURE_TARGET_HEIGHT,
            target_fps=self.TARGET_FPS,
        )
        # 优化分辨率获取逻辑
        if self.cam_index is not None and self.cap.isOpened():
            self.capture_w, self.capture_h = get_camera_resolution(self.cap)
            # 预分配黑帧
            self._black_frame = np.zeros((self.capture_h, self.capture_w, 3), dtype=np.uint8)
        else:
            print("[WARN] 使用默认分辨率 1280x720")
        # 直接设置曝光（不验证）
        if self.exposure is not None and self.cap.isOpened():
            set_exposure(self.cap, self.exposure, verbose=True)

    def _run_loop(self):

        # 调试用帧率开关（fps统计开关）
        DEBUG_FPS = False
        fps_counter = 0
        fps_timer = time.perf_counter()  # 使用更高精度的时钟
        # 成功帧数统计
        success_frame_count = 0
        
        while not self._stop_event.is_set():
            loop_start = time.perf_counter()  # 使用 perf_counter
            # 先获取时间戳，后面异常帧和绘制都会使用同一个 ts
            ts = time.time()
            frame = None
            success_read = False
            
            # 读取帧
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    success_read = True
                    success_frame_count += 1
                else:
                    # 读取失败 → 用预分配的黑帧代替
                    frame = self._black_frame
            else:
                # 摄像头未打开 → 使用黑帧
                frame = self._black_frame
            
            # 模拟摄像头异常——随机把帧替换成全白图像
            if self.simulate_error and random.random() < self.error_probability:
                # 避免创建新数组，使用高效填充
                frame.fill(255)
            
            # 镜像翻转（原地操作）使用 dst 参数避免新分配
            if frame is not None and frame.size > 0:
                cv2.flip(frame, 1, dst=frame)
                
                # 是否在画面上绘制时间戳
                if self.draw_timestamp:
                    draw_timestamp_on_frame(frame, ts)
                
                # 生成 TimedFrame（供回调使用）
                timed_frame = TimedFrame(img=frame, timestamp=ts, cam_index=self.cam_index)
                
                # 摄像头未找到的文字提示
                if self.cam_index is None:
                    draw_centered_text(frame, "Camera Not Found", color=(0, 0, 255), scale=2, thickness=6)
                
                # 调整显示尺寸
                display_frame = resize_with_aspect_ratio(
                    frame,
                    self.OUTPUT_WIDTH if self.display_callback else self.DISPLAY_WINDOW_WIDTH,
                    self.OUTPUT_HEIGHT if self.display_callback else self.DISPLAY_WINDOW_HEIGHT,
                )
                
                # 处理回调或放入队列
                if self.display_callback is None:
                    # 放入队列供主线程显示
                    try:
                        # 非阻塞放入，避免队列满时阻塞捕获线程
                        self.frame_queue.put_nowait((display_frame, frame))
                    except queue.Full:
                        # 队列满时丢弃旧帧，保持实时性
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put_nowait((display_frame, frame))
                        except:
                            pass
                else:
                    rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    try:
                        if self._callback_wants_timestamp:
                            self.display_callback(rgb, timed_frame.timestamp)
                        else:
                            self.display_callback(rgb)
                    except Exception as e:
                        print(f"[ERROR] display_callback error: {e}")
                        traceback.print_exc()
            
            # FPS 统计（基于成功读取的帧）
            if DEBUG_FPS:
                fps_counter += 1
                if time.perf_counter() - fps_timer >= 1.0:
                    # 显示实际成功帧率
                    print(f"[INFO] FPS: {success_frame_count} (循环: {fps_counter})")
                    fps_counter = 0
                    success_frame_count = 0
                    fps_timer = time.perf_counter()
            
            # 控制帧率（更精确）
            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0.0, (1.0 / self.TARGET_FPS) - elapsed)
            # 使用更精确的睡眠
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # 确保资源释放
        if self.cap is not None:
            self.cap.release()
            self.cap = None

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
        # 即使超时也尝试释放资源
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self._thread = None

    def run(self):
        self.start()
        # 在主线程中处理GUI显示
        if self.display_callback is None:
            win_name = "Camera"
            cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(win_name, self.DISPLAY_WINDOW_WIDTH, self.DISPLAY_WINDOW_HEIGHT)
            
            try:
                while self._thread and self._thread.is_alive():
                    try:
                        # 从队列获取帧，超时检查线程状态
                        display_frame, original_frame = self.frame_queue.get(timeout=0.1)
                        cv2.imshow(win_name, display_frame)
                        
                        key = cv2.waitKey(self.FRAME_DELAY_MS) & 0xFF
                        if self.is_standalone and key == ord('s'):
                            take_screenshot(original_frame, self.screenshot_path)
                        if cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) < 1 or key == 27:
                            break
                    except queue.Empty:
                        continue
            finally:
                self.stop()  # 确保停止捕获线程
                cv2.destroyAllWindows()
        else:
            # 使用回调模式时直接等待线程结束
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
        exposure=-6,  # 可调整
        draw_timestamp=True,
        enable_timestamp=True,
        simulate_error=False,      # 是否开启异常帧模拟
        error_probability=0.01,     # 异常帧出现概率 
        target_fps=30              # 摄像头目标帧率
    )
    viewer.run()

# 备注：如果曝光时间较高，受限于物理因素，摄像头帧速会达不到30fps
# 备注2：目前设置30帧是ok的，设置60帧的时候只能输出45帧左右，可能是图像变换的计算量的限制。
# 备注3：draw_timestamp 改动的是图像本身，建议仅调试时开启
# 备注4：enable_timestamp 只控制数值的传递，决定是否把 timestamp（浮点数）作为参数传递给 display_callback ，
#        以及是否在 TimedFrame 对象里保存该时间戳。不影响 frame 本身是否被绘制文字

if __name__ == "__main__":
    main()