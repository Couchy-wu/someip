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
    def __init__(self, root, selected_file=None):
        self.root = root
        self.root.title("CANFD 设备控制")
        self.root.geometry("500x300")
        self.sub_window = None  # 用于跟踪子窗口是否存在
        self.selected_file = selected_file  # 保存主窗口的 StringVar

        # 一些变量
        self.repeat_var = tk.StringVar(value="1")   # 用例重复检测次数

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
            width=10,
            height=1,
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
            width=10,
            height=1,
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
            width=10,
            height=1,
            command=self.open_subwindow
        )
        self.sub_btn.grid(row=0, column=3, pady=5, padx=10, sticky='e')  # 修改列位置为3，靠右对齐
        # 配置列权重，使第3列（设备管理所在列）吸收多余空间，实现右对齐
        root.grid_columnconfigure(3, weight=1)

        # 按键：ON档电
        self.send_btn = tk.Button(
            root,
            text="ON档电",
            font=("微软雅黑", 12),
            bg="#CEA022",    
            fg="white",
            activebackground="#8D8119",
            width=10,
            height=1,
            state=tk.DISABLED,
            command=self.start_send_on_signal
        )
        self.send_btn.grid(row=1, column=0, pady=5, padx=10, sticky='ew')

        # 新增：OFF档电
        self.off_btn = tk.Button(
            root,
            text="OFF档电",
            font=("微软雅黑", 12),
            bg="#CEA022",    
            fg="white",
            activebackground="#8D8119",
            width=10,
            height=1,
            state=tk.DISABLED,
            command=self.start_send_off_signal
        )
        self.off_btn.grid(row=1, column=1, pady=5, padx=10, sticky='ew')

        # 按键：开始测试
        self.test_btn = tk.Button(
            root,
            text="开始测试",
            font=("微软雅黑", 12),
            bg="#DB218E",
            fg="white",
            activebackground="#5A1154",
            width=10,
            height=1,
            state=tk.DISABLED,
            command=self.start_testing
        )
        self.test_btn.grid(row=2, column=0, pady=5, padx=10, sticky='ew')

        # 输入框：用例重复侧测试次数
        tk.Label(root, text="用例重复测试次数:", font=("微软雅黑", 10)).grid(row=3, column=0, sticky='w', padx=12, pady=5)
        self.repeat_entry = tk.Entry(
            root,
            textvariable=self.repeat_var,
            width=10,
            font=("微软雅黑", 10),
            state=tk.DISABLED  # 初始禁用，等待初始化完成再启用
        )
        self.repeat_entry.grid(row=3, column=1, sticky='w', padx=10, pady=5)

        # 为输入框绑定验证功能
        self.repeat_entry.configure(validate='key', validatecommand=(root.register(self._validate_positive_integer), '%P'))

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
            self.off_btn.config(state=tk.NORMAL)
            self.test_btn.config(state=tk.NORMAL)
            self._update_repeat_entry_state()  # 控制输入框

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
        self.send_btn.config(state=tk.DISABLED)     # ON 电禁用
        self.off_btn.config(state=tk.DISABLED)      # OFF电禁用
        self.test_btn.config(state=tk.DISABLED)     # 开始测试按键保持不可用
        self._update_repeat_entry_state()           # 自动禁用输入框

    #----------------------ON档电信号发送---------------------------
    def start_send_on_signal(self):
        self.send_btn.config(state=tk.DISABLED)
        threading.Thread(target=self.send_can_on_signal, daemon=True).start()

    def send_can_on_signal(self):
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
            print("ON档电信号发送成功!") 
        except Exception as e:
            error_msg = str(e)
            print(f"ON档电信号发送失败: {error_msg}") 
        finally:
            self.root.after(0, lambda: self.send_btn.config(state=tk.NORMAL))


    #----------------------OFF档电信号发送---------------------------
    def start_send_off_signal(self):
        self.off_btn.config(state=tk.DISABLED)
        threading.Thread(target=self.send_can_off_signal, daemon=True).start()

    def send_can_off_signal(self):
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
                data=[0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00],  # OFF数据
                msg_type='canfd',
                signal_type='Cycle',
                cycle_ms=50,
                index=1
            )
            print("OFF档电信号发送成功!") 
        except Exception as e:
            error_msg = str(e)
            print(f"OFF档电信号发送失败: {error_msg}") 
        finally:
            self.root.after(0, lambda: self.off_btn.config(state=tk.NORMAL))

    def start_testing(self):
        """启动自动化测试，调用 can_testcase_runner.py 中的逻辑"""
        self.test_btn.config(state=tk.DISABLED)  # 防止重复点击
        self.send_btn.config(state=tk.DISABLED)  # 禁用ON
        self.off_btn.config(state=tk.DISABLED)   # 禁用OFF
        self.repeat_entry.config(state=tk.DISABLED) # 禁用输入框
        threading.Thread(target=self.run_automation_test, daemon=True).start()

    def run_automation_test(self):
        """执行自动化测试主逻辑"""
        success = False
        try:
            from CanDataProcessing.can_testcase_runner import LogParser

            if not self.selected_file:
                raise ValueError("未传入测试用例选择器")

            selected_xlsx = self.selected_file.get()
            if not selected_xlsx or selected_xlsx == "无文件":
                raise ValueError("请先选择一个有效的测试用例文件")

            base_name = os.path.splitext(selected_xlsx)[0]
            log_filename = f"{base_name}_data.log"
            log_file_path = os.path.join("TestcaseCollection", log_filename)

            # 检查日志文件是否存在
            if not os.path.exists(log_file_path):
                raise FileNotFoundError(f"对应的日志文件未找到: {log_file_path}")

            # 获取重复次数
            try:
                repeat_count = int(self.repeat_var.get())
            except Exception:
                repeat_count = 1

            # 创建解析器并运行测试
            parser = LogParser(
                log_path=log_file_path,
                device_handle=self.device_handle,
                channel_handles=self.channel_handles,
                receive_threads=self.receive_threads,
                case_repeat_count=repeat_count
            )
            parser.run()
            success = True  # 标记成功

        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("测试错误", f"自动化测试执行失败：\n{msg}"))
        finally:
            self.root.after(0, lambda: self._post_test_finish(success))



    def _post_test_finish(self, success=False):
        """测试结束后的 UI 恢复，并弹出独立提示窗口"""
        # 恢复主界面按钮状态
        self.test_btn.config(state=tk.NORMAL)
        self.send_btn.config(state=tk.NORMAL)
        self.off_btn.config(state=tk.NORMAL)
        self._update_repeat_entry_state()
        # 成功完成才弹出提示
        if success:
            self.show_test_completed_window()

    def show_test_completed_window(self):
        """创建一个非模态的独立提示窗口，不阻塞主窗口"""
        # 创建 Toplevel 窗口
        notify_window = tk.Toplevel(self.root)
        notify_window.title("测试完成提醒")
        notify_window.geometry("400x200")
        notify_window.resizable(False, False)

        # 设置窗口图标（可选）
        # notify_window.iconbitmap("path/to/icon.ico")

        # 居中显示
        notify_window.transient(self.root)  # 置于主窗口上方
        notify_window.grab_set()            # 可选：点击其他地方不失去焦点（若想完全非模态可注释这行）
        notify_window.focus_set()

        # 提示内容
        container = tk.Frame(notify_window)
        container.pack(expand=True)

        tk.Label(
            container,
            text="测试已完成！",
            font=("微软雅黑", 12, "bold"),
            fg="#4A90E2"
        ).pack(pady=5)

        tk.Label(
            container,
            text="所有测试用例已执行完毕",
            font=("微软雅黑", 10)
        ).pack(pady=5)

        # # 可选：10秒后自动关闭
        # self.root.after(10000, lambda: self.destroy_window_safely(notify_window))

    def destroy_window_safely(self, window):
        """安全地关闭窗口，防止调用已销毁的窗口"""
        try:
            if window.winfo_exists():
                window.destroy()
        except tk.TclError:
            pass  # 窗口已被销毁，忽略错误

    def _validate_positive_integer(self, value):
        """验证输入是否为大于 0 的整数"""
        if value == "":
            return True  # 允许空（便于删除）
        try:
            val = int(value)
            return val > 0
        except ValueError:
            return False

    def _update_repeat_entry_state(self):
        """根据按钮状态决定是否允许编辑重复次数输入框"""
        init_btn_disabled = self.init_btn['state'] == tk.DISABLED
        test_btn_enabled = self.test_btn['state'] == tk.NORMAL

        if init_btn_disabled and test_btn_enabled:
            self.repeat_entry.config(state=tk.NORMAL)
        else:
            self.repeat_entry.config(state=tk.DISABLED)


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