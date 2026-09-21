"""can_gui.gui_config —— 配置读写与子窗口管理（Mixin）

从 can_send_receive_gui.py 拆出：
  · 平台分辨率等配置的加载与保存（XML / 本地配置）
  · 子窗口打开与关闭处理

设计：以 Mixin 提供能力，由 CANFDGUI 组合；行为与拆分前一致。
样式（字体）统一走 hudcore.ui.Theme，不再硬编码「微软雅黑」。
"""
from __future__ import annotations

import os
import re
import time
import tkinter as tk
import xml.etree.ElementTree as ET
from tkinter import messagebox, ttk

from hudcore.ui import Theme

# 判断是否被 import 调用
IS_STANDALONE = __name__ == "__main__"




def _device_config_path() -> str:
    """设备配置文件路径：data/ 优先，兼容旧的 can_data_tools/ 位置。

    原实现直接写 "can_data_tools/can_device_config.xml"（相对当前工作目录），
    换目录运行即失效；现改为基于项目根定位。
    """
    try:
        from hudcore.platform.paths import paths
        for c in (paths.data_dir / "can_device_config.xml",
                  paths.project_root / "can_data_tools" / "can_device_config.xml"):
            if c.is_file():
                return str(c)
        return str(paths.data_dir / "can_device_config.xml")
    except Exception:
        return "data/can_device_config.xml"


class ConfigMixin:
    """can_gui.gui_config —— 配置读写与子窗口管理（Mixin）（由 CANFDGUI 组合使用）。"""



    # --------------------- can设备管理子窗口 ---------------------
    def open_subwindow(self):
        """打开子窗口，限制只能打开一个"""
        if self.sub_window is not None and self.sub_window.winfo_exists():
            return  

        # 子窗口视为"已打开"：交给状态机置灰（规则表里 sub 的规则是"空闲即可用"）
        self._subwindow_open = True
        self._apply_ui_state()

        # 创建子窗口
        self.sub_window = tk.Toplevel(self.root)
        self.sub_window.title("设备管理窗口")
        self.sub_window.geometry("600x400")
        self.sub_window.resizable(False, False)

        # 设置关闭事件回调
        self.sub_window.protocol("WM_DELETE_WINDOW", self._on_subwindow_close)

        # 加载配置
        config_file = _device_config_path()
        config = self._local_load_config(config_file)  # 使用本地函数读取 XML

        # 设置默认值（若未读取到）
        device_default = config["device_type"] if config else "ZCAN_USBCANFD_200U"
        merge_default = config["merge_receive"] if config else 0
        transmit_type_value = config["transmit_type"] if config else 2
        chn_default = int(config["chn"]) if config and "chn" in config else 0

        # 映射数值 → 中文描述
        transmit_map = {0: "正常发送", 1: "单次发送", 2: "自发自收", 3: "单次自发自收"}
        transmit_default = transmit_map.get(transmit_type_value, "自发自收")

        # --------------------- UI 控件 ---------------------
        frame = tk.Frame(self.sub_window)
        frame.pack(pady=50, padx=60, fill="both", expand=True)

        # --- 1. 选择设备 ---
        tk.Label(frame, text="选择设备:", font=Theme.font_tuple(10)).grid(row=0, column=0, sticky='w', pady=10)
        self.device_var = tk.StringVar(value=device_default)
        device_combobox = ttk.Combobox(
            frame,
            textvariable=self.device_var,
            values=[
                "ZCAN_USBCANFD_100U",
                "ZCAN_USBCANFD_200U",
                "ZCAN_USBCANFD_400U",
                "ZCAN_USBCANFD_800U",
                "ZCAN_USBCANFD_MINI"
            ],
            state="readonly",
            width=30,
            font=Theme.font_tuple(10)
        )
        device_combobox.grid(row=0, column=1, padx=10, pady=10)

        # --- 2. 是否启用合并接收 ---
        tk.Label(frame, text="合并接收:", font=Theme.font_tuple(10)).grid(row=1, column=0, sticky='w', pady=10)

        # 映射：显示文本 → 实际值
        self.merge_display_to_value = {"不启用": 0, "启用": 1}
        self.merge_value_to_display = {0: "不启用", 1: "启用"}
        current_merge_display = self.merge_value_to_display.get(merge_default, "不启用")
        self.merge_display_var = tk.StringVar(value=current_merge_display)
        merge_combobox = ttk.Combobox(
            frame,
            textvariable=self.merge_display_var,
            values=["不启用", "启用"],
            state="readonly",
            width=30,
            font=Theme.font_tuple(10)
        )
        merge_combobox.grid(row=1, column=1, padx=10, pady=10)

        # --- 3. 发送类型 ---
        tk.Label(frame, text="发送类型:", font=Theme.font_tuple(10)).grid(row=2, column=0, sticky='w', pady=10)
        self.transmit_type_var = tk.StringVar(value=transmit_default)
        transmit_combobox = ttk.Combobox(
            frame,
            textvariable=self.transmit_type_var,
            values=["正常发送", "单次发送", "自发自收", "单次自发自收"],
            state="readonly",
            width=30,
            font=Theme.font_tuple(10)
        )
        transmit_combobox.grid(row=2, column=1, padx=10, pady=10)

        # --- 4. 选择通道 ---
        tk.Label(frame, text="选择通道:", font=Theme.font_tuple(10)).grid(row=3, column=0, sticky='w', pady=10)
        self.chn_var = tk.StringVar(value=str(chn_default))
        chn_combobox = ttk.Combobox(
            frame,
            textvariable=self.chn_var,
            values=["0", "1"],
            state="readonly",
            width=30,
            font=Theme.font_tuple(10)
        )
        chn_combobox.grid(row=3, column=1, padx=10, pady=10)

        # --- 保存按钮 ---
        save_btn = tk.Button(
            self.sub_window,
            text="保存配置",
            font=Theme.font_tuple(10),
            bg="#4A90E2",
            fg="white",
            command=lambda: self.save_config_to_xml(
                self.device_var.get(),
                self.merge_display_to_value[self.merge_display_var.get()], 
                self.transmit_type_var.get(),
                self.chn_var.get()  
            )
        )
        tk.Label(self.sub_window, justify="left", anchor="w",
                 **Theme.hint_label(text="说明：设备类型/通道号需与现场硬件一致；"
                                         "「自发自收」用于无总线时的自测。")
                 ).pack(fill="x", padx=20)
        save_btn.pack(pady=20)


    # 子窗口关闭时安全恢复按钮状态
    def _on_subwindow_close(self):
        """子窗口关闭时安全恢复按钮状态"""
        if self.sub_window is not None:
            try:
                self.sub_window.destroy()
            except tk.TclError:
                pass
            self.sub_window = None
        self._subwindow_open = False
        self._apply_ui_state()


    # 加载 XML 配置
    def _local_load_config(self, config_file):
        """本地实现：从 XML 文件读取配置，不依赖 can_control 模块"""
        if not os.path.exists(config_file):
            return None  # 文件不存在则返回 None，使用默认值

        try:
            tree = ET.parse(config_file)
            root = tree.getroot()
            config = {
                "device_type": root.find("device_type").text.strip() if root.find("device_type") is not None else "ZCAN_USBCANFD_200U",
                "merge_receive": int(root.find("merge_receive").text.strip()) if root.find("merge_receive") is not None else 0,
                "transmit_type": int(root.find("transmit_type").text.strip()) if root.find("transmit_type") is not None else 2,
                "chn": root.find("chn").text.strip() if root.find("chn") is not None else "0"
            }
            return config
        except Exception as e:
            print(f"警告：解析 XML 配置失败，使用默认值。错误：{e}")
            return None


    # 将用户选择保存到 XML 配置文件
    def save_config_to_xml(self, device_type, merge_receive, transmit_type_str, chn_str):
        """保存配置到 XML，保留格式和注释（安全 + 无正则反向引用问题）"""
        config_file = _device_config_path()
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        # 发送类型映射
        transmit_map = {
            "正常发送": 0,
            "单次发送": 1,
            "自发自收": 2,
            "单次自发自收": 3
        }
        transmit_type_value = transmit_map[transmit_type_str]
        chn_value = int(chn_str)

        # 默认模板
        default_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <!-- 
        CAN设备配置文件
        用于初始化周立功CANFD设备,以及提供相应设置项
    -->
    <canfd_config>
        <!-- 设备类型 -->
        <device_type>ZCAN_USBCANFD_200U</device_type>

        <!-- 是否启用合并接收：0 = 否，1 = 是 --> 
        <merge_receive>0</merge_receive>

        <!-- 发送类型：
             0 - 正常发送（总线发送，不等待确认）
             1 - 单次发送（总线发送，失败不再重试）
             2 - 自发自收（仅本地接收，不输出到总线）
             3 - 单次自发自收 -->
        <transmit_type>2</transmit_type>

        <!-- 通道号：0 或 1 -->
        <chn>0</chn>

    </canfd_config>
    '''

        # 安全读取当前内容
        current_content = default_content
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    current_content = f.read()
        except Exception as e:
            print(f"警告：读取配置文件失败，使用默认模板。错误：{e}")

        # 使用函数替换
        def replace_tag(content, tag, new_value):
            pattern = rf'(<{tag}\s*>)(.*?)(</{tag}>)'
            return re.sub(pattern, lambda m: m.group(1) + str(new_value) + m.group(3), content, flags=re.DOTALL)

        # 逐个替换
        current_content = replace_tag(current_content, 'device_type', device_type)
        current_content = replace_tag(current_content, 'merge_receive', merge_receive)
        current_content = replace_tag(current_content, 'transmit_type', transmit_type_value)
        current_content = replace_tag(current_content, 'chn', chn_value)

        # 保存文件
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(current_content)
            messagebox.showinfo("成功", "配置已保存")

            # 主动关闭并清理
            if self.sub_window is not None:
                self.sub_window.destroy()
            self.sub_window = None
            self._subwindow_open = False
            self._apply_ui_state()
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")

        # 保存完后，加一个简单 sleep 确保写入完成
        time.sleep(0.01)
