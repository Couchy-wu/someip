#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_deps.py —— 在 Wine 的 Windows Python 中校验依赖是否可用
================================================================
用途：镜像构建阶段的"依赖自检"。由 Dockerfile 复制进镜像后用
      `wine C:\\Python313\\python.exe Z:\\opt\\check_deps.py` 执行。

为什么单独放一个文件：
  Dockerfile 的 RUN 里写 heredoc 需要 BuildKit 语法支持，用独立脚本
  可以兼容传统 builder，也便于本地复用。

输出：每个依赖一行 OK/FAIL + 版本号；有 FAIL 时退出码为 1（构建即失败，
      避免"装了个空壳镜像、跑到验证阶段才发现缺依赖"）。
"""
from __future__ import annotations

import sys

MODULES = [
    # 运行期必需
    "tkinter", "numpy", "pandas", "openpyxl", "PIL", "cv2",
    # 可选（缺失时对应功能禁用，但主程序仍可启动）
    "yaml", "requests", "psutil", "pyperclip", "watchdog", "ffmpeg", "tqdm", "natsort",
]

failed: list[str] = []
print(f"Python: {sys.version.split()[0]}  |  {sys.platform}")
for name in MODULES:
    try:
        mod = __import__(name)
        ver = getattr(mod, "__version__", "") or getattr(mod, "TkVersion", "")
        print(f"  OK   {name:12s} {ver}")
    except Exception as exc:                       # noqa: BLE001
        print(f"  FAIL {name:12s} {type(exc).__name__}: {exc}")
        failed.append(name)

if failed:
    print(f"\n缺少依赖: {failed}")
    sys.exit(1)
print("\n全部依赖可用 ✓")
