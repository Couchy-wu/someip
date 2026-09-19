# -*- coding: utf-8 -*-
"""can_data_tools.label_verify —— Di 用例「标贴/标签」校验

用例的 `expected_output` 给出期望显示的标贴（`primary_label`）、不应显示的标贴
（`negative_label`）、位置约束与最低置信度。本模块负责**判定实际画面里这些标贴是否出现**：

    画面（HUD 截图/相机帧）
        → 按参考图配置（data/UI_Config/*.json）取标贴所在区域
        → 与参考图/预计算 dHash 比对（`image_testing.image_similarity`，阈值来自 min_confidence）
        → 得到 matched / mismatch / no_reference / error

标贴（英文）到参考图的映射见 `data/DI_Config/label_map.json`（可用参数覆盖）。
**没有参考图的标贴一律记为 `no_reference`**，不会当作通过 —— 避免"没验"被误读成"验过了"。

阈值语义（与项目已有实现一致）：`min_confidence` 是 0~1 的比例，换算成百分比整数
（0.9 → 90）后传给 `compare_with_precomputed_hash(img, hash, thr)`；
dHash 为 64 位，置信度 = 100 × (64 - 汉明距离) / 64。
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from hudcore import logging_setup
from hudcore.platform.paths import paths

LOGGER_NAME = "di_case"

DEFAULT_MAP = Path("data") / "DI_Config" / "label_map.json"
DEFAULT_THRESHOLD = 90                     # min_confidence 缺失/为 0 时的兜底阈值（百分比）


# --------------------------------------------------------------------------- 结果
@dataclass(frozen=True)
class RefHit:
    """一个标贴对应的参考图条目。"""

    label: str
    key: str                               # 参考图配置里的键（图片文件名）
    entry: dict                            # 配置条目（left/top/width/height/hash/name/...）
    image: Path | None = None              # 参考图路径（找不到时为 None）

    @property
    def box(self) -> tuple[int, int, int, int] | None:
        try:
            left, top = int(self.entry["left"]), int(self.entry["top"])
            width, height = int(self.entry["width"]), int(self.entry["height"])
        except (KeyError, TypeError, ValueError):
            return None
        return left, top, left + width, top + height

    @property
    def precomputed_hash(self) -> int | None:
        value = self.entry.get("hash")
        return int(value) if isinstance(value, (int, float)) else None


@dataclass(frozen=True)
class LabelVerdict:
    """单个标贴的校验结论。"""

    label: str
    role: str                              # "primary"（应显示） / "negative"（不应显示）
    status: str                            # matched / mismatch / no_reference / error / nothing
    detail: str = ""
    confidence: float | None = None
    threshold: float | None = None

    @property
    def ok(self) -> bool:
        return self.status in ("matched", "nothing")

    def describe(self) -> str:
        conf = f"，置信度 {self.confidence:.1f}%（阈值 {self.threshold:.0f}%）" \
            if self.confidence is not None else ""
        return f"[{self.role}] {self.label or '(空)'} → {self.status}{conf}｜{self.detail}"


@dataclass(frozen=True)
class FrameVerdict:
    """一次画面校验的整体结论。"""

    verdicts: tuple[LabelVerdict, ...]
    frame_size: tuple[int, int] | None = None
    background_size: tuple[int, int] | None = None
    note: str = ""

    @property
    def ok(self) -> bool:
        return all(v.ok for v in self.verdicts)

    @property
    def status(self) -> str:
        """pass / fail / unverifiable（全部无参考图时）。"""
        if not self.verdicts:
            return "unverifiable"
        if any(v.status in ("mismatch", "error") for v in self.verdicts):
            return "fail"
        if all(v.status == "no_reference" for v in self.verdicts):
            return "unverifiable"
        return "pass"

    def describe(self) -> str:
        head = f"画面校验={self.status}"
        if self.frame_size:
            head += f"，画面 {self.frame_size[0]}x{self.frame_size[1]}"
            if self.background_size and self.frame_size != self.background_size:
                head += f"（参考背景 {self.background_size[0]}x{self.background_size[1]}，坐标系可能不一致）"
        lines = [head] + [f"    {v.describe()}" for v in self.verdicts]
        if self.note:
            lines.append(f"    {self.note}")
        return "\n".join(lines)


class LabelVerifierError(RuntimeError):
    """参考图配置或图像依赖不可用。"""


# --------------------------------------------------------------------------- 校验器
class LabelVerifier:
    """按参考图配置校验走贴（标贴）。"""

    def __init__(self, config_name: str | None = None, image_dir: str | Path | None = None,
                 map_path: str | Path | None = None, threshold: int | None = None,
                 config_dir: str | Path | None = None) -> None:
        self._map_path = Path(map_path) if map_path else paths.project_root / DEFAULT_MAP
        self._map = self._load_map(self._map_path)
        self._config_name = config_name or self._map.get("config") or "ui_config_SQ.json"
        self._config_dir = Path(config_dir) if config_dir else paths.data_dir / "UI_Config"
        self._image_dir = Path(image_dir) if image_dir else \
            paths.project_root / (self._map.get("image_dir") or "Resources/ImageUI/SQ")
        self._threshold_override = int(threshold) if threshold is not None else None
        self._config: dict | None = None
        self._image_index: dict[str, Path] | None = None

    # ---- 配置 ----
    @staticmethod
    def _load_map(path: Path | None = None) -> dict:
        path = Path(path) if path else paths.project_root / DEFAULT_MAP
        if not path.is_file():
            logging_setup.warning(LOGGER_NAME, f"标贴映射文件不存在：{path}（全部标贴将记为无参考图）")
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging_setup.error(LOGGER_NAME, f"标贴映射解析失败：{path}（{exc}）")
            return {}

    @property
    def config(self) -> dict:
        if self._config is None:
            path = self._config_dir / self._config_name
            if not path.is_file():
                raise LabelVerifierError(f"参考图配置不存在：{path}")
            try:
                self._config = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise LabelVerifierError(f"参考图配置解析失败：{path}（{exc}）") from exc
        return self._config

    def background_size(self) -> tuple[int, int] | None:
        """参考背景尺寸（用于判断画面坐标系是否一致）。"""
        for entry in self.config.values():
            if entry.get("class_name") == "background":
                try:
                    return int(entry["width"]), int(entry["height"])
                except (KeyError, TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _normalize(text: str) -> str:
        """标签归一化：去 `NO_` 前缀、统一大小写、只留字母数字（便于宽松匹配）。"""
        import re
        text = str(text or "").strip()
        if text.upper().startswith("NO_"):
            text = text[3:]
        return re.sub(r"[^0-9a-z]", "", text.lower())

    def _image_index_map(self) -> dict[str, Path]:
        """参考图索引：NFC 归一化文件名 → 路径（macOS 上文件名可能是 NFD）。"""
        if self._image_index is None:
            index: dict[str, Path] = {}
            if self._image_dir.is_dir():
                for p in self._image_dir.rglob("*"):
                    if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
                        index.setdefault(unicodedata.normalize("NFC", p.name), p)
            self._image_index = index
        return self._image_index

    def resolve(self, label: str) -> tuple[RefHit, ...]:
        """解析标贴 → 参考图条目（可能多个，例如"左右盲区都要亮"）。

        匹配顺序：① 映射表精确命中 → ② 映射表归一化命中 → ③ 配置条目 class_name/name 归一化命中。
        """
        text = str(label or "").strip()
        if not text:
            return ()
        aliases: dict = self._map.get("aliases", {})
        keys: Sequence[str] = aliases.get(text) or ()
        if not keys:
            norm = self._normalize(text)
            for name, value in aliases.items():
                if self._normalize(name) == norm:
                    keys = value
                    break
        if not keys:                                   # 回退：用配置里的 class_name / name 猜
            for key, entry in self.config.items():
                for field in ("class_name", "name"):
                    if self._normalize(entry.get(field, "")) == self._normalize(text):
                        keys = [key]
                        break
                if keys:
                    break
        hits: list[RefHit] = []
        for key in keys:
            entry = self.config.get(key)
            if entry is None:
                logging_setup.warning(LOGGER_NAME, f"标贴映射指向了不存在的配置键：{key}")
                continue
            hits.append(RefHit(label=text, key=key, entry=entry,
                               image=self._image_index_map().get(unicodedata.normalize("NFC", key))))
        return tuple(hits)

    def coverage(self, labels: Iterable[str]) -> dict:
        """统计标贴可校验情况（报告用）。"""
        total, covered, missing = 0, [], []
        for label in sorted({str(x).strip() for x in labels if str(x).strip()}):
            total += 1
            (covered if self.resolve(label) else missing).append(label)
        return {"labels": total, "covered": len(covered),
                "uncovered": len(missing), "uncovered_list": missing}

    # ---- 校验 ----
    def verify_frame(self, frame, expected) -> FrameVerdict:
        """校验一帧画面。

        :param frame: 画面（图片路径 / PIL.Image / ndarray）；None 表示没有可用画面
        :param expected: `di_case_parser.ExpectedOutput`
        """
        verdicts: list[LabelVerdict] = []
        if frame is None:
            for label, role in ((expected.primary_label, "primary"),
                                (expected.negative_label, "negative")):
                if label:
                    verdicts.append(LabelVerdict(label, role, "error", "未提供画面"))
            return FrameVerdict(tuple(verdicts), note="没有可用画面（相机/截图未接入）")

        image = self._load_image(frame)
        size = getattr(image, "size", None)
        threshold = self._threshold_override or self._threshold_of(expected)
        note = ""
        bg = self.background_size()
        if bg and size and tuple(size) != bg:
            note = "画面尺寸与参考背景不一致：按参考图坐标裁剪可能偏移"

        if expected.primary_label:
            verdicts.append(self._verify_one(image, expected.primary_label, "primary",
                                             expect_visible=True, threshold=threshold))
        if expected.negative_label:
            verdicts.append(self._verify_one(image, expected.negative_label, "negative",
                                             expect_visible=False, threshold=threshold))
        if not verdicts:
            verdicts.append(LabelVerdict("", "primary", "nothing", "用例未声明标贴"))
        return FrameVerdict(tuple(verdicts), frame_size=tuple(size) if size else None,
                            background_size=bg, note=note)

    @staticmethod
    def _threshold_of(expected) -> int:
        value = float(getattr(expected, "min_confidence", 0.0) or 0.0)
        return int(round(value * 100)) if value > 0 else DEFAULT_THRESHOLD

    @staticmethod
    def _load_image(frame):
        try:
            from PIL import Image
        except ImportError as exc:                     # pragma: no cover - 依赖缺失
            raise LabelVerifierError("未安装 Pillow，无法校验画面") from exc
        if isinstance(frame, (str, Path)):
            return Image.open(frame).convert("RGB")
        if hasattr(frame, "convert") or hasattr(frame, "size"):     # PIL.Image
            return frame
        return Image.fromarray(frame).convert("RGB")   # ndarray

    def _verify_one(self, image, label: str, role: str, *, expect_visible: bool,
                    threshold: int) -> LabelVerdict:
        hits = self.resolve(label)
        if not hits:
            return LabelVerdict(label, role, "no_reference",
                                "仓库内暂无该标贴的参考图（见 data/DI_Config/label_map.json）")
        details, confidences = [], []
        mismatch_images = []
        for hit in hits:
            box = hit.box
            if box is None:
                return LabelVerdict(label, role, "error", f"参考图条目缺少位置/尺寸：{hit.key}")
            if hit.image is None:
                return LabelVerdict(label, role, "no_reference", f"参考图文件缺失：{hit.key}")
            if box[2] > image.size[0] or box[3] > image.size[1]:
                return LabelVerdict(label, role, "error",
                                    f"画面小于参考区域 {box}（{hit.key}），坐标系不匹配")
            confidence, same = self._compare(image.crop(box), hit, threshold)
            confidences.append(confidence)
            details.append(f"{hit.key} 置信度 {confidence:.1f}%")
            if not same:
                mismatch_images.append(hit)

        matched = not mismatch_images
        # 期望显示：全部参考图都要命中；期望不显示：一个都不能命中
        ok = matched if expect_visible else not matched
        best = max(confidences) if confidences else None
        detail = "；".join(details)
        if not expect_visible:
            detail += "（负向：不应命中）"
        return LabelVerdict(label, role, "matched" if ok else "mismatch", detail,
                            confidence=best, threshold=float(threshold))

    @staticmethod
    def _compare(crop, hit: RefHit, threshold: int) -> tuple[float, bool]:
        """返回 (置信度百分比, 是否一致)。优先用配置里的预计算哈希，否则现算参考图哈希。"""
        from image_testing.image_similarity import compute_dhash, get_image_hash, to_grayscale
        current = compute_dhash(to_grayscale(crop))
        reference = hit.precomputed_hash
        if reference is None and hit.image is not None:
            reference = get_image_hash(str(hit.image))
        if reference is None:
            return 0.0, False
        if current == 0:                     # 纯色区域：项目约定视为"无 UI"
            return 0.0, False
        confidence = 100.0 * (64 - (current ^ int(reference)).bit_count()) / 64
        return confidence, confidence >= threshold


__all__ = ["LabelVerifier", "LabelVerdict", "FrameVerdict", "RefHit",
           "LabelVerifierError", "DEFAULT_MAP", "DEFAULT_THRESHOLD"]
