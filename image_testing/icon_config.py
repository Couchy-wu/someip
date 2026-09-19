# -*- coding: utf-8 -*-
"""image_testing.icon_config —— 图标配置读写与哈希计算（Mixin）

从 icon_manager.py 拆出，聚焦"配置持久化 + 图标哈希维护"：
  · 子目录扫描与配置文件路径推导
  · 配置读写（config.json）
  · 图标哈希计算与更新（配合 image_similarity 的 dHash）
  · 背景图就绪检查

设计：以 Mixin 提供能力，由 IconManagerApp 组合，行为与拆分前一致。
依赖约束：不引入新的界面逻辑；可依赖同包 image_similarity / icon_data。
"""
import hashlib
import json
import os
from PIL import Image   # 背景图尺寸读取
from tkinter import messagebox   # 默认图标/校验提示需要 messagebox

try:                                     # 包导入优先
    from .icon_data import IconData
    from .image_similarity import get_image_hash
except ImportError:                       # 脚本模式回退
    from icon_data import IconData
    from image_similarity import get_image_hash


def _ui_config_dir() -> str:
    """界面工具配置目录：data/UI_Config 优先，兼容旧的 image_testing/UI_Config。"""
    try:
        import hudcore.platform.paths as _p
        d = _p.paths.data_dir / "UI_Config"
        legacy = _p.paths.project_root / "image_testing" / "UI_Config"
        return str(legacy if (legacy.is_dir() and not d.is_dir()) else d)
    except Exception:
        return "data/UI_Config"


class IconConfigMixin:
    """图标配置读写与哈希计算（由 IconManagerApp 组合使用）。"""

    
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
        return os.path.join(_ui_config_dir(), config_name)
    
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

    # 计算并写入所有图像的 dHash 到 JSON 配置中
    def compute_and_update_hashes(self):
        """遍历当前平台文件夹，计算每张图像的 dHash 并写入 json"""
        # 1. 确认 json 已经生成
        if not os.path.exists(self.config_file):
            messagebox.showwarning("提示", "请先生成 json 配置文件！")
            return

        # 2. 逐图像计算哈希
        changed = False
        for filename in self.image_files:
            # 背景图也需要哈希
            img_path = os.path.join(self.resources_dir, filename)
            try:
                hash_val = get_image_hash(img_path)          # 调用公共接口
            except Exception as e:
                messagebox.showerror("错误", f"计算 {filename} 哈希失败：{e}")
                continue

            # 3. 若 config 中没有该条目则创建默认 IconData
            if filename not in self.config_data:
                self.config_data[filename] = IconData(
                    name=os.path.splitext(filename)[0],
                    width=0,
                    height=0,
                    top=0,
                    left=0,
                    class_name=""
                )
            # 4. 更新/新增 hash
            if getattr(self.config_data[filename], "hash", None) != hash_val:
                self.config_data[filename].hash = hash_val
                changed = True

        if changed:
            self.unsaved_changes = True
            self.update_thumbnail_highlights()   # （可选）刷新 UI 高亮
            messagebox.showinfo("完成", "所有图像的哈希已计算并写入配置（未保存）。")
        else:
            messagebox.showinfo("完成", "所有图像的哈希已是最新状态。")
