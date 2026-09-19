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

from .system import IS_WINDOWS, IS_LINUX, IS_MACOS, arch_name


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
        # 形如 linux-x86_64 / linux-aarch64：用于按"平台+架构"分目录存放第三方运行时库
        # （同名库在 aarch64 与 x86_64 上 ABI 不兼容，混放会导致 dlopen 报 wrong ELF class）
        self.platform_arch_dir_name: str = f"{self.platform_dir_name}-{arch_name()}"

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
        """界面资源（图标/图片素材等，随仓库分发、只读）"""
        return self.project_root / "Resources"

    @property
    def data_dir(self) -> Path:
        """应用数据目录（业务数据与运行期状态，与代码分离）

        内容示例：
            outputMatrix.csv          信号矩阵（业务输入数据）
            can_device_config.xml     设备配置
            platform_resolution.json  平台分辨率映射
            fixed_corners.json        透视标定结果（运行期生成）
            UI_Config/                界面工具生成的配置文件
        设计目的：避免"业务数据/运行期状态散落在代码包里"，
        也避免相对当前工作目录的路径导致换目录即失效。
        """
        return self._ensure(self.project_root / "data")

    @property
    def thirdparty_dir(self) -> Path:
        """第三方内容目录（统一收纳，按子目录分别管理）

        约定（见 thirdparty/README.md）：
            thirdparty/ultralytics/   YOLO 框架源码
            thirdparty/paddleocr/     PaddleOCR 源码
            thirdparty/zlg/           ZLG CAN SDK 资源
            thirdparty/ffmpeg/        随项目分发的 ffmpeg 构建
            thirdparty/models/        第三方预训练权重

        与 drivers/、bin/ 的边界：drivers/<平台>/ 与 bin/<平台>/ 是**按平台分发的
        部署目录**（现场替换库/可执行文件、且被 .gitignore 忽略），不属于"随仓库
        分发的第三方源码"，因此保留在项目根。
        """
        return self.project_root / "thirdparty"

    def thirdparty(self, name: str, *legacy_relpaths: str) -> Path:
        """取第三方子目录；若新位置不存在则回退到旧位置（便于平滑迁移）。

        :param name: 子目录名（如 "ultralytics"）
        :param legacy_relpaths: 旧相对路径（如 "yolo_framework/ultralytics-8.3.217"）
        """
        new = self.thirdparty_dir / name
        if new.exists():
            return new
        for rel in legacy_relpaths:
            old = self.project_root / rel
            if old.exists():
                return old
        return new                     # 都不存在时返回约定位置（便于给出明确报错）

    @property
    def models_dir(self) -> Path:
        """第三方预训练权重目录（thirdparty/models，兼容旧 models/）"""
        return self.thirdparty("models", "models")

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
