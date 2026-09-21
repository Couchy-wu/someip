# -*- coding: utf-8 -*-
"""can_gui.gui_camera —— 相机取流、图像处理与透视标定（Mixin）

从 can_send_receive_gui.py 拆出（原 CANFDGUI 单类 1611 行）：
  · 相机取流与画面刷新（含旋转、曝光、按键快捷键）
  · 抓拍保存、无相机占位图、临时文件清理
  · 平台分辨率读取与切换
  · 透视变换校正（手动/自动）、错误图检测与校验工作线程

设计：以 Mixin 提供能力，由 CANFDGUI 组合；行为与拆分前一致。
依赖：Tkinter / PIL / OpenCV / camera_tools（预览、标定、错误图检测）/ image_testing（相似度）。
"""
import datetime
import glob
import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

from camera_tools.camera_preview import CameraViewer, rotate_image_180, set_exposure
from camera_tools.error_image_detection import is_error_image
from camera_tools.perspective_calibration import PerspectiveCalibrator
from image_testing.image_similarity import compare_with_precomputed_hash

# 判断是否被 import 调用
IS_STANDALONE = __name__ == "__main__"



class CameraMixin:
    """can_gui.gui_camera —— 相机取流、图像处理与透视标定（Mixin）（由 CANFDGUI 组合使用）。"""


    # --------------------- 摄像头线程入口 ---------------------
    def _run_camera_viewer(self):
        """
        在子线程中启动 CameraViewer（而不是直接调用 camera_preview.main）。
        CameraViewer 会在内部循环读取摄像头并通过回调把每帧 RGB 送进来。
        当窗口关闭时，外部会调用 self._camera_viewer.stop() 来终止循环。
        """
        try:
            # 创建并启动可自行停止的摄像头实例
            self._camera_viewer = CameraViewer(
                display_callback=self._camera_frame_callback,
                is_standalone=False,
                exposure=-4,               # 曝光值
                draw_timestamp = False,    # 绘制时间戳文字
                enable_timestamp = True,   # 启用时间戳功能
                simulate_error=False,      # 是否开启异常帧模拟
                error_probability=0.01,    # 异常帧出现概率    
                target_fps=30              # 摄像头目标帧率             
                )

            self._camera_viewer.start()          # 在后台 daemon 线程里运行
            while not getattr(self, "_stop_camera_thread", False):
                time.sleep(0.1)
        except Exception as e:
            # 若摄像头初始化失败，保持黑屏并打印错误
            print(f"[WARN] CameraViewer 运行异常: {e}")


    # 切换是否在显示前旋转图像的标记。
    def toggle_rotate(self):
        self.rotate_flag = not self.rotate_flag


    def _camera_frame_callback(self, frame_rgb, timestamp=None):
        """
        camera_preview 通过此回调把每帧 RGB 的 numpy 数组送进来。
        1️⃣ 首先根据 “是否开启图像测试” 与 “图像旋转，镜面翻转” 等标记，生成 **第一块**画面；
        2️⃣ 再把 **已经旋转（如果有）的同一帧** 交给变换函数，生成 **第二块**画面；
        3️⃣ 两块画面统一缩放、转成 PhotoImage、交给主线程 via after。
        """
        # ----------- 若窗口已请求关闭，则直接返回 ----------
        if getattr(self, "_stop_camera_thread", False):
            return
        # 先把原始（未做任何处理的）帧保存下来，以便后续 “透视变换校正” 使用
        self.latest_frame = frame_rgb.copy()   # 保留最新的原始帧

        try:
            # 1) 显示摄像头画面（并可选 180° 旋转）
            if self.image_test_var.get() == 1:
                img_arr = frame_rgb             # 读取原始帧
                # 180° 旋转（如果打开）
                if self.rotate_flag:                     
                    img_arr = rotate_image_180(img_arr) 
                # 镜面水平翻转（如果打开）
                if self.mirror_enable_var.get() == 1: 
                    img_arr = img_arr[:, ::-1, :] 
                # 转为 Pillow Image                    
                img = Image.fromarray(img_arr)
            else: 
                img = self._make_no_camera_image(text="Camera is Not Open")     # 开关关闭 → 用黑屏 + 文字提示 占位，用已封装的文字图
                img_arr = None                               # 下面的变换不使用
                
            # 2) 变换后的画面
            if (self.transform_enable_var.get() == 1 and self.image_test_var.get() == 1 and img_arr is not None):
                # 这里调用占位的变换函数；实际项目中换成真正的算法
                img2 = self._apply_transform(img_arr, timestamp) # 把时间戳一起传入
            else:
                img2 = self._make_no_camera_image(text="Not activated transformation")

            # 记录最近一次 “变换C” 的图像（供键盘保存使用）
            if self.transform_option_var.get() == "变换C" and self.image_test_var.get() == 1:
                # img2 已经是 Pillow Image（变换C 的最终结果）
                self._last_transform_c_image = img2.copy()
            else:
                self._last_transform_c_image = None

            # GUI显示帧率控制（仅显示部分限制fps，但保持30fps处理）
            current_time = time.time()
            if current_time - self._last_gui_update_time < self._gui_frame_interval:
                return  # 跳过GUI更新，但保持30fps处理

            self._last_gui_update_time = current_time

            # 缩放到 640×360（对应 OUTPUT_WIDTH / OUTPUT_HEIGHT）
            img = img.resize((640, 360), Image.LANCZOS)
            img2 = img2.resize((640, 360), Image.LANCZOS)

            # 在主线程中更新 UI（Tk 只能在主线程操作）
            photo = ImageTk.PhotoImage(img)
            photo2 = ImageTk.PhotoImage(img2)

            # 取消未完成的更新（避免堆积）
            if self._after_id:
                self.root.after_cancel(self._after_id)
            if hasattr(self, '_after_id2') and self._after_id2:
                self.root.after_cancel(self._after_id2)

            # 使用 after_idle 替代 after(0, ...) 更高效
            self._after_id = self.root.after_idle(self._update_video_label, photo)
            self._after_id2 = self.root.after_idle(self._update_video_label2, photo2)

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


    def _update_video_label2(self, photo_image):
        """把第二块的 PhotoImage 放到 video_label2 上（只能在主线程调用）"""
        if not getattr(self, "video_label2", None) or not self.video_label2.winfo_exists():
            return
        try:
            self.video_label2.configure(image=photo_image)
            self.video_label2.image = photo_image   # 防止被 GC
        except tk.TclError:
            pass


    def _on_key_press(self, event):
        """
        当窗口获得焦点且用户按下键盘时调用。
        若打开了 “图像采集模式” 并且按下的是字母键 **a**，则保存最近一次
        经过 “变换C” 的帧到 Resources/Captured 目录，文件名递增。
        """
        if event.keysym.lower() != 'a':
            return
        if getattr(self, "image_capture_var", None) and self.image_capture_var.get() == 1:
            self._save_captured_image()


    def _save_captured_image(self):
        """
        将最近一次 **选中的变换**（A、B 或 C）处理后的图像保存为 PNG。
        目标目录为项目根目录下的 ``Resources/Captured``，文件名从 1 开始递增。

        保存规则：
        1️⃣ 必须满足以下条件才会尝试保存：
            • 已打开摄像头并捕获到原始帧（self.latest_frame 不为 None）；
            • “图像测试”已开启（self.image_test_var == 1）；
            • “开启图像变换”已勾选（self.transform_enable_var == 1）；
            • 当前下拉框中有合法的变换选项（A/B/C）。
        2️⃣ 根据当前 ``self.transform_option_var`` 调用 ``self._apply_transform`` 对原始帧进行相同的处理，
            生成对应的 Pillow Image（已完成所有颜色通道转换）。
        3️⃣ 将生成的图像保存到 ``Resources/Captured``，文件名递增（1.png、2.png …）。
        4️⃣ 若任意前置条件不满足，则弹出警告；保存出错则弹出错误提示；成功保存仅在控制台打印路径。
        """
        # --------------------------------------------------------------
        # 1️⃣ 前置检查：确保有可保存的帧以及变换已启用
        # --------------------------------------------------------------
        if self.latest_frame is None:
            messagebox.showwarning("保存失败", "未捕获到任何摄像头帧，无法保存图像。")
            return
        if self.image_test_var.get() != 1:
            messagebox.showwarning("保存失败", "请先开启“图像测试”，才能保存图像。")
            return
        if self.transform_enable_var.get() != 1:
            messagebox.showwarning("保存失败", "请先勾选“开启图像变换”，才能保存变换后的图像。")
            return

        # --------------------------------------------------------------
        try:
            proc_frame = self.latest_frame.copy()          # 复制原始帧
            if self.rotate_flag:                           # 根据旋转标记处理
                proc_frame = rotate_image_180(proc_frame)
            if self.mirror_enable_var.get() == 1:          # 根据镜面开关处理
                proc_frame = proc_frame[:, ::-1, :]
            # 3️⃣ 根据当前选项生成对应的变换图像
            transformed_img = self._apply_transform(proc_frame)  # 使用处理后的帧
            if transformed_img is None:
                raise RuntimeError("变换函数返回了 None")
        except Exception as e:
            messagebox.showerror("保存错误", f"生成变换图像时出现异常:\n{e}")
            return

        # --------------------------------------------------------------
        # 3️⃣ 计算保存目录（使用项目根目录的绝对路径）
        # --------------------------------------------------------------
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        save_dir = os.path.join(project_root, "Resources", "Captured")
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("目录创建错误", f"无法创建保存目录:\n{save_dir}\n异常: {e}")
            return

        # --------------------------------------------------------------
        # 4️⃣ 生成递增的文件名（1.png、2.png、…）
        # --------------------------------------------------------------
        try:
            existing = [f for f in os.listdir(save_dir) if f.lower().endswith('.png')]
            numbers = [int(os.path.splitext(f)[0]) for f in existing if os.path.splitext(f)[0].isdigit()]
            next_idx = max(numbers) + 1 if numbers else 1
            filename = os.path.join(save_dir, f"{next_idx}.png")
        except Exception as e:
            messagebox.showerror("文件名计算错误", f"生成文件名时出错: {e}")
            return

        # --------------------------------------------------------------
        # 5️⃣ 实际写文件
        # --------------------------------------------------------------
        try:
            # Pillow.Image 已经是 RGB 格式，直接保存
            transformed_img.save(filename, format="PNG")
            print(f"[INFO] 已保存变换图像 → {filename}")
        except Exception as e:
            messagebox.showerror("保存错误", f"保存图像时出现异常:\n{e}")


    def _make_no_camera_image(self, width=640, height=360,
                              text="Camera is Not Open\nor\nNot activated transformation"):
        """
        生成一张指定宽高的黑底占位图，并把 *多行* 文本居中绘制。
        参数
        ----
        width, height : 图片尺寸（默认 640×360，与你的 video_label 大小一致）。
        text          : 需要显示的文字，支持换行（`\n`）。
        """
        # 1️⃣ 创建黑底
        img = Image.new('RGB', (width, height), (0, 0, 0))
        # 2️⃣ 准备绘图对象
        draw = ImageDraw.Draw(img)
        # 3️⃣ 选取字体（系统自带的 Arial，若不存在则回退到默认字体）
        try:
            # 跨平台字体（Windows: 微软雅黑/Arial；Ubuntu: Noto Sans CJK / DejaVu）
            try:
                from hudcore.platform.fonts import load_pil_font
                font = load_pil_font(32)
            except Exception:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        # 4️⃣ 把传进来的文本按行拆分
        lines = text.split('\n')
        # 5️⃣ 计算每行文字的宽高（Pillow≥10 建议使用 getbbox）
        line_sizes = [font.getbbox(l)[2:] for l in lines]  # (w, h) 列表
        line_heights = [h for (_, h) in line_sizes]
        # 6️⃣ 计算整体文字块的高度（行间距 4px，可自行调）
        line_spacing = 4
        total_text_h = sum(line_heights) + line_spacing * (len(lines) - 1)
        # 7️⃣ 计算首行左上角的起始坐标，使整个文字块在图片中心
        start_y = (height - total_text_h) // 2
        # 8️⃣ 逐行绘制，每行水平居中
        for i, line in enumerate(lines):
            w, h = line_sizes[i]
            x = (width - w) // 2               # 水平居中
            y = start_y + sum(line_heights[:i]) + line_spacing * i
            draw.text((x, y), line, font=font, fill=(0, 255, 0))
        return img


    def _cleanup_temp_files(self, prefix: str) -> None:
        """
        删除指定前缀的所有残留临时文件，以防止在透视变换校正时，因异常退出而遗留的文件堆积。
        """
        script_dir = os.path.abspath(os.path.dirname(__file__))
        pattern = os.path.join(script_dir, f"{prefix}*.png")
        for tmp_path in glob.glob(pattern):
            try:
                os.remove(tmp_path)
            except Exception as e:
                print(f"[WARN] 删除残留临时文件 {tmp_path} 时出错: {e}")


    # 透视变换校正入口（非阻塞）
    def start_perspective_correction(self):
        """
        按下 “透视变换校正” 按键后执行的回调。
        步骤：
        1. 读取最近一次捕获的原始帧（self.latest_frame）。
        2. 将该帧保存为临时 PNG 文件（opencv 读取更方便）。
        3. 在子线程里实例化 PerspectiveCalibrator 并调用 .run()，
           保证整个过程不阻塞 GUI 主线程。
        4. 线程结束后自动删除临时文件。
        """
        self._cleanup_temp_files("tmp_cam_")  # 清理旧的临时文

        # ① 检查是否已有帧可用
        if self.latest_frame is None:
            messagebox.showwarning("提示", "当前没有可用的摄像头帧，请先确保摄像头正常工作后再尝试校正。")
            return

        # 对 latest_frame 应用当前 UI 中的翻转/旋转设置
        proc_frame = self.latest_frame.copy()          # 复制防止修改原始缓存
        # 180° 旋转（如果打开）
        if self.rotate_flag:
            proc_frame = rotate_image_180(proc_frame)
        # 镜面水平翻转（如果打开）
        if self.mirror_enable_var.get() == 1:
            proc_frame = proc_frame[:, ::-1, :]

        # ② 将处理后的帧写入 **代码所在目录** 的临时文件
        # 使用当前脚本所在目录而不是系统临时目录,避免临时图像残留找不到位置
        script_dir = os.path.abspath(os.path.dirname(__file__))
        tmp_path = os.path.join(
            script_dir,
            f"tmp_cam_{int(time.time() * 1000)}.png"
        )
        # cv2.imwrite 需要 BGR 格式，proc_frame 已经是 RGB（camera_preview 里返回的是 RGB），先转回 BGR
        cv2.imwrite(tmp_path, cv2.cvtColor(proc_frame, cv2.COLOR_RGB2BGR))

        # ③ 在新线程中运行校正器
        def _run_calibrator():
            try:
                # 这里使用与主程序相同的输出分辨率，可自行修改
                calibrator = PerspectiveCalibrator(
                    image_path=tmp_path,
                    display_width=640,
                    display_height=360,
                    output_resolution="720p"      # 与主界面保持一致，可自行改为 "original"/"1080p"
                )
                calibrator.run()                # 进入交互式手动校准界面（OpenCV 窗口）
            except Exception as e:
                print(f"[ERROR] 透视校正异常: {e}")
            finally:
                self._cleanup_temp_files("tmp_cam_")  # 删除临时文件
        threading.Thread(target=_run_calibrator, daemon=True).start()


    # 曝光值实时更新回调
    def _on_exposure_change(self, event=None):
        """
        当用户在曝光下拉框中选择新值时调用。
        """
        # 取得用户选中的整数曝光值
        try:
            new_exp = int(self.exposure_var.get())
        except Exception:
            # 非法值回退到默认
            new_exp = -4
            self.exposure_var.set(new_exp)

        # 如果摄像头已经在运行，尝试即时修改
        if hasattr(self, "_camera_viewer") and self._camera_viewer is not None:
            cap = getattr(self._camera_viewer, "cap", None)
            if cap is not None and cap.isOpened():
                # 调用 camera_preview 中封装好的 set_exposure（返回是否成功；失败仅告警）
                if not set_exposure(cap, new_exp, verbose=True):
                    print(f"[WARN] 曝光值 {new_exp} 设置失败，保持原值")
            # 同时更新实例内部的 exposure 属性，防止后续 restart 时使用旧值
            self._camera_viewer.exposure = new_exp
        else:
            pass


    def _ts_to_fname(self, ts: float) -> str:
        """
        把 Unix epoch 秒（float）转为适合文件名的字符串：
        "YYYYMMDD_HHMMSS_mmm.jpg"（毫秒精度）。

        例子： 2023‑06‑05 17:29:51.975 → "20230605_172951_975.jpg"
        """
        # 这里直接使用已经在文件顶部 import 的 datetime
        dt = datetime.datetime.fromtimestamp(ts)
        # %f 给出微秒，取前 3 位即毫秒
        return dt.strftime("%Y%m%d_%H%M%S_%f")[:-3]


    def _load_platform_resolutions(self):
        """读取平台分辨率的辅助函数: 从 platform_resolution.json 加载平台→分辨率映射。"""
        # 数据目录优先，兼容旧位置（与模块同目录）
        json_path = None
        try:
            from hudcore.platform.paths import paths
            cand = paths.data_dir / "platform_resolution.json"
            if cand.is_file():
                json_path = str(cand)
        except Exception:
            json_path = None
        if json_path is None:
            legacy = os.path.join(os.path.dirname(__file__), "platform_resolution.json")
            json_path = legacy if os.path.isfile(legacy) else None
        if json_path is None:
            print("[平台分辨率] 未找到 platform_resolution.json（跳过）")
            return {}
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"[WARN] 加载平台分辨率文件失败: {e}")
            return {}


    def _on_platform_change(self, event=None):
        """平台切换回调（更新当前分辨率）: 当用户在平台下拉框中选择新平台时更新分辨率信息。"""
        platform = self.platform_var.get()
        self.selected_resolution = self.platform_resolutions.get(platform)

        # print(f"[INFO] 选择平台: {platform}, 分辨率: {self.selected_resolution}")

    # --------------------- 图像变换相关功能 ---------------------
    def _apply_transform(self, frame_rgb, timestamp=None):
        """
        根据下拉框当前选项返回不同的处理结果。
        - 变换A → 透视自动校正；
        - 变换B → 灰度化（保持 3 通道）；
        - 变换C → 先透视校正（变换A），再进行图像增强；
        - 变换D → 变换C + 图像分辨率拉伸。

        注意：
        * 这里的 ``frame_rgb`` 实际上是 **BGR**（CameraViewer 直接返回的 OpenCV 帧），
          为避免颜色通道错位，所有需要 **RGB** 的地方都会先做 BGR→RGB 转换，
          需要 **BGR** 的地方则直接使用原始数组。
        """
        option = self.transform_option_var.get()
        # ------------------------------------------------------------------
        # 统一获取 parser（如果还未创建则为 None），防止属性错误
        # ------------------------------------------------------------------
        parser = getattr(self, "parser", None)   # 只在测试已启动后才会有值

        if option == "变换A":
            # 先得到透视校正结果
            result_img = self._apply_perspective_auto(frame_rgb)         # 透视自动校正
            # 在解析器存在且当前工况为 “执行响应” 时启动检查线程（原逻辑保持）
            if (parser and
                getattr(parser, "get_current_state", None) and
                parser.get_current_state() == "执行响应"):
                threading.Thread(
                    target=self._check_and_save_error_image,
                    args=(result_img, timestamp),
                    daemon=True
                ).start()
            # 若已有 parser 并已读取当前用例信息，则把图像放入校验队列
            if parser:
                case_id = getattr(parser, "current_case_id", None)
                case_cfg = getattr(parser, "current_case_config", [])
                if case_id and case_cfg:
                    self._verification_queue.put((result_img.copy(), case_id, case_cfg))
            return result_img

        elif option == "变换B":
            # ---------- 灰度化（保持 3 通道） ----------
            img = Image.fromarray(frame_rgb)
            # 放入校验队列
            if parser:
                case_id = getattr(parser, "current_case_id", None)
                case_cfg = getattr(parser, "current_case_config", [])
                if case_id and case_cfg:
                    self._verification_queue.put((img.copy(), case_id, case_cfg))
            return img

        elif option == "变换C":                         # 先透视校正 → 再图像增强
            # 1️⃣ 透视校正（使用已有的自动函数），得到 Pillow Image (RGB)
            corrected_img = self._apply_perspective_auto(frame_rgb)
            # 2️⃣ Pillow Image → numpy **RGB** 数组
            import numpy as np                         # 局部导入，避免全局改动）
            corrected_rgb = np.array(corrected_img)      # (H, W, 3) RGB ndarray
            # 3️⃣ ImageEnhancer 需要 **BGR** 输入 → 先把 RGB 转回 BGR
            corrected_bgr = cv2.cvtColor(corrected_rgb, cv2.COLOR_RGB2BGR)
            # 4️⃣ 进行图像增强（返回 BGR），再转回 RGB 供 Pillow 使用
            enhanced_bgr = self._enhancer.process(corrected_bgr, save_output=False)
            enhanced_rgb = cv2.cvtColor(enhanced_bgr, cv2.COLOR_BGR2RGB)
            final_img = Image.fromarray(enhanced_rgb)       # 返回 Pillow Image (RGB)
            # 放入校验队列
            if parser:
                case_id = getattr(parser, "current_case_id", None)
                case_cfg = getattr(parser, "current_case_config", [])
                if case_id and case_cfg:
                    self._verification_queue.put((final_img.copy(), case_id, case_cfg))
            return final_img

        elif option == "变换D":
            # 前置处理
            corrected_img = self._apply_perspective_auto(frame_rgb)   # 透视校正，返回 Pillow Image
            # 根据当前平台分辨率进行尺寸调整（拉伸/压缩）
            if getattr(self, "selected_resolution", None):
                target_w = self.selected_resolution.get("width")
                target_h = self.selected_resolution.get("height")
                if target_w and target_h:
                    # 使用高质量的 Lanczos 插值
                    corrected_img = corrected_img.resize((target_w, target_h), Image.LANCZOS)
            # 以下保持变换C的增强流程
            import numpy as np
            corrected_rgb = np.array(corrected_img)                  # Pillow → RGB ndarray
            corrected_bgr = cv2.cvtColor(corrected_rgb, cv2.COLOR_RGB2BGR)
            enhanced_bgr = self._enhancer.process(corrected_bgr, save_output=False)
            enhanced_rgb = cv2.cvtColor(enhanced_bgr, cv2.COLOR_BGR2RGB)
            final_img = Image.fromarray(enhanced_rgb)                # 与变换C返回相同的 Pillow Image
            # 放入校验队列
            if parser:
                case_id = getattr(parser, "current_case_id", None)
                case_cfg = getattr(parser, "current_case_config", [])
                if case_id and case_cfg:
                    self._verification_queue.put((final_img.copy(), case_id, case_cfg))
            return final_img

        else:
            # 兜底：直接返回原始帧（BGR → RGB → Pillow）
            rgb = cv2.cvtColor(frame_rgb, cv2.COLOR_BGR2RGB)
            result = Image.fromarray(rgb)
            # 放入校验队列
            if parser:
                case_id = getattr(parser, "current_case_id", None)
                case_cfg = getattr(parser, "current_case_config", [])
                if case_id and case_cfg:
                    self._verification_queue.put((result.copy(), case_id, case_cfg))
            return result


    def _apply_perspective_auto(self, frame_rgb):
        """
        透视变换实现（零磁盘 IO 优化版）。
        - 直接把当前帧（RGB ndarray）传给 ``PerspectiveCalibrator.run_auto``；
        - 不再创建临时文件，完全在内存中处理；
        - 返回 ``PIL.Image``，若校正失败则返回原始帧对应的 Image。
        """
        try:
            # 直接传入 image_path=None，避免任何磁盘读取
            calibrator = PerspectiveCalibrator(
                image_path=None,                   # 不再创建临时文件
                display_width=640,
                display_height=360,
                output_resolution="720p"
            )
            # 通过 image_data 参数直接传入 numpy 数组，彻底避免磁盘 IO
            warped_bgr = calibrator.run_auto(
                enable_watch=False,
                save_output=False,
                image_data=frame_rgb               # 直接使用内存数据
            )
            # 若得到结果，转回 RGB 并返回 Pillow Image；否则返回原图
            if warped_bgr is not None:
                warped_rgb = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2RGB)
                return Image.fromarray(warped_rgb)
            else:
                return Image.fromarray(frame_rgb)
        except Exception as e:
            # 增加异常保护，防止透视变换失败导致 GUI 线程崩溃
            print(f"[ERROR] 透视变换处理失败: {e}")
            return Image.fromarray(frame_rgb)



    # --------------------- 图像变换相关功能 ---------------------
    def _check_and_save_error_image(self, pil_img, timestamp=None):
        """
        在单独线程中检查 ``pil_img``（Pillow Image）是否为异常图像，
        若是则以统一的时间戳格式保存为 JPG。
        """
        ENABLE_ERROR_CHECK = True
        if not ENABLE_ERROR_CHECK:
            return
        try:
            img_np = np.array(pil_img)
            if is_error_image(img_np):
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                save_dir = os.path.join(project_root, "error_image")
                os.makedirs(save_dir, exist_ok=True)

                if timestamp is None:
                    timestamp = time.time()
                    print("[INFO] 未传入时间戳则使用当前时间")
                # 调用实例方法得到文件名（不含扩展名）
                filename = f"{self._ts_to_fname(timestamp)}.jpg"
                save_path = os.path.join(save_dir, filename)

                pil_img.save(save_path, format="JPEG")
                print(f"[INFO] 异常图像已保存 → {save_path}")
        except Exception as e:
            print(f"[WARN] 检查/保存异常图像时出错: {e}")


    # 图标校验工作线程
    def _verification_worker(self):
        """
        持续从 ``self._verification_queue`` 取图像并在满足以下条件时进行图标校验：
            1.变换已开启（self.transform_enable_var == 1）
            2.解析器存在且当前工况为 “执行响应”
        若校验 **不通过**，把整张图像保存到 ``output/nosuccess`` 目录，文件名使用时间戳。
        """
        while not self._stop_verification.is_set():
            try:
                # 超时 0.2 s 让线程能够及时响应 termination 信号
                img, case_id, icon_list = self._verification_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            # 条件检查
            if self.transform_enable_var.get() != 1:
                self._verification_queue.task_done()
                continue
            if not (hasattr(self, "parser") and self.parser):
                self._verification_queue.task_done()
                continue
            if self.parser.get_current_state() != "执行响应":
                self._verification_queue.task_done()
                continue

            # --------- 开始图标效验 ----------
            mismatched = []
            img_arr = np.array(img)                     # 转为 ndarray 供比较函数使用
            for icon in icon_list:
                name = icon["name"]
                top_left = icon["top_left"]
                bottom_right = icon["bottom_right"]
                expected_hash = icon["ui_hash"]
                is_only_image = icon["is_only_image"]

                # 坐标 (x, y) → (y, x)
                y1, x1 = top_left[1], top_left[0]
                y2, x2 = bottom_right[1], bottom_right[0]
                if y1 >= y2 or x1 >= x2:
                    continue
                cropped = img_arr[y1:y2, x1:x2]

                # 阈值：仅图片→thr 参数，否则固定 40
                thr = 80 if is_only_image else 40
                try:
                    same = compare_with_precomputed_hash(
                        cropped,
                        precomputed_hash=expected_hash,
                        thr=thr,
                    )
                except Exception:
                    same = False

                if not same:
                    mismatched.append(name)

            # --------- 保存未通过的图像 ----------
            if mismatched:
                # 项目根目录 → output/nosuccess/<测试用例名称>
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                # 基础 nosuccess 目录
                nosuccess_base = os.path.join(project_root, "output", "nosuccess")
                # 为当前 case_id（即测试用例名称）创建子文件夹
                case_dir = os.path.join(nosuccess_base, str(case_id))
                os.makedirs(case_dir, exist_ok=True)
                # 使用已有的时间戳函数生成文件名（毫秒级）
                timestamp_fname = self._ts_to_fname(time.time())
                filename = f"{case_id}_{timestamp_fname}.png"
                save_path = os.path.join(case_dir, filename)
                try:
                    img.save(save_path, format="PNG")
                    print(f"[INFO] 图标校验未通过，已保存至 {save_path}")
                except Exception as e:
                    print(f"[WARN] 保存未通过校验的图像失败: {e}")
            # 结束本轮处理
            self._verification_queue.task_done()
