# -*- coding: utf-8 -*-
"""tests/test_architecture_rules.py —— 架构规则守卫（防回归）

这些测试把 P0/P1 阶段确立的**结构约定**固化成可执行的断言，
避免后续开发（或下一轮重构）把它们悄悄破坏：

  1. 每个业务包都必须有 `__init__.py`（包边界显式化）
  2. 自研代码里不得出现 `import *`（命名空间污染）
  3. 业务代码不得用 `sys.path.append/insert` 绕过包结构
     （`tools/` 下的独立脚本与依赖第三方目录的脚本除外）
  4. 不得在模块级产生副作用：`tk.Tk()` / `mainloop()` / `parse_args()`
     （导入即建界面、导入即解析命令行，都会让模块无法作为库使用）
  5. 根目录只放入口脚本，共享库模块必须在包内
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# 第三方/资源目录：不属于自研代码
SKIP_DIRS = {
    "PaddleOCR-main", "yolo_framework", "kerneldlls", "vendor", "__pycache__",
    ".git", ".idea", ".vscode", "Resources", "models", "bin", "logs",
    "output", "output_ocr", "TestcaseCollection", "drivers", "tests",
    "docker",          # 验证工程（自身需要 sys.path 注入以便挂载运行）
}

# 允许保留 sys.path 注入的脚本：独立工具（需在任意目录运行）/ 依赖第三方源码目录
SYS_PATH_ALLOWED = {"ocr_icon_test.py"}


def own_py_files() -> list[Path]:
    out = []
    for p in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        out.append(p)
    return out


def test_every_package_has_init():
    """业务包必须有 __init__.py（声明包边界与职责）。"""
    packages = set()
    for p in own_py_files():
        rel = p.relative_to(ROOT)
        if len(rel.parts) > 1 and rel.parts[0] in {
            "hudcore", "can_core", "gui_handlers", "can_gui", "can_data_tools",
            "image_testing", "camera_tools", "misc_tools", "auto_labeling",
        }:
            packages.add(rel.parts[0])
    assert packages, "未识别到任何业务包，检查目录结构"
    missing = [pkg for pkg in sorted(packages) if not (ROOT / pkg / "__init__.py").is_file()]
    assert not missing, f"以下包缺少 __init__.py：{missing}"


def test_no_wildcard_imports():
    """不得使用 `from x import *`（绕过包结构、污染命名空间）。"""
    offenders = []
    for p in own_py_files():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:                      # 语法错误由静态检查单独负责
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                offenders.append(f"{p.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, f"存在通配符导入：{offenders}"


def test_no_sys_path_hacks_in_business_code():
    """业务代码不得用 sys.path 注入绕过包结构（独立脚本白名单除外）。"""
    offenders = []
    for p in own_py_files():
        rel = p.relative_to(ROOT)
        if rel.parts[0] == "tools" or p.name in SYS_PATH_ALLOWED:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Attribute)
                    and isinstance(node.func.value.value, ast.Name)
                    and node.func.value.value.id == "sys"
                    and node.func.value.attr == "path"
                    and node.func.attr in ("append", "insert")):
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, f"业务代码中存在 sys.path 注入：{offenders}"


def test_no_module_level_side_effects():
    """模块级不得建 GUI / 跑 mainloop / 解析命令行参数（导入副作用）。"""
    offenders = []
    for p in own_py_files():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:                    # 只看模块级语句
            if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                continue
            fn = node.value.func
            name = getattr(fn, "attr", getattr(fn, "id", ""))
            if name in ("mainloop", "Tk", "Toplevel", "parse_args"):
                offenders.append(f"{p.relative_to(ROOT)}:{node.lineno} → {name}()")
    assert not offenders, f"模块级副作用：{offenders}"


@pytest.mark.parametrize("name", ["main.py"])
def test_root_keeps_only_entry_points(name):
    """根目录只保留入口脚本；共享库模块必须在包内。"""
    root_py = {p.name for p in ROOT.glob("*.py")}
    assert name in root_py
    # 允许保留在根目录的：入口与独立脚本
    allowed = {"main.py", "ocr_icon_test.py", "yolo_train.py"}
    extra = sorted(root_py - allowed)
    assert not extra, f"根目录出现非入口模块（应下沉到包内）：{extra}"
