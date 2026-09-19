#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/check_static.py —— 静态检查闸门（pyflakes）
=================================================
用途：在"移动/拆分模块"这类机械重构后兜底，抓出**导入期与运行期都不会暴露、
      只有在真正跑到那行代码时才炸**的问题，典型如：

        · undefined name —— 通配符导入改显式导入后漏了名字、拆分后漏 import
        · redefinition   —— 重复定义
        · import *       —— 绕过包结构的写法（本项目约定禁止）

为什么必须有它：验证套件只能覆盖"被调用到的路径"，而 CAN 设备、图标管理器等
界面/硬件路径在容器里跑不到；`undefined name` 属于静态可判定错误，应当在此拦截。

用法：
    python tools/check_static.py            # 报告问题；有 undefined name 时退出码 1
    python tools/check_static.py --strict   # 任何问题（含未使用导入）都视为失败
    python tools/check_static.py -v         # 打印被检查的文件数

依赖：pyflakes（未安装时给出明确安装提示并跳过，退出码 0，避免阻断无该工具的现场）
      安装：pip install pyflakes
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 第三方/资源目录：不属于"自研代码"，不做静态检查
SKIP_DIRS = {
    "PaddleOCR-main", "yolo_framework", "kerneldlls", "vendor", "__pycache__",
    ".git", ".idea", ".vscode", "Resources", "models", "bin", "logs",
    "output", "output_ocr", "TestcaseCollection", "drivers",
}

# 视为"必须修复"的问题类别（会导致运行期错误或明确的代码缺陷）
#   · undefined name  —— 名字未定义，跑到即崩
#   · redefinition    —— 重复定义（后者覆盖前者，易造成语义误判）
#   · import *        —— 绕过包结构的写法（本项目禁止）
# 未使用变量/导入属于"死代码提示"，不阻断（用 --strict 可升级为失败）
CRITICAL = ("undefined name", "redefinition", "import *")


def iter_files() -> list[Path]:
    files = []
    for p in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        files.append(p)
    return files


def run_pyflakes(files: list[Path]) -> tuple[int, list[str]]:
    """分批调用 pyflakes（避免超长命令行），返回 (退出码, 输出行)。"""
    out_lines: list[str] = []
    rc = 0
    batch = 60
    for i in range(0, len(files), batch):
        chunk = [str(f.relative_to(ROOT)) for f in files[i:i + batch]]
        r = subprocess.run([sys.executable, "-m", "pyflakes", *chunk],
                           cwd=str(ROOT), capture_output=True, text=True)
        rc = rc or r.returncode
        out_lines += [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    return rc, out_lines


def main() -> int:
    ap = argparse.ArgumentParser(description="pyflakes 静态检查闸门")
    ap.add_argument("--strict", action="store_true", help="任何问题都判失败")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if importlib.util.find_spec("pyflakes") is None:
        print("[跳过] 未安装 pyflakes：pip install pyflakes")
        print("       （该检查用于拦截 undefined name 等机械重构残留问题，建议安装）")
        return 0

    files = iter_files()
    if args.verbose:
        print(f"检查文件: {len(files)} 个")
    rc, lines = run_pyflakes(files)

    critical = [l for l in lines if any(k in l for k in CRITICAL)]
    others = [l for l in lines if l not in critical]

    print(f"静态检查（pyflakes）：{len(files)} 个文件")
    print(f"  严重问题（undefined name / 重复定义 / 通配符导入）: {len(critical)}")
    print(f"  其他提示（未使用导入等）: {len(others)}")
    for l in critical:
        print("  ✗ " + l)
    if args.verbose:
        for l in others:
            print("  · " + l)

    if critical:
        print("\n存在严重静态问题：请修复后再继续（这类问题运行时才会暴露，"
              "容器验证覆盖不到所有路径）")
        return 1
    if args.strict and others:
        print("\n--strict：存在其他提示，判失败")
        return 1
    print("静态检查通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
