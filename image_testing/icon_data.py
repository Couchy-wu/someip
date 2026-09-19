# -*- coding: utf-8 -*-
"""image_testing.icon_data —— 图标数据模型

从 icon_manager.py 拆出：纯数据结构（名称/尺寸/位置/复用信息）与 dict 互转，
**不含任何界面依赖**，因此可被算法、测试与批量脚本直接复用。
"""
import dataclasses  # noqa: F401  （保留给后续扩展；当前实现用普通类）


class IconData:
    # 为支持多重复用，扩展 __init__ 参数列表
    def __init__(self, name="", width=0, height=0, top=0, left=0,
                 reuse=False, reuse_name="", reuse_top=0, reuse_left=0,
                 reuse2=False, reuse_top_2=0, reuse_left_2=0,
                 reuse3=False, reuse_top_3=0, reuse_left_3=0,
                 class_name="", hash_val=None):
        self.name = name
        self.width = width
        self.height = height
        self.top = top
        self.left = left
        self.reuse = reuse
        self.reuse_name = reuse_name
        self.reuse_top = reuse_top
        self.reuse_left = reuse_left
        # 第二套复用坐标
        self.reuse2 = reuse2
        self.reuse_top_2 = reuse_top_2
        self.reuse_left_2 = reuse_left_2
        # 第三套复用坐标
        self.reuse3 = reuse3
        self.reuse_top_3 = reuse_top_3
        self.reuse_left_3 = reuse_left_3
        self.class_name = class_name  # UI 类名
        self.hash = hash_val if hash_val is not None else 0
    
    @classmethod
    def from_dict(cls, data):
        reuse_cnt = int(data.get("reuse", 0))          # 0‑3
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
            reuse2=data.get("reuse2", False),
            reuse_top_2=data.get("reuse_top_2", 0),
            reuse_left_2=data.get("reuse_left_2", 0),
            reuse3=data.get("reuse3", False), 
            reuse_top_3=data.get("reuse_top_3", 0),
            reuse_left_3=data.get("reuse_left_3", 0),
            class_name=data.get("class_name", ""),  # 从JSON读取类名
            hash_val=data.get("hash", None)
        )
    

    def to_dict(self):
        """导出为 JSON 字典"""
        # 统计当前对象实际启用了多少套复用
        reuse_cnt = (
            int(bool(self.reuse)) +
            int(bool(self.reuse2)) +
            int(bool(self.reuse3))
        )
        result = {
            "name": self.name,
            "class_name": self.class_name,
            "width": self.width,
            "height": self.height,
            "top": self.top,
            "left": self.left,
            "reuse": reuse_cnt,
        }
        if self.reuse:
            result["reuse_top"] = self.reuse_top
            result["reuse_left"] = self.reuse_left
        if self.reuse2:
            result["reuse_top_2"] = self.reuse_top_2
            result["reuse_left_2"] = self.reuse_left_2
        if self.reuse3:
            result["reuse_top_3"] = self.reuse_top_3
            result["reuse_left_3"] = self.reuse_left_3
        if self.hash:
            result["hash"] = self.hash
        return result
