import cv2
import numpy as np

# 功能：图像预处理
# 内容：gamma校正 + 高斯滤波 + 图像锐化 + 边缘提取

def gamma_correction(image, gamma=1.0):
    """使用向量化操作优化的Gamma校正"""
    if gamma <= 0:
        raise ValueError("Gamma值必须大于0")
    inv_gamma = 1.0 / gamma
    table = np.power(np.arange(256)/255.0, inv_gamma) * 255
    table = np.clip(table, 0, 255).astype("uint8")
    return cv2.LUT(image, table)

def preprocess_v_channel(v_channel):
    """对V通道进行预处理——gamma校正+高斯滤波+锐化"""
    gamma = 1.5
    gamma_corrected = gamma_correction(v_channel, gamma)
    blurred = cv2.GaussianBlur(gamma_corrected, (5, 5), 0)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(blurred, -1, kernel)
    return sharpened

def main():
    # 读取并验证图像
    image = cv2.imread("image3.png")
    if image is None or len(image.shape) != 3 or image.shape[2] != 3:
        print("图像读取失败或格式错误")
        return

    # 颜色空间转换
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v_channel = hsv_image[:, :, 2]
    
    # 图像增强处理
    processed_v = preprocess_v_channel(v_channel)
    edges = cv2.Canny(processed_v, 100, 200)
    
    # 结果展示
    cv2.imshow("Edges", edges)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()