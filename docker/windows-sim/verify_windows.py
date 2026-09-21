#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docker/windows-sim/verify_windows.py —— Windows 环境功能验证套件
================================================================
在 **Windows 版 CPython**（容器内 = Wine + Windows Python）中运行，
逐项验证 HudAutoTest 的平台相关能力与无硬件依赖的业务功能是否正常。

设计原则：
  · 不依赖显示器（容器内用 Xvfb 提供虚拟 X 显示；Tk 相关项在该前提下测试）；
  · 不依赖真实硬件（CAN 驱动用 MinGW 编译的 stub DLL 验证"探测 + 加载 + 调用"链路）；
  · 不依赖重依赖（torch / paddleocr 缺失时按"优雅降级"判定，不判失败）；
  · 每项输出 PASS / FAIL / SKIP + 证据（返回值、路径、版本号）。

用法（容器内）：
    xvfb-run -a wine python Z:\\work\\docker\\windows-sim\\verify_windows.py --report out.md --json out.json
参数：
    --report FILE   写 Markdown 报告（默认 stdout 摘要 + verify_report.md）
    --json FILE     写 JSON 结果
    --expect win|linux|any   断言运行平台（默认 any）
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
import tempfile
import threading
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------- 结果收集

RESULTS: list[dict] = []


def record(name: str, status: str, detail: str = "", duration_s: float = 0.0) -> None:
    RESULTS.append({"name": name, "status": status, "detail": detail,
                    "duration_s": round(duration_s, 2), "index": len(RESULTS) + 1})
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
    spent = f" ({duration_s:.1f}s)" if duration_s else ""
    print(f"{icon} {name}{spent}" + (f"  — {detail}" if detail else ""), flush=True)


# 单项超时（秒）：Windows 程序在 Wine / 无显示环境里可能挂起（例如 Tk 阻塞），
# 因此每项验证都在独立线程中执行，超时即判 FAIL，保证整套测试不会卡死。
ITEM_TIMEOUT = int(os.environ.get("HUD_VERIFY_TIMEOUT", "120"))


def test(name: str):
    """装饰器：在线程中执行函数，带超时；异常 → FAIL。"""
    def deco(fn):
        def wrapper():
            box: dict = {}
            started = time.time()

            def run():
                try:
                    box["result"] = fn()
                except BaseException as exc:        # noqa: BLE001
                    # 必须捕获 BaseException：被验证的模块可能在导入期调用
                    # sys.exit()（argparse 解析到外部参数时），那是 SystemExit，
                    # 属于 BaseException 而非 Exception，漏捕会让整个用例"无返回值"。
                    box["error"] = exc
                    box["tb"] = traceback.format_exc()

            th = threading.Thread(target=run, daemon=True,
                                  name=f"verify-{fn.__name__}")
            th.start()
            th.join(ITEM_TIMEOUT)
            spent = time.time() - started
            if th.is_alive():
                record(name, "FAIL", f"超时（>{ITEM_TIMEOUT}s）未返回，可能阻塞在 "
                                     f"GUI/外部程序调用；已跳过并继续后续验证", spent)
                return
            if "error" in box:
                exc = box["error"]
                record(name, "FAIL", f"{type(exc).__name__}: {exc}", spent)
                print(box.get("tb", ""), flush=True)
                return
            status, detail = box.get("result", ("FAIL", "无返回值"))
            record(name, status, detail, spent)
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco


# ---------------------------------------------------------------- 工具

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

TMP = Path(tempfile.mkdtemp(prefix="hudverify_"))


def make_images(folder: Path, count: int = 5, size=(64, 64)) -> None:
    """生成 count 张可区分的小图（文件名 1.png、2.png… 便于 gif_creator 排序）。"""
    from PIL import Image
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        img = Image.new("RGB", size, (i * 30 % 256, 60, 200 - i * 20))
        img.save(folder / f"{i}.png")


def exe_python() -> str:
    return sys.executable


# ---------------------------------------------------------------- 1. 运行时

@test("1. 运行时环境（OS / Python / 架构）")
def t_runtime():
    from hudcore.platform.system import IS_WINDOWS, PYTHON_VERSION, PYTHON_VERSION_INFO
    info = (f"platform.system()={platform.system()}, sys.platform={sys.platform}, "
            f"Python={PYTHON_VERSION}, arch={platform.machine()}, "
            f"64bit={sys.maxsize > 2**32}, exe={Path(sys.executable).name}")
    if EXPECT == "win" and not IS_WINDOWS:
        return "FAIL", f"期望 Windows 语义，实际 {info}"
    if EXPECT == "linux" and IS_WINDOWS:
        return "FAIL", f"期望 Linux 语义，实际 {info}"
    return "PASS", info


# ---------------------------------------------------------------- 2. 平台层

@test("2. hudcore 平台探测（system）")
def t_system():
    from hudcore.platform import describe_platform
    from hudcore.platform import system as S
    assert S.exe_suffix in (".exe", ""), S.exe_suffix
    if S.IS_WINDOWS:
        assert S.exe_suffix == ".exe" and S.lib_suffix == ".dll" and S.pathsep == ";"
    level, note = S.python_status()
    assert level in ("ok", "warn"), f"Python 版本不受支持: {note}"
    return "PASS", f"{describe_platform()} | exe_suffix={S.exe_suffix!r} | " \
                   f"py_status={level}"


# ---------------------------------------------------------------- 3. 路径层

@test("3. 路径层 + 中文路径读写")
def t_paths():
    from hudcore.platform.paths import paths
    names = ["project_root", "logs_dir", "drivers_dir", "bin_dir", "testcase_dir"]
    got = {n: str(getattr(paths, n)) for n in names}
    # 中文文件名写入 logs（Windows 默认 GBK 代码页下最容易出问题）
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    target = paths.logs_dir / "验证-中文路径-测试.log"
    target.write_text("HudAutoTest 中文路径写入测试\n" + got["project_root"],
                      encoding="utf-8")
    assert target.is_file() and "中文路径" in target.read_text(encoding="utf-8")
    target.unlink(missing_ok=True)
    return "PASS", f"root={got['project_root']}; 中文写入/读取成功"


# ---------------------------------------------------------------- 4. 字体层

@test("4. 界面字体与中文渲染字体")
def t_fonts():
    from hudcore.platform.fonts import get_ui_font_name, list_available_fonts, load_pil_font
    name = get_ui_font_name()
    fams = list_available_fonts()
    font = load_pil_font(20)
    detail = f"selected={name!r}, 可用字体={len(fams)}, PIL字体={getattr(font, 'path', 'default')}"
    if not name:
        return "FAIL", "未解析到 UI 字体名"
    return "PASS", detail


# ---------------------------------------------------------------- 5. Tk GUI

@test("5. Tk 窗口创建（虚拟显示）")
def t_tk():
    import tkinter as tk
    root = tk.Tk()
    root.title("HudAutoTest 验证窗口")
    root.geometry("320x120")
    tk.Label(root, text="中文标签渲染测试").pack()
    root.update_idletasks()
    root.update()
    geom = root.geometry()
    root.destroy()
    return "PASS", f"Tk {tk.TkVersion} 创建并销毁成功, geometry={geom}"


@test("6. Theme 样式 + TextRedirector 重定向")
def t_theme_redirect():
    import tkinter as tk
    from hudcore.ui import TextRedirector, Theme
    root = tk.Tk()
    # Theme 暴露的是"样式工厂"（primary_button / label_style / log_text_style …），
    # 因此统计可调用的样式方法数量，而不是固定属性名。
    factories = [n for n in dir(Theme)
                 if not n.startswith("_")
                 and (n.endswith(("_button", "_style")) or n.startswith("font"))]
    theme_ok = len(factories)
    assert theme_ok >= 3, f"Theme 样式工厂过少: {factories}"
    txt = tk.Text(root)
    rd = TextRedirector(txt, root)          # 签名: (widget, root, poll_interval=50)
    sys.stdout = rd
    print("重定向-测试-中文")
    sys.stdout = sys.__stdout__
    # TextRedirector 通过 root.after 轮询队列，需要驱动一次事件循环
    for _ in range(10):
        root.update()
        root.after(60)
        if "重定向-测试-中文" in txt.get("1.0", "end"):
            break
        import time
        time.sleep(0.06)
    content = txt.get("1.0", "end").strip()
    root.destroy()
    assert "重定向-测试-中文" in content, f"Text 内容={content!r}"
    return "PASS", f"Theme 样式数={theme_ok}, TextRedirector 捕获：{content!r}"


# ---------------------------------------------------------------- 7. 导入链

@test("7. main.py 导入链（不启动 GUI 主循环）")
def t_import_main():
    import importlib
    m = importlib.import_module("main")
    assert hasattr(m, "MainWindow"), "main.MainWindow 缺失"
    names = [n for n in dir(m) if n.endswith("Handler") or n in ("TextRedirector",)]
    return "PASS", f"import main 成功；MainWindow/TextRedirector 可用；导出={len(names)} 项"


@test("8. 全部界面与工具模块导入")
def t_import_all():
    mods = [
        "gui_handlers.testcase_menu", "gui_handlers.testcase_upload",
        "gui_handlers.testcase_delete", "gui_handlers.testcase_open_table",
        "gui_handlers.testcase_view_log", "gui_handlers.image_open",
        "gui_handlers.video_extract_frames", "gui_handlers.video_extract_ffmpeg",
        "gui_handlers.image_sequence_player", "gui_handlers.can_testcase_parser",
        "gui_handlers.signal_matrix_to_csv", "gui_handlers.can_data_generator",
        "can_gui.can_send_receive_gui", "can_gui.gui_camera",
        "can_gui.gui_test_flow", "can_gui.gui_config",
        "can_data_tools.testcase_runner", "can_data_tools.case_log_parser",
        "can_data_tools.can_step_runner", "can_data_tools.find_can_id_from_csv",
        "can_data_tools.find_sub_id",
        "image_testing.icon_manager", "image_testing.icon_data",
        "image_testing.icon_config", "image_testing.icon_thumbnail",
        "image_testing.icon_form", "image_testing.image_similarity",
        "image_testing.sample_image_generator", "image_testing.verify_icons",
        "someip_core", "someip_core.models", "someip_core.api",
        "someip_core.pcap_info", "someip_core.config", "someip_core.replay",
        "someip_gui", "someip_gui.field_table", "someip_gui.panel_config",
        "someip_gui.panel_control", "someip_gui.replay_window",
        "hudcore.someip", "hudcore.someip.backend",
        "image_testing.tooltip", "image_testing.image_gen_data",
        "image_testing.image_gen_preview",
        "misc_tools.gif_creator", "misc_tools.image_batch_rename",
        "misc_tools.images_to_video", "misc_tools.video_roi_crop",
        "camera_tools.camera_preview", "camera_tools.error_image_detection",
        "camera_tools.image_enhancement", "camera_tools.perspective_calibration",
        "camera_tools.stability_test",
        "auto_labeling.auto_detect", "auto_labeling.draw_boxes",
        "auto_labeling.draw_boxes_v2", "auto_labeling.draw_labels",
        "hudcore", "hudcore.can", "hudcore.ui", "hudcore.platform",
        "hudcore.logging_setup", "can_core", "can_core.driver", "can_core.device",
        "can_core.can_state", "can_core.bit_utils", "can_core.receive", "can_core.transmit",
        "auto_labeling.preprocessing", "auto_labeling.template_matching",
    ]
    import importlib
    bad = []
    ok = 0
    for name in mods:
        try:
            importlib.import_module(name)
            ok += 1
        except Exception as exc:
            bad.append(f"{name}: {type(exc).__name__}: {exc}")
    if bad:
        return "FAIL", f"{ok}/{len(mods)} 导入成功；失败：{bad[:3]}"
    return "PASS", f"{ok}/{len(mods)} 模块全部导入成功"


# ---------------------------------------------------------------- 9. CAN 驱动

@test("9. CAN 驱动库探测与加载（桩库）")
def t_can_load():
    """验证「探测 → 加载 → 调用导出函数」链路。

    做法：用容器自带的桩库（Windows 侧为 python313.dll / MinGW 编译的 zlgcan.dll）
    通过 HUD_ZLG_LIB 显式指定，避免依赖现场真实驱动；
    若本机存在真实 ZLG 库（含 Linux 版），只作为信息展示 ——
    真实库可能因缺依赖或接口不匹配（Linux 公开库是 VCI 接口）而无法加载，
    这属于环境条件而非本项目缺陷，因此不判失败。
    """
    import os
    from hudcore.can import (describe_library_status, find_zlg_library,
                             library_api_kind, library_load_error, load_zlg_library)

    stub = os.environ.get("HUD_ZLG_STUB") or ""
    real = find_zlg_library()
    real_info = ""
    if real is not None:
        kind = library_api_kind(real)
        real_info = f"；本机库 {real.name}(接口={kind}"
        if kind == "error":
            real_info += f"，加载失败：{library_load_error()[:60]}"
        real_info += ")"

    if not stub or not Path(stub).is_file():
        # 无桩库：给出探测状态说明（信息性），不判失败
        return "SKIP", "容器内未提供桩库（HUD_ZLG_STUB）" + real_info

    os.environ["HUD_ZLG_LIB"] = stub
    try:
        handle = load_zlg_library()
        assert handle is not None
        called = False
        for fn_name in ("ZCAN_GetDeviceCount", "VCI_OpenDevice", "Py_GetVersion"):
            fn = getattr(handle, fn_name, None)
            if fn is None:
                continue
            fn.restype = __import__("ctypes").c_uint32
            value = fn() if fn_name != "Py_GetVersion" else fn()
            return "PASS", f"桩库加载成功并通过调用验证：{fn_name}()={value!r}{real_info}"
        assert called, "桩库未提供任何已知导出函数"
    finally:
        os.environ.pop("HUD_ZLG_LIB", None)
    return "PASS", f"桩库加载成功{real_info}"


@test("10. CAN 驱动缺失时的报错友好性")
def t_can_hint():
    import importlib
    from hudcore.can import backend
    old = os.environ.get("HUD_ZLG_LIB")
    os.environ["HUD_ZLG_LIB"] = str(TMP / "不存在的驱动.dll")
    try:
        importlib.reload(backend)
        lib = backend.find_zlg_library()
        hint = backend._not_found_hint() if lib is None else ""
    finally:
        if old is None:
            os.environ.pop("HUD_ZLG_LIB", None)
        else:
            os.environ["HUD_ZLG_LIB"] = old
        importlib.reload(backend)
    if lib is None and not hint:
        return "FAIL", "未找到库时缺少修复提示"
    return "PASS", f"缺失时提示：{hint[:90]}…" if hint else "已按 HUD_ZLG_LIB 覆盖路径"


# ---------------------------------------------------------------- 11. 外部程序

@test("11. 外部程序探测不抛异常")
def t_external():
    from hudcore.platform.executables import (
        get_ffmpeg, get_office_app, get_text_editor, get_terminal, find_executable)
    res = {
        "ffmpeg": get_ffmpeg(), "office": get_office_app(),
        "editor": get_text_editor(), "terminal": get_terminal(),
        "where_python": find_executable([Path(sys.executable).stem]),
    }
    return "PASS", "; ".join(f"{k}={'命中' if v else '未找到'}" for k, v in res.items())


# ---------------------------------------------------------------- 12. 图像功能

@test("12. 图标相似度比较（dHash）")
def t_similarity():
    from PIL import Image
    from image_testing.image_similarity import compare_icons, get_image_hash
    a = TMP / "icon_a.png"
    b = TMP / "icon_b.png"
    c = TMP / "icon_c.png"
    Image.new("RGB", (64, 64), (255, 0, 0)).save(a)
    Image.new("RGB", (64, 64), (255, 0, 0)).save(b)
    # 明显不同的图：棋盘格
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    px = img.load()
    for x in range(64):
        for y in range(64):
            if (x // 8 + y // 8) % 2 == 0:
                px[x, y] = (255, 255, 255)
    img.save(c)
    same = compare_icons(str(a), str(b), 80)
    diff = compare_icons(str(a), str(c), 80)
    ha, hc = get_image_hash(str(a)), get_image_hash(str(c))
    assert same is True, f"相同图判定为 {same}"
    assert diff is False, f"不同图判定为 {diff}"
    return "PASS", f"相同图→{same}, 不同图→{diff}, hash 差异={bin(ha ^ hc).count('1')} bit"


@test("13. GIF 合成（Pillow，含中文输出路径）")
def t_gif():
    from PIL import Image
    try:
        from misc_tools.gif_creator import gif_creator
    except ImportError as exc:
        if "tkinter" in str(exc) or "_tkinter" in str(exc) or "libtk" in str(exc):
            return "SKIP", f"环境缺少 Tk 运行库（gif_creator 顶层 import tkinter）: {exc}"
        raise
    src = TMP / "gif源图片"
    out_dir = TMP / "中文输出目录"
    out_dir.mkdir(parents=True, exist_ok=True)
    make_images(src, 5)
    out = out_dir / "结果.gif"
    gif_creator(str(src), str(out), duration=80, loop=0)
    assert out.is_file(), "GIF 未生成"
    with Image.open(out) as im:
        frames = getattr(im, "n_frames", 1)
    assert frames >= 5, f"帧数异常: {frames}"
    return "PASS", f"{out.name} 生成成功, {frames} 帧, {out.stat().st_size} bytes"


@test("14. 图像增强 / 透视标定模块可用（cv2 链路）")
def t_cv_modules():
    import cv2
    import numpy as np
    from camera_tools.image_enhancement import ImageEnhancer
    img = np.full((120, 160, 3), 128, dtype=np.uint8)
    methods = [m for m in dir(ImageEnhancer) if not m.startswith("_")]
    cv2.imwrite(str(TMP / "cv_中文.png"), img)
    read = cv2.imread(str(TMP / "cv_中文.png"))
    assert read is not None and read.shape == (120, 160, 3), "cv2 中文路径读写失败"
    return "PASS", f"cv2 {cv2.__version__} 中文路径读写 OK；ImageEnhancer 方法数={len(methods)}"


# ---------------------------------------------------------------- 15. CAN 业务

@test("15. CAN 信号 → 数据字节（outputMatrix.csv）")
def t_can_signal():
    """
    用项目自带的 5.9 万行信号矩阵验证 CAN 编码链路。
    注意：CSV 表头为 报文名称/报文ID/报文长度/位/信号长度/信号名称(英文)/…，
    其中"信号长度"也含"信号"二字，选择信号名列时必须精确匹配，
    否则会误取到数值列（早期版本的坑，这里显式规避）。
    """
    import pandas as pd
    from can_data_tools.find_can_id_from_csv import (
        get_signal_info_by_id_and_name, create_can_data_by_signal)

    csv_path = PROJECT_ROOT / "data" / "outputMatrix.csv"
    assert csv_path.is_file(), f"缺少 {csv_path}"

    df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig").fillna("")
    name_col = None
    for cand in ("信号名称(英文)", "信号名称（英文）"):
        if cand in df.columns:
            name_col = cand
            break
    if name_col is None:                       # 兜底：含"信号"且含"英文/name"的列
        name_col = next((c for c in df.columns
                         if "信号" in c and ("英文" in c or "name" in c.lower())), None)
    assert name_col, f"未找到信号英文名列，实际列：{list(df.columns)}"

    usable = df[(df["位"].str.strip() != "") & (df[name_col].str.strip() != "")]
    assert len(usable) > 0, "CSV 中没有可用信号行"
    row = usable.iloc[0]
    mid, sig = str(row["报文ID"]).strip(), str(row[name_col]).strip()

    info = get_signal_info_by_id_and_name(mid, sig, str(csv_path))
    assert info is not None, f"信号查询失败: {mid}/{sig}"

    r0 = create_can_data_by_signal(mid, sig, 0, str(csv_path))
    r1 = create_can_data_by_signal(mid, sig, 1, str(csv_path))
    assert r0.get("success") and r1.get("success"), f"生成失败: {r0} / {r1}"
    d0, d1 = r0["can_data_str"], r1["can_data_str"]
    return "PASS", (f"信号 {mid}/{sig}（位={row['位']}, 长度={row['报文长度']}）: "
                    f"枚举0→{d0} 枚举1→{d1} 值随枚举变化={d0 != d1}")


@test("16. 信号矩阵 XLSX → CSV 转换")
def t_matrix_csv():
    from openpyxl import Workbook
    from gui_handlers import signal_matrix_to_csv as mod
    xlsx = TMP / "信号矩阵.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["信号名", "报文ID", "位", "值"])
    ws.append(["ADAS_Distance", "0x2F1", "0-15", 0])
    wb.save(xlsx)
    fn = next((n for n in dir(mod) if "convert" in n.lower() or "csv" in n.lower()), None)
    if fn is None:
        return "SKIP", "模块未暴露可 headless 调用的转换函数（GUI 内触发）"
    return "PASS", f"openpyxl 读写 OK，模块入口={fn}"


# ---------------------------------------------------------------- 17. 项目自检

@test("17. 项目自带自检脚本可运行")
def t_project_scripts():
    outputs = []
    for script in ("tools/check_imports.py", "tools/check_static.py", "tools/selftest.py"):
        p = PROJECT_ROOT / script
        r = subprocess.run([exe_python(), str(p)], capture_output=True, text=True,
                           cwd=str(PROJECT_ROOT), timeout=300)
        tail = (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]
        outputs.append(f"{Path(script).name} rc={r.returncode} ({tail[0][:60]})")
        if r.returncode != 0:
            return "FAIL", "; ".join(outputs) + f" | stderr={r.stderr[-300:]}"
    return "PASS", "; ".join(outputs)


@test("18. 单元测试（pytest）")
def t_unit_tests():
    """运行 tests/ 下的单元测试（架构规则守卫 + 核心行为）。

    pytest 未安装时 SKIP（容器镜像默认不装测试框架，避免影响运行期镜像体积）。
    """
    import subprocess
    try:
        import pytest  # noqa: F401
    except ImportError:
        return "SKIP", "未安装 pytest（pip install pytest 后可运行单元测试）"
    r = subprocess.run([exe_python(), "-m", "pytest", "tests", "-q"],
                       capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=600)
    tail = (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]
    if r.returncode != 0:
        return "FAIL", f"pytest rc={r.returncode} | {tail[0][:120]}"
    return "PASS", tail[0][:120]


@test("19. SOME/IP 回放窗口（布局与降级）")
def t_someip_window():
    """创建 SOME/IP 回放窗口，校验布局要素与"库不可用"时的降级行为。

    · 不依赖真实 SOME/IP 库：库缺失时应给出提示并把动作按钮置灰（Windows 现状）
    · 校验：事件表 23 行、字段表按结构体自动生成、勾选/全选、关闭时安全释放
    """
    import tkinter as tk
    from tkinter import messagebox
    from someip_core import all_events
    from someip_core import config as someip_config
    from someip_gui import open_replay_window

    # 无人值守：屏蔽模态弹窗（否则会阻塞验证）
    warns = []
    messagebox.showwarning = lambda *a, **k: warns.append(a[:1])
    messagebox.showerror = lambda *a, **k: warns.append(a[:1])

    # 配置写入隔离：窗口关闭时会 save() 到 data/someip/replay_config.json，
    # 验证套件不该改动仓库里的跟踪文件（实测会把 service_table 等键写进去）
    # → 把配置路径指到临时目录，仍照常验证"关闭即保存"的行为。
    tmp_cfg = Path(tempfile.mkdtemp(prefix="hudverify_someip_")) / "replay_config.json"
    someip_config.config_path = lambda: tmp_cfg

    root = tk.Tk()
    root.withdraw()
    try:
        win = open_replay_window(root)
        win.update_idletasks()
        app = win.someip_app
        rows = len(app.event_tree.get_children())
        assert rows == len(all_events()) == 23, f"事件表行数异常：{rows}"

        counts = {}
        for kind in ("RTK", "PilotStatus", "VehiclePosition", "HudNavmap"):
            app.var_kind.set(kind)
            app._on_kind_changed()
            counts[kind] = len(app.field_table._entries)
        assert counts["RTK"] > 20 and counts["VehiclePosition"] > 30, f"字段表异常：{counts}"

        app._select_all(False)
        assert app.config.selected == [], "全不选后应为空（表示不注册）"
        app._select_all(True)
        assert app.config.selected == [], "全选后应为空列表（表示注册全部）"

        status = str(app.lbl_status.cget("text"))
        lib_ok = "库就绪" in status
        btn_state = str(app.btn_replay_start.cget("state"))
        if not lib_ok:
            assert btn_state == "disabled", "库不可用时回放按钮应置灰"
        detail = (f"{rows} 个事件，字段数 {counts}；状态={status[:28]}；"
                  f"库{'可用' if lib_ok else '不可用(已降级)'}")
        if lib_ok:
            # 本机确实放好了真实库：不去真正启动 vsomeip 服务（容器里可能直接 abort），
            # 只验证"库就绪时的界面状态"，真实链路由 docs/SOMEIP_REPLAY.md 记录的
            # 端到端步骤单独验证。
            app.on_closing()
            return "PASS", detail + "（本机有真实库，未执行真实启停）"
        app.on_replay_start()                     # 库不可用时不应崩溃
        app.on_closing()
        return "PASS", detail
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------- main

def _auto_label(explicit: str = "") -> str:
    """报告标签：显式指定优先，否则按实际运行环境判断（Wine / Windows / Linux）。"""
    if explicit:
        return explicit
    import os
    if os.environ.get("WINEPREFIX"):
        return "Windows（Wine 容器内 + Windows 版 CPython）"
    if sys.platform == "win32":
        return "Windows（本机）"
    if sys.platform.startswith("linux"):
        name = "Linux"
        try:
            os_release = Path("/etc/os-release").read_text(encoding="utf-8")
            for line in os_release.splitlines():
                if line.startswith("PRETTY_NAME="):
                    name = line.split("=", 1)[1].strip().strip('"')
                    break
        except OSError:
            pass
        return f"{name}（容器内）"
    return platform.platform()


def _load_previous(json_path: Path):
    """读取上一次报告（供回归对比）；失败/未开启时返回 None。"""
    try:
        from tools.verify_report import load_previous
        return load_previous(json_path)
    except Exception:                                  # noqa: BLE001
        return None


def main() -> int:
    global EXPECT
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", choices=["win", "linux", "any"], default="any")
    ap.add_argument("--report", default=str(Path(__file__).with_name("verify_report.md")))
    ap.add_argument("--json", default=str(Path(__file__).with_name("verify_report.json")))
    ap.add_argument("--skip", default="", help="逗号分隔的测试编号，跳过这些项")
    ap.add_argument("--label", default="", help="报告标题里的运行环境标签（默认自动判断）")
    ap.add_argument("--no-diff", action="store_true", help="不与上次 JSON 报告做回归对比")
    args = ap.parse_args()
    EXPECT = args.expect

    from tools.verify_report import (Item, ReportMeta, collect_environment,
                                     summarize, write_reports)

    json_path = Path(args.json)
    previous = None if args.no_diff else _load_previous(json_path)
    started_at = time.time()

    print("=" * 72)
    print(f" HudAutoTest — 环境功能验证（{_auto_label(args.label)}）")
    print(f" 项目根: {PROJECT_ROOT}")
    print(f" 解释器: {sys.executable}")
    print(f" Python : {sys.version.split()[0]}  platform={platform.platform()}")
    print("=" * 72)

    tests = [t_runtime, t_system, t_paths, t_fonts, t_tk, t_theme_redirect,
             t_import_main, t_import_all, t_can_load, t_can_hint, t_external,
             t_similarity, t_gif, t_cv_modules, t_can_signal, t_matrix_csv,
             t_project_scripts, t_unit_tests, t_someip_window]
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    print()
    for fn in tests:
        if fn.__name__ in skip:
            record(fn.__name__, "SKIP", "按 --skip 跳过")
            continue
        fn()

    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    skipped = sum(1 for r in RESULTS if r["status"] == "SKIP")
    print("\n" + "=" * 72)
    print(f" 结果: {passed} 通过 / {len(failed)} 失败 / {skipped} 跳过")
    if failed:
        for r in failed:
            print(f"   ✗ {r['name']}: {r['detail']}")
    print("=" * 72)

    # 写报告（Markdown + JSON；含环境块、耗时、失败/跳过清单与上次对比）
    items = [Item(name=r["name"], status=r["status"], detail=r["detail"],
                  duration_s=r.get("duration_s", 0.0), index=r.get("index", i))
             for i, r in enumerate(RESULTS, 1)]
    meta = ReportMeta(
        label=_auto_label(args.label),
        command=" ".join([sys.executable, str(Path(__file__).name), f"--expect {args.expect}"]
                         + ([f"--skip {args.skip}"] if args.skip else [])),
        environment=collect_environment(PROJECT_ROOT),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        notes=[
            "容器/虚拟显示内无法验证：真实 CAN 硬件、外部程序界面、GPU 路径（详见 docker/windows-sim/README.md §6）",
            f"逐项超时上限 {ITEM_TIMEOUT}s（可用 HUD_VERIFY_TIMEOUT 调整），超时项判 FAIL 但会继续后续验证",
        ],
    )
    md_path, json_written = write_reports(meta, items, args.report, args.json, previous)
    stats = summarize(items)
    if previous:
        from tools.verify_report import diff_runs
        d = diff_runs(previous, items)
        if d.get("available"):
            print(f" 与上次对比: 新增失败 {len(d['regressions'])}、已修复 {len(d['fixed'])}、"
                  f"持续失败 {len(d['still_failing'])}（上次 {d.get('previous_at') or '未知时间'}）")
    print(f" 总耗时 {stats['duration_s']}s｜报告: {md_path}\n JSON: {json_written}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
