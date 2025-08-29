import cv2
import numpy as np

def template_match_advanced(image_path, template_path):
    # 读取图像和模板
    image = cv2.imread(image_path)
    template = cv2.imread(template_path)

    if image is None or template is None:
        print("❌ 错误：图像或模板文件未找到，请检查路径是否正确。")
        return

    print(f"✅ 图像尺寸: {image.shape[1]}x{image.shape[0]}")
    print(f"✅ 模板尺寸: {template.shape[1]}x{template.shape[0]}")

    # 转换为灰度图像
    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    # 使用SIFT特征检测器
    sift = cv2.SIFT_create()

    # 检测关键点和描述子
    kp1, des1 = sift.detectAndCompute(template_gray, None)
    kp2, des2 = sift.detectAndCompute(image_gray, None)

    print(f"✅ 模板图像检测到 {len(kp1)} 个关键点")
    print(f"✅ 目标图像检测到 {len(kp2)} 个关键点")

    # 使用FLANN匹配器进行特征匹配
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1, des2, k=2)

    # 筛选好的匹配点
    good_matches = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good_matches.append(m)

    print(f"✅ 初始匹配点数量: {len(matches)}")
    print(f"✅ 筛选后有效匹配点数量: {len(good_matches)}")

    # 至少需要4个匹配点来计算单应性矩阵
    if len(good_matches) >= 4:
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # 使用RANSAC算法计算单应性矩阵
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

        if M is not None:
            h, w = template_gray.shape
            pts = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)
            dst = cv2.perspectiveTransform(pts, M)

            # 绘制匹配区域
            image_with_box = cv2.polylines(image, [np.int32(dst)], True, (0, 255, 0), 3, cv2.LINE_AA)
            print("✅ 成功找到模板匹配区域！")

            # 显示结果
            cv2.imshow('Matched Image', image_with_box)
            print("📸 按任意键关闭窗口...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            print("❌ 无法找到单应性矩阵")
    else:
        print(f"❌ 匹配点不足，只有 {len(good_matches)} 个匹配点")

# 测试代码
image_path = 'test.png'  # 替换为你的图像路径
template_path = 'kmh.png'  # 替换为你的模板路径
template_match_advanced(image_path, template_path)