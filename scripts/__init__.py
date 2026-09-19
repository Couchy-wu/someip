# -*- coding: utf-8 -*-
"""scripts —— 面向使用者的独立脚本（非库代码）

约定：
  · 这里的脚本可以带 `if __name__ == "__main__"`、可以解析命令行参数；
  · 但它们不属于业务包，不能被 `main.py` 导入；
  · 运行方式：`python scripts/<脚本名>.py`（根目录只保留 main.py 一个入口）。

现有脚本：
  ocr_icon_test.py  OCR + YOLO 图标识别自测（原根目录 image_test.py）
  yolo_train.py     YOLOv8 微调/验证（原根目录 train_freeze.py）
"""
