

import os
os.environ["PADDLE_DISABLE_AUTO_DOWNLOAD"] = "1"


def _ensure_dummy_font():
    # Windows: %USERPROFILE%\.paddlex\fonts
    # Linux/macOS: ~/.paddlex/fonts
    user_home = os.path.expanduser("~")
    font_dir = os.path.join(user_home, ".paddlex", "fonts")
    os.makedirs(font_dir, exist_ok=True)

    # 两个库里会请求的字体文件名
    for fname in ("PingFang-SC-Regular.ttf", "simfang.ttf"):
        font_path = os.path.join(font_dir, fname)
        if not os.path.exists(font_path):
            # 创建一个 **空文件**（0 字节），足以让 paddlex 认为已经有本地字体
            open(font_path, "wb").close()

_ensure_dummy_font()
import warnings
from paddleocr import PaddleOCR
warnings.filterwarnings("ignore", category=DeprecationWarning)


ocr = PaddleOCR(
    text_detection_model_dir="./inference/PP-OCRv5_server_det_infer",  # 指定本地模型路径
    text_recognition_model_dir="./inference/PP-OCRv5_server_rec_infer",  # 识别模型路径
    use_textline_orientation=False,  # 可选，分类模型路径
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    device="cpu"
)

result = ocr.ocr("test.jpg", cls=False)
print(result)


#
# # 方法 1：直接读取 PaddleOCR 包自带的 __version__ 变量
# import paddleocr
# print("PaddleOCR version :", paddleocr.__version__)   # 例如：2.7.0
#
# # 方法 2：从 paddle 包本身读取（PaddleOCR 依赖的底层框架）
# import paddle
# print("PaddlePaddle version :", paddle.__version__)   # 例如：2.5.2
# import paddlex
#
# print("Paddlex version :", paddlex.__version__)   # 例如：2.5.2