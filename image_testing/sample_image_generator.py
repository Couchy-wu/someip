# File: image_testing/sample_image_generator.py
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
from datetime import datetime

# 图像生成器，输出XX_ImageData.json


# ---- 拆分后的能力组合（见各模块说明） ----
from image_testing.image_gen_data import ImageGenDataMixin        # noqa: E402
from image_testing.image_gen_preview import ImagePreviewMixin     # noqa: E402
from image_testing.tooltip import Tooltip                         # noqa: E402


class ImageGeneratorApp(ImagePreviewMixin, ImageGenDataMixin):
    """测试图生成器主类。

    界面装配与预览 → image_gen_preview.ImagePreviewMixin
    数据读取与导出 → image_gen_data.ImageGenDataMixin
    悬浮提示       → tooltip.Tooltip
    """
    def __init__(self, root, json_file_path=None, project_root=None):
        self.root = root
        self.root.title("OSD 图像生成器")
        self.root.geometry("1400x700")
        self.root.minsize(1000, 600)
        
        # ========== 路径配置 =========
        # 初始化路径配置
        if project_root is None:
            # 默认使用原逻辑获取项目根目录
            self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.project_root = project_root  # 允许外部传入自定义路径
        
        # 图标资源目录：Resources/ImageUI/{platform}/
        self.resources_dir = os.path.join(self.project_root, "Resources", "ImageUI")
        # UI 配置文件目录：image_testing/UI_Config/
        self.config_dir = os.path.join(self.project_root, "image_testing", "UI_Config")
        # 测试用例目录：image_testing/TestcaseCollection/
        self.testcase_dir = os.path.join(self.project_root, "TestcaseCollection")
        
        # ========== 当前平台相关 ==========
        self.current_platform = ""          # 当前选择的平台名称（如：A5）
        self.current_platform_dir = ""      # 当前平台资源目录路径
        self.config_file = ""               # 当前平台配置文件路径
        self.config_data = {}               # 存储平台图标配置 {filename: config_dict}
        # ========== 多图像管理 ==========
        self.image_configs = []             # 所有图像配置列表：[{name, icon_states, preview}]
        self.current_image_index = -1       # 当前正在编辑的图像索引
        # ========== 图像缓存 ==========
        self.image_cache = {}               # PIL.Image 缓存 {filename: Image}
        self.photo_cache = {}               # Tkinter.PhotoImage 缓存 {filename: PhotoImage}
        # ========== 背景信息 ==========
        self.bg_image = None                # 背景图（PIL.Image）
        self.bg_width = 800                 # 背景图宽度
        self.bg_height = 480                # 背景图高度
        # ========== 测试用例数据 ==========
        self.test_cases = []                # 从 JSON 加载的测试用例列表
        # ========== 状态颜色映射 ==========
        self.status_colors = {
            "main": "blue",      # 🔵 启用位置1（主位置）
            "reuse": "green",    # 🟢 启用位置2（复用位置）
            "reuse2": "orange",  # 🟠 启用位置3（第二个复用位置)
            "reuse3": "purple",  # 🟣 启用位置4（第三个复用位置）
            "enabled": "red",    # 🔴 启用（无复用）
            None: "lightgray"    # ⚪ 不启用
        }
        # ========== 初始化 ==========
        # 获取所有平台（Resources/ImageUI 下的子文件夹）
        self.platforms = self.get_platforms()
        if not self.platforms:
            messagebox.showerror("错误", "未找到任何平台文件夹！请检查 ImageUI 目录结构。")
            self.root.destroy()
            return
        # 构建图形界面
        self.setup_gui()
        # 初始化第一个平台
        self.current_platform = self.platforms[0]
        self.load_platform(self.current_platform)
        # 如果启动时传入了 JSON 文件路径，则加载
        if json_file_path and os.path.exists(json_file_path):
            self.load_test_cases_from_json(json_file_path)
            self.generate_images_from_test_cases()
