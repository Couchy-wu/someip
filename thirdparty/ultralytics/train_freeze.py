# -*- coding: utf-8 -*-
"""
在 Windows 环境下安全启动 YOLOv8 微调（可选），
训练结束后（或直接使用已有权重）对验证集进行一次前向推理，
- 使用与 model.val 完全相同的阈值与过滤条件；
- 自动保存的图片（val_batch0_pred.jpg）即为最终可视化；
- 同时把每张图片的过滤后框保存为 JSON‑Lines。
"""

import os, json, warnings, pathlib, torch, yaml, multiprocessing as mp, cv2

from modelscope.models.cv.video_depth_estimation.utils.image_gt import flip_lr

warnings.filterwarnings('ignore')

# --------------------------------------------------------------
# 0️⃣ 必须在任何 import 之前设定 multiprocessing start 方法
# --------------------------------------------------------------
mp.set_start_method('spawn', force=True)   # Windows 推荐使用 spawn

# --------------------------------------------------------------
# 1️⃣ 关闭 Ultralytics 自动下载（防止网络被防火墙拦截）
# --------------------------------------------------------------
os.environ["ULTRALYTICS_DISABLE_AUTO_DOWNLOAD"] = "1"

# --------------------------------------------------------------
# 2️⃣ 导入 Ultralytics 主类
# --------------------------------------------------------------
from ultralytics import YOLO

# --------------------------------------------------------------
# 3️⃣ 参数（可自行在命令行里覆盖）
# --------------------------------------------------------------
def get_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="YOLOv8 微调（可选） + 验证（统一可视化 & JSON‑Lines）"
    )
    # ------------------- 是否进行训练 -------------------
    parser.add_argument(
        "--do_train",
        type=lambda x: (str(x).lower() == 'true'),
        default=True,
        help="是否执行微调（训练）。若为 False，则直接使用 --weights 指定的模型进行推理/验证。"
    )
    # ------------------- 基础路径 -------------------
    parser.add_argument(
        "--weights",
        type=str,
        default=r"best.pt",
        help="官方预训练权重路径（训练阶段使用）或任意 .pt 权重（在 --do_train=False 时使用）。"
    )
    parser.add_argument(
        "--data",
        type=str,
        default=r"YOLODataset/dataset.yaml",
        help="dataset.yaml（必须包含 val: 条目）。"
    )
    # ------------------- 训练超参数 -------------------
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--lr0", type=float, default=0.001)
    parser.add_argument("--optimizer", type=str, default="SGD")
    parser.add_argument("--cos_lr", action="store_true", default=True)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--freeze", type=str, default="backbone",
                        help="冻结前 N 层，只微调检测头。")
    # ------------------- 推理 & 过滤（与 model.val 保持一致） -------------------
    parser.add_argument("--conf", type=float, default=0.5,
                        help="阈值（conf）用于 model.val 与手动过滤，建议与 min_conf 相同。")
    parser.add_argument("--iou", type=float, default=0.5,
                        help="NMS 的 IoU 阈值。")
    parser.add_argument("--min_conf", type=float, default=0.5,
                        help="保存 JSON‑Lines 时仅保留置信度 >= min_conf 的框（与 conf 保持一致）。")
    parser.add_argument("--min_area", type=float, default=0.0,
                        help="保存 JSON‑Lines 时仅保留归一化面积 >= min_area 的框。")
    parser.add_argument(
        "--classes",
        type=int,
        nargs="*",
        default=None,
        help="只保留这些类别（整数 id），若不提供则保留全部。"
    )
    parser.add_argument("--visualize", action="store_true", default=True,
                        help="若开启，则保存只含过滤后框的可视化图片（使用 model.val 自动保存）。")
    # ------------------- 输出路径 -------------------
    parser.add_argument("--project", type=str, default="runs/detect",
                        help="根目录，保存指标、JSON‑Lines、可视化图片。")
    parser.add_argument("--name", type=str, default=None,
                        help="子文件夹名，若 None 使用权重父文件夹名。")
    parser.add_argument("--out_prefix", type=str, default="",
                        help="输出 JSON‑Lines 文件名前缀（如 'exp1_'）。")
    parser.add_argument("--workers", type=int, default=4,
                        help="DataLoader 工作线程数（Windows 建议 0）。")
    return parser.parse_args()


# --------------------------------------------------------------
# 4️⃣ 辅助函数：过滤框（用于 JSON‑Lines）
# --------------------------------------------------------------
def filter_boxes(cls_arr, conf_arr, xywhn_arr, args):
    filtered = []
    for c, p, b in zip(cls_arr, conf_arr, xywhn_arr):
        if p < args.min_conf:
            continue
        if args.classes is not None and int(c) not in args.classes:
            continue
        area = b[2] * b[3]   # 归一化面积
        if area < args.min_area:
            continue
        filtered.append({
            "class": int(c),
            "conf": float(p),
            "bbox": [float(v) for v in b.tolist()]   # [x_center, y_center, w, h] 归一化
        })
    return filtered


# --------------------------------------------------------------
# 5️⃣ 主函数
# --------------------------------------------------------------
def main():
    args = get_args()

    # ------------------- 项目根目录 -------------------
    ROOT = pathlib.Path(__file__).parent.resolve()
    print("项目根目录 :", ROOT)

    # ------------------- 检查路径 -------------------
    PRETRAINED_PT = pathlib.Path(args.weights).resolve()
    if not PRETRAINED_PT.is_file():
        raise FileNotFoundError(f"权重文件不存在 → {PRETRAINED_PT}")

    DATA_CFG = pathlib.Path(args.data).resolve()
    if not DATA_CFG.is_file():
        raise FileNotFoundError(f"dataset.yaml 未找到 → {DATA_CFG}")

    # ------------------- 设备 -------------------
    DEVICE = "0" if torch.cuda.is_available() else "cpu"
    print("\n使用设备 :", DEVICE)

    # ------------------- 训练（可选） -------------------
    if args.do_train:
        print("\n=== 加载官方预训练模型进行微调 ===")
        model = YOLO(str(PRETRAINED_PT))
        print("\n✅ 官方预训练模型已加载")

        print("\n=== 开始微调（只训练检测头） ===")
        model.train(
            data=str(DATA_CFG),
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            lr0=args.lr0,
            optimizer=args.optimizer,
            cos_lr=args.cos_lr,
            patience=args.patience,
            project=str(ROOT / "runs" / "detect"),
            name="my_yolov8m_finetune_head",
            device=DEVICE,
            amp=False,
            workers=args.workers,
            freeze=args.freeze,
            verbose=True,
            fliplr=0.0,
            flipud=0.0
        )
        print("\n=== 微调结束 ===")
        # 加载微调后得到的 best.pt
        best_pt = pathlib.Path(ROOT) / "runs" / "detect" / "my_yolov8m_finetune_head" / "weights" / "best.pt"
        if not best_pt.is_file():
            raise FileNotFoundError(f"训练结束后未找到 best.pt → {best_pt}")
        print(f"\n加载微调后的权重：{best_pt}")
        model = YOLO(str(best_pt))
    else:
        print("\n=== 跳过训练，直接使用提供的权重 ===")
        model = YOLO(str(PRETRAINED_PT))

    # ------------------- 读取 dataset.yaml，获取 val 文件夹 -------------------
    with open(str(DATA_CFG), encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    root_dir = pathlib.Path(cfg['path'])
    val_folder = root_dir / cfg['val']
    if not val_folder.is_dir():
        raise FileNotFoundError(f"val 文件夹不存在 → {val_folder}")

    # ------------------- 自动生成子文件夹名称 -------------------
    if args.name is None:
        args.name = pathlib.Path(PRETRAINED_PT).parent.name   # 使用权重所在的父文件夹名

    save_dir = pathlib.Path(args.project) / args.name
    os.makedirs(save_dir, exist_ok=True)

    # ------------------- 统一阈值、IoU -------------------
    # 这里我们把 `model.val` 的 conf 与我们手动过滤的 min_conf 同步
    # 注意：model.val 的内部阈值是 `conf`，所以直接把 args.conf 设为我们想要的阈值
    val_conf = args.conf   # 与前向推理使用同一阈值

    # ------------------- 计算并保存整体验证指标（使用统一阈值） -------------------
    print("\n=== 计算整体验证指标（val） ===")
    val_res = model.val(
        data=str(DATA_CFG),
        batch=args.batch,
        imgsz=args.imgsz,
        device=DEVICE,
        conf=val_conf,          # 与后续推理保持一致
        iou=args.iou,
        half=False,
        save_json=True,         # 保存 COCO‑style predictions.json
        save=args.visualize,    # 开启可视化保存（会生成 val_batch0_pred.jpg 等）
        project=str(save_dir),  # 保存目录统一
        name="val_metrics"
    )
    print("\n=== 验证指标概览 ===")
    print(val_res)


# --------------------------------------------------------------
# 入口点（Windows 必须使用 if __name__ == '__main__'）
# --------------------------------------------------------------
if __name__ == "__main__":
    mp.freeze_support()   # 对于打包 .exe 可选，安全起见保留
    main()