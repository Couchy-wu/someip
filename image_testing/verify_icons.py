# verify_icons.py
# -*- coding: utf-8 -*-
"""
根据 JSON 配置文件验证单张图片中图标是否一致。
"""

import json
import os
from typing import Any, Dict, List

import numpy as np
from PIL import Image

# --------------------------------------------------------------
#  第三方工具：请确保下面的模块能够被导入
# --------------------------------------------------------------
# 该函数在 image_testing/image_similarity.py 中实现，
# 用来比较裁剪后图像的 dHash 与预先保存的 hash。
try:                                     # 包导入优先
    from .image_similarity import compare_with_precomputed_hash  # noqa: E402
except ImportError:                      # 脚本模式回退
    from image_similarity import compare_with_precomputed_hash  # noqa: E402


def _load_json(json_path: str) -> Dict[str, Any]:
    """
    读取 JSON 配置文件并返回字典。

    参数
    ----
    json_path : str
        JSON 文件的完整路径。

    返回
    ----
    dict
        以配置键名为主键的字典。
    """
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_image_against_json(
    image_path: str,
    json_path: str,
    config_key: str,
    thr: int,
) -> None:
    """
    一次读取 JSON、一次读取图片、一次完成全部图标校验。

    参数
    ----
    image_path : str
        待检测的图片路径（如 `SQ_5_6_003.png`）。
    json_path : str
        JSON 配置文件路径。
    config_key : str
        JSON 中对应的键名（例如 `"SQ_5_4_1_6_001"`）。
    thr : int
        当图标 `is_only_image=True` 时使用的阈值（取值 0‑100，默认 80），
        `is_only_image=False` 时阈值强制为 40。

    说明
    ----
    - 若 `config_key` 不在 JSON 中，会直接报错并返回。
    - 若图片读取失败，会报错并返回。
    - 对每个图标，会打印「一致」或「不一致」信息，并在全部结束后输出「合格」或
      「不合格：<列表>」。
    """
    # 1️⃣ 读取 JSON（一次 I/O）
    data = _load_json(json_path)

    # 2️⃣ 检查配置键是否存在
    if config_key not in data:
        print(f"❌ 配置键名 '{config_key}' 在 JSON 文件中未找到对应配置。")
        return

    # 3️⃣ 加载图片
    try:
        img = Image.open(image_path)
        img_array = np.array(img)
    except Exception as e:
        print(f"❌ 无法加载图像 {image_path}: {e}")
        return

    # 4️⃣ 取出该键对应的图标列表
    icon_list = data[config_key]

    mismatched_icons: List[str] = []

    print(f"🔍 正在验证图像 (Key: {config_key}): {os.path.basename(image_path)}")

    # 5️⃣ 逐个图标进行校验
    for icon in icon_list:
        name = icon["name"]
        top_left = icon["top_left"]
        bottom_right = icon["bottom_right"]
        expected_hash = icon["ui_hash"]
        is_only_image = icon["is_only_image"]

        # JSON 中坐标顺序为 (x, y) → NumPy 切片需使用 (y, x)
        y1, x1 = top_left[1], top_left[0]
        y2, x2 = bottom_right[1], bottom_right[0]

        # ---------- 边界检查 ----------
        if y1 >= y2 or x1 >= x2:
            print(
                f"⚠️  跳过无效区域 {name}: "
                f"top_left={top_left}, bottom_right={bottom_right}"
            )
            continue

        try:
            # 裁剪对应区域
            cropped = img_array[y1:y2, x1:x2]

            # 根据是否纯图片动态决定阈值
            effective_thr = thr if is_only_image else 40

            # 调用第三方对比函数
            is_same = compare_with_precomputed_hash(
                cropped,
                precomputed_hash=expected_hash,
                thr=effective_thr,
            )

            if is_same:
                print(f"✅ 一致：{name}")
            else:
                mismatched_icons.append(name)
                print(f"❌ 不一致：{name}")

        except Exception as e:
            print(f"❌ 处理图标 {name} 时出错：{e}")
            mismatched_icons.append(name)

    # 6️⃣ 最终结果输出
    if not mismatched_icons:
        print("合格")
    else:
        print(f"不合格：{', '.join(mismatched_icons)}")


# --------------------------------------------------------------
# 直接运行脚本时的示例（保持与原文件相同的入口）
# --------------------------------------------------------------
if __name__ == "__main__":
    # 请根据实际路径自行修改以下参数
    verify_image_against_json(
        image_path="output/nosuccess/SQ_5_4_1_6_005_20260323_143707_550.png",
        json_path="TestcaseCollection/测试校验功能_ImageData.json",
        config_key="SQ_5_4_1_6_004",
        thr=80,
    )