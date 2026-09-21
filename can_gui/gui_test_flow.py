# -*- coding: utf-8 -*-
"""can_gui.gui_test_flow —— 测试流程编排与设备收发（Mixin）

从 can_send_receive_gui.py 拆出：
  · 设备初始化/关闭、子流程钩子
  · 信号开关发送（ON/OFF）
  · 自动化测试执行、状态文本与暂停/恢复、完成提示
  · 窗口关闭与清理

设计：以 Mixin 提供能力，由 CANFDGUI 组合；行为与拆分前一致。
依赖：can_core（设备收发）/ can_data_tools（用例解析）。
"""
import os
import tkinter as tk
from tkinter import messagebox, ttk
import threading
from hudcore import logging_setup

from can_core import device
import re
import time
import xml.etree.ElementTree as ET
from can_data_tools.testcase_runner import LogParser
from PIL import Image, ImageTk, ImageDraw, ImageFont
from camera_tools.camera_preview import CameraViewer, rotate_image_180, set_exposure
import cv2
from camera_tools.perspective_calibration import PerspectiveCalibrator
import tempfile, glob
import numpy as np
from camera_tools.error_image_detection import is_error_image
import datetime
import json
import queue
from image_testing.image_similarity import compare_with_precomputed_hash

# 判断是否被 import 调用
IS_STANDALONE = __name__ == "__main__"



class TestFlowMixin:
    """can_gui.gui_test_flow —— 测试流程编排与设备收发（Mixin）（由 CANFDGUI 组合使用）。"""



    # --------------------- CAN设备初始化 ---------------------
    def start_init(self):
        """点击“初始化设备”后，启动子线程执行真正的初始化逻辑"""
        self.init_btn.config(state=tk.DISABLED)   # 防止重复点击
        threading.Thread(target=self.init_device, daemon=True).start()


    def init_device(self):
        """调用初始化函数并保存返回值

        先做**子进程探测**：Linux 上未插卡时底层 VCI 驱动会段错误（SIGSEGV），
        在主进程里直接 OpenDevice 会把整个上位机带走；探测失败则按"初始化失败"处理。
        """
        try:
            from can_core import probe_can_device
            probe = probe_can_device()
            if not probe.available:
                logging_setup.error("candata", probe.describe())
                print(f"[CAN] {probe.describe()}")            # 同步到界面日志
                self.device_handle = None
                self.channel_handles = None
                self.receive_threads = None
                self.root.after(0, self._post_init)
                return
        except Exception as exc:                              # noqa: BLE001 - 探测异常也按失败处理
            logging_setup.warning("candata", f"设备探测异常，跳过预检：{exc}")

        device_handle, channel_handles, receive_threads = device.Initialize_Canfd_Device(
            device_type=device.ZCAN_USBCANFD_200U,
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
            device.Close_Canfd_Device(self.device_handle, self.channel_handles, self.receive_threads)

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
            device.Send_Can_Signal(
                device_handle=device_handle,
                chn_handle=channel_handles,
                chn=0,
                stdorext=0,
                id=0x12D,
                data=[0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00],
                msg_type='canfd',
                signal_type='Cycle',
                cycle_ms=50,
                index=0
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
            device.Send_Can_Signal(
                device_handle=device_handle,
                chn_handle=channel_handles,
                chn=0,
                stdorext=0,
                id=0x12D,
                data=[0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00],  # OFF数据
                msg_type='canfd',
                signal_type='Cycle',
                cycle_ms=50,
                index=0
            )
            print("OFF档电信号发送成功!") 
        except Exception as e:
            error_msg = str(e)
            print(f"OFF档电信号发送失败: {error_msg}") 
        finally:
            self.root.after(0, lambda: self.off_btn.config(state=tk.NORMAL))


    def start_testing(self):
        """启动自动化测试，调用 testcase_runner.py 中的逻辑"""
        self.test_btn.config(state=tk.DISABLED)  # 防止重复点击
        self.send_btn.config(state=tk.DISABLED)  # 禁用ON
        self.off_btn.config(state=tk.DISABLED)   # 禁用OFF
        self.repeat_entry.config(state=tk.DISABLED) # 禁用用例重复测试次数的输入框
        self.rounds_entry.config(state=tk.DISABLED)  # 禁用完整测试轮数的输入框
        threading.Thread(target=self.run_automation_test, daemon=True).start()


    def run_automation_test(self):
        """执行自动化测试主逻辑"""
        success = False
        try:
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

            # 获取重复测试次数（每个用例内部重复）
            try:
                repeat_count = int(self.repeat_var.get())
            except Exception:
                repeat_count = 1

            # 获取完整测试轮数（整个流程执行几轮）
            try:
                rounds_count = int(self.rounds_var.get())
            except Exception:
                rounds_count = 1

            # 创建解析器并运行测试
            self.parser = LogParser(
                log_path=log_file_path,
                device_handle=self.device_handle,
                channel_handles=self.channel_handles,
                receive_threads=self.receive_threads,
                case_repeat_count=repeat_count,
                total_test_rounds=rounds_count
            )

            # 把 GUI 的截图方法封装为在主线程执行的回调
            self.parser.screenshot_callback = lambda: self.root.after(0, self._save_captured_image)
            
            # 注册状态回调，使 GUI 实时显示当前工况 和 用例编号
            self.parser.set_state_callback(
                lambda s: self.root.after(
                    0,
                    # 读取当前 parser 的 case 编号（在没有用例时为 None）
                    lambda txt=s, cid=getattr(self.parser, "current_case_id", None):
                        self.state_label.config(
                            text=self._format_state_text(txt, cid)
                        )
                )
            )
            # 直接在当前线程（后台线程）运行解析器
            self.parser.run()
            success = True  # 标记成功

        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("测试错误", f"自动化测试执行失败：\n{msg}"))
        finally:
            self.root.after(0, lambda: self._post_test_finish(success))


    def _format_state_text(self, state: str, case_id: str) -> str:
        """
        根据当前工况 `state` 和正在执行的用例编号 `case_id` 生成展示文字。
        - 当状态为 “等待” 时，只显示 “等待”；
        - 其它状态下在前面加上用例编号，格式如 “xx1, 执行动作”。
        """
        if state == "等待":
            return f"当前工况：{state}"
        # 当 case_id 为空或为 None 时，仍只显示状态（防止首次无用例时报错）
        prefix = f"{case_id}, " if case_id else ""
        return f"当前工况：{prefix} {state}"



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

        # 防闪烁居中
        notify_window.withdraw()  # 1. 创建时隐藏窗口
        notify_window.update_idletasks()  # 2. 强制更新布局，获取真实尺寸

        # 计算居中位置
        window_width = notify_window.winfo_width()
        window_height = notify_window.winfo_height()
        screen_width = notify_window.winfo_screenwidth()
        screen_height = notify_window.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        notify_window.geometry(f"400x200+{x}+{y}")  # 3. 设置尺寸 + 位置
        notify_window.deiconify()  # 4. 显示窗口（此时已位于中央）
        notify_window.focus_force()  # 强制聚焦（可选）

        # 保持原有行为
        notify_window.transient(self.root)  # 置于主窗口上方
        notify_window.grab_set()  # 可选：模态行为（点击其他窗口不响应）

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
        """根据按钮状态决定是否允许编辑重复次数和完整轮数输入框"""
        init_btn_disabled = self.init_btn['state'] == tk.DISABLED
        test_btn_enabled = self.test_btn['state'] == tk.NORMAL

        if init_btn_disabled and test_btn_enabled:
            self.repeat_entry.config(state=tk.NORMAL)
            self.rounds_entry.config(state=tk.NORMAL)
        else:
            self.repeat_entry.config(state=tk.DISABLED)
            self.rounds_entry.config(state=tk.DISABLED)


    def toggle_pause_resume(self):
        """切换暂停/继续测试状态，完全基于 _pause_event 当前状态判断，不依赖额外标志"""
        if not hasattr(self, 'parser') or self.parser is None:
            return
    
        # 核心判断：使用已存在的 _pause_event.is_set() 状态
        if self.parser._pause_event.is_set():
            # 当前正在运行 → 执行暂停
            self.parser.pause_test()
            self.toggle_pause_resume_btn.config(text="继续测试")
        else:
            # 当前已暂停（_pause_event 为 clear）→ 执行继续
            self.parser.resume_test()
            self.toggle_pause_resume_btn.config(text="暂停测试")



    def stop_testing(self):
        """终止测试"""
        if hasattr(self, 'parser') and self.parser is not None:
            self.parser.close_test()
        # 无论是否存在 parser，都尝试恢复 UI
        self._post_test_finish(success=False)


    def on_closing(self):
        """
        安全关闭主窗口的统一入口。

        主要职责：
        1 防止在 CAN 设备仍未关闭的情况下退出程序；
        2 正常结束摄像头采集线程，防止 after 回调在窗口销毁后继续执行；
        3 取消所有已安排的 `after` 回调（包括原来的 video_label 和 video_label2）
        4 终止实时工况刷新线程
        5 最终销毁根窗口。
        """
        # 检查 CAN 设备是否已经关闭
        if self.close_btn.winfo_exists() and str(self.close_btn['state']) == 'normal':
            import tkinter.messagebox as messagebox
            messagebox.showwarning(
                "无法退出",
                "请先点击【关闭设备】按钮释放CAN资源。",
                parent=self.root
            )
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(0, lambda: self.root.attributes("-topmost", False))
            return

        # 让摄像头线程自行退出，标记回调函数不再处理新帧
        self._stop_camera_thread = True

        # 停止图标校验线程
        self._stop_verification.set()
        if self._verification_thread and self._verification_thread.is_alive():
            self._verification_thread.join(timeout=2)

        # 取消所有待处理的 after 调用（使用循环清理）
        for attr in ['_after_id', '_after_id2']:
            if hasattr(self, attr):
                aid = getattr(self, attr)
                if aid:
                    try:
                        self.root.after_cancel(aid)
                    except:
                        pass
                    setattr(self, attr, None)

        # 若已经创建了 CameraViewer 实例，调用它的 stop()
        if hasattr(self, "_camera_viewer") and self._camera_viewer is not None:
            try:
                self._camera_viewer.stop()
            except Exception as e:
                print(f"[WARN] 停止 CameraViewer 时异常: {e}")

        # 取消可能已经排好的 after 回调
        for aid in (getattr(self, "_after_id", None),
                    getattr(self, "_after_id2", None)):
            if aid:
                try:
                    self.root.after_cancel(aid)
                except Exception:
                    # 有可能已经执行完或被别处取消，直接忽略
                    pass
        self._after_id  = None
        self._after_id2 = None

        # 终止实时工况刷新
        if hasattr(self, "parser") and self.parser:
            # 移除回调，防止在窗口销毁后仍尝试更新 UI
            self.parser.set_state_callback(None)  

        # 等待摄像头子线程自行结束（最多 1 秒）
        if hasattr(self, "_camera_thread") and self._camera_thread.is_alive():
            self._camera_thread.join(timeout=1.0)

        # 最后销毁窗口
        self.root.destroy()
