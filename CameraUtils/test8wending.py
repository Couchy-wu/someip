#!/usr/bin/env python
# -*- coding: utf-8 -*-
# --------------------------------------------------------------
# 1️⃣ 读取图像并分离 YUV
# 2️⃣ 导向滤波 + 边缘恢复
# 3️⃣ 自适应中位数阈值迭代 → 低亮度压缩
# 4️⃣ 亮度增强（Fast‑Retinex）
# 5️⃣ 锐化（可选）
# 6️⃣ Otsu 二值化 + 小面积噪声去除
# 7️⃣ 彩色图合成（使用处理后的 Y 通道）
# 8️⃣ 只保存最终彩色图（final_color.png）
# --------------------------------------------------------------

import cv2
import numpy as np
import time                     
from pathlib import Path
from typing import List, Tuple, Dict

# ============================= 参数 ============================= #
# ---------- 开关 ----------
ENABLE_TIMING = True          # True → 记录每一步耗时
ENABLE_GUIDED_FILTER = False   # 是否在亮度通道上执行导向滤波
ENABLE_EDGE_RESTORE  = False   # 导向滤波后是否把原始强边缘恢复回去
ENABLE_FAST_RETINEX   = True   # True → Fast‑Retinex；False → 直接使用原始 Y（仅压暗部）
ENABLE_SHARPEN       = True   # 是否在亮度增强后执行锐化
ENABLE_BINARY        = True    # 是否对最终亮度图做 Otsu 二值化
ENABLE_SMALL_NOISE_REMOVE = True  # 是否启用小面积噪声去除（新增开关）

# ---------- Fast‑Retinex ----------
FAST_RETINEX_SIGMA = 80          # 高斯模糊的标准差（尺度），越大平滑范围越广
FAST_RETINEX_GAIN  = 128.0       # 增益系数，用于放大对数差分的幅度
FAST_RETINEX_OFFSET = 0.0        # 偏置，可在需要时微调整体亮度

# ---------- 路径 ----------
INPUT_PATH   = "CameraUtils/screenshot_7_warped.jpg"   # 待处理的原始图像路径
OUTPUT_DIR   = Path("./output")               # 只保存 final_color.png

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

# ---------- 全局参数 ----------
GUIDED_DOWNSAMPLE_SCALE = 1   # 导向滤波的降采样倍率（1 = 不降采样）
MIN_AREA_THRESHOLD = 50      # 小面积噪声去除阈值（像素）

# ---------- Fast‑Retinex 加速选项 ----------
RETINEX_DOWNSAMPLE_SCALE = 2          # 1 → 不降采样；2 → 1/2 分辨率；4 → 1/4 分辨率 …
RETINEX_USE_BOXFILTER   = True       # True → 用积分图实现的 boxFilter（近似高斯，极快）

# =========================================================== #
# ------------------- 基础工具 ------------------- #

def maybe_time(name: str, func, *args, **kwargs):
    """
    如果 ENABLE_TIMING 为 True，则使用 record_time 记录耗时；
    否则直接调用 func 并返回结果（不产生任何计时信息）。
    """
    if ENABLE_TIMING:
        return record_time(name, func, *args, **kwargs)
    else:
        return func(*args, **kwargs)

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"无法读取图像文件: {path}")
    return img

def rgb2yuv(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
    return yuv[:, :, 0], yuv[:, :, 1], yuv[:, :, 2]

# ------------------- Fast‑Retinex（加速版） ------------------- #
def fast_retinex_fast(y: np.ndarray,
                      sigma: int = FAST_RETINEX_SIGMA,
                      gain: float = FAST_RETINEX_GAIN,
                      offset: float = FAST_RETINEX_OFFSET,
                      scale: int = RETINEX_DOWNSAMPLE_SCALE,
                      use_box: bool = RETINEX_USE_BOXFILTER) -> np.ndarray:
    """快速 Retinex，支持降采样和盒式滤波（积分图实现）。"""
    # 1️⃣ 降采样
    if scale > 1:
        small = cv2.resize(y,
                           (y.shape[1] // scale, y.shape[0] // scale),
                           interpolation=cv2.INTER_LINEAR)
    else:
        small = y
    # 2️⃣ 转 float 并防止 log(0)
    img = small.astype(np.float32) + 1.0
    # 3️⃣ 对数
    log_img = np.log10(img)
    # 4️⃣ 平滑
    if use_box:
        ksize = max(3, int(6 * sigma) // scale | 1)   # 经验：盒式核大小 ≈ 6*sigma
        blur = cv2.boxFilter(img, ddepth=-1,
                             ksize=(ksize, ksize),
                             normalize=True)
    else:
        blur = cv2.GaussianBlur(img, (0, 0),
                                sigmaX=sigma / scale,
                                sigmaY=sigma / scale)
    # 5️⃣ 对数模糊
    log_blur = np.log10(blur + 1.0)
    # 6️⃣ Retinex 差分
    ret = log_img - log_blur
    ret = gain * (ret + offset)
    # 7️⃣ 归一化到 0‑255
    ret = cv2.normalize(ret, None, alpha=0, beta=255,
                        norm_type=cv2.NORM_MINMAX)
    # 8️⃣ 若有降采样，插值回原尺寸
    if scale > 1:
        ret = cv2.resize(ret,
                         (y.shape[1], y.shape[0]),
                         interpolation=cv2.INTER_LINEAR)
    return ret.astype(np.uint8)

# ------------------- 自适应迭代中位数阈值（直方图 O(n)） ------------------- #
def adaptive_median_threshold(
    y: np.ndarray,
    max_iter: int = ITERATIONS,
    stop_median: int = 200,
    downscale: float = 0.25,   # 下采样，0.25 → 总像素数约 1/16
    interp: int = None,        # 保留参数但不再使用，避免调用方代码出错
) -> Tuple[List[int], int]:
    """
    在可选的下采样图像上求取自适应中位数阈值序列。
    返回 (thresholds, best_iter)。若 downscale == 1.0，则行为与原实现完全相同。
    
    参数说明
    ----------
    y : np.ndarray
        输入灰度图，dtype 必须是 uint8（0‑255）。
    max_iter : int
        最大迭代次数（默认 ITERATIONS）。
    stop_median : int
        当中位数 > stop_median 时提前退出（默认 STOP_MEDIAN）。
    downscale : float
        缩放系数，<1 表示把宽高都乘以该系数（即像素数约为系数²）。
        典型取值 0.5 → 总像素数约为原来的 1/4。
    interp : int
        已弃用，不再影响下采样方式。现在使用切片下采样，计算量最小。
    """
    # -------------------------------------------------
    # 1️⃣ 使用切片进行快速下采样（无需插值，计算量最小）
    # -------------------------------------------------
    if downscale < 1.0:
        step = max(1, int(round(1.0 / downscale)))
        y_small = y[::step, ::step]
    else:
        y_small = y                     # 不下采样，直接使用原图

    # -------------------------------------------------
    # 2️⃣ 直方图一次性统计（固定 256 桶）
    # -------------------------------------------------
    hist = np.bincount(y_small.ravel(), minlength=256).astype(np.int64)
    total_pixels = y_small.size
    thresholds: List[int] = []          # 每轮得到的阈值（中位数）
    cur_len = total_pixels
    iter_cnt = 0

    # -------------------------------------------------
    # 3️⃣ 主循环：向量化累计 + 搜索中位数
    # -------------------------------------------------
    while cur_len > 0 and iter_cnt < max_iter:
        # (cur_len-1)//2 = 0‑based 中位数索引（从大到小累计时的目标位置）
        target = (cur_len - 1) // 2
        # 反向累计（大 → 小），一次性得到累计直方图
        cum_hist = np.cumsum(hist[::-1])
        # 第一个累计值 > target 的位置（右侧开区间）
        idx = np.searchsorted(cum_hist, target + 1, side='right')
        median_val = 255 - idx            # 恢复到原灰度值
        thresholds.append(int(median_val))

        # 早停条件
        if median_val > stop_median:
            break
        
        # 直接使用累计计数得到本轮保留的像素数
        cur_len = int(cum_hist[idx])
        
        # 清零低位，防止下一轮再次计入
        if median_val > 0:
            hist[:median_val] = 0

        iter_cnt += 1

    # -------------------------------------------------
    # 4️⃣ 选取最佳迭代次数（保持原逻辑）
    # -------------------------------------------------
    best_iter = 1
    if len(thresholds) > 1:
        diffs = [abs(thresholds[i] - thresholds[i - 1]) for i in range(1, len(thresholds))]
        min_diff_idx = int(np.argmin(diffs))
        best_iter = min_diff_idx + 2   # +2 因为 diffs 索引比 thresholds 小 1，且取“后一次”

    # 5️⃣ 信息打印（可自行关闭）
    # print(f"[INFO] (downscale={downscale:.2f}) 迭代阈值 = {thresholds}")
    # print(f"[INFO] 最佳迭代轮数 = 第 {best_iter} 次 → 阈值 = {thresholds[best_iter-1]}")
    return thresholds, best_iter

def compress_low_levels(y: np.ndarray, thr: int) -> np.ndarray:
    """把所有低于 thr 的像素提升到 thr """
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
    _, binary = cv2.threshold(gray, 0, 255,
                             cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # print(f"[INFO] Otsu 自动阈值 = {_:.2f}")
    return binary

# ------------------- 导向滤波（降采样‑上采样） ------------------- #
def fast_guided_filter(y_uint8: np.ndarray,
                       radius: int = GUIDED_RADIUS,
                       eps: float = GUIDED_EPS,
                       scale: int = GUIDED_DOWNSAMPLE_SCALE) -> np.ndarray:
    """降采样 → 导向滤波 → 上采样 的加速方案。"""
    if scale <= 1:
        I = y_uint8.astype(np.float32) / 255.0
        out = cv2.ximgproc.guidedFilter(I, I, radius, eps)
        return (out * 255).astype(np.uint8)

    # 1️⃣ 降采样
    small = cv2.resize(y_uint8,
                       (y_uint8.shape[1] // scale,
                        y_uint8.shape[0] // scale),
                       interpolation=cv2.INTER_LINEAR)
    # 2️⃣ 小图上导向滤波
    I_small = small.astype(np.float32) / 255.0
    radius_small = max(1, radius // scale)
    out_small = cv2.ximgproc.guidedFilter(I_small, I_small,
                                          radius_small, eps)
    # 3️⃣ 上采样回原分辨率
    up = cv2.resize(out_small,
                    (y_uint8.shape[1], y_uint8.shape[0]),
                    interpolation=cv2.INTER_LINEAR)
    return (up * 255).astype(np.uint8)

# ------------------- 边缘恢复 ------------------- #
def restore_edges(original_y: np.ndarray,
                  filtered_y: np.ndarray,
                  low: int = CANNY_LOW,
                  high: int = CANNY_HIGH,
                  dilate_k: int = DILATE_KERNEL_SIZE,
                  iterations: int = DILATE_ITERATIONS) -> np.ndarray:
    """将原始图像的强边缘写回到滤波结果中。"""
    edges = cv2.Canny(original_y, low, high)
    if dilate_k > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                           (dilate_k, dilate_k))
        edges = cv2.dilate(edges, kernel, iterations=iterations)
    mask = edges.astype(bool)
    np.copyto(filtered_y, original_y, where=mask)
    return filtered_y

# ------------------- 小面积噪声去除 ------------------- #
def remove_small_noise_regions(binary_mask: np.ndarray,
                               min_area: int = MIN_AREA_THRESHOLD) -> np.ndarray:
    """移除二值图中面积小于 min_area 的白色连通区域。"""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_mask,
                                                                  connectivity=8)
    clean_mask = np.zeros_like(binary_mask)
    for label in range(1, num_labels):          # 跳过背景 (label 0)
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_area:
            clean_mask[labels == label] = 255
    return clean_mask

# ------------------- 保存帮助函数 ------------------- #
def save_stage(name: str, img: np.ndarray) -> None:
    """统一的保存函数（仅用于最终结果）。"""
    path = OUTPUT_DIR / f"{name}.png"
    cv2.imwrite(str(path), img)

# ------------------- 重建最终彩色图（极简版 - 背景全黑） ------------------- #
def reconstruct_final_color_black_bg(
    Y_original: np.ndarray,      # 使用原始 Y 通道
    U: np.ndarray,
    V: np.ndarray,
    binary_mask: np.ndarray     
) -> np.ndarray:
    """
    使用原始 Y 通道合成彩色图，mask 区域保留，其他区域为黑色背景。
    """
    if binary_mask is None:
        # 没有 mask 时直接把原始 Y、U、V 合成 BGR
        return cv2.cvtColor(cv2.merge([Y_original, U, V]), cv2.COLOR_YUV2BGR)

    # 1️⃣ 创建全黑 BGR 背景
    result_bgr = np.zeros((Y_original.shape[0], Y_original.shape[1], 3), dtype=np.uint8)

    # 2️⃣ 用原始 Y 通道合成 YUV → BGR
    yuv_original = cv2.merge([Y_original, U, V])
    bgr_original = cv2.cvtColor(yuv_original, cv2.COLOR_YUV2BGR)

    # 3️⃣ 只复制 mask 区域（OpenCV 高效实现）
    cv2.copyTo(bgr_original, binary_mask, result_bgr)
    return result_bgr

# ============================= 计时工具 ============================= #
# 用于统一记录每一步耗时的字典
timings: Dict[str, float] = {}

def record_time(name: str, func, *args, **kwargs):
    """
    简单包装器：记录 ``func(*args, **kwargs)`` 的执行时间并返回结果。
    同时把耗时写入全局 ``timings``。
    """
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    timings[name] = elapsed
    return result

# ============================= 主流程 ============================= #
def main() -> None:
    """主流程（每一步都会记录耗时）"""
    total_start = time.perf_counter()
    ensure_dir(OUTPUT_DIR)

    # -------------------------------------------------
    # 1️⃣ 读取图像并拆分 YUV
    # -------------------------------------------------
    img_bgr = maybe_time("load_image", load_image, INPUT_PATH)
    Y_orig, U, V = rgb2yuv(img_bgr)

    # -------------------------------------------------
    # 2️⃣ 导向滤波 + 边缘恢复（仅在需要时执行）
    # -------------------------------------------------
    Y_tmp = Y_orig
    if ENABLE_GUIDED_FILTER or ENABLE_EDGE_RESTORE:
        Y_tmp = Y_orig.copy()
        if ENABLE_GUIDED_FILTER:
            Y_tmp = maybe_time("guided_filter",
                                fast_guided_filter,
                                Y_tmp,
                                radius=GUIDED_RADIUS,
                                eps=GUIDED_EPS,
                                scale=GUIDED_DOWNSAMPLE_SCALE)
        if ENABLE_EDGE_RESTORE:
            Y_tmp = maybe_time("edge_restore",
                                restore_edges,
                                Y_orig,
                                Y_tmp,
                                low=CANNY_LOW,
                                high=CANNY_HIGH,
                                dilate_k=DILATE_KERNEL_SIZE,
                                iterations=DILATE_ITERATIONS)

    # -------------------------------------------------
    # 3️⃣ 自适应中位数阈值 & 低亮度压缩
    # -------------------------------------------------
    thresholds, best_iter = maybe_time("adaptive_median",
                                        adaptive_median_threshold,
                                        Y_tmp,
                                        max_iter=ITERATIONS,
                                        stop_median=200)
    best_thr = thresholds[best_iter - 1]
    Y_tmp = maybe_time("compress_low_levels",
                        compress_low_levels,
                        Y_tmp,
                        best_thr)

    # -------------------------------------------------
    # 4️⃣ 亮度增强（Fast‑Retinex）——可选
    # -------------------------------------------------
    if ENABLE_FAST_RETINEX:
        Y_tmp = maybe_time("fast_retinex",
                            fast_retinex_fast,
                            Y_tmp)

    # -------------------------------------------------
    # 5️⃣ 锐化（可选）
    # -------------------------------------------------
    if ENABLE_SHARPEN:
        Y_tmp = maybe_time("sharpen",
                            sharpen_unsharp_mask,
                            Y_tmp,
                            amount=SHARPEN_AMOUNT,
                            ksize=SHARPEN_KERNEL_SIZE,
                            sigma=SHARPEN_SIGMA)

    # -------------------------------------------------
    # 6️⃣ Otsu 二值化 + 小噪声去除（可选）
    # -------------------------------------------------
    Y_binary_clean = None
    if ENABLE_BINARY:
        Y_binary = maybe_time("otsu_binary",
                               otsu_binary,
                               Y_tmp)

        if ENABLE_SMALL_NOISE_REMOVE:
            Y_binary_clean = maybe_time("remove_small_noise",
                                         remove_small_noise_regions,
                                         Y_binary,
                                         min_area=MIN_AREA_THRESHOLD)
        else:
            Y_binary_clean = Y_binary.copy()

    # 7️⃣ 合成最终彩色图（使用 **原始** Y 通道，只保存 final_color.png）
    final_color = maybe_time(
        "reconstruct_color",
        reconstruct_final_color_black_bg,
        Y_orig,          # ★ MOD: 传入原始亮度通道
        U,
        V,
        Y_binary_clean   # binary_mask（可能为 None）
    )

    # -------------------------------------------------
    # 8️⃣ 保存结果
    # -------------------------------------------------
    save_stage("final_color", final_color)

    total_elapsed = time.perf_counter() - total_start
    timings["total"] = total_elapsed

    # ------------------- 打印计时报告 ------------------- #
    print("\n=== 运行时间统计 (seconds) ===")
    ordered_keys = [
        ("load_image",          "加载图像"),
        ("guided_filter",       "导向滤波"),
        ("edge_restore",        "边缘恢复"),
        ("adaptive_median",     "自适应中位数阈值"),
        ("compress_low_levels", "低亮度压缩"),
        ("fast_retinex",        "Fast‑Retinex"),
        ("sharpen",             "锐化"),
        ("otsu_binary",         "Otsu 二值化"),
        ("remove_small_noise",  "小噪声去除"),
        ("reconstruct_color",   "重建彩色图"),
        ("total",               "总耗时")
    ]
    for key, label in ordered_keys:
        if key in timings:
            ms = timings[key] * 1000          # 秒 → 毫秒
            print(f"{label:20s} {ms:8.2f} ms")
    print("===============================\n")

if __name__ == "__main__":
    main()