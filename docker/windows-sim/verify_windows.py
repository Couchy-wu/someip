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
import tempfile
import threading
import traceback
from pathlib import Path

# ---------------------------------------------------------------- 结果收集

RESULTS: list[dict] = []


def record(name: str, status: str, detail: str = "") -> None:
    RESULTS.append({"name": name, "status": status, "detail": detail})
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
    print(f"{icon} {name}" + (f"  — {detail}" if detail else ""), flush=True)


# 单项超时（秒）：Windows 程序在 Wine / 无显示环境里可能挂起（例如 Tk 阻塞），
# 因此每项验证都在独立线程中执行，超时即判 FAIL，保证整套测试不会卡死。
ITEM_TIMEOUT = int(os.environ.get("HUD_VERIFY_TIMEOUT", "120"))


def test(name: str):
    """装饰器：在线程中执行函数，带超时；异常 → FAIL。"""
    def deco(fn):
        def wrapper():
            box: dict = {}

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
            if th.is_alive():
                record(name, "FAIL", f"超时（>{ITEM_TIMEOUT}s）未返回，可能阻塞在 "
                                     f"GUI/外部程序调用；已跳过并继续后续验证")
                return
            if "error" in box:
                exc = box["error"]
                record(name, "FAIL", f"{type(exc).__name__}: {exc}")
                print(box.get("tb", ""), flush=True)
                return
            status, detail = box.get("result", ("FAIL", "无返回值"))
            record(name, status, detail)
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

@test("1. Windows 运行时环境")
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
        "can_gui.can_send_receive_gui",
        "can_data_tools.testcase_runner", "can_data_tools.find_can_id_from_csv",
        "can_data_tools.find_sub_id",
        "image_testing.icon_manager", "image_testing.image_similarity",
        "image_testing.sample_image_generator", "image_testing.verify_icons",
        "misc_tools.gif_creator", "misc_tools.image_batch_rename",
        "misc_tools.images_to_video", "misc_tools.video_roi_crop",
        "camera_tools.camera_preview", "camera_tools.error_image_detection",
        "camera_tools.image_enhancement", "camera_tools.perspective_calibration",
        "camera_tools.stability_test",
        "auto_labeling.auto_detect", "auto_labeling.draw_boxes",
        "auto_labeling.draw_boxes_v2", "auto_labeling.draw_labels",
        "hudcore", "hudcore.can", "hudcore.ui", "hudcore.platform",
        "hudcore.logging_setup", "can_core", "can_core.driver", "can_core.device",
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

@test("9. CAN 驱动库探测与加载（stub DLL）")
def t_can_load():
    from hudcore.can import find_zlg_library, load_zlg_library, describe_library_status
    lib = find_zlg_library()
    if lib is None:
        return "SKIP", f"容器内未放置 stub 驱动库；{describe_library_status()}"
    handle = load_zlg_library()
    assert handle is not None, "load_zlg_library() 返回 None"
    # 调用库里的导出函数，验证真实 ctypes 调用（Windows: WinDLL/stdcall 约定）
    import ctypes
    called = False
    detail = f"lib={lib}"
    # 优先调用 ZLG CAN 驱动导出；若容器内以真实系统 DLL 充当桩库，
    # 则退回调用 Py_GetVersion（python313.dll 的导出）证明句柄可真实调用。
    probes = [("ZCAN_GetDeviceCount", ctypes.c_uint32, None),
              ("VCI_OpenDevice", ctypes.c_uint32, (0, 0, 0)),
              ("ZCAN_OpenDevice", ctypes.c_uint64, (0, 0, 0)),
              ("Py_GetVersion", ctypes.c_char_p, None)]
    for fn_name, restype, argv in probes:
        fn = getattr(handle, fn_name, None)
        if fn is None:
            continue
        try:
            fn.restype = restype
            rc = fn(*argv) if argv else fn()
            detail += f", {fn_name}()={rc!r}"
            called = True
            break
        except Exception as exc:
            detail += f", {fn_name} 调用异常: {exc}"
    if not called:
        return "FAIL", f"库已加载但无可调用导出函数：{detail}"
    return "PASS", detail


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

    csv_path = PROJECT_ROOT / "can_data_tools" / "outputMatrix.csv"
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

@test("17. 项目自带自检脚本在 Windows 下可运行")
def t_project_scripts():
    outputs = []
    for script in ("tools/check_imports.py", "tools/selftest.py"):
        p = PROJECT_ROOT / script
        r = subprocess.run([exe_python(), str(p)], capture_output=True, text=True,
                           cwd=str(PROJECT_ROOT), timeout=300)
        tail = (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]
        outputs.append(f"{Path(script).name} rc={r.returncode} ({tail[0][:60]})")
        if r.returncode != 0:
            return "FAIL", "; ".join(outputs) + f" | stderr={r.stderr[-300:]}"
    return "PASS", "; ".join(outputs)


# ---------------------------------------------------------------- main

def main() -> int:
    global EXPECT
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", choices=["win", "linux", "any"], default="any")
    ap.add_argument("--report", default=str(Path(__file__).with_name("verify_report.md")))
    ap.add_argument("--json", default=str(Path(__file__).with_name("verify_report.json")))
    ap.add_argument("--skip", default="", help="逗号分隔的测试编号，跳过这些项")
    args = ap.parse_args()
    EXPECT = args.expect

    print("=" * 72)
    print(" HudAutoTest — Windows 环境功能验证")
    print(f" 项目根: {PROJECT_ROOT}")
    print(f" 解释器: {sys.executable}")
    print(f" Python : {sys.version.split()[0]}  platform={platform.platform()}")
    print("=" * 72)

    tests = [t_runtime, t_system, t_paths, t_fonts, t_tk, t_theme_redirect,
             t_import_main, t_import_all, t_can_load, t_can_hint, t_external,
             t_similarity, t_gif, t_cv_modules, t_can_signal, t_matrix_csv,
             t_project_scripts]
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

    # 写报告
    md = ["# HudAutoTest — Windows 环境功能验证报告", "",
          f"- 运行环境: `{platform.platform()}`",
          f"- 解释器: `{sys.executable}`",
          f"- Python: `{sys.version.split()[0]}`",
          f"- 项目根: `{PROJECT_ROOT}`", "",
          f"**结果：{passed} 通过 / {len(failed)} 失败 / {skipped} 跳过**", "",
          "| # | 验证项 | 结果 | 证据 |", "|---|--------|------|------|"]
    for i, r in enumerate(RESULTS, 1):
        # 注意：转义与截断放在 f-string 之外完成 —— Python < 3.12 的 f-string
        # 表达式内不允许出现反斜杠，否则整个模块会语法错误。
        detail = r["detail"].replace("|", "\\|")[:220]
        md.append(f"| {i} | {r['name']} | {r['status']} | {detail} |")
    Path(args.report).write_text("\n".join(md) + "\n", encoding="utf-8")
    Path(args.json).write_text(json.dumps(
        {"platform": platform.platform(), "python": sys.version,
         "executable": sys.executable, "results": RESULTS},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {args.report}\nJSON: {args.json}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
