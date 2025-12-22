import cv2
import numpy as np

def zncc(img: np.ndarray, tmpl: np.ndarray) -> np.ndarray:
    """
    Zero‑Mean Normalized Cross‑Correlation (ZNCC) via FFT.
    返回匹配响应图，值越大表示匹配程度越好。
    """
    img_f = np.float32(img)
    tmpl_f = np.float32(tmpl)

    # 1️⃣ 均值、方差
    img_mean = cv2.blur(img_f, tmpl.shape[::-1])
    tmpl_mean = np.mean(tmpl_f)

    img2 = img_f - img_mean
    tmpl2 = tmpl_f - tmpl_mean

    # 2️⃣ FFT 相关（卷积 = 逆FFT(FFT(A)*FFT(B))）
    # 为避免循环卷积，先 pad 到足够大
    dft_size = [cv2.getOptimalDFTSize(s) for s in (img.shape[0] + tmpl.shape[0],
                                                   img.shape[1] + tmpl.shape[1])]

    # FFT of image and template
    img_dft = cv2.dft(cv2.copyMakeBorder(img2, 0, dft_size[0]-img.shape[0],
                                         0, dft_size[1]-img.shape[1],
                                         cv2.BORDER_CONSTANT, value=0),
                      flags=cv2.DFT_COMPLEX_OUTPUT)
    tmpl_dft = cv2.dft(cv2.copyMakeBorder(tmpl2, 0, dft_size[0]-tmpl.shape[0],
                                          0, dft_size[1]-tmpl.shape[1],
                                          cv2.BORDER_CONSTANT, value=0),
                       flags=cv2.DFT_COMPLEX_OUTPUT)

    # 相关（共轭乘积）
    corr = cv2.mulSpectrums(img_dft, tmpl_dft, 0, conjB=True)
    corr = cv2.idft(corr, flags=cv2.DFT_SCALE | cv2.DFT_REAL_OUTPUT)

    # 只取有效区域 (H‑h+1, W‑w+1)
    h, w = tmpl.shape[:2]
    corr = corr[h-1:img.shape[0], w-1:img.shape[1]]

    # 3️⃣ 归一化分母
    sq_img = cv2.blur(img_f * img_f, tmpl.shape[::-1]) - img_mean * img_mean
    sq_tmpl = np.var(tmpl_f) * (tmpl.shape[0] * tmpl.shape[1])
    denom = np.sqrt(sq_img * sq_tmpl) + 1e-5   # 防止除 0

    zncc_map = corr / denom
    return zncc_map


def pyramid_match(img, tmpl, levels=4, scale=0.5):
    """
    金字塔多尺度 ZNCC 匹配 + 亚像素细化。
    返回最优匹配点 (x, y) 以及对应的尺度 factor。
    """
    best_val = -np.inf
    best_pt = None
    best_scale = 1.0

    cur_img = img.copy()
    cur_tmpl = tmpl.copy()
    factor = 1.0

    for lvl in range(levels):
        zncc_map = zncc(cur_img, cur_tmpl)

        # 找最大响应
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(zncc_map)
        if max_val > best_val:
            best_val = max_val
            best_pt = (max_loc[0] * (1/factor), max_loc[1] * (1/factor))
            best_scale = factor

        # 进入下一层金字塔（下采样）
        cur_img = cv2.pyrDown(cur_img)
        cur_tmpl = cv2.pyrDown(cur_tmpl)
        factor *= 2.0

    # ------- 亚像素细化（二次插值） -------
    x, y = best_pt
    ix, iy = int(round(x)), int(round(y))
    # 取 3×3 窗口（确保不越界）
    win = zncc_map[iy-1:iy+2, ix-1:ix+2]
    if win.shape == (3, 3):
        # 采用二维二次曲面拟合
        dx = (win[1, 2] - win[1, 0]) / (2 * (2 * win[1, 1] - win[1, 0] - win[1, 2] + 1e-6))
        dy = (win[2, 1] - win[0, 1]) / (2 * (2 * win[1, 1] - win[0, 1] - win[2, 1] + 1e-6))
        x += dx
        y += dy

    return (x, y), best_scale, best_val


# ------------------- 示例 -------------------
if __name__ == "__main__":
    img  = cv2.imread('scene.png', cv2.IMREAD_GRAYSCALE)
    tmpl = cv2.imread('template.png', cv2.IMREAD_GRAYSCALE)

    (px, py), scale, score = pyramid_match(img, tmpl, levels=5)
    print(f"匹配位置: ({px:.2f}, {py:.2f})  scale={scale:.2f}  score={score:.4f}")

    # 在原图上画框
    h, w = tmpl.shape[:2]
    h = int(h * scale)
    w = int(w * scale)
    top_left = (int(px), int(py))
    bottom_right = (int(px + w), int(py + h))
    img_vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(img_vis, top_left, bottom_right, (0, 255, 0), 2)
    cv2.imwrite('matched_result.png', img_vis)