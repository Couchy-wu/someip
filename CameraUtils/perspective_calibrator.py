import cv2
import numpy as np
import json
from pathlib import Path
from threading import Thread, Timer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import uuid
import threading

class _GlobalWatcher:
    """
    单例 watchdog.Observer，所有 PerspectiveCalibrator 实例共享同一个 Observer。
    每个实例只需要把自己的回调注册进去，内部统一防抖。
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, directory):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._observer = Observer()
                cls._instance._observer.start()
                cls._instance._handlers = {}      # Path -> [callback, ...]
                cls._instance._directories = {}   # dir -> Handler
            return cls._instance

    def register(self, path: Path, callback):
        """为指定文件注册回调，内部统一防抖。"""
        path = path.resolve()
        directory = str(path.parent)

        # 为目录仅创建一次 Handler
        if directory not in self._directories:
            handler = self._make_handler()
            self._observer.schedule(handler, directory, recursive=False)
            self._directories[directory] = handler

        # 保存回调（同一文件可有多个实例）
        self._handlers.setdefault(path, []).append(callback)

    def _make_handler(self):
        parent = self

        class Handler(FileSystemEventHandler):
            def on_modified(self, event):
                p = Path(event.src_path).resolve()
                if p in parent._handlers:
                    # 防抖 0.3 s，防止一次保存触发多次加载
                    if hasattr(self, "_timer") and self._timer:
                        self._timer.cancel()
                    self._timer = Timer(0.3,
                                        lambda: [cb(str(p)) for cb in parent._handlers[p]])
                    self._timer.start()
        return Handler()

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
    _file_lock = threading.Lock()          # 所有实例共享的文件读写锁

    def __init__(self, image_path=None,          # 改为可选，默认 None
                 display_width=960, display_height=540,
                 output_resolution="original",
                 config_name=None):

        # ---------- 唯一实例标识 ----------
        self._uid = uuid.uuid4().hex[:8]             # 用于窗口名、文件名等唯一化

        # ---------- 窗口名 ----------
        self._win_main   = f"PC-{self._uid}-Manual"   # 主窗口唯一名称
        self._win_warped = f"PC-{self._uid}-Warped"   # 透视结果窗口唯一名称

        # ---------- 基础图像 ----------
        # 支持 image_path=None，避免强制磁盘读取
        if image_path is not None:
            self.original_image = cv2.imread(image_path)
            if self.original_image is None:
                raise FileNotFoundError(f"无法加载图像: {image_path}")
            self.orig_height, self.orig_width = self.original_image.shape[:2]
        else:
            # 延迟初始化，等待 run_auto 的 image_data
            self.original_image = None
            self.orig_height = 0
            self.orig_width = 0
        # ---------- 显示尺寸 ----------
        self.display_width = display_width
        self.display_height = display_height

        # ---------- 基准比例（原始 → 显示） ----------
        # 避免除零，若原始尺寸为0则先设为1
        self.base_scale_x = (self.orig_width / self.display_width) if self.orig_width > 0 else 1.0
        self.base_scale_y = (self.orig_height / self.display_height) if self.orig_height > 0 else 1.0
        # ---------- 当前整体缩放（放大/缩小） ----------
        self.current_scale = 1.0

        # ---------- 用于显示的缩放图 ----------
        # 若原始图像未加载，则创建空白占位图，避免后续报错
        if self.original_image is not None:
            self.display_image = cv2.resize(self.original_image,
                                           (display_width, display_height))
        else:
            self.display_image = np.zeros((display_height, display_width, 3), dtype=np.uint8)
        self.working_image = self.display_image.copy()

        # ---------- 坐标容器 ----------
        self.points = []        # 显示坐标 (float, float) —— 用 float 防止累计取整误差
        self.real_points = []   # 原始图像坐标 (int, int)

        # ---------- 拖拽状态 ----------
        self.dragging = False
        self.drag_point_idx = None
        self.point_order = []   # 角点键的顺序，例如 ["top_left_corner", ...]

        # ---------- 输出分辨率 ----------
        self.output_resolution = output_resolution  # "720p", "1080p", "original"

        # ---------- 配置文件 ----------
        # 当 image_path 为 None 时，使用空路径（后续依赖 image_path 的地方已做保护）
        self.image_path = Path(image_path) if image_path is not None else Path("memory_buffer")
        self._config_dir = Path(__file__).resolve().parent
        self.config_path = self._config_dir / "fixed_corners.json"

        # ---------- 缓存 ----------
        self.original_corners = None      # 原始检测到的角点（用于缩放基准）
        self.corners = None               # 初始化 corners 属性
        self.perspective_matrix = None    # 计算好的透视矩阵（热更新直接使用）
        # ---------- Canny边缘显示标志 ----------
        self.show_canny = False

    def _on_config_modified(self, path_str):
        """文件被外部修改后，仅在本实例内部重新加载角点/矩阵。"""
        self.load_corners(path_str)

    # -----------------------------------------------------------------
    # 1️⃣ 鼠标事件：点击、拖拽
    # -----------------------------------------------------------------
    def click_event(self, event, x, y, flags, param):
        """
        鼠标点击或拖拽。
        - 前四次点击收集点
        - 收集完后进入拖拽模式
        """
        # ---------- (1) 仍在收集 4 个点 ----------
        if len(self.points) < 4:
            if event == cv2.EVENT_LBUTTONDOWN:
                # 保存 **显示坐标**（float，防止后续累计误差）
                self.points.append((float(x), float(y)))
                # 显示坐标 → 原始坐标（考虑当前整体缩放）
                real_x = int(x * self.base_scale_x / self.current_scale)
                real_y = int(y * self.base_scale_y / self.current_scale)
                self.real_points.append((real_x, real_y))
                # 在图像上标记
                cv2.circle(self.working_image, (x, y), 5, (0, 255, 0), -1)
                cv2.imshow(self._win_main, self.working_image)
                if len(self.points) == 4:
                    self._finalize_quad_selection()
            return
        # ---------- (2) 已有 4 点 → 进入拖拽模式 ----------
        # 2.1 鼠标按下 → 判断是否点在某个角点附近
        if event == cv2.EVENT_LBUTTONDOWN:
            for i, pt in enumerate(self.points):
                if (x - pt[0]) ** 2 + (y - pt[1]) ** 2 <= 10 ** 2:   # 10px 半径
                    self.dragging = True
                    self.drag_point_idx = i
                    break
        # 2.2 鼠标移动且处于拖拽状态 → 实时更新坐标并重绘
        elif event == cv2.EVENT_MOUSEMOVE and self.dragging:
            idx = self.drag_point_idx
            # 更新 **显示坐标**（float）
            self.points[idx] = (float(x), float(y))
            # 计算对应的 **原始坐标**（考虑整体缩放）
            real_x = int(x * self.base_scale_x / self.current_scale)
            real_y = int(y * self.base_scale_y / self.current_scale)
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
            # 清除旧的透视矩阵，使后续得到最新矩阵
            self.perspective_matrix = None
            # 直接重新计算并保存（save 在 apply 中完成）
            self.apply_perspective_transform()

    # -----------------------------------------------------------------
    # 2️⃣ 完成四点选择后自动排序并绘制
    # -----------------------------------------------------------------
    def _finalize_quad_selection(self):
        """确认并处理用户选择的四个角点, 完成四边形的构建"""
        pts = np.array(self.real_points, dtype="float32")
        # 按 x 分左右
        sorted_x = pts[np.argsort(pts[:, 0])]
        left_group = sorted_x[:2]
        right_group = sorted_x[2:]
        # 每组按 y 分上下
        tl = left_group[np.argsort(left_group[:, 1])][0]   # 左上
        bl = left_group[np.argsort(left_group[:, 1])][1]   # 左下
        tr = right_group[np.argsort(right_group[:, 1])][0] # 右上
        br = right_group[np.argsort(right_group[:, 1])][1] # 右下
        # 将原始坐标映射回显示坐标（考虑当前缩放比例），并统一保存顺序
        def to_display(pt):
            return (int(pt[0] / self.base_scale_x * self.current_scale),
                    int(pt[1] / self.base_scale_y * self.current_scale))

        tl_d, tr_d, bl_d, br_d = map(to_display, [tl, tr, bl, br])

        # 保存显示坐标（float）供后续拖拽使用，顺序必须与 point_order 对应
        self.points = [
            (float(tl_d[0]), float(tl_d[1])),
            (float(tr_d[0]), float(tr_d[1])),
            (float(bl_d[0]), float(bl_d[1])),
            (float(br_d[0]), float(br_d[1]))
        ]

        # 绘制边框
        cv2.line(self.working_image, tl_d, tr_d, (255, 0, 0), 1)
        cv2.line(self.working_image, tr_d, br_d, (255, 0, 0), 1)
        cv2.line(self.working_image, br_d, bl_d, (255, 0, 0), 1)
        cv2.line(self.working_image, bl_d, tl_d, (255, 0, 0), 1)
        # 标记角点
        for pt, label in zip([tl_d, tr_d, bl_d, br_d], ["TL", "TR", "BL", "BR"]):
            cv2.circle(self.working_image, pt, 6, (0, 0, 255), -1)
            offset_x = -10 if "L" in label else 10
            offset_y = -10 if "T" in label else 20
            cv2.putText(self.working_image, label,
                        (pt[0] + offset_x, pt[1] + offset_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.imshow(self._win_main, self.working_image)
        print("已自动识别并连接四个角点")

        # 保存四个角点（原始坐标）
        self.corners = {
            "top_left_corner": tuple(map(int, tl)),
            "top_right_corner": tuple(map(int, tr)),
            "bottom_left_corner": tuple(map(int, bl)),
            "bottom_right_corner": tuple(map(int, br))
        }
        # 记录角点顺序（后续拖拽需要）
        self.point_order = [
            "top_left_corner",
            "top_right_corner",
            "bottom_left_corner",
            "bottom_right_corner"
        ]
        # 保存原始角点作为缩放基准
        self.original_corners = self.corners.copy()
        self.current_scale = 1.0
        # 自动保存（此时会连同透视矩阵一起保存，矩阵尚未生成会被忽略）
        self.save_corners()
        # 执行透视变换（首次计算矩阵并写回 JSON）
        self.apply_perspective_transform()

    # -----------------------------------------------------------------
    # 3️⃣ 缩放四边形（保持中心不变）
    # -----------------------------------------------------------------
    def scale_quad(self, scale_factor):
        """
        对检测到的四边形进行等比例缩放，保持中心点不变
        scale_factor: 缩放因子，>1 为扩大，<1 为缩小
        """
        if self.original_corners is None:
            print("请先完成四个角点的检测")
            return

        # 计算新的累计缩放比例
        new_scale = self.current_scale * scale_factor
        if new_scale < 0.3 or new_scale > 2.0:
            print(f"缩放比例超出限制 (当前: {self.current_scale:.0%}, 操作后: {new_scale:.0%})")
            print("允许范围: 30% - 200%")
            return

        # 使用 **原始角点** 进行缩放，得到实际坐标（仍是原始图像坐标）
        pts = np.array([
            self.original_corners["top_left_corner"],
            self.original_corners["top_right_corner"],
            self.original_corners["bottom_left_corner"],
            self.original_corners["bottom_right_corner"]
        ], dtype="float32")

        center = np.mean(pts, axis=0)                     # 四边形中心
        scaled_pts = center + (pts - center) * new_scale   # 按 new_scale 缩放

        # ---------- 更新内部状态 ----------
        # 1) 角点（原始坐标）已被缩放
        self.corners = {
            "top_left_corner":     tuple(map(int, scaled_pts[0])),
            "top_right_corner":    tuple(map(int, scaled_pts[1])),
            "bottom_left_corner":  tuple(map(int, scaled_pts[2])),
            "bottom_right_corner": tuple(map(int, scaled_pts[3])),
        }

        # 2) real_points 与 corners 同步（整数坐标）
        self.real_points = [tuple(map(int, pt)) for pt in scaled_pts]

        # 3) 计算 **显示坐标**（float），此处只把原始坐标映射到显示尺寸，
        #    不再乘以 self.current_scale，因为 corners 已经包含了累计缩放。
        self.points = [
            (pt[0] / self.base_scale_x, pt[1] / self.base_scale_y) for pt in scaled_pts
        ]

        # 4) 更新累计缩放比例
        self.current_scale = new_scale

        # ---------- 调试信息 ----------
        print(f"已应用缩放: {scale_factor:.0%} → 累计缩放: {self.current_scale:.0%}")

        # ---------- 重绘 ----------
        self._redraw_with_corners()

        # 清除旧矩阵，使后续得到最新矩阵
        self.perspective_matrix = None
        # 重新计算并保存透视矩阵
        self.apply_perspective_transform()

    # -----------------------------------------------------------------
    # 4️⃣ 重置缩放至 100%
    # -----------------------------------------------------------------
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
        # 重新计算显示坐标（float）
        self.points = [(x / self.base_scale_x, y / self.base_scale_y)
                       for (x, y) in self.real_points]
        self._redraw_with_corners()
        # 需要重新计算矩阵
        self.perspective_matrix = None
        self.apply_perspective_transform()
        print("已重置至原始大小 (100%)")

    # -----------------------------------------------------------------
    # 5️⃣ 完全重置，重新开始选择
    # -----------------------------------------------------------------
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
        cv2.imshow(self._win_main, self.working_image)
        print("已重置，可重新选择4个角点...")
        # 安全关闭 "Warped View" 窗口
        try:
            cv2.destroyWindow("Warped View")
        except cv2.error:
            pass

    # -----------------------------------------------------------------
    # 6️⃣ 保存角点（包括透视矩阵）
    # -----------------------------------------------------------------
    def save_corners(self):
        """将当前角点自动保存为 JSON 文件"""
        if not self.corners:
            print("没有可保存的角点数据")
            return
        # 加全局写锁，防止多实例并发写入同一文件
        with PerspectiveCalibrator._file_lock:
            try:
                data_to_save = self.corners.copy()
                if self.perspective_matrix is not None:
                    data_to_save["perspective_matrix"] = self.perspective_matrix.tolist()
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"保存配置失败: {e}")

    # -----------------------------------------------------------------
    # 7️⃣ 加载角点（热更新）
    # -----------------------------------------------------------------
    def load_corners(self, src_path=None):
        """从 JSON 文件加载角点并刷新显示（支持热更新）"""
        if src_path:
            pass    # 保留占位，保持原接口
        if not self.config_path.exists():
            print(f"角点配置文件不存在: {self.config_path}")
            return False

        # 加全局读锁，防止读取时被其他实例写入覆盖
        with PerspectiveCalibrator._file_lock:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"加载角点配置失败: {e}")
                return False

        required_keys = ["top_left_corner", "top_right_corner",
                         "bottom_left_corner", "bottom_right_corner"]
        if not all(k in data for k in required_keys):
            print("角点配置文件格式错误：缺少必要键")
            return False

        # 读取角点（原始坐标）
        self.corners = {k: tuple(v) for k, v in data.items()
                        if k in required_keys}
        # 读取透视矩阵（若有）
        if "perspective_matrix" in data:
            self.perspective_matrix = np.array(
                data["perspective_matrix"], dtype=np.float32)
        else:
            self.perspective_matrix = None

        ordered_pts = [
            self.corners["top_left_corner"],
            self.corners["top_right_corner"],
            self.corners["bottom_left_corner"],
            self.corners["bottom_right_corner"]
        ]
        self.real_points = ordered_pts
        # 计算显示坐标（float，考虑当前整体缩放）
        self.points = [(x / self.base_scale_x * self.current_scale,
                        y / self.base_scale_y * self.current_scale)
                       for (x, y) in ordered_pts]

        # 记录角点顺序，以便后续拖拽时能够映射到字典键
        self.point_order = [
            "top_left_corner",
            "top_right_corner",
            "bottom_left_corner",
            "bottom_right_corner"
        ]

        # 第一次加载时设为基准
        if self.original_corners is None:
            self.original_corners = self.corners.copy()
            self.current_scale = 1.0

        self._redraw_with_corners()
        self.apply_perspective_transform()
        return True

    # -----------------------------------------------------------------
    # 8️⃣ 根据当前 corners 重绘显示图像
    # -----------------------------------------------------------------
    def _redraw_with_corners(self):
        """根据当前 corners（原始坐标）重新绘制显示图像"""
        self.working_image = self.display_image.copy()
        
        # 检查角点是否存在，避免未选择角点时调用报错
        if self.corners is None:
            # 仅显示Canny边缘（如果开启）
            if self.show_canny:
                gray = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150)
                edges_colored = np.zeros_like(self.original_image)
                edges_colored[edges > 0] = [0, 255, 0]
                edges_display = cv2.resize(edges_colored, (self.display_width, self.display_height))
                self.working_image = cv2.addWeighted(self.working_image, 1.0, edges_display, 1.0, 0)
            cv2.imshow(self._win_main, self.working_image)
            return
        
        pts_disp = {}
        for key, (rx, ry) in self.corners.items():
            # 原始 → 显示（**不再乘以 self.current_scale**，因为 corners 已经是
            # 已经缩放后的原始坐标）
            disp_x = int(rx / self.base_scale_x)
            disp_y = int(ry / self.base_scale_y)
            pts_disp[key] = (disp_x, disp_y)
            cv2.circle(self.working_image, (disp_x, disp_y), 5,
                       (0, 255, 0), -1)

        # 四条边
        cv2.line(self.working_image, pts_disp["top_left_corner"],
                 pts_disp["top_right_corner"], (255, 0, 0), 1)
        cv2.line(self.working_image, pts_disp["top_right_corner"],
                 pts_disp["bottom_right_corner"], (255, 0, 0), 1)
        cv2.line(self.working_image, pts_disp["bottom_right_corner"],
                 pts_disp["bottom_left_corner"], (255, 0, 0), 1)
        cv2.line(self.working_image, pts_disp["bottom_left_corner"],
                 pts_disp["top_left_corner"], (255, 0, 0), 1)

        label_map = {
            "top_left_corner": "TL",
            "top_right_corner": "TR",
            "bottom_left_corner": "BL",
            "bottom_right_corner": "BR"
        }
        for key, label in label_map.items():
            pt = pts_disp[key]
            cv2.circle(self.working_image, pt, 6, (0, 0, 255), -1)
            offset_x = -10 if "L" in label else 10
            offset_y = -10 if "T" in label else 20
            cv2.putText(self.working_image, label,
                        (pt[0] + offset_x, pt[1] + offset_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # 叠加Canny边缘（辅助角点选择）
        if hasattr(self, 'show_canny') and self.show_canny:
            gray = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edges_colored = np.zeros_like(self.original_image)
            edges_colored[edges > 0] = [0, 255, 0]
            edges_display = cv2.resize(edges_colored, (self.display_width, self.display_height))
            self.working_image = cv2.addWeighted(self.working_image, 1.0, edges_display, 1.0, 0)
        
        cv2.imshow(self._win_main, self.working_image)

    # -----------------------------------------------------------------
    # 9️⃣ 主交互循环
    # -----------------------------------------------------------------
    def run(self):
        """启动角点检测并在两个窗口均被手动关闭时退出"""
        cv2.namedWindow(self._win_main, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self._win_main,
                         self.display_width, self.display_height)
        cv2.imshow(self._win_main, self.working_image)
        cv2.setMouseCallback(self._win_main, self.click_event)
        # ---------- 帮助信息 ----------
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
        print("   - 't' 键: 切换Canny边缘显示（辅助角点选择）")
        print("   - 'q' 键: 直接读取已保存的角点并使用")
        # print("   - 'w' 键: 保存拉直后的图像")
        print(f"   - 当前输出分辨率: {current_res_name}")
        # ---------- 主循环 ----------
        while True:
            key = cv2.waitKey(10) & 0xFF
            if key == ord('r'):               # 重置选择
                self.reset()
                try:
                    cv2.destroyWindow(self._win_warped)
                except:
                    pass
            elif key == ord('e'):             # 重置缩放比例至100%
                self.reset_scale()
            elif key == ord('z'):             # 放大5%
                self.scale_quad(1.05)
            elif key == ord('x'):             # 缩小5%
                self.scale_quad(0.95)
            elif key == ord('t'):             # 切换Canny边缘显示
                self.show_canny = not self.show_canny
                print(f"Canny边缘显示: {'开启' if self.show_canny else '关闭'}")
                self._redraw_with_corners()
            elif key == ord('q'):
                #  # 按下 'q' 时直接加载已保存的 fixed_corners.json,若成功会自动绘制并计算透视矩阵
                if self.load_corners():
                    print("✅ 已从 fixed_corners.json 加载并应用角点信息")
                else:
                    print("⚠️ 未能加载 fixed_corners.json，请检查文件是否存在或格式是否正确")

            # elif key == ord('w'):             # 保存变换后的图像
            #     if hasattr(self, 'warped_image') and self.warped_image is not None:
            #         output_path = self.image_path.parent / f"{self.image_path.stem}_warped.jpg"
            #         cv2.imwrite(str(output_path), self.warped_image)
            #         print(f"已保存变换后的图像: {output_path}")
            #     else:
            #         print("无变换图像可保存，请先选择四个角点")

            # ---------- 窗口关闭检测 ----------
            manual_visible = cv2.getWindowProperty(
                self._win_main, cv2.WND_PROP_VISIBLE) >= 1
            warped_visible = cv2.getWindowProperty(
                self._win_warped, cv2.WND_PROP_VISIBLE) >= 1
            if not manual_visible and not warped_visible:
                break
        # ---------- 清理 ----------
        cv2.destroyAllWindows()
        return self.corners if self.corners else None
        
    # -----------------------------------------------------------------
    # 10️⃣ 自动模式（仅使用已有矩阵）
    # -----------------------------------------------------------------
    def run_auto(self, enable_watch=True, save_output=False, image_data=None):
        """
        透视变换自动模式。

        现在支持两种输入方式：
        1️⃣ 传统方式 – 通过 `self.image_path`（在 __init__ 中读取的文件）。
        2️⃣ 直接传入 numpy RGB 图像 – `image_data` 参数 (shape: H×W×3, dtype=uint8)。

        当 `image_data` 不为 None 时，直接使用该数组做变换，
        并在内部更新 `self.original_image`、`self.orig_height`、`self.orig_width`，
        其余逻辑保持不变（读取透视矩阵、计算输出尺寸、warp 等）。
        """
        # ---------- ① 若传入了 image_data，直接使用 ----------
        if image_data is not None:
            # OpenCV 需要 BGR 格式；这里假设传入的是 RGB → 转为 BGR
            if image_data.ndim == 3 and image_data.shape[2] == 3:
                self.original_image = cv2.cvtColor(image_data, cv2.COLOR_RGB2BGR)
            else:
                # 已经是 BGR（或单通道）则直接使用
                self.original_image = image_data
            self.orig_height, self.orig_width = self.original_image.shape[:2]

        # -----------------------------------------------------------------
        # ② 读取透视矩阵（保持原实现）
        # -----------------------------------------------------------------
        def _process():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "perspective_matrix" not in data:
                print("❌ 配置文件缺少 `perspective_matrix` 键")
                return False
            self.perspective_matrix = np.array(
                data["perspective_matrix"], dtype=np.float32)
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
                flags=cv2.INTER_LINEAR)
            if save_output:
                output_path = (self.image_path.parent /
                               f"{self.image_path.stem}_warped_auto.jpg")
                cv2.imwrite(str(output_path), self.warped_image)
            return True
        # -----------------------------------------------------------------
        # ③ 首次处理
        # -----------------------------------------------------------------
        if not _process():
            return None

        # -----------------------------------------------------------------
        # ④ 可选的热更新监听（保持原实现）
        # -----------------------------------------------------------------
        if enable_watch:
            import time
            last_mtime = self.config_path.stat().st_mtime
            print("🔄 已开启 透视变换矩阵 热更新监听 (fixed_corners.json)")
            try:
                while True:
                    time.sleep(2)
                    cur_mtime = self.config_path.stat().st_mtime
                    if cur_mtime != last_mtime:
                        print("🔄 检测到配置文件变化，重新加载并变换")
                        if _process():
                            last_mtime = cur_mtime
            except KeyboardInterrupt:
                pass
        return self.warped_image

    # -----------------------------------------------------------------
    # 11️⃣ 计算并显示透视变换
    # -----------------------------------------------------------------
    def apply_perspective_transform(self):
        """根据四个角点进行透视变换，将四边形区域拉直"""
        if not self.corners:
            print("没有可用的角点数据，无法进行透视变换")
            return
        # 若已有缓存矩阵且未被手动清除，则直接使用
        if self.perspective_matrix is not None:
            matrix = self.perspective_matrix
            # print("使用已缓存的透视矩阵进行变换")
        else:
            # 获取原始图像中的四个角点（顺序：TL, TR, BR, BL）
            pts_src = np.array([
                self.corners["top_left_corner"],
                self.corners["top_right_corner"],
                self.corners["bottom_right_corner"],
                self.corners["bottom_left_corner"]
            ], dtype="float32")
            # 根据分辨率设置目标尺寸
            if self.output_resolution == "720p":
                width, height = 1280, 720
            elif self.output_resolution == "1080p":
                width, height = 1920, 1080
            else:  # original
                width, height = self.orig_width, self.orig_height
            pts_dst = np.array([
                [0, 0],
                [width - 1, 0],
                [width - 1, height - 1],
                [0, height - 1]
            ], dtype="float32")
            matrix = cv2.getPerspectiveTransform(pts_src, pts_dst)
            self.perspective_matrix = matrix
            self.save_corners()
        # 再次确定输出尺寸（上面已经算过，这里重复使用）
        if self.output_resolution == "720p":
            width, height = 1280, 720
        elif self.output_resolution == "1080p":
            width, height = 1920, 1080
        else:
            width, height = self.orig_width, self.orig_height
        self.warped_image = cv2.warpPerspective(
            self.original_image,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR)
        # 创建显示用的缩小版本
        display_warped = cv2.resize(self.warped_image,
                                   (self.display_width, self.display_height))
        # apply_perspective_transform – 创建/显示透视结果窗口
        cv2.namedWindow(self._win_warped, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self._win_warped,
                         self.display_width, self.display_height)
        cv2.imshow(self._win_warped, display_warped)  

    # -----------------------------------------------------------------
    # 12️⃣ 文件监听器（保持不变，仅做了少量注释）
    # -----------------------------------------------------------------
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
            self.observer.schedule(event_handler,
                                   str(self.directory), recursive=False)
            thread = Thread(target=self.observer.start, daemon=True)
            thread.start()
            # print(f"📁 正在监听配置文件变化: {self.config_path}")


# --------------------------------------------------------------
# 示例入口（保持原样）
# --------------------------------------------------------------
if __name__ == "__main__":
    image_path = "Resources/Captured/3.png"  # 替换为你的图像路径
    # 可选值："720p" | "1080p" | "original"
    OUTPUT_RESOLUTION = "720p"  # ←←← 在这里修改输出分辨率

    if not Path(image_path).exists():
        print(f"图像文件不存在: {image_path}")
    else:
        detector = PerspectiveCalibrator(
            image_path,
            display_width=640,
            display_height=360,
            output_resolution=OUTPUT_RESOLUTION
        )
        corners = detector.run()