# File: ImageTest/icon_manager.py
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import random

# ========================================
# 数据类
# ========================================
class IconData:
    def __init__(self, name="", width=0, height=0, top=0, left=0, reuse=False, 
                 reuse_name="", reuse_top=0, reuse_left=0, class_name=""):
        self.name = name
        self.width = width
        self.height = height
        self.top = top
        self.left = left
        self.reuse = reuse
        self.reuse_name = reuse_name
        self.reuse_top = reuse_top
        self.reuse_left = reuse_left
        self.class_name = class_name  # UI类名
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            top=data.get("top", 0),
            left=data.get("left", 0),
            reuse=data.get("reuse", False),
            reuse_name=data.get("reuse_name", ""),
            reuse_top=data.get("reuse_top", 0),
            reuse_left=data.get("reuse_left", 0),
            class_name=data.get("class_name", "")  # 从JSON读取类名
        )
    
    def to_dict(self):
        result = {
            "name": self.name,
            "class_name": self.class_name,  # 类名写入JSON
            "width": self.width,
            "height": self.height,
            "top": self.top,
            "left": self.left,
            "reuse": self.reuse
        }
        if self.reuse:
            result["reuse_name"] = self.reuse_name
            result["reuse_top"] = self.reuse_top
            result["reuse_left"] = self.reuse_left
        return result

# ========================================
# 主应用类
# ========================================
class IconManagerApp:
    THUMBNAIL_SIZE = (80, 80)
    ITEM_WIDTH = 110
    ITEM_HEIGHT = 125
    PREVIEW_HEIGHT = 165
    
    def __init__(self, root):
        self.root = root
        self.root.title("UI 图标管理器")
        self.root.geometry("1000x700")
        self.root.minsize(900, 650)
        
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
    
    def get_subfolders(self):
        """获取ImageUI下的所有子文件夹"""
        if not os.path.exists(self.base_resources_dir):
            return []
        
        subfolders = []
        for item in os.listdir(self.base_resources_dir):
            item_path = os.path.join(self.base_resources_dir, item)
            if os.path.isdir(item_path):
                subfolders.append(item)
        
        return sorted(subfolders)
    
    def generate_config_path(self, subfolder):
        """根据子文件夹生成对应的配置文件路径"""
        config_name = f"ui_config_{subfolder}.json"
        # 修改：将所有配置文件集中放在UI_Config文件夹中
        return os.path.join(self.project_root, "ImageTest", "UI_Config", config_name)
    
    def ensure_background_image(self):
        """确保 background.png 存在，不存在则创建 100x100 黑色图片"""
        bg_path = os.path.join(self.resources_dir, 'background.png')
        if not os.path.exists(bg_path):
            try:
                img = Image.new('RGB', (100, 100), color='black')
                img.save(bg_path)
                print(f"已创建 background.png (100x100) 在 {self.resources_dir}")
            except Exception as e:
                print(f"创建 background.png 失败: {e}")
    
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
    
    def load_config(self):
        """加载当前子文件夹对应的JSON配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                self.config_data = {}
                for filename, data in raw_data.items():
                    self.config_data[filename] = IconData.from_dict(data)
            except Exception as e:
                messagebox.showerror("错误", f"加载配置失败：{e}")
                self.config_data = {}
        else:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=4, ensure_ascii=False)
            self.config_data = {}
    
    def save_config(self):
        """手动保存配置"""
        self.save_current_form()
        
        # 确保 background.png 在 JSON 首位
        export_data = {}
        if 'background.png' in self.config_data:
            export_data['background.png'] = self.config_data['background.png'].to_dict()
        
        # 添加其他文件
        for fn, ic in self.config_data.items():
            if fn != 'background.png':
                export_data[fn] = ic.to_dict()
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("成功", "配置已保存！")
            self.unsaved_changes = False
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{e}")
    
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
        self.image_label.grid(row=0, column=0, rowspan=12, padx=(0, 10), sticky="nsew")
        
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
        
        # 复用配置
        self.reuse_var = tk.BooleanVar()
        reuse_check = ttk.Checkbutton(form_frame, text="启用复用", variable=self.reuse_var, 
                                     command=self.toggle_reuse_fields)
        reuse_check.grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 5))
        
        ttk.Label(form_frame, text="复用顶部 (px):").grid(row=10, column=0, sticky="w", pady=2)
        self.reuse_top_var = tk.IntVar()
        self.reuse_top_entry = ttk.Entry(form_frame, textvariable=self.reuse_top_var, width=20)
        self.reuse_top_entry.grid(row=10, column=1, sticky="w", pady=2, padx=(0, 10))
        
        ttk.Label(form_frame, text="复用左侧 (px):").grid(row=11, column=0, sticky="w", pady=2)
        self.reuse_left_var = tk.IntVar()
        self.reuse_left_entry = ttk.Entry(form_frame, textvariable=self.reuse_left_var, width=20)
        self.reuse_left_entry.grid(row=11, column=1, sticky="w", pady=2, padx=(0, 10))
        
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
        
        # 第 3 行：按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        
        # 删除图标按钮
        ttk.Button(btn_frame, text="删除图标", command=self.delete_icon, style="Danger.TButton").pack(side="right", padx=(0, 10))
        
        # 清除按钮
        ttk.Button(btn_frame, text="清除所有位置", command=self.clear_all, style="Danger.TButton").pack(side="right", padx=(0, 10))
        
        # 保存按钮
        ttk.Button(btn_frame, text="保存配置", command=self.save_config).pack(side="right")
    
    def validate_class_name(self, input_str):
        """验证UI类名：只允许英文、数字和下划线"""
        if not input_str:  # 允许为空
            return True
        # 检查每个字符是否为字母、数字或下划线
        return all(c.isalnum() or c == '_' for c in input_str) and input_str.isascii()
    
    def toggle_reuse_fields(self):
        """切换复用字段的显示/隐藏。复用开启时自动把复用名称设为当前 UI 名称（内部保存），不再显示复用名称输入框。"""
        if self.reuse_var.get():
            # 只显示复用坐标字段
            self.reuse_top_entry.grid()
            self.reuse_left_entry.grid()
        else:
            # 隐藏复用坐标字段
            self.reuse_top_entry.grid_remove()
            self.reuse_left_entry.grid_remove()
    
    def on_folder_change(self, event):
        """处理文件夹切换"""
        new_subfolder = self.folder_combobox.get()
        
        if new_subfolder == self.current_subfolder:
            return
        
        # 检查是否有未保存的更改
        if self.unsaved_changes:
            result = messagebox.askyesnocancel(
                "切换平台确认",
                f"是否保存后再切换到 {new_subfolder}？\n\n"
                "“是”：保存并切换\n"
                "“否”：不保存，直接切换\n"
                "“取消”：返回继续编辑"
            )
            if result is True:
                self.save_config()
                self.switch_to_folder(new_subfolder)
            elif result is False:
                self.unsaved_changes = False
                self.switch_to_folder(new_subfolder)
            # 如果取消，则不切换，恢复下拉菜单的值为当前文件夹
            else:
                self.folder_combobox.set(self.current_subfolder)
        else:
            self.switch_to_folder(new_subfolder)
    
    def switch_to_folder(self, new_subfolder):
        """切换到新文件夹"""
        self.current_subfolder = new_subfolder
        self.resources_dir = os.path.join(self.base_resources_dir, self.current_subfolder)
        self.config_file = self.generate_config_path(self.current_subfolder)
        
        # 创建必要目录
        os.makedirs(self.resources_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # 确保 background.png 存在
        self.ensure_background_image()
        
        # 重置状态
        self.current_index = 0
        self.unsaved_changes = False
        self.thumbnail_images.clear()
        self.highlight_frames.clear()
        self.reuse_labels.clear()
        self.class_name_colors.clear()
        self.used_colors.clear()
        
        # 清空缩略图区域
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        # 重新加载数据
        self.load_image_files()
        self.load_config()
        self.create_thumbnail_strip()
        self.update_display()
        
        # 更新窗口标题
        self.root.title(f"UI 图标管理器 - {self.current_subfolder}")
    
    def mark_unsaved_changes(self):
        """标记有未保存的更改"""
        self.unsaved_changes = True
    
    def create_thumbnail_strip(self):
        """创建完整缩略图条"""
        for filename in self.image_files:
            item_frame = tk.Frame(self.scroll_frame, width=self.ITEM_WIDTH, height=self.ITEM_HEIGHT, padx=2, pady=2)
            item_frame.pack(side="left", padx=6, pady=6)
            item_frame.pack_propagate(False)
            
            # 创建复用状态标签（初始隐藏）
            reuse_label = tk.Label(item_frame, text="复用", bg="lightgreen", font=("微软雅黑", 7))
            self.reuse_labels[filename] = reuse_label
            
            # 获取高亮颜色
            color = self.get_highlight_color(filename)
            highlight_frame = tk.Frame(
                item_frame,
                highlightbackground=color if color else "gray",
                highlightthickness=3 if color else 1
            )
            highlight_frame.pack(fill="both", expand=True)
            self.highlight_frames[filename] = highlight_frame
            
            # 加载并显示缩略图
            photo = self.get_thumbnail(filename)
            if photo:
                img_label = tk.Label(
                    highlight_frame,
                    image=photo,
                    text=os.path.splitext(filename)[0],
                    compound="bottom",
                    font=("微软雅黑", 8),
                    anchor="center",
                    bg="lightgray"
                )
                img_label.image = photo  # 保持引用
                img_label.pack(fill="both", expand=True, padx=2, pady=2)
                img_label.bind("<Button-1>", lambda e, f=filename: self.select_image(f))
    
    def get_thumbnail(self, filename):
        """获取缩略图"""
        if filename in self.thumbnail_images:
            return self.thumbnail_images[filename]
        
        img_path = os.path.join(self.resources_dir, filename)
        try:
            img = Image.open(img_path)
            img.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.thumbnail_images[filename] = photo
            return photo
        except Exception as e:
            print(f"缩略图加载失败: {filename}, {e}")
            return None
    
    def get_highlight_color(self, filename):
        """计算高亮颜色 - 支持多种状态判断"""
        if filename not in self.config_data:
            return "red"
        
        data = self.config_data[filename]
        
        # 如果没有类名，红色高亮
        if not data.class_name:
            return "red"
        
        # 主位置为0,0，红色高亮
        if data.top == 0 and data.left == 0:
            return "red"
        
        # 如果启用了复用，复用位置为0,0也需要红色高亮
        if data.reuse and data.reuse_top == 0 and data.reuse_left == 0:
            return "red"
        
        # 如果有类名且该类名有多个图标，使用对应的颜色
        if data.class_name and data.class_name in self.class_name_colors:
            return self.class_name_colors[data.class_name]
        
        return None
    
    def generate_unique_color(self):
        """
        生成一个唯一且相对较深的随机颜色（十六进制 #RRGGBB）。
        采用 HSV（色相‑饱和度‑明度）空间生成颜色：
        - 色相随即取值 0‑1，保证颜色多样；
        - 饱和度保持在 0.6‑1.0，使颜色不至于过于灰暗；
        - 明度（亮度）限制在 0.3‑0.6 之间，确保颜色足够“深”，在灰色 GUI 背景上更明显。
        """
        import colorsys, random

        while True:
            # 随机生成色相
            h = random.random()                     # 0.0 – 1.0
            # 高饱和度，避免出现过于淡的颜色
            s = random.uniform(0.6, 1.0)             # 0.6 – 1.0
            # 低明度，使颜色偏暗
            v = random.uniform(0.3, 0.6)             # 0.3 – 0.6

            # 将 HSV 转换为 RGB（0‑255 整数）
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            r, g, b = int(r * 255), int(g * 255), int(b * 255)

            color = f'#{r:02x}{g:02x}{b:02x}'
            # 确保颜色在当前已使用集合中唯一
            if color not in self.used_colors:
                self.used_colors.add(color)   # 记录已使用，防止后续重复
                return color
    
    def update_thumbnail_highlights(self):
        """更新高亮状态和复用标签显示"""
        # 先清空颜色映射，重新统计类名出现次数
        self.class_name_colors.clear()
        self.used_colors.clear()
        
        # 统计所有非空类名的出现次数
        class_name_counts = {}
        for filename in self.image_files:
            if filename in self.config_data:
                class_name = self.config_data[filename].class_name
                if class_name:  # 只统计非空类名
                    class_name_counts[class_name] = class_name_counts.get(class_name, 0) + 1
        
        # 只为出现次数大于1的类名生成颜色
        for class_name, count in class_name_counts.items():
            if count > 1 and class_name not in self.class_name_colors:
                color = self.generate_unique_color()
                self.class_name_colors[class_name] = color
                self.used_colors.add(color)
        
        # 更新每个图标的高亮
        for filename in self.image_files:
            frame = self.highlight_frames.get(filename)
            reuse_label = self.reuse_labels.get(filename)
            
            if frame:
                color = self.get_highlight_color(filename)
                if color:
                    frame.configure(highlightbackground=color, highlightthickness=3)
                else:
                    frame.configure(highlightbackground="gray", highlightthickness=1)
            
            # 更新复用标签显示
            if reuse_label:
                if filename in self.config_data and self.config_data[filename].reuse:
                    reuse_label.pack(side="top", fill="x")
                else:
                    reuse_label.pack_forget()
    
    def select_image(self, filename):
        """选择图标（切换前自动保存）"""
        self.save_current_form()
        try:
            self.current_index = self.image_files.index(filename)
            self.update_display()
        except ValueError:
            pass
    
    def resize_background_image(self, width, height):
        """调整 background.png 的尺寸"""
        try:
            bg_path = os.path.join(self.resources_dir, 'background.png')
            img = Image.open(bg_path)
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            img.save(bg_path)
            # 清除缩略图缓存，使其重新加载
            if 'background.png' in self.thumbnail_images:
                del self.thumbnail_images['background.png']
            print(f"background.png 已调整为 {width}x{height}")
        except Exception as e:
            print(f"调整 background.png 尺寸失败: {e}")
            messagebox.showerror("错误", f"调整背景图片尺寸失败：{e}")
    
    def save_current_form(self):
        """保存当前表单，检测是否更改"""
        if not self.image_files:
            return
        
        filename = self.image_files[self.current_index]
        if filename not in self.config_data:
            return
        
        # 强制background.png名称为"background"，类名也为"background"
        if filename == 'background.png':
            new_name = "background"
            new_class_name = "background"
        else:
            new_name = self.name_var.get().strip()
            new_class_name = self.class_name_var.get().strip()
        
        new_top = self.top_var.get()
        new_left = self.left_var.get()
        new_width = self.width_var.get()
        new_height = self.height_var.get()
        
        # 复用配置
        has_reuse = self.reuse_var.get()
        new_reuse_name = new_name if has_reuse else ""
        new_reuse_top = self.reuse_top_var.get() if has_reuse else 0
        new_reuse_left = self.reuse_left_var.get() if has_reuse else 0
        
        # 全局名称唯一性验证，检查新名称是否与已有名称冲突（排除当前文件本身）
        for other_filename, other_data in self.config_data.items():
            if other_filename == filename:
                continue  # 跳过当前文件
            # 检查主名称冲突
            if new_name == other_data.name:
                messagebox.showwarning("警告", f"主名称 '{new_name}' 已存在于 '{other_filename}' 中！\n所有UI名称必须唯一。")
                return
            # 检查主名称是否与他人的复用名称冲突
            if other_data.reuse and new_name == other_data.reuse_name:
                messagebox.showwarning("警告", f"主名称 '{new_name}' 已作为复用名称存在于 '{other_filename}' 中！\n所有UI名称必须唯一。")
                return
            # 检查复用名称冲突
            if has_reuse:
                if new_reuse_name == other_data.name:
                    messagebox.showwarning("警告", f"复用名称 '{new_reuse_name}' 已存在于 '{other_filename}' 中！\n所有UI名称必须唯一。")
                    return
                if other_data.reuse and new_reuse_name == other_data.reuse_name:
                    messagebox.showwarning("警告", f"复用名称 '{new_reuse_name}' 已作为复用名称存在于 '{other_filename}' 中！\n所有UI名称必须唯一。")
                    return
        
        old_data = self.config_data[filename]
        # 检查是否有更改
        has_changes = (
            old_data.name != new_name or 
            old_data.class_name != new_class_name or  # 检查类名变化
            old_data.top != new_top or 
            old_data.left != new_left or
            old_data.width != new_width or
            old_data.height != new_height or
            old_data.reuse != has_reuse or
            old_data.reuse_name != new_reuse_name or
            old_data.reuse_top != new_reuse_top or
            old_data.reuse_left != new_reuse_left
        )
        
        if has_changes:
            # 如果是background.png，且尺寸改变，则调整图片
            if filename == 'background.png' and (old_data.width != new_width or old_data.height != new_height):
                self.resize_background_image(new_width, new_height)
            
            self.config_data[filename].name = new_name
            self.config_data[filename].class_name = new_class_name  # 保存类名
            self.config_data[filename].top = new_top
            self.config_data[filename].left = new_left
            self.config_data[filename].width = new_width
            self.config_data[filename].height = new_height
            self.config_data[filename].reuse = has_reuse
            self.config_data[filename].reuse_name = new_reuse_name
            self.config_data[filename].reuse_top = new_reuse_top
            self.config_data[filename].reuse_left = new_reuse_left
            self.unsaved_changes = True
            self.update_thumbnail_highlights()
    
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
    
    def on_frame_configure(self, event):
        """更新滚动区域"""
        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))
    
    def on_mousewheel(self, event):
        """支持鼠标滚轮横向滚动"""
        self.thumb_canvas.xview_scroll(-1 * (event.delta // 120), "units")
    
    def on_shift_mousewheel(self, event):
        """支持Shift+滚轮快速滚动"""
        self.thumb_canvas.xview_scroll(-3 * (event.delta // 120), "units")
    
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
                reuse_left=0
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

# ============ 启动 ============
if __name__ == "__main__":
    root = tk.Tk()
    app = IconManagerApp(root)
    root.mainloop()