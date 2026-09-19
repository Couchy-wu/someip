# -*- coding: utf-8 -*-
"""image_testing.icon_form —— 图标表单编辑与文件夹切换（Mixin）

从 icon_manager.py 拆出，聚焦"编辑一个图标条目"的交互逻辑：
  · 类名校验、复用字段开关
  · 保存当前表单（写回配置）
  · 子文件夹切换、未保存变更标记

设计：以 Mixin 提供能力，由 IconManagerApp 组合，行为与拆分前一致。
"""
import tkinter as tk
import os   # 路径处理
from tkinter import messagebox


class IconFormMixin:
    """图标表单编辑与文件夹切换（由 IconManagerApp 组合使用）。"""

    
    def validate_class_name(self, input_str):
        """验证UI类名：只允许英文、数字和下划线"""
        if not input_str:  # 允许为空
            return True
        # 检查每个字符是否为字母、数字或下划线
        return all(c.isalnum() or c == '_' for c in input_str) and input_str.isascii()
    
    def toggle_reuse_fields(self):
        """切换复用字段的显示/隐藏，并同步状态与变量"""
        # 控制第一个复用
        if self.reuse_var.get():
            self.reuse_top_entry.grid()
            self.reuse_left_entry.grid()
        else:
            self.reuse_top_entry.grid_remove()
            self.reuse_left_entry.grid_remove()
            # 主复用关闭时，强制关闭所有子复用并重置状态
            self.reuse2_var.set(False)
            self.reuse3_var.set(False)
            self.reuse2_check.grid_remove()
            self.reuse3_check.grid_remove()
            self.reuse_top_2_entry.grid_remove()
            self.reuse_left_2_entry.grid_remove()
            self.reuse_top_3_entry.grid_remove()
            self.reuse_left_3_entry.grid_remove()

        # 控制第二个复用：只有第一个启用才能启用第二个
        if self.reuse_var.get():
            self.reuse2_check.grid()  # 显示开关
            if self.reuse2_var.get():
                self.reuse_top_2_entry.grid()
                self.reuse_left_2_entry.grid()
            else:
                self.reuse_top_2_entry.grid_remove()
                self.reuse_left_2_entry.grid_remove()
        else:
            # 已在上面统一处理
            pass

        # 控制第三个复用：只有第二个启用才能启用第三个
        if self.reuse2_var.get():
            self.reuse3_check.grid()  # 显示开关
            if self.reuse3_var.get():
                self.reuse_top_3_entry.grid()
                self.reuse_left_3_entry.grid()
            else:
                self.reuse_top_3_entry.grid_remove()
                self.reuse_left_3_entry.grid_remove()
        else:
            self.reuse3_check.grid_remove()
            self.reuse_top_3_entry.grid_remove()
            self.reuse_left_3_entry.grid_remove()

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
        new_reuse_top = self.reuse_top_var.get() if has_reuse else 0
        new_reuse_left = self.reuse_left_var.get() if has_reuse else 0

        has_reuse2 = self.reuse2_var.get()
        new_reuse_top_2 = self.reuse_top_2_var.get() if has_reuse2 else 0
        new_reuse_left_2 = self.reuse_left_2_var.get() if has_reuse2 else 0

        has_reuse3 = self.reuse3_var.get()
        new_reuse_top_3 = self.reuse_top_3_var.get() if has_reuse3 else 0
        new_reuse_left_3 = self.reuse_left_3_var.get() if has_reuse3 else 0

        # 计算复用次数（0‑3），保存到 data.reuse
        reuse_cnt = int(has_reuse) + int(has_reuse2) + int(has_reuse3)
        
        # -------------------  名称唯一性校验（不再检查 reuse_name） -------------------
        for other_filename, other_data in self.config_data.items():
            if other_filename == filename:
                continue  # 跳过当前文件
            
            # 检查主名称冲突
            if new_name == other_data.name:
                messagebox.showwarning("警告", f"主名称 '{new_name}' 已存在于 '{other_filename}' 中！\n所有UI名称必须唯一。")
                return
        
            # 检查主名称与他人的复用名称冲突
            if other_data.reuse and new_name == other_data.reuse_name:
                messagebox.showwarning("警告", f"主名称 '{new_name}' 已作为复用名称存在于 '{other_filename}' 中！\n所有UI名称必须唯一。")
                return
        
        old_data = self.config_data[filename]
        # 检查是否有更改
        has_changes = (
            old_data.name != new_name or 
            old_data.class_name != new_class_name or      # 检查类名变化
            old_data.top != new_top or 
            old_data.left != new_left or
            old_data.width != new_width or
            old_data.height != new_height or
            old_data.reuse != reuse_cnt or
            old_data.reuse_top != new_reuse_top or
            old_data.reuse_left != new_reuse_left or
            old_data.reuse2 != has_reuse2 or
            old_data.reuse_top_2 != new_reuse_top_2 or
            old_data.reuse_left_2 != new_reuse_left_2 or
            old_data.reuse3 != has_reuse3 or
            old_data.reuse_top_3 != new_reuse_top_3 or
            old_data.reuse_left_3 != new_reuse_left_3
        )
        
        if has_changes:
            # 如果是background.png，且尺寸改变，则调整图片
            if filename == 'background.png' and (old_data.width != new_width or old_data.height != new_height):
                self.resize_background_image(new_width, new_height)
            
            self.config_data[filename].name = new_name
            self.config_data[filename].class_name = new_class_name      # 保存类名
            self.config_data[filename].top = new_top
            self.config_data[filename].left = new_left
            self.config_data[filename].width = new_width
            self.config_data[filename].height = new_height
            # 统一保存复用次数
            self.config_data[filename].reuse = reuse_cnt
            # 仍然保存每套坐标
            self.config_data[filename].reuse_top = new_reuse_top
            self.config_data[filename].reuse_left = new_reuse_left
            self.config_data[filename].reuse2 = has_reuse2
            self.config_data[filename].reuse_top_2 = new_reuse_top_2
            self.config_data[filename].reuse_left_2 = new_reuse_left_2
            self.config_data[filename].reuse3 = has_reuse3
            self.config_data[filename].reuse_top_3 = new_reuse_top_3
            self.config_data[filename].reuse_left_3 = new_reuse_left_3
            self.unsaved_changes = True
            self.update_thumbnail_highlights()
