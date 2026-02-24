# File: ImageTest/icon_manager.py
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# ========================================
# 数据类
# ========================================
class IconData:
    def __init__(self, name="", width=0, height=0, top=0, left=0):
        self.name = name
        self.width = width
        self.height = height
        self.top = top
        self.left = left
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            top=data.get("top", 0),
            left=data.get("left", 0)
        )
    
    def to_dict(self):
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "top": self.top,
            "left": self.left
        }

# ========================================
# 主应用类
# ========================================
class IconManagerApp:
    # 缩略图设置作为类变量
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
        self.current_index = 0
        self.unsaved_changes = False
        
        self.load_image_files()
        self.load_config()
        self.setup_gui()
        self.create_thumbnail_strip()
        self.update_display()
        
        # 拦截关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
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
        # 将所有配置文件集中放在UI_Config文件夹中
        return os.path.join(self.project_root, "ImageTest", "UI_Config", config_name)
    
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
        export_data = {fn: ic.to_dict() for fn, ic in self.config_data.items()}
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
        
        self.unsaved_changes = True
        
        # 刷新显示
        self.update_display()
        messagebox.showinfo("完成", "所有位置数据已重置为 0，请记得保存！")
    
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
        preview_frame = ttk.LabelFrame(main_frame, text="选择图标（红色边框为未设置位置）", 
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
        self.image_label.grid(row=0, column=0, rowspan=6, padx=(0, 10), sticky="nsew")
        
        # 右侧：表单
        form_frame = ttk.LabelFrame(content_frame, text="图标信息", padding="10")
        form_frame.grid(row=0, column=1, sticky="nsew")
        
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # 表单内容
        ttk.Label(form_frame, text="图像文件名:").grid(row=0, column=0, sticky="w", pady=2)
        self.filename_var = tk.StringVar()
        ttk.Label(form_frame, textvariable=self.filename_var).grid(row=0, column=1, sticky="w", pady=2)
        
        ttk.Label(form_frame, text="UI 名称:").grid(row=1, column=0, sticky="w", pady=2)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(form_frame, textvariable=self.name_var, width=40)
        name_entry.grid(row=1, column=1, sticky="ew", pady=2)
        
        ttk.Label(form_frame, text="宽度 (px):").grid(row=2, column=0, sticky="w", pady=2)
        self.width_var = tk.IntVar()
        width_entry = ttk.Entry(form_frame, textvariable=self.width_var, width=20, state="readonly")
        width_entry.grid(row=2, column=1, sticky="w", pady=2, padx=(0, 10))
        
        ttk.Label(form_frame, text="高度 (px):").grid(row=3, column=0, sticky="w", pady=2)
        self.height_var = tk.IntVar()
        height_entry = ttk.Entry(form_frame, textvariable=self.height_var, width=20, state="readonly")
        height_entry.grid(row=3, column=1, sticky="w", pady=2, padx=(0, 10))
        
        ttk.Label(form_frame, text="顶部 (px):").grid(row=4, column=0, sticky="w", pady=2)
        self.top_var = tk.IntVar()
        ttk.Entry(form_frame, textvariable=self.top_var, width=20).grid(row=4, column=1, sticky="w", pady=2, padx=(0, 10))
        
        ttk.Label(form_frame, text="左侧 (px):").grid(row=5, column=0, sticky="w", pady=2)
        self.left_var = tk.IntVar()
        ttk.Entry(form_frame, textvariable=self.left_var, width=20).grid(row=5, column=1, sticky="w", pady=2, padx=(0, 10))
        
        form_frame.columnconfigure(1, weight=1)
        
        # 绑定变量变化事件
        self.name_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.top_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        self.left_var.trace_add("write", lambda *args: self.mark_unsaved_changes())
        
        # 第 3 行：按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        
        # 清除按钮（在保存按钮左侧）
        ttk.Button(btn_frame, text="清除所有位置", command=self.clear_all, style="Danger.TButton").pack(side="right", padx=(0, 10))
        
        # 保存按钮
        ttk.Button(btn_frame, text="保存配置", command=self.save_config).pack(side="right")
    
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
        
        # 重置状态
        self.current_index = 0
        self.unsaved_changes = False
        self.thumbnail_images.clear()
        self.highlight_frames.clear()
        
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
            
            highlight_frame = tk.Frame(
                item_frame,
                highlightbackground="red" if self.should_highlight(filename) else "gray",
                highlightthickness=3 if self.should_highlight(filename) else 1
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
    
    def should_highlight(self, filename):
        """判断是否高亮"""
        if filename not in self.config_data:
            return True
        data = self.config_data[filename]
        return data.top == 0 and data.left == 0
    
    def update_thumbnail_highlights(self):
        """更新高亮状态"""
        for filename in self.image_files:
            frame = self.highlight_frames.get(filename)
            if frame:
                if self.should_highlight(filename):
                    frame.configure(highlightbackground="red", highlightthickness=3)
                else:
                    frame.configure(highlightbackground="gray", highlightthickness=1)
    
    def select_image(self, filename):
        """选择图标（切换前自动保存）"""
        self.save_current_form()
        try:
            self.current_index = self.image_files.index(filename)
            self.update_display()
        except ValueError:
            pass
    
    def save_current_form(self):
        """保存当前表单，检测是否更改"""
        if not self.image_files:
            return
        
        filename = self.image_files[self.current_index]
        if filename not in self.config_data:
            return
        
        new_name = self.name_var.get().strip()
        new_top = self.top_var.get()
        new_left = self.left_var.get()
        old_data = self.config_data[filename]
        
        if (old_data.name != new_name or 
            old_data.top != new_top or 
            old_data.left != new_left):
            self.config_data[filename].name = new_name
            self.config_data[filename].top = new_top
            self.config_data[filename].left = new_left
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
                height=h
            )
        
        icon_data = self.config_data[filename]
        self.name_var.set(icon_data.name)
        self.width_var.set(icon_data.width)
        self.height_var.set(icon_data.height)
        self.top_var.set(icon_data.top)
        self.left_var.set(icon_data.left)
        
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

# ============ 启动 ============
if __name__ == "__main__":
    root = tk.Tk()
    app = IconManagerApp(root)
    root.mainloop()