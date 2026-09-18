#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/check_env.py —— HudAutoTest 环境自检（Windows / Ubuntu 通用）
===================================================================
一次性检查运行所需的全部条件，输出"问题 + 修复命令"，现场排障首选。

用法：
    python tools/check_env.py
    ./run.sh --check          # Linux
    run.bat --check           # Windows
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

# 让脚本能 import hudcore（无论从哪个目录调用）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OK = "[OK]  "
WARN = "[警告]"
FAIL = "[错误]"

problems: list[tuple[str, str]] = []   # (问题, 修复建议)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def check_platform() -> None:
    section("平台")
    try:
        from hudcore.platform import describe_platform, IS_WINDOWS, IS_LINUX, IS_MACOS
        print(f"{OK} {describe_platform()}")
        if not (IS_WINDOWS or IS_LINUX or IS_MACOS):
            problems.append(("不支持的平台", "本项目正式支持 Windows / Ubuntu 22.04"))
        if IS_LINUX:
            from hudcore.platform.system import IS_UBUNTU, UBUNTU_VERSION
            print(f"{OK} Linux 发行版: {'Ubuntu ' + UBUNTU_VERSION if IS_UBUNTU else '非 Ubuntu（尽力支持）'}")
    except Exception as e:
        problems.append((f"hudcore 导入失败: {e}", "确认在项目根目录下运行，且 hudcore/ 目录存在"))
    print(f"{OK} Python {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 8):
        problems.append(("Python 版本过低", "建议 Python 3.10（Ubuntu 22.04 默认）"))


def check_paths() -> None:
    section("路径")
    try:
        from hudcore.platform.paths import paths
        for name in ("project_root", "logs_dir", "drivers_dir", "bin_dir"):
            print(f"{OK} {name}: {getattr(paths, name)}")
    except Exception as e:
        problems.append((f"路径初始化失败: {e}", "检查目录权限"))


def check_python_deps() -> None:
    section("Python 依赖")
    # (模块名, 展示名, 是否必需, 修复建议)
    deps = [
        ("tkinter", "tkinter (GUI)", True,
         "Windows: 重装 Python 并勾选 tcl/tk；Ubuntu: sudo apt install -y python3-tk"),
        ("numpy", "numpy", True, "pip install numpy"),
        ("pandas", "pandas", True, "pip install pandas"),
        ("openpyxl", "openpyxl (xlsx)", True, "pip install openpyxl"),
        ("cv2", "opencv (cv2)", True, "pip install opencv-python"),
        ("PIL", "Pillow", True, "pip install pillow"),
        ("ffmpeg", "ffmpeg-python", False, "pip install ffmpeg-python（抽帧功能需要）"),
        ("ultralytics", "ultralytics (YOLO)", False, "pip install ultralytics（图标检测需要）"),
        ("paddleocr", "paddleocr", False, "pip install paddleocr paddlepaddle（OCR 需要）"),
        ("easyocr", "easyocr", False, "pip install easyocr"),
        ("torch", "torch", False,
         "GPU: pip install torch --index-url https://download.pytorch.org/whl/cu126\n"
         "         CPU: pip install torch --index-url https://download.pytorch.org/whl/cpu"),
    ]
    for mod, label, required, fix in deps:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "")
            print(f"{OK} {label} {ver}")
        except Exception as e:
            if required:
                print(f"{FAIL} {label} 缺失: {type(e).__name__}")
                problems.append((f"缺少必需依赖 {label}", fix))
            else:
                print(f"{WARN} {label} 缺失（可选功能不可用）")
                problems.append((f"可选依赖 {label} 缺失", fix))


def check_can_driver() -> None:
    section("CAN 驱动库")
    try:
        from hudcore.can import describe_library_status, is_library_available, find_zlg_library
        print(describe_library_status())
        if is_library_available():
            lib = find_zlg_library()
            print(f"{OK} 驱动库就绪: {lib}")
            _check_so_deps(lib)
        else:
            fix = ("将 zlgcan.dll 放入 drivers/windows/，或设置 HUD_ZLG_LIB=<完整路径>"
                   if sys.platform == "win32" else
                   "从 ZLG 官网获取 Linux 驱动：将 libzlgcan.so 放入 drivers/linux/，"
                   "或设置 HUD_ZLG_LIB=<完整路径>；系统依赖 sudo apt install -y libusb-1.0-0")
            problems.append(("未找到 CAN 驱动库（CAN 功能不可用）", fix))
    except Exception as e:
        problems.append((f"驱动库探测异常: {e}", "检查 hudcore/can/backend.py"))


def _check_so_deps(lib_path) -> None:
    """Linux：用 ldd 检查 .so 的缺失依赖"""
    if not sys.platform.startswith("linux"):
        return
    import subprocess
    try:
        out = subprocess.run(["ldd", str(lib_path)], capture_output=True, text=True, timeout=10).stdout
        missing = [l.strip() for l in out.splitlines() if "not found" in l]
        if missing:
            print(f"{FAIL} 库依赖缺失：")
            for m in missing:
                print(f"        {m}")
            problems.append(("CAN 驱动库缺少系统依赖",
                             "sudo apt install -y libusb-1.0-0 libusb-1.0-0-dev"))
        else:
            print(f"{OK} 库依赖完整")
    except Exception as e:
        print(f"{WARN} 无法检查库依赖: {e}")


def check_external_tools() -> None:
    section("外部程序")
    try:
        from hudcore.platform.executables import (
            get_ffmpeg, get_office_app, get_text_editor, get_terminal)
        for label, path, fix in (
            ("ffmpeg", get_ffmpeg(), "Ubuntu: sudo apt install -y ffmpeg；Windows: 放入 bin/windows/ 或加入 PATH"),
            ("表格应用(WPS/Excel/LibreOffice)", get_office_app(),
             "Ubuntu: sudo apt install -y libreoffice-calc"),
            ("文本编辑器", get_text_editor(), "Ubuntu: sudo apt install -y gedit"),
        ):
            if path:
                print(f"{OK} {label}: {path}")
            else:
                print(f"{WARN} {label}: 未找到")
                problems.append((f"未找到 {label}", fix))
    except Exception as e:
        problems.append((f"外部程序探测异常: {e}", "检查 hudcore/platform/executables.py"))


def check_fonts() -> None:
    section("界面字体")
    try:
        from hudcore.platform.fonts import get_ui_font_name, list_available_fonts
        name = get_ui_font_name()
        print(f"{OK} 选用字体: {name}")
        fams = list_available_fonts()
        if fams:
            cjk = [f for f in fams if any(k in f for k in ("CJK", "WenQuanYi", "YaHei", "雅黑", "宋体", "黑体"))]
            if cjk:
                print(f"{OK} 中文字体可用: {', '.join(cjk[:4])}")
            elif sys.platform.startswith("linux"):
                problems.append(("未检测到中文字体（界面可能显示方块）",
                                 "sudo apt install -y fonts-noto-cjk"))
                print(f"{WARN} 未检测到中文字体")
        else:
            print(f"{WARN} 无法枚举字体（无显示环境时正常）")
    except Exception as e:
        problems.append((f"字体检查异常: {e}", "确认已安装 tkinter"))


def check_testcase_dir() -> None:
    section("业务目录")
    try:
        from hudcore.platform.paths import paths
        tc = paths.testcase_dir
        xlsx = list(tc.glob("*.xlsx")) if tc.exists() else []
        print(f"{OK} 测试用例目录: {tc}（{len(xlsx)} 个 xlsx）")
        if not xlsx:
            print(f"{WARN} 目录为空：可通过 GUI 的「上传测试用例」添加")
    except Exception as e:
        problems.append((f"业务目录检查异常: {e}", ""))


def main() -> int:
    print("=" * 66)
    print(" HudAutoTest 环境自检")
    print("=" * 66)

    check_platform()
    check_paths()
    check_python_deps()
    check_fonts()
    check_can_driver()
    check_external_tools()
    check_testcase_dir()

    section("结论")
    required_problems = [p for p in problems if "可选依赖" not in p[0] and "未检测到中文字体" not in p[0]
                         and "未找到 ffmpeg" not in p[0] and "未找到 表格应用" not in p[0]
                         and "未找到 文本编辑器" not in p[0] and "目录为空" not in p[0]]
    if not problems:
        print(f"{OK} 环境完整，可直接运行：python main.py")
        return 0

    print(f"发现 {len(problems)} 项需处理（其中 {len(required_problems)} 项影响核心功能）：")
    for i, (prob, fix) in enumerate(problems, 1):
        print(f"\n  {i}. {prob}")
        if fix:
            for line in str(fix).split("\n"):
                print(f"     修复: {line}")
    return 1 if required_problems else 0


if __name__ == "__main__":
    sys.exit(main())
