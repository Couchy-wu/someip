#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ImageEnhancer: 用于低光照图像增强与二值化处理的完整流程封装
"""
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
from typing import Union, Tuple, List, Dict, Optional

class ImageEnhancer:
    def __init__(self, enable_timing: bool = True):
        """
        初始化增强器，所有参数设为实例属性（避免全局变量）
        """
        # ============================= 参数 ============================= #
        # ---------- 开关 ----------
        self.enable_timing = False          # True → 记录每一步耗时
        self.enable_guided_filter = False           # 是否在亮度通道上执行导向滤波
        self.enable_edge_restore  = False            # 导向滤波后是否把原始强边缘恢复回去
        self.enable_fast_retinex   = True            # True → Fast‑Retinex；False → 直接使用原始 Y（仅压暗部）
        self.enable_sharpen       = True            # 是否在亮度增强后执行锐化
        self.enable_binary        = True             # 是否对最终亮度图做 Otsu 二值化
        self.enable_small_noise_remove = True       # 是否启用小面积噪声去除（新增开关）

        # ---------- Fast‑Retinex ----------
        self.fast_retinex_sigma = 80                # 高斯模糊的标准差（尺度），越大平滑范围越广
        self.fast_retinex_gain  = 128.0            # 增益系数，用于放大对数差分的幅度
        self.fast_retinex_offset = 0.0             # 偏置，可在需要时微调整体亮度

        # ---------- 路径 ----------
        self.output_dir   = Path("./output")       # 只保存 final_color.png

        # ---------- 其余处理 ----------
        self.iterations   = 20                     # 自适应中位数阈值的最大迭代次数
        self.guided_radius = 12                     # 导向滤波的局部窗口半径（越大越平滑）
        self.guided_eps    = 1e-3                  # 导向滤波的正则化项，控制平滑强度
        self.canny_low          = 50               # Canny 边缘检测的低阈值
        self.canny_high         = 150              # Canny 边缘检测的高阈值
        self.dilate_kernel_size = 2                # 边缘膨胀的结构元素尺寸（用于扩大恢复的边缘）
        self.dilate_iterations  = 1                # 边缘膨胀的迭代次数
        self.sharpen_amount = 1                    # 锐化时高频分量的加权系数
        self.sharpen_kernel_size = 3               # 锐化时高斯模糊的核大小（必须为奇数）
        self.sharpen_sigma = 0.0                   # 锐化时高斯模糊的 sigma（0 ⇒ 自动计算）

        # ---------- 全局参数 ----------
        self.guided_downsample_scale = 1           # 导向滤波的降采样倍率（1 = 不降采样）
        self.min_area_threshold = 50               # 小面积噪声去除阈值（像素）

        # ---------- Fast‑Retinex 加速选项 ----------
        self.retinex_downsample_scale = 2          # 1 → 不降采样；2 → 1/2 分辨率；4 → 1/4 分辨率 …
        self.retinex_use_boxfilter   = True        # True → 用积分图实现的 boxFilter（近似高斯，极快）

        # --- 内部计时器 ---
        self.timings: Dict[str, float] = {}

    def _record_time(self, name: str, func, *args, **kwargs):
        """
        简单包装器：记录 ``func(*args, **kwargs)`` 的执行时间并返回结果。
        同时把耗时写入全局 ``timings``。
        """
        if not self.enable_timing:
            return func(*args, **kwargs)
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        self.timings[name] = elapsed
        return result

    def _maybe_time(self, name: str, func, *args, **kwargs):
        """
        如果 ENABLE_TIMING 为 True，则使用 record_time 记录耗时；
        否则直接调用 func 并返回结果（不产生任何计时信息）。
        """
        return self._record_time(name, func, *args, **kwargs) if self.enable_timing else func(*args, **kwargs)

    def _ensure_dir(self, p: Path) -> None:
        p.mkdir(parents=True, exist_ok=True)

    def _load_image(self, path: str) -> np.ndarray:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"无法读取图像文件: {path}")
        return img

    def _rgb2yuv(self, img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        将 BGR 图像转换为 YUV，并分离三个通道
        返回：Y, U, V 三个单通道图像
        """
        yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
        return yuv[:, :, 0], yuv[:, :, 1], yuv[:, :, 2]

    # ------------------- Fast‑Retinex（加速版） ------------------- #
    def _fast_retinex_fast(self, y: np.ndarray) -> np.ndarray:
        """
        快速 Retinex，支持降采样和盒式滤波（积分图实现）。
        参数:
            y: 输入亮度通道（uint8）
            sigma: 高斯模糊尺度
            gain: 增益系数
            offset: 偏置
            scale: 降采样倍率
            use_box: 是否使用 boxFilter 代替高斯模糊
        返回: 增强后的亮度图（uint8）
        """
        sigma = self.fast_retinex_sigma
        gain = self.fast_retinex_gain
        offset = self.fast_retinex_offset
        scale = self.retinex_downsample_scale
        use_box = self.retinex_use_boxfilter

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
    def _adaptive_median_threshold(self, y: np.ndarray) -> Tuple[List[int], int]:
        """
        在可选的下采样图像上求取自适应中位数阈值序列。
        返回 (thresholds, best_iter)。
        """
        # -------------------------------------------------
        # 参数
        # -------------------------------------------------
        max_iter = self.iterations
        stop_median = 200          # 停止迭代的最大中位数阈值
        downscale = 0.25           # 下采样参数

        # -------------------------------------------------
        # 1️⃣ 快速下采样（切片）
        # -------------------------------------------------
        if downscale < 1.0:
            step = max(1, int(round(1.0 / downscale)))
            y_small = y[::step, ::step]
        else:
            y_small = y

        # -------------------------------------------------
        # 2️⃣ 直方图一次性统计（固定 256 桶）
        # -------------------------------------------------
        hist = np.bincount(y_small.ravel(), minlength=256).astype(np.int64)
        total_pixels = y_small.size
        thresholds: List[int] = []
        cur_len = total_pixels
        iter_cnt = 0

        # -------------------------------------------------
        # 3️⃣ 主循环：向量化累计 + 搜索中位数
        # -------------------------------------------------
        while cur_len > 0 and iter_cnt < max_iter:
            target = (cur_len - 1) // 2
            cum_hist = np.cumsum(hist[::-1])                 # 反向累计
            idx = np.searchsorted(cum_hist, target + 1, side='right')
            median_val = 255 - idx
            thresholds.append(int(median_val))

            # 达到停止阈值则退出
            if median_val > stop_median:
                break

            # 把已经“小于等于 median_val”的计数归零，以便下一轮只统计更大的像素
            if median_val >= 0:
                hist[:median_val + 1] = 0

            cur_len = int(hist.sum())
            iter_cnt += 1

            # print("\n[AdaptiveMedian] 迭代阈值序列:")
            # for idx, val in enumerate(thresholds, start=1):
            #     print(f"  第 {idx:2d} 次迭代 → 中位数阈值 = {val}")

        # -------------------------------------------------
        # 4️⃣ 若未产生任何阈值，直接返回空
        # -------------------------------------------------
        N = len(thresholds)
        if N == 0:
            return [], 1

        # -------------------------------------------------
        # 5️⃣ 计算原始的 “差值最小” 作为 fallback
        # -------------------------------------------------
        original_best_iter = 1
        if len(thresholds) > 1:
            diffs = [abs(thresholds[i] - thresholds[i - 1]) for i in range(1, len(thresholds))]
        else:
            diffs = []
        if diffs:
            min_diff_idx = int(np.argmin(diffs))
            original_best_iter = min_diff_idx + 1      # 1‑based
        else:
            original_best_iter = 1

        # -------------------------------------------------
        # 6️⃣ 检测 **第一个突变**：B - A
        # -------------------------------------------------
        jump_index: int | None = None          # thresholds 中的索引（0‑based），对应 B
        for n in range(1, N):
            if thresholds[n] - thresholds[n - 1] > 30:
                jump_index = n
                break

        # -----------------------------------------------------------------
        # 🆕  新增规则：若 C 与 A 之间也存在大幅跳变，直接返回 A
        # -----------------------------------------------------------------
        if jump_index is not None:
            # A 是突变前的值（阈值列表里的 jump_index-1 位置）
            A = thresholds[jump_index - 1]          # 对应第 jump_index 次迭代（1‑based）
            # 检查是否存在 C（jump_index-2）
            if jump_index >= 2:                     # 至少要有第 n‑1 次迭代
                C = thresholds[jump_index - 2]
                if abs(A - C) > 25:                        # 判断 A 与 C 差距
                    best_iter = jump_index - 1             # 直接选 C 所在的迭代（n‑1）
                    return thresholds, best_iter
            # 若没有 C 或 C 与 A 差距 ≤50，则继续执行原有的跳变后处理逻辑
        else:
            # 没有任何突变，直接使用原始的 fallback 结果
            return thresholds, original_best_iter

        # -------------------------------------------------
        # 7️⃣ 已有跳变的后续处理（原始代码）
        # -------------------------------------------------
        A = thresholds[jump_index - 1]          # 再取一次，保持语义一致
        lower_bound = A / 3

        # 考察前 jump_index - 1 次迭代（第 1 到第 jump_index-1 次）
        candidate_iters: List[int] = []
        for i in range(jump_index - 1):         # 索引 0 … jump_index-2
            if thresholds[i] >= lower_bound:
                candidate_iters.append(i + 1)   # 转为 1‑based

        default_included_iter = jump_index      # 第 jump_index 次迭代（1‑based）默认保留

        # -------------------------------------------------
        # candidate_iters 数量决定最佳迭代
        # -------------------------------------------------
        if len(candidate_iters) == 0:
            best_iter = original_best_iter
        elif len(candidate_iters) == 1:
            best_iter = candidate_iters[0]
        elif len(candidate_iters) == 2:
            best_iter = max(candidate_iters)
        else:
            # ≥3 个满足 → 在 candidate_iters + [default_included_iter] 中找 diffs 最小的相邻对
            valid_iters_set = set(candidate_iters) | {default_included_iter}
            best_iter = default_included_iter  # 默认 fallback

            # 从后往前遍历 diffs，优先找后期平稳的
            candidate_positions: List[Tuple[int, int]] = []   # (diff_value, later_iter)
            for i in range(len(diffs)):
                prev_iter = i + 1      # diffs[i] 关联第 i+1 与 i+2 次迭代
                curr_iter = i + 2
                if prev_iter in valid_iters_set and curr_iter in valid_iters_set:
                    candidate_positions.append((diffs[i], curr_iter))

            if candidate_positions:
                # 按差值升序、若相同取 later_iter 较大的（更靠后）
                candidate_positions.sort(key=lambda x: (x[0], -x[1]))
                best_iter = candidate_positions[0][1]
            else:
                # 没有相邻对都合法 → 取最大合法迭代
                best_iter = max(valid_iters_set)

        # best_thr = thresholds[best_iter - 1]          # 依据最佳迭代取得阈值
        # print(f"[AdaptiveMedian] 最终选取第 {best_iter} 次迭代阈值 = {best_thr}")

        return thresholds, best_iter

    def _compress_low_levels(self, y: np.ndarray, thr: int) -> np.ndarray:
        """把所有低于 thr 的像素提升到 thr """
        yc = y.copy()
        yc[yc < thr] = thr
        return yc

    # ------------------- 锐化 ------------------- #
    def _sharpen_unsharp_mask(self, gray: np.ndarray) -> np.ndarray:
        """
        非锐化掩模（Unsharp Mask）锐化
        参数:
            gray: 输入灰度图
            amount: 高频增强权重
            ksize: 高斯核大小
            sigma: 高斯标准差（0 表示自动）
        返回: 锐化后图像
        """
        amount = self.sharpen_amount
        ksize = self.sharpen_kernel_size
        sigma = self.sharpen_sigma
        blurred = cv2.GaussianBlur(gray, (ksize, ksize), sigmaX=sigma, sigmaY=sigma)
        high_freq = cv2.subtract(gray, blurred)
        sharpened = cv2.addWeighted(gray, 1.0, high_freq, amount, 0)
        return sharpened

    # ------------------- Otsu 二值化 ------------------- #
    def _otsu_binary(self, gray: np.ndarray) -> np.ndarray:
        """
        使用 Otsu 方法自动计算阈值进行二值化
        """
        _, binary = cv2.threshold(gray, 0, 255,
                                 cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    # ------------------- 导向滤波（降采样‑上采样） ------------------- #
    def _fast_guided_filter(self, y_uint8: np.ndarray) -> np.ndarray:
        """
        降采样 → 导向滤波 → 上采样 的加速方案。
        """
        radius = self.guided_radius
        eps = self.guided_eps
        scale = self.guided_downsample_scale

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
    def _restore_edges(self, original_y: np.ndarray, filtered_y: np.ndarray) -> np.ndarray:
        """
        将原始图像的强边缘写回到滤波结果中。
        """
        low = self.canny_low
        high = self.canny_high
        dilate_k = self.dilate_kernel_size
        iterations = self.dilate_iterations

        edges = cv2.Canny(original_y, low, high)
        if dilate_k > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                               (dilate_k, dilate_k))
            edges = cv2.dilate(edges, kernel, iterations=iterations)
        mask = edges.astype(bool)
        np.copyto(filtered_y, original_y, where=mask)
        return filtered_y

    # ------------------- 小面积噪声去除 ------------------- #
    def _remove_small_noise_regions(self, binary_mask: np.ndarray) -> np.ndarray:
        """
        移除二值图中面积小于 min_area 的白色连通区域。
        """
        min_area = self.min_area_threshold
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_mask,
                                                                      connectivity=8)
        clean_mask = np.zeros_like(binary_mask)
        for label in range(1, num_labels):          # 跳过背景 (label 0)
            area = stats[label, cv2.CC_STAT_AREA]
            if area >= min_area:
                clean_mask[labels == label] = 255
        return clean_mask

    # ------------------- 保存帮助函数 ------------------- #
    def _save_stage(self, name: str, img: np.ndarray) -> None:
        """统一的保存函数（仅用于最终结果）。"""
        self._ensure_dir(self.output_dir)
        path = self.output_dir / f"{name}.png"
        cv2.imwrite(str(path), img)

    # ------------------- 重建最终彩色图（极简版 - 背景全黑） ------------------- #
    def _reconstruct_final_color_black_bg(
        self,
        Y_original: np.ndarray,      # 使用原始 Y 通道
        U: np.ndarray,
        V: np.ndarray,
        binary_mask: Optional[np.ndarray]
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

    # ============================= 主流程 ============================= #
    def process(self, image_input: Union[str, np.ndarray], save_output: bool = False) -> np.ndarray:
        """
        主接口函数
        参数:
            image_input: 图像路径（str）或 numpy 数组 (H, W, 3)
            save_output: 是否保存最终图像
        返回:
            处理后的 BGR 图像
        """
        total_start = time.perf_counter()
        self.timings.clear()
        # -------------------------------------------------
        # 1️⃣ 读取图像并拆分 YUV
        # -------------------------------------------------
        if isinstance(image_input, str):
            img_bgr = self._maybe_time("load_image", self._load_image, image_input)
        elif isinstance(image_input, np.ndarray):
            # 直接把传入的 ndarray 赋给 img_bgr
            img_bgr = image_input
            if img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
                raise ValueError("输入图像必须是 H×W×3 的 BGR 图像")
        else:
            raise TypeError("image_input 必须是字符串路径或 numpy 数组")
        Y_orig, U, V = self._rgb2yuv(img_bgr)
        Y_tmp = Y_orig.copy()
        # -------------------------------------------------
        # 2️⃣ 导向滤波 + 边缘恢复（仅在需要时执行）
        # -------------------------------------------------
        if self.enable_guided_filter or self.enable_edge_restore:
            if self.enable_guided_filter:
                Y_tmp = self._maybe_time("guided_filter",
                                        self._fast_guided_filter,
                                        Y_tmp)
            if self.enable_edge_restore:
                Y_tmp = self._maybe_time("edge_restore",
                                        self._restore_edges,
                                        Y_orig,
                                        Y_tmp)
        # -------------------------------------------------
        # 3️⃣ 自适应中位数阈值 & 低亮度压缩
        # -------------------------------------------------
        thresholds, best_iter = self._maybe_time("adaptive_median",
                                                self._adaptive_median_threshold,
                                                Y_tmp)
        best_thr = thresholds[best_iter - 1]
        Y_tmp = self._maybe_time("compress_low_levels",
                                self._compress_low_levels,
                                Y_tmp,
                                best_thr)
        # -------------------------------------------------
        # 4️⃣ 亮度增强（Fast‑Retinex）——可选
        # -------------------------------------------------
        if self.enable_fast_retinex:
            Y_tmp = self._maybe_time("fast_retinex",
                                    self._fast_retinex_fast,
                                    Y_tmp)
        # -------------------------------------------------
        # 5️⃣ 锐化（可选）
        # -------------------------------------------------
        if self.enable_sharpen:
            Y_tmp = self._maybe_time("sharpen",
                                    self._sharpen_unsharp_mask,
                                    Y_tmp)
        # -------------------------------------------------
        # 6️⃣ Otsu 二值化 + 小噪声去除（可选）
        # -------------------------------------------------
        Y_binary_clean = None
        if self.enable_binary:
            Y_binary = self._maybe_time("otsu_binary",
                                       self._otsu_binary,
                                       Y_tmp)
            if self.enable_small_noise_remove:
                Y_binary_clean = self._maybe_time("remove_small_noise",
                                                 self._remove_small_noise_regions,
                                                 Y_binary)
            else:
                Y_binary_clean = Y_binary.copy()
        # 7️⃣ 合成最终彩色图（使用 **原始** Y 通道，只保存 final_color.png）
        final_color = self._maybe_time(
            "reconstruct_color",
            self._reconstruct_final_color_black_bg,
            Y_orig,          # 传入原始亮度通道
            U,
            V,
            Y_binary_clean   # binary_mask（可能为 None）
        )
        # -------------------------------------------------
        # 8️⃣ 保存结果
        # -------------------------------------------------
        if save_output:
            self._save_stage("final_color", final_color)
        total_elapsed = time.perf_counter() - total_start
        self.timings["total"] = total_elapsed
        # ------------------- 打印计时报告 ------------------- #
        if self.enable_timing:
            print("\n=== 运行时间统计 (milliseconds) ===")
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
                if key in self.timings:
                    ms = self.timings[key] * 1000          # 秒 → 毫秒
                    print(f"{label:20s} {ms:8.2f} ms")
            print("=================================\n")
        return final_color


# ============================= 示例用法 =============================
if __name__ == "__main__":
    # 创建增强器实例
    enhancer = ImageEnhancer(enable_timing=True)

    # 调用接口（路径输入，保存输出）
    result_image = enhancer.process(
        image_input="Resources/Captured/14.png",
        save_output=True
    )

    # 或者传入图像数组
    # img_array = cv2.imread("path/to/image.jpg")
    # result_image = enhancer.process(img_array, save_output=True)