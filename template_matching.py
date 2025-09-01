import cv2
import numpy as np
from image_preprocessing import preprocess_v_channel

# 功能：基于描述符的模板匹配
# 核心方法：SIFT + RANSAC
# 步骤：
# 1.图像预处理 ：将图像从BGR转换为HSV颜色空间，并对V通道进行特定的预处理，以增强图像特征。
# 2.特征提取 ：使用SIFT算法在模板和目标图像中提取特征点及其描述子。
# 3.特征匹配 ：通过FLANN匹配器进行特征点匹配，并使用Lowe's比率测试筛选优质匹配点。
# 4.几何变换 ：利用RANSAC算法计算单应性矩阵，确定模板在目标图像中的位置，并绘制包围框。
# 5.结果评估 ：计算匹配率、平均距离和包围框面积占比，评估匹配质量。

# 读取图像（彩色图像）
template_bgr = cv2.imread('kmh.png')    # 模版图像
target_bgr = cv2.imread('image2.png')       # 目标图像

# 转换为HSV颜色空间
template_hsv = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2HSV)
target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)

# 分离通道
template_h, template_s, template_v = cv2.split(template_hsv)
target_h, target_s, target_v = cv2.split(target_hsv)

# 应用预处理函数（仅处理V通道），随后V通道作为灰度图用于特征提取
# preprocess_v_channel--gamma校正 + 高斯滤波 + 图像锐化
template_gray = preprocess_v_channel(template_v)
target_gray = preprocess_v_channel(target_v)

# 初始化SIFT检测器，并调整参数
# SIFT 是一种对尺度和旋转不变的特征提取方法
sift = cv2.SIFT_create(nfeatures=0, nOctaveLayers=3, contrastThreshold=0.04, edgeThreshold=10, sigma=1.0)
# nfeatures         -- 最多检测的关键点数量。0 表示不限制
# nOctaveLayers     -- 高斯金字塔的层数，增加层数可以检测到更细微的尺度变化，但会增加计算量
# contrastThreshold -- 过滤掉低对比度的关键点，保留更稳定的特征点。值越大，关键点越少但更稳定。图对比度低（暗光或糊）可以降低，噪声多可以增加
# edgeThreshold     -- 用于区分边缘与角点的阈值。值越大，越不容易检测到边缘点。如果图像中存在大量边缘，可以适当提高该值
# sigma             -- 初始高斯滤波器的 sigma 值，控制图像的平滑程度。如果图像模糊可以适当增加，如果边缘特征是关键可以适当降低

# 提取特征点和描述子
kp1, des1 = sift.detectAndCompute(template_gray, None)         # 模版图
kp2, des2 = sift.detectAndCompute(target_gray, None)           # 目标图

# 使用FLANN匹配器，并调整参数
FLANN_INDEX_KDTREE = 1
index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)      # 增加 trees 可提升匹配鲁棒性，但占用更多内存，一般设置为 5 或 10，在速度和精度间取得平衡
search_params = dict(checks=50)                                 # 增加 checks 可提高匹配准确性，但会降低速度。建议50或100
flann = cv2.FlannBasedMatcher(index_params, search_params)

# 进行knn匹配
matches = flann.knnMatch(des1, des2, k=2)

# 筛选优质匹配（Lowe's Ratio Test）
# 通过比较最近邻与次近邻的距离，保留稳定性高的匹配点
good_matches = []
for m, n in matches:
    if m.distance < 0.7 * n.distance:
        good_matches.append(m)

# 输出匹配结果的基本信息
print(f"总匹配点数: {len(matches)}")
print(f"优质匹配点数: {len(good_matches)}")
if len(matches) > 0:
    match_rate = (len(good_matches) / len(matches)) * 100
    print(f"匹配率: {match_rate:.2f}%")
else:
    print("无匹配结果")

if len(good_matches) > 0:
    avg_distance = sum(m.distance for m in good_matches) / len(good_matches)
    print(f"平均匹配距离: {avg_distance:.2f}")

# 判断是否找到目标
target_color = cv2.cvtColor(target_gray, cv2.COLOR_GRAY2BGR)
if len(good_matches) >= 4:
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    
    # 使用RANSAC计算单应性矩阵，并调整参数
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 7.0, None, 2000, 0.95)
    
    if H is not None:
        # 获取模板图像的尺寸
        h, w = template_gray.shape
        # 定义模板图像的四个角点
        corners = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)
        # 将角点映射到目标图像上
        transformed_corners = cv2.perspectiveTransform(corners, H)
        # 将变换后的角点转换为整数坐标
        transformed_corners = np.int32(transformed_corners)
        # 计算包围框（轴对齐的矩形）
        x_coords = transformed_corners[:, 0, 0]
        y_coords = transformed_corners[:, 0, 1]
        x_min, x_max = np.min(x_coords), np.max(x_coords)
        y_min, y_max = np.min(y_coords), np.max(y_coords)
        # 绘制轴对齐的矩形框
        cv2.rectangle(target_color, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        # 计算包围框的面积占比
        target_height, target_width = target_gray.shape
        bbox_area = (x_max - x_min) * (y_max - y_min)
        total_area = target_width * target_height
        area_ratio = (bbox_area / total_area) * 100
        print(f"包围框面积占比: {area_ratio:.2f}%")
        print("找到了")
    else:
        print("没找到")
else:
    print("没找到")

# 显示结果
cv2.imshow('Matched Result', target_color)
cv2.waitKey(0)
cv2.destroyAllWindows()