import cv2
import numpy as np

class ManualCornerDetector:
    """
    手动角点检测器：用户在固定大小的图像上点击4个点，
    程序自动判断并连接为四边形（TL, TR, BL, BR），支持坐标映射回原图。
    """
    def __init__(self, image_path, display_width=640, display_height=360):
        self.original_image = cv2.imread(image_path)
        if self.original_image is None:
            raise FileNotFoundError(f"无法加载图像: {image_path}")

        self.orig_height, self.orig_width = self.original_image.shape[:2]
        self.display_width = display_width
        self.display_height = display_height

        # 缩放比例（原始 -> 显示）
        self.scale_x = self.orig_width / self.display_width
        self.scale_y = self.orig_height / self.display_height

        # 缩放图像用于显示
        self.display_image = cv2.resize(self.original_image, (display_width, display_height))
        self.working_image = self.display_image.copy()
        self.points = []        # 存储显示坐标 (x, y)
        self.real_points = []   # 存储原始图像坐标

    def click_event(self, event, x, y, flags, param):
        """鼠标点击，手动选择图像中的四个角点"""
        if event == cv2.EVENT_LBUTTONDOWN:      # 判断鼠标左键点击事件
            if len(self.points) < 4:
                self.points.append((x, y))
                real_x = int(x * self.scale_x)
                real_y = int(y * self.scale_y)
                self.real_points.append((real_x, real_y))

                # 在图像上标记
                cv2.circle(self.working_image, (x, y), 5, (0, 255, 0), -1)
                cv2.imshow("Manual Corner Detector", self.working_image)
                # print(f"点击位置 (显示): ({x}, {y}) → 原图: ({real_x}, {real_y})")

                if len(self.points) == 4:
                    self._connect_corners()

    def _connect_corners(self):
        # 使用原始坐标判断位置
        pts = np.array(self.real_points, dtype="float32")

        # 按 x 分左右
        sorted_x = pts[np.argsort(pts[:, 0])]
        left_group = sorted_x[:2]
        right_group = sorted_x[2:]

        # 每组按 y 分上下
        tl = left_group[np.argsort(left_group[:, 1])][0]  # 左上
        bl = left_group[np.argsort(left_group[:, 1])][1]  # 左下
        tr = right_group[np.argsort(right_group[:, 1])][0]  # 右上
        br = right_group[np.argsort(right_group[:, 1])][1]  # 右下

        # 映射回显示坐标绘图
        def to_display(pt):
            return (int(pt[0] / self.scale_x), int(pt[1] / self.scale_y))

        tl_d, tr_d, bl_d, br_d = map(to_display, [tl, tr, bl, br])

        # 绘制边框
        cv2.line(self.working_image, tl_d, tr_d, (255, 0, 0), 2)
        cv2.line(self.working_image, tr_d, br_d, (255, 0, 0), 2)
        cv2.line(self.working_image, br_d, bl_d, (255, 0, 0), 2)
        cv2.line(self.working_image, bl_d, tl_d, (255, 0, 0), 2)

        # 标记角点
        for pt, label in zip([tl_d, tr_d, bl_d, br_d], ["TL", "TR", "BL", "BR"]):
            cv2.circle(self.working_image, pt, 6, (0, 0, 255), -1)
            offset_x = -10 if "L" in label else 10
            offset_y = -10 if "T" in label else 20
            cv2.putText(self.working_image, label, (pt[0] + offset_x, pt[1] + offset_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        cv2.imshow("Manual Corner Detector", self.working_image)
        print("已自动识别并连接四个角点")

        # 输出原始图像中的坐标（可用于后续处理，如透视变换）
        corners = {
            "top_left": tuple(map(int, tl)),
            "top_right": tuple(map(int, tr)),
            "bottom_left": tuple(map(int, bl)),
            "bottom_right": tuple(map(int, br))
        }
        print("原始图像中检测到的角点坐标：")
        for k, v in corners.items():
            print(f"   {k}: {v}")

        # 返回角点坐标
        self.corners = corners

    def reset(self):
        """重置所有已选角点，允许重新点击选择"""
        self.points = []
        self.real_points = []
        self.corners = None
        self.working_image = self.display_image.copy()  # 恢复原始显示图像
        cv2.imshow("Manual Corner Detector", self.working_image)
        print("已重置，可重新选择4个角点...")

    def run(self):
        """启动角点检测"""
        cv2.namedWindow("Manual Corner Detector", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Manual Corner Detector", self.display_width, self.display_height)
        cv2.imshow("Manual Corner Detector", self.working_image)
        cv2.setMouseCallback("Manual Corner Detector", self.click_event)
        print(f"请在图像上点击 4 个角点（顺序任意）...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        # 返回检测到的角点
        if hasattr(self, 'corners'):
            return self.corners
        return None


# 使用示例
if __name__ == "__main__":
    image_path = "CameraUtils/test_image2.jpg"  # 替换为你的图像路径
    detector = ManualCornerDetector(image_path, display_width=640, display_height=360)
    corners = detector.run()