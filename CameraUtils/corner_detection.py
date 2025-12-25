import cv2
import numpy as np
import json
from pathlib import Path
from threading import Thread, Timer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
        # 配置文件路径
        self.image_path = Path(image_path)
        self.config_path = self.image_path.parent / "fixed_corners.json"
        # 启动配置文件监听（热更新）
        self.watcher = self.ConfigFileWatcher(self, self.config_path)
        self.watcher.start()

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
        self.corners = {
            "top_left_corner": tuple(map(int, tl)),
            "top_right_corner": tuple(map(int, tr)),
            "bottom_left_corner": tuple(map(int, bl)),
            "bottom_right_corner": tuple(map(int, br))
        }
        print("原始图像中检测到的角点坐标：")
        for k, v in self.corners.items():
            print(f"   {k}: {v}")
        # 自动保存
        self.save_corners()

    def reset(self):
        """重置所有已选角点，允许重新点击选择"""
        self.points = []
        self.real_points = []
        self.corners = None
        self.working_image = self.display_image.copy()  # 恢复原始显示图像
        cv2.imshow("Manual Corner Detector", self.working_image)
        print("已重置，可重新选择4个角点...")

    def save_corners(self):
        """将当前角点自动保存为 JSON 文件"""
        if not self.corners:
            print("没有可保存的角点数据")
            return
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.corners, f, indent=4, ensure_ascii=False)
            print(f"角点已自动保存至: {self.config_path}")
        except Exception as e:
            print(f"保存配置失败: {e}")

    def load_corners(self):
        """从 JSON 文件加载角点并刷新显示（支持热更新）"""
        if not self.config_path.exists():
            print(f"角点配置文件不存在: {self.config_path}")
            return False
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            required_keys = ["top_left_corner", "top_right_corner", "bottom_left_corner", "bottom_right_corner"]
            if not all(k in data for k in required_keys):
                print("角点配置文件格式错误：缺少必要键")
                return False
            self.corners = {k: tuple(v) for k, v in data.items()}
            ordered_pts = [
                self.corners["top_left_corner"],
                self.corners["top_right_corner"],
                self.corners["bottom_left_corner"],
                self.corners["bottom_right_corner"]
            ]
            self.real_points = ordered_pts
            self.points = [(int(x / self.scale_x), int(y / self.scale_y)) for x, y in ordered_pts]
            self._redraw_with_corners()
            print(f"已热更新加载角点配置: {self.config_path}")
            return True
        except Exception as e:
            print(f"加载角点配置失败: {e}")
            return False

    def _redraw_with_corners(self):
        """根据当前 corners 重绘图像"""
        self.working_image = self.display_image.copy()
        pts_d = {}
        for key, pt in self.corners.items():
            x_d = int(pt[0] / self.scale_x)
            y_d = int(pt[1] / self.scale_y)
            pts_d[key] = (x_d, y_d)
            cv2.circle(self.working_image, (x_d, y_d), 5, (0, 255, 0), -1)
        cv2.line(self.working_image, pts_d["top_left_corner"], pts_d["top_right_corner"], (255, 0, 0), 2)
        cv2.line(self.working_image, pts_d["top_right_corner"], pts_d["bottom_right_corner"], (255, 0, 0), 2)
        cv2.line(self.working_image, pts_d["bottom_right_corner"], pts_d["bottom_left_corner"], (255, 0, 0), 2)
        cv2.line(self.working_image, pts_d["bottom_left_corner"], pts_d["top_left_corner"], (255, 0, 0), 2)
        label_map = {
            "top_left_corner": "TL",
            "top_right_corner": "TR",
            "bottom_left_corner": "BL",
            "bottom_right_corner": "BR"
        }
        for key, label in label_map.items():
            pt = pts_d[key]
            cv2.circle(self.working_image, pt, 6, (0, 0, 255), -1)
            offset_x = -10 if "L" in label else 10
            offset_y = -10 if "T" in label else 20
            cv2.putText(self.working_image, label, (pt[0] + offset_x, pt[1] + offset_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.imshow("Manual Corner Detector", self.working_image)

    def run(self):
        """启动角点检测"""
        cv2.namedWindow("Manual Corner Detector", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Manual Corner Detector", self.display_width, self.display_height)
        cv2.imshow("Manual Corner Detector", self.working_image)
        cv2.setMouseCallback("Manual Corner Detector", self.click_event)

        print("\n📌 操作说明:")
        print("   - 点击图像选择4个角点（顺序任意）")
        print("   - 选完4个点后将自动保存配置")
        print("   - 'r' 键: 重置选择")
        print("   - ESC 或任意键退出")

        # --- 使用非阻塞循环，支持热更新 ---
        while True:
            key = cv2.waitKey(10) & 0xFF  # 每10ms检查一次
            if key == 27:  # ESC
                break
            elif key == ord('r'):
                self.reset()
        cv2.destroyAllWindows()
        return self.corners if hasattr(self, 'corners') and self.corners else None

    # 内部类：文件监听器
    class ConfigFileWatcher:
        """监听配置文件变化，实现热更新（带防抖）"""
        def __init__(self, detector, config_path):
            self.detector = detector
            self.config_path = Path(config_path)
            self.directory = self.config_path.parent
            self.observer = Observer()
            self.timer = None  # 防抖定时器

        def on_modified(self):
            """防抖处理：合并短时间内多次修改"""
            if self.timer:
                self.timer.cancel()
            self.timer = Timer(0.3, self._load_now)
            self.timer.start()

        def _load_now(self):
            """执行实际加载"""
            self.detector.load_corners()
            self.timer = None

        class Handler(FileSystemEventHandler):
            def __init__(self, watcher):
                super().__init__()
                self.watcher = watcher

            def on_modified(self, event):
                if not event.is_directory and Path(event.src_path) == self.watcher.config_path:
                    print(f"🔄 检测到配置文件修改: {event.src_path}")
                    self.watcher.on_modified()

        def start(self):
            event_handler = self.Handler(self)
            self.observer.schedule(event_handler, str(self.directory), recursive=False)
            thread = Thread(target=self.observer.start, daemon=True)
            thread.start()
            print(f"📁 正在监听配置文件变化: {self.config_path}")


# 使用示例
if __name__ == "__main__":
    image_path = "CameraUtils/test_image2.jpg"  # 替换为你的图像路径
    # --- 可选：检查图像是否存在 ---
    if not Path(image_path).exists():
        print(f"图像文件不存在: {image_path}")
    else:
        detector = ManualCornerDetector(image_path, display_width=960, display_height=540)
        corners = detector.run()

    # (640, 360),   # nHD
    # (960, 540),   # qHD
    # (1280, 720),  # HD / 720p 
    # (1920, 1080), # Full HD / 1080p