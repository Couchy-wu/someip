import cv2
import numpy as np
from image_preprocessing import preprocess_v_channel
import time
import os

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
template_paths = [
    'find1.png', 
    'find2.png', 
    'find3.png', 
    'find4.png', 
]

# 目标图像路径
target_path = 'TemporaryResources/ARHUD/620.png'

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
# 读取目标图像
# =============================
target_bgr = cv2.imread(target_path)
if target_bgr is None:
    print(f"目标图像读取失败: {target_path}")
    exit()

target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)
target_v = cv2.split(target_hsv)[2]
target_gray = preprocess_v_channel(target_v)

# 初始化SIFT（只需一次）
sift = cv2.SIFT_create(nfeatures=0, nOctaveLayers=3, contrastThreshold=0.04, edgeThreshold=10, sigma=1.0)
kp2_target, des2_target = sift.detectAndCompute(target_gray, None)

if des2_target is None or des2_target.size == 0:
    print("目标图像无法提取特征描述子，匹配失败")
    cv2.imshow('Matched Result', target_bgr)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    exit()

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
# 定义单个模板匹配函数
# =============================
def match_single_template(template_path, color):
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
            cv2.rectangle(result_image, (x_min, y_min), (x_max, y_max), color, 2)
            print(f"匹配成功: ({x_min}, {y_min}) - ({x_max}, {y_max})")

        # 标记已用关键点
        used_train_indices.update(m.trainIdx for m in inlier_matches)

    print(f"模板 {os.path.basename(template_path)} 共找到 {len(bounding_boxes)} 个实例")
    return bounding_boxes

# =============================
# 主循环：遍历所有模板
# =============================
all_results = {}

for idx, tpl_path in enumerate(template_paths):
    color = colors[idx % len(colors)]  # 循环使用颜色
    boxes = match_single_template(tpl_path, color)
    all_results[os.path.basename(tpl_path)] = boxes

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
cv2.imshow('Multi-Template Matched Result', result_image)
cv2.waitKey(0)
cv2.destroyAllWindows()