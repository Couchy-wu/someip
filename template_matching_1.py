import cv2
import numpy as np
import os
import time
from concurrent.futures import ThreadPoolExecutor
from image_preprocessing import preprocess_v_channel
from natsort import natsorted
import shutil  # 用于删除文件夹内容

# =================== 清空文件夹函数 ===================
def clear_folder(folder_path):
    """ 清空指定文件夹中的所有内容（文件和子文件夹）"""
    if not os.path.exists(folder_path):
        return  # 文件夹不存在，无需处理
    
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"无法删除 {file_path}. 原因: {e}")

# =================== 参数配置 ===================
INPUT_FOLDER = 'TemporaryResources/ARHUD/'
OUTPUT_FOLDER = 'Matched_Results/'
MAX_CONCURRENT_JOBS = 4  # 并行线程数
SCALE_RATIO = 1          # 图像缩放比例 (显著影响速度)
FLANN_CHECKS = 50        # FLANN 匹配精度（越低，精度越低）

# =================== 工具函数 ===================

def resize_image(img, scale_ratio):
    """ 缩放图像，减少计算量 """
    return cv2.resize(img, None, fx=scale_ratio, fy=scale_ratio, interpolation=cv2.INTER_AREA)

def process_single_image(file_path, template_info):
    """ 单图像处理函数，用于并行执行 """
    template_gray, kp1, des1 = template_info

    target_bgr = cv2.imread(file_path)
    if target_bgr is None:
        return file_path, None

    # 图像预处理 + 缩放
    target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)
    _, _, target_v = cv2.split(target_hsv)
    target_gray = preprocess_v_channel(target_v)
    target_gray = resize_image(target_gray, SCALE_RATIO)
    target_color = cv2.cvtColor(target_gray, cv2.COLOR_GRAY2BGR)

    # SIFT 特征提取
    sift = cv2.SIFT_create()
    kp2, des2 = sift.detectAndCompute(target_gray, None)

    if des1 is None or des2 is None:
        return file_path, target_color

    # FLANN 匹配（降低 checks 值）
    flann = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=FLANN_CHECKS))
    matches = flann.knnMatch(des1, des2, k=2)
    good = [m for m, n in matches if m.distance < 0.7 * n.distance]

    # 单应性变换
    if len(good) >= 4:
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

        if H is not None:
            h, w = template_gray.shape
            corners = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)
            transformed = cv2.perspectiveTransform(corners, H).astype(int)
            x1, y1 = np.min(transformed[:, 0, :], axis=0)
            x2, y2 = np.max(transformed[:, 0, :], axis=0)
            cv2.rectangle(target_color, (x1, y1), (x2, y2), (0, 255, 0), 2)

    return file_path, target_color

# =================== 主函数 ===================

def main():
    # 1. 预处理模板图像
    template_bgr = cv2.imread('kmh.png')
    if template_bgr is None:
        print("模板图像读取失败")
        return

    template_hsv = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2HSV)
    _, _, template_v = cv2.split(template_hsv)
    template_gray = preprocess_v_channel(template_v)
    template_gray = resize_image(template_gray, SCALE_RATIO)
    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(template_gray, None)

    # 2. 设置输出文件夹
    output_folder = 'Matched_Results/'
    os.makedirs(output_folder, exist_ok=True)
    clear_folder(output_folder)  # 清空文件夹内容

    # 3. 准备图像文件列表
    image_files = natsorted([f for f in os.listdir(INPUT_FOLDER) 
                            if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    file_paths = [os.path.join(INPUT_FOLDER, f) for f in image_files]

    # 4. 并行处理图像
    template_info = (template_gray, kp1, des1)
    results = []

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as executor:
        futures = [executor.submit(process_single_image, path, template_info) for path in file_paths]
        for future in futures:
            file_path, result_img = future.result()
            if result_img is not None:
                base_name = os.path.basename(file_path)
                output_path = os.path.join(output_folder, base_name)
                cv2.imwrite(output_path, result_img)
                print(f"Saved: {output_path}")

# =================== 程序入口 ===================
if __name__ == '__main__':
    start = time.time()
    main()
    end = time.time()
    print(f"总处理时间: {end - start:.2f} 秒")
