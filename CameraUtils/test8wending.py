#!/usr/bin/env python
# -*- coding: utf-8 -*-
# --------------------------------------------------------------
# 1️⃣ 读取图像并分离 YUV
# 2️⃣ 导向滤波 + 边缘恢复
# 3️⃣ 自适应中位数阈值迭代 → 低亮度压缩
# 4️⃣ 亮度增强（Fast‑Retinex + 全局 γ）或仅使用原始 Y 通道
# 5️⃣ 锐化（可选）
# 6️⃣ Otsu 二值化 + 小面积噪声去除（新增开关控制）
# 7️⃣ 彩色图合成
# 8️⃣ 只保存最终彩色图（final_color.png）
# --------------------------------------------------------------
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any
import time   # 用于时间统计
# ============================= 参数 ============================= #
# ---------- 开关 ----------
ENABLE_FAST_RETINEX   = False   # True → Fast‑Retinex + 全局 γ；False → 直接使用原始 Y（仅压暗部）
ENABLE_GUIDED_FILTER = False   # 是否在亮度通道上执行导向滤波
ENABLE_EDGE_RESTORE  = False   # 导向滤波后是否把原始强边缘恢复回去
ENABLE_SHARPEN       = False   # 是否在亮度增强后执行锐化
ENABLE_BINARY        = True    # 是否对最终亮度图做 Otsu 二值化
ENABLE_SMALL_NOISE_REMOVE = True  # 是否启用小面积噪声去除（新增开关）
# ---------- Fast‑Retinex ----------
FAST_RETINEX_SIGMA = 80          # 高斯模糊的标准差（尺度），越大平滑范围越广
FAST_RETINEX_GAIN  = 128.0       # 增益系数，用于放大对数差分的幅度
FAST_RETINEX_OFFSET = 0.0        # 偏置，可在需要时微调整体亮度
# ---------- 全局伽马 ----------
GLOBAL_GAMMA = 0.8               # <1 ⇒ 提亮整体；>1 ⇒ 整体变暗
# ---------- 路径 ----------
INPUT_PATH   = "CameraUtils/NEW_warped.jpg"   # 待处理的原始图像路径
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
MIN_AREA_THRESHOLD = 30      # 小面积噪声去除阈值（像素）
# ---------- Fast‑Retinex 加速选项 ----------
RETINEX_DOWNSAMPLE_SCALE = 2          # 1 → 不降采样；2 → 1/2 分辨率；4 → 1/4 分辨率 …
RETINEX_USE_BOXFILTER   = True       # True → 用积分图实现的 boxFilter（近似高斯，极快）
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
# ------------------- 全局伽马 ------------------- #
def global_gamma(y: np.ndarray, gamma: float = GLOBAL_GAMMA) -> np.ndarray:
    """对整幅亮度通道统一做 γ 变换。"""
    y_norm = y.astype(np.float32) / 255.0
    out = np.power(y_norm, gamma)
    out = np.clip(out * 255.0, 0, 255).astype(np.uint8)
    return out
# ------------------- 自适应迭代中位数阈值（直方图 O(n)） ------------------- #
def adaptive_median_threshold(y: np.ndarray,
                              max_iter: int = ITERATIONS,
                              stop_median: int = 200) -> Tuple[List[int], int]:
    """使用 256 桶直方图的 O(n) 实现，功能等价于原来的 adaptive_median_threshold。"""
    hist = np.bincount(y.ravel(), minlength=256)   # 统计全图直方图
    total_pixels = y.size
    thresholds: List[int] = []
    cur_len = total_pixels
    for _ in range(max_iter):
        if cur_len == 0:
            break
        target = (cur_len - 1) // 2          # 中位数的索引（0‑based）
        cum = 0
        median_val = 0
        for v in range(255, -1, -1):         # 从大到小累计
            cum += hist[v]
            if cum > target:
                median_val = v
                break
        thresholds.append(median_val)
        if median_val > stop_median:
            break
        # 只保留 >= median_val 的像素作为下一轮候选
        cur_len = int(hist[median_val:].sum())
        hist[:median_val] = 0   # 清零低位
    # ----- 选取最佳迭代次数（保持原逻辑） -----
    best_iter = 1
    if len(thresholds) > 1:
        diffs = [abs(thresholds[i] - thresholds[i - 1]) for i in range(1, len(thresholds))]
        min_diff_idx = int(np.argmin(diffs))
        best_iter = min_diff_idx + 2   # +2 因为 diffs 索引比 thresholds 小 1，且要取“后一次”
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
    _, binary = cv2.threshold(gray, 0, 255,
                             cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    print(f"[INFO] Otsu 自动阈值 = {_:.2f}")
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
    print(f"[INFO] 已保存: {path}")
# ============================= 主流程 ============================= #
def main() -> None:
    """主流程（经过“跳过无效步骤”优化的版本）"""
    ensure_dir(OUTPUT_DIR)

    # -------------------------------------------------
    # 1️⃣ 读取图像并拆分 YUV
    # -------------------------------------------------
    with _time_it("load_image & split YUV"):
        img_bgr = load_image(INPUT_PATH)
        Y_orig, U, V = rgb2yuv(img_bgr)

    # -------------------------------------------------
    # 2️⃣ 导向滤波 + 边缘恢复（仅在需要时执行）
    # -------------------------------------------------
    # 这里直接把 Y_tmp 指向 Y_orig，只有在需要修改时才复制一次。
    Y_tmp = Y_orig  # 可能是原图的引用，也可能是拷贝（下面会处理）

    if ENABLE_GUIDED_FILTER or ENABLE_EDGE_RESTORE:
        # 必须拷贝一次，后面的滤波/恢复会改写数据
        Y_tmp = Y_orig.copy()

        if ENABLE_GUIDED_FILTER:
            with _time_it("guided filter"):
                Y_tmp = fast_guided_filter(
                    Y_tmp,
                    radius=GUIDED_RADIUS,
                    eps=GUIDED_EPS,
                )
                print("[INFO] 导向滤波已启用（fast_guided_filter）")

        if ENABLE_EDGE_RESTORE:
            with _time_it("edge restore"):
                Y_tmp = restore_edges(
                    Y_orig,
                    Y_tmp,
                    low=CANNY_LOW,
                    high=CANNY_HIGH,
                    dilate_k=DILATE_KERNEL_SIZE,
                    iterations=DILATE_ITERATIONS,
                )
                print("[INFO] 边缘恢复已启用（restore_edges）")
    else:
        print("[INFO] 导向滤波 & 边缘恢复均已关闭，直接使用原始 Y 通道")

    # -------------------------------------------------
    # 3️⃣ 自适应中位数阈值 & 低亮度压缩
    # -------------------------------------------------
    with _time_it("adaptive median threshold"):
        thresholds, best_iter = adaptive_median_threshold(
            Y_tmp, max_iter=ITERATIONS, stop_median=200
        )
        best_thr = thresholds[best_iter - 1]

    with _time_it("compress low levels"):
        # 直接在 Y_tmp 上做压缩，省掉一次拷贝
        Y_tmp = compress_low_levels(Y_tmp, best_thr)

    # -------------------------------------------------
    # 4️⃣ 亮度增强（Fast‑Retinex + 全局 γ）——可选
    # -------------------------------------------------
    if ENABLE_FAST_RETINEX:
        with _time_it("fast_retinex"):
            Y_tmp = fast_retinex_fast(Y_tmp)          # 已在内部完成降采样/上采样
        with _time_it("global_gamma"):
            Y_tmp = global_gamma(Y_tmp, gamma=GLOBAL_GAMMA)
        print("[INFO] 已完成 Fast‑Retinex + 全局 γ 亮度增强")
    else:
        print("[INFO] Fast‑Retinex 已关闭，使用压缩后的 Y 通道作为增强基准")

    # -------------------------------------------------
    # 5️⃣ 锐化（可选）
    # -------------------------------------------------
    if ENABLE_SHARPEN:
        with _time_it("sharpen"):
            Y_tmp = sharpen_unsharp_mask(
                Y_tmp,
                amount=SHARPEN_AMOUNT,
                ksize=SHARPEN_KERNEL_SIZE,
                sigma=SHARPEN_SIGMA,
            )
            print("[INFO] 锐化已启用")
    else:
        print("[INFO] 锐化已关闭")

    # -------------------------------------------------
    # 6️⃣ Otsu 二值化 + 小噪声去除（可选）
    # -------------------------------------------------
    Y_binary_clean = None  # 统一的占位变量，后面拼接时判断是否为 None
    if ENABLE_BINARY:
        with _time_it("otsu binary"):
            Y_binary = otsu_binary(Y_tmp)
        
        # 新增开关控制小面积噪声去除
        if ENABLE_SMALL_NOISE_REMOVE:
            with _time_it("remove small noise"):
                Y_binary_clean = remove_small_noise_regions(
                    Y_binary, min_area=MIN_AREA_THRESHOLD
                )
            print(f"[INFO] 二值化 + 小噪声去除已完成（阈值={MIN_AREA_THRESHOLD}）")
        else:
            Y_binary_clean = Y_binary.copy()
            print("[INFO] 小噪声去除已关闭，仅执行二值化")
    else:
        print("[INFO] 二值化已关闭")

    # -------------------------------------------------
    # 7️⃣ 合成最终彩色图（只保存 final_color.png）
    # -------------------------------------------------
    with _time_it("reconstruct final color"):
        if Y_binary_clean is not None:                     # 需要根据 mask 把原始颜色拷回
            mask = Y_binary_clean == 255
            # 只在需要时创建新数组，避免无意义的全量拷贝
            Y_final = np.zeros_like(Y_tmp)
            U_final = np.full_like(U, 128)
            V_final = np.full_like(V, 128)

            Y_final[mask] = Y_orig[mask]
            U_final[mask] = U[mask]
            V_final[mask] = V[mask]
        else:                                              # 直接使用当前的 Y 通道
            Y_final = Y_tmp
            U_final = U
            V_final = V

        yuv_final = cv2.merge([Y_final, U_final, V_final])
        final_color = cv2.cvtColor(yuv_final, cv2.COLOR_YUV2BGR)

        # 只保存最终结果
        save_stage("final_color", final_color)

    # -------------------------------------------------
    # 8️⃣ 时间统计 & 结束提示
    # -------------------------------------------------
    print_time_summary()
    print(f"\n[INFO] 结果已保存至: {OUTPUT_DIR.resolve()}\n")


if __name__ == "__main__":
    main()