# File: ImageTest/image_generator.py
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from PIL import Image, ImageTk
from datetime import datetime

# 项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES_DIR = os.path.join(PROJECT_ROOT, "Resources", "ImageUI")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "ImageTest", "UI_Config")

class Tooltip:
    """工具提示类"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        
        widget.bind("<Enter>", self.showtip)
        widget.bind("<Leave>", self.hidetip)
        widget.bind("<ButtonPress>", self.hidetip)
    
    def showtip(self, event=None):
        """显示提示框"""
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        
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
    def __init__(self, root):
        self.root = root
        self.root.title("OSD 图像生成器")
        self.root.geometry("1400x700")
        self.root.minsize(1000, 600)
        
        # 当前平台相关
        self.current_platform = ""
        self.current_platform_dir = ""
        self.config_file = ""
        self.config_data = {}  # {filename: IconData}
        
        # 多图像管理
        self.image_configs = []  # 存储所有图像配置: [{name: str, icon_states: dict, preview: PhotoImage}]
        self.current_image_index = -1  # 当前编辑的图像索引
        
        # 图像缓存
        self.image_cache = {}  # {filename: PIL.Image}
        self.photo_cache = {}  # {filename: Tkinter.PhotoImage}
        
        # 背景信息
        self.bg_image = None  # PIL.Image 背景图
        self.bg_photo = None  # Tkinter.PhotoImage 用于显示
        self.bg_width = 800
        self.bg_height = 480
        
        # 状态颜色映射
        self.status_colors = {
            "main": "blue",      # 🔵 启用位置1
            "reuse": "green",    # 🟢 启用位置2
            "enabled": "red",    # 🔴 启用（无复用）
            None: "lightgray"    # ⚪ 不启用
        }
        
        # 获取平台列表
        self.platforms = self.get_platforms()
        if not self.platforms:
            messagebox.showerror("错误", "未找到任何平台文件夹！请检查 ImageUI 目录结构。")
            self.root.destroy()
            return
        
        # 构建 GUI
        self.setup_gui()
        
        # 初始化第一个平台
        self.current_platform = self.platforms[0]
        self.load_platform(self.current_platform)
        
        # 自动创建第一个图像配置并显示背景
        self.add_new_image()
    
    def get_platforms(self):
        """获取 ImageUI 下的所有子文件夹名称"""
        if not os.path.exists(RESOURCES_DIR):
            return []
        folders = [
            f for f in os.listdir(RESOURCES_DIR)
            if os.path.isdir(os.path.join(RESOURCES_DIR, f))
        ]
        return sorted(folders)
    
    def setup_gui(self):
        """构建主界面"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 第一行：平台选择 + 控制按钮
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
        
        # 新增：加载配置文件按钮
        self.load_config_btn = ttk.Button(top_frame, text="加载配置文件", command=self.load_config_file)
        self.load_config_btn.pack(side="left", padx=(20, 0))
        
        # 控制按钮（从右到左排列）
        self.batch_export_btn = ttk.Button(top_frame, text="批量导出所有图像", command=self.batch_export_images)
        self.batch_export_btn.pack(side="right", padx=(0, 5))
        
        # 修改按钮文本
        self.export_config_btn = ttk.Button(top_frame, text="生成或更新配置文件", command=self.generate_unified_config_file)
        self.export_config_btn.pack(side="right", padx=(0, 5))
        
        self.save_single_btn = ttk.Button(top_frame, text="保存当前图像", command=self.save_single_image)
        self.save_single_btn.pack(side="right", padx=(0, 5))
        
        self.clear_current_btn = ttk.Button(top_frame, text="清除当前选择", command=self.clear_current_selection)
        self.clear_current_btn.pack(side="right", padx=(0, 5))
        
        # 主内容区域
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True)
        
        # 左侧：预览画布 + 图像列表
        left_panel = ttk.Frame(content_frame)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # 图像列表区域
        image_list_frame = ttk.LabelFrame(left_panel, text="图像列表管理", padding="5")
        image_list_frame.pack(fill="x", pady=(0, 10))
        
        # 图像列表工具栏
        list_toolbar = ttk.Frame(image_list_frame)
        list_toolbar.pack(fill="x", pady=(0, 5))
        
        self.add_image_btn = ttk.Button(list_toolbar, text="➕ 添加图像", command=self.add_new_image, width=12)
        self.add_image_btn.pack(side="left", padx=(0, 5))
        
        self.rename_image_btn = ttk.Button(list_toolbar, text="✏️ 重命名", command=self.rename_current_image, width=12)
        self.rename_image_btn.pack(side="left", padx=(0, 5))
        
        self.delete_image_btn = ttk.Button(list_toolbar, text="🗑️ 删除", command=self.delete_current_image, width=12)
        self.delete_image_btn.pack(side="left")
        
        # 图像列表框
        self.image_listbox = tk.Listbox(image_list_frame, height=5, font=("微软雅黑", 9))
        self.image_listbox.pack(side="left", fill="both", expand=True)
        self.image_listbox.bind("<<ListboxSelect>>", self.on_image_selection_change)
        
        # 图像列表滚动条
        self.image_scrollbar = ttk.Scrollbar(image_list_frame, orient="vertical", command=self.image_listbox.yview)
        self.image_scrollbar.pack(side="right", fill="y")
        self.image_listbox.config(yscrollcommand=self.image_scrollbar.set)
        
        # 预览画布区域
        self.canvas_frame = ttk.LabelFrame(left_panel, text="OSD 预览", padding="5")
        self.canvas_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            self.canvas_frame,
            width=800,
            height=480,
            bg="lightgray",
            relief="sunken"
        )
        self.canvas.pack(expand=True, fill="both")
        
        # 右侧：图标选择面板（含状态提示列）
        self.icon_panel_frame = ttk.LabelFrame(content_frame, text="选择图标", padding="10")
        self.icon_panel_frame.pack(side="right", fill="y")
        
        # 创建滚动条区域
        self.icon_canvas = tk.Canvas(self.icon_panel_frame, width=250)
        self.icon_canvas.pack(side="left", fill="y", expand=True)
        
        self.icon_scrollbar = ttk.Scrollbar(
            self.icon_panel_frame,
            orient="vertical",
            command=self.icon_canvas.yview
        )
        self.icon_scrollbar.pack(side="right", fill="y")
        
        self.icon_canvas.configure(yscrollcommand=self.icon_scrollbar.set)
        
        self.icons_inner_frame = ttk.Frame(self.icon_canvas)
        self.icon_canvas.create_window((0, 0), window=self.icons_inner_frame, anchor="nw")
        self.icons_inner_frame.bind("<Configure>", self.on_icon_frame_configure)
        
        # 绑定鼠标滚轮
        self.icon_canvas.bind_all("<MouseWheel>", self.on_mousewheel)
    
    def on_icon_frame_configure(self, event):
        """更新滚动区域"""
        self.icon_canvas.configure(scrollregion=self.icon_canvas.bbox("all"))
    
    def on_mousewheel(self, event):
        """支持鼠标滚轮滚动"""
        self.icon_canvas.yview_scroll(-1 * (event.delta // 120), "units")
    
    def on_platform_change(self, event):
        """平台切换"""
        new_platform = self.platform_var.get()
        if new_platform == self.current_platform:
            return
        self.current_platform = new_platform
        self.load_platform(new_platform)
        # 切换平台后重置所有图像配置
        self.image_configs.clear()
        self.current_image_index = -1
        self.image_listbox.delete(0, tk.END)
        self.add_new_image()
    
    def load_platform(self, platform):
        """加载指定平台的配置和图像"""
        self.current_platform_dir = os.path.join(RESOURCES_DIR, platform)
        self.config_file = os.path.join(CONFIG_DIR, f"ui_config_{platform}.json")
        
        if not os.path.exists(self.config_file):
            messagebox.showerror("错误", f"未找到配置文件：\n{self.config_file}")
            return
        
        # 清空当前状态
        self.image_cache.clear()
        self.photo_cache.clear()
        
        # 加载配置
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            self.config_data = {}
            for filename, data in raw_data.items():
                self.config_data[filename] = data
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败：{e}")
            return
        
        # 加载背景图并设置画布尺寸
        self.load_background()
        
        # 加载非背景图标并创建按钮
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
        
        self.bg_photo = ImageTk.PhotoImage(self.bg_image)
    
    def load_icons_and_create_buttons(self):
        """加载非背景图标的按钮 + 状态提示列"""
        for widget in self.icons_inner_frame.winfo_children():
            widget.destroy()
        
        icon_files = [
            fn for fn in self.config_data.keys()
            if fn != "background.png"
        ]
        
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
            
            # 整行容器
            row_frame = ttk.Frame(self.icons_inner_frame)
            row_frame.pack(fill="x", pady=4)
            
            # 左侧：图标按钮
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
            btn.filename = filename  # 存储文件名以便后续更新状态
            
            # 右侧：状态提示色块（20x20）
            status_label = tk.Label(
                row_frame,
                width=3,
                height=1,
                bg="lightgray",
                relief="flat",
                borderwidth=2
            )
            
            # 绑定点击事件
            btn.bind("<Button-1>", lambda e, f=filename, b=btn, s=status_label: 
                     self.on_icon_click(f, b, s))
            
            # 创建工具提示
            tooltip_text = self.get_status_tooltip_text(filename)
            Tooltip(status_label, tooltip_text)
            
            # 布局
            btn.pack(side="left", padx=(0, 10))
            status_label.pack(side="left", padx=(0, 5))
            
            # 更新状态色块
            self.update_status_label(filename, status_label)
    
    def get_status_tooltip_text(self, filename):
        """获取状态提示文字"""
        if self.current_image_index < 0:
            return "不启用"
        current_states = self.image_configs[self.current_image_index]["icon_states"]
        state = current_states.get(filename)
        config = self.config_data.get(filename, {})
        has_reuse = config.get("reuse", False)
        
        if state is None:
            return "不启用"
        elif has_reuse:
            if state == "main":
                return "启用位置1"
            elif state == "reuse":
                return "启用位置2"
        else:
            if state == "enabled":
                return "启用"
        
        return "未知状态"
    
    def update_status_label(self, filename, label):
        """根据当前状态更新色块颜色"""
        if self.current_image_index < 0:
            color = self.status_colors[None]
        else:
            current_states = self.image_configs[self.current_image_index]["icon_states"]
            state = current_states.get(filename)
            config = self.config_data.get(filename, {})
            
            if state is None:
                color = self.status_colors[None]
            elif config.get("reuse", False):
                color = self.status_colors["main"] if state == "main" else self.status_colors["reuse"]
            else:
                color = self.status_colors["enabled"] if state == "enabled" else self.status_colors[None]
        
        label.config(bg=color)
    
    def on_icon_click(self, filename, button, status_label):
        """点击图标按钮：循环切换状态"""
        if self.current_image_index < 0:
            messagebox.showwarning("警告", "请先创建或选择一个图像！")
            return
        
        current_states = self.image_configs[self.current_image_index]["icon_states"]
        current_state = current_states.get(filename, None)
        config = self.config_data[filename]
        has_reuse = config.get("reuse", False)
        
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
        
        self.update_status_label(filename, status_label)
        self.update_listbox_item_color(self.current_image_index)
        
        # 更新工具提示
        tooltip_text = self.get_status_tooltip_text(filename)
        Tooltip(status_label, tooltip_text)
        
        self.redraw_preview()
    
    def load_config_file(self):
        """加载配置文件并在列表中创建新图像（只加载预览不保存文件）"""
        file_path = filedialog.askopenfilename(
            title="加载配置文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        # 先清空当前的图像数据，防止与新加载的配置混杂
        self.image_configs.clear()
        self.image_listbox.delete(0, tk.END)
        self.current_image_index = -1
        self.refresh_icon_buttons()          # 更新图标按钮的状态显示
        self.canvas.delete("all")            # 清除预览画布
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                messagebox.showerror("错误", "配置文件格式不正确！")
                return
            
            loaded_count = 0
            
            # 遍历每个图像配置
            for image_name, items in data.items():
                # 创建新图像配置
                new_config = {
                    "name": image_name,
                    "icon_states": {},
                    "preview": None
                }
                
                # 解析每个图标项
                for item in items:
                    name = item.get("name")
                    top_left = item.get("top_left", [])
                    
                    if not name or len(top_left) < 2:
                        continue
                    
                    # 查找匹配的filename
                    matched = False
                    
                    for filename, config in self.config_data.items():
                        if filename == "background.png":
                            continue
                        
                        # 检查是否匹配
                        if config.get("name") == name:
                            # 标准位置
                            if top_left[0] == config.get("left") and top_left[1] == config.get("top"):
                                state = "main" if config.get("reuse", False) else "enabled"
                                new_config["icon_states"][filename] = state
                                matched = True
                                break
                        elif config.get("reuse", False) and config.get("reuse_name") == name:
                            # 复用位置
                            if top_left[0] == config.get("reuse_left") and top_left[1] == config.get("reuse_top"):
                                new_config["icon_states"][filename] = "reuse"
                                matched = True
                                break
                    
                    if not matched:
                        print(f"警告：无法匹配图标 '{name}' 在位置 {top_left}")
                
                # 只添加有内容的配置，若无图标也要保留以显示为红色
                if new_config["icon_states"]:
                    self.image_configs.append(new_config)
                    self.image_listbox.insert(tk.END, image_name)
                    self.update_listbox_item_color(len(self.image_configs) - 1)
                    loaded_count += 1
            
            # 读取完毕后恢复当前索引与界面状态
            if self.image_configs:
                self.current_image_index = len(self.image_configs) - 1
                self.image_listbox.selection_clear(0, tk.END)
                self.image_listbox.selection_set(self.current_image_index)
                self.image_listbox.see(self.current_image_index)
                
                self.refresh_icon_buttons()   # 刷新按钮状态
                self.redraw_preview()         # 绘制最新预览
            
            messagebox.showinfo("成功", f"已加载 {loaded_count} 个有效图像配置！")
            
        except Exception as e:
            messagebox.showerror("错误", f"加载配置文件失败：\n{e}")
    
    def add_new_image(self):
        """添加新的图像配置"""
        # 自动生成默认名称
        timestamp = datetime.now().strftime("%m%d_%H%M%S")
        default_name = f"图像_{len(self.image_configs) + 1}_{timestamp}"
        
        new_config = {
            "name": default_name,
            "icon_states": {},
            "preview": None
        }
        self.image_configs.append(new_config)
        self.current_image_index = len(self.image_configs) - 1
        
        # 更新列表框并设置颜色（若为空则为红色）
        self.image_listbox.insert(tk.END, default_name)
        self.update_listbox_item_color(self.current_image_index)
        self.image_listbox.selection_clear(0, tk.END)
        self.image_listbox.selection_set(self.current_image_index)
        self.image_listbox.see(self.current_image_index)
        
        # 根据当前配置刷新按钮状态
        self.refresh_icon_buttons()
        
        # 立即刷新预览，显示空白背景（新图像是空的）
        self.redraw_preview()

    def update_listbox_item_color(self, idx):
        """根据图像是否只有背景来设置列表项颜色。没有任何图标（icon_states 为空）时使用红色，否则使用默认黑色。"""
        if idx < 0 or idx >= len(self.image_configs):
            return
        # 是否仅有背景
        has_icons = bool(self.image_configs[idx]["icon_states"])
        fg_color = "red" if not has_icons else "black"
        # 同时设置普通前景和选中前景
        self.image_listbox.itemconfig(
            idx,
            {
                "fg": fg_color,                # 普通文字颜色
                "selectforeground": fg_color   # 选中时的文字颜色
            }
        )

    def rename_current_image(self):
        """重命名当前选中的图像"""
        if self.current_image_index < 0:
            messagebox.showwarning("警告", "请先选择一个图像！")
            return
        
        current_name = self.image_configs[self.current_image_index]["name"]
        new_name = simpledialog.askstring("重命名", "请输入新的图像名称:", initialvalue=current_name)
        
        if new_name and new_name.strip():
            new_name = new_name.strip()
            self.image_configs[self.current_image_index]["name"] = new_name
            
            # 更新列表框
            self.image_listbox.delete(self.current_image_index)
            self.image_listbox.insert(self.current_image_index, new_name)
            self.update_listbox_item_color(self.current_image_index)
            self.image_listbox.selection_set(self.current_image_index)
    
    def delete_current_image(self):
        """删除当前选中的图像"""
        if self.current_image_index < 0:
            messagebox.showwarning("警告", "请先选择一个图像！")
            return
        
        if len(self.image_configs) <= 1:
            messagebox.showwarning("警告", "至少需要保留一个图像配置！")
            return
        
        confirm = messagebox.askyesno("确认删除", f"确定要删除图像 '{self.image_configs[self.current_image_index]['name']}' 吗？")
        if not confirm:
            return
        
        # 删除当前配置
        del self.image_configs[self.current_image_index]
        
        # 更新列表框
        self.image_listbox.delete(self.current_image_index)
        
        # 调整当前选中索引
        if self.current_image_index >= len(self.image_configs):
            self.current_image_index = len(self.image_configs) - 1
        
        # 重新加载当前图像状态
        self.refresh_icon_buttons()
        self.redraw_preview()
        
        # 选中新的项目
        if self.current_image_index >= 0:
            self.image_listbox.selection_set(self.current_image_index)
    
    def on_image_selection_change(self, event):
        """切换选中的图像配置"""
        selection = self.image_listbox.curselection()
        if not selection:
            return
        
        new_index = selection[0]
        if new_index == self.current_image_index:
            return
        
        self.current_image_index = new_index
        
        # 刷新图标按钮状态
        self.refresh_icon_buttons()
        
        # 重绘预览
        self.redraw_preview()
    
    def refresh_icon_buttons(self):
        """根据当前图像配置刷新所有图标按钮的状态显示"""
        if self.current_image_index < 0:
            return
        
        current_states = self.image_configs[self.current_image_index]["icon_states"]
        
        for row_frame in self.icons_inner_frame.winfo_children():
            children = row_frame.winfo_children()
            if len(children) >= 2:
                btn = children[0]
                status_label = children[1]
                if isinstance(btn, tk.Button) and isinstance(status_label, tk.Label):
                    filename = getattr(btn, 'filename', None)
                    if filename:
                        state = current_states.get(filename)
                        config = self.config_data.get(filename, {})
                        
                        # 更新按钮状态
                        if state is None:
                            btn.config(relief="raised")
                        else:
                            btn.config(relief="sunken")
                        
                        # 更新状态标签颜色
                        self.update_status_label(filename, status_label)
                        
                        # 更新工具提示
                        tooltip_text = self.get_status_tooltip_text(filename)
                        Tooltip(status_label, tooltip_text)
    
    def clear_current_selection(self):
        """清除当前图像的选择"""
        if self.current_image_index < 0:
            return
        
        self.image_configs[self.current_image_index]["icon_states"].clear()
        
        # 更新UI显示
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
                
                if pos_x < 0 or pos_y < 0 or pos_x >= self.bg_width or pos_y >= self.bg_height:
                    print(f"警告：图标 {filename} 位置超出背景范围，已忽略。")
                    continue
                
                composite_img.paste(icon_img, (pos_x, pos_y), icon_img)
            except Exception as e:
                print(f"绘制失败: {filename}, {e}")
        
        # 保存预览图到当前配置
        self.image_configs[self.current_image_index]["preview"] = ImageTk.PhotoImage(composite_img)
        
        # 显示预览
        self.canvas.create_image(0, 0, image=self.image_configs[self.current_image_index]["preview"], anchor="nw")
        self.canvas.image = self.image_configs[self.current_image_index]["preview"]
    
    def save_single_image(self):
        """保存当前选中的单张图像"""
        if self.current_image_index < 0:
            messagebox.showwarning("警告", "没有可保存的图像！")
            return
        
        current_config = self.image_configs[self.current_image_index]
        if not current_config["icon_states"]:
            messagebox.showinfo("提示", "当前图像没有启用任何图标，无法保存！")
            return
        
        # 建议文件名使用图像名称
        suggested_name = f"{current_config['name']}.png"
        
        file_path = filedialog.asksaveasfilename(
            title="保存图像",
            defaultextension=".png",
            initialfile=suggested_name,
            filetypes=[("PNG 图像", "*.png"), ("JPEG 图像", "*.jpg"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            final_img = self._compose_image(current_config["icon_states"])
            final_img.save(file_path, "PNG" if file_path.lower().endswith('.png') else "JPEG")
            messagebox.showinfo("成功", f"图像已保存：\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{e}")
    
    def _compose_image(self, icon_states):
        """根据图标状态合成最终图像"""
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
        """生成包含所有图像配置的统一JSON文件（保留紧凑单行格式）"""
        if not self.image_configs:
            messagebox.showinfo("提示", "当前没有图像配置，无法生成配置文件。")
            return
        
        # 过滤掉没有启用图标的配置
        valid_configs = [cfg for cfg in self.image_configs if cfg["icon_states"]]
        
        if not valid_configs:
            messagebox.showinfo("提示", "所有图像配置都未启用任何图标，无法生成配置文件。")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="保存统一配置文件",
            defaultextension=".json",
            initialfile=f"ui_config_{self.current_platform}_all.json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # 构建输出数据：每个图像名称对应一个紧凑格式的JSON数组
            output_lines = ["{"]
            image_entries = []
            
            for config in valid_configs:
                image_name = config["name"]
                items = []
                
                for filename, state in config["icon_states"].items():
                    if filename not in self.config_data:
                        continue
                    
                    data = self.config_data[filename]
                    has_reuse = data.get("reuse", False) and state == "reuse"
                    
                    # 名称
                    name = data.get("reuse_name", "") if has_reuse else data.get("name", "")
                    if not name:
                        name = f"{data.get('name', '')}_2" if has_reuse else os.path.splitext(filename)[0]
                    
                    # 位置
                    pos_x = data["reuse_left"] if has_reuse else data["left"]
                    pos_y = data["reuse_top"] if has_reuse else data["top"]
                    
                    # 宽高
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
                    
                    # 构造单个项（紧凑格式）
                    item = {
                        "name": name,
                        "top_left": [pos_x, pos_y],
                        "bottom_right": [pos_x + width, pos_y + height]
                    }
                    # 使用紧凑格式序列化
                    item_str = json.dumps(item, ensure_ascii=False, separators=(',', ':'))
                    items.append(item_str)
                
                # 构建该图像的紧凑数组
                if items:
                    # 格式: "图像名称": [{...},{...}]
                    image_entry = f'  "{image_name}": [\n    ' + ',\n    '.join(items) + '\n  ]'
                    image_entries.append(image_entry)
            
            # 组合所有图像配置
            if image_entries:
                output_lines.append(',\n'.join(image_entries))
            
            output_lines.append("}")
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))
            
            messagebox.showinfo("成功", f"统一配置文件已生成：\n{file_path}\n共包含 {len(valid_configs)} 个图像配置。")
        except Exception as e:
            messagebox.showerror("错误", f"生成配置文件失败：\n{e}")
    
    def batch_export_images(self):
        """批量导出所有启用了图标的图像"""
        if not self.image_configs:
            messagebox.showinfo("提示", "当前没有图像配置，无法导出图像。")
            return
        
        # 过滤掉没有启用图标的配置
        valid_configs = [cfg for cfg in self.image_configs if cfg["icon_states"]]
        
        if not valid_configs:
            messagebox.showinfo("提示", "所有图像配置都未启用任何图标，无法导出图像。")
            return
        
        # 选择保存目录
        export_dir = filedialog.askdirectory(title="选择批量导出目录")
        if not export_dir:
            return
        
        try:
            success_count = 0
            failed_images = []
            
            for config in valid_configs:
                try:
                    # 清理文件名中的非法字符
                    safe_name = "".join(c for c in config["name"] if c not in r'\/:*?"<>|')
                    if not safe_name:
                        safe_name = f"image_{self.image_configs.index(config)}"
                    
                    file_path = os.path.join(export_dir, f"{safe_name}.png")
                    
                    # 合成图像
                    final_img = self._compose_image(config["icon_states"])
                    final_img.save(file_path, "PNG")
                    success_count += 1
                except Exception as e:
                    failed_images.append(f"{config['name']}: {str(e)}")
            
            # 显示结果
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
    app = ImageGeneratorApp(root)
    root.mainloop()