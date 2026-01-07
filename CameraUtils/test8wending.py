#!/usr/bin/env python
# -*- coding: utf-8 -*-
# --------------------------------------------------------------
# 亮度增强与噪声抑制流水线（带时间统计）
# --------------------------------------------------------------
# 1️⃣ 读取图像并分离 YUV
# 2️⃣ 导向滤波 + 边缘恢复
# 3️⃣ 自适应中位数阈值迭代 → 低亮度压缩
# 4️⃣ 亮度增强（Fast‑Retinex + 分段伽马）或直接使用原始 Y 通道
# 5️⃣ 锐化（可选）
# 6️⃣ Otsu 二值化 + 小面积噪声去除
# 7️⃣ 彩色图合成
# 8️⃣ 保存所有阶段结果（可通过开关统一控制）
# --------------------------------------------------------------

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any
import time   # ← 用于时间统计

# ============================= 参数 ============================= #
# ---------- 开关 ----------
ENABLE_FAST_RETINEX   = False   # True → Fast‑Retinex + 分段伽马；False → 直接使用原始 Y（仅压暗部）
ENABLE_GUIDED_FILTER = True    # 是否在亮度通道上执行导向滤波
ENABLE_EDGE_RESTORE  = True    # 导向滤波后是否把原始强边缘恢复回去
ENABLE_SHARPEN       = False   # 是否在亮度增强后执行锐化
ENABLE_BINARY        = True    # 是否对最终亮度图做 Otsu 二值化
ENABLE_SAVE_STAGES   = False    # **新增**：是否保存所有中间阶段（final_color 始终保存）

# ---------- Fast‑Retinex ----------
FAST_RETINEX_SIGMA = 80          # 高斯模糊的标准差（尺度），越大平滑范围越广
FAST_RETINEX_GAIN  = 128.0       # 增益系数，用于放大对数差分的幅度
FAST_RETINEX_OFFSET = 0.0        # 偏置，可在需要时微调整体亮度

# ---------- 分段伽马 ----------
HIGH_LIGHT_THRESH = 200          # 伽马分段阈值：<= 此值使用 gamma_high，> 此值使用 gamma_low
GAMMA_LOW  = 0.6                 # 对高亮区使用的 gamma（<1 ⇒ 亮度提升）
GAMMA_HIGH = 1.2                 # 对暗部使用的 gamma（>1 ⇒ 亮度压暗）

# ---------- 路径 ----------
INPUT_PATH   = "CameraUtils/NEW_warped.jpg"   # 待处理的原始图像路径
OUTPUT_DIR   = Path("./output")               # 所有阶段结果的保存目录

# ---------- 其余处理 ----------
ITERATIONS   = 10               # 自适应中位数阈值的最大迭代次数
GUIDED_RADIUS = 12              # 导向滤波的局部窗口半径（越大越平滑）
GUIDED_EPS    = 1e-3            # 导向滤波的正则化项，控制平滑强度
CANNY_LOW          = 50        # Canny 边缘检测的低阈值
CANNY_HIGH         = 150       # Canny 边缘检测的高阈值
DILATE_KERNEL_SIZE = 2         # 边缘膨胀的结构元素尺寸（用于扩大恢复的边缘）
DILATE_ITERATIONS  = 1         # 边缘膨胀的迭代次数
SHARPEN_AMOUNT = 1             # 锐化时高频分量的加权系数
SHARPEN_KERNEL_SIZE = 3        # 锐化时高斯模糊的核大小（必须为奇数）
SHARPEN_SIGMA = 0.0            # 锐化时高斯模糊的 sigma（0 ⇒ 自动计算）
BINARY_THRESHOLD = 210         # （保留）手动阈值，当前不直接使用（预留）
HIGH_BRIGHTNESS_OFFSET = 30    # （保留）亮度偏移量，若后续需要可用于后处理
# =========================================================== #

# ------------------- 时间统计工具 ------------------- #
_step_times: Dict[str, float] = {}

def _time_it(step_name: str) -> Any:
    """上下文管理器：记录 step_name 对应代码块的耗时（毫秒）。"""
    class _Timer:
        def __enter__(self):
            self.t0 = time.perf_counter()
            return None
        def __exit__(self, exc_type, exc_val, exc_tb):
            elapsed = (time.perf_counter() - self.t0) * 1000.0
            _step_times[step_name] = elapsed
            print(f"[TIME] {step_name:<30} {elapsed:8.2f} ms")
    return _Timer()

def print_time_summary() -> None:
    """统一输出所有步骤的耗时表。"""
    print("\n===== 运行时间统计 =====")
    total = sum(_step_times.values())
    for name, ms in _step_times.items():
        print(f"{name:<30} {ms:8.2f} ms")
    print(f"{'TOTAL':<30} {total:8.2f} ms")
    print("=========================\n")

# ------------------- 基础工具 ------------------- #
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

# ------------------- Fast‑Retinex ------------------- #
def fast_retinex(y: np.ndarray,
                 sigma: int = FAST_RETINEX_SIGMA,
                 gain: float = FAST_RETINEX_GAIN,
                 offset: float = FAST_RETINEX_OFFSET) -> np.ndarray:
    img = y.astype(np.float32) + 1.0
    log_img = np.log10(img)
    blur = cv2.GaussianBlur(img, (0, 0), sigmaX=sigma, sigmaY=sigma)
    log_blur = np.log10(blur + 1.0)
    ret = log_img - log_blur
    ret = gain * (ret + offset)
    ret = cv2.normalize(ret, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    return ret.astype(np.uint8)

# ------------------- 分段伽马 ------------------- #
def piecewise_gamma(y: np.ndarray,
                    high_thresh: int = HIGH_LIGHT_THRESH,
                    gamma_low: float = GAMMA_LOW,
                    gamma_high: float = GAMMA_HIGH) -> np.ndarray:
    y_norm = y.astype(np.float32) / 255.0
    low_mask  = y <= high_thresh
    high_mask = ~low_mask
    out = np.empty_like(y_norm)
    out[low_mask]  = np.power(y_norm[low_mask], gamma_high)
    out[high_mask] = np.power(y_norm[high_mask], gamma_low)
    out = np.clip(out * 255.0, 0, 255).astype(np.uint8)
    return out

# ------------------- 自适应迭代中位数阈值 ------------------- #
def adaptive_median_threshold(y: np.ndarray,
                             max_iter: int = ITERATIONS,
                             stop_median: int = HIGH_LIGHT_THRESH) -> Tuple[List[int], int]:
    flat_sorted = np.sort(y.ravel())[::-1]
    n = flat_sorted.size
    thresholds: List[int] = []
    cur_len = n
    for i in range(max_iter):
        if cur_len == 0:
            break
        median_idx = (cur_len - 1) // 2
        median_val = int(flat_sorted[median_idx])
        thresholds.append(median_val)
        if median_val > stop_median:
            break
        cur_len = median_idx + 1
    best_iter = 1
    if len(thresholds) > 1:
        diffs = [abs(thresholds[i] - thresholds[i - 1]) for i in range(1, len(thresholds))]
        min_diff_idx = int(np.argmin(diffs))
        best_iter = min_diff_idx + 2
    print(f"[INFO] 迭代阈值 (A,B,…,Tₙ) = {thresholds}")
    print(f"[INFO] 最佳迭代轮数 = 第 {best_iter} 次 → 阈值 = {thresholds[best_iter-1]}")
    return thresholds, best_iter

def compress_low_levels(y: np.ndarray, thr: int) -> np.ndarray:
    yc = y.copy()
    yc[yc < thr] = thr
    return yc

# ------------------- 锐化 ------------------- #
def sharpen_unsharp_mask(gray: np.ndarray,
                        amount: float = SHARPEN_AMOUNT,
                        ksize: int = SHARPEN_KERNEL_SIZE,
                        sigma: float = SHARPEN_SIGMA) -> np.ndarray:
    blurred = cv2.GaussianBlur(gray, (ksize, ksize), sigmaX=sigma, sigmaY=sigma)
    high_freq = cv2.subtract(gray, blurred)
    sharpened = cv2.addWeighted(gray, 1.0, high_freq, amount, 0)
    return sharpened

# ------------------- Otsu 二值化 ------------------- #
def otsu_binary(gray: np.ndarray) -> np.ndarray:
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    print(f"[INFO] Otsu 自动阈值 = {_:.2f}")
    return binary

# ------------------- 加速版 导向滤波 ------------------- #
def fast_guided_filter(y_uint8: np.ndarray,
                       radius: int = GUIDED_RADIUS,
                       eps: float = GUIDED_EPS) -> np.ndarray:
    """
    单通道 Y 的快速导向滤波（只调用一次 cv2.ximgproc.guidedFilter）。
    """
    I = y_uint8.astype(np.float32) / 255.0          # 归一化到 [0,1]
    out = cv2.ximgproc.guidedFilter(I, I, radius, eps)
    return (out * 255).astype(np.uint8)

# ------------------- 加速版 边缘恢复 ------------------- #
def restore_edges(original_y: np.ndarray,
                  filtered_y: np.ndarray,
                  low: int = CANNY_LOW,
                  high: int = CANNY_HIGH,
                  dilate_k: int = DILATE_KERNEL_SIZE,
                  iterations: int = DILATE_ITERATIONS) -> np.ndarray:
    """
    1️⃣ Canny 检测原始强边缘  
    2️⃣ 可选膨胀扩大边缘宽度  
    3️⃣ 用 np.copyto 把原始像素写回到滤波结果对应位置
    """
    edges = cv2.Canny(original_y, low, high)
    if dilate_k > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                           (dilate_k, dilate_k))
        edges = cv2.dilate(edges, kernel, iterations=iterations)
    mask = edges.astype(bool)
    np.copyto(filtered_y, original_y, where=mask)
    return filtered_y

# ------------------- 统计信息 ------------------- #
def calculate_y_median(y_channel: np.ndarray, name: str = "Y通道") -> float:
    median = float(np.median(y_channel))
    print(f"\n📊 {name} 中位数 = {median:.2f}")
    return median

# ------------------- 保存帮助函数 ------------------- #
def save_stage(name: str, img: np.ndarray) -> None:
    path = OUTPUT_DIR / f"{name}.png"
    cv2.imwrite(str(path), img)
    print(f"[INFO] 已保存: {path}")

# ✅ 小面积噪声去除（连通域分析） ----------
def remove_small_noise_regions(binary_mask: np.ndarray,
                               min_area: int = 150) -> np.ndarray:
    """
    移除二值图像中面积小于 min_area 的白色连通区域，保留大区域。
    """
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_mask,
                                                                  connectivity=8)
    clean_mask = np.zeros_like(binary_mask)
    for label in range(1, num_labels):          # 跳过背景 (label 0)
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_area:
            clean_mask[labels == label] = 255
    return clean_mask

# ============================= 主流程 ============================= #
def main() -> None:
    ensure_dir(OUTPUT_DIR)

    # ------------------- 1️⃣ 读取图像并分离 YUV ------------------- #
    with _time_it("load_image & split YUV"):
        img_bgr = load_image(INPUT_PATH)
        Y_orig, U, V = rgb2yuv(img_bgr)
        if ENABLE_SAVE_STAGES:
            save_stage("Y_original", Y_orig)

    # ------------------- 2️⃣ 导向滤波 + 边缘恢复 ------------------- #
    with _time_it("guided filter + edge restore"):
        Y_tmp = Y_orig.copy()
        if ENABLE_GUIDED_FILTER:
            Y_tmp = fast_guided_filter(Y_tmp,
                                       radius=GUIDED_RADIUS,
                                       eps=GUIDED_EPS)
            print("[INFO] 导向滤波已启用（fast_guided_filter）")
        if ENABLE_EDGE_RESTORE:
            Y_tmp = restore_edges(Y_orig, Y_tmp,
                                  low=CANNY_LOW, high=CANNY_HIGH,
                                  dilate_k=DILATE_KERNEL_SIZE,
                                  iterations=DILATE_ITERATIONS)
            print("[INFO] 边缘恢复已启用（restore_edges）")
        if ENABLE_SAVE_STAGES:
            save_stage("Y_guided_edge", Y_tmp)

    # ------------------- 3️⃣ 自适应中位数阈值 & 低亮度压缩 ------------------- #
    with _time_it("adaptive median threshold"):
        thresholds, best_iter = adaptive_median_threshold(
            Y_tmp, max_iter=ITERATIONS, stop_median=HIGH_LIGHT_THRESH)
        best_thr = thresholds[best_iter - 1]

    with _time_it("compress low levels"):
        Y_compressed = compress_low_levels(Y_tmp, best_thr)
        Y_denoised = Y_compressed   # 预留位置，后续若加入其它去噪可直接在此修改
        if ENABLE_SAVE_STAGES:
            save_stage("Y_compressed_denoised", Y_denoised)

    # ------------------- 4️⃣ 亮度增强（Fast‑Retinex + 分段伽马）或原始 Y ------------------- #
    with _time_it("brightness enhancement"):
        if ENABLE_FAST_RETINEX:
            Y_enhanced = fast_retinex(Y_denoised)
            print("[INFO] 使用 Fast‑Retinex 进行亮度增强")
            Y_enhanced = piecewise_gamma(Y_enhanced)   # 必须做分段伽马
        else:
            Y_enhanced = Y_denoised.copy()
            print("[INFO] 直接使用原始 Y 通道（已完成低亮度压缩），不做伽马校正")
        if ENABLE_SAVE_STAGES:
            save_stage("Y_brightness_gamma", Y_enhanced)

    # ------------------- 5️⃣ 锐化 ------------------- #
    with _time_it("sharpen"):
        if ENABLE_SHARPEN:
            Y_sharpened = sharpen_unsharp_mask(Y_enhanced,
                                               amount=SHARPEN_AMOUNT,
                                               ksize=SHARPEN_KERNEL_SIZE,
                                               sigma=SHARPEN_SIGMA)
            print("[INFO] 锐化已启用")
        else:
            Y_sharpened = Y_enhanced.copy()
        if ENABLE_SAVE_STAGES:
            save_stage("Y_sharpened", Y_sharpened)

    # ------------------- 6️⃣ 二值化 + 小噪声去除 ------------------- #
    if ENABLE_BINARY:
        with _time_it("otsu binary"):
            Y_binary = otsu_binary(Y_sharpened)
            if ENABLE_SAVE_STAGES:
                save_stage("Y_binary", Y_binary)
            print("[INFO] Otsu 二值化已完成")
        with _time_it("remove small noise"):
            MIN_AREA_THRESHOLD = 150
            Y_binary_clean = remove_small_noise_regions(Y_binary,
                                                        min_area=MIN_AREA_THRESHOLD)
            if ENABLE_SAVE_STAGES:
                save_stage("Y_binary_cleaned", Y_binary_clean)
            print(f"[INFO] 已移除面积 < {MIN_AREA_THRESHOLD} 的噪声区域")
    else:
        Y_binary_clean = None
        print("[INFO] 二值化已关闭")

    # ------------------- 7️⃣ 合成最终彩色图 ------------------- #
    with _time_it("reconstruct final color"):
        if Y_binary_clean is not None:
            mask_white = Y_binary_clean == 255
            Y_final = np.zeros_like(Y_sharpened)
            U_final = np.full_like(U, 128)
            V_final = np.full_like(V, 128)
            Y_final[mask_white] = Y_orig[mask_white]
            U_final[mask_white] = U[mask_white]
            V_final[mask_white] = V[mask_white]
        else:
            Y_final = Y_sharpened
            U_final = U
            V_final = V
        yuv_final = cv2.merge([Y_final, U_final, V_final])
        final_color = cv2.cvtColor(yuv_final, cv2.COLOR_YUV2BGR)
        save_stage("final_color", final_color)   # final_color 必保存

    # ------------------- 8️⃣ 保存原始图（便于对比） ------------------- #
    with _time_it("save original BGR"):
        save_stage("orig_bgr", img_bgr)

    # ------------------- 统计时间 ------------------- #
    print_time_summary()
    print(f"\n[INFO] 所有结果已保存至: {OUTPUT_DIR.resolve()}\n")

if __name__ == "__main__":
    main()