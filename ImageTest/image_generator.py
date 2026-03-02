# File: ImageTest/image_generator.py
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
from datetime import datetime

# 图像生成器，输出XX_ImageData.json

class Tooltip:
    """工具提示类：为任意 Tkinter 控件添加鼠标悬停提示"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        # 绑定事件：鼠标进入、离开、点击时显示/隐藏提示
        widget.bind("<Enter>", self.showtip)
        widget.bind("<Leave>", self.hidetip)
        widget.bind("<ButtonPress>", self.hidetip)
    def showtip(self, event=None):
        """显示提示框"""
        # 获取控件位置
        x, y, cx, cy = self.widget.bbox("insert")
        # 计算提示框位置（控件右下方）
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        # 创建无边框顶层窗口
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # 无窗口边框
        tw.wm_geometry("+%d+%d" % (x, y))  # 定位
        # 创建提示文本标签
        label = tk.Label(tw, text=self.text, justify="left",
                        background="#ffffe0", relief="solid", borderwidth=1,
                        font=("微软雅黑", 9))
        label.pack(ipadx=1)
    def hidetip(self, event=None):
        """隐藏提示框"""
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None

class ImageGeneratorApp:
    """
    OSD 图像生成器主应用类
    功能：
    - 加载平台配置（图标、位置、复用信息）
    - 从 *_data.json 文件加载测试用例
    - 为每个测试用例生成图像配置
    - 图标状态管理（启用/复用/禁用）
    - 预览合成图像
    - 批量导出图像与配置文件
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
        # UI 配置文件目录：ImageTest/UI_Config/
        self.config_dir = os.path.join(self.project_root, "ImageTest", "UI_Config")
        # 测试用例目录：ImageTest/TestcaseCollection/
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
    
    def load_test_cases_from_json(self, json_file_path):
        """
        从指定 JSON 文件加载测试用例数据
        支持格式：
          - 纯数组：[{}, {}, ...]
          - 包含 test_cases 字段的对象：{"test_cases": [...]}
          - 单个对象（视为一个用例）
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                self.test_cases = data
            elif isinstance(data, dict) and "test_cases" in data:
                self.test_cases = data["test_cases"]
            else:
                self.test_cases = [data] if isinstance(data, dict) else []
            print(f"✅ 已从 {json_file_path} 加载 {len(self.test_cases)} 个测试用例")
        except Exception as e:
            messagebox.showerror("错误", f"加载测试用例文件失败：\n{e}")
            self.test_cases = []
    
    def generate_images_from_test_cases(self):
        """
        根据当前加载的测试用例，自动生成图像配置
        每个测试用例对应一个可编辑的图像项
        """
        self.image_configs.clear()
        self.image_listbox.delete(0, tk.END)
        if not self.test_cases:
            # 没有用例时创建默认图像
            default_config = {
                "name": "默认图像",
                "icon_states": {},
                "icon_values": {},      # 用于存放每个图标的“数值”
                "preview": None
            }
            self.image_configs.append(default_config)
            self.image_listbox.insert(tk.END, "默认图像")
            self.update_listbox_item_color(0)
        else:
            # 为每个测试用例创建一个图像配置项
            for i, test_case in enumerate(self.test_cases):
                # 直接取第一行的 "*用例编号" 作为图像名称（理论上用例编号必定存在且唯一，已通过其他手段限制了，这里不再进行检查）
                case_id = test_case["rows"][0]["*用例编号"]
                new_config = {
                    "name": case_id,
                    "icon_states": {},  # 初始无图标
                    "icon_values": {},
                    "preview": None
                }
                self.image_configs.append(new_config)
                self.image_listbox.insert(tk.END, case_id)
                self.update_listbox_item_color(len(self.image_configs) - 1)
        # 设置第一个为当前选中项
        if self.image_configs:
            self.current_image_index = 0
            self.image_listbox.selection_clear(0, tk.END)
            self.image_listbox.selection_set(0)
            self.image_listbox.see(0)
            self.refresh_icon_buttons()
            self.redraw_preview()
            self.populate_case_table(0)
    
    def get_platforms(self):
        """
        获取 Resources/ImageUI 下的所有子文件夹名称（即平台名）
        返回排序后的列表
        """
        if not os.path.exists(self.resources_dir):
            return []
        folders = [
            f for f in os.listdir(self.resources_dir)
            if os.path.isdir(os.path.join(self.resources_dir, f))
        ]
        return sorted(folders)
    
    def setup_gui(self):
        """
        构建主图形用户界面
        包括：
          - 平台选择
          - 加载测试用例按钮
          - 图像列表
          - 预览画布
          - 图标选择面板
          - 测试用例表格
        """
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        # ========== 第一行：平台选择 + 控制按钮 ==========
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(top_frame, text="选择平台:").pack(side="left")
        self.platform_var = tk.StringVar()
        self.platform_combo = ttk.Combobox(
            top_frame,
            textvariable=self.platform_var,
            values=self.platforms,
            state="readonly",
            width=30
        )
        self.platform_combo.pack(side="left", padx=(10, 0))
        self.platform_combo.set(self.platforms[0])
        self.platform_combo.bind("<<ComboboxSelected>>", self.on_platform_change)
        # ========== 加载测试用例按钮 ==========
        self.load_config_btn = ttk.Button(top_frame, text="加载测试用例", command=self.load_testcase_file)
        self.load_config_btn.pack(side="left", padx=(20, 0))
        # ========== 当前测试用例显示框（只读） ==========
        self.current_case_var = tk.StringVar()
        self.current_case_var.set("待上传")          # 初始状态
        self.current_case_entry = tk.Entry(
            top_frame,
            textvariable=self.current_case_var,
            width=30,
            font=("微软雅黑", 9),
            state="readonly",
            readonlybackground="white",
            fg="black"
        )
        self.current_case_entry.pack(side="left", padx=(0, 10))
        Tooltip(self.load_config_btn, "从 TestcaseCollection 中选择 *_data.json 文件加载测试用例")
        # ========== 右侧控制按钮 ==========
        self.batch_export_btn = ttk.Button(top_frame, text="批量导出所有图像", command=self.batch_export_images)
        self.batch_export_btn.pack(side="right", padx=(0, 5))
        self.export_config_btn = ttk.Button(top_frame, text="生成或更新配置文件", command=self.generate_unified_config_file)
        self.export_config_btn.pack(side="right", padx=(0, 5))
        self.save_single_btn = ttk.Button(top_frame, text="保存当前图像", command=self.save_single_image)
        self.save_single_btn.pack(side="right", padx=(0, 5))
        self.clear_current_btn = ttk.Button(top_frame, text="清除当前选择", command=self.clear_current_selection)
        self.clear_current_btn.pack(side="right", padx=(0, 5))
        # ========== 主内容区域 ==========
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True)
        # 为左右两列设置权重（左 65%，右 35%），让它们按比例伸缩
        content_frame.columnconfigure(0, weight=65)
        content_frame.columnconfigure(1, weight=35)
        content_frame.rowconfigure(0, weight=1)
        # ========== 左侧：图像列表、用例表格、预览 ==========
        left_panel = ttk.Frame(content_frame)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        # ---- 图像列表区域 ----
        image_list_frame = ttk.LabelFrame(left_panel, text="图像列表 (自动从测试用例生成)", padding="5")
        image_list_frame.pack(fill="x", pady=(0, 10))
        self.image_listbox = tk.Listbox(image_list_frame, height=5, font=("微软雅黑", 9), exportselection=False)
        self.image_listbox.pack(side="left", fill="both", expand=True)
        self.image_scrollbar = ttk.Scrollbar(image_list_frame, orient="vertical", command=self.image_listbox.yview)
        self.image_scrollbar.pack(side="right", fill="y")
        self.image_listbox.config(yscrollcommand=self.image_scrollbar.set)
        self.image_listbox.bind("<<ListboxSelect>>", self.on_image_selection_change)
        # ---- 测试用例详情表格 ----
        case_table_frame = ttk.LabelFrame(left_panel, text="测试用例详情", padding="5")
        case_table_frame.pack(fill="x", expand=False, pady=(0, 10))
        self.case_tree = ttk.Treeview(case_table_frame, show="headings", height=4)
        self.case_tree.pack(side="left", fill="x", expand=True)
        case_scroll_y = ttk.Scrollbar(case_table_frame, orient="vertical", command=self.case_tree.yview)
        case_scroll_y.pack(side="right", fill="y")
        self.case_tree.configure(yscrollcommand=case_scroll_y.set)
        # ---- OSD 预览画布 ----
        self.canvas_frame = ttk.LabelFrame(left_panel, text="OSD 预览", padding="5")
        self.canvas_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.canvas_frame, width=800, height=480, bg="lightgray", relief="sunken")
        self.canvas.pack(expand=True, fill="both")
        # ========== 右侧：图标选择面板 ==========
        # 直接放在 content_frame 的右侧列，保持固定宽度
        self.icon_panel_frame = ttk.LabelFrame(content_frame, text="选择图标", padding="10", width=300)
        self.icon_panel_frame.grid(row=0, column=1, sticky="nsew")
        self.icon_panel_frame.grid_propagate(False)                 # 防止内部控件撑宽
        self.icon_canvas = tk.Canvas(self.icon_panel_frame, width=250)
        self.icon_canvas.pack(side="left", fill="both", expand=True)
        self.icon_scrollbar = ttk.Scrollbar(self.icon_panel_frame, orient="vertical", command=self.icon_canvas.yview)
        self.icon_scrollbar.pack(side="right", fill="y")
        self.icon_canvas.configure(yscrollcommand=self.icon_scrollbar.set)
        self.icons_inner_frame = ttk.Frame(self.icon_canvas)
        self.icon_canvas.create_window((0, 0), window=self.icons_inner_frame, anchor="nw", width=250)
        self.icons_inner_frame.bind("<Configure>", self.on_icon_frame_configure)
        self.icon_canvas.bind_all("<MouseWheel>", self.on_mousewheel)
    
    def populate_case_table(self, case_index: int):
        """把 JSON rows 渲染为表格，仅显示第1-5列和第7列，并按比例填充宽度"""
        # 清空旧数据
        for col in self.case_tree["columns"]:
            self.case_tree.heading(col, text="")
        self.case_tree.delete(*self.case_tree.get_children())
        # 防护：若没有加载用例直接返回
        if not self.test_cases or case_index < 0 or case_index >= len(self.test_cases):
            return
        rows = self.test_cases[case_index].get("rows", [])
        if not rows:
            return
        # 获取所有列名并确定要显示的列（第1-5列索引0-4，第7列索引6）
        base_keys = list(rows[0].keys())
        extra_keys = []
        for r in rows[1:]:
            for k in r.keys():
                if k not in base_keys and k not in extra_keys:
                    extra_keys.append(k)
        all_keys = base_keys + extra_keys
        # 选择要显示的列索引（0-based）
        display_indices = [0, 1, 2, 3, 4, 6]
        filtered_keys = []
        for i in display_indices:
            if i < len(all_keys):
                filtered_keys.append(all_keys[i])
        # 设置表格列
        self.case_tree["columns"] = filtered_keys
        # 动态计算可用宽度，确保响应式
        self.case_tree.update_idletasks()  # 确保几何信息最新
        parent_width = self.case_tree.winfo_width()
        if parent_width <= 1:
            parent_width = 800  # 合理默认值
        scrollbar_width = 20
        padding = 10
        available_width = max(300, parent_width - scrollbar_width - padding)
        width_ratio = [3, 3, 3, 2, 10, 10]
        col_widths = [
            int(available_width * width_ratio[0] / sum(width_ratio)),   # 第1列
            int(available_width * width_ratio[1] / sum(width_ratio)),   # 第2列
            int(available_width * width_ratio[2] / sum(width_ratio)),   # 第3列
            int(available_width * width_ratio[3] / sum(width_ratio)),   # 第4列
            int(available_width * width_ratio[4] / sum(width_ratio)),   # 第5列
            int(available_width * width_ratio[5] / sum(width_ratio))    # 第7列
        ]
        # 配置列（设置stretch=True使列自动填充）
        for idx, k in enumerate(filtered_keys):
            self.case_tree.heading(k, text=k, anchor="w")
            self.case_tree.column(k, width=col_widths[idx], anchor="w", stretch=True)
        # 填充行数据（仅显示过滤后的列）
        for r in rows:
            values = [r.get(k, "") if r.get(k) is not None else "" for k in filtered_keys]
            self.case_tree.insert("", "end", values=values)
        # 强制更新Treeview并重新应用列宽（修复首次加载比例问题）
        self.case_tree.update_idletasks()
        for idx, k in enumerate(filtered_keys):
            self.case_tree.column(k, width=col_widths[idx], stretch=True)
    
    def on_icon_frame_configure(self, event):
        """当图标面板内容变化时，更新滚动区域"""
        self.icon_canvas.configure(scrollregion=self.icon_canvas.bbox("all"))
    def on_mousewheel(self, event):
        """处理鼠标滚轮事件，实现垂直滚动"""
        self.icon_canvas.yview_scroll(-1 * (event.delta // 120), "units")
    
    def on_platform_change(self, event):
        """平台切换事件：加载新平台并重新生成图像配置"""
        new_platform = self.platform_var.get()
        if new_platform == self.current_platform:
            return
        self.current_platform = new_platform
        # 重置当前图像索引（修复越界关键）
        self.current_image_index = -1
        self.load_platform(new_platform)
        # 切换平台时重置测试用例状态
        self.current_case_var.set("待上传")
        if hasattr(self, 'current_testcase_path'):
            delattr(self, 'current_testcase_path')
        self.image_configs.clear()
        self.image_listbox.delete(0, tk.END)
        # 清空预览画布
        self.canvas.delete("all")
        self.canvas.config(bg="lightgray")
    
    def load_platform(self, platform):
        """加载指定平台的配置和资源"""
        self.current_platform_dir = os.path.join(self.resources_dir, platform)
        self.config_file = os.path.join(self.config_dir, f"ui_config_{platform}.json")
        if not os.path.exists(self.config_file):
            messagebox.showerror("错误", f"未找到配置文件：\n{self.config_file}")
            return
        # 清空缓存
        self.image_cache.clear()
        self.photo_cache.clear()
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            self.config_data = {}
            for filename, data in raw_data.items():
                self.config_data[filename] = data
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败：{e}")
            return
        self.load_background()
        self.load_icons_and_create_buttons()
    
    def load_background(self):
        """加载背景图并设置画布尺寸"""
        bg_filename = "background.png"
        if bg_filename not in self.config_data:
            messagebox.showwarning("警告", "配置中缺少 background.png！将使用默认尺寸。")
            self.bg_width = 800
            self.bg_height = 480
            self.canvas.config(width=800, height=480)
            self.bg_image = Image.new("RGBA", (800, 480), (0, 0, 0, 0))
            return
        bg_data = self.config_data[bg_filename]
        self.bg_width = bg_data["width"]
        self.bg_height = bg_data["height"]
        self.canvas.config(width=self.bg_width, height=self.bg_height)
        bg_path = os.path.join(self.current_platform_dir, bg_filename)
        if not os.path.exists(bg_path):
            messagebox.showwarning("警告", f"背景图文件不存在：{bg_path}")
            self.bg_image = Image.new("RGBA", (self.bg_width, self.bg_height), (0, 0, 0, 0))
            return
        try:
            self.bg_image = Image.open(bg_path).convert("RGBA")
            if self.bg_image.size != (self.bg_width, self.bg_height):
                self.bg_image = self.bg_image.resize((self.bg_width, self.bg_height), Image.Resampling.LANCZOS)
        except Exception as e:
            messagebox.showerror("错误", f"加载背景图失败：{e}")
            self.bg_image = Image.new("RGBA", (self.bg_width, self.bg_height), (0, 0, 0, 0))
    
    def load_icons_and_create_buttons(self):
        """加载所有非背景图标，创建按钮、状态指示以及数值输入框"""
        for widget in self.icons_inner_frame.winfo_children():
            widget.destroy()
        icon_files = [fn for fn in self.config_data.keys() if fn != "background.png"]
        for filename in icon_files:
            file_path = os.path.join(self.current_platform_dir, filename)
            if not os.path.exists(file_path):
                continue
            try:
                img = Image.open(file_path)
                img.thumbnail((60, 60), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.photo_cache[filename] = photo
            except Exception as e:
                print(f"缩略图加载失败: {filename}, {e}")
                continue
            row_frame = ttk.Frame(self.icons_inner_frame)
            row_frame.pack(fill="x", pady=4)
            # ---------- 图标按钮 ----------
            btn = tk.Button(
                row_frame,
                image=photo,
                text=self.config_data[filename].get("name", filename),
                compound="top",
                font=("微软雅黑", 8),
                width=80,
                height=80,
                relief="raised"
            )
            btn.image = photo
            btn.filename = filename
            # ---------- 状态指示块 ----------
            status_label = tk.Label(
                row_frame,
                width=3,
                height=1,
                bg="lightgray",
                relief="flat",
                borderwidth=2
            )
            # ---------- 数值输入框 ----------
            value_entry = tk.Entry(
                row_frame,
                width=8,
                font=("微软雅黑", 9),
                justify="center"
            )
            value_entry.insert(0, "")
            value_entry.config(state="disabled")
            # 将 entry 与按钮关联，后面方便取到
            btn.value_entry = value_entry
            # 绑定图标点击事件（切换启用状态）
            btn.bind("<Button-1>", lambda e, f=filename, b=btn, s=status_label: 
                     self.on_icon_click(f, b, s))
            # 绑定数值变化事件，实时写入 image_configs
            def on_value_change(ev, fn=filename, entry=value_entry):
                if self.current_image_index < 0:
                    return
                val = entry.get().strip()
                # 如果值为空，则从icon_values中删除该键
                if not val:
                    self.image_configs[self.current_image_index]["icon_values"].pop(fn, None)
                else:
                    self.image_configs[self.current_image_index]["icon_values"][fn] = val
            value_entry.bind("<KeyRelease>", on_value_change)
            # ---------- 布局 ----------
            btn.pack(side="left", padx=(0, 10))
            status_label.pack(side="left", padx=(0, 5))
            value_entry.pack(side="left", padx=(0, 5))
            Tooltip(status_label, self.get_status_tooltip_text(filename))
            self.update_status_label(filename, status_label)
    
    def get_status_tooltip_text(self, filename):
        """获取状态提示文字（用于工具提示）"""
        # 添加越界检查（修复错误关键）
        if self.current_image_index < 0 or self.current_image_index >= len(self.image_configs):
            return "不启用"
        current_states = self.image_configs[self.current_image_index]["icon_states"]
        state = current_states.get(filename)
        config = self.config_data.get(filename, {})
        has_reuse = config.get("reuse", False)
        if state is None:
            return "不启用"
        elif has_reuse:
            return "启用位置1" if state == "main" else "启用位置2"
        else:
            return "启用"
    
    def update_status_label(self, filename, label):
        """更新状态指示色块的颜色"""
        # 添加越界检查（修复错误关键）
        if self.current_image_index < 0 or self.current_image_index >= len(self.image_configs):
            color = self.status_colors[None]
        else:
            current_states = self.image_configs[self.current_image_index]["icon_states"]
            state = current_states.get(filename)
            config = self.config_data.get(filename, {})
            has_reuse = config.get("reuse", False)
            if state is None:
                color = self.status_colors[None]
            elif has_reuse:
                color = self.status_colors["main"] if state == "main" else self.status_colors["reuse"]
            else:
                color = self.status_colors["enabled"] if state == "enabled" else self.status_colors[None]
        label.config(bg=color)
    
    def on_icon_click(self, filename, button, status_label):
        """点击图标按钮：循环切换启用状态，并控制数值输入框"""
        if self.current_image_index < 0:
            messagebox.showwarning("警告", "请先创建或选择一个图像！")
            return
        current_states = self.image_configs[self.current_image_index]["icon_states"]
        current_state = current_states.get(filename, None)
        config = self.config_data[filename]
        has_reuse = config.get("reuse", False)
        # ---------- 状态切换 ----------
        if current_state is None:
            current_states[filename] = "main" if has_reuse else "enabled"
            button.config(relief="sunken")
        elif has_reuse:
            if current_state == "main":
                current_states[filename] = "reuse"
                button.config(relief="sunken")
            elif current_state == "reuse":
                current_states.pop(filename, None)
                button.config(relief="raised")
        else:
            if current_state == "enabled":
                current_states.pop(filename, None)
                button.config(relief="raised")
        # ---------- 同步数值框 ----------
        # button.value_entry 在 load_icons_and_create_buttons 中创建
        entry = getattr(button, "value_entry", None)
        if entry:
            if current_states.get(filename) is None:   # 已被清除（不启用）
                entry.delete(0, tk.END)
                entry.config(state="disabled")
                # 同时把之前可能保存的数值删掉
                self.image_configs[self.current_image_index]["icon_values"].pop(filename, None)
            else:                                      # 已启用
                entry.config(state="normal")
                # 若之前已经有保存的数值，回写到 entry
                saved_val = self.image_configs[self.current_image_index]["icon_values"].get(filename, "")
                entry.delete(0, tk.END)
                entry.insert(0, saved_val)
        # ---------- 其余 UI 同步 ----------
        self.update_status_label(filename, status_label)
        self.update_listbox_item_color(self.current_image_index)
        Tooltip(status_label, self.get_status_tooltip_text(filename))
        self.redraw_preview()
    
    def load_testcase_file(self):
        """
        【核心功能】加载测试用例文件
        流程：
          1. 打开文件对话框，默认进入 TestcaseCollection 目录
          2. 仅显示 *_data.json 格式的文件
          3. 用户选择后，加载 JSON 数据
          4. 为每个测试用例生成一个图像配置项
          5. 刷新 UI 显示
        """
        # 检查测试用例目录是否存在
        if not os.path.exists(self.testcase_dir):
            messagebox.showerror("错误", f"测试用例目录不存在：\n{self.testcase_dir}")
            return
        # 打开文件选择对话框
        file_path = filedialog.askopenfilename(
            title="选择测试用例文件",
            initialdir=self.testcase_dir,
            filetypes=[("测试用例文件 (*_data.json)", "*_data.json"), ("JSON 文件", "*.json")],
            parent=self.root
        )
        if not file_path:
            return  # 用户取消选择
        # 验证文件名格式
        filename = os.path.basename(file_path)
        if not filename.endswith("_data.json"):
            messagebox.showwarning("警告", "请选择符合 '*_data.json' 格式的文件！")
            return
        # 记录路径并更新显示框
        self.current_testcase_path = file_path
        self.current_case_var.set(filename)
        # 先加载测试用例（但先不生成图像配置）
        self.load_test_cases_from_json(file_path)
        # 尝试加载对应的 XX_ImageData.json 配置文件
        base_name = filename.replace("_data.json", "_ImageData.json")
        config_path = os.path.join(os.path.dirname(file_path), base_name)
        # 预检查平台一致性，在生成图像列表之前进行
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    saved_data_raw = f.read().strip()
                    if saved_data_raw:
                        saved_data = json.loads(saved_data_raw)
                        # 检查 platform 字段是否存在且与当前平台匹配
                        if "platform" in saved_data:
                            saved_platform = saved_data["platform"]
                            if saved_platform != self.current_platform:
                                messagebox.showerror(
                                    "平台不匹配",
                                    f"检测到 {base_name} 应属于 '{saved_platform}' 平台，\n"
                                    f"但当前选择的是 '{self.current_platform}' 平台。\n\n"
                                    "请检查是否平台选择有误！"
                                )
                                # 清空测试用例数据，不生成图像列表
                                self.test_cases = []
                                return  # 中断整个加载流程
            except Exception as e:
                # 如果配置文件检查失败，继续正常流程（兼容旧格式）
                print(f"⚠️ 配置文件预检查失败: {e}")
        # 只有在平台匹配或无配置文件时，才生成图像配置
        self.generate_images_from_test_cases()
        # ---------- 恢复已保存的图标状态 ----------
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                print(f"✅ 检测到配置文件，正在恢复图像状态：{base_name}")
                # 遍历每个图像配置，恢复所有图标（而不是仅恢复当前索引的图标）
                for img_idx, img_cfg in enumerate(self.image_configs):
                    image_name = img_cfg["name"]
                    if image_name not in saved_data:
                        continue  # 该图像无保存记录
                    items = saved_data[image_name]  # 该图像的所有图标项列表
                    for item in items:
                        icon_name = item.get("name")
                        top_left = item.get("top_left", [])
                        if not icon_name or len(top_left) < 2:
                            continue
                        matched = False
                        # 分别检查主位置和复用位置，避免同名图标被误判
                        for filename, data in self.config_data.items():
                            if filename == "background.png":
                                continue
                            # -------- 主位置匹配 --------
                            if data.get("name") == icon_name:
                                if (abs(top_left[0] - data["left"]) < 5 and
                                    abs(top_left[1] - data["top"]) < 5):
                                    img_cfg["icon_states"][filename] = (
                                        "main" if data.get("reuse", False) else "enabled"
                                    )
                                    matched = True
                                    break  # 找到匹配后结束当前 filename 检查
                            # -------- 复用位置匹配 --------
                            if data.get("reuse", False) and data.get("reuse_name") == icon_name:
                                if (abs(top_left[0] - data["reuse_left"]) < 5 and
                                    abs(top_left[1] - data["reuse_top"]) < 5):
                                    img_cfg["icon_states"][filename] = "reuse"
                                    matched = True
                                    break
                        if not matched:
                            print(f"⚠️ 无法匹配图标: {icon_name} @ {top_left}")
                        # 若配置里携带数值，则同步到 icon_values
                        if "value" in item and item["value"] != "":
                            img_cfg["icon_values"][filename] = item["value"]
                # 恢复完成后刷新 UI
                self.refresh_icon_buttons()
                self.redraw_preview()
                # 更新列表项的颜色（有/无图标）
                for idx in range(len(self.image_configs)):
                    self.update_listbox_item_color(idx)
                # 选中第一张图像（或保持之前的选中），并展示对应的用例表格
                if self.image_configs:
                    self.current_image_index = 0
                    self.image_listbox.selection_clear(0, tk.END)
                    self.image_listbox.selection_set(0)
                    self.populate_case_table(0)
                messagebox.showinfo(
                    "恢复成功",
                    f"已从 {base_name} 恢复图像配置！\n共恢复 {len(self.image_configs)} 个图像的状态。"
                )
            except Exception as e:
                messagebox.showwarning(
                    "警告",
                    f"加载配置文件失败，将使用空白配置：\n{e}"
                )
                print(f"❌ 恢复配置失败: {e}")
        # 最终刷新 UI
        self.refresh_icon_buttons()
        self.redraw_preview()
    
    def update_listbox_item_color(self, idx):
        """根据图像是否启用了图标，设置列表项文字颜色（无图标为红色）"""
        if idx < 0 or idx >= len(self.image_configs):
            return
        has_icons = bool(self.image_configs[idx]["icon_states"])
        fg_color = "red" if not has_icons else "black"
        self.image_listbox.itemconfig(idx, {"fg": fg_color, "selectforeground": fg_color})
    
    def on_image_selection_change(self, event):
        """图像列表选择变化事件"""
        selection = self.image_listbox.curselection()
        if not selection:
            return
        new_index = selection[0]
        if new_index == self.current_image_index:
            return
        self.current_image_index = new_index
        self.refresh_icon_buttons()
        self.redraw_preview()
        self.populate_case_table(new_index)
    
    def refresh_icon_buttons(self):
        """刷新所有图标按钮的显示状态（根据当前图像配置），并同步数值输入框"""
        if self.current_image_index < 0:
            return
        current_states = self.image_configs[self.current_image_index]["icon_states"]
        current_values = self.image_configs[self.current_image_index]["icon_values"]
        for row_frame in self.icons_inner_frame.winfo_children():
            children = row_frame.winfo_children()
            if len(children) >= 3:                     # btn, status_label, entry
                btn = children[0]
                status_label = children[1]
                entry = children[2]
                if isinstance(btn, tk.Button) and hasattr(btn, 'filename'):
                    filename = btn.filename
                    state = current_states.get(filename)
                    btn.config(relief="sunken" if state else "raised")
                    # ----- 数值框状态 -----
                    if state:
                        entry.config(state="normal")
                        entry.delete(0, tk.END)
                        entry.insert(0, current_values.get(filename, ""))
                    else:
                        entry.delete(0, tk.END)
                        entry.config(state="disabled")
                    # ----- 状态指示块 -----
                    self.update_status_label(filename, status_label)
                    Tooltip(status_label, self.get_status_tooltip_text(filename))
    
    def clear_current_selection(self):
        """清除当前图像的所有图标选择"""
        if self.current_image_index < 0:
            return
        self.image_configs[self.current_image_index]["icon_states"].clear()
        for row_frame in self.icons_inner_frame.winfo_children():
            children = row_frame.winfo_children()
            if len(children) >= 2:
                btn = children[0]
                status_label = children[1]
                if isinstance(btn, tk.Button):
                    btn.config(relief="raised")
                if isinstance(status_label, tk.Label):
                    status_label.config(bg=self.status_colors[None])
        self.redraw_preview()
        self.update_listbox_item_color(self.current_image_index)
    
    def redraw_preview(self):
        """重新绘制预览图像：背景 + 已选图标（支持主/复用位置）"""
        if self.bg_image is None or self.current_image_index < 0:
            return
        composite_img = self.bg_image.copy()
        current_states = self.image_configs[self.current_image_index]["icon_states"]
        for filename, state in current_states.items():
            if filename not in self.config_data:
                continue
            file_path = os.path.join(self.current_platform_dir, filename)
            if not os.path.exists(file_path):
                continue
            try:
                icon_img = Image.open(file_path).convert("RGBA")
                if state in ("main", "enabled"):
                    pos_x = self.config_data[filename]["left"]
                    pos_y = self.config_data[filename]["top"]
                elif state == "reuse":
                    pos_x = self.config_data[filename]["reuse_left"]
                    pos_y = self.config_data[filename]["reuse_top"]
                else:
                    continue
                if 0 <= pos_x < self.bg_width and 0 <= pos_y < self.bg_height:
                    composite_img.paste(icon_img, (pos_x, pos_y), icon_img)
            except Exception as e:
                print(f"绘制失败: {filename}, {e}")
        preview_img = ImageTk.PhotoImage(composite_img)
        self.image_configs[self.current_image_index]["preview"] = preview_img
        self.canvas.create_image(0, 0, image=preview_img, anchor="nw")
        self.canvas.image = preview_img
    
    def save_single_image(self):
        """保存当前选中的单张图像"""
        if self.current_image_index < 0:
            messagebox.showwarning("警告", "没有可保存的图像！")
            return
        config = self.image_configs[self.current_image_index]
        if not config["icon_states"]:
            messagebox.showinfo("提示", "当前图像没有启用任何图标，无法保存！")
            return
        suggested_name = f"{config['name']}.png"
        file_path = filedialog.asksaveasfilename(
            title="保存图像",
            defaultextension=".png",
            initialfile=suggested_name,
            filetypes=[("PNG 图像", "*.png"), ("JPEG 图像", "*.jpg"), ("所有文件", "*.*")]
        )
        if not file_path:
            return
        try:
            final_img = self._compose_image(config["icon_states"])
            final_img.save(file_path, "PNG" if file_path.lower().endswith('.png') else "JPEG")
            messagebox.showinfo("成功", f"图像已保存：\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{e}")
    
    def _compose_image(self, icon_states):
        """合成最终图像（用于保存）"""
        if self.bg_image is None:
            raise ValueError("背景图像未加载")
        composite_img = self.bg_image.copy()
        for filename, state in icon_states.items():
            if filename not in self.config_data:
                continue
            file_path = os.path.join(self.current_platform_dir, filename)
            if not os.path.exists(file_path):
                continue
            try:
                icon_img = Image.open(file_path).convert("RGBA")
                if state in ("main", "enabled"):
                    pos_x = self.config_data[filename]["left"]
                    pos_y = self.config_data[filename]["top"]
                elif state == "reuse":
                    pos_x = self.config_data[filename]["reuse_left"]
                    pos_y = self.config_data[filename]["reuse_top"]
                else:
                    continue
                composite_img.paste(icon_img, (pos_x, pos_y), icon_img)
            except Exception as e:
                print(f"绘制失败: {filename}, {e}")
        return composite_img
    
    def generate_unified_config_file(self):
        """
        生成或更新统一配置文件（JSON 格式）
        直接输出到 TestcaseCollection 目录，文件名格式为 XX_ImageData.json
        如果文件已存在，则直接覆盖更新
        """
        # ---------- 检查 ----------
        if not self.test_cases:
            messagebox.showwarning("警告", "尚未加载任何测试用例文件，无法生成配置文件！")
            return
        if not hasattr(self, 'current_testcase_path') or not self.current_testcase_path:
            messagebox.showwarning("警告", "无法确定原始测试用例文件路径，无法生成配置文件！")
            return
        input_path = self.current_testcase_path
        input_filename = os.path.basename(input_path)
        if not input_filename.endswith("_data.json"):
            messagebox.showwarning("警告", "当前加载的文件不符合 *_data.json 格式，无法生成输出文件名！")
            return
        base_name = input_filename.replace("_data.json", "_ImageData.json")
        output_path = os.path.join(os.path.dirname(input_path), base_name)
        # ---------- 构造 JSON ----------
        try:
            output_parts = []
            # 平台信息
            output_parts.append(f'  "platform": "{self.current_platform}"')
            # 对每张图像进行遍历
            for img_idx, config in enumerate(self.image_configs):   # ★ MOD
                image_name = config["name"]
                items = []
                # 读取该图像对应的数值字典（若不存在则为空 dict）
                values_dict = config.get("icon_values", {})
                for filename, state in config["icon_states"].items():
                    if filename not in self.config_data:
                        continue
                    data = self.config_data[filename]
                    # ----------------- 读取图标的 class_name -----------------
                    class_name = data.get("class_name", "")
                    has_reuse = data.get("reuse", False) and state == "reuse"
                    name = data.get("reuse_name", "") if has_reuse else data.get("name", "")
                    if not name:
                        name = f"{data.get('name', '')}_2" if has_reuse else os.path.splitext(filename)[0]
                    pos_x = data["reuse_left"] if has_reuse else data["left"]
                    pos_y = data["reuse_top"] if has_reuse else data["top"]
                    width = data.get("width", 0) or 0
                    height = data.get("height", 0) or 0
                    if width == 0 or height == 0:
                        img_path = os.path.join(self.current_platform_dir, filename)
                        if os.path.exists(img_path):
                            try:
                                img = Image.open(img_path)
                                w, h = img.size
                                width = w if width == 0 else width
                                height = h if height == 0 else height
                            except:
                                pass
                    # ----------------- 生成单个图标项 -----------------
                    item = {
                        "name": name,
                        "class_name": class_name,
                        "top_left": [pos_x, pos_y],
                        "bottom_right": [pos_x + width, pos_y + height]
                    }
                    # 如果该图标有数值且非空，则写入 "value"
                    val = values_dict.get(filename)
                    # 非空检查，避免生成空value字段
                    if val is not None and str(val).strip() != "":
                        # 尝试转换为数值类型（int或float）
                        try:
                            # 先尝试转为int
                            if '.' in str(val):
                                item["value"] = float(val)
                            else:
                                item["value"] = int(val)
                        except ValueError:
                            # 转换失败则保持原字符串
                            item["value"] = val
                    items.append(json.dumps(item, ensure_ascii=False, separators=(',', ':')))
                image_entry = f'  "{image_name}": [\n    ' + ',\n    '.join(items) + '\n  ]'
                output_parts.append(image_entry)
            # ---------- 合并并写文件 ----------
            output_content = ',\n'.join(output_parts)
            output_lines = ["{", output_content, "}"]
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))
            action = "更新" if os.path.exists(output_path) else "生成"
            print(f"✅ 已{action}配置文件：{output_path}")
            messagebox.showinfo("成功", f"配置文件已{action}：\n{base_name}\n路径：{os.path.dirname(output_path)}")
        except Exception as e:
            messagebox.showerror("错误", f"生成配置文件失败：\n{e}")
    
    def batch_export_images(self):
        """批量导出所有启用了图标的图像"""
        if not self.image_configs:
            messagebox.showinfo("提示", "当前没有图像配置，无法导出图像。")
            return
        valid_configs = [cfg for cfg in self.image_configs if cfg["icon_states"]]
        if not valid_configs:
            messagebox.showinfo("提示", "所有图像配置都未启用任何图标，无法导出图像。")
            return
        export_dir = filedialog.askdirectory(title="选择批量导出目录")
        if not export_dir:
            return
        try:
            success_count = 0
            failed_images = []
            for config in valid_configs:
                try:
                    safe_name = "".join(c for c in config["name"] if c not in r'\/:*?"<>|')
                    if not safe_name:
                        safe_name = f"image_{self.image_configs.index(config)}"
                    file_path = os.path.join(export_dir, f"{safe_name}.png")
                    final_img = self._compose_image(config["icon_states"])
                    final_img.save(file_path, "PNG")
                    success_count += 1
                except Exception as e:
                    failed_images.append(f"{config['name']}: {str(e)}")
            message = f"批量导出完成！\n成功导出 {success_count} 个图像到：\n{export_dir}"
            if failed_images:
                message += f"\n\n失败 {len(failed_images)} 个：\n" + "\n".join(failed_images[:5])
                if len(failed_images) > 5:
                    message += f"\n... 共 {len(failed_images)} 个失败"
            messagebox.showinfo("成功", message)
        except Exception as e:
            messagebox.showerror("错误", f"批量导出失败：\n{e}")

# ============ 启动 ============
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageGeneratorApp(root)  # 可传入自定义 project_root 参数，如：project_root="/path/to/your/project"
    root.mainloop()