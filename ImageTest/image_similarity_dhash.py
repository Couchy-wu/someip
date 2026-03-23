# ImageTest/image_similarity_dhash.py
from typing import Union, Tuple
import numpy as np
from PIL import Image

"""
图标一致性比较（dHash + 汉明距离）
输入支持：文件路径 / PIL.Image / ndarray（灰度或彩色）
灰度化 → 缩放至 9×8（使用 PIL BILINEAR）
差值哈希 → 64 位整数
汉明距离判定
"""

# ========================================
# 将灰度转换逻辑提取为全局函数，供内外部复用
# ========================================
def to_grayscale(img: Union[str, Image.Image, np.ndarray]) -> np.ndarray:
    """
    统一转为 8-bit 灰度 ndarray (H, W)
    参数：
        img: 图像输入，支持文件路径、PIL.Image 或 ndarray
    返回：
        灰度图像 ndarray (H, W)，dtype=np.uint8
    """
    if isinstance(img, str):
        return np.array(Image.open(img).convert("L"), dtype=np.uint8)
    elif isinstance(img, Image.Image):
        return np.array(img.convert("L"), dtype=np.uint8)
    elif isinstance(img, np.ndarray):
        if img.ndim == 2:
            return img
        # 多通道：使用 Luma 加权转灰度（更准确）
        if img.shape[2] == 3:
            return (0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]).astype(np.uint8)
        elif img.shape[2] == 4:  # RGBA
            rgb = img[:, :, :3]
            alpha = img[:, :, 3] / 255.0
            return ((0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]) * alpha).astype(np.uint8)
        else:
            return np.mean(img, axis=2).astype(np.uint8)
    else:
        raise TypeError(f"不支持的图像类型: {type(img)}")

# 快速等比缩放 + 填充至目标尺寸（9x8）
def resize_with_padding(image_array: np.ndarray, target_size=(9, 8)) -> np.ndarray:
    """
    将灰度图像 ndarray 等比缩放并填充至目标尺寸 (9, 8)
    使用 PIL 进行高效缩放和填充，最后转回 ndarray
    """
    # 转为 PIL 图像以便使用 resize 和 paste
    pil_img = Image.fromarray(image_array, mode="L")
    target_width, target_height = target_size

    # 计算缩放比例，保持宽高比
    src_width, src_height = pil_img.size
    scale = min(target_width / src_width, target_height / src_height)
    new_width = max(1, int(src_width * scale))
    new_height = max(1, int(src_height * scale))

    # 缩放（使用 BILINEAR，与原逻辑一致）
    resized = pil_img.resize((new_width, new_height), Image.BILINEAR)

    # 创建居中填充的画布，背景为中性灰（128），减少边缘干扰
    padded = Image.new("L", target_size, 128)
    offset = ((target_width - new_width) // 2, (target_height - new_height) // 2)
    padded.paste(resized, offset)

    # 转回 numpy array
    return np.array(padded, dtype=np.uint8)


# ========================================
# dHash 计算提取为全局函数，供内外部复用
# ========================================
def compute_dhash(image_array: np.ndarray) -> int:
    """
    计算图像的 dHash 值（64位整数）
    参数：
        image_array: 8-bit 灰度 ndarray (H, W)
    返回：
        dHash 值（int）
    """
    # 转为 PIL 图像
    pil_img = Image.fromarray(image_array)
    # 缩放至 9×8（宽9，高8）
    data = resize_with_padding(image_array, (9, 8))
    # 行内差分：后一列 > 前一列 → bool (8,8)
    diff = data[:, 1:] > data[:, :-1]
    # 展平为 64 位，打包为 int
    bits = diff.ravel()  # (64,)
    packed = np.packbits(bits)  # (8,) uint8
    # 使用 int.from_bytes 替代循环，更快
    return int.from_bytes(packed, 'big')


def compare_icons(
    img_a: Union[str, Image.Image, np.ndarray],
    img_b: Union[str, Image.Image, np.ndarray],
    thr:int
) -> Tuple[bool]:
    """
    比较两个图标是否一致（基于 dHash）
    参数：
        img_a, img_b: 图像输入，支持：
            - 文件路径（str）
            - PIL.Image.Image
            - NumPy ndarray（灰度 H×W 或彩色 H×W×3/4）
        thr(int):置信度阈值, 如80
    返回：
        (is_same: bool, hamming: int, confidence_score: float)
    """
    # 1. 统一转为 8-bit 灰度 ndarray (H, W)
    arr_a = to_grayscale(img_a)
    arr_b = to_grayscale(img_b)
    
    # 2. dHash 计算（调用全局函数）
    hash_a = compute_dhash(arr_a)
    hash_b = compute_dhash(arr_b)
    
    # 3. 汉明距离 + 置信度计算
    hamming_distance = (hash_a ^ hash_b).bit_count()
    confidence_score = 100.0 * (64 - hamming_distance) / 64
    
    # 只要置信度大于thr%就视为"一致"
    is_same = confidence_score >= thr
    print(f"{confidence_score}")
    return is_same


def compare_with_precomputed_hash(
    img: Union[str, Image.Image, np.ndarray],
    precomputed_hash: int,
    thr:int
) -> Tuple[bool]:
    """
    与已经得到的 dHash 哈希值进行比较。比较两个图标是否一致
    参数：
        img: 图像输入，支持：
            - 文件路径（str）
            - PIL.Image.Image
            - NumPy ndarray（灰度 H×W 或彩色 H×W×3/4）
        thr(int): 置信度阈值, 如80
    返回：
        (is_same: bool, hamming: int, confidence_score: float)
    """
    # 1. 转为 8-bit 灰度 ndarray
    gray_arr = to_grayscale(img)
    
    # 2. 计算待比较图像的 dHash
    cur_hash = compute_dhash(gray_arr)

    # 检查哈希值是否为0
    if cur_hash == 0:
        print("疑似无UI, 图像哈希值为0")
        #  直接返回不一致
        return False

    # 3. 汉明距离与置信度计算
    hamming_distance = (cur_hash ^ precomputed_hash).bit_count()
    confidence_score = 100.0 * (64 - hamming_distance) / 64
    
    # 只要置信度大于thr%就视为"一致"
    is_same = confidence_score >= thr
    # print(f"置信度：{confidence_score}")
    
    return is_same


# ========================================
# 新增接口函数，供外部程序获取图像哈希
# ========================================
def get_image_hash(img: Union[str, Image.Image, np.ndarray]) -> int:
    """
    计算单张图像的 dHash 值（64位整数）
    参数：
        img: 图像输入，支持：
            - 文件路径（str）
            - PIL.Image.Image
            - NumPy ndarray（灰度 H×W 或彩色 H×W×3/4）
    返回：
        dHash 值（int），与 compare_icons 内部计算完全一致
    """
    # 调用全局 to_grayscale 函数进行灰度转换
    gray_array = to_grayscale(img)
    # 复用全局 compute_dhash 函数计算哈希值
    return compute_dhash(gray_array)


# ========================================
# 示例用法（直接运行时执行）
# ========================================
if __name__ == "__main__":
    # 请替换为你的图标路径
    ICON_A = "ADS接管_标准.png"
    ICON_B = "ADS接管.png"
    result = compare_icons(ICON_A, ICON_B, 80)
    print("比较完成:", result)
    
    # 新增接口函数使用示例
    hash_val = get_image_hash(ICON_A)
    print(f"图像 {ICON_A} 的 dHash 值: {hash_val}")