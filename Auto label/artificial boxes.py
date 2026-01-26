#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
交互式目标检测标注（Tkinter + 类别颜色 + 前后 3 张带框缩略图）

功能
  • 左侧 Canvas 显示图像 + 框（不同类别使用不同颜色）
  • 右侧按钮：Undo / Clear / DelAll / Save / Last / Next / Quit
  • 类别下拉框（ComboBox）读取 YOLO‑style yaml 中的 `names` 列表
  • 底部显示 **7 张缩略图**（前 3、当前、后 3），每张缩略图都带有对应的标注框
    （包括当前图片的新增框），点击任意缩略图即可跳转
  • 右侧仍保留 “跳转到第 n 张” 输入框（可选）
  • 关闭窗口右上角的 X 与点击 Quit 按钮等价（保存后退出程序）
"""

# -------------------------------------------------
# 0️⃣ 必要导入（必须放在文件最顶部，防止某些 IDE 找不到 ttk）
# -------------------------------------------------
import os
import sys
import argparse
import cv2
import numpy as np
import yaml                     # pip install pyyaml
from tqdm import tqdm
from PIL import Image, ImageTk
from functools import partial
import tkinter as tk            # 标准库自带

import threading, queue
from auto_detect import load_templates, detect_multi
# -------------------------------------------------
# 1️⃣ 参数 & 环境检查
# -------------------------------------------------
parser = argparse.ArgumentParser(description='交互式标注（Tkinter + 前后带框缩略图）')
parser.add_argument('--data_root',   type=str, default='dataset',
                    help='原始数据根目录，必须包含 images/ 与 labels/')
parser.add_argument('--subset',      type=str, default='',
                    help='子集名称 (train / val / test)，空表示全部')
parser.add_argument('--default_class', type=int, default=0,
                    help='启动时的默认类别 ID（从 0 开始）')
parser.add_argument('--max_class',   type=int, default=79,
                    help='最大类别 ID（含），默认 0~79（80 类）')
parser.add_argument('--yaml_path',   type=str, default='',
                    help='YOLO‑style yaml 文件路径（默认 data_root/data.yaml）')
args = parser.parse_args()
DATA_ROOT    = args.data_root
SUBSET       = args.subset.strip()
DEFAULT_CLASS = args.default_class
MAX_CLASS    = args.max_class
YAML_PATH    = args.yaml_path or os.path.join(DATA_ROOT, 'data.yaml')

# -------------------------------------------------
# 2️⃣ 小工具（仅使用 os / os.path）
# -------------------------------------------------
def list_image_files(img_root):
    """递归返回所有 jpg/jpeg/png 文件的完整路径列表（已排序）"""
    files = []
    for root, _, fnames in os.walk(img_root):
        for f in fnames:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                files.append(os.path.join(root, f))
    return sorted(files)

def txt_path_from_img(img_path, img_root, lbl_root):
    """根据图片路径得到对应的 txt 标注路径（保持子目录结构一致）"""
    rel_dir = os.path.relpath(os.path.dirname(img_path), img_root)
    base = os.path.splitext(os.path.basename(img_path))[0]
    return os.path.join(lbl_root, rel_dir, base + '.txt')

def read_boxes(txt_path):
    """读取 YOLO txt，返回 [(cls, xc, yc, w, h), ...]（归一化坐标）"""
    if not os.path.isfile(txt_path):
        return []
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    boxes = []
    for ln in lines:
        parts = ln.split()
        if len(parts) != 5:
            continue
        cls, xc, yc, w, h = map(float, parts)
        boxes.append((int(cls), xc, yc, w, h))
    return boxes

def ensure_dir(p):
    if not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)

def load_class_names(yaml_path):
    """读取 YOLO‑style yaml（data.yaml）并返回 names 列表"""
    if not os.path.isfile(yaml_path):
        print(f"[Error] 找不到 yaml 文件: {yaml_path}")
        sys.exit(1)
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if 'names' not in data:
        print(f"[Error] yaml 中没有 `names` 键，请检查文件格式")
        sys.exit(1)
    names = data['names']
    if not isinstance(names, list):
        print("[Error] `names` 必须是列表")
        sys.exit(1)
    return names

def generate_color_map(num_classes):
    """
    为每个类别生成一种颜色（BGR）。前 6 类使用常规颜色，
    其余使用 OpenCV COLORMAP_JET 随机取色。
    """
    base_colors = [
        (0, 0, 255),      # 0 - red
        (0, 255, 0),      # 1 - green
        (255, 0, 0),      # 2 - blue
        (255, 255, 0),    # 3 - cyan
        (255, 0, 255),    # 4 - magenta
        (0, 255, 255),    # 5 - yellow
    ]
    colors = base_colors[:]
    if num_classes > len(base_colors):
        extra = num_classes - len(base_colors)
        jet = cv2.applyColorMap(
            np.arange(0, 256, dtype=np.uint8).reshape(-1, 1),
            cv2.COLORMAP_JET
        ).squeeze()
        idxs = np.linspace(0, 255, extra, dtype=int)
        for i in idxs:
            b, g, r = jet[i].tolist()
            colors.append((int(b), int(g), int(r)))
    return colors[:num_classes]

# -------------------------------------------------
# 3️⃣ 核心标注类（业务层，仅负责标注文件的读取/写入/框选/撤销等）
# -------------------------------------------------
class AnnotatorCore:
    """
    负责：
        • 读取/保存 YOLO 框
        • 记录本次新增框（归一化坐标）
        • 删除/撤销/清空等业务
        • 将框绘制到 OpenCV BGR 图像上（供 UI 调用）
    """
    def __init__(self, img_path, txt_path, default_class, class_colors):
        self.img_path = img_path
        self.txt_path = txt_path
        self.cur_class = default_class

        # 读取图像
        self.cv_img = cv2.imread(img_path)
        if self.cv_img is None:
            raise RuntimeError(f'Cannot read image: {img_path}')
        self.h, self.w = self.cv_img.shape[:2]

        # 已有框（只用于显示）
        self.existing_boxes = read_boxes(txt_path)

        # 本次新增框（归一化坐标）
        self.new_boxes = []

        # DeleteAll 标记（保存时需要截断文件）
        self._deleted_all = False

        # 颜色映射（list[(B,G,R), ...]），长度 = 类别数
        self.class_colors = class_colors

    # -------------------------------------------------
    # 业务方法（供 UI 按钮调用）
    # -------------------------------------------------
    def undo(self):
        if self.new_boxes:
            removed = self.new_boxes.pop()
            print(f"[Info] 撤销框 {removed}")
        else:
            print("[Info] 没有可撤销的框")

    def clear(self):
        self.new_boxes.clear()
        print("[Info] 已清空本次新增框")

    def delete_all(self):
        self.existing_boxes.clear()
        self.new_boxes.clear()
        self._deleted_all = True
        print("[Warning] 已清空当前图片的全部框（包括原有的），记得点击 Save/Next 保存")

    def save(self):
        """把本次新增框写入 txt，并合并进 existing_boxes 使 UI 仍能显示"""
        ensure_dir(os.path.dirname(self.txt_path))
        if self._deleted_all:
            open(self.txt_path, 'w', encoding='utf-8').close()
            self._deleted_all = False
        if self.new_boxes:
            with open(self.txt_path, 'a', encoding='utf-8') as f:
                for cls, xc, yc, w, h in self.new_boxes:
                    f.write(f"{cls} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
            # 合并进已有框
            self.existing_boxes.extend(self.new_boxes)
            self.new_boxes.clear()
        print("[Info] 已保存（新增框已合并进已有框）")

    # -------------------------------------------------
    # 鼠标框选（供 UI 调用）
    # -------------------------------------------------
    def start_box(self, x, y):
        self._drawing = True
        self._start_pt = (x, y)
        self._cur_rect = (x, y, x, y)

    def update_box(self, x, y):
        if getattr(self, '_drawing', False):
            self._cur_rect = (self._start_pt[0], self._start_pt[1], x, y)

    def finish_box(self, x, y):
        if not getattr(self, '_drawing', False):
            return
        self._drawing = False
        x1, y1, x2, y2 = self._cur_rect
        xc = (x1 + x2) / 2.0 / self.w
        yc = (y1 + y2) / 2.0 / self.h
        bw = abs(x2 - x1) / self.w
        bh = abs(y2 - y1) / self.h
        if bw > 0 and bh > 0:
            self.new_boxes.append((self.cur_class, xc, yc, bw, bh))
        self._cur_rect = None

    # -------------------------------------------------
    # 绘制函数（返回已绘制框的 OpenCV BGR 图像）
    # -------------------------------------------------
    def draw(self, show_cur_rect=True):
        """
        如果只想要框（用于缩略图），可以调用 draw(show_cur_rect=False)
        """
        canvas = self.cv_img.copy()

        # 已有框（使用对应颜色）
        for cls, xc, yc, w, h in self.existing_boxes:
            color = self.class_colors[cls % len(self.class_colors)]
            x1 = int((xc - w/2) * self.w)
            y1 = int((yc - h/2) * self.h)
            x2 = int((xc + w/2) * self.w)
            y2 = int((yc + h/2) * self.h)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            cv2.putText(canvas, str(cls), (x1, y1-4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # 本次新增框（同样使用对应颜色）
        for cls, xc, yc, w, h in self.new_boxes:
            color = self.class_colors[cls % len(self.class_colors)]
            x1 = int((xc - w/2) * self.w)
            y1 = int((yc - h/2) * self.h)
            x2 = int((xc + w/2) * self.w)
            y2 = int((yc + h/2) * self.h)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            cv2.putText(canvas, str(cls), (x1, y1-4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # 正在绘制的矩形（红色固定）
        if show_cur_rect and getattr(self, '_cur_rect', None):
            x1, y1, x2, y2 = self._cur_rect
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 255), 2)

        # 当前类别提示（右上角，用当前类别颜色）
        cur_color = self.class_colors[self.cur_class % len(self.class_colors)]
        cv2.rectangle(canvas, (0, 0), (120, 30), (0, 0, 0), -1)
        cv2.putText(canvas, f"Class: {self.cur_class}",
                    (5, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    cur_color, 2)

        return canvas

    # -------------------------------------------------
    # 键盘类别切换（供 UI 调用，保留快捷键功能）
    # -------------------------------------------------
    def change_class(self, key):
        """key 为 `ord('0')..ord('9')` 或 `ord('a')..ord('z')`"""
        if 48 <= key <= 57:               # 0‑9
            self.cur_class = (key - 48) % (MAX_CLASS + 1)
        elif 97 <= key <= 122:            # a‑z → 10‑35
            self.cur_class = (key - 97 + 10) % (MAX_CLASS + 1)
        print(f"[Info] 当前类别切换为 {self.cur_class}")

    # -------------------------------------------------
    # 通过类别名称直接设置类别 ID（下拉框回调使用）
    # -------------------------------------------------
    def set_class_by_name(self, name, names_list):
        """name 必须在 names_list 中出现，返回对应的索引作为类别 ID"""
        try:
            idx = names_list.index(name)
            self.cur_class = idx
            print(f"[Info] 类别切换为 [{idx}] {name}")
        except ValueError:
            print(f"[Warning] 名称 `{name}` 不在类别列表中，保持原类别 {self.cur_class}")

# -------------------------------------------------
# 4️⃣ Tkinter UI（图像 + 按钮 + 类别下拉框 + 缩略图条）
# -------------------------------------------------
class AnnotatorUI:
    """
    Tkinter 窗口负责：
        • 显示图像（Canvas）
        • 绘制实时矩形（每帧更新）
        • 响应按钮点击 → 调用 AnnotatorCore 相应方法
        • 类别下拉框（从 yaml 中读取）
        • 底部显示 **7 张带框的缩略图**（前 3、当前、后 3）；
          点击任意缩略图立即跳转
        • 右侧仍保留 “跳转到第 n 张” 输入框（可选）
        • 关闭窗口（X）时自动保存并退出
    """
    def __init__(self, core: AnnotatorCore, class_names,
                 img_files, img_index, total_imgs,
                 img_root, lbl_root):
        # ---------- 基础属性 ----------
        self.core = core
        self.class_names = class_names
        self.img_files   = img_files
        self.img_index   = img_index
        self.total_imgs  = total_imgs
        self.img_root    = img_root          # 用来生成正确的 txt 路径
        self.lbl_root    = lbl_root

        # ---------- 返回指令 ----------
        self.result = None          # "next" / "last" / "jump" / "quit"
        self.jump_to = None         # 若 result == "jump"，这里保存目标索引（0‑based）
        # ------------------- 线程/队列 -------------------
        self._detect_queue = queue.Queue()
        self._detect_running = False
        # ------------------- 加载模板 -------------------
        TPL_DIR = os.path.join(DATA_ROOT, "muban_shixiao")  # 根据你的目录自行修改
        self._templates = load_templates(TPL_DIR)
        print(f"[Info] 已加载 {len(self._templates)} 张模板")
        # ---------- ttk / Button/Combobox ----------
        try:
            from tkinter import ttk
            self.ButtonCls   = ttk.Button
            self.ComboboxCls = ttk.Combobox
        except Exception:
            self.ButtonCls   = tk.Button
            self.ComboboxCls = tk.OptionMenu   # 退化为普通 OptionMenu

        # ---------- 主窗口 ----------
        self.root = tk.Tk()
        self.root.title(f"Annotate – {os.path.basename(core.img_path)}  (X = quit)")

        # ---------- 左侧 Canvas ----------
        self.canvas = tk.Canvas(self.root,
                                width=self.core.w,
                                height=self.core.h,
                                bg='black')
        self.canvas.grid(row=0, column=0, padx=5, pady=5)

        # ---------- 右侧按钮 ----------
        btn_frame = tk.Frame(self.root)
        btn_frame.grid(row=0, column=1, sticky='ns', padx=5, pady=5)

        # 按钮顺序：Undo / Clear / DelAll / Save / Last / Next / Quit
        # （原来的 Add 按钮是占位，这里直接去掉）
        self.ButtonCls(btn_frame, text="Undo",   width=10,
                       command=self.core.undo).grid(pady=2)
        self.ButtonCls(btn_frame, text="Clear",  width=10,
                       command=self.core.clear).grid(pady=2)
        self.ButtonCls(btn_frame, text="DelAll", width=10,
                       command=self.core.delete_all).grid(pady=2)
        self.ButtonCls(btn_frame, text="Save",   width=10,
                       command=self.core.save).grid(pady=2)
        self.ButtonCls(btn_frame, text="AutoDetect", width=10,
                       command=self._on_auto_detect).grid(pady=2)
        self.ButtonCls(btn_frame, text="Last",   width=10,
                       command=self._on_last).grid(pady=2)
        self.ButtonCls(btn_frame, text="Next",   width=10,
                       command=self._on_next).grid(pady=2)
        self.ButtonCls(btn_frame, text="Quit",   width=10,
                       command=self._on_quit).grid(pady=2)

        # ---------- 类别下拉框 ----------
        init_name = (self.class_names[self.core.cur_class]
                     if 0 <= self.core.cur_class < len(self.class_names)
                     else self.class_names[0])
        if hasattr(self, 'ComboboxCls') and self.ComboboxCls is not tk.OptionMenu:
            self.combo = self.ComboboxCls(btn_frame,
                                          values=self.class_names,
                                          state='readonly',
                                          width=15)
            self.combo.set(init_name)
            self.combo.grid(pady=8)
            self.combo.bind("<<ComboboxSelected>>",
                           self._on_class_selected)
        else:
            self.combo_var = tk.StringVar(value=init_name)
            self.combo = tk.OptionMenu(btn_frame,
                                      self.combo_var,
                                      *self.class_names,
                                      command=self._on_class_selected_optionmenu)
            self.combo.grid(pady=8)

        # 小提示（快捷键）
        tip = tk.Label(btn_frame, text="0‑9 / a‑z → change class",
                       fg='gray')
        tip.grid(pady=10)

        # ---------- 底部缩略图条（7 张） ----------
        thumb_bar = tk.Frame(self.root)
        thumb_bar.grid(row=2, column=0, columnspan=2, pady=5)
        self.thumb_buttons = []   # 保存 7 个按钮对象
        for i in range(7):
            btn = tk.Button(thumb_bar, width=80, height=80,
                            command=partial(self._on_thumb_click, i))
            btn.grid(row=0, column=i, padx=2)
            self.thumb_buttons.append(btn)

        # ---------- 跳转输入框 ----------
        bottom_frame = tk.Frame(self.root)
        bottom_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)
        jump_frame = tk.Frame(bottom_frame)
        jump_frame.pack(side='right', padx=5)
        tk.Label(jump_frame,
                 text=f"第 {self.img_index+1}/{self.total_imgs} 张  →  跳转到第").grid(row=0, column=0)
        self.jump_entry = tk.Entry(jump_frame, width=5)
        self.jump_entry.grid(row=0, column=1, padx=2)
        tk.Button(jump_frame, text="Go", command=self._on_jump).grid(row=0, column=2, padx=2)
        self.jump_entry.bind("<Return>", lambda e: self._on_jump())

        # ---------- 绑定鼠标、键盘 ----------
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.root.bind("<Key>", self._on_key)

        # ---------- 窗口关闭 ----------
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

        # ---------- 缓存 & 刷新 ----------
        self._thumb_cache = {}          # {idx: PhotoImage}
        self._last_new_boxes = []       # 用来检测本轮框是否变化
        self._refresh_interval = 33     # ms ≈ 30 FPS

        # 首次绘制（包括缩略图）
        self._refresh_ui()
        # 开始定时刷新（只负责 Canvas，缩略图走缓存）
        self._schedule_refresh()
        self.root.mainloop()

    # -------------------------------------------------
    # 按钮回调
    # -------------------------------------------------
    def _on_auto_detect(self):
        if self._detect_running:
            print("[Info] 检测已在进行中，请稍候…")
            return
        self._detect_running = True
        threading.Thread(target=self._run_detection_thread, daemon=True).start()
        self.root.after(100, self._check_detection_result)

    def _run_detection_thread(self):
        try:
            frame_gray = cv2.cvtColor(self.core.cv_img, cv2.COLOR_BGR2GRAY)
            det_results = detect_multi(
                frame_gray,
                self._templates,
                self.class_names,
                ratio_thr=0.4,
                min_match=4,
                ransac_thr=12.0,
                scale_factor=2.0,
                max_instances=20,
                nms_iou=0.3,
            )
            self._detect_queue.put(det_results)
        except Exception as e:
            self._detect_queue.put(e)

    def _check_detection_result(self):
        try:
            result = self._detect_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self._check_detection_result)
            return

        self._detect_running = False

        if isinstance(result, Exception):
            print("[Error] 自动检测异常：", result)
            return

        dets = result
        if not dets:
            print("[Info] 本帧未检测到任何模板")
        else:
            print(f"[Info] 检测到 {len(dets)} 个实例，写入标注")
            img_h, img_w = self.core.h, self.core.w
            for bbox, class_id, score in dets:
                x, y, w, h = bbox
                xc = (x + w / 2.0) / img_w
                yc = (y + h / 2.0) / img_h
                nw = w / img_w
                nh = h / img_h
                # 这里使用方案 A（直接写入 existing_boxes），如果想要撤销请改成 new_boxes
                self.core.existing_boxes.append((class_id, xc, yc, nw, nh))

            # 可选：自动保存
            # self.core.save()

            # 刷新 UI，缩略图也会同步显示新框
            self._refresh_ui()

    def _on_next(self):
        self.result = "next"
        self.root.destroy()

    def _on_last(self):
        self.result = "last"
        self.root.destroy()

    def _on_quit(self):
        # 退出前自动保存，防止误操作丢失
        self.core.save()
        self.result = "quit"
        self.root.destroy()

    # -------------------------------------------------
    # 类别下拉框回调
    # -------------------------------------------------
    def _on_class_selected(self, event):
        chosen_name = self.combo.get()
        self.core.set_class_by_name(chosen_name, self.class_names)

    def _on_class_selected_optionmenu(self, chosen_name):
        self.core.set_class_by_name(chosen_name, self.class_names)

    # -------------------------------------------------
    # 缩略图点击回调（直接跳转到真实的图片索引）
    # -------------------------------------------------
    def _on_thumb_click(self, slot_idx):
        start, _ = self._calc_thumb_range()
        real_idx = start + slot_idx
        if real_idx < self.total_imgs:
            self.result = "jump"
            self.jump_to = real_idx
            self.root.destroy()

    # -------------------------------------------------
    # 跳转框回调（右侧输入框）
    # -------------------------------------------------
    def _on_jump(self):
        txt = self.jump_entry.get().strip()
        if not txt.isdigit():
            print("[Warning] 跳转输入必须是正整数")
            return
        target = int(txt) - 1          # 用户输入的是 1‑based，内部使用 0‑based
        if target < 0 or target >= self.total_imgs:
            print("[Warning] 跳转目标超出范围")
            return
        self.result = "jump"
        self.jump_to = target
        self.root.destroy()

    # -------------------------------------------------
    # 鼠标事件（框选）
    # -------------------------------------------------
    def _on_mouse_down(self, event):
        self.core.start_box(event.x, event.y)

    def _on_mouse_move(self, event):
        self.core.update_box(event.x, event.y)

    def _on_mouse_up(self, event):
        self.core.finish_box(event.x, event.y)

    # -------------------------------------------------
    # 键盘事件（类别切换 + Esc 退出）
    # -------------------------------------------------
    def _on_key(self, event):
        if event.char:
            self.core.change_class(ord(event.char.lower()))
        if event.keysym == 'Escape':
            self._on_quit()

    # -------------------------------------------------
    # 计算当前需要显示的 7 张缩略图的范围（返回 start, end）
    # -------------------------------------------------
    def _calc_thumb_range(self):
        """
        返回 (start_idx, end_idx) —— Python 切片的左闭右开区间，
        包含当前图片在内且总长度不超过 7。
        """
        half = 3
        start = max(0, self.img_index - half)
        end = start + 7
        if end > self.total_imgs:
            end = self.total_imgs
            start = max(0, end - 7)
        return start, end

    # -------------------------------------------------
    # 缩略图更新（使用缓存，只有在需要时才重新渲染）
    # -------------------------------------------------
    def _update_thumbnails(self):
        start, _ = self._calc_thumb_range()
        for slot_idx, btn in enumerate(self.thumb_buttons):
            real_idx = start + slot_idx
            if real_idx >= self.total_imgs:
                btn.configure(image='', state=tk.DISABLED)
                btn.image = None
                continue

            # 检查缓存
            if real_idx in self._thumb_cache:
                photo = self._thumb_cache[real_idx]
            else:
                # 正确的 txt 路径
                txt_path = txt_path_from_img(
                    self.img_files[real_idx],
                    self.img_root,
                    self.lbl_root
                )
                # 临时 core 用于渲染缩略图（不显示实时红框）
                tmp_core = AnnotatorCore(
                    img_path=self.img_files[real_idx],
                    txt_path=txt_path,
                    default_class=self.core.cur_class,
                    class_colors=self.core.class_colors
                )
                # 把当前页面的新增框同步过去（让所有缩略图看到本轮框）
                tmp_core.new_boxes = self.core.new_boxes.copy()
                thumb_img = tmp_core.draw(show_cur_rect=False)

                # 缩放到 80×80
                thumb_small = cv2.resize(thumb_img, (80, 80),
                                         interpolation=cv2.INTER_AREA)
                thumb_rgb = cv2.cvtColor(thumb_small, cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(thumb_rgb)
                photo = ImageTk.PhotoImage(pil)

                # 写入缓存
                self._thumb_cache[real_idx] = photo

            btn.configure(image=photo, state=tk.NORMAL)
            btn.image = photo   # 防止被 GC

    # -------------------------------------------------
    # 主画面刷新（每帧重新绘制图像 + 框），并同步缩略图
    # -------------------------------------------------
    def _refresh_ui(self):
        cv_img = self.core.draw()
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        self.photo = ImageTk.PhotoImage(pil)
        # 先清空旧的图像再绘制，防止残影
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo)

        # 缩略图只在新增框变化时刷新缓存
        if self.core.new_boxes != self._last_new_boxes:
            self._thumb_cache.clear()
            self._last_new_boxes = self.core.new_boxes.copy()
        self._update_thumbnails()

    def _schedule_refresh(self):
        self._refresh_ui()
        self.root.after(self._refresh_interval, self._schedule_refresh)

# -------------------------------------------------
# 5️⃣ 主入口：遍历图片并逐张打开 Tkinter 标注窗口
# -------------------------------------------------
def main():
    img_root = os.path.join(DATA_ROOT, 'images')
    lbl_root = os.path.join(DATA_ROOT, 'labels')
    if SUBSET:
        img_root = os.path.join(img_root, SUBSET)
        lbl_root = os.path.join(lbl_root, SUBSET)

    img_files = list_image_files(img_root)
    if not img_files:
        print(f'⚠️ 未在 {img_root} 中找到图片')
        sys.exit(1)

    # ---------- 读取类别名称 ----------
    class_names = load_class_names(YAML_PATH)
    print(f"[Info] 已读取 {len(class_names)} 个类别（来自 {YAML_PATH}）")

    # ---------- 为每个类别生成颜色 ----------
    class_colors = generate_color_map(len(class_names))

    # ---------- 处理默认类别 ----------
    default_class = DEFAULT_CLASS
    if default_class >= len(class_names):
        print("[Warning] 默认类别 ID 超出 yaml 中的类别数，已重置为 0")
        default_class = 0

    total_imgs = len(img_files)
    idx = 0
    print(f'🖼️ 共计 {total_imgs} 张图片待标注')

    while 0 <= idx < total_imgs:
        img_path = img_files[idx]
        txt_path = txt_path_from_img(img_path, img_root, lbl_root)

        core = AnnotatorCore(img_path, txt_path, default_class, class_colors)

        # 打开 Tkinter 窗口进行标注
        ui = AnnotatorUI(core, class_names,
                         img_files, idx, total_imgs,
                         img_root, lbl_root)   # ← 这里把根目录传进去

        # 根据 UI 返回的指令决定下一步索引
        if ui.result == "next":
            idx += 1
        elif ui.result == "last":
            idx -= 1
        elif ui.result == "jump":
            idx = ui.jump_to
        elif ui.result == "quit":
            print("[Info] 用户主动退出 → 程序结束")
            sys.exit(0)
        else:
            idx += 1

        # 防止 idx 越界
        if idx < 0:
            idx = 0
        if idx >= total_imgs:
            break

    print('\n✅ 所有图片已完成标注！')

if __name__ == '__main__':
    main()