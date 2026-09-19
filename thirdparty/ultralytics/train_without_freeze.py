from ultralytics import YOLO
import os
import warnings

warnings.filterwarnings('ignore')      # 可选：关闭不必要的警告

# 必须在最顶部（在任何 import 之前）声明 start method（可选）
# from multiprocessing import freeze_support   # 只在打包 exe 时需要
import torch.multiprocessing as mp
mp.set_start_method('spawn', force=True)   # Windows 推荐



if __name__ == '__main__':

    model = YOLO('my_yolov8.yaml')  # 自定义结构

    print('=== model (high‑level) ===')
    print(model)  # 包含模型名称、训练/推理模式等信息
    print('\n=== model.model (nn.Module) ===')
    model = YOLO("./yolov8m.pt")
    # 训练
    results = model.val(
        data='./YOLODataset/dataset.yaml',               # 数据配置
        batch=1,
        imgsz=640,
        lr0=0.001,
        optimizer='SGD',
        cos_lr=True,
        patience=10,
        project='runs/detect',          # 输出根目录
        name='my_yolov8n_finetune',    # 子文件夹
        device='0'                      # GPU id，若为 CPU 可写 'cpu'
        ,amp = False
    )

    # 打印训练日志（每个 epoch 的指标）
    print(results)


    # model.train(data='coco128.yaml', epochs=100, imgsz=640, batch=16,amp = False, device=0)
    # results = model.train(data="coco128.yaml", epochs=3)  # 训练模型
    # results = model.val()  # 在验证集上评估模型性能
    # results = model("https://ultralytics.com/images/bus.jpg")  # 预测图像

    # results = model.predict(source="Temptestimages/bus.jpg", save=True, imgsz=640, conf=0.25)