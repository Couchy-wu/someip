#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/check_imports.py —— 项目内部导入静态校验
===============================================
用途：不启动 GUI、不加载重依赖，静态检查"项目内部模块"的 import 是否都能解析到
      真实存在的 .py 文件 / 包目录。重构（改名、移动目录）后用它兜底，
      避免出现"改完名、import 还是旧名"的隐性错误。

判定规则：
    · 只校验"项目内"的顶层模块名（项目根下存在的 .py 或目录）；
    · 第三方库、标准库一律忽略（不联网、不导入）；
    · 支持 `import a.b.c`、`from a.b import c`、相对导入（from . import x）；
    · 相对导入按文件所在包逐级回溯，解析到项目根为止。

用法：
    python tools/check_imports.py            # 检查并汇总
    python tools/check_imports.py -v         # 打印每个文件的导入来源
退出码：0 = 全部可解析；1 = 存在无法解析的项目内导入。
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 第三方/生成目录：不参与校验
SKIP_DIRS = {
    ".git", "__pycache__", ".idea", ".vscode", ".venv", "venv", "node_modules",
    "yolo_framework", "YOLO+=+_", "PaddleOCR-main", "kerneldlls",
    "vendor", "ffmpeg", "models", "Resources", "output", "output_ocr", "logs", "bin",
    "dataset", "muban", "template_matching",
}

# 顶层名 → 对应文件/目录是否存在
_TOP_CACHE: dict[str, bool] = {}


def top_level_exists(name: str) -> bool:
    """项目根下是否存在该顶层模块（.py 文件或包目录）。"""
    if name in _TOP_CACHE:
        return _TOP_CACHE[name]
    ok = (ROOT / f"{name}.py").is_file() or (ROOT / name).is_dir()
    _TOP_CACHE[name] = ok
    return ok


def module_target_ok(*parts: str) -> bool:
    """判断模块路径是否存在，接受两种形态：
      · 普通包/模块：<pkg>/__init__.py 或 <pkg>.py
      · 命名空间包：只有目录、没有 __init__.py（本项目的 gui_handlers/ 等即属此类）
    """
    if not parts:
        return False
    target = ROOT.joinpath(*parts)
    return (target.with_suffix(".py").is_file()
            or (target / "__init__.py").is_file()
            or target.is_dir())


def resolve_from(base_pkg: list[str], module: str | None, name: str) -> Path | None:
    """把 `from <base>.<module> import <name>` 解析成候选文件路径列表。"""
    parts = list(base_pkg)
    if module:
        parts += module.split(".")
    # from X import y ：y 可能是子模块，也可能是模块内的函数/类
    candidates = [ROOT.joinpath(*parts, f"{name}.py"),
                  ROOT.joinpath(*parts, name, "__init__.py")]
    if parts:
        candidates.append(ROOT.joinpath(*parts).with_suffix(".py"))
    for c in candidates:
        if c.is_file():
            return c
    return None


def check_file(path: Path, verbose: bool) -> list[str]:
    problems: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [f"{path.relative_to(ROOT)}: 语法/编码错误: {exc}"]

    rel = path.relative_to(ROOT)
    # 当前文件所在包（相对导入用）
    pkg = list(rel.parts[:-1])
    if path.name == "__init__.py":
        pkg = list(rel.parts[:-1])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if not top_level_exists(top):
                    continue                      # 第三方/标准库
                if not module_target_ok(*alias.name.split(".")):
                    problems.append(
                        f"{rel}:{node.lineno}: import {alias.name} → 未找到对应模块文件")
                elif verbose:
                    print(f"  {rel}:{node.lineno}: import {alias.name} ✓")

        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = (node.module or "").split(".") if node.module else []
                top = base[0] if base else ""
                if not top or not top_level_exists(top):
                    continue                      # 第三方/标准库
                if node.module:
                    if not module_target_ok(*base):
                        problems.append(
                            f"{rel}:{node.lineno}: from {node.module} import ... "
                            f"→ 未找到模块文件")
                        continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    if resolve_from([], node.module, alias.name):
                        if verbose:
                            print(f"  {rel}:{node.lineno}: from {node.module} import {alias.name} ✓")
            else:
                # 相对导入：从当前包向上 level-1 级
                up = node.level - 1
                base = pkg[: len(pkg) - up] if up <= len(pkg) else []
                base = [b for b in base if b not in ("", ".")]
                if base and not (ROOT.joinpath(*base).is_dir()):
                    continue
                module = node.module or ""
                if module:
                    if not module_target_ok(*base, *module.split(".")):
                        problems.append(
                            f"{rel}:{node.lineno}: from {'.' * node.level}{module} "
                            f"import ... → 未找到模块文件")
                        continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    if resolve_from(base, module or None, alias.name):
                        if verbose:
                            print(f"  {rel}:{node.lineno}: from {'.'*node.level}{module} "
                                  f"import {alias.name} ✓")
                    elif module:
                        # from .mod import name —— name 应是 mod 内的符号；无法静态确证时
                        # 只提示"未找到同名子模块"，不判定为错误（避免误报）
                        continue
    return problems


def iter_py():
    for p in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def main() -> int:
    ap = argparse.ArgumentParser(description="项目内部导入静态校验")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每个导入")
    args = ap.parse_args()

    count, problems = 0, []
    for path in iter_py():
        count += 1
        problems += check_file(path, args.verbose)

    print(f"\n检查文件: {count} 个")
    if problems:
        print(f"发现问题: {len(problems)} 处")
        for p in problems:
            print("  ✗ " + p)
        return 1
    print("项目内部导入全部可解析 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
