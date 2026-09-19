# -*- coding: utf-8 -*-
"""image_testing.image_gen_preview —— 测试图生成界面（Mixin）

从 sample_image_generator.py 拆出，聚焦『界面装配与预览交互』：
  · 主界面搭建、用例表格填充
  · 图标按钮加载与点击、选中态与颜色、滚轮与尺寸事件
  · 预览重绘、单张保存

设计：以 Mixin 提供能力，由 ImageGeneratorApp 组合；行为与拆分前一致。
"""
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

from image_testing.tooltip import Tooltip



class ImagePreviewMixin:
    """界面装配与预览交互（由 ImageGeneratorApp 组合使用）。"""

    
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

    
    def update_status_label(self, filename, label):
        """更新状态指示色块的颜色"""
        # 添加越界检查（修复错误关键）
        if self.current_image_index < 0 or self.current_image_index >= len(self.image_configs):
            color = self.status_colors[None]
        else:
            current_states = self.image_configs[self.current_image_index]["icon_states"]
            state = current_states.get(filename)
            config = self.config_data.get(filename, {})
            has_reuse = config.get("reuse", 0)
            if state is None:
                color = self.status_colors[None]
            elif has_reuse:
                # 多重复用映射
                if state == "main":
                    color = self.status_colors["main"]
                elif state == "reuse":
                    color = self.status_colors["reuse"]
                elif state == "reuse2":
                    color = self.status_colors["reuse2"]
                elif state == "reuse3":
                    color = self.status_colors["reuse3"]
                else:
                    color = self.status_colors[None]
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
        has_reuse = config.get("reuse", 0)
        # ---------- 状态切换 ----------
        if current_state is None:                         # 当前未启用 → 启用主位置
            current_states[filename] = "main" if has_reuse else "enabled"
            button.config(relief="sunken")
        else:
            if has_reuse:                                 # 有复用，需要更多轮转
                # 根据已有状态决定下一个状态
                if current_state == "main":
                    current_states[filename] = "reuse"    # 第1个复用位置
                    button.config(relief="sunken")
                elif current_state == "reuse":
                    if has_reuse >= 2:
                        current_states[filename] = "reuse2"   # 第2个复用位置
                    else:
                        current_states.pop(filename, None)    # 回到未启用
                        button.config(relief="raised")
                    button.config(relief="sunken")
                elif current_state == "reuse2":
                    if has_reuse >= 3:
                        current_states[filename] = "reuse3"   # 第3个复用位置
                        button.config(relief="sunken")
                    else:
                        current_states.pop(filename, None)    # 回到未启用
                        button.config(relief="raised")
                elif current_state == "reuse3":
                    # 最后一次点击恢复为未启用
                    current_states.pop(filename, None)
                    button.config(relief="raised")
                else:
                    # 防御性回退
                    current_states.pop(filename, None)
                    button.config(relief="raised")
            else:                                         # 没有复用，仅在 enabled 与未启用之间切换
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
                # 根据状态选择坐标
                if state == "main" or state == "enabled":
                    pos_x = self.config_data[filename]["left"]
                    pos_y = self.config_data[filename]["top"]
                elif state == "reuse":
                    pos_x = self.config_data[filename]["reuse_left"]
                    pos_y = self.config_data[filename]["reuse_top"]
                elif state == "reuse2":
                    pos_x = self.config_data[filename]["reuse_left_2"]
                    pos_y = self.config_data[filename]["reuse_top_2"]
                elif state == "reuse3":
                    pos_x = self.config_data[filename]["reuse_left_3"]
                    pos_y = self.config_data[filename]["reuse_top_3"]
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
                # 复用坐标选择
                if state == "main" or state == "enabled":
                    pos_x = self.config_data[filename]["left"]
                    pos_y = self.config_data[filename]["top"]
                elif state == "reuse":
                    pos_x = self.config_data[filename]["reuse_left"]
                    pos_y = self.config_data[filename]["reuse_top"]
                elif state == "reuse2":
                    pos_x = self.config_data[filename]["reuse_left_2"]
                    pos_y = self.config_data[filename]["reuse_top_2"]
                elif state == "reuse3":
                    pos_x = self.config_data[filename]["reuse_left_3"]
                    pos_y = self.config_data[filename]["reuse_top_3"]
                else:
                    continue
                composite_img.paste(icon_img, (pos_x, pos_y), icon_img)
            except Exception as e:
                print(f"绘制失败: {filename}, {e}")
        return composite_img
