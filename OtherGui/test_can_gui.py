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
from CanDataProcessing.can_testcase_runner import LogParser
from PIL import Image, ImageTk
from CameraUtils.camera_viewer import CameraViewer


# 判断是否被 import 调用
IS_STANDALONE = __name__ == "__main__"

class CANFDGUI:
    def __init__(self, root, selected_file=None):
        self.root = root
        self.root.title("CANFD 设备控制")
        self.root.geometry("1200x800")
        self.sub_window = None  # 用于跟踪子窗口是否存在
        
        # === 修改：安全获取 selected_file ===
        if selected_file is None:
            # 独立运行时自己创建
            self.selected_file = tk.StringVar(value="无文件")
        else:
            # 被 main.py 调用时，使用传入的 StringVar
            self.selected_file = selected_file

        # ---------- 线程控制 ----------
        self._stop_camera_thread = False          # 用来在关闭窗口时让摄像头回调提前退出
        self._after_id = None                     # 用来保存 after 的 id

        # 一些变量
        self.repeat_var = tk.StringVar(value="1")   # 用例重复检测次数
        self.rounds_var = tk.StringVar(value="1")   # 完整测试执行轮数

        # 用来保存初始化返回的句柄、通道列表、线程列表
        self.device_handle = None               # 设备句柄
        self.channel_handles = None             # 通道句柄
        self.receive_threads = None             # 接收线程列表        

        # ---------- 右上角摄像头显示区域 ----------
        # 用一个固定大小的 Label 充当画布（640×360）
        self.video_label = tk.Label(root, bg="black")
        self.video_label.grid(row=0, column=4, rowspan=5, padx=10, pady=5, sticky='e')
        root.grid_columnconfigure(4, weight=1)

        # 预先准备一张黑色占位图（640×360）
        self._black_placeholder = ImageTk.PhotoImage(
            Image.new('RGB', (640, 360), (0, 0, 0))
        )
        self.video_label.configure(image=self._black_placeholder)
        self.video_label.image = self._black_placeholder   # 防止被 GC

        # 启动摄像头采集线程（始终运行，内部回调自行判断是否显示）
        self._camera_thread = threading.Thread(
            target=self._run_camera_viewer, daemon=True
        )
        self._camera_thread.start()


        # 图像测试勾选框状态
        self.image_test_var = tk.IntVar(value=0)   # 默认开关项 0 – 关闭， 1 – 开启

        # 是否开启图像测试（勾选框）
        # 文字说明
        tk.Label(root, text="是否开启图像测试:", font=("微软雅黑", 10)).grid(
            row=5, column=0, sticky='w', padx=12, pady=5)

        # 勾选框，勾选即开启
        tk.Checkbutton(
            root,
            text="开启",
            variable=self.image_test_var,   # 绑定到上面声明的 IntVar
            onvalue=1,                     # 勾选时的取值
            offvalue=0,                    # 未勾选时的取值
            font=("微软雅黑", 10)
        ).grid(row=5, column=1, sticky='w', padx=5)


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
        # self.sub_btn.grid(row=0, column=4, pady=5, padx=10, sticky='e')  # 修改列位置为3，靠右对齐
        self.sub_btn.grid(row=1, column=3, pady=5, padx=10, sticky='ew')  # 修改列位置为3，靠右对齐
        # 配置列权重，使（设备管理所在列）吸收多余空间，实现右对齐
        # root.grid_columnconfigure(4, weight=1)

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

        # 按键：暂停/继续测试（合并按钮）
        self.toggle_pause_resume_btn = tk.Button(
            root,
            text="暂停测试",
            font=("微软雅黑", 12),
            bg="#F0AD4E",
            fg="white",
            activebackground="#EB983A",
            width=10,
            height=1,
            command=self.toggle_pause_resume
        )
        self.toggle_pause_resume_btn.grid(row=2, column=1, pady=5, padx=10, sticky='ew')

        # 按键：终止测试
        self.stop_btn = tk.Button(
            root,
            text="强制终止测试",
            font=("微软雅黑", 12),
            bg="#D9534F",
            fg="white",
            activebackground="#C9302C",
            width=10,
            height=1,
            command=self.stop_testing
        )
        self.stop_btn.grid(row=0, column=3, pady=5, padx=10, sticky='ew')


        # 输入框：用例重复测试次数
        tk.Label(root, text="用例重复测试次数:", font=("微软雅黑", 10)).grid(row=3, column=0, sticky='w', padx=12, pady=5)
        self.repeat_entry = tk.Entry(
            root,
            textvariable=self.repeat_var,
            width=10,
            font=("微软雅黑", 10),
            state=tk.DISABLED  # 初始禁用，等待初始化完成再启用
        )
        self.repeat_entry.grid(row=3, column=1, sticky='w', padx=10, pady=5)
        # 为输入框绑定验证功能（只允许大于0的整数）
        self.repeat_entry.configure(validate='key', validatecommand=(root.register(self._validate_positive_integer), '%P'))

        # 输入框：用例完整测试轮数
        tk.Label(root, text="用例完整测试轮数:", font=("微软雅黑", 10)).grid(row=4, column=0, sticky='w', padx=12, pady=5)
        self.rounds_entry = tk.Entry(
            root,
            textvariable=self.rounds_var,
            width=10,
            font=("微软雅黑", 10),
            state=tk.DISABLED  # 初始禁用，等待初始化完成
        )
        self.rounds_entry.grid(row=4, column=1, sticky='w', padx=10, pady=5)
        # 为新输入框绑定验证功能（只允许大于0的整数）
        self.rounds_entry.configure(validate='key', validatecommand=(root.register(self._validate_positive_integer), '%P'))

        # 拦截窗口关闭事件：必须先关闭设备
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --------------------- 摄像头线程入口 ---------------------
    def _run_camera_viewer(self):
        """
        在子线程中启动 CameraViewer（而不是直接调用 camera_viewer.main）。
        CameraViewer 会在内部循环读取摄像头并通过回调把每帧 RGB 送进来。
        当窗口关闭时，外部会调用 self._camera_viewer.stop() 来终止循环。
        """
        try:
            # 创建并启动可自行停止的摄像头实例
            self._camera_viewer = CameraViewer(display_callback=self._camera_frame_callback)
            self._camera_viewer.start()          # 在后台 daemon 线程里运行
            while not getattr(self, "_stop_camera_thread", False):
                time.sleep(0.1)
        except Exception as e:
            # 若摄像头初始化失败，保持黑屏并打印错误
            print(f"[WARN] CameraViewer 运行异常: {e}")

    def _camera_frame_callback(self, frame_rgb):
        """
        camera_viewer 通过此回调把每帧 RGB 的 numpy 数组送进来。
        - 当 “是否开启图像测试” 为 1 时显示真实画面；
        - 否则用全黑图像覆盖。
        """
        # ----------- 若窗口已请求关闭，则直接返回 ----------
        if getattr(self, "_stop_camera_thread", False):
            return
        try:
            if self.image_test_var.get() == 1:
                # 正常显示摄像头画面
                img = Image.fromarray(frame_rgb)
            else:
                # 开关关闭 → 用黑屏占位
                img = Image.new('RGB', (frame_rgb.shape[1], frame_rgb.shape[0]), (0, 0, 0))
            # 缩放到 640×360（对应 OUTPUT_WIDTH / OUTPUT_HEIGHT）
            img = img.resize((640, 360), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            # 在主线程中更新 UI（Tk 只能在主线程操作）
            self._after_id = self.root.after(0, self._update_video_label, photo)
        except Exception as err:
            print(f"[ERROR] 摄像头回调异常: {err}")

    def _update_video_label(self, photo_image):
        """把生成好的 PhotoImage 放到 video_label 上（只能在主线程调用）"""
        # ---------- 如果标签已经被销毁，直接返回 ----------
        if not getattr(self, "video_label", None) or not self.video_label.winfo_exists():
            return
        try:
            self.video_label.configure(image=photo_image)
            self.video_label.image = photo_image   # 防止被垃圾回收
        except tk.TclError:
            # 可能在窗口销毁的瞬间被调用，安全忽略
            pass

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
                index=0
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
            self.parser.run()
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
        安全关闭检查：只有当“关闭设备”按钮不可用时才允许退出。
        这里会显式结束摄像头线程，防止 after 回调触发错误或卡顿。
        """
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
        # 若已经创建了 CameraViewer 实例，调用它的 stop()
        if hasattr(self, "_camera_viewer") and self._camera_viewer is not None:
            try:
                self._camera_viewer.stop()
            except Exception as e:
                print(f"[WARN] 停止 CameraViewer 时异常: {e}")
        # 取消可能已经排好的 after 回调
        if getattr(self, "_after_id", None):
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        # 等待摄像头子线程自行结束（最多 1 秒）
        if hasattr(self, "_camera_thread") and self._camera_thread.is_alive():
            self._camera_thread.join(timeout=1.0)
        # 最后销毁窗口
        self.root.destroy()


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