# -*- coding: utf-8 -*-
"""
hudcore.platform.fonts —— 跨平台界面字体
========================================
解决 Windows 写死 "微软雅黑"、Ubuntu 上字体不存在导致界面乱码/方块的问题。

字体回退链（按平台）：
  Windows : 微软雅黑 → Microsoft YaHei → SimHei → Arial
  Linux   : Noto Sans CJK SC → Source Han Sans SC → WenQuanYi Micro Hei → DejaVu Sans
  macOS   : PingFang SC → Heiti SC → Helvetica

用法：
    from hudcore.platform.fonts import get_ui_font_name, get_ui_font
    name = get_ui_font_name()                  # 字符串，直接给 tk.Label(font=(name, 10))
    f = get_ui_font(size=10, weight="bold")    # tkfont.Font（需要已存在 Tk root）
"""
from __future__ import annotations

from typing import Optional

from .system import IS_WINDOWS, IS_LINUX, IS_MACOS

# 各平台字体回退链（首选在前）
FONT_CHAIN: dict[str, list[str]] = {
    "windows": ["微软雅黑", "Microsoft YaHei", "SimHei", "SimSun", "Arial"],
    "linux": ["Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei",
              "WenQuanYi Zen Hei", "AR PL UMing CN", "DejaVu Sans", "Liberation Sans"],
    "macos": ["PingFang SC", "Heiti SC", "STHeiti", "Helvetica"],
}


def _chain() -> list[str]:
    if IS_WINDOWS:
        return FONT_CHAIN["windows"]
    if IS_MACOS:
        return FONT_CHAIN["macos"]
    return FONT_CHAIN["linux"]


_cached_name: Optional[str] = None


def list_available_fonts() -> list[str]:
    """列出 Tk 可用字体族（需要已创建 Tk root；失败返回空列表）"""
    try:
        from tkinter import font as tkfont
        return sorted(tkfont.families())
    except Exception:
        return []


def get_ui_font_name(verify: bool = True) -> str:
    """
    返回当前平台可用的界面字体名（回退链首个可用项）。

    :param verify: True 时用 Tk 实际校验字体是否存在（需要 Tk root；
                   无 root 或校验失败时返回链首，由 Tk 自行回退）
    """
    global _cached_name
    if _cached_name:
        return _cached_name
    chain = _chain()
    if verify:
        available = list_available_fonts()
        if available:
            # Tk 字体名大小写不敏感匹配
            lower_map = {f.lower(): f for f in available}
            for name in chain:
                hit = lower_map.get(name.lower())
                if hit:
                    _cached_name = hit
                    return hit
    _cached_name = chain[0]
    return _cached_name


def get_ui_font(size: int = 10, weight: str = "normal", root=None):
    """
    返回 tkinter.font.Font 对象（跨平台字体）。

    :param size: 字号
    :param weight: "normal" / "bold"
    :param root: Tk 实例（多 root 场景显式传入；默认使用当前默认 root）
    """
    from tkinter import font as tkfont
    return tkfont.Font(root=root, family=get_ui_font_name(), size=size, weight=weight)


def get_ui_font_tuple(size: int = 10, weight: str = "normal") -> tuple:
    """返回 (family, size, weight) 元组，可直接用于多数 Tk 控件的 font= 参数"""
    return (get_ui_font_name(), size, weight)


def reset_cache() -> None:
    """清空字体缓存（测试或多 root 场景用）"""
    global _cached_name
    _cached_name = None

# ---------------------------------------------------------------- 字体文件（PIL / OpenCV 用）

# 各平台常见中文字体文件（按优先级）
_FONT_FILES: dict[str, list[str]] = {
    "windows": [
        r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\arial.ttf",
    ],
    "linux": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
    "macos": [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/Library/Fonts/Arial.ttf",
    ],
}

_font_file_cache: list = [None, False]   # [path, resolved]


def get_cjk_font_path():
    """
    返回系统中可用的中文字体文件路径（供 PIL.ImageFont / OpenCV putText 使用）。
    找不到返回 None。Linux 上会尝试 fc-match 兜底。
    """
    from pathlib import Path
    if _font_file_cache[1]:
        return _font_file_cache[0]

    key = "windows" if IS_WINDOWS else "macos" if IS_MACOS else "linux"
    for cand in _FONT_FILES.get(key, []):
        try:
            p = Path(cand)
            if p.is_file():
                _font_file_cache[0] = p
                _font_file_cache[1] = True
                return p
        except OSError:
            continue

    # Linux 兜底：用 fontconfig 按字体名查文件
    if IS_LINUX:
        import subprocess
        for name in (_chain() + ["sans-serif"]):
            try:
                out = subprocess.run(["fc-match", "-f", "%{file}", name],
                                     capture_output=True, text=True, timeout=5).stdout.strip()
                if out and Path(out).is_file():
                    _font_file_cache[0] = Path(out)
                    _font_file_cache[1] = True
                    return Path(out)
            except Exception:
                break

    _font_file_cache[1] = True
    return None


def load_pil_font(size: int = 12):
    """
    加载 PIL 字体（供 ImageDraw 绘制中文），跨平台自动选择字体文件；
    找不到时回退到 PIL 默认字体（不支持中文，但保证不报错）。

    用法：
        from hudcore.platform.fonts import load_pil_font
        font = load_pil_font(32)
        draw.text((10, 10), "你好", font=font, fill=(255, 0, 0))
    """
    from PIL import ImageFont
    path = get_cjk_font_path()
    if path:
        try:
            return ImageFont.truetype(str(path), size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def reset_font_file_cache() -> None:
    _font_file_cache[0] = None
    _font_file_cache[1] = False
