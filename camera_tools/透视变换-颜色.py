import cv2
import numpy as np
from scipy.spatial import cKDTree
import  sys


def my_getPerspectiveTransform(src_pts, dst_pts):
    """
    手写版 cv2.getPerspectiveTransform（仅适用于 4 对点）。
    参数:
        src_pts : (4,2) ndarray, 原图四个角点 (float或int)
        dst_pts : (4,2) ndarray, 目标四个角点 (float或int)
    返回:
        3x3 Homography 矩阵 (float64)
    """
    src = np.asarray(src_pts, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(dst_pts, dtype=np.float64).reshape(-1, 2)

    if src.shape != (4, 2) or dst.shape != (4, 2):
        raise ValueError("src_pts and dst_pts 必须都是 4x2 的数组")

    # 构造矩阵 A (8x8) 和向量 b (8,)
    A = []
    b = []
    for (x, y), (xp, yp) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -x * xp, -y * xp])
        A.append([0, 0, 0, x, y, 1, -x * yp, -y * yp])
        b.append(xp)
        b.append(yp)

    A = np.asarray(A, dtype=np.float64)   # (8,8)
    b = np.asarray(b, dtype=np.float64)   # (8,)

    # 直接求解线性方程组（A 必须可逆）
    h = np.linalg.solve(A, b)             # (8,)

    # 把 h 拼成 3x3 矩阵，最后一个元素固定为 1
    H = np.append(h, 1).reshape(3, 3)

    return H

def nearest_points_kdtree(mask: np.ndarray,
                         x_min, y_min,x_max, y_max,
                         avoid_duplicate: bool = True):
    """
    从 mask 中找出每个 target 最近的前景像素。
    参数
    ----
    mask   : (H, W) 二值图，前景像素值 > 0
    targets: shape (4, 2) 或 list/tuple，[[x1,y1],...]
    avoid_duplicate:
        True  → 让每个目标点得到唯一的像素（若冲突则取次近点）
        False → 直接返回最近点，可能出现相同像素被多次使用

    返回
    ----
    nearest_pts : list of (x, y)   长度 4

    """
    targets = np.array([[x_min, y_min],
                        [x_max, y_min],
                        [x_max, y_max],
                        [x_min, y_max]], dtype=np.float32)
    # 1️⃣ 把 mask 中所有前景像素坐标取出来（x 为列索引，y 为行索引）
    ys, xs = np.where(mask > 0)          # 注意返回的是 (row, col) → (y, x)
    foreground = np.column_stack((xs, ys))   # shape (N, 2)

    if foreground.shape[0] == 0:
        raise ValueError("mask 中没有前景像素")

    # 2️⃣ 构建 KD‑Tree
    tree = cKDTree(foreground)

    # 3️⃣ 查询最近点（一次性查询 4 条）
    # `k=1` 返回最近点的距离和索引
    dists, idxs = tree.query(targets, k=1)

    # 4️⃣ 防止重复（若需要唯一像素）
    if avoid_duplicate:
        # 记录已经占用的索引
        used = set()
        final_pts = []
        for i, target in enumerate(targets):
            # 首先尝试第一次查询得到的最近点
            cand_idx = idxs[i]
            if cand_idx not in used:
                used.add(cand_idx)
                final_pts.append(foreground[cand_idx])
                continue

            # 已被占用 → 重新查询次近点（k=10 足够大，若仍冲突则继续扩大 k）
            k = 10
            while True:
                dists_k, idxs_k = tree.query(target, k=k)
                # idxs_k 是数组，遍历找第一个未占用的
                found = False
                for cand in idxs_k:
                    if cand not in used:
                        used.add(cand)
                        final_pts.append(foreground[cand])
                        found = True
                        break
                if found:
                    break
                k *= 2                     # 没找到则扩大搜索范围
        nearest_pts = final_pts
    else:
        nearest_pts = foreground[idxs]

    # 把 (x, y) 转成 Python 原生 tuple 方便后续使用
    return [tuple(pt.tolist()) for pt in nearest_pts]

def mask_blue_hsv(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([100, 50, 50])
    upper_blue = np.array([130, 255, 255])
    return cv2.inRange(hsv, lower_blue, upper_blue)

def clean_mask(mask, k=7):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    return mask

def find_blue_rect(mask, min_area=800, ar_range=(0.3, 5)):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        ar = w / float(h)
        if not (ar_range[0] <= ar <= ar_range[1]):
            continue
        if area > best_area:
            best_area = area
            best = (x, y, w, h)
    return best

def draw_rect(img, rect):
    if rect:
        x, y, w, h = rect
        cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
    return img, x, y, x + w, y + h
def find_perspective_corners(x_min, y_min,x_max, y_max):
    targets = np.array([[0, 0],
                        [x_max-x_min, 0],
                        [x_max-x_min, y_max-y_min],
                        [0, y_max-y_min]], dtype=int)
    return np.stack(targets)

if __name__ == '__main__':
    img = cv2.imread('B.jpg')
    if img is None:
        raise FileNotFoundError('图片读取失败')
    mask = mask_blue_hsv(img)
    mask = clean_mask(mask, k=7)
    rect = find_blue_rect(mask, min_area=800, ar_range=(0.3, 5))
    out,x_min, y_min,x_max, y_max = draw_rect(img.copy(), rect)

    clockwise_point = nearest_points_kdtree(mask,x_min, y_min,x_max, y_max)
    target_clockwise_point =find_perspective_corners(x_min, y_min,x_max, y_max)
    matrix = my_getPerspectiveTransform(clockwise_point, target_clockwise_point)

    print(matrix)
    # 计算透视变换后的图片
    perspective_img = cv2.warpPerspective(img, matrix,
                                          (target_clockwise_point[2][0], target_clockwise_point[2][1]))
    cv2.imwrite("perspective_image.jpg", perspective_img)


    cv2.imwrite('result_blue_box.jpg', out)
    cv2.imwrite('blue_mask.jpg', mask)