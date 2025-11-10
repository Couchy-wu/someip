# Initialize PaddleOCR instance
import os
os.environ["PADDLE_DISABLE_AUTO_DOWNLOAD"] = "1"
os.environ["PADDLE_MODEL_HOME"] = r"E:/hud自动化台架/PaddleOCR-main/PaddleOCR-main"
from paddleocr import PaddleOCR
import time





MODEL_ROOT = r"./model"

DET_MODEL_DIR = os.path.join(MODEL_ROOT, "PP-OCRv5_server_det_infer")   # e.g. det_infer/
REC_MODEL_DIR = os.path.join(MODEL_ROOT, "PP-OCRv5_server_rec_infer")   # e.g. rec_infer/
CLS_MODEL_DIR = os.path.join(MODEL_ROOT, "cls")   # 若不需要方向分类可不写




ocr = PaddleOCR(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_detection_model_dir=DET_MODEL_DIR,  # 指定本地模型路径
    text_recognition_model_dir=REC_MODEL_DIR,  # 识别模型路径

)


# Run OCR inference on a sample image
test_image_path = "./test_images/"

images_list = os.listdir(test_image_path)
for i in images_list:
    image_path = test_image_path+i
    time_start = time.time()
    result = ocr.predict(input=image_path)
    time_end = time.time()
    _time = time_end - time_start

# Visualize the results and save the JSON results
    for res in result:
        # res.print()
        print(res["rec_texts"],_time)

        res.save_to_img("output")
        res.save_to_json("output")