#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
交互式标注 + ORB 多模板自动检测（调参/Debug 版）
"""

# -------------------------------------------------
# 0️⃣ 必要导入
# -------------------------------------------------
import os, sys, argparse, cv2, numpy as np, random, colorsys, yaml, threading, queue
from pathlib import Path
from tqdm import tqdm
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk
from functools import partial

# -------------------------------------------------
# 1️⃣ 参数 & 环境检查（加入可调参数）
# -------------------------------------------------
parser = argparse.ArgumentParser(description='交互式标注（Tkinter + 自动检测）')
parser.add_argument('--data_root',   type=str, default='dataset')
parser.add_argument('--subset',      type=str, default='')
parser.add_argument('--default_class', type=int, default=0)
parser.add_argument('--max_class',   type=int, default=79)
parser.add_argument('--yaml_path',   type=str, default='')

# ---------- 可调参数 ----------
parser.add_argument('--tpl_dir',     type=str, default='muban',
                    help='模板文件夹（相对于 data_root）')
parser.add_argument('--ratio_thr',   type=float, default=0.6,
                    help='Ratio Test 阈值（越小越宽松）')
parser.add_argument('--ransac_thr',  type=float, default=20.0,
                    help='RANSAC 误差阈值')
parser.add_argument('--scale_factor',type=float, default=3.0,
                    help='模板放大倍数（>1 表示放大）')
parser.add_argument('--min_match',   type=int, default=4,
                    help='最少匹配数')
parser.add_argument('--nms_iou',    type=float, default=0.5,
                    help='NMS IOU 阈值')
args = parser.parse_args()

DATA_ROOT    = args.data_root
SUBSET       = args.subset.strip()
DEFAULT_CLASS = args.default_class
MAX_CLASS    = args.max_class
YAML_PATH    = args.yaml_path or os.path.join(DATA_ROOT, 'data.yaml')

TPL_DIR      = os.path.join(args.tpl_dir)

RATIO_THR    = args.ratio_thr
RANSAC_THR   = args.ransac_thr
SCALE_FACTOR = args.scale_factor
MIN_MATCH    = args.min_match
NMS_IOU      = args.nms_iou

tpl_dir = Path('muban')   # <-- 改成实际路径
files = list(tpl_dir.glob("*.*"))
print("模板文件数（所有后缀）:", len(files))
for p in files:
    print(p.name, p.suffix)
    img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    print("  读取成功?" , img is not None)
# -------------------------------------------------
# 2️⃣ 小工具（文件遍历、路径转换、yaml、颜色）
# -------------------------------------------------
def list_image_files(img_root):
    files = []
    for root, _, fnames in os.walk(img_root):
        for f in fnames:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                files.append(os.path.join(root, f))
    return sorted(files)

def txt_path_from_img(img_path, img_root, lbl_root):
    rel_dir = os.path.relpath(os.path.dirname(img_path), img_root)
    base = os.path.splitext(os.path.basename(img_path))[0]
    return os.path.join(lbl_root, rel_dir, base + '.txt')

def read_boxes(txt_path):
    if not os.path.isfile(txt_path):
        return []
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    boxes = []
    for ln in lines:
        parts = ln.split()
        if len(parts) != 5: continue
        cls, xc, yc, w, h = map(float, parts)
        boxes.append((int(cls), xc, yc, w, h))
    return boxes

def ensure_dir(p):
    if not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)

def load_class_names(yaml_path):
    if not os.path.isfile(yaml_path):
        print(f"[Error] 找不到 yaml 文件: {yaml_path}")
        sys.exit(1)
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if 'names' not in data:
        print("[Error] yaml 中没有 `names` 键")
        sys.exit(1)
    names = data['names']
    if not isinstance(names, list):
        print("[Error] `names` 必须是列表")
        sys.exit(1)
    return names

def generate_color_map(num_classes):
    base_colors = [
        (0, 0, 255), (0, 255, 0), (255, 0, 0),
        (255, 255, 0), (255, 0, 255), (0, 255, 255)
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
# 3️⃣ ORB 多模板检测模块（调试打印已加入）
# -------------------------------------------------
def nms(boxes, scores, iou_thr=0.3):
    if not boxes: return []
    boxes = np.array(boxes, dtype=np.float32)
    scores = np.array(scores, dtype=np.float32)
    x1, y1 = boxes[:,0], boxes[:,1]
    x2, y2 = boxes[:,0]+boxes[:,2]-1, boxes[:,1]+boxes[:,3]-1
    areas = (x2-x1+1)*(y2-y1+1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2-xx1+1)
        h = np.maximum(0.0, yy2-yy1+1)
        inter = w*h
        iou = inter/(areas[i]+areas[order[1:]]-inter)
        inds = np.where(iou <= iou_thr)[0]
        order = order[inds+1]
    return keep

_ORB = cv2.ORB_create(
    nfeatures=5000,
    edgeThreshold=5,
    patchSize=31,
    scaleFactor=1.2,
    nlevels=8,
)
_BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

def _detect_one_template(frame_gray, tmpl_gray,
                         ratio_thr=0.55, min_match=4,
                         ransac_thr=12.0, scale_factor=2.0,
                         max_instances=20):
    if scale_factor != 1.0:
        tmpl_gray = cv2.resize(
            tmpl_gray,
            (int(tmpl_gray.shape[1]*scale_factor),
             int(tmpl_gray.shape[0]*scale_factor)),
            interpolation=cv2.INTER_LINEAR)
    kp_t, des_t = _ORB.detectAndCompute(tmpl_gray, None)
    kp_i, des_i = _ORB.detectAndCompute(frame_gray, None)
    print(f"[DEBUG] 模板关键点数 = {len(kp_t)}，帧关键点数 = {len(kp_i)}")
    if des_t is None or des_i is None:
        return []
    matches = _BF.knnMatch(des_t, des_i, k=2)
    good = [m for m, n in matches if m.distance < ratio_thr * n.distance]
    print(f"[DEBUG] 匹配总数 = {len(matches)}，好匹配数 = {len(good)}（ratio_thr={ratio_thr}）")
    results = []
    instance_id = 0
    while len(good) >= min_match and instance_id < max_instances:
        src_pts = np.float32([kp_t[m.queryIdx].pt for m in good]).reshape(-1,1,2)
        dst_pts = np.float32([kp_i[m.trainIdx].pt for m in good]).reshape(-1,1,2)
        if src_pts.shape[0] < 4:
            break
        H, mask = cv2.findHomography(src_pts, dst_pts,
                                     cv2.RANSAC, ransac_thr)
        if H is None:
            print("[DEBUG] RANSAC 失败（Homography 为 None）")
            break
        h, w = tmpl_gray.shape[:2]
        corners = np.float32([[0,0],[w,0],[w,h],[0,h]]).reshape(-1,1,2)
        proj = cv2.perspectiveTransform(corners, H)
        x, y, w_box, h_box = cv2.boundingRect(proj.astype(np.int32))
        inlier_cnt = int(mask.sum())
        score = inlier_cnt / max(len(kp_t), 1)
        results.append(((x, y, w_box, h_box), H, float(score)))
        good = [g for i, g in enumerate(good) if mask[i] == 0]
        instance_id += 1
    return results

def detect_multi(frame_gray, templates, class_names,
                 ratio_thr=0.55, min_match=4,
                 ransac_thr=12.0, scale_factor=2.0,
                 max_instances=20, nms_iou=0.3):
    all_res = []
    for name, tmpl in templates.items():
        if name not in class_names:
            class_names.append(name)
            print(f"[INFO] 自动把模板 `{name}` 加入类别列表，class_id={len(class_names)-1}")
        class_id = class_names.index(name)
        raw = _detect_one_template(
            frame_gray, tmpl,
            ratio_thr=ratio_thr,
            min_match=min_match,
            ransac_thr=ransac_thr,
            scale_factor=scale_factor,
            max_instances=max_instances,
        )
        if not raw:
            continue
        boxes = [r[0] for r in raw]
        scores = [r[2] for r in raw]
        keep = nms(boxes, scores, iou_thr=nms_iou)
        print(f"[DEBUG] {name}: raw={len(raw)}，NMS 后 keep={len(keep)}")
        for idx in keep:
            bbox, _, score = raw[idx]
            all_res.append((bbox, class_id, score))
    return all_res

def load_templates(tpl_dir):
    tmpl_paths = list(Path(tpl_dir).glob("*.*"))
    templates = {}
    for p in tmpl_paths:
        if p.suffix.lower() not in {".png",".jpg",".jpeg"}:
            continue
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"[WARN] 读取模板失败 → {p}")
            continue
        templates[p.stem] = img
    return templates

# -------------------------------------------------
# 4️⃣ 业务层 – AnnotatorCore（保持原实现）
# -------------------------------------------------
class AnnotatorCore:
    def __init__(self, img_path, txt_path, default_class, class_colors):
        self.img_path = img_path
        self.txt_path = txt_path
        self.cur_class = default_class
        self.cv_img = cv2.imread(img_path)
        if self.cv_img is None:
            raise RuntimeError(f'Cannot read image: {img_path}')
        self.h, self.w = self.cv_img.shape[:2]
        self.existing_boxes = read_boxes(txt_path)
        self.new_boxes = []
        self._deleted_all = False
        self.class_colors = class_colors
    # ---------- 业务方法 ----------
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
        ensure_dir(os.path.dirname(self.txt_path))
        if self._deleted_all:
            open(self.txt_path, 'w', encoding='utf-8').close()
            self._deleted_all = False
        if self.new_boxes:
            with open(self.txt_path, 'a', encoding='utf-8') as f:
                for cls, xc, yc, w, h in self.new_boxes:
                    f.write(f"{cls} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
            self.existing_boxes.extend(self.new_boxes)
            self.new_boxes.clear()
        print("[Info] 已保存（新增框已合并进已有框）")
    # ---------- 框选 ----------
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
    # ---------- 绘制 ----------
    def draw(self, show_cur_rect=True):
        canvas = self.cv_img.copy()
        for cls, xc, yc, w, h in self.existing_boxes:
            color = self.class_colors[cls % len(self.class_colors)]
            x1 = int((xc - w/2) * self.w)
            y1 = int((yc - h/2) * self.h)
            x2 = int((xc + w/2) * self.w)
            y2 = int((yc + h/2) * self.h)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            cv2.putText(canvas, str(cls), (x1, y1-4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        for cls, xc, yc, w, h in self.new_boxes:
            color = self.class_colors[cls % len(self.class_colors)]
            x1 = int((xc - w/2) * self.w)
            y1 = int((yc - h/2) * self.h)
            x2 = int((xc + w/2) * self.w)
            y2 = int((yc + h/2) * self.h)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            cv2.putText(canvas, str(cls), (x1, y1-4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        if show_cur_rect and getattr(self, '_cur_rect', None):
            x1, y1, x2, y2 = self._cur_rect
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0,0,255), 2)
        cur_color = self.class_colors[self.cur_class % len(self.class_colors)]
        cv2.rectangle(canvas, (0,0), (120,30), (0,0,0), -1)
        cv2.putText(canvas, f"Class: {self.cur_class}",
                    (5,22), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    cur_color, 2)
        return canvas
    # ---------- 键盘切类 ----------
    def change_class(self, key):
        if 48 <= key <= 57:
            self.cur_class = (key-48) % (MAX_CLASS+1)
        elif 97 <= key <= 122:
            self.cur_class = (key-97+10) % (MAX_CLASS+1)
        print(f"[Info] 当前类别切换为 {self.cur_class}")
    def set_class_by_name(self, name, names_list):
        try:
            idx = names_list.index(name)
            self.cur_class = idx
            print(f"[Info] 类别切换为 [{idx}] {name}")
        except ValueError:
            print(f"[Warning] 名称 `{name}` 不在类别列表中，保持原类别 {self.cur_class}")

# -------------------------------------------------
# 5️⃣ UI 层 – AnnotatorUI（加入 AutoDetect）
# -------------------------------------------------
class AnnotatorUI:
    def __init__(self, core: AnnotatorCore, class_names,
                 img_files, img_index, total_imgs,
                 img_root, lbl_root):
        # ---------- 基础属性 ----------
        self.core = core
        self.class_names = class_names
        self.img_files   = img_files
        self.img_index   = img_index
        self.total_imgs  = total_imgs
        self.img_root    = img_root
        self.lbl_root    = lbl_root
        self.result = None
        self.jump_to = None
        self._detect_queue = queue.Queue()
        self._detect_running = False

        # ---------- 加载模板 ----------
        self._templates = load_templates(TPL_DIR)
        print(f"[Info] 已加载 {len(self._templates)} 张模板用于自动检测")
        # （可选）打印模板尺寸
        for n, im in self._templates.items():
            h,w = im.shape[:2]
            print(f"  - {n}: {w}×{h}")

        # ---------- Tkinter 主窗口 ----------
        self.root = tk.Tk()
        self.root.title(f"Annotate – {os.path.basename(core.img_path)}  (X = quit)")

        # ---------- Canvas ----------
        self.canvas = tk.Canvas(self.root,
                                width=self.core.w,
                                height=self.core.h,
                                bg='black')
        self.canvas.grid(row=0, column=0, padx=5, pady=5)

        # ---------- 右侧按钮 ----------
        btn_frame = tk.Frame(self.root)
        btn_frame.grid(row=0, column=1, sticky='ns', padx=5, pady=5)
        ttk.Button(btn_frame, text="Undo",   width=10,
                    command=self.core.undo).grid(pady=2)
        ttk.Button(btn_frame, text="Clear",  width=10,
                    command=self.core.clear).grid(pady=2)
        ttk.Button(btn_frame, text="DelAll", width=10,
                    command=self.core.delete_all).grid(pady=2)
        ttk.Button(btn_frame, text="Save",   width=10,
                    command=self.core.save).grid(pady=2)
        ttk.Button(btn_frame, text="AutoDetect", width=10,
                    command=self._on_auto_detect).grid(pady=2)
        ttk.Button(btn_frame, text="Last",   width=10,
                    command=self._on_last).grid(pady=2)
        ttk.Button(btn_frame, text="Next",   width=10,
                    command=self._on_next).grid(pady=2)
        ttk.Button(btn_frame, text="Quit",   width=10,
                    command=self._on_quit).grid(pady=2)

        # ---------- 类别下拉框 ----------
        init_name = (self.class_names[self.core.cur_class]
                     if 0 <= self.core.cur_class < len(self.class_names)
                     else self.class_names[0])
        self.combo = ttk.Combobox(btn_frame,
                                  values=self.class_names,
                                  state='readonly',
                                  width=15)
        self.combo.set(init_name)
        self.combo.grid(pady=8)
        self.combo.bind("<<ComboboxSelected>>", self._on_class_selected)

        tk.Label(btn_frame, text="0‑9 / a‑z → change class",
                 fg='gray').grid(pady=10)

        # ---------- 缩略图条 ----------
        thumb_bar = tk.Frame(self.root)
        thumb_bar.grid(row=2, column=0, columnspan=2, pady=5)
        self.thumb_buttons = []
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

        # ---------- 事件绑定 ----------
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.root.bind("<Key>", self._on_key)
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

        # ---------- 刷新控制 ----------
        self._refresh_interval = 33
        self._thumb_cache = {}
        self._last_new_boxes = []

        self._refresh_ui()
        self._schedule_refresh()
        self.root.mainloop()

    # -------------------------------------------------
    # 按钮回调
    # -------------------------------------------------
    def _on_next(self):
        self.result = "next"
        self.root.destroy()
    def _on_last(self):
        self.result = "last"
        self.root.destroy()
    def _on_quit(self):
        # 先取消定时刷新
        if hasattr(self, '_refresh_job'):
            self.root.after_cancel(self._refresh_job)
        self.core.save()  # 自动保存，防止误删
        self.result = "quit"
        self.root.destroy()
        # self.core.save()
        # self.result = "quit"
        # self.root.destroy()

    # -------------------------------------------------
    # 类别下拉框回调
    # -------------------------------------------------
    def _on_class_selected(self, event):
        chosen_name = self.combo.get()
        self.core.set_class_by_name(chosen_name, self.class_names)

    # -------------------------------------------------
    # 缩略图点击跳转
    # -------------------------------------------------
    def _on_thumb_click(self, slot_idx):
        start, _ = self._calc_thumb_range()
        real_idx = start + slot_idx
        if real_idx < self.total_imgs:
            self.result = "jump"
            self.jump_to = real_idx
            self.root.destroy()

    # -------------------------------------------------
    # 跳转框回调
    # -------------------------------------------------
    def _on_jump(self):
        txt = self.jump_entry.get().strip()
        if not txt.isdigit():
            print("[Warning] 跳转输入必须是正整数")
            return
        target = int(txt) - 1
        if target < 0 or target >= self.total_imgs:
            print("[Warning] 跳转目标超出范围")
            return
        self.result = "jump"
        self.jump_to = target
        self.root.destroy()

    # -------------------------------------------------
    # 鼠标框选
    # -------------------------------------------------
    def _on_mouse_down(self, event):
        self.core.start_box(event.x, event.y)
    def _on_mouse_move(self, event):
        self.core.update_box(event.x, event.y)
    def _on_mouse_up(self, event):
        self.core.finish_box(event.x, event.y)

    # -------------------------------------------------
    # 键盘快捷键
    # -------------------------------------------------
    def _on_key(self, event):
        if event.char:
            self.core.change_class(ord(event.char.lower()))
        if event.keysym == 'Escape':
            self._on_quit()

    # -------------------------------------------------
    # 计算 7 张缩略图的范围
    # -------------------------------------------------
    def _calc_thumb_range(self):
        half = 3
        start = max(0, self.img_index - half)
        end = start + 7
        if end > self.total_imgs:
            end = self.total_imgs
            start = max(0, end - 7)
        return start, end

    # -------------------------------------------------
    # 缩略图更新（缓存版）
    # -------------------------------------------------
    def _update_thumbnails(self):
        start, _ = self._calc_thumb_range()
        for i, btn in enumerate(self.thumb_buttons):
            real_idx = start + i
            if real_idx >= self.total_imgs:
                btn.configure(image='', state=tk.DISABLED)
                btn.image = None
                continue

            if real_idx in self._thumb_cache:
                photo = self._thumb_cache[real_idx]
            else:
                txt_path = txt_path_from_img(
                    self.img_files[real_idx],
                    self.img_root,
                    self.lbl_root,
                )
                tmp_core = AnnotatorCore(
                    img_path=self.img_files[real_idx],
                    txt_path=txt_path,
                    default_class=self.core.cur_class,
                    class_colors=self.core.class_colors,
                )
                # ------------------- 关键改动 -------------------
                # 下面这行 **必须去掉**，否则会把当前图片的 new_boxes 复制到所有缩略图
                # tmp_core.new_boxes = self.core.new_boxes.copy()
                # ------------------------------------------------
                thumb_img = tmp_core.draw(show_cur_rect=False)
                thumb_small = cv2.resize(thumb_img, (80, 80), interpolation=cv2.INTER_AREA)
                thumb_rgb = cv2.cvtColor(thumb_small, cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(thumb_rgb)
                photo = ImageTk.PhotoImage(pil)
                self._thumb_cache[real_idx] = photo
            btn.configure(image=photo, state=tk.NORMAL)
            btn.image = photo

    # -------------------------------------------------
    # 主画面刷新（每帧）
    # -------------------------------------------------
    def _refresh_ui(self):
        cv_img = self.core.draw()
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        self.photo = ImageTk.PhotoImage(pil)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo)
        if self.core.new_boxes != self._last_new_boxes:
            self._thumb_cache.clear()
            self._last_new_boxes = self.core.new_boxes.copy()
        self._update_thumbnails()
    def _schedule_refresh(self):
        # self._refresh_ui()
        # self.root.after(self._refresh_interval, self._schedule_refresh)
        self._refresh_ui()
        # 把 after 的返回 id 保存下来，后面可以取消
        self._refresh_job = self.root.after(self._refresh_interval,
                                            self._schedule_refresh)

    # -------------------------------------------------
    # ---------- 自动检测 ----------
    # -------------------------------------------------
    def _on_auto_detect(self):
        if self._detect_running:
            print("[Info] 正在检测，请稍候…")
            return
        self._detect_running = True
        threading.Thread(target=self._run_detection_thread, daemon=True).start()
        self.root.after(100, self._check_detection_result)

    def _run_detection_thread(self):
        try:
            frame_gray = cv2.cvtColor(self.core.cv_img, cv2.COLOR_BGR2GRAY)
            det_res = detect_multi(
                frame_gray,
                self._templates,
                self.class_names,
                ratio_thr=RATIO_THR,
                min_match=MIN_MATCH,
                ransac_thr=RANSAC_THR,
                scale_factor=SCALE_FACTOR,
                max_instances=20,
                nms_iou=NMS_IOU,
            )
            self._detect_queue.put(det_res)
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
            print(f"[Info] 检测到 {len(dets)} 个实例，写入标注（放入 new_boxes）")
            img_h, img_w = self.core.h, self.core.w
            for bbox, class_id, score in dets:
                x, y, w, h = bbox
                xc = (x + w / 2.0) / img_w
                yc = (y + h / 2.0) / img_h
                nw = w / img_w
                nh = h / img_h

                self.core.new_boxes.append((class_id, xc, yc, nw, nh))
                # --------------------
            # 刷新 UI（包括缩略图会同步显示新框）
            self._refresh_ui()

# -------------------------------------------------
# 6️⃣ 主入口（遍历图片、打开 UI）
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

    class_names = load_class_names(YAML_PATH)
    print(f"[Info] 已读取 {len(class_names)} 个类别（来自 {YAML_PATH}）")
    class_colors = generate_color_map(len(class_names))

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

        ui = AnnotatorUI(core, class_names,
                         img_files, idx, total_imgs,
                         img_root, lbl_root)   # ← 传根目录

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
        idx = max(0, min(idx, total_imgs-1))
    print('\n✅ 所有图片已完成标注！')

if __name__ == '__main__':
    main()