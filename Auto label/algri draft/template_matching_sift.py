import cv2
import numpy as np
from image_preprocessing import preprocess_v_channel
import time
import os
import re
from collections import defaultdict
from typing import List, Tuple, Dict, Optional
start_time = time.time()

# =============================
# 参数设置
# =============================
FLANN_CHECKS = 50         # FLANN 匹配器搜索时检查的最近邻节点数。值越大越精确但越慢
MATCH_THRESHOLD = 30      # 匹配率阈值（百分比）
MIN_MATCH_COUNT = 4       # 单次匹配所需最小内点数(至少为4)
INLIER_DISTANCE = 5.0     # RANSAC 投影误差（单位：像素）
OVERLAP_THRESHOLD = 0.3   # 去重阈值（IoU）

# =============================
# 模板图像路径列表（可扩展）
# =============================


# 目标图像路径
target_path = '../../TemporaryResources/ARHUD_frames/'
target_list =  os.listdir(target_path)
target_label = "TemporaryResources/label/"
target_muban = "TemporaryResources/muban/"
label_images = "TemporaryResources/label_images/"
muban_list2 = os.listdir(target_muban)
muban_list = [target_muban+i for i in muban_list2]


# 不同模板的绘制颜色（BGR），自动循环使用
colors = [
    (0, 255, 0),     # 绿色
    (255, 0, 0),     # 蓝色
    (0, 0, 255),     # 红色
    (255, 255, 0),   # 青色
    (255, 0, 255),   # 品红
    (0, 255, 255),   # 黄色
    (255, 165, 0),   # 橙色
    (128, 0, 128),   # 紫色
    (255, 192, 203), # 粉色
]



# =============================
# 定义单个模板匹配函数
# =============================
def match_single_template(template_path,des2_target , color):
    print(f"\n--- 开始匹配模板: {template_path} ---")

    # 读取模板图像
    template_bgr = cv2.imread(template_path)
    if template_bgr is None:
        print(f"模板图像读取失败: {template_path}")
        return []

    template_hsv = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2HSV)
    template_v = cv2.split(template_hsv)[2]
    template_gray = preprocess_v_channel(template_v)

    # 提取模板特征
    kp1, des1 = sift.detectAndCompute(template_gray, None)
    if des1 is None or des1.size == 0:
        print(f"模板 {template_path} 无有效描述子，跳过")
        return []

    des1 = np.float32(des1)
    h, w = template_gray.shape
    corners = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)

    # 获取所有knn匹配对
    all_matches = flann.knnMatch(des1, des2_target, k=2)
    print(f"模板 {os.path.basename(template_path)}: 总knn匹配对数: {len(all_matches)}")

    bounding_boxes = []           # 存储该模板的包围框
    used_train_indices = set()    # 已使用的目标图关键点索引

    # 主循环：查找多个匹配实例
    while True:
        candidate_matches = []
        good_matches = []

        # 筛选未使用的关键点匹配对
        for m, n in all_matches:
            if m.trainIdx not in used_train_indices:
                candidate_matches.append((m, n))

        # Lowe's Ratio Test
        for m, n in candidate_matches:
            if m.distance < 0.7 * n.distance:
                good_matches.append(m)

        if len(good_matches) < MIN_MATCH_COUNT:
            print("优质匹配不足，退出循环")
            break

        match_rate = (len(good_matches) / len(candidate_matches)) * 100 if candidate_matches else 0
        print(f"本轮匹配率: {match_rate:.2f}% (优质匹配: {len(good_matches)})")

        if match_rate < MATCH_THRESHOLD:
            print(f"匹配率低于阈值 {MATCH_THRESHOLD}%，停止")
            break

        # 提取点对
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2_target[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # RANSAC 计算单应性矩阵
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, INLIER_DISTANCE, confidence=0.99, maxIters=2000)
        if H is None or mask is None:
            break

        matches_mask = mask.ravel().tolist()
        inlier_matches = [good_matches[i] for i in range(len(good_matches)) if matches_mask[i]]

        if len(inlier_matches) < MIN_MATCH_COUNT:
            break

        # 重新计算更精确的H
        inlier_src = np.float32([kp1[m.queryIdx].pt for m in inlier_matches]).reshape(-1, 1, 2)
        inlier_dst = np.float32([kp2_target[m.trainIdx].pt for m in inlier_matches]).reshape(-1, 1, 2)
        H_refined, _ = cv2.findHomography(inlier_src, inlier_dst, cv2.RANSAC, INLIER_DISTANCE)
        if H_refined is None:
            break

        # 投影角点
        transformed_corners = cv2.perspectiveTransform(corners, H_refined)
        transformed_corners = np.int32(transformed_corners)

        x_coords = transformed_corners[:, 0, 0]
        y_coords = transformed_corners[:, 0, 1]
        x_min, x_max = int(np.min(x_coords)), int(np.max(x_coords))
        y_min, y_max = int(np.min(y_coords)), int(np.max(y_coords))

        # 重叠检测（仅在当前模板内部去重）
        is_overlapping = False
        for (bx_min, bx_max, by_min, by_max) in bounding_boxes:
            inter_xmin = max(x_min, bx_min)
            inter_xmax = min(x_max, bx_max)
            inter_ymin = max(y_min, by_min)
            inter_ymax = min(y_max, by_max)
            if inter_xmin < inter_xmax and inter_ymin < inter_ymax:
                inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)
                curr_area = (x_max - x_min) * (y_max - y_min)
                prev_area = (bx_max - bx_min) * (by_max - by_min)
                union_area = curr_area + prev_area - inter_area
                if union_area > 0 and inter_area / union_area > OVERLAP_THRESHOLD:
                    is_overlapping = True
                    break

        if is_overlapping:
            print("检测到重叠区域，跳过")
        else:
            bounding_boxes.append((x_min, x_max, y_min, y_max))
            # cv2.rectangle(result_image, (x_min, y_min), (x_max, y_max), color, 2)
            print(f"匹配成功: ({x_min}, {y_min}) - ({x_max}, {y_max})")

        # 标记已用关键点
        used_train_indices.update(m.trainIdx for m in inlier_matches)

    print(f"模板 {os.path.basename(template_path)} 共找到 {len(bounding_boxes)} 个实例")
    return bounding_boxes

def xyxy_to_yolo(x_min, y_min, x_max, y_max, img_w, img_h):
    xc = (x_min + x_max) / 2.0 / img_w
    yc = (y_min + y_max) / 2.0 / img_h
    w  = (x_max - x_min) / img_w
    h  = (y_max - y_min) / img_h
    return xc, yc, w, h
def get_prefix(filename: str) -> str:
    """
    例：
        velocity1.png   -> "velocity"
        velocity10.png  -> "velocity"
        find2.png       -> "find"
        daohang1.png    -> "daohang"
        my_image.png    -> "my_image" (没有数字，直接返回去掉扩展名的部分)
    """
    # 先去掉扩展名
    name = filename.rsplit('.', 1)[0]

    # 正则找第一个数字或下划线的位置
    m = re.search(r'[\d_]', name)
    if m:
        return name[:m.start()]          # 前缀 = 左侧子串
    else:
        return name                      # 整个名字本身就是前缀



def merge_by_prefix(
    data: Dict[str, List[Tuple[int, int, int, int]]],
    metric: str = "area"
) -> Dict[str, Optional[Tuple[int, int, int, int]]]:
    """
    参数
    ----
    data   : 原始 {filename: [bbox, ...]} 结构
    metric : 用来比较大小的指标，"area"（默认）或 "perimeter"

    返回
    ----
    {prefix: (x1, y1, x2, y2) 或 None}
    """
    # ① 建立 prefix → 所有框的列表
    grouped: Dict[str, List[Tuple[int, int, int, int]]] = defaultdict(list)

    for fname, boxes in data.items():
        pref = get_prefix(fname)
        grouped[pref].extend(boxes)          # 把同类的所有框都放进来

    # ② 按指标挑选“最大”的框
    result: Dict[str, Optional[Tuple[int, int, int, int]]] = {}

    for pref, boxes in grouped.items():
        if not boxes:                        # 该类根本没有框
            result[pref] = None
            continue

        # 计算比较值
        if metric == "area":
            key_func = lambda b: (b[2] - b[0]) * (b[3] - b[1])   # w * h
        elif metric == "perimeter":
            key_func = lambda b: 2 * ((b[2] - b[0]) + (b[3] - b[1]))
        else:
            raise ValueError("metric must be 'area' or 'perimeter'")

        # max() 会返回面积/周长最大的那个框
        best_box = max(boxes, key=key_func)
        result[pref] = best_box

    return result



# =============================
# 读取目标图像
# =============================
# 初始化SIFT（只需一次）
sift = cv2.SIFT_create(nfeatures=0, nOctaveLayers=3, contrastThreshold=0.04, edgeThreshold=10, sigma=1.0)
for item_path in target_list:
    target_bgr = cv2.imread(target_path+item_path)

    if target_bgr is None:
        print(f"目标图像读取失败: {target_path}")
        exit()

    target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)
    target_v = cv2.split(target_hsv)[2]
    target_gray = preprocess_v_channel(target_v)


    kp2_target, des2_target = sift.detectAndCompute(target_gray, None)

    if des2_target is None or des2_target.size == 0:
        print("目标图像无法提取特征描述子，匹配失败")
        # cv2.imshow('Matched Result', target_bgr)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        label_path = target_label + item_path[:-4] + ".txt"
        cv2.imwrite(label_images + item_path, target_bgr)
        with open(label_path, "w", encoding="utf-8") as f_label:
            # 遍历每个模板的检测框
            f_label.write("")

        continue
        # exit()

    # 转换为 float32
    des2_target = np.float32(des2_target)

    # 初始化 FLANN 匹配器
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=FLANN_CHECKS)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    # 创建结果图像（彩色）
    result_image = target_bgr.copy()

    # 存储所有已绘制的包围框（用于不同模板之间的去重？可选）
    # 如果你希望不同模板之间也避免重叠，可以统一去重；否则只在单个模板内去重
    # 这里我们 **每个模板独立去重**，不同模板允许重叠


    # =============================
    # 主循环：遍历所有模板
    # =============================
    all_results = {}

    for idx, tpl_path in enumerate(muban_list):
        color = colors[idx % len(colors)]  # 循环使用颜色
        boxes = match_single_template(tpl_path,des2_target, color)
        all_results[os.path.basename(tpl_path)] = boxes

    img_h, img_w = target_bgr.shape[:2]
    merged = merge_by_prefix(all_results)


    name_to_id = {fname: idx for idx, fname in enumerate(merged)}



    # 为当前目标图像创建对应的 txt 文件（与图片同名）
    label_path = target_label +item_path[:-4] + ".txt"
    with open(label_path, "w", encoding="utf-8") as f_label:
        # 遍历每个模板的检测框
        for tpl_name, boxes in merged.items():  # 直接遍历文件名，省掉 enumerate
            class_id = name_to_id[tpl_name]  # 正确使用映射表
            if boxes is None:
                continue
            for (x_min, x_max, y_min, y_max) in [boxes]:
                cv2.rectangle(result_image, (x_min, y_min), (x_max, y_max), colors[0], 2)
                xc, yc, w, h = xyxy_to_yolo(x_min, y_min, x_max, y_max,
                                            img_w, img_h)
                f_label.write(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
    # =============================
    # 输出统计与显示
    # =============================
    print("\n" + "="*50)
    for name, boxes in all_results.items():
        print(f"{name}: 找到 {len(boxes)} 个匹配实例")

    total_instances = sum(len(boxes) for boxes in all_results.values())
    print(f"总共找到 {total_instances} 个匹配实例")

    execution_time = time.time() - start_time
    print(f"总运行时间: {execution_time:.2f} 秒")

    # 显示结果
    cv2.imwrite(label_images+item_path, result_image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()