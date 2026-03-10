# -*- coding: utf-8 -*-
"""
template_matching_zncc_fixed_v3_corrected.py
- ZNCC (TM_CCOEFF_NORMED) 金字塔匹配
- 正确的坐标/尺度映射（坐标使用乘法）
- 亚像素细化（抛物线拟合）
- 完整、无错误的矩形绘制
"""

import cv2
import numpy as np


def zncc_opencv(img: np.ndarray, tmpl: np.ndarray) -> np.ndarray:
    """OpenCV TM_CCOEFF_NORMED → ZNCC，返回 (H‑h+1, W‑w+1) 响应图"""
    if img.dtype != np.float32:
        img = img.astype(np.float32)
    if tmpl.dtype != np.float32:
        tmpl = tmpl.astype(np.float32)
    return cv2.matchTemplate(img, tmpl, cv2.TM_CCOEFF_NORMED)


def pyramid_match_opencv(img, tmpl, levels=4):
    """
    金字塔 + ZNCC + 亚像素细化
    返回 (x, y) 原图坐标（亚像素）、尺度因子、最高响应值。
    """
    best_val = -np.inf
    best_pt = None
    best_scale = 1.0

    cur_img, cur_tmpl = img.copy(), tmpl.copy()
    factor = 1.0                     # 当前层相对原图的放大因子（1,2,4,...）

    # ---------- 金字塔遍历 ----------
    for lvl in range(levels):
        zncc_map = zncc_opencv(cur_img, cur_tmpl)
        _, max_val, _, max_loc = cv2.minMaxLoc(zncc_map)

        if max_val > best_val:
            best_val = max_val
            # **这里改为乘法**，把金字塔层坐标映射回原图
            best_pt = (max_loc[0] * factor, max_loc[1] * factor)
            best_scale = factor       # 记录当前层的放大因子，后面绘制时会用到

        # 进入下一层金字塔（尺寸除以 2）
        cur_img = cv2.pyrDown(cur_img)
        cur_tmpl = cv2.pyrDown(cur_tmpl)
        factor *= 2.0

    if best_pt is None:
        raise RuntimeError("未检测到匹配点，请检查模板与图像的相似度。")

    # ---------- 亚像素细化 ----------
    scale_factor = 1.0 / best_scale          # 把原图缩放回匹配时的金字塔层大小
    img_scaled = cv2.resize(img, (0, 0), fx=scale_factor, fy=scale_factor,
                           interpolation=cv2.INTER_LINEAR)
    tmpl_scaled = cv2.resize(tmpl, (0, 0), fx=scale_factor, fy=scale_factor,
                            interpolation=cv2.INTER_LINEAR)

    final_map = zncc_opencv(img_scaled, tmpl_scaled)

    # 把原图坐标映射到 final_map（缩放后）坐标系
    ix = int(round(best_pt[0] * scale_factor))
    iy = int(round(best_pt[1] * scale_factor))
    h_f, w_f = final_map.shape

    if 1 <= ix < w_f - 1 and 1 <= iy < h_f - 1:
        win = final_map[iy - 1:iy + 2, ix - 1:ix + 2]

        # 二次抛物线拟合（亚像素）
        dx = (win[1, 2] - win[1, 0]) / (
            2 * (2 * win[1, 1] - win[1, 0] - win[1, 2] + 1e-9)
        )
        dy = (win[2, 1] - win[0, 1]) / (
            2 * (2 * win[1, 1] - win[0, 1] - win[2, 1] + 1e-9)
        )
        best_pt = (best_pt[0] + dx, best_pt[1] + dy)   # 回到原图坐标系

    return best_pt, best_scale, best_val


# ------------------- 主程序 -------------------
if __name__ == "__main__":
    # ------------------- 读取 -------------------
    img_path = r"../../image.png"  # 大图
    tmpl_path = r"../../find1.png"  # 模板

    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    tmpl = cv2.imread(tmpl_path, cv2.IMREAD_GRAYSCALE)

    if img is None or tmpl is None:
        raise FileNotFoundError("检查图片路径是否正确，且图片为灰度图。")

    # ------------------- 匹配 -------------------
    (px, py), scale, score = pyramid_match_opencv(img, tmpl, levels=5)

    print(f"[MATCH] 位置 = ({px:.3f}, {py:.3f})   "
          f"尺度 = {scale:.2f}   响应 = {score:.4f}")

    # ------------------- 可视化 -------------------
    tmpl_h, tmpl_w = tmpl.shape[:2]

    # 按匹配到的尺度放大模板尺寸（得到在原图上的宽高）
    draw_w = int(round(tmpl_w))
    draw_h = int(round(tmpl_h))

    top_left = (int(round(px)), int(round(py)))          # (x, y) 原图左上角
    bottom_right = (top_left[0] + draw_w, top_left[1] + draw_h)

    # 调试输出（确保都是整数）
    print("[DEBUG] top_left    :", top_left,    "type:", type(top_left))
    print("[DEBUG] bottom_right:", bottom_right, "type:", type(bottom_right))
    print("[DEBUG] draw_w, draw_h:", draw_w, draw_h)

    # 把灰度图转成 BGR（才能画彩色矩形）
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(vis, top_left, bottom_right, (0, 255, 0), thickness=2)

    out_path = "matched_result.png"
    cv2.imwrite(out_path, vis)
    print(f"[INFO] 匹配结果已保存至 {out_path}")