import cv2
import numpy as np
import json
from pathlib import Path
from threading import Thread, Timer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class PerspectiveCalibrator:
    """
    透视校准器：用户在缩放后的图像上点击4个点，
    程序自动识别为四边形（TL, TR, BL, BR），支持：
      - 角点保存与热更新
      - 透视变换校正（拉直）
      - 变换图像保存
      - 四边形等比例缩放（z: +5%, x: -5%, e: 重置缩放比例）
      - 输出分辨率预设（在初始化时设置）
    适用于文档扫描、投影对齐等场景。
    """
    def __init__(self, image_path, display_width=960, display_height=540, output_resolution="original"):
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

        # ---------- 新增用于拖拽的状态 ----------
        self.dragging = False          # 是否正在拖拽
        self.drag_point_idx = None     # 正在拖拽的点在 self.points 中的下标
        self.point_order = []          # 角点键的顺序，例如 ["top_left_corner", ...]
        # -----------------------------------------

        # 输出分辨率设置（在代码中硬编码设置）
        self.output_resolution = output_resolution  # "720p", "1080p", "original"

        # 配置文件路径
        self.image_path = Path(image_path)
        self.config_path = self.image_path.parent / "fixed_corners.json"

        # 保存原始角点和当前缩放比例
        self.original_corners = None  # 原始检测到的角点
        self.current_scale = 1.0      # 当前缩放比例

        # 缓存透视矩阵（首次计算后保存、后续热更新直接使用）
        self.perspective_matrix = None

        # 启动配置文件监听（热更新）
        self.watcher = self.ConfigFileWatcher(self, self.config_path)
        self.watcher.start()

    def click_event(self, event, x, y, flags, param):
        """鼠标点击，手动选择图像中的四个角点或拖拽已选角点"""
        # ---------- (1)仍在收集 4 个点 ----------
        if len(self.points) < 4:
            if event == cv2.EVENT_LBUTTONDOWN:      # 判断鼠标左键点击事件
                self.points.append((x, y))
                real_x = int(x * self.scale_x)
                real_y = int(y * self.scale_y)
                self.real_points.append((real_x, real_y))
                # 在图像上标记
                cv2.circle(self.working_image, (x, y), 5, (0, 255, 0), -1)
                cv2.imshow("Manual Corner Detector", self.working_image)
                if len(self.points) == 4:
                    self._finalize_quad_selection()
            return
        # ---------- (2)已有 4 点 → 进入拖拽模式 ----------
        # 2.1 鼠标按下 → 判断是否点在某个角点附近
        if event == cv2.EVENT_LBUTTONDOWN:
            for i, pt in enumerate(self.points):
                # 设定“点击半径”阈值 10 像素
                if (x - pt[0]) ** 2 + (y - pt[1]) ** 2 <= 10 ** 2:
                    self.dragging = True
                    self.drag_point_idx = i
                    break
        # 2.2 鼠标移动且处于拖拽状态 → 实时更新坐标并重绘
        elif event == cv2.EVENT_MOUSEMOVE and self.dragging:
            idx = self.drag_point_idx
            # 更新显示坐标
            self.points[idx] = (x, y)
            # 更新原图坐标
            real_x = int(x * self.scale_x)
            real_y = int(y * self.scale_y)
            self.real_points[idx] = (real_x, real_y)
            # 同步到 corners 字典（利用 point_order 保存的键名）
            corner_key = self.point_order[idx]
            self.corners[corner_key] = (real_x, real_y)
            # 重新绘制四边形
            self._redraw_with_corners()
        # 2.3 鼠标左键弹起 → 结束拖拽，保存并重新做透视变换
        elif event == cv2.EVENT_LBUTTONUP and self.dragging:
            self.dragging = False
            self.drag_point_idx = None
            # 将当前拖拽后的结果设为新的“原始”角点，便于后续缩放基准
            self.original_corners = self.corners.copy()
            self.current_scale = 1.0
            # 清除旧的透视矩阵，使后续计算得到最新矩阵
            self.perspective_matrix = None  
            # 直接重新计算并保存（save 在 apply 中完成）
            self.apply_perspective_transform()   

    def _finalize_quad_selection(self):
        """确认并处理用户选择的四个角点, 完成四边形的构建"""
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
        # 记录角点顺序
        self.point_order = [
            "top_left_corner",
            "top_right_corner",
            "bottom_left_corner",
            "bottom_right_corner"
        ]
        # 保存原始角点作为缩放基准
        self.original_corners = self.corners.copy()
        self.current_scale = 1.0

        # print("原始图像中检测到的角点坐标：")
        # for k, v in self.corners.items():
        #     print(f"   {k}: {v}")

        # 自动保存（此时会连同透视矩阵一起保存，矩阵尚未生成会被忽略）
        self.save_corners()
        # 执行透视变换（首次计算矩阵并写回 JSON）
        self.apply_perspective_transform()

    def scale_quad(self, scale_factor):
        """
        对检测到的四边形进行等比例缩放，保持中心点不变
        scale_factor: 缩放因子，>1 为扩大，<1 为缩小
        """
        if self.original_corners is None:
            print("请先完成四个角点的检测")
            return

        # 计算新的缩放比例
        new_scale = self.current_scale * scale_factor

        # 检查缩放限制
        if new_scale < 0.3 or new_scale > 2.0:
            print(f"缩放比例超出限制 (当前: {self.current_scale:.0%}, 操作后: {new_scale:.0%})")
            print("允许范围: 30% - 200%")
            return

        self.current_scale = new_scale
        print(f"应用缩放: {scale_factor:.0f} → 当前缩放比例: {self.current_scale:.0%}")

        # 计算原始角点的中心点
        pts = np.array([
            self.original_corners["top_left_corner"],
            self.original_corners["top_right_corner"],
            self.original_corners["bottom_left_corner"],
            self.original_corners["bottom_right_corner"]
        ], dtype="float32")

        center = np.mean(pts, axis=0)

        # 计算缩放后的新角点
        scaled_pts = center + (pts - center) * self.current_scale

        # 更新当前角点
        self.corners = {
            "top_left_corner": tuple(map(int, scaled_pts[0])),
            "top_right_corner": tuple(map(int, scaled_pts[1])),
            "bottom_left_corner": tuple(map(int, scaled_pts[2])),
            "bottom_right_corner": tuple(map(int, scaled_pts[3]))
        }

        # 更新 real_points 和 points
        self.real_points = [tuple(map(int, pt)) for pt in scaled_pts]
        self.points = [(int(x / self.scale_x), int(y / self.scale_y)) for x, y in self.real_points]

        # 重绘图像
        self._redraw_with_corners()

        # 清除旧矩阵，使后续得到最新矩阵
        self.perspective_matrix = None         
        # 直接调用 apply（内部会重新计算矩阵并保存）
        self.apply_perspective_transform()   

    def reset_scale(self):
        """重置缩放比例至100%"""
        if self.original_corners is None:
            print("请先完成四个角点的检测")
            return

        self.current_scale = 1.0
        self.corners = self.original_corners.copy()
        self.real_points = [
            self.original_corners["top_left_corner"],
            self.original_corners["top_right_corner"],
            self.original_corners["bottom_left_corner"],
            self.original_corners["bottom_right_corner"]
        ]
        self.points = [(int(x / self.scale_x), int(y / self.scale_y)) for x, y in self.real_points]

        self._redraw_with_corners()
        # 需要重新计算矩阵
        self.perspective_matrix = None         
        self.apply_perspective_transform()     
        print("已重置至原始大小 (100%)")

    def reset(self):
        """重置所有已选角点，允许重新点击选择"""
        self.points = []
        self.real_points = []
        self.corners = None
        self.original_corners = None
        self.current_scale = 1.0
        # 清除缓存的透视矩阵
        self.perspective_matrix = None    
        self.working_image = self.display_image.copy()
        cv2.imshow("Manual Corner Detector", self.working_image)
        print("已重置，可重新选择4个角点...")
        # 安全关闭 "Warped View" 窗口
        try:
            cv2.destroyWindow("Warped View")
        except cv2.error:
            pass  # 窗口不存在时忽略错误

    def save_corners(self):
        """将当前角点自动保存为 JSON 文件"""
        if not self.corners:
            print("没有可保存的角点数据")
            return
        try:
            data_to_save = self.corners.copy()
            # 若已有透视矩阵则一起保存
            if self.perspective_matrix is not None:
                data_to_save["perspective_matrix"] = self.perspective_matrix.tolist() 
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            print(f"角点已自动保存至: {self.config_path}")
        except Exception as e:
            print(f"保存配置失败: {e}")

    def load_corners(self, src_path=None): 
        """从 JSON 文件加载角点并刷新显示（支持热更新）"""
        if src_path: 
            print(f"🔄 检测到配置文件修改: {src_path}")
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
            self.corners = {k: tuple(v) for k, v in data.items() if k in required_keys}
            # 读取透视矩阵
            if "perspective_matrix" in data:
                self.perspective_matrix = np.array(data["perspective_matrix"], dtype=np.float32)  
                print("已加载透视矩阵")
            else:
                self.perspective_matrix = None  
            ordered_pts = [
                self.corners["top_left_corner"],
                self.corners["top_right_corner"],
                self.corners["bottom_left_corner"],
                self.corners["bottom_right_corner"]
            ]
            self.real_points = ordered_pts
            self.points = [(int(x / self.scale_x), int(y / self.scale_y)) for x, y in ordered_pts]
            # 如果是首次加载，将其设为原始角点
            if self.original_corners is None:
                self.original_corners = self.corners.copy()
                self.current_scale = 1.0
            self._redraw_with_corners()
            # print(f"已热更新加载角点配置: {self.config_path}")  # ★ MOD: 注释掉原有的打印
            self.apply_perspective_transform()              # 加载后执行透视变换
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
        """启动角点检测并在两个窗口均被手动关闭时退出"""
        cv2.namedWindow("Manual Corner Detector", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Manual Corner Detector", self.display_width, self.display_height)
        cv2.imshow("Manual Corner Detector", self.working_image)
        cv2.setMouseCallback("Manual Corner Detector", self.click_event)

        # ---------- 显示帮助信息 ----------
        resolution_names = {
            "720p": "720P (1280x720)",
            "1080p": "1080P (1920x1080)",
            "original": f"原始尺寸 ({self.orig_width}x{self.orig_height})"
        }
        current_res_name = resolution_names.get(self.output_resolution, "未知")
        print("\n📌 操作说明:")
        print("   - 点击图像选择4个角点（顺序任意）")
        print("   - 选完4个点后将自动保存配置")
        print("   - 'r' 键: 重置选择")
        print("   - 'e' 键: 重置缩放比例至100%")
        print("   - 'z' 键: 扩大5%")
        print("   - 'x' 键: 缩小5%")
        print("   - 'w' 键: 保存拉直后的图像")
        print(f"   - 当前输出分辨率: {current_res_name}")

        # ---------- 主循环 ----------
        while True:
            key = cv2.waitKey(10) & 0xFF  # 每10ms检查一次键盘

            # ---------- 键盘快捷键 ----------
            if key == ord('r'):               # 小写 r 重置选择
                self.reset()
                try:
                    cv2.destroyWindow("Warped View")
                except:
                    pass
            elif key == ord('e'):             # e 键重置缩放比例至100%
                self.reset_scale()
            elif key == ord('z'):             # 扩大5%
                self.scale_quad(1.05)
            elif key == ord('x'):             # 缩小5%
                self.scale_quad(0.95)
            elif key == ord('w'):             # 保存变换后的图像
                if hasattr(self, 'warped_image') and self.warped_image is not None:
                    output_path = self.image_path.parent / f"{self.image_path.stem}_warped.jpg"
                    cv2.imwrite(str(output_path), self.warped_image)
                    print(f"已保存变换后的图像: {output_path}")
                else:
                    print("无变换图像可保存，请先选择四个角点")

            # ---------- 窗口关闭检测 ----------
            # 当两个窗口都不可见（用户点击右上角 X）时退出循环
            manual_visible = cv2.getWindowProperty(
                "Manual Corner Detector", cv2.WND_PROP_VISIBLE) >= 1  
            warped_visible = cv2.getWindowProperty(
                "Warped View", cv2.WND_PROP_VISIBLE) >= 1       
            if not manual_visible and not warped_visible:       
                # print("检测到两个窗口均已关闭，程序即将退出…") 
                break

        # ---------- 清理 ----------
        cv2.destroyAllWindows()
        return self.corners if hasattr(self, 'corners') and self.corners else None

    def run_auto(self, enable_watch=True, save_output=False):
        """
        自动模式（仅使用 JSON 中已有的透视矩阵对原始图像做透视变换）：
        ----
        enable_watch : bool, default True
            开启/关闭热更新监听。
        save_output : bool, default False
            开启/关闭变换后图像的自动保存。
        """
        # -----------------------------------------------------------------
        # ① 执行一次变换（内部函数，复用两次）
        # -----------------------------------------------------------------
        def _process():
            # 读取 JSON（文件一定存在且格式正确）
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "perspective_matrix" not in data:
                print("❌ 配置文件缺少 `perspective_matrix` 键")
                return False

            # 直接使用保存的矩阵
            self.perspective_matrix = np.array(
                data["perspective_matrix"], dtype=np.float32
            )

            # 计算输出尺寸（保持原有分辨率逻辑）
            if self.output_resolution == "720p":
                width, height = 1280, 720
            elif self.output_resolution == "1080p":
                width, height = 1920, 1080
            else:  # original
                width, height = self.orig_width, self.orig_height

            # 进行透视变换
            self.warped_image = cv2.warpPerspective(
                self.original_image,
                self.perspective_matrix,
                (width, height),
                flags=cv2.INTER_LINEAR,
            )

            # ------------------- 保存（受开关控制） -------------------
            if save_output:
                output_path = (
                    self.image_path.parent
                    / f"{self.image_path.stem}_warped_auto.jpg"
                )
                cv2.imwrite(str(output_path), self.warped_image)
                # print(f"✅ 已完成透视变换并自动保存: {output_path}")
            else:
                # print("✅ 已完成透视变换（未保存文件）")
                pass
            return True
        # -----------------------------------------------------------------
        # ② 第一次处理
        # -----------------------------------------------------------------
        if not _process():
            return None                

        # -----------------------------------------------------------------
        # ③ 可选的热更新监听（同样受 save_output 控制）
        # -----------------------------------------------------------------
        if enable_watch:
            import time
            last_mtime = self.config_path.stat().st_mtime
            print("🔄 已开启 透视变换矩阵 热更新监听 (fixed_corners.json)")
            try:
                while True:
                    time.sleep(2)
                    cur_mtime = self.config_path.stat().st_mtime
                    if cur_mtime != last_mtime:                     # 文件被修改
                        print("🔄 检测到配置文件变化，重新加载并变换")
                        if _process():
                            last_mtime = cur_mtime
            except KeyboardInterrupt:
                # 手动 Ctrl‑C 停止监听
                pass
        return self.warped_image                                        


    def apply_perspective_transform(self):
        """根据四个角点进行透视变换，将四边形区域拉直"""
        if not hasattr(self, 'corners') or not self.corners:
            print("没有可用的角点数据，无法进行透视变换")
            return

        # 若已有缓存矩阵且未被手动清除，则直接使用
        if self.perspective_matrix is not None:
            matrix = self.perspective_matrix
            print("使用已缓存的透视矩阵进行变换")
        else:
            # 获取原始图像中的四个角点（顺序：TL, TR, BR, BL）
            pts_src = np.array([
                self.corners["top_left_corner"],
                self.corners["top_right_corner"],
                self.corners["bottom_right_corner"],
                self.corners["bottom_left_corner"]
            ], dtype="float32")

            # 根据分辨率设置计算目标尺寸
            if self.output_resolution == "720p":
                width, height = 1280, 720
            elif self.output_resolution == "1080p":
                width, height = 1920, 1080
            else:  # original
                width, height = self.orig_width, self.orig_height

            # 目标矩形的四个点
            pts_dst = np.array([
                [0, 0],
                [width - 1, 0],
                [width - 1, height - 1],
                [0, height - 1]
            ], dtype="float32")
            # 计算变换矩阵
            matrix = cv2.getPerspectiveTransform(pts_src, pts_dst)  
            #  缓存矩阵并写回 JSON（确保热更新时可直接读取）
            self.perspective_matrix = matrix  
            self.save_corners()               

        # 根据分辨率设置计算目标尺寸（已在上面计算过，重复使用）
        if self.output_resolution == "720p":
            width, height = 1280, 720
        elif self.output_resolution == "1080p":
            width, height = 1920, 1080
        else:  # original
            width, height = self.orig_width, self.orig_height

        # 执行透视变换，输出原始尺寸图像
        self.warped_image = cv2.warpPerspective(
            self.original_image,
            matrix,
            (width, height),  # 输出尺寸
            flags=cv2.INTER_LINEAR
        )

        # 创建显示用的缩小版本
        display_warped = cv2.resize(self.warped_image, (self.display_width, self.display_height))

        # 显示变换后的图像
        cv2.namedWindow("Warped View", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Warped View", self.display_width, self.display_height)
        cv2.imshow("Warped View", display_warped)

        resolution_names = {
            "720p": "720P (1280x720)",
            "1080p": "1080P (1920x1080)",
            "original": f"原始尺寸 ({self.orig_width}x{self.orig_height})"
        }
        # print(f"透视变换完成 → 输出分辨率: {resolution_names[self.output_resolution]}")

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
            self.detector.load_corners(str(self.config_path))
            self.timer = None

        class Handler(FileSystemEventHandler):
            def __init__(self, watcher):
                super().__init__()
                self.watcher = watcher

            def on_modified(self, event):
                if not event.is_directory and Path(event.src_path) == self.watcher.config_path:
                    # print(f"🔄 检测到配置文件修改: {event.src_path}")
                    self.watcher.on_modified()

        def start(self):
            event_handler = self.Handler(self)
            self.observer.schedule(event_handler, str(self.directory), recursive=False)
            thread = Thread(target=self.observer.start, daemon=True)
            thread.start()
            # print(f"📁 正在监听配置文件变化: {self.config_path}")


# 使用示例
if __name__ == "__main__":
    image_path = "CameraUtils/screenshot_4.png"  # 替换为你的图像路径

    # --- 快速设置输出分辨率（在此修改）---
    # 可选值："720p" | "1080p" | "original"
    OUTPUT_RESOLUTION = "720p"  # ←←← 在这里修改输出分辨率

    # --- 可选：检查图像是否存在 ---
    if not Path(image_path).exists():
        print(f"图像文件不存在: {image_path}")
    else:
        # 创建校准器实例，使用预设的输出分辨率
        detector = PerspectiveCalibrator(
            image_path,
            display_width=640,
            display_height=360,
            output_resolution=OUTPUT_RESOLUTION  # 应用预设分辨率
        )
        corners = detector.run()
    # (640, 360),   # nHD
    # (960, 540),   # qHD
    # (1280, 720),  # HD / 720p 
    # (1920, 1080), # Full HD / 1080p