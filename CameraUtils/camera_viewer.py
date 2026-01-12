# -*- coding: utf-8 -*-
# camera_viewer.py
"""
摄像头打开程序
"""
import os
import cv2
import numpy as np
import sys
import traceback
import threading          # <-- 新增
import time               # <-- 新增（统一使用）


# 读取摄像头，并设置分辨率
def try_open_camera(indices=(0, 1), target_width=1280, target_height=720, target_fps=30):
    """
    按顺序尝试打开摄像头索引，并尝试设置指定分辨率。
    
    参数:
        indices (tuple): 摄像头索引尝试顺序，默认 (0, 1)
        target_width (int): 目标图像宽度，最大 1920
        target_height (int): 目标图像高度，最大 1080

    返回:
        (cap, index):
            cap   - cv2.VideoCapture 对象，若全部失败则返回未打开的对象
            index - 成功打开的摄像头索引，若全部失败返回 None
    """
    for i in indices:
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # Windows建议用CAP_DSHOW
        if cap.isOpened():
            print(f"[INFO] 成功打开摄像头 (index={i})")

            # === 尝试设置目标分辨率 ===
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)

            # ---- 帧率----
            cap.set(cv2.CAP_PROP_FPS, target_fps)
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            print(f"[INFO] 目标帧率: {target_fps} FPS, 实际帧率: {actual_fps:.2f} FPS")

            # 再次获取，确认是否设置成功
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if w >= target_width and h >= target_height:
                print(f"[INFO] 摄像头分辨率已成功设置为: {w}x{h}")
            else:
                print(f"[WARN] 无法设置目标分辨率 {target_width}x{target_height}，当前分辨率: {w}x{h}（可能不支持或被驱动限制）")
            return cap, i
        cap.release()

    # 所有摄像头打开失败
    print("[WARN] 未检测到可用摄像头，将使用黑屏模式")
    return cv2.VideoCapture(), None

def get_camera_resolution(cap):
    """
    读取摄像头的分辨率，返回宽度和高度分辨率。
    若获取不到, 则返回 None。
    """
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if w > 0 and h > 0:
        return w, h

    # 有时摄像头在打开后第一次 get 仍返回 0，尝试抓一帧再获取
    ret, frame = cap.read()
    if ret:
        h, w = frame.shape[:2]
        return w, h
    return None

# 等比缩放并居中填充黑边
def resize_with_aspect_ratio(frame, target_width, target_height, interpolation=cv2.INTER_AREA):
    """
    将图像等比缩放到适合 target_width x target_height 的区域，并居中填充黑边
    """
    h, w = frame.shape[:2]
    target_ratio = target_width / target_height
    img_ratio = w / h

    # 计算缩放后尺寸
    if img_ratio > target_ratio:
        # 图像更“宽”，以宽度为基准
        new_w = target_width
        new_h = int(target_width / img_ratio)
    else:
        # 图像更“高”，以高度为基准
        new_h = target_height
        new_w = int(target_height * img_ratio)

    # 缩放图像
    resized = cv2.resize(frame, (new_w, new_h), interpolation=interpolation)

    # 创建黑色背景
    result = np.zeros((target_height, target_width, 3), dtype=np.uint8)

    # 居中粘贴
    y_offset = (target_height - new_h) // 2
    x_offset = (target_width - new_w) // 2
    result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized

    return result

def draw_centered_text(img, text, color=(0, 255, 0),
                      font=cv2.FONT_HERSHEY_SIMPLEX,
                      scale=0.8, thickness=2):
    """在 img 上把 text 居中绘制（水平+垂直）"""
    (w, h), _ = cv2.getTextSize(text, font, scale, thickness)
    H, W = img.shape[:2]
    x = (W - w) // 2               # 左下角的 x（水平居中）
    y = (H + h) // 2               # 左下角的 y（垂直居中）
    cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)

def take_screenshot(frame, save_path="Resources/Picture"):
    """
    将传入的图像帧保存为截图，保存分辨率为原始摄像头分辨率。
    图片命名按文件夹中已有最大序号递增，从1开始。

    参数:
        frame       - 要保存的图像帧 (numpy array)
        save_path   - 保存路径，默认为 Resources/Picture
    """
    # 确保保存目录存在
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    # 获取当前目录下所有以数字命名的png文件，如 screenshot_1.png
    existing_files = [f for f in os.listdir(save_path) if f.startswith("screenshot_") and f.endswith(".png")]
    # 提取序号
    numbers = []
    for f in existing_files:
        try:
            num = int(f.replace("screenshot_", "").replace(".png", ""))
            numbers.append(num)
        except ValueError:
            continue  # 忽略无法解析的文件名
    # 计算下一个序号
    next_num = max(numbers) + 1 if numbers else 1
    # 构造文件名
    filename = f"screenshot_{next_num}.png"
    filepath = os.path.join(save_path, filename)
    # 保存图像
    success = cv2.imwrite(filepath, frame)
    if success:
        print(f"[INFO] 截图已保存: {filepath}")
    else:
        print(f"[WARN] 截图保存失败: {filepath}")


# 线程化摄像头封装类
class CameraViewer:
    """
    将原来的摄像头主循环封装为可在后台线程运行的对象。
    - start()   → 在 daemon 线程中启动循环（若已在跑则直接返回）
    - stop()    → 立刻请求退出并安全释放资源
    - run()     → 兼容原来的直接调用方式（阻塞式运行）
    """
    def __init__(self, display_callback=None):
        self.display_callback = display_callback

        # ---------- 与原 main 中硬编码的配置保持一致 ----------
        self.CAMERA_INDICES = (0, 1)
        self.CAPTURE_TARGET_WIDTH = 1280
        self.CAPTURE_TARGET_HEIGHT = 720
        self.DISPLAY_WINDOW_WIDTH = 640    # 独立运行时窗口大小
        self.DISPLAY_WINDOW_HEIGHT = 360
        self.OUTPUT_WIDTH = 640             # 嵌入模式输出尺寸（横屏 16:9）
        self.OUTPUT_HEIGHT = 360
        self.TARGET_FPS = 30
        self.FRAME_DELAY_MS = 1000 // self.TARGET_FPS

        # ---------- 运行控制 ----------
        self._stop_event = threading.Event()
        self._thread = None
        self.cap = None
        self.cam_index = None

    # --------------------------------------------------------------
    # 初始化摄像头（把返回值保存为成员变量）
    # --------------------------------------------------------------
    def _init_camera(self):
        self.cap, self.cam_index = try_open_camera(
            indices=self.CAMERA_INDICES,
            target_width=self.CAPTURE_TARGET_WIDTH,
            target_height=self.CAPTURE_TARGET_HEIGHT,
            target_fps=self.TARGET_FPS,
        )
        # 读取实际采集分辨率
        if self.cam_index is not None and self.cap.isOpened():
            resolution = get_camera_resolution(self.cap)
            if resolution is None:
                self.capture_w, self.capture_h = 1280, 720
            else:
                self.capture_w, self.capture_h = resolution
        else:
            self.capture_w, self.capture_h = 1280, 720

    # --------------------------------------------------------------
    # 主循环（原来 while True 循环搬进这里，加入 stop 标识）
    # --------------------------------------------------------------
    def _run_loop(self):
        win_name = "Camera"
        if self.display_callback is None:
            cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(win_name,
                            self.DISPLAY_WINDOW_WIDTH,
                            self.DISPLAY_WINDOW_HEIGHT)

        try:
            while not self._stop_event.is_set():
                # ---------- 读取帧 ----------
                if self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if not ret:
                        frame = np.zeros((self.capture_h,
                                         self.capture_w, 3), dtype=np.uint8)
                else:
                    frame = np.zeros((self.capture_h,
                                     self.capture_w, 3), dtype=np.uint8)

                # ---------- 无摄像头提示 ----------
                if self.cam_index is None:
                    draw_centered_text(frame,
                                       "Camera Not Found",
                                       color=(0, 255, 0),
                                       scale=3,
                                       thickness=7)

                # ---------- 等比缩放 + 黑边填充 ----------
                display_frame = resize_with_aspect_ratio(
                    frame,
                    self.OUTPUT_WIDTH if self.display_callback else self.DISPLAY_WINDOW_WIDTH,
                    self.OUTPUT_HEIGHT if self.display_callback else self.DISPLAY_WINDOW_HEIGHT,
                )

                # ---------- 分发 ----------
                if self.display_callback is None:
                    cv2.imshow(win_name, display_frame)
                    key = cv2.waitKey(self.FRAME_DELAY_MS) & 0xFF
                    if (cv2.getWindowProperty(win_name,
                                              cv2.WND_PROP_VISIBLE) < 1
                            or key == 27):
                        break
                else:
                    rgb = cv2.cvtColor(display_frame,
                                       cv2.COLOR_BGR2RGB)
                    self.display_callback(rgb)

                # ---------- 控制帧率 ----------
                time.sleep(1.0 / self.TARGET_FPS)
        finally:
            # 确保资源一定被释放
            if self.cap is not None:
                self.cap.release()
            if self.display_callback is None:
                cv2.destroyAllWindows()

    # --------------------------------------------------------------
    # 对外启动 / 关闭接口
    # --------------------------------------------------------------
    def start(self):
        """在后台 daemon 线程中启动摄像头循环（若已在跑则直接返回）。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._init_camera()
        self._thread = threading.Thread(target=self._run_loop,
                                        daemon=True)
        self._thread.start()

    def stop(self):
        """请求结束循环并等待线程退出（子窗口关闭时调用）。"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)   # 防止死锁
        self._thread = None

    def run(self):
        """
        保持与旧的 `if __name__ == "__main__": main()` 调用方式兼容。
        直接在当前线程里运行（相当于原来的行为），
        仍然可以通过 `stop()` 中断。
        """
        self.start()
        if self._thread:
            self._thread.join()


# ----------------------------------------------------------------------
# 6️⃣ 兼容原来的入口函数
# ----------------------------------------------------------------------
def main(display_callback=None):
    """
    摄像头主函数（保持向后兼容）。
    现在内部会实例化 ``CameraViewer`` 并调用 ``run()``。
    """
    viewer = CameraViewer(display_callback=display_callback)
    viewer.run()          # 阻塞，直到窗口关闭或外部调用 viewer.stop()


# ----------------------------------------------------------------------
# 7️⃣ 直接运行时的入口
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()