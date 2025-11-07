import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import can_control
import re
import time
import xml.etree.ElementTree as ET

class CANFDGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CANFD 设备控制")
        self.root.geometry("800x600")
        self.sub_window = None  # 用于跟踪子窗口是否存在

        # 用来保存初始化返回的句柄、通道列表、线程列表
        self.device_handle = None            # 设备句柄
        self.channel_handles = None       # 通道句柄
        self.receive_threads = None           # 接收线程列表        

        # 按键：设备初始化按键
        self.init_btn = tk.Button(
            root,
            text="初始化设备",
            font=("微软雅黑", 12),
            bg="#4A90E2",    # 蓝色背景
            fg="white",      # 白色文字
            activebackground="#357ABD",  # 按下时背景色
            command=self.start_init,
        )
        self.init_btn.grid(row=0, column=0, pady=5, padx=10, sticky='ew')

        # 按键：关闭设备按钮（初始不可用）
        self.close_btn = tk.Button(
            root,
            text="关闭设备",
            font=("微软雅黑", 12),
            bg="#D9534F",
            fg="white",
            activebackground="#C9302C",
            state=tk.DISABLED,          # 只有成功初始化后才可点
            command=self.start_close,
        )
        self.close_btn.grid(row=0, column=1, pady=5, padx=10, sticky='ew')

        # 按键：设备管理
        self.sub_btn = tk.Button(
            root,
            text="设备管理",
            font=("微软雅黑", 12),
            bg="#5CB85C",
            fg="white",
            activebackground="#4CAE4C",
            command=self.open_subwindow
        )
        self.sub_btn.grid(row=0, column=2, pady=5, padx=450, sticky='ew')

        # 按键：发送信号
        self.send_btn = tk.Button(
            root,
            text="发送信号",
            font=("微软雅黑", 12),
            bg="#F0AD4E",
            fg="white",
            activebackground="#EB983F",
            state=tk.DISABLED,
            command=self.start_send_signal
        )
        self.send_btn.grid(row=1, column=0, pady=5, padx=10, sticky='ew')

    # --------------------- CAN设备初始化 ---------------------
    def start_init(self):
        """点击“初始化设备”后，启动子线程执行真正的初始化逻辑"""
        self.init_btn.config(state=tk.DISABLED)   # 防止重复点击
        threading.Thread(target=self.init_device, daemon=True).start()

    def init_device(self):
        """调用初始化函数并保存返回值"""
        device_handle, channel_handles, receive_threads = can_control.Initialize_Canfd_Device(
            device_type=can_control.ZCAN_USBCANFD_200U,
            merge_receive=0,
        )
        # 保存返回值，后面关闭时会用到
        self.device_handle = device_handle
        self.channel_handles = channel_handles
        self.receive_threads = receive_threads

        # 回到主线程更新 UI
        self.root.after(0, self._post_init)

    def _post_init(self):
        """初始化结束后的 UI 更新"""
        if self.device_handle is None:
            # 初始化失败，恢复“初始化设备”按钮
            self.init_btn.config(state=tk.NORMAL)
            messagebox.showerror("错误", "CANFD 设备初始化失败！")
        else:
            # 成功后让“关闭设备”等按钮可用
            self.close_btn.config(state=tk.NORMAL)
            self.send_btn.config(state=tk.NORMAL)

    # --------------------- CAN设备关闭 ---------------------
    def start_close(self):
        """点击“关闭设备”后，启动子线程执行关闭逻辑"""
        self.close_btn.config(state=tk.DISABLED)   # 防止重复点击
        threading.Thread(target=self.close_device, daemon=True).start()

    def close_device(self):
        """调用关闭can设备函数,并在完成后恢复 UI 状态"""
        if self.device_handle is not None:
            can_control.Close_Canfd_Device(self.device_handle, self.channel_handles, self.receive_threads)

        # 关闭后清理内部状态
        self.device_handle = None
        self.channel_handles = None
        self.receive_threads = None

        # 回到主线程更新 UI
        self.root.after(0, self._post_close)

    def _post_close(self):
        """关闭结束后的 UI 更新"""
        self.init_btn.config(state=tk.NORMAL)       # 重新允许初始化
        self.close_btn.config(state=tk.DISABLED)    # 关闭按钮保持不可用
        self.send_btn.config(state=tk.DISABLED)     # 发送按键保持不可用

    
    #----------------------CAN信号发送---------------------------
    def start_send_signal(self):
        self.send_btn.config(state=tk.DISABLED)
        threading.Thread(target=self.send_can_signal, daemon=True).start()

    def send_can_signal(self):
        try:
            if self.device_handle is None or self.channel_handles is None:
                raise Exception("设备未初始化，无法发送信号！")
            device_handle = self.device_handle         
            channel_handles = self.channel_handles[0]
            can_control.Send_Can_Signal(
                device_handle=device_handle,
                chn_handle=channel_handles,
                chn=0,
                stdorext=0,
                id=0x12D,
                data=[0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00],
                msg_type='canfd',
                signal_type='Cycle',
                cycle_ms=50,
                index=1
            )
            print("can信号发送成功!") 
        except Exception as e:
            error_msg = str(e)
            print(f"can信号发送失败: {error_msg}") 
        finally:
            self.root.after(0, lambda: self.send_btn.config(state=tk.NORMAL))


    # --------------------- can设备管理子窗口 ---------------------
    def open_subwindow(self):
        """打开子窗口，限制只能打开一个"""
        if self.sub_window is not None and self.sub_window.winfo_exists():
            return  

        # 禁用按钮
        self.sub_btn.config(state=tk.DISABLED)

        # 创建子窗口
        self.sub_window = tk.Toplevel(self.root)
        self.sub_window.title("设备管理窗口")
        self.sub_window.geometry("600x400")
        self.sub_window.resizable(False, False)

        # 设置关闭事件回调
        self.sub_window.protocol("WM_DELETE_WINDOW", self._on_subwindow_close)

        # 加载配置
        config_file = "CanDataProcessing/can_device_config.xml"
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
        tk.Label(frame, text="选择设备:", font=("微软雅黑", 10)).grid(row=0, column=0, sticky='w', pady=10)
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
            font=("微软雅黑", 10)
        )
        device_combobox.grid(row=0, column=1, padx=10, pady=10)

        # --- 2. 是否启用合并接收 ---
        tk.Label(frame, text="合并接收:", font=("微软雅黑", 10)).grid(row=1, column=0, sticky='w', pady=10)

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
            font=("微软雅黑", 10)
        )
        merge_combobox.grid(row=1, column=1, padx=10, pady=10)

        # --- 3. 发送类型 ---
        tk.Label(frame, text="发送类型:", font=("微软雅黑", 10)).grid(row=2, column=0, sticky='w', pady=10)
        self.transmit_type_var = tk.StringVar(value=transmit_default)
        transmit_combobox = ttk.Combobox(
            frame,
            textvariable=self.transmit_type_var,
            values=["正常发送", "单次发送", "自发自收", "单次自发自收"],
            state="readonly",
            width=30,
            font=("微软雅黑", 10)
        )
        transmit_combobox.grid(row=2, column=1, padx=10, pady=10)

        # --- 4. 选择通道 ---
        tk.Label(frame, text="选择通道:", font=("微软雅黑", 10)).grid(row=3, column=0, sticky='w', pady=10)
        self.chn_var = tk.StringVar(value=str(chn_default))
        chn_combobox = ttk.Combobox(
            frame,
            textvariable=self.chn_var,
            values=["0", "1"],
            state="readonly",
            width=30,
            font=("微软雅黑", 10)
        )
        chn_combobox.grid(row=3, column=1, padx=10, pady=10)

        # --- 保存按钮 ---
        save_btn = tk.Button(
            self.sub_window,
            text="保存配置",
            font=("微软雅黑", 10),
            bg="#4A90E2",
            fg="white",
            command=lambda: self.save_config_to_xml(
                self.device_var.get(),
                self.merge_display_to_value[self.merge_display_var.get()], 
                self.transmit_type_var.get(),
                self.chn_var.get()  
            )
        )
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
        self.sub_btn.config(state=tk.NORMAL)

    # 加载 XML 配置
    def _local_load_config(self, config_file):
        """本地实现：从 XML 文件读取配置，不依赖 can_control 模块"""
        import os
        import xml.etree.ElementTree as ET

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
        config_file = "CanDataProcessing/can_device_config.xml"
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
            messagebox.showinfo("成功", f"配置已保存")

            # 主动关闭并清理
            if self.sub_window is not None:
                self.sub_window.destroy()
            self.sub_window = None
            self.sub_btn.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")

        # 保存完后，加一个简单 sleep 确保写入完成
        time.sleep(0.01)


if __name__ == "__main__":
    root = tk.Tk()
    app = CANFDGUI(root)
    root.mainloop()