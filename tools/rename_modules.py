#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/rename_modules.py —— 目录/文件重命名映射表与执行脚本
============================================================
用途：把语义模糊的目录/文件名统一改为"见名知意"的英文命名，
      并同步更新全项目内的 import 与字符串引用。

用法：
    python tools/rename_modules.py --dry-run    # 预览（不改动）
    python tools/rename_modules.py --apply      # 执行（git mv + 引用替换）

安全措施：
    · 目录/文件移动使用 `git mv`（保留历史）
    · 引用替换只针对"模块引用"模式（import/from/字符串模块名），避免误伤
    · 执行前打印完整映射表；建议先 --dry-run
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------------ 映射表

# 1) 目录重命名（自有目录 + 乱码第三方目录）
DIR_RENAMES: list[tuple[str, str]] = [
    ("GuiFunction",       "gui_handlers"),      # 主界面各功能的事件处理器
    ("OtherGui",          "can_gui"),           # CAN 收发 GUI
    ("CanDataProcessing", "can_data_tools"),    # CAN 数据解析 / 检索工具
    ("ImageTest",         "image_testing"),     # 图像测试（图标识别/生成/相似度）
    ("CameraUtils",       "camera_tools"),      # 相机标定 / 图像增强
    ("Simple_Tools",      "misc_tools"),        # 杂项小工具
    ("Auto label",        "auto_labeling"),     # 自动标注（原目录名带空格，无法作为包导入）
    ("YOLO+=+_",          "yolo_framework"),    # 原名乱码，代码中引用的 "YOLO框架" 已失效
]

# 2) 文件重命名（相对项目根）
FILE_RENAMES: list[tuple[str, str]] = [
    # ---- 根目录 ----
    ("zlgcan.py",              "zlgcan_driver.py"),        # ZLG CAN 驱动绑定
    ("mylog.py",               "log_setup.py"),            # 日志初始化
    ("train_freeze.py",        "yolo_train.py"),           # YOLO 训练脚本
    ("image_test.py",          "ocr_icon_test.py"),        # OCR + YOLO 图标识别测试

    # ---- gui_handlers/（原 GuiFunction）----
    ("GuiFunction/file_updater.py",           "gui_handlers/testcase_menu.py"),
    ("GuiFunction/file_handler.py",           "gui_handlers/testcase_upload.py"),
    ("GuiFunction/delete_handler.py",         "gui_handlers/testcase_delete.py"),
    ("GuiFunction/view_case_handler.py",      "gui_handlers/testcase_open_table.py"),
    ("GuiFunction/view_case_processor.py",    "gui_handlers/testcase_view_log.py"),
    ("GuiFunction/image_handler.py",          "gui_handlers/image_open.py"),
    ("GuiFunction/video_processor.py",        "gui_handlers/video_extract_frames.py"),
    ("GuiFunction/video_processor_ffmpeg.py", "gui_handlers/video_extract_ffmpeg.py"),
    ("GuiFunction/image_player.py",           "gui_handlers/image_sequence_player.py"),
    ("GuiFunction/can_testcase_processor.py", "gui_handlers/can_testcase_parser.py"),
    ("GuiFunction/matrix_to_csv.py",          "gui_handlers/signal_matrix_to_csv.py"),
    ("GuiFunction/binhex_gui.py",             "gui_handlers/can_data_generator.py"),

    # ---- can_gui/（原 OtherGui）----
    ("OtherGui/test_can_gui.py",              "can_gui/can_send_receive_gui.py"),

    # ---- can_data_tools/（原 CanDataProcessing）----
    ("CanDataProcessing/can_testcase_runner.py", "can_data_tools/testcase_runner.py"),
    ("CanDataProcessing/find_can_from_csv.py",   "can_data_tools/find_can_id_from_csv.py"),
    ("CanDataProcessing/find_subid.py",          "can_data_tools/find_sub_id.py"),

    # ---- image_testing/（原 ImageTest）----
    ("ImageTest/image_generator.py",          "image_testing/test_image_generator.py"),
    ("ImageTest/image_similarity_dhash.py",   "image_testing/image_similarity.py"),
    ("ImageTest/verify_icons_by_json.py",     "image_testing/verify_icons.py"),

    # ---- camera_tools/（原 CameraUtils）----
    ("CameraUtils/perspective_calibrator.py", "camera_tools/perspective_calibration.py"),
    ("CameraUtils/image_enhancer.py",         "camera_tools/image_enhancement.py"),
    ("CameraUtils/camera_viewer.py",          "camera_tools/camera_preview.py"),
    ("CameraUtils/test8wending.py",           "camera_tools/stability_test.py"),

    # ---- misc_tools/（原 Simple_Tools）----
    ("Simple_Tools/create_gif.py",            "misc_tools/gif_creator.py"),
    ("Simple_Tools/image_re_name.py",         "misc_tools/image_batch_rename.py"),
    ("Simple_Tools/images_to_mp4.py",         "misc_tools/images_to_video.py"),
    ("Simple_Tools/video_roi.py",             "misc_tools/video_roi_crop.py"),

    # ---- auto_labeling/（原 Auto label）----
    ("Auto label/artificial boxes.py",        "auto_labeling/draw_boxes.py"),
    ("Auto label/artificial boxes2.py",       "auto_labeling/draw_boxes_v2.py"),
    ("Auto label/artificial label.py",        "auto_labeling/draw_labels.py"),
]

# 3) 模块名引用替换（用于更新 import / 字符串引用）
#    注意：长名在前，避免 video_processor 先匹配掉 video_processor_ffmpeg
MODULE_RENAMES: list[tuple[str, str]] = [
    # 目录（包）名
    ("GuiFunction",       "gui_handlers"),
    ("OtherGui",          "can_gui"),
    ("CanDataProcessing", "can_data_tools"),
    ("ImageTest",         "image_testing"),
    ("CameraUtils",       "camera_tools"),
    ("Simple_Tools",      "misc_tools"),
    ("Auto label",        "auto_labeling"),
    ("YOLO框架",           "yolo_framework"),
    # 文件（模块）名 —— 长名优先
    ("video_processor_ffmpeg", "video_extract_ffmpeg"),
    ("video_processor",        "video_extract_frames"),
    ("view_case_processor",    "testcase_view_log"),
    ("view_case_handler",      "testcase_open_table"),
    ("image_similarity_dhash", "image_similarity"),
    ("can_testcase_processor", "can_testcase_parser"),
    ("can_testcase_runner",    "testcase_runner"),
    ("perspective_calibrator", "perspective_calibration"),
    ("error_image_detection",  "error_image_detection"),   # 保持不变（显式列出便于审阅）
    ("file_updater",           "testcase_menu"),
    ("file_handler",           "testcase_upload"),
    ("delete_handler",         "testcase_delete"),
    ("image_handler",          "image_open"),
    ("image_player",           "image_sequence_player"),
    ("matrix_to_csv",          "signal_matrix_to_csv"),
    ("binhex_gui",             "can_data_generator"),
    ("find_can_from_csv",      "find_can_id_from_csv"),
    ("find_subid",             "find_sub_id"),
    ("image_generator",        "test_image_generator"),
    ("verify_icons_by_json",   "verify_icons"),
    ("image_enhancer",         "image_enhancement"),
    ("camera_viewer",          "camera_preview"),
    ("test8wending",           "stability_test"),
    ("create_gif",             "gif_creator"),
    ("image_re_name",          "image_batch_rename"),
    ("images_to_mp4",          "images_to_video"),
    ("video_roi",              "video_roi_crop"),
    ("test_can_gui",           "can_send_receive_gui"),
    ("zlgcan",                 "zlgcan_driver"),
    ("mylog",                  "log_setup"),
    ("train_freeze",           "yolo_train"),
    ("image_test",             "ocr_icon_test"),           # 注意：在 image_testing 之后处理
    ("artificial boxes2",      "draw_boxes_v2"),
    ("artificial boxes",       "draw_boxes"),
    ("artificial label",       "draw_labels"),
]

# ------------------------------------------------------------------ P0 结构整改记录（第二轮）
# 目的：让"根目录只放入口"，把共享基础设施下沉到包内；并消除命名残留。
# 这些改名已完成并通过工具/文档同步（此表用于追溯，不再由脚本执行）。
P0_STRUCTURE_MOVES: list[tuple[str, str, str]] = [
    # (原路径, 新路径, 理由)
    ("log_setup.py",            "hudcore/logging_setup.py",        "横切基础设施，归入 hudcore（零反向依赖层）"),
    ("zlgcan_driver.py",        "can_core/driver.py",              "CAN 驱动绑定 → can_core 包"),
    ("can_control.py",          "can_core/device.py",              "CAN 设备/通道操作 → can_core 包"),
    ("image_preprocessing.py",  "auto_labeling/preprocessing.py",  "仅被模板匹配使用，就近下沉（高内聚）"),
    ("Auto label/algri draft/", "auto_labeling/template_matching/", "目录名含空格+缩写，且缺包声明"),
    ("camera_tools/透视变换-结构.py", "camera_tools/perspective_geometry.py", "中文文件名（跨平台工具链风险）"),
    ("camera_tools/透视变换-颜色.py", "camera_tools/perspective_color.py",    "中文文件名（跨平台工具链风险）"),
    ("image_testing/test_image_generator.py", "image_testing/sample_image_generator.py",
     "test_ 前缀会被 pytest 误判为测试代码"),
    ("can_gui/platfoem_resolution.json", "can_gui/platform_resolution.json", "文件名拼写错误 platform"),
]

# 新增包（声明 API 边界与依赖约束；此前均为无 __init__.py 的命名空间包）
INITIALIZED_PACKAGES: list[str] = [
    "can_core", "gui_handlers", "can_gui", "can_data_tools",
    "image_testing", "camera_tools", "misc_tools", "auto_labeling",
    "auto_labeling/template_matching",
]

# 需要更新引用的文件类型
TEXT_SUFFIXES = (".py", ".md", ".sh", ".bat", ".txt", ".json", ".yaml", ".yml", ".spec", ".cfg")

# 跳过目录：版本库/缓存/第三方库/资源（第三方目录内的引用不属于本次重构范围）
SKIP_DIRS = (".git", "__pycache__", ".idea", ".vscode", ".venv", "node_modules",
             "yolo_framework", "YOLO+=+_", "PaddleOCR-main", "kerneldlls",
             "vendor", "ffmpeg", "models", "Resources", "output", "output_ocr", "logs")

# 跳过文件：本脚本自身（含映射表，不应被改写）
SKIP_FILES = {Path(__file__).resolve()}

# 保护片段：驱动库文件名/系统库名，替换时先占位、后还原
PROTECTED_SNIPPETS = [
    "zlgcan.dll", "zlgcan_x64.dll", "libzlgcan.so", "libzlgcan.dylib",
    "libusbcanfd.so", "libusbcan.so", "libcanfd.so",
    "/opt/zlgcan/lib", "/opt/zlgcan",          # ZLG Linux 驱动的安装路径
]


def run(cmd: list[str], dry: bool) -> None:
    print("  $ " + " ".join(cmd))
    if dry:
        return
    try:
        subprocess.run(cmd, cwd=ROOT, check=True)
    except subprocess.CalledProcessError:
        # git mv 失败时降级：常见原因是 macOS 上中文文件名的 NFC/NFD 不一致，
        # git 认为该文件"已删除"（bad source），此时改用文件系统移动再 git add。
        src, dst = cmd[-2], cmd[-1]
        print(f"  [降级] git mv 失败，改用文件系统移动: {src} -> {dst}")
        shutil.move(str(ROOT / src), str(ROOT / dst))
        # 源路径若从未被 git 跟踪（如本机乱码目录），只 add 目标路径
        for pathspec in ([src, dst], [dst]):
            r = subprocess.run(["git", "add", "-A", "--", *pathspec], cwd=ROOT)
            if r.returncode == 0:
                break


def resolve_old(rel: str) -> str:
    """把映射表里的旧目录名解析为当前实际路径（支持脚本分多次执行）。"""
    for old, new in DIR_RENAMES:
        if rel == old or rel.startswith(old + "/"):
            candidate = new + rel[len(old):]
            if (ROOT / candidate).exists():
                return candidate
    return rel


def do_dirs(dry: bool) -> None:
    print("\n=== 目录重命名 ===")
    for old, new in DIR_RENAMES:
        src, dst = ROOT / old, ROOT / new
        if not src.exists():
            print(f"  [跳过] {old} 不存在")
            continue
        if dst.exists():
            print(f"  [跳过] 目标已存在: {new}")
            continue
        run(["git", "mv", old, new], dry)


def do_files(dry: bool) -> None:
    print("\n=== 文件重命名 ===")
    for old, new in FILE_RENAMES:
        old = resolve_old(old)
        src, dst = ROOT / old, ROOT / new
        if not src.exists():
            print(f"  [跳过] {old} 不存在")
            continue
        (ROOT / new).parent.mkdir(parents=True, exist_ok=True)
        run(["git", "mv", old, new], dry)


def iter_text_files():
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def replace_refs(dry: bool) -> None:
    print("\n=== 更新引用（import / 字符串模块名）===")
    # 模块引用模式：from X / import X / "X" / 'X' / X.y / X/
    patterns = []
    for old, new in MODULE_RENAMES:
        if old == new:
            continue
        esc = re.escape(old)
        # 允许前置字符为 '.'（点号模块路径，如 `from 包.模块 import`）
        # 与 '/'（路径引用，如 "包/模块.py"）；只禁止前置单词字符（避免
        # xyzmylog 这类前缀误伤）。
        patterns.append((
            re.compile(rf'(?<![\w]){esc}(?![\w])'),
            new, old
        ))

    total_hits = 0
    for path in iter_text_files():
        if path.resolve() in SKIP_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        # 保护驱动库文件名：临时替换为占位符
        guards = {}
        guarded = text
        for i, snip in enumerate(PROTECTED_SNIPPETS):
            if snip in guarded:
                token = f"\x00PROT{i}\x00"
                guards[token] = snip
                guarded = guarded.replace(snip, token)

        new_text = guarded
        hits = []
        for pat, new, old in patterns:
            new_text, n = pat.subn(new, new_text)
            if n:
                hits.append(f"{old}->{new}({n})")

        # 还原保护片段
        for token, snip in guards.items():
            new_text = new_text.replace(token, snip)

        if hits and new_text != text:
            total_hits += 1
            print(f"  {path.relative_to(ROOT)}: {', '.join(hits)}")
            if not dry:
                path.write_text(new_text, encoding="utf-8")
    print(f"  受影响文件: {total_hits}")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="只预览，不改动")
    g.add_argument("--apply", action="store_true", help="执行重命名与引用替换")
    args = ap.parse_args()
    dry = args.dry_run

    print(f"{'[预览模式]' if dry else '[执行模式]'} 项目根: {ROOT}")
    do_dirs(dry)
    do_files(dry)
    replace_refs(dry)
    print("\n完成。" + ("（未做任何改动）" if dry else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
