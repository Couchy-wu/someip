# -*- coding: utf-8 -*-
# camera_viewer.py
"""
摄像头打开程序
"""

import cv2
import numpy as np
import sys
import traceback


# 读取摄像头，并设置分辨率
def try_open_camera(indices=(0, 1), target_width=1920, target_height=1080):
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

def main():
    # 摄像头初始化
    cap, cam_index = try_open_camera((0, 1))

    # 获取采集分辨率（用于读取帧）
    if cam_index is not None and cap.isOpened():
        # 有摄像头 → 读取真实分辨率
        resolution = get_camera_resolution(cap)
        if resolution is None:
            print("[WARN] 获取摄像头分辨率失败，使用默认 1080P 图像采集分辨率")
            CAPTURE_W, CAPTURE_H = 1920, 1080  # 假设我们仍按1080P采集
        else:
            CAPTURE_W, CAPTURE_H = resolution
            print(f"[INFO] 获取摄像头分辨率成功, 图像采集分辨率：{CAPTURE_W}x{CAPTURE_H}")
    else:
        # 没有摄像头 → 使用默认尺寸
        CAPTURE_W, CAPTURE_H = 1920, 1080
        print(f"[INFO] 未识别到摄像头，使用模拟 1080P 图像采集分辨率")

    # 创建窗口
    win_name = "Camera"
    DISPLAY_W, DISPLAY_H = 640, 360         # 设置显示窗口大小
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, DISPLAY_W, DISPLAY_H)
    print(f"[INFO] 显示窗口大小设置为: {DISPLAY_W}x{DISPLAY_H}")

    # 主循环（唯一的循环）
    while True:
        # 读取帧
        if cap.isOpened():
            ret, frame = cap.read()
            if not ret:                     # 读取失败 → 用黑帧补位
                frame = np.zeros((CAPTURE_H, CAPTURE_W, 3), dtype=np.uint8)
        else:
            # 没有摄像头 → 直接生成黑帧
            frame = np.zeros((CAPTURE_H, CAPTURE_W, 3), dtype=np.uint8)

        # 如果是“无摄像头”模式，在画面中央写提示文字
        if cam_index is None:
            draw_centered_text(frame, "No Camera", color=(0, 255, 0), scale=5, thickness=10)

        # 等比缩放 + 黑边填充
        display_frame = resize_with_aspect_ratio(frame, DISPLAY_W, DISPLAY_H)

        # 显示缩放后的帧
        cv2.imshow(win_name, display_frame)

        # 退出检测
        key = cv2.waitKey(1) & 0xFF          # 1ms 超时，几乎不影响帧率
        if cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) < 1:
            print("[INFO] 检测到窗口关闭，准备退出")
            break

        # 兼容键盘退出（可选）
        # if key == 27: 
        #     print("[INFO] 按下 ESC 键，准备退出")
        #     break

    # 资源释放
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()