# -*- coding: utf-8 -*-
"""image_testing.icon_thumbnail —— 缩略图条与高亮渲染（Mixin）

从 icon_manager.py 拆出，聚焦"缩略图列表的渲染与交互"：
  · 缩略图条构建、缩略图生成与高亮更新
  · 唯一高亮色分配
  · 背景图缩放、画布滚轮事件

设计：以 Mixin 提供能力，由 IconManagerApp 组合；依赖 Tkinter 与 Pillow。
"""
import random
from PIL import Image, ImageTk   # 缩略图渲染
import os   # 缩略图路径处理
import tkinter as tk
from tkinter import messagebox   # 缩略图异常提示

try:                                     # 包导入优先
    from .icon_data import IconData
except ImportError:                       # 脚本模式回退
    from icon_data import IconData


class IconThumbnailMixin:
    """缩略图条与高亮渲染（由 IconManagerApp 组合使用）。"""

    
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
        
        # 类名缺失或位置为 (0,0) 时均视为未配置
        if not data.class_name:
            return "red"
        if data.top == 0 and data.left == 0:
            return "red"
        
        # 复用次数对应的坐标若仍为 (0,0) 也视为未配置
        # 这里 data.reuse 已是整数 0‑3
        if data.reuse >= 1 and data.reuse_top == 0 and data.reuse_left == 0:
            return "red"
        if data.reuse >= 2 and data.reuse_top_2 == 0 and data.reuse_left_2 == 0:
            return "red"
        if data.reuse >= 3 and data.reuse_top_3 == 0 and data.reuse_left_3 == 0:
            return "red"
        
        # 同一类名出现多次时使用统一颜色
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
        import colorsys          # random 已在模块顶层导入

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
    
    def on_frame_configure(self, event):
        """更新滚动区域"""
        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))
    
    def on_mousewheel(self, event):
        """支持鼠标滚轮横向滚动"""
        self.thumb_canvas.xview_scroll(-1 * (event.delta // 120), "units")
    
    def on_shift_mousewheel(self, event):
        """支持Shift+滚轮快速滚动"""
        self.thumb_canvas.xview_scroll(-3 * (event.delta // 120), "units")
