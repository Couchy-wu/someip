import cv2
import numpy as np


def is_pure_white_image(image):
    """
    判断图像是否是纯白色图像（所有像素值均为255）
    
    参数:
        image: numpy array, 图像数据 (H x W x C 或 H x W)
    
    返回:
        bool: True 表示是纯白色图像，False 表示不是
    """
    if image is None:
        return False
    
    if image.ndim == 3:  # 彩色图像 (H, W, C)
        return np.all(image == 255)
    elif image.ndim == 2:  # 灰度图像 (H, W)
        return np.all(image == 255)
    else:
        raise ValueError("Unsupported image shape")


import numpy as np

def is_error_image(image, white_ratio_thr=0.80):
    """
    判断输入的图像是否是异常图像。
    当前异常定义：空图像、维度非法，或 **白色像素占比 ≥ white_ratio_thr**。

    参数
    ----
    image : numpy.ndarray 或 None
        待检测的图像（H×W×C 或 H×W）。
    white_ratio_thr : float, default 0.80
        判定为异常的白色像素占比阈值，取值范围 0~1。

    返回
    ----
    bool
        True 表示异常图像，False 表示正常图像。
    """
    # 空图像直接视为异常
    if image is None:
        return True

    # 维度非法视为异常
    if image.ndim not in (2, 3):
        return True

    # 计算白色像素占比
    # ① 灰度图：像素值为 255 即为白色
    if image.ndim == 2:
        white_pixels = np.count_nonzero(image == 255)
        total_pixels = image.size
    # ② 彩色图：只有 R=G=B=255 时才算白色
    else:  # image.ndim == 3
        # 先生成每个像素是否全为 255 的布尔掩码
        white_mask = np.all(image == 255, axis=2)      # shape (H, W)
        white_pixels = np.count_nonzero(white_mask)
        total_pixels = image.shape[0] * image.shape[1]

    # ③ 计算比例并与阈值比较
    white_ratio = white_pixels / total_pixels
    return white_ratio >= white_ratio_thr


# 示例用法：
if __name__ == "__main__":
    # 创建一个全白图像测试
    white_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
    print(f"是否为纯白色图像: {is_pure_white_image(white_image)}")  # 输出: True
    print(f"是否为异常图像: {is_error_image(white_image)}")  # 输出: True
    
    # 创建一个正常图像（全黑）
    normal_image = np.zeros((100, 100, 3), dtype=np.uint8)
    print(f"是否为纯白色图像: {is_pure_white_image(normal_image)}")  # 输出: False
    print(f"是否为异常图像: {is_error_image(normal_image)}")  # 输出: False
    
    # 测试灰度图像
    gray_white = np.ones((100, 100), dtype=np.uint8) * 255
    print(f"灰度图是否为纯白色图像: {is_pure_white_image(gray_white)}")  # 输出: True
    print(f"灰度图是否为异常图像: {is_error_image(gray_white)}")  # 输出: True

    # 测试空图像
    print(f"空图像是否为异常图像: {is_error_image(None)}")  # 输出: True