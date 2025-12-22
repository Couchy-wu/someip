
import pathlib
# Initialize PaddleOCR instance
import os
import json
from pathlib import Path
from paddleocr import PaddleOCR
import time
import sys
import cv2
import numpy as np
import pandas as pd
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
YOLO_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "YOLO框架","ultralytics-8.3.217"))
OCR_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "PaddleOCR-main"))
os.environ["PADDLE_DISABLE_AUTO_DOWNLOAD"] = "1"
os.environ["PADDLE_MODEL_HOME"] = OCR_DIR


sys.path.append(YOLO_DIR)
sys.path.append(OCR_DIR)

from ultralytics import YOLO

import warnings
warnings.filterwarnings('ignore')
import torch.multiprocessing as mp
mp.set_start_method('spawn', force=True)   # Windows 推荐

def to_builtin(o):
    if isinstance(o, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(o)
    if isinstance(o, (np.floating, np.float64, np.float32, np.float16)):
        return float(o)
    if isinstance(o, (np.bool_, np.bool)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (pd.Series, pd.DataFrame)):
        return o.to_dict(orient='records')   # 轉成 list of dict
    if isinstance(o, dict):
        return {k: to_builtin(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [to_builtin(v) for v in o]
    return o

def save_json(All_message_json_path, ALL_message_dict, mode = "w"):
    json_path = Path(All_message_json_path)

    with json_path.open( mode, encoding="utf-8") as fp:
        json.dump(ALL_message_dict, fp, ensure_ascii=False)
    print(f"[INFO] 已写入 {json_path.resolve()}，共 {len(ALL_message_dict)} 条记录")
#
# def read_img_cv(path: str) -> np.ndarray:
#     # 读取原始字节流（np.fromfile 更快，因为直接映射到内存）
#     data = np.fromfile(path, dtype=np.uint8)
#     # 解码为 BGR ndarray，shape = (H, W, 3)
#     img_bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
#     # 如需 RGB，可在后面一次性转换
#     img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
#     return img_rgb







if __name__ == '__main__':

    ##路径信息
    ################################################
    yaml_path = os.path.join(YOLO_DIR , 'my_yolov8.yaml')
    pt_path = os.path.join(YOLO_DIR , 'best.pt')
    # data_yaml_path = os.path.join(YOLO_DIR , 'coco128.yaml')
    test_images_path = os.path.join(YOLO_DIR, 'ARHUD_frames')
    output_dir = "./image_result/output_images"
    crop_dir = "./image_result/crop_images"
    OCR_MODEL_ROOT = r"./PaddleOCR-main/model"
    DET_MODEL_DIR = os.path.join(OCR_MODEL_ROOT, "PP-OCRv5_server_det_infer")  # e.g. det_infer/
    REC_MODEL_DIR = os.path.join(OCR_MODEL_ROOT, "PP-OCRv5_server_rec_infer")  # e.g. rec_infer/
    CLS_MODEL_DIR = os.path.join(OCR_MODEL_ROOT, "cls")  # 若不需要方向分类可不写
    All_message_json_path = "./image_result/all_message.json"
    test_images_name = os.listdir(test_images_path)
    test_image_path_list = [os.path.join(test_images_path, i) for i in test_images_name]

    ################################################


    ##模型结构
    ################################################
    model = YOLO(yaml_path)  # 自定义结构
    model.overrides['save'] = False
    # print('=== model (high‑level) ===')
    # print(model)  # 包含模型名称、训练/推理模式等信息
    # print('\n=== model.model (nn.Module) ===')

    model = YOLO(pt_path)  ##加载模型

    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        # text_det_box_thresh= 0.1,
        # text_rec_score_thresh=0.1,

        text_detection_model_dir=DET_MODEL_DIR,  # 指定本地模型路径
        text_recognition_model_dir=REC_MODEL_DIR,  # 识别模型路径
        device="gpu",

    )

    ALL_message_dict= []  #
    ################################################



    ##模型训练
    ################################################
    # model.train(data=data_yaml_path, epochs=100, imgsz=640, batch=16,amp = False, device=0)
    # results = model.train(data=data_yaml_path, epochs=3,amp=False)  # 训练模型
    # results = model.val()  # 在验证集上评估模型性能
    # results = model("https://ultralytics.com/images/bus.jpg")  # 预测图像
    ################################################


    # 目标检测输出
    num = 1
    ################################################
    for test_image_path in test_image_path_list:
        all_message_item = {"whole_frame_id":"", "frame_name": "", "class": [], "text": []}

        all_message_item["whole_frame_id"]= num


        img = cv2.imread(test_image_path)
        img_orgin = cv2.imread(test_image_path)
        results = model.predict(source=test_image_path, save=False, imgsz=640, conf=0.25)
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
            whole_image_name = test_images_name[(num-1)][:-4]
            folder_path = os.path.join(crop_dir,whole_image_name)  ####!!!!
            if not os.path.isdir(folder_path):  # 或者 os.path.exists(folder_path)
                os.makedirs(folder_path)  # 自动创建所有缺失的父目录
                print(f"创建目录: {folder_path}")
            else:
                print(f"目录已存在: {folder_path}")
            save_crop_path = folder_path+"/"+f"{name}_{i}.png"
            crops_list.append(save_crop_path)
            cv2.imwrite(save_crop_path,crop)


            ##小图输入ocr模型
        for i in range(len(crops_list)):

            image_path =  crops_list[i]
            # time_start = time.time()
            # img = read_img_cv(i)
            result = ocr.predict(input=image_path)
            # result = ocr.ocr(img=img)
            # time_end = time.time()
            all_message_item["class"].append(cls_ids[i])

            # _time = time_end - time_start
            # Visualize the results and save the JSON results
            for res in result:
                # res.print()
                # print(res["rec_texts"], _time)
                print(res["rec_texts"])

                all_message_item["text"].append(res["rec_texts"])

                res.save_to_img("output_ocr")
                res.save_to_json("output_ocr")

        clean_dict = to_builtin(all_message_item)
        ALL_message_dict.append(clean_dict)
        num = num + 1



save_json(All_message_json_path,ALL_message_dict)









        #     # 绘制矩形
        #     cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
        #
        #     # 在左上角写上 “类别 conf”
        #     label = f"{name} {confs[i]:.2f}"
        #     # 为了让文字更清晰，先画一个黑色底框
        #     (label_width, label_height), baseline = cv2.getTextSize(
        #         label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        #     )
        #     # 文字背景矩形（左上角）
        #     cv2.rectangle(
        #         img,
        #         (x1, y1 - label_height - baseline),
        #         (x1 + label_width, y1),
        #         color,
        #         -1,  # -1 表示填充
        #     )
        #     # 文字本身（白色）
        #     cv2.putText(
        #         img,
        #         label,
        #         (x1, y1 - baseline),
        #         cv2.FONT_HERSHEY_SIMPLEX,
        #         0.5,
        #         (255, 255, 255),  # 白色文字
        #         1,
        #         cv2.LINE_AA,
        #     )
        #
        # # 6) 保存绘制后的图片
        # save_path = os.path.join(output_dir , "bus.jpg")
        # cv2.imwrite(save_path, img)























