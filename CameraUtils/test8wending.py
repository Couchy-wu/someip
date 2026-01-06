#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
流程（带开关）：
1️⃣ （可选）导向滤波 → 2️⃣ （可选）边缘恢复
3️⃣ 迭代中位数阈值 → 低亮度压缩 → 直方图拉伸
4️⃣ （可选）锐化
5️⃣ （可选）二值化（单阈值）
6️⃣ 合并 U、V → BGR
7️⃣ 保存所有关键结果（不产生二值图、轮廓图或可视化窗口）
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict

# ============================= 参数 ============================= #
# ----------- 开关 ----------
ENABLE_GUIDED_FILTER = True      # 导向滤波开关
ENABLE_EDGE_RESTORE  = True      # 边缘恢复开关
ENABLE_SHARPEN       = True      # 锐化开关
ENABLE_BINARY        = True      # 二值化开关（新增）

# ----------- 路径 ----------
INPUT_PATH   = "CameraUtils/test_warped_1080.jpg"   # ← 改成自己的路径
OUTPUT_DIR   = Path("./output")                     # 结果保存目录

# ----------- 处理流程 ----------
ITERATIONS   = 5            # 中位数阈值迭代次数 N

# ----------- 导向滤波 ----------
GUIDED_RADIUS = 12
GUIDED_EPS    = 1e-3

# ----------- 边缘恢复 ----------
CANNY_LOW          = 50
CANNY_HIGH         = 150
DILATE_KERNEL_SIZE = 2   # 0 → 不进行膨胀
DILATE_ITERATIONS  = 1

# ----------- 锐化 ----------
SHARPEN_AMOUNT = 2.5         # 细节放大系数
SHARPEN_KERNEL_SIZE = 5       # 高斯模糊核大小（奇数）
SHARPEN_SIGMA = 0.0           # 0 → 自动计算

# ----------- 二值化 ----------
BINARY_THRESHOLD = 100      # 单阈值二值化阈值（0~255）
# =========================================================== #

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"无法读取图像文件: {path}")
    print(f"[INFO] 已加载图像: {path}   shape={img.shape}")
    return img

def rgb2yuv(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
    return yuv[:, :, 0], yuv[:, :, 1], yuv[:, :, 2]

def iterative_median_threshold(y: np.ndarray, n_iter: int) -> List[int]:
    """迭代求中位数阈值：A → B → C … (返回阈值列表)。"""
    thresholds = []
    mask = np.ones_like(y, dtype=bool)   # 初始保留全部像素
    for i in range(n_iter):
        vals = y[mask]
        median = int(np.median(vals)) if vals.size else 255
        thresholds.append(median)
        mask = mask & (y >= median)      # 只保留 >= 当前 median 的像素
        print(f"[DEBUG] 迭代 {i+1}/{n_iter} → median = {median}, 剩余像素数 = {mask.sum()}")
    return thresholds

def compress_low_levels(y: np.ndarray, thr: int) -> np.ndarray:
    """把所有 < thr 的像素提升为 thr（即把 [0,thr) → thr）。"""
    yc = y.copy()
    yc[yc < thr] = thr
    return yc

def stretch_histogram(y: np.ndarray, low: int) -> np.ndarray:
    """把区间 [low,255] 线性映射到 [0,255]。"""
    scale = 255.0 / max(1, 255 - low)
    yst = ((y.astype(np.float32) - low) * scale).clip(0, 255)
    return yst.astype(np.uint8)

def apply_edge_preserving_smooth(gray_uint8: np.ndarray,
                                 radius: int = GUIDED_RADIUS,
                                 eps: float = GUIDED_EPS) -> np.ndarray:
    """
    Edge‑Preserving Guided Filter（若无 ximgproc 则回退）。
    返回 uint8 图像。
    """
    try:
        if hasattr(cv2.ximgproc, "createFastGuidedFilter"):
            I = gray_uint8.astype(np.float32) / 255.0
            fast = cv2.ximgproc.createFastGuidedFilter(I, radius, eps)
            out = fast.filter(I)
            return (out * 255).astype(np.uint8)
        if hasattr(cv2.ximgproc, "guidedFilter"):
            I = gray_uint8.astype(np.float32) / 255.0
            out = cv2.ximgproc.guidedFilter(I, I, radius, eps)
            return (out * 255).astype(np.uint8)
        # fallback: OpenCV 自带的 edgePreservingFilter
        return cv2.edgePreservingFilter(gray_uint8, flags=1, sigma_s=60, sigma_r=0.4)
    except Exception as e:
        print(f"[WARN] 导向滤波失效，回退至 bilateralFilter，原因: {e}")
        return cv2.bilateralFilter(gray_uint8, d=9, sigmaColor=75, sigmaSpace=75)

def edge_restore_on_y(original_y: np.ndarray,
                     processed_y: np.ndarray,
                     low: int = CANNY_LOW,
                     high: int = CANNY_HIGH,
                     dilate_k: int = DILATE_KERNEL_SIZE,
                     iterations: int = DILATE_ITERATIONS) -> np.ndarray:
    """
    用原始 Y 的强 Canny 边缘把已经平滑的 Y 中被抹掉的细节恢复回来。
    """
    edges = cv2.Canny(original_y, low, high)
    if dilate_k > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                           (dilate_k, dilate_k))
        edges = cv2.dilate(edges, kernel, iterations=iterations)
    mask = edges != 0
    out = processed_y.copy()
    out[mask] = original_y[mask]
    return out

def sharpen_unsharp_mask(gray: np.ndarray,
                        amount: float = SHARPEN_AMOUNT,
                        ksize: int = SHARPEN_KERNEL_SIZE,
                        sigma: float = SHARPEN_SIGMA) -> np.ndarray:
    """Unsharp‑Mask 锐化：gray + amount * (gray - blur(gray))"""
    blurred = cv2.GaussianBlur(gray, (ksize, ksize), sigmaX=sigma, sigmaY=sigma)
    high_freq = cv2.subtract(gray, blurred)
    sharpened = cv2.addWeighted(gray, 1.0, high_freq, amount, 0)
    return sharpened

def simple_binary_threshold(gray: np.ndarray,
                            thresh: int = BINARY_THRESHOLD,
                            maxval: int = 255) -> np.ndarray:
    """
    单阈值二值化（阈值为 `thresh`），返回 0 / `maxval` 的 uint8 图像。
    若后期想尝试 Otsu，只需把 `cv2.threshold(..., cv2.THRESH_OTSU)` 替换进去。
    """
    _, binary = cv2.threshold(gray, thresh, maxval, cv2.THRESH_BINARY)
    return binary

def calculate_y_stats(y_channel: np.ndarray, name: str = "Y通道") -> Dict[str, float]:
    stats = {
        "平均值": float(np.mean(y_channel)),
        "中位数": float(np.median(y_channel)),
        "标准差": float(np.std(y_channel)),
        "最小值": int(np.min(y_channel)),
        "最大值": int(np.max(y_channel)),
    }
    print(f"\n📊 {name} 统计信息:")
    for k, v in stats.items():
        print(f"  {k}: {v:.2f}")
    return stats

# ============================= 主流程 ============================= #
def main() -> None:
    ensure_dir(OUTPUT_DIR)

    # -------------------------------------------------
    # 1️⃣ 读取图像并分离 YUV
    # -------------------------------------------------
    img_bgr = load_image(INPUT_PATH)
    Y_orig, U, V = rgb2yuv(img_bgr)

    # -------------------------------------------------
    # 2️⃣ （可选）导向滤波
    # -------------------------------------------------
    if ENABLE_GUIDED_FILTER:
        Y_tmp = apply_edge_preserving_smooth(Y_orig,
                                             radius=GUIDED_RADIUS,
                                             eps=GUIDED_EPS)
        print("[INFO] 导向滤波已启用")
        cv2.imwrite(str(OUTPUT_DIR / "Y_guided.png"), Y_tmp)
    else:
        Y_tmp = Y_orig.copy()
        print("[INFO] 导向滤波已关闭（使用原始 Y）")

    # -------------------------------------------------
    # 3️⃣ （可选）边缘恢复
    # -------------------------------------------------
    if ENABLE_EDGE_RESTORE:
        Y_tmp = edge_restore_on_y(Y_orig, Y_tmp,
                                 low=CANNY_LOW,
                                 high=CANNY_HIGH,
                                 dilate_k=DILATE_KERNEL_SIZE,
                                 iterations=DILATE_ITERATIONS)
        print("[INFO] 边缘恢复已启用")
        cv2.imwrite(str(OUTPUT_DIR / "Y_edge_restored.png"), Y_tmp)
    else:
        print("[INFO] 边缘恢复已关闭")

    # -------------------------------------------------
    # 4️⃣ 迭代中位数阈值 → 低亮度压缩 → 直方图拉伸
    # -------------------------------------------------
    thresholds = iterative_median_threshold(Y_tmp, ITERATIONS)
    final_thr = thresholds[-1]
    print(f"[INFO] 迭代阈值 (A,B,…,Tₙ) = {thresholds}")

    Y_compressed = compress_low_levels(Y_tmp, final_thr)
    Y_stretched  = stretch_histogram(Y_compressed, final_thr)

    cv2.imwrite(str(OUTPUT_DIR / "Y_compressed.png"), Y_compressed)
    cv2.imwrite(str(OUTPUT_DIR / "Y_stretched.png"), Y_stretched)

    # -------------------------------------------------
    # 5️⃣ （可选）锐化（在拉伸后的图上执行）
    # -------------------------------------------------
    if ENABLE_SHARPEN:
        Y_final = sharpen_unsharp_mask(Y_stretched,
                                       amount=SHARPEN_AMOUNT,
                                       ksize=SHARPEN_KERNEL_SIZE,
                                       sigma=SHARPEN_SIGMA)
        print("[INFO] 锐化已启用")
        cv2.imwrite(str(OUTPUT_DIR / "Y_sharpened.png"), Y_final)
    else:
        Y_final = Y_stretched
        print("[INFO] 锐化已关闭")

    # -------------------------------------------------
    # 6️⃣ （可选）二值化（单阈值）   ← **新增步骤**
    # -------------------------------------------------
    if ENABLE_BINARY:
        Y_binary = simple_binary_threshold(Y_final, thresh=BINARY_THRESHOLD)
        print("[INFO] 二值化已启用 (阈值 = %d)" % BINARY_THRESHOLD)
        cv2.imwrite(str(OUTPUT_DIR / "Y_binary.png"), Y_binary)
    else:
        Y_binary = None
        print("[INFO] 二值化已关闭")

    # -------------------------------------------------
    # 7️⃣ 合并 U、V → BGR（得到最终彩色图）
    # -------------------------------------------------
    yuv_final = cv2.merge([Y_final, U, V])
    final_color = cv2.cvtColor(yuv_final, cv2.COLOR_YUV2BGR)

    # -------------------------------------------------
    # 8️⃣ 保存全部关键结果（全部 PNG，保持无损）
    # -------------------------------------------------
    cv2.imwrite(str(OUTPUT_DIR / "orig_bgr.png"), img_bgr)      # 原始彩色
    cv2.imwrite(str(OUTPUT_DIR / "Y_original.png"), Y_orig)    # 原始 Y
    # 已保存的中间文件：Y_guided.png、Y_edge_restored.png、Y_compressed.png、
    #                     Y_stretched.png、Y_sharpened.png（若开启）
    #                     Y_binary.png（若开启）
    cv2.imwrite(str(OUTPUT_DIR / "final_color.png"), final_color)  # 最终彩色（含所有处理）

    print(f"[INFO] 所有结果已保存至: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()