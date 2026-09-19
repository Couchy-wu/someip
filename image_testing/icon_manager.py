# File: image_testing/icon_manager.py
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
try:                                     # 作为包导入（python -m / import image_testing.icon_manager）
    from .image_similarity import get_image_hash
except ImportError:                      # 直接运行本文件（脚本模式，目录已在 sys.path）
    from image_similarity import get_image_hash
import random


# ========================================
# 主应用类
# ========================================
# ---- 拆分后的能力组合（见各模块说明） ----
from image_testing.icon_config import IconConfigMixin          # noqa: E402
from image_testing.icon_data import IconData                   # noqa: E402
from image_testing.icon_thumbnail import IconThumbnailMixin    # noqa: E402


from image_testing.icon_form import IconFormMixin                  # noqa: E402


class IconManagerApp(IconConfigMixin, IconThumbnailMixin, IconFormMixin):
    THUMBNAIL_SIZE = (80, 80)
    ITEM_WIDTH = 110
    ITEM_HEIGHT = 125
    PREVIEW_HEIGHT = 165
    
    def __init__(self, root):
        self.root = root
        self.root.title("UI 图标管理器")
        self.root.geometry("1100x800")
        self.root.minsize(1000, 750)
        
        # 路径配置作为实例变量
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_resources_dir = os.path.join(self.project_root, "Resources", "ImageUI")
        
        # 获取子文件夹列表
        self.subfolders = self.get_subfolders()
        self.current_subfolder = self.subfolders[0] if self.subfolders else ""
        
        # 初始化当前文件夹路径
        self.resources_dir = os.path.join(self.base_resources_dir, self.current_subfolder)
        self.config_file = self.generate_config_path(self.current_subfolder)
        
        # 创建必要目录
        os.makedirs(self.resources_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # 初始化其他实例变量
        self.image_files = []
        self.config_data = {}
        self.thumbnail_images = {}
        self.highlight_frames = {}
        self.reuse_labels = {}  # 存储复用状态标签
        self.current_index = 0
        self.unsaved_changes = False
        
        # 类名颜色映射
        self.class_name_colors = {}
        self.used_colors = set()

        # 复用控件引用存储
        self.reuse_var = tk.BooleanVar()
        self.reuse2_var = tk.BooleanVar()
        self.reuse3_var = tk.BooleanVar()

        self.reuse_top_var = tk.IntVar()
        self.reuse_top_2_var = tk.IntVar()
        self.reuse_top_3_var = tk.IntVar()

        self.reuse_left_var = tk.IntVar()
        self.reuse_left_2_var = tk.IntVar()
        self.reuse_left_3_var = tk.IntVar()

        self.ensure_background_image()
        
        self.load_image_files()
        self.load_config()
        self.setup_gui()
        self.create_thumbnail_strip()
        self.update_display()
        
        # 拦截关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 绑定系统剪贴板快捷键
        self.root.bind_all('<Control-c>', self.copy_to_clipboard)
        # self.root.bind_all('<Control-v>', self.paste_from_clipboard)
        self.root.bind_all('<Control-x>', self.cut_to_clipboard)
    
    def load_image_files(self):
        """扫描当前子文件夹中的图像文件"""
        extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'}
        
        if not os.path.exists(self.resources_dir):
            self.image_files = []
            return
        
        self.image_files = sorted([
            f for f in os.listdir(self.resources_dir)
            if os.path.isfile(os.path.join(self.resources_dir, f))
            and os.path.splitext(f.lower())[1] in extensions
        ])
        
        # 确保 background.png 在列表第一位
        if 'background.png' in self.image_files:
            self.image_files.remove('background.png')
            self.image_files.insert(0, 'background.png')
        
        if not self.image_files:
            messagebox.showwarning("警告", f"未在 {self.current_subfolder} 目录中找到图像文件！")

    def clear_all(self):
        """一键清除所有位置数据"""
        if not self.config_data:
            messagebox.showinfo("提示", "当前没有可清除的配置数据。")
            return
        
        result = messagebox.askyesno(
            "清除确认",
            "确定要清除所有图标的位置数据吗？\n\n"
            "此操作会将所有图标的【顶部】和【左侧】值重置为 0。\n"
            "点击“保存配置”后才会写入文件。"
        )
        
        if not result:
            return
        
        # 清除所有位置数据
        for icon_data in self.config_data.values():
            icon_data.top = 0
            icon_data.left = 0
            if icon_data.reuse:
                icon_data.reuse_top = 0
                icon_data.reuse_left = 0
        
        self.unsaved_changes = True
        
        # 刷新显示
        self.update_display()
        messagebox.showinfo("完成", "所有位置数据已重置为 0，请记得保存！")
    
    def delete_icon(self):
        """删除当前图标"""
        if not self.image_files:
            return
        
        filename = self.image_files[self.current_index]
        
        # 禁止删除 background.png
        if filename == 'background.png':
            messagebox.showwarning("警告", "该图标不可删除")
            return
        
        # 二次确认
        result = messagebox.askyesno(
            "删除确认",
            f"确定要删除图标 '{filename}' 吗？\n\n"
            "此操作将同时删除图像文件和配置数据。\n"
            "点击“是”确认删除。"
        )
        
        if not result:
            return
        
        # 删除文件
        file_path = os.path.join(self.resources_dir, filename)
        try:
            os.remove(file_path)
        except Exception as e:
            messagebox.showerror("错误", f"删除文件失败：{e}")
            return
        
        # 从配置数据中删除
        self.config_data.pop(filename, None)
        
        # 从缩略图缓存中删除
        self.thumbnail_images.pop(filename, None)
        self.highlight_frames.pop(filename, None)
        self.reuse_labels.pop(filename, None)
        
        # 从列表中删除
        self.image_files.pop(self.current_index)
        
        # 调整当前索引
        if self.current_index >= len(self.image_files):
            self.current_index = len(self.image_files) - 1
        
        self.unsaved_changes = True
        
        # 重新创建缩略图条
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.create_thumbnail_strip()
        
        # 更新显示
        if self.image_files:
            self.update_display()
        else:
            # 如果没有图标了，清空显示
            self.image_label.config(text="无图像可显示", image="")
            self.filename_var.set("")
            self.name_var.set("")
            self.width_var.set(0)
            self.height_var.set(0)
            self.top_var.set(0)
            self.left_var.set(0)
            self.reuse_var.set(False)
            self.reuse_top_var.set(0)
            self.reuse_left_var.set(0)
            self.class_name_var.set("")  # 清空类名显示
        
        messagebox.showinfo("完成", f"'{filename}' 已删除！")
    
    def setup_gui(self):
        """构建主界面"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 第 0 行：平台选择下拉菜单
        platform_frame = ttk.LabelFrame(main_frame, text="选择平台文件夹", padding="10")
        platform_frame.pack(fill="x", pady=(0, 10))
        
        # 下拉菜单标签和说明
        select_frame = ttk.Frame(platform_frame)
        select_frame.pack(fill="x")
        
        ttk.Label(select_frame, text="当前平台:").pack(side="left")
        
        # 创建下拉菜单
        self.folder_combobox = ttk.Combobox(
            select_frame, 
            values=self.subfolders,
            state="readonly",
            width=30
        )
        self.folder_combobox.pack(side="left", padx=(10, 0))
        
        if self.current_subfolder:
            self.folder_combobox.set(self.current_subfolder)
        
        # 绑定选择事件
        self.folder_combobox.bind("<<ComboboxSelected>>", self.on_folder_change)
        
        # 第 1 行：缩略图预览条
        preview_frame = ttk.LabelFrame(main_frame, text="选择图标（红色边框为未设置位置或类名）", 
                                     height=self.PREVIEW_HEIGHT)
        preview_frame.pack(fill="x", pady=(0, 10), anchor="n")
        preview_frame.pack_propagate(False)
        
        # Canvas + 内容 Frame
        self.thumb_canvas = tk.Canvas(preview_frame, height=self.PREVIEW_HEIGHT - 4, highlightthickness=0)
        self.thumb_canvas.pack(side="left", fill="x", expand=True)
        
        # 水平滚动条
        h_scroll = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.thumb_canvas.xview)
        h_scroll.pack(side="bottom", fill="x")
        self.thumb_canvas.configure(xscrollcommand=h_scroll.set)
        
        # 内容框架
        self.scroll_frame = ttk.Frame(self.thumb_canvas)
        self.scroll_frame_id = self.thumb_canvas.create_window(0, 0, window=self.scroll_frame, anchor="nw")
        
        # 绑定事件
        self.scroll_frame.bind("<Configure>", self.on_frame_configure)
        
        # 支持鼠标滚轮
        self.thumb_canvas.bind_all("<MouseWheel>", self.on_mousewheel)
        self.thumb_canvas.bind_all("<Shift-MouseWheel>", self.on_shift_mousewheel)
        
        # 滚动按钮
        btn_left = ttk.Button(preview_frame, text="◀", width=5, 
                             command=lambda: self.thumb_canvas.xview_scroll(-3, "units"))
        btn_left.pack(side="left", padx=(0, 3))
        
        btn_right = ttk.Button(preview_frame, text="▶", width=5, 
                              command=lambda: self.thumb_canvas.xview_scroll(3, "units"))
        btn_right.pack(side="left", padx=(0, 8))
        
        # 第 2 行：主编辑区
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True)
        
        # 左侧：大图预览
        self.image_label = ttk.Label(
            content_frame,
            text="暂无图像",
            anchor="center",
            relief="sunken",
            font=("微软雅黑", 12),
            background="lightgray"
        )
        self.image_label.grid(row=0, column=0, rowspan=16, padx=(0, 10), sticky="nsew")
        
        # 右侧：表单
        form_frame = ttk.LabelFrame(content_frame, text="图标信息", padding="10")
        form_frame.grid(row=0, column=1, sticky="nsew")
        
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # 主配置表单内容
        ttk.Label(form_frame, text="图像文件名:").grid(row=0, column=0, sticky="w", pady=2)
        self.filename_var = tk.StringVar()
        ttk.Label(form_frame, textvariable=self.filename_var).grid(row=0, column=1, sticky="w", pady=2)
        
        ttk.Label(form_frame, text="UI 名称:").grid(row=1, column=0, sticky="w", pady=2)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(form_frame, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=1, column=1, sticky="ew", pady=2)
        
        ttk.Label(form_frame, text="UI 类名:").grid(row=2, column=0, sticky="w", pady=2)
        self.class_name_var = tk.StringVar()
        self.validate_cmd = root.register(self.validate_class_name)
        self.class_name_entry = ttk.Entry(
            form_frame, 
            textvariable=self.class_name_var, 
            width=40,
            validate="key",
            validatecommand=(self.validate_cmd, "%P")
        )
        self.class_name_entry.grid(row=2, column=1, sticky="ew", pady=2)
        
        ttk.Label(form_frame, text="宽度 (px):").grid(row=3, column=0, sticky="w", pady=2)
        self.width_var = tk.IntVar()
        # 修改为可编辑的 Entry，在 update_display 中动态控制状态
        self.width_entry = ttk.Entry(form_frame, textvariable=self.width_var, width=20)
        self.width_entry.grid(row=3, column=1, sticky="w", pady=2, padx=(0, 10))
        
        ttk.Label(form_frame, text="高度 (px):").grid(row=4, column=0, sticky="w", pady=2)
        self.height_var = tk.IntVar()
        self.height_entry = ttk.Entry(form_frame, textvariable=self.height_var, width=20)
        self.height_entry.grid(row=4, column=1, sticky="w", pady=2, padx=(0, 10))
        
        ttk.Label(form_frame, text="顶部 (px):").grid(row=5, column=0, sticky="w", pady=2)
        self.top_var = tk.IntVar()
        ttk.Entry(form_frame, textvariable=self.top_var, width=20).grid(row=5, column=1, sticky="w", pady=2, padx=(0, 10))
        
        ttk.Label(form_frame, text="左侧 (px):").grid(row=6, column=0, sticky="w", pady=2)
        self.left_var = tk.IntVar()
        ttk.Entry(form_frame, textvariable=self.left_var, width=20).grid(row=6, column=1, sticky="w", pady=2, padx=(0, 10))
        
        # 分隔线
        separator = ttk.Separator(form_frame, orient='horizontal')
        separator.grid(row=7, column=0, columnspan=2, sticky="ew", pady=10)
        
        # 将三个复用开关放在同一行，使用 column 分隔
        self.reuse_check = ttk.Checkbutton(form_frame, text="启用复用", variable=self.reuse_var, 
                                     command=self.toggle_reuse_fields)
        self.reuse_check.grid(row=8, column=0, sticky="w", padx=(0, 10), pady=(0, 5))

        self.reuse2_check = ttk.Checkbutton(form_frame, text="启用第二个复用", variable=self.reuse2_var, 
                                           command=self.toggle_reuse_fields)
        self.reuse2_check.grid(row=8, column=1, sticky="w", padx=(0, 10), pady=(0, 5))  # 紧跟其后

        self.reuse3_check = ttk.Checkbutton(form_frame, text="启用第三个复用", variable=self.reuse3_var, 
                                           command=self.toggle_reuse_fields)
        self.reuse3_check.grid(row=9, column=0, sticky="w", pady=(0, 5))  # 最右边的也靠左排列

        # 复用坐标字段（初始隐藏）
        ttk.Label(form_frame, text="复用顶部 (px):").grid(row=10, column=0, sticky="w", pady=2)
        self.reuse_top_entry = ttk.Entry(form_frame, textvariable=self.reuse_top_var, width=20)
        self.reuse_top_entry.grid(row=10, column=1, sticky="w", pady=2, padx=(0, 10))
        ttk.Label(form_frame, text="复用左侧 (px):").grid(row=11, column=0, sticky="w", pady=2)
        self.reuse_left_entry = ttk.Entry(form_frame, textvariable=self.reuse_left_var, width=20)
        self.reuse_left_entry.grid(row=11, column=1, sticky="w", pady=2, padx=(0, 10))
        # 第二组坐标
        ttk.Label(form_frame, text="第二个复用顶部 (px):").grid(row=12, column=0, sticky="w", pady=2)  
        self.reuse_top_2_entry = ttk.Entry(form_frame, textvariable=self.reuse_top_2_var, width=20)
        self.reuse_top_2_entry.grid(row=12, column=1, sticky="w", pady=2, padx=(0, 10))
        ttk.Label(form_frame, text="第二个复用左侧 (px):").grid(row=13, column=0, sticky="w", pady=2)  
        self.reuse_left_2_entry = ttk.Entry(form_frame, textvariable=self.reuse_left_2_var, width=20)
        self.reuse_left_2_entry.grid(row=13, column=1, sticky="w", pady=2, padx=(0, 10))
        # 第三组坐标
        ttk.Label(form_frame, text="第三个复用顶部 (px):").grid(row=14, column=0, sticky="w", pady=2)
        self.reuse_top_3_entry = ttk.Entry(form_frame, textvariable=self.reuse_top_3_var, width=20)
        self.reuse_top_3_entry.grid(row=14, column=1, sticky="w", pady=2, padx=(0, 10))
        ttk.Label(form_frame, text="第三个复用左侧 (px):").grid(row=15, column=0, sticky="w", pady=2) 
        self.reuse_left_3_entry = ttk.Entry(form_frame, textvariable=self.reuse_left_3_var, width=20)
        self.reuse_left_3_entry.grid(row=15, column=1, sticky="w", pady=2, padx=(0, 10))
        
        # 初始隐藏复用字段
        self.toggle_reuse_fields()
        
        form_frame.columnconfigure(1, weight=1)
        
        # 绑定变量变化事件
        self.name_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.class_name_var.trace_add("write", lambda *args: self.mark_unsaved_changes())  # 监听类名变化
        self.width_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.height_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.top_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.left_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.reuse_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.reuse_top_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.reuse_left_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.reuse2_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.reuse_top_2_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.reuse_left_2_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.reuse3_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.reuse_top_3_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.reuse_left_3_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        
        # 第 3 行：按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        
        # 删除图标按钮
        ttk.Button(btn_frame, text="删除图标", command=self.delete_icon, style="Danger.TButton").pack(side="right", padx=(0, 10))
        
        # 清除按钮
        ttk.Button(btn_frame, text="清除所有位置", command=self.clear_all, style="Danger.TButton").pack(side="right", padx=(0, 10))
        
        # 计算所有图像哈希值按钮
        ttk.Button(btn_frame, text="计算所有图像哈希值",
                   command=self.compute_and_update_hashes).pack(side="right", padx=(0, 10))

        # 保存按钮
        ttk.Button(btn_frame, text="保存配置", command=self.save_config).pack(side="right")
    
    def select_image(self, filename):
        """选择图标（切换前自动保存）"""
        self.save_current_form()
        try:
            self.current_index = self.image_files.index(filename)
            self.update_display()
        except ValueError:
            pass
    
    def on_closing(self):
        """关闭前确认"""
        if not self.unsaved_changes:
            result = messagebox.askyesno(
                "退出确认",
                "确定要退出程序吗？\n\n"
                "“是”：直接退出\n"
                "“否”：返回继续编辑"
            )
            if result:
                self.root.destroy()
            return
        
        result = messagebox.askyesnocancel(
            "退出确认",
            "是否保存并退出？\n\n"
            "“是”：保存并退出\n"
            "“否”：不保存，直接退出\n"
            "“取消”：返回继续编辑"
        )
        if result is True:
            self.save_config()
            self.root.destroy()
        elif result is False:
            self.root.destroy()
    
    def update_display(self):
        """更新当前显示"""
        if not self.image_files:
            self.image_label.config(text="无图像可显示")
            return
        
        filename = self.image_files[self.current_index]
        filepath = os.path.join(self.resources_dir, filename)
        self.filename_var.set(filename)
        
        if filename not in self.config_data:
            try:
                img = Image.open(filepath)
                w, h = img.size
            except:
                w, h = 0, 0
            self.config_data[filename] = IconData(
                name=os.path.splitext(filename)[0],
                width=w,
                height=h,
                reuse=False,
                reuse_name="",
                reuse_top=0,
                reuse_left=0,
                reuse2=False,
                reuse_top_2=0,
                reuse_left_2=0,
                reuse3=False,
                reuse_top_3=0,
                reuse_left_3=0
            )
        
        icon_data = self.config_data[filename]
        
        # 强制 background.png 名称为 background，类名也为 background
        if filename == 'background.png':
            self.name_var.set("background")
            self.class_name_var.set("background")
        else:
            self.name_var.set(icon_data.name)
            self.class_name_var.set(icon_data.class_name)
        
        self.width_var.set(icon_data.width)
        self.height_var.set(icon_data.height)
        self.top_var.set(icon_data.top)
        self.left_var.set(icon_data.left)
        
        # 更新复用相关变量
        self.reuse_var.set(icon_data.reuse)
        self.reuse_top_var.set(icon_data.reuse_top)
        self.reuse_left_var.set(icon_data.reuse_left)
        self.reuse2_var.set(icon_data.reuse2)
        self.reuse_top_2_var.set(icon_data.reuse_top_2)
        self.reuse_left_2_var.set(icon_data.reuse_left_2)
        self.reuse3_var.set(icon_data.reuse3)
        self.reuse_top_3_var.set(icon_data.reuse_top_3)
        self.reuse_left_3_var.set(icon_data.reuse_left_3)
        
        # 控制 width 和 height 输入框状态（background.png 可编辑）
        if filename == 'background.png':
            self.width_entry.config(state="normal")
            self.height_entry.config(state="normal")
            self.name_entry.config(state="readonly")
            self.class_name_entry.config(state="readonly")
        else:
            self.width_entry.config(state="readonly")
            self.height_entry.config(state="readonly")
            self.name_entry.config(state="normal")
            self.class_name_entry.config(state="normal")
        
        # 根据复用状态显示/隐藏复用字段
        self.toggle_reuse_fields()
        
        try:
            image = Image.open(filepath)
            image.thumbnail((350, 350), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo
        except Exception as e:
            self.image_label.config(text=f"加载失败\n{e}", image="")
            self.image_label.image = None
        
        self.update_thumbnail_highlights()
    
    # 新增：剪贴板操作函数
    def copy_to_clipboard(self, event=None):
        """复制选中文本到系统剪贴板"""
        try:
            widget = self.root.focus_get()
            if isinstance(widget, (tk.Entry, ttk.Entry)):
                selected_text = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected_text)
        except:
            pass
        return "break"
    
    def cut_to_clipboard(self, event=None):
        """剪切选中文本到系统剪贴板"""
        try:
            widget = self.root.focus_get()
            if isinstance(widget, (tk.Entry, ttk.Entry)):
                selected_text = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected_text)
                widget.delete('sel.first', 'sel.last')
        except:
            pass
        return "break"
