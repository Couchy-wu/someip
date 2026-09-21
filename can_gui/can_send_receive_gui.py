import os
import tkinter as tk
from tkinter import messagebox, ttk
import threading
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

# ---- 拆分后的能力组合（见各模块说明） ----
from can_gui.gui_camera import CameraMixin              # noqa: E402
from can_gui.gui_config import ConfigMixin              # noqa: E402
from can_gui.gui_test_flow import TestFlowMixin         # noqa: E402


class CANFDGUI(CameraMixin, TestFlowMixin, ConfigMixin):
    """CAN 信号自动收发界面（主类）。

    界面构建见本模块 __init__；
    相机与图像处理 → gui_camera.CameraMixin
    测试流程与设备收发 → gui_test_flow.TestFlowMixin
    配置与子窗口 → gui_config.ConfigMixin
    """

    def __init__(self, root, selected_file=None):
        self.root = root
        self.root.title("CANFD 设备控制")
        self.root.geometry("1500x800")
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

        # ---------- 图标校验线程 ----------
        self._verification_queue = queue.Queue()          # 用于在每帧变换后传递图像
        self._stop_verification = threading.Event()       # 关闭 GUI 时用于停止校验线程
        self._verification_thread = threading.Thread(    # 启动独立校验线程
            target=self._verification_worker,
            daemon=True,
        )
        self._verification_thread.start()                # GUI 一启动即启动校验线程

        # ---------- 、保存最近一帧原始图像 ----------
        self.latest_frame = None                  # 、用于透视校正时取帧

        # 一些变量
        self.repeat_var = tk.StringVar(value="1")   # 用例重复检测次数
        self.rounds_var = tk.StringVar(value="1")   # 完整测试执行轮数

        # 用来保存初始化返回的句柄、通道列表、线程列表
        self.device_handle = None               # 设备句柄
        self.channel_handles = None             # 通道句柄
        self.receive_threads = None             # 接收线程列表       

        # ---------- 图像预处理 ----------
        # 在 GUI 中创建一次 ImageEnhancer 实例，以便在 “变换” 中复用
        from camera_tools.image_enhancement import ImageEnhancer
        self._enhancer = ImageEnhancer(enable_timing=False)    

        # 读取平台分辨率 JSON
        self.platform_resolutions = self._load_platform_resolutions()
        if self.platform_resolutions:
            first_platform = list(self.platform_resolutions.keys())[0]
            self.platform_var = tk.StringVar(value=first_platform)               # 当前平台
            self.selected_resolution = self.platform_resolutions[first_platform] # 当前分辨率 dict
        else:
            self.platform_var = tk.StringVar(value="")
            self.selected_resolution = None

        # GUI显示帧率控制
        self._gui_frame_interval = 0.1          # 0.2 = 200ms间隔 = 5 fps 
        self._last_gui_update_time = 0          # 上次GUI更新时间戳

        # ---------- 第一块视频显示：右上角摄像头显示区域 ----------
        # 用一个固定大小的 Label 充当画布（640×360）
        self.video_label = tk.Label(root, bg="black")
        self.video_label.grid(row=1, column=4, rowspan=5, padx=10, pady=5, sticky='e')
        root.grid_columnconfigure(4, weight=1)

        # 立即显示 “Camera is not open” 的占位图（避免首次出现纯黑屏）
        no_cam_img = self._make_no_camera_image(text="Camera is Not Open")
        self._no_cam_placeholder = ImageTk.PhotoImage(no_cam_img)
        self.video_label.configure(image=self._no_cam_placeholder)
        self.video_label.image = self._no_cam_placeholder   # 防止被 GC

        # 启动摄像头采集线程（始终运行，内部回调自行判断是否显示）
        self._camera_thread = threading.Thread(
            target=self._run_camera_viewer, daemon=True
        )
        self._camera_thread.start()

        # ---------- 第二块视频显示：变换相关 ----------
        self.transform_enable_var = tk.IntVar(value=1)          # 勾选框：是否开启变换，value=1为默认开启
        self.transform_option_var = tk.StringVar(value="变换A") # 下拉框当前选项

        # 视频显示
        # 先放一个黑屏占位图（同样 640×360）
        self.video_label2 = tk.Label(root, bg="black")
        self.video_label2.grid(row=6, column=4, rowspan=5, padx=10, pady=5, sticky='e')
        no_cam_img2 = self._make_no_camera_image(text="Not activated transformation")
        self._no_cam_placeholder2 = ImageTk.PhotoImage(no_cam_img2)
        self.video_label2.configure(image=self._no_cam_placeholder2)
        self.video_label2.image = self._no_cam_placeholder2


        # 图像测试勾选框状态
        self.image_test_var = tk.IntVar(value=1)   # 默认开关项 0 – 关闭， 1 – 开启
        # 勾选框，勾选即开启
        tk.Checkbutton(
            root,
            text="开启图像测试",
            variable=self.image_test_var,   # 绑定到上面声明的 IntVar
            onvalue=1,                     # 勾选时的取值
            offvalue=0,                    # 未勾选时的取值
            font=("微软雅黑", 10)
        ).grid(row=5, column=0, sticky='w', padx=5)

        # 图像采集模式开关
        self.image_capture_var = tk.IntVar(value=1)   #默认： 0 – 关闭，1 – 开启
        tk.Checkbutton(
            root,
            text="开启图像采集模式",
            variable=self.image_capture_var,
            onvalue=1,
            offvalue=0,
            font=("微软雅黑", 10)
        ).grid(row=5, column=2, sticky='w', padx=5, pady=5)   # 与其它勾选框保持布局
        self.root.bind("<Key>", self._on_key_press)   # 绑定键盘事件（全局捕获）


        # 记录图像是否需要旋转
        self.rotate_flag = False
        #  “图像旋转” 按键 
        self.rotate_btn = tk.Button(
            root,
            text="图像旋转",                 
            font=("微软雅黑", 12),
            bg="#5BC0DE",
            fg="white",
            activebackground="#31B0D5",
            command=self.toggle_rotate,           # 切换标记
        )
        # 放在已有按钮右侧（示例放在第 2 行第 2 列）
        self.rotate_btn.grid(row=2, column=2, pady=5, padx=10, sticky='ew')

        # 镜面反转 勾选状态
        self.mirror_enable_var = tk.IntVar(value=0)   # 0 – 关闭， 1 – 开启
        # 勾选框：是否开启镜面反转
        tk.Checkbutton(
            root,
            text="开启镜面反转",
            variable=self.mirror_enable_var,   # 绑定到新声明的 IntVar
            onvalue=1,                         # 勾选时的取值
            offvalue=0,                        # 未勾选时的取值
            font=("微软雅黑", 10)
        ).grid(row=5, column=1, pady=5, padx=10, sticky='w')

        # 曝光值下拉框
        self.exposure_var = tk.IntVar(value=-4)                     # 默认值
        # 下拉框，选项为 0、-1 …
        ttk.Label(root, text="曝光值:", font=("微软雅黑", 10)).grid(
            row=1, column=3, sticky='w', padx=5, pady=5)
        self.exposure_cb = ttk.Combobox(
            root,
            textvariable=self.exposure_var,
            values=[0, -1, -2, -3, -4, -5, -6, -7, -8, -9],
            state="readonly",
            width=8,
            font=("微软雅黑", 10)
        )
        self.exposure_cb.grid(row=1, column=4, sticky='w', padx=5, pady=5)
        # 绑定选择事件，实时更新摄像头曝光
        self.exposure_cb.bind("<<ComboboxSelected>>", self._on_exposure_change)

        # 平台选择下拉框（单选）
        ttk.Label(root, text="平台:", font=("微软雅黑", 10)).grid(
            row=0, column=3, sticky='w', padx=5, pady=5)
        self.platform_cb = ttk.Combobox(
            root,
            textvariable=self.platform_var,
            values=list(self.platform_resolutions.keys()),
            state="readonly",
            width=8,
            font=("微软雅黑", 10)
        )
        self.platform_cb.grid(row=0, column=4, sticky='w', padx=5, pady=5)
        self.platform_cb.bind("<<ComboboxSelected>>", self._on_platform_change)

        # ---------- 变换控制 ----------
        # 勾选框：是否启用变换
        tk.Checkbutton(
            root,
            text="开启图像变换",
            variable=self.transform_enable_var,
            onvalue=1,
            offvalue=0,
            font=("微软雅黑", 10)
        ).grid(row=6, column=0, pady=5, padx=10, sticky='w')

        # 下拉框：变换类型（A/B，后续可继续添加）
        ttk.Combobox(
            root,
            textvariable=self.transform_option_var,
            values=["变换A", "变换B", "变换C", "变换D"],
            state="readonly",
            width=12,
            font=("微软雅黑", 10)
        ).grid(row=6, column=1, pady=5, padx=10, sticky='w')

        # “透视变换校正” 按键（放在已有按钮的下面，保持布局一致）
        self.perspective_btn = tk.Button(
            root,
            text="透视变换校正",
            font=("微软雅黑", 12),
            bg="#3CC4A6", 
            fg="white",
            activebackground="#35D164",
            command=self.start_perspective_correction
        )
        self.perspective_btn.grid(row=3, column=2, pady=5, padx=10, sticky='ew')

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

        # 按键：检测设备（子进程探测；未插卡时底层驱动会段错误，不能在主进程里试）
        self.probe_btn = tk.Button(
            root,
            text="检测设备",
            font=("微软雅黑", 12),
            bg="#5BC0DE",    # 浅蓝
            fg="white",
            width=10,
            height=1,
            activebackground="#31B0D5",
            command=self.start_probe,
        )
        self.probe_btn.grid(row=0, column=3, pady=5, padx=10, sticky='ew')

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
        self.sub_btn.grid(row=1, column=2, pady=5, padx=10, sticky='ew')  # 修改列位置为3，靠右对齐
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
        self.stop_btn.grid(row=0, column=2, pady=5, padx=10, sticky='ew')


        # 工况显示区域
        self.state_label = tk.Label(
            root,
            text="当前工况: 等待",               # 初始显示
            font=("微软雅黑", 12),
            bg="#222222",
            fg="#00FF00",
            anchor="w",
            width=64,
        )
        self.state_label.grid(row=0, column=4, padx=10, pady=5, sticky='e')


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
