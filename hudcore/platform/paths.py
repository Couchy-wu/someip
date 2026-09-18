# -*- coding: utf-8 -*-
"""
hudcore.platform.paths —— 跨平台路径约定
========================================
统一管理项目内目录，避免各处硬编码 "./logs"、"TestcaseCollection"、反斜杠拼接。

用法：
    from hudcore.platform.paths import paths
    paths.project_root        # 项目根目录
    paths.logs_dir            # <root>/logs（自动创建）
    paths.drivers_dir         # <root>/drivers/{windows|linux}
    paths.ensure(paths.output_dir)
"""
from __future__ import annotations

import os
from pathlib import Path

from .system import IS_WINDOWS, IS_LINUX, IS_MACOS


def _platform_dir_name() -> str:
    if IS_WINDOWS:
        return "windows"
    if IS_MACOS:
        return "macos"
    return "linux"


class Paths:
    """项目路径集合（懒创建，只读属性返回 Path）"""

    def __init__(self, root: Path | None = None):
        # hudcore/platform/paths.py -> 上溯两级 = 项目根
        self.project_root: Path = (root or Path(__file__).resolve().parents[2]).resolve()
        self.platform_dir_name: str = _platform_dir_name()

    # ---- 项目内目录 ----
    @property
    def logs_dir(self) -> Path:
        return self._ensure(self.project_root / "logs")

    @property
    def output_dir(self) -> Path:
        return self._ensure(self.project_root / "output")

    @property
    def output_ocr_dir(self) -> Path:
        return self._ensure(self.project_root / "output_ocr")

    @property
    def testcase_dir(self) -> Path:
        """测试用例集合目录"""
        return self._ensure(self.project_root / "TestcaseCollection")

    @property
    def resources_dir(self) -> Path:
        return self.project_root / "Resources"

    @property
    def models_dir(self) -> Path:
        return self.project_root / "models"

    @property
    def docs_dir(self) -> Path:
        return self.project_root / "docs"

    # ---- 平台相关目录（驱动 / 外部可执行）----
    @property
    def drivers_dir(self) -> Path:
        """当前平台的 CAN 驱动库目录：drivers/windows | drivers/linux"""
        return self._ensure(self.project_root / "drivers" / self.platform_dir_name)

    @property
    def drivers_all_dir(self) -> Path:
        return self.project_root / "drivers"

    @property
    def bin_dir(self) -> Path:
        """当前平台的外部可执行文件目录：bin/windows | bin/linux"""
        return self._ensure(self.project_root / "bin" / self.platform_dir_name)

    # ---- 辅助 ----
    @staticmethod
    def _ensure(p: Path) -> Path:
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return p

    def ensure(self, p: Path | str) -> Path:
        """确保目录存在并返回 Path"""
        p = Path(p)
        return self._ensure(p if p.is_absolute() else self.project_root / p)

    def to_posix(self, p: Path | str) -> str:
        """转为正斜杠字符串（跨平台拼接/显示用）"""
        return str(p).replace(os.sep, "/")


paths = Paths()
