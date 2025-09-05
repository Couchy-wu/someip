import cv2
import numpy as np
from image_preprocessing import preprocess_v_channel
import time

start_time = time.time()

# 参数设置
FLANN_CHECKS = 50
MATCH_THRESHOLD = 30      # 匹配率阈值（百分比）
MIN_MATCH_COUNT = 4       # 单次匹配所需最小内点数
INLIER_DISTANCE = 5.0     # RANSAC 投影误差
OVERLAP_THRESHOLD = 0.3   # 去重阈值（IoU）



# 读取图像
template_bgr = cv2.imread('kmh.png')
target_bgr = cv2.imread('TemporaryResources/ARHUD/10.png')

if template_bgr is None or target_bgr is None:
    print("图像读取失败，请检查路径")
    exit()

# 转换为HSV并预处理V通道
template_hsv = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2HSV)
target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)

template_v = cv2.split(template_hsv)[2]
target_v = cv2.split(target_hsv)[2]

template_gray = preprocess_v_channel(template_v)
target_gray = preprocess_v_channel(target_v)

# 初始化SIFT
sift = cv2.SIFT_create(nfeatures=0, nOctaveLayers=3, contrastThreshold=0.04, edgeThreshold=10, sigma=1.0)
kp1, des1 = sift.detectAndCompute(template_gray, None)
kp2, des2 = sift.detectAndCompute(target_gray, None)

# 使用原始彩色图像作为绘制底图（无论是否匹配都显示彩色）
result_image = target_bgr.copy()  # 直接使用原始彩色图

# 检查描述子
if des1 is None or des2 is None or des1.size == 0 or des2.size == 0:
    print("无法提取有效特征描述子，匹配失败")
    # 即使失败，也显示彩色原图
    cv2.imshow('Matched Result', result_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    exit()

des1 = np.float32(des1)
des2 = np.float32(des2)

# FLANN匹配器
FLANN_INDEX_KDTREE = 1
index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
search_params = dict(checks=FLANN_CHECKS)
flann = cv2.FlannBasedMatcher(index_params, search_params)

# 所有候选匹配（暂不筛选）
all_matches = flann.knnMatch(des1, des2, k=2)
print(f"总knn匹配对数: {len(all_matches)}")

# 存储所有通过阈值检测的有效包围框
bounding_boxes = []

# 当前可用的关键点索引（目标图上的 trainIdx），用于避免重复检测
used_train_indices = set()

# 获取图像尺寸
h, w = template_gray.shape
corners = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)

# 迭代查找多个实例
while True:
    # Step 1: 筛选未使用的匹配对，并进行 Lowe's Ratio Test
    good_matches = []
    candidate_matches = []

    for m, n in all_matches:
        if m.trainIdx not in used_train_indices:
            candidate_matches.append((m, n))

    # 对未使用的匹配重新应用 Lowe's Ratio Test
    for m, n in candidate_matches:
        if m.distance < 0.7 * n.distance:
            good_matches.append(m)

    if len(good_matches) < MIN_MATCH_COUNT:
        break  # 没有足够的优质匹配

    # 计算当前匹配率
    match_rate = (len(good_matches) / len(candidate_matches)) * 100 if candidate_matches else 0
    print(f"本轮优质匹配点数: {len(good_matches)}, 候选总数: {len(candidate_matches)}, 匹配率: {match_rate:.2f}%")

    # 判断是否达到匹配率阈值
    if match_rate < MATCH_THRESHOLD:
        print(f"匹配率 {match_rate:.2f}% 低于阈值 {MATCH_THRESHOLD}%，跳过该实例")
        break  # 不足阈值，停止

    # 提取源点和目标点
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    # 使用 RANSAC 计算单应性矩阵
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, INLIER_DISTANCE, confidence=0.99, maxIters=2000)

    if H is None or mask is None:
        break

    matches_mask = mask.ravel().tolist()
    inlier_matches = [good_matches[i] for i in range(len(good_matches)) if matches_mask[i]]

    if len(inlier_matches) < MIN_MATCH_COUNT:
        break

    # 使用内点重新计算单应性矩阵
    inlier_src = np.float32([kp1[m.queryIdx].pt for m in inlier_matches]).reshape(-1, 1, 2)
    inlier_dst = np.float32([kp2[m.trainIdx].pt for m in inlier_matches]).reshape(-1, 1, 2)
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

    # 重叠检测（去重）
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
        # 添加新包围框
        bounding_boxes.append((x_min, x_max, y_min, y_max))
        # 在原始彩色图像上绘制绿色矩形
        cv2.rectangle(result_image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        print(f" 成功添加一个匹配实例，位置: ({x_min}, {y_min}) - ({x_max}, {y_max})")

    # 将本次内点对应的 trainIdx 标记为已使用
    used_train_indices.update(m.trainIdx for m in inlier_matches)

# 输出结果
print(f"\n 总共找到 {len(bounding_boxes)} 个满足匹配率阈值的匹配实例")

# 计算运行时间
end_time = time.time()
execution_time = end_time - start_time
print(f"代码运行时间: {execution_time:.2f} 秒")

# 显示结果
cv2.imshow('Matched Result', result_image)
cv2.waitKey(0)
cv2.destroyAllWindows()