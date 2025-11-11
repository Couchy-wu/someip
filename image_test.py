

# Initialize PaddleOCR instance
import os
os.environ["PADDLE_DISABLE_AUTO_DOWNLOAD"] = "1"
os.environ["PADDLE_MODEL_HOME"] = r"./PaddleOCR-main"
from paddleocr import PaddleOCR
import time
import sys
import cv2

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
YOLO_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "YOLO框架","ultralytics-8.3.217"))
sys.path.append(YOLO_DIR)

from ultralytics import YOLO

import warnings
warnings.filterwarnings('ignore')
import torch.multiprocessing as mp
mp.set_start_method('spawn', force=True)   # Windows 推荐


if __name__ == '__main__':

    ##路径信息
    ################################################
    yaml_path = os.path.join(YOLO_DIR , 'my_yolov8.yaml')
    pt_path = os.path.join(YOLO_DIR , 'yolov8m.pt')
    data_yaml_path = os.path.join(YOLO_DIR , 'coco128.yaml')
    test_images_path = os.path.join(YOLO_DIR, 'Temptestimages/bus.jpg')
    output_dir = "./output_images"
    crop_dir = "./crop_images"
    ################################################


    ##模型结构
    ################################################
    model = YOLO(yaml_path)  # 自定义结构
    model.overrides['save'] = False
    # print('=== model (high‑level) ===')
    # print(model)  # 包含模型名称、训练/推理模式等信息
    # print('\n=== model.model (nn.Module) ===')

    model = YOLO(pt_path)  ##加载模型
    ################################################



    ##模型训练
    ################################################
    # model.train(data=data_yaml_path, epochs=100, imgsz=640, batch=16,amp = False, device=0)
    # results = model.train(data=data_yaml_path, epochs=3,amp=False)  # 训练模型
    # results = model.val()  # 在验证集上评估模型性能
    # results = model("https://ultralytics.com/images/bus.jpg")  # 预测图像
    ################################################


    # 目标检测输出
    ################################################
    img = cv2.imread(test_images_path)
    img_orgin = cv2.imread(test_images_path)
    results = model.predict(source=test_images_path, save=False, imgsz=640, conf=0.25)
    r = results[0]

    # 8.1 原始图像（NumPy, BGR）
    # img = r.orig_img  # shape = (H, W, 3), dtype=uint8

    # 8.2 检测框（tensor）——左上 (x1, y1), 右下 (x2, y2)
    boxes_xyxy = r.boxes.xyxy.cpu().numpy()  # (N, 4)   float32
    # 8.3 检测框（tensor）——中心 (x, y), 宽, 高
    boxes_xywh = r.boxes.xywh.cpu().numpy()  # (N, 4)

    # 8.4 置信度
    confs = r.boxes.conf.cpu().numpy()  # (N,)

    # 8.5 类别 id（0‑based）以及对应的文字名称
    cls_ids = r.boxes.cls.cpu().numpy().astype(int)  # (N,)
    # 类别名称映射（模型自带）
    names = r.names
    cls_names = [names[i] for i in cls_ids]  # List[str]
    names = r.names  # dict: {0: 'person', 1: 'bicycle', ...}


    ##小图列表
    crops_list=[]

    for i in range(len(cls_ids)):
        name = cls_names[i]
        x1,y1,x2,y2 = boxes_xyxy[i]
        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))


        # 颜色：随机或固定，这里用固定蓝色 (B,G,R) = (255,0,0)
        color = (255, 0, 0)          # 蓝色（OpenCV BGR）
        thickness = 2                # 线宽


       #存储小图
        crop = img_orgin[y1:y2,x1:x2]
        folder_path = os.path.join(crop_dir,"bus")
        if not os.path.isdir(folder_path):  # 或者 os.path.exists(folder_path)
            os.makedirs(folder_path)  # 自动创建所有缺失的父目录
            print(f"创建目录: {folder_path}")
        else:
            print(f"目录已存在: {folder_path}")
        save_crop_path = folder_path+"/"+f"{name}_{i}.png"
        crops_list.append(save_crop_path)
        cv2.imwrite(save_crop_path,crop)



        # 绘制矩形
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

        # 在左上角写上 “类别 conf”
        label = f"{name} {confs[i]:.2f}"
        # 为了让文字更清晰，先画一个黑色底框
        (label_width, label_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        # 文字背景矩形（左上角）
        cv2.rectangle(
            img,
            (x1, y1 - label_height - baseline),
            (x1 + label_width, y1),
            color,
            -1,  # -1 表示填充
        )
        # 文字本身（白色）
        cv2.putText(
            img,
            label,
            (x1, y1 - baseline),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),  # 白色文字
            1,
            cv2.LINE_AA,
        )

    # 6) 保存绘制后的图片
    save_path = os.path.join(output_dir , "bus.jpg")
    cv2.imwrite(save_path, img)























