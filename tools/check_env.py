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
    try:
        from hudcore.platform.system import python_status, PYTHON_MIN, PYTHON_MAX_TESTED
        level, note = python_status()
        if level == "error":
            problems.append((note, "Windows: 安装 Python 3.13（python.org）；"
                                   "Ubuntu: sudo apt install -y python3.13 python3.13-tk "
                                   "（或使用 deadsnakes PPA）"))
            print(f"{FAIL} {note}")
        elif level == "warn":
            print(f"{WARN} {note}")
        else:
            print(f"{OK} Python 版本受支持（{PYTHON_MIN[0]}.{PYTHON_MIN[1]} ~ "
                  f"{PYTHON_MAX_TESTED[0]}.{PYTHON_MAX_TESTED[1]}）")
            if note and "paddlepaddle" in note:
                print(f"     注: {note}")
    except Exception:
        if sys.version_info < (3, 10):
            problems.append(("Python 版本过低", "建议 Python 3.10（Ubuntu 22.04 默认）~ 3.13"))


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
        ("ffmpeg", "ffmpeg-python", False,
         "pip install ffmpeg-python（缺失时 ffmpeg 抽帧功能禁用，不影响启动）"),
        ("pyperclip", "pyperclip", False,
         "pip install pyperclip（缺失时 CAN 数据生成器的复制按钮禁用，不影响启动）"),
        ("watchdog", "watchdog", False,
         "pip install watchdog（缺失时透视标定文件监视禁用，不影响启动）"),
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
    section("CAN 驱动库（含接口形态/后端选择）")
    try:
        from hudcore.can import describe_library_status, is_library_available, find_zlg_library
        print(describe_library_status())
        if is_library_available():
            lib = find_zlg_library()
            print(f"{OK} 驱动库就绪: {lib}")
            # 接口形态（zcan / vci / unknown）与最终使用的后端：Linux 公开驱动是 VCI 形态，
            # 由 can_core.vci_adapter 适配，这里一并显示，避免现场误判为"库不匹配"
            try:
                from can_core import describe_driver_status, driver_kind
                print(f"   接口形态: {driver_kind(__import__('hudcore.can', fromlist=['x']).load_zlg_library())}")
                print("   " + describe_driver_status().replace("\n", "\n   "))
            except Exception as exc:                     # noqa: BLE001 - 自检不应因显示失败而中断
                print(f"{WARN} 后端形态检测跳过: {exc}")
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


def check_py313_compat() -> None:
    """Python 3.13 专项：确认重依赖版本满足"有 cp313 wheel"的最低要求。

    背景：paddlepaddle 直到 3.2.1 才提供 cp313 wheel；低于该版本在 3.13 上
    只能源码编译（大概率失败），必须显式升级。
    """
    ver = sys.version_info[:2]
    if ver < (3, 13):
        return
    section("Python 3.13 兼容性")

    # (模块名, 展示名, 3.13 最低版本, 升级命令)
    requirements = [
        ("paddle", "paddlepaddle", (3, 2, 1),
         "pip install -U 'paddlepaddle>=3.2.1'"),
        ("torch", "torch", (2, 6, 0),
         "pip install -U torch --index-url https://download.pytorch.org/whl/cpu"),
        ("numpy", "numpy", (2, 1, 0), "pip install -U 'numpy>=2.1'"),
        ("cv2", "opencv-python", (4, 10, 0), "pip install -U 'opencv-python>=4.10'"),
        ("tokenizers", "tokenizers", (0, 21, 0), "pip install -U 'tokenizers>=0.21'"),
    ]
    for mod, label, min_ver, fix in requirements:
        try:
            m = importlib.import_module(mod)
        except Exception:
            continue                      # 未安装：上面的依赖检查已给出提示
        raw = str(getattr(m, "__version__", "") or "")
        cur = tuple(int(x) for x in raw.split(".")[:3] if x.isdigit())
        if cur and cur < min_ver:
            need = ".".join(map(str, min_ver))
            print(f"{FAIL} {label} {raw} 低于 3.13 所需最低版本 {need}（无 cp313 wheel）")
            problems.append((f"{label} {raw} 在 Python 3.13 上不受支持", fix))
        else:
            print(f"{OK} {label} {raw}（满足 3.13 要求 >= "
                  f"{'.'.join(map(str, min_ver))}）")
    print(f"{OK} 说明：Python 3.13 上首次安装请用 "
          f"`pip install -r requirements-py313.txt`（已固定可用版本）")


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
    check_py313_compat()
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
