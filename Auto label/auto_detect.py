# -*- coding: utf-8 -*-
"""
auto_detect.py
----------------
提供：
    - load_templates(tpl_dir) → dict{name: gray_image}
    - detect_multi(frame_gray, templates, class_names, **params)
      返回 [(bbox, class_id, score), ...]（bbox 为 (x, y, w, h) 的整数像素坐标）
"""

import cv2
import numpy as np
import random, colorsys
from pathlib import Path
from typing import Dict, List, Tuple

# -------------------------------------------------
# ① 基础工具（颜色、NMS）
# -------------------------------------------------
def random_color():
    """返回 (B, G, R) 随机但可辨认的颜色，供可视化使用（非必需）"""
    h = random.random()
    s = 0.6 + 0.4 * random.random()
    v = 0.6 + 0.4 * random.random()
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(b*255), int(g*255), int(r*255))

def nms(boxes: List[Tuple[int, int, int, int]],
        scores: List[float],
        iou_thr: float = 0.3) -> List[int]:
    """标准的 NMS，实现与手动标注脚本中相同"""
    if not boxes:
        return []
    boxes = np.array(boxes, dtype=np.float32)
    scores = np.array(scores, dtype=np.float32)

    x1, y1, x2, y2 = (
        boxes[:, 0],
        boxes[:, 1],
        boxes[:, 0] + boxes[:, 2] - 1,
        boxes[:, 1] + boxes[:, 3] - 1,
    )
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter)

        inds = np.where(iou <= iou_thr)[0]
        order = order[inds + 1]
    return keep


# -------------------------------------------------
# ② ORB 初始化（全局复用，避免每张图都重新创建）
# -------------------------------------------------
_ORB = cv2.ORB_create(
    nfeatures=5000,
    edgeThreshold=5,
    patchSize=31,
    scaleFactor=1.2,
    nlevels=8,
)
_BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)


# -------------------------------------------------
# ③ 多实例检测核心（与原脚本相同，只做了少量参数默认化）
# -------------------------------------------------
def _detect_one_template(frame_gray: np.ndarray,
                        tmpl_gray: np.ndarray,
                        ratio_thr: float = 0.55,
                        min_match: int = 4,
                        ransac_thr: float = 12.0,
                        scale_factor: float = 2.0,
                        max_instances: int = 20) -> List[Tuple[Tuple[int, int, int, int], np.ndarray, float]]:
    """
    返回 [(bbox, H, score), ...]，每个元素对应一次检测到的实例。
    bbox = (x, y, w, h)  —— 整型像素坐标
    """
    # 1️⃣ 放大模板（有时模板太小导致特征点不足）
    if scale_factor != 1.0:
        tmpl_gray = cv2.resize(
            tmpl_gray,
            (int(tmpl_gray.shape[1] * scale_factor),
             int(tmpl_gray.shape[0] * scale_factor)),
            interpolation=cv2.INTER_LINEAR,
        )

    # 2️⃣ 特征点
    kp_t, des_t = _ORB.detectAndCompute(tmpl_gray, None)
    kp_i, des_i = _ORB.detectAndCompute(frame_gray, None)
    if des_t is None or des_i is None:
        return []   # 没有特征点

    # 3️⃣ 初始匹配（knn + Ratio Test）
    matches = _BF.knnMatch(des_t, des_i, k=2)
    good = [m for m, n in matches if m.distance < ratio_thr * n.distance]

    results = []
    instance_id = 0
    while len(good) >= min_match and instance_id < max_instances:
        src_pts = np.float32([kp_t[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp_i[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        if src_pts.shape[0] < 4:
            break

        H, mask = cv2.findHomography(src_pts, dst_pts,
                                     cv2.RANSAC, ransac_thr)
        if H is None:
            break

        # 计算外接矩形（得到 bbox）
        h, w = tmpl_gray.shape[:2]
        corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        proj = cv2.perspectiveTransform(corners, H)
        x, y, w_box, h_box = cv2.boundingRect(proj.astype(np.int32))

        inlier_cnt = int(mask.sum())
        score = inlier_cnt / max(len(kp_t), 1)

        results.append(((x, y, w_box, h_box), H, float(score)))

        # 剔除已使用的内点，继续寻找下一个实例
        good = [g for i, g in enumerate(good) if mask[i] == 0]
        instance_id += 1

    return results


# -------------------------------------------------
# ④ 对所有模板一次性检测并返回统一结构
# -------------------------------------------------
def detect_multi(frame_gray: np.ndarray,
                 templates: Dict[str, np.ndarray],
                 class_names: List[str],
                 *,
                 ratio_thr: float = 0.55,
                 min_match: int = 4,
                 ransac_thr: float = 12.0,
                 scale_factor: float = 2.0,
                 max_instances: int = 20,
                 nms_iou: float = 0.3) -> List[Tuple[Tuple[int, int, int, int], int, float]]:
    """
    参数
    -----
    frame_gray : 当前帧的灰度图
    templates  : {template_name: gray_image}
    class_names: YOLO 类别名称列表（从 data.yaml 读取）

    返回
    -----
    List[(bbox, class_id, score), ...]   # bbox 为 (x, y, w, h) 整型
    """
    all_results = []

    for name, tmpl in templates.items():
        # 若模板名在 class_names 中找不到，尝试自动追加（可自行决定是否允许）
        if name not in class_names:
            # 这里直接把新类别追加到列表的末尾，返回的 class_id 为新索引
            class_names.append(name)
            print(f"[INFO] 自动把模板名 `{name}` 加入类别列表，class_id={len(class_names)-1}")

        class_id = class_names.index(name)

        raw_res = _detect_one_template(
            frame_gray,
            tmpl,
            ratio_thr=ratio_thr,
            min_match=min_match,
            ransac_thr=ransac_thr,
            scale_factor=scale_factor,
            max_instances=max_instances,
        )
        if not raw_res:
            continue

        # NMS（同一模板的多框合并）
        boxes = [r[0] for r in raw_res]
        scores = [r[2] for r in raw_res]
        keep = nms(boxes, scores, iou_thr=nms_iou)

        for idx in keep:
            bbox, _, score = raw_res[idx]
            all_results.append((bbox, class_id, score))

    return all_results


# -------------------------------------------------
# ⑤ 加载模板（一次性读取，后面直接复用）
# -------------------------------------------------
def load_templates(tpl_dir: str) -> Dict[str, np.ndarray]:
    """
    返回 {template_name_without_ext: gray_image}
    支持 png/jpg/jpeg，忽略读取失败的文件。
    """
    tmpl_paths = list(Path(tpl_dir).glob("*.*"))
    templates = {}
    for p in tmpl_paths:
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"[WARN] 读取模板失败 → {p}")
            continue
        templates[p.stem] = img
    return templates