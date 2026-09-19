# -*- coding: utf-8 -*-
"""image_testing.image_gen_data —— 测试图生成的数据层（Mixin）

从 sample_image_generator.py 拆出，聚焦『读配置、找素材、导出结果』：
  · 测试用例 JSON 读取
  · 平台 / 背景 / 图标资源定位与加载
  · 生成测试图（单张、批量）与统一配置文件导出

设计：以 Mixin 提供能力，由 ImageGeneratorApp 组合；行为与拆分前一致。
界面装配与预览交互见 image_gen_preview.ImagePreviewMixin。
"""
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk



class ImageGenDataMixin:
    """测试图生成的数据读取与导出能力（由 ImageGeneratorApp 组合使用）。"""

    
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
            if state == "main":
                return "启用位置1（主位置）"
            elif state == "reuse":
                return "启用位置2（复用位置 1）"
            elif state == "reuse2":
                return "启用位置3（复用位置 2）"
            elif state == "reuse3":
                return "启用位置4（复用位置 3）"
            else:
                return "启用"
        else:
            return "启用"

    
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
                            # ---------------- 主位置匹配 ----------------
                            if data.get("name") == icon_name:
                                if (abs(top_left[0] - data["left"]) < 5 and
                                    abs(top_left[1] - data["top"]) < 5):
                                    img_cfg["icon_states"][filename] = (
                                        "main" if bool(data.get("reuse", 0)) else "enabled"
                                    )
                                    matched = True
                                    # 若主位置已经匹配成功，直接退出当前 filename 循环
                                    break
                            # ---------------- 复用位置 1 ----------------
                            if data.get("reuse", 0) >= 1:
                                if (abs(top_left[0] - data["reuse_left"]) < 5 and
                                    abs(top_left[1] - data["reuse_top"]) < 5):
                                    img_cfg["icon_states"][filename] = "reuse"
                                    matched = True
                                    break
                            # ---------------- 复用位置 2 ----------------
                            if data.get("reuse", 0) >= 2:
                                if (abs(top_left[0] - data.get("reuse_left_2", -9999)) < 5 and
                                    abs(top_left[1] - data.get("reuse_top_2", -9999)) < 5):
                                    img_cfg["icon_states"][filename] = "reuse2"
                                    matched = True
                                    break
                            # ---------------- 复用位置 3 ----------------
                            if data.get("reuse", 0) >= 3:
                                if (abs(top_left[0] - data.get("reuse_left_3", -9999)) < 5 and
                                    abs(top_left[1] - data.get("reuse_top_3", -9999)) < 5):
                                    img_cfg["icon_states"][filename] = "reuse3"
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

        # ---------- 校验图文 UI 必须有数值 ----------
        missing_values = []   # 用于收集缺失数值的项，结构为 (image_name, icon_display_name)
        for cfg in self.image_configs:                     # 遍历每张图像
            img_name = cfg["name"]
            values_dict = cfg.get("icon_values", {})
            for filename, state in cfg["icon_states"].items():
                if filename not in self.config_data:
                    continue
                data = self.config_data[filename]
                class_name = data.get("class_name", "")
                # 判断是否为图文 UI（非纯图片）
                is_only_image = not class_name.startswith("Text_Icon_")
                if not is_only_image:                     # 只在图文 UI 时检查
                    # 若对应的 value 为空或不存在，记录错误
                    val = values_dict.get(filename)
                    if not val or str(val).strip() == "":
                        missing_values.append((img_name, data.get("name", filename)))
        if missing_values:
            # 组装提示信息，只显示前几条以免弹窗过长
            preview = "\n".join(
                f'  图像 "{img}" 中的图文 UI "{icon}"' for img, icon in missing_values[:5]
            )
            more = f"\n... 等共 {len(missing_values)} 项缺失" if len(missing_values) > 5 else ""
            messagebox.showwarning(
                "数值缺失",
                f"检测到有图文 UI 没有输入数值，请先在 GUI 中为以下项填写数值：\n{preview}{more}"
            )
            return                                          # 中止后续写文件

        # ---------- 构造 JSON ----------
        try:
            output_parts = []
            # 平台信息
            output_parts.append(f'  "platform": "{self.current_platform}"')
            # 对每张图像进行遍历
            for img_idx, config in enumerate(self.image_configs):
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
                    # is_only_image 判断(是：纯图像，否：图文)
                    if class_name.startswith("Icon_"):
                        is_only_image = True
                    elif class_name.startswith("Text_Icon_"):
                        is_only_image = False
                    else:
                        is_only_image = True
                    # ----------------- 计算坐标 -----------------
                    if state == "main" or state == "enabled":
                        pos_x = data["left"]
                        pos_y = data["top"]
                    elif state == "reuse":
                        pos_x = data["reuse_left"]
                        pos_y = data["reuse_top"]
                    elif state == "reuse2":
                        pos_x = data["reuse_left_2"]
                        pos_y = data["reuse_top_2"]
                    elif state == "reuse3":
                        pos_x = data["reuse_left_3"]
                        pos_y = data["reuse_top_3"]
                    else:
                        continue
                    # ----------------- 宽高（若配置中缺失则实时读取） -----------------
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
                        "name": data.get("name", ""),
                        "class_name": class_name,
                        "is_only_image": is_only_image,
                        "ui_hash": data.get("hash"),
                        "top_left": [pos_x, pos_y],
                        "bottom_right": [pos_x + width, pos_y + height]
                    }
                    # 直接以字符串形式保存 value
                    val = values_dict.get(filename)
                    if val is not None and str(val).strip() != "":
                        item["value"] = str(val)  # 强制转为 str 类型
                    items.append(json.dumps(item, ensure_ascii=False, separators=(',', ':')))
                image_entry = f'  "{image_name}": [\n    ' + ',\n    '.join(items) + '\n  ]'
                output_parts.append(image_entry)
            # ---------- 合并并写文件 ----------
            output_content = ',\n'.join(output_parts)
            output_lines = ["{", output_content, "}"]
            # 判断是“生成”还是“更新”
            action = "更新" if os.path.exists(output_path) else "生成"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))
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
