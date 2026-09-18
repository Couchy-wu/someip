# -*- coding: utf-8 -*-
"""
hudcore.platform.executables —— 外部程序探测与调用
==================================================
解决"Windows 上写死 .exe 路径 / Linux 上找不到程序"的问题：
统一用**探测链**（项目 bin 目录 → PATH → 平台常见安装路径）找可执行文件，
并用平台原生方式打开文件。

用法：
    from hudcore.platform.executables import (
        find_executable, get_ffmpeg, get_office_app,
        open_with_default_app, open_in_text_editor)
    ff = get_ffmpeg()                      # Path 或 None
    open_with_default_app("a.xlsx")        # Windows: startfile / Linux: xdg-open
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from .system import IS_WINDOWS, IS_LINUX, IS_MACOS, exe_suffix
from .paths import paths

# ---------------------------------------------------------------- 基础探测

def find_executable(names: Iterable[str] | str,
                    extra_dirs: Iterable[Path | str] = (),
                    env_var: Optional[str] = None) -> Optional[Path]:
    """
    跨平台查找可执行文件。

    查找顺序：
      1. 环境变量 `env_var` 指定的路径（若存在且可执行）
      2. 项目 bin 目录（bin/<platform>/）
      3. PATH（shutil.which）
      4. extra_dirs 指定的附加目录
      5. 平台常见安装路径（Windows: Program Files；Linux: /usr/bin 等）

    :param names: 候选可执行名（可含多个候选，如 ["soffice", "libreoffice"]）
    :param extra_dirs: 附加搜索目录
    :param env_var: 可覆盖的环境变量名（如 "HUD_FFMPEG"）
    :return: 首个命中的 Path；找不到返回 None
    """
    if isinstance(names, str):
        names = [names]

    # 1) 环境变量优先
    if env_var:
        cand = os.environ.get(env_var)
        if cand:
            p = Path(cand).expanduser()
            if p.is_file():
                return p

    search_dirs: list[Path] = [paths.bin_dir]
    search_dirs += [Path(d) for d in extra_dirs]

    # 2) 项目 bin 目录 + 附加目录（含带/不带 .exe 后缀）
    for d in search_dirs:
        for name in names:
            for cand_name in {name, f"{name}{exe_suffix}"}:
                p = d / cand_name
                if p.is_file():
                    return p

    # 3) PATH
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)

    # 4) 平台常见安装路径
    for d in _platform_search_dirs():
        for name in names:
            for cand_name in {name, f"{name}{exe_suffix}"}:
                p = d / cand_name
                if p.is_file():
                    return p
    return None


def _platform_search_dirs() -> list[Path]:
    """平台常见安装目录"""
    dirs: list[Path] = []
    if IS_WINDOWS:
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                dirs.append(Path(base))
        # 常见：WPS 多版本目录、ffmpeg 解压目录
        dirs += [Path(r"C:\Program Files (x86)\Kingsoft\WPS Office"),
                 Path(r"C:\Program Files\Kingsoft\WPS Office"),
                 Path(r"C:\ffmpeg\bin"), Path(r"C:\Program Files\ffmpeg\bin")]
    elif IS_LINUX:
        dirs += [Path("/usr/bin"), Path("/usr/local/bin"), Path("/bin"),
                 Path("/snap/bin"), Path("/opt")]
    elif IS_MACOS:
        dirs += [Path("/usr/local/bin"), Path("/opt/homebrew/bin")]
    return [d for d in dirs if d.exists()]


# ---------------------------------------------------------------- 具体程序

def get_ffmpeg() -> Optional[Path]:
    """ffmpeg 可执行文件（可用环境变量 HUD_FFMPEG 覆盖）"""
    return find_executable(["ffmpeg"], env_var="HUD_FFMPEG")


def get_office_app() -> Optional[Path]:
    """
    表格/文档应用（用于打开测试用例 xlsx）。
    Windows: WPS(et.exe) → Excel
    Linux  : libreoffice / soffice / localc
    macOS  : 交给系统 open
    """
    if IS_WINDOWS:
        # WPS 的 et.exe 在各版本子目录下，递归查找
        for wps_root in (Path(r"C:\Program Files (x86)\Kingsoft\WPS Office"),
                         Path(r"C:\Program Files\Kingsoft\WPS Office")):
            if wps_root.is_dir():
                for root, _dirs, files in os.walk(wps_root):
                    if "et.exe" in files:
                        return Path(root) / "et.exe"
        return find_executable(["excel", "et"])
    if IS_LINUX:
        return find_executable(["libreoffice", "soffice", "localc", "onlyoffice-desktopeditors"])
    return None


def get_text_editor() -> Optional[Path]:
    """
    文本编辑器（查看解析日志用）。
    Windows: notepad++ → notepad ；Linux: gedit/kate/xdg-open ；macOS: 交给 open
    """
    if IS_WINDOWS:
        return find_executable(["notepad++", "notepad"])
    if IS_LINUX:
        return find_executable(["gedit", "kate", "mousepad", "xdg-open"])
    return None


def get_terminal() -> Optional[Path]:
    """终端程序（需要独立终端运行子命令时用）"""
    if IS_WINDOWS:
        return find_executable(["wt", "powershell", "cmd"])
    if IS_LINUX:
        return find_executable(["gnome-terminal", "konsole", "xterm"])
    return None


# ---------------------------------------------------------------- 打开文件

def open_with_default_app(path: Path | str) -> bool:
    """
    用系统默认程序打开文件（跨平台）。
    Windows: os.startfile ；Linux: xdg-open ；macOS: open
    """
    p = Path(path)
    if not p.exists():
        return False
    try:
        if IS_WINDOWS:
            os.startfile(str(p))                       # type: ignore[attr-defined]
        elif IS_LINUX:
            subprocess.Popen(["xdg-open", str(p)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif IS_MACOS:
            subprocess.Popen(["open", str(p)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            return False
        return True
    except Exception:
        return False


def open_in_text_editor(path: Path | str) -> bool:
    """用文本编辑器打开（找不到编辑器时回退到系统默认程序）"""
    editor = get_text_editor()
    if editor:
        try:
            subprocess.Popen([str(editor), str(path)], close_fds=True)
            return True
        except Exception:
            pass
    return open_with_default_app(path)


def open_in_office_app(path: Path | str) -> bool:
    """
    用表格应用打开（Windows: WPS/Excel；Linux: libreoffice）
    找不到时回退到系统默认程序。
    """
    app = get_office_app()
    if app:
        try:
            subprocess.Popen([str(app), str(Path(path).resolve())], close_fds=True)
            return True
        except Exception:
            pass
    return open_with_default_app(path)
