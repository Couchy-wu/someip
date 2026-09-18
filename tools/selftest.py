#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/selftest.py —— hudcore 平台层回归自测（Windows / Ubuntu / macOS）
=======================================================================
不依赖业务数据与硬件，验证平台抽象层各项能力；GUI 相关项在无 tkinter /
无显示环境下自动跳过。

用法：
    python tools/selftest.py
退出码：0 全部通过；1 有失败项
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASS, FAIL, SKIP = "[PASS]", "[FAIL]", "[SKIP]"
results = {"pass": 0, "fail": 0, "skip": 0}


def ok(name: str, detail: str = "") -> None:
    results["pass"] += 1
    print(f"{PASS} {name}" + (f"  ({detail})" if detail else ""))


def bad(name: str, err: str) -> None:
    results["fail"] += 1
    print(f"{FAIL} {name}  -> {err}")


def skip(name: str, why: str) -> None:
    results["skip"] += 1
    print(f"{SKIP} {name}  ({why})")


def test(name: str):
    """极简测试装饰器"""
    def deco(fn):
        try:
            detail = fn()
            ok(name, detail if isinstance(detail, str) else "")
        except _Skip as e:
            skip(name, str(e))
        except Exception as e:
            bad(name, f"{type(e).__name__}: {e}")
        return fn
    return deco


class _Skip(Exception):
    pass


def section(t: str) -> None:
    print(f"\n--- {t} ---")


# ------------------------------------------------------------------ 平台层

section("platform.system")
@test("system 常量/描述")
def t_system():
    from hudcore.platform.system import (
        IS_WINDOWS, IS_LINUX, IS_MACOS, describe, exe_suffix, lib_suffix)
    assert IS_WINDOWS or IS_LINUX or IS_MACOS
    assert exe_suffix in (".exe", "")
    assert lib_suffix in (".dll", ".so")
    return describe()



section("platform.paths")
@test("paths 目录约定")
def t_paths():
    from hudcore.platform.paths import paths
    assert paths.project_root.exists(), "项目根不存在"
    assert paths.logs_dir.exists()
    assert paths.drivers_dir.exists()
    assert paths.bin_dir.exists()
    assert paths.drivers_dir.name in ("windows", "linux", "macos")
    return f"{paths.platform_dir_name} / root={paths.project_root}"



section("platform.fonts")
@test("fonts 字体名（无 Tk）")
def t_font_name():
    from hudcore.platform.fonts import get_ui_font_name
    name = get_ui_font_name()
    assert name, "字体名为空"
    return name



@test("fonts Tk 字体对象")
def t_font_tk():
    try:
        import tkinter as tk
    except ImportError:
        raise _Skip("tkinter 未安装")
    from hudcore.platform.fonts import get_ui_font, get_ui_font_tuple, list_available_fonts, reset_cache
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        raise _Skip(f"无显示环境: {type(e).__name__}")
    try:
        reset_cache()
        fams = list_available_fonts()
        f = get_ui_font(size=11, weight="bold", root=root)
        assert f.cget("size") == 11
        t = get_ui_font_tuple(12, "normal")
        assert len(t) == 3
        return f"可用字体 {len(fams)} 个, 选用 {f.cget('family')}"
    finally:
        root.destroy()



section("platform.executables")
@test("executables 查找解释器")
def t_find_exe():
    from hudcore.platform.executables import find_executable
    p = find_executable(["python3", "python", "py"])
    assert p, "连 python 解释器都找不到（异常）"
    return str(p)



@test("executables 可选工具探测")
def t_optional_tools():
    from hudcore.platform.executables import get_ffmpeg, get_office_app, get_text_editor, get_terminal
    found = {k: (str(v) if v else None)
             for k, v in (("ffmpeg", get_ffmpeg()), ("office", get_office_app()),
                          ("editor", get_text_editor()), ("terminal", get_terminal()))}
    return f"命中 {sum(1 for v in found.values() if v)}/4"



# ------------------------------------------------------------------- CAN 层

section("can.backend")
@test("can 驱动库探测")
def t_can_probe():
    from hudcore.can import describe_library_status, is_library_available
    status = describe_library_status()
    assert "候选" in status
    return "就绪" if is_library_available() else "未安装驱动库（预期，无硬件时正常）"



@test("can 缺失场景报错")
def t_can_load_missing():
    """未配置驱动库时应抛 FileNotFoundError 且带安装提示"""
    from hudcore.can import load_zlg_library
    from hudcore.can.backend import _candidates, find_zlg_library
    if find_zlg_library() is not None:
        raise _Skip("环境里已有驱动库，跳过缺失场景")
    try:
        load_zlg_library()
    except FileNotFoundError as e:
        assert "HUD_ZLG_LIB" in str(e), "提示信息不含排查指引"
        return "缺失时正确抛出 FileNotFoundError + 安装指引"
    raise AssertionError("未找到库时应当抛 FileNotFoundError")



@test("can 探测→加载→调用全链路")
def t_can_load_real(tmpname="libzlgcan.so"):
    """构造最小共享库，验证 探测 → 加载 → 调用 全链路"""
    import ctypes
    from hudcore.can import find_zlg_library, load_zlg_library
    from hudcore.platform.paths import paths

    from hudcore.can.backend import LIB_CANDIDATES
    from hudcore.platform.system import IS_WINDOWS, IS_MACOS
    lib_name = (LIB_CANDIDATES["windows"][0] if IS_WINDOWS
                else LIB_CANDIDATES["macos"][0] if IS_MACOS
                else LIB_CANDIDATES["linux"][0])
    target = paths.drivers_dir / lib_name
    if target.exists():
        raise _Skip(f"{target.name} 已存在，跳过伪造测试")

    src = Path(tempfile.mkdtemp()) / "fake.c"
    src.write_text("int arhud_selftest_api(void){return 42;}\n", encoding="utf-8")
    if not sys.platform.startswith("linux"):
        raise _Skip("非 Linux 平台跳过（库后缀/编译参数不同）")
    cmd = ["gcc", "-shared", "-fPIC", "-o", str(target), str(src)]
    if os.system(" ".join(f'"{c}"' for c in cmd) + " >/dev/null 2>&1") != 0:
        raise _Skip("无 C 编译器，跳过")
    try:
        found = find_zlg_library()
        assert found == target, f"探测结果不符: {found}"
        lib = load_zlg_library()
        fn = getattr(lib, "arhud_selftest_api", None)
        assert fn is not None, "符号未导出"
        fn.restype = ctypes.c_int
        val = fn()
        assert val == 42, f"调用结果异常: {val}"
        return "探测→加载→调用 全链路 OK (返回 42)"
    finally:
        try:
            target.unlink()
        except OSError:
            pass



# -------------------------------------------------------------------- UI 层

section("ui.theme / ui.text_redirector")
@test("Theme 控件样式")
def t_theme_styles():
    from hudcore.ui.theme import Theme
    for style in (Theme.primary_button(), Theme.danger_button(),
                  Theme.success_button(), Theme.log_text_style(),
                  Theme.label_style(bold=True)):
        assert isinstance(style, dict) and "font" in style, "样式缺少 font"
    return "5 种控件样式可用"



@test("TextRedirector stdout 重定向")
def t_redirector():
    try:
        import tkinter as tk
    except ImportError:
        raise _Skip("tkinter 未安装")
    from hudcore.ui import TextRedirector
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        raise _Skip(f"无显示环境: {type(e).__name__}")
    try:
        text = tk.Text(root)
        r = TextRedirector(text, root, poll_interval=10)
        r.write("hello\n")
        root.update()          # 触发 after 轮询
        root.update()
        content = text.get("1.0", tk.END)
        r.stop_polling()
        assert "hello" in content, f"未写入: {content!r}"
        return "stdout 重定向写入 Text 成功"
    finally:
        root.destroy()




# ---------------------------------------------------------------------- 汇总

def main() -> int:
    print("\n" + "=" * 60)
    print(f" 结果: {results['pass']} 通过 / {results['fail']} 失败 / {results['skip']} 跳过")
    print("=" * 60)
    return 1 if results["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
