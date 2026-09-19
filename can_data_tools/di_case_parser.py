# -*- coding: utf-8 -*-
"""can_data_tools.di_case_parser —— Di 测试用例（JSON）解析

用例来源：`TestcaseCollection/Di_testcases/TC-*.json`（497 个，随仓库分发）。
与**旧格式**（`gui_handlers/can_testcase_parser.py` 处理的中文键 JSON）是两套独立格式，
旧解析链路保持原样不动；选择由 `can_data_tools.case_format` 的开关决定。

单个用例的格式（已按 497 个样例逐一核对，见 docs/DI_TESTCASES.md）：

    {
      "scenario_id": "TC-ACC-ACTIVE-HIGHSPEED",
      "description": "……",
      "input_combination": {
        "can":    [{"signal_id": "0x4C1", "sub_id": "", "bit_range": "6.0-6.1",
                    "value": 1, "desc": "……"}],              # 报文级信号（可按位下发）
        "someip": [{"key": "hnmap_s.navigation_map", "value": 1},        # ① 字段型
                   {"service_id": "0x010A", "instance_id": "0x01",       # ② 链路型
                    "online": 1, "desc": "……"}],
        "mem":    [{"field": "dataValue.arEnginData...", "value": 2, "desc": "……"}]
      },
      "expected_output": {"primary_label": "ACC", "negative_label": "",
                          "location_constraint": "540,259", "min_confidence": 0.9},
      "wait_ms": 100
    }

实测分布（497 个用例）：
  · can 条目 0~11 条（bit_range 有 1355 条、缺失 416 条 —— 缺失者代表"整帧在线"类信号）
  · someip 条目 0~3 条，其中"字段型"6 种键、"链路型"只涉及 0x010A / 0x000C 两个服务
  · mem 条目出现在约一半用例（HUD 内部状态量，**无法从外部注入**）
  · expected_output.primary_label 可为空（185 个"应不显示"的负向用例）
  · location_constraint 三种形态：`x,y`（点）、`x1,y1,x2,y2`（线段）、空（不约束位置）

本模块只做**解析与分类**（纯函数、无 IO 副作用、不依赖界面），执行见
`can_data_tools.di_case_runner`。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from hudcore import logging_setup

LOGGER_NAME = "di_case"

# 默认用例目录（项目内，随仓库分发）
DEFAULT_CASE_DIR = Path("TestcaseCollection") / "Di_testcases"

_BIT_RANGE_RE = re.compile(r"^\s*\d+\.\d+\s*(-\s*\d+\.\d+\s*)?$")
_HEX_RE = re.compile(r"^0[xX][0-9A-Fa-f]+$")
_LOCATION_RE = re.compile(r"^\s*-?\d+\s*,\s*-?\d+\s*$")


class DiCaseParseError(ValueError):
    """用例文件结构不可解析（缺关键字段等）。"""


# --------------------------------------------------------------------------- 数据结构
@dataclass(frozen=True)
class CanSignal:
    """一条 CAN 输入（报文 + 位域 + 值）。"""

    signal_id: str
    value: int
    bit_range: str | None = None
    sub_id: str = ""
    desc: str = ""

    @property
    def can_id(self) -> int:
        """CAN ID（支持 "0x4C1" 与 "1217" 两种写法）。"""
        text = str(self.signal_id).strip()
        try:
            return int(text, 16) if text.lower().startswith("0x") else int(text)
        except ValueError as exc:
            raise DiCaseParseError(f"无法解析 signal_id={self.signal_id!r}") from exc

    @property
    def is_extended(self) -> bool:
        return self.can_id > 0x7FF

    @property
    def data_length(self) -> int:
        """该信号需要的数据字节数（无位域信息时按整帧 8 字节处理）。

        Di 用例的字节号是 **0 起**（见 can_bit_writer 模块说明），因此长度为"最大下标 + 1"，
        最大 64（CANFD）。例如 `"46.0-46.7"` → 47 字节。
        """
        if not self.bit_range:
            return 8
        highest = max(int(part.split(".")[0]) for part in self.bit_range.split("-"))
        return max(1, min(64, highest + 1))

    def describe(self) -> str:
        bits = self.bit_range or "整帧"
        return (f"CAN {self.signal_id} 位[{bits}] = {self.value}"
                f"{' (扩展帧)' if self.is_extended else ''}")


@dataclass(frozen=True)
class SomeipField:
    """SOME/IP「字段型」输入：`key` 形如 `hnmap_s.navigation_map`。"""

    key: str
    value: Any
    desc: str = ""

    @property
    def prefix(self) -> str:
        return self.key.split(".", 1)[0] if "." in self.key else ""

    @property
    def field_name(self) -> str:
        return self.key.split(".", 1)[1] if "." in self.key else self.key


@dataclass(frozen=True)
class SomeipLink:
    """SOME/IP「链路型」输入：某服务在线/离线。"""

    service_id: str
    instance_id: str
    online: int
    desc: str = ""

    def describe(self) -> str:
        state = "在线" if self.online else "离线"
        return f"SOME/IP {self.service_id}:{self.instance_id} {state}"


@dataclass(frozen=True)
class MemField:
    """HUD 内部状态量（`mem`）：外部无法直接注入，按"需要台架/桩"处理。"""

    field: str
    value: Any
    desc: str = ""


@dataclass(frozen=True)
class ExpectedOutput:
    """期望的界面输出（标贴/标签 + 位置 + 置信度）。"""

    primary_label: str = ""
    negative_label: str = ""
    location_constraint: str = ""
    min_confidence: float = 0.0

    @property
    def expect_visible(self) -> bool:
        return bool(self.primary_label)

    @property
    def points(self) -> tuple[tuple[int, int], ...]:
        """把位置约束解析成坐标点序列（空串 → 空元组，表示不约束位置）。"""
        text = (self.location_constraint or "").strip()
        if not text:
            return ()
        parts = [p.strip() for p in text.split(",")]
        if len(parts) % 2 != 0:
            return ()
        try:
            nums = [int(p) for p in parts]
        except ValueError:
            return ()
        return tuple((nums[i], nums[i + 1]) for i in range(0, len(nums), 2))

    @property
    def location_kind(self) -> str:
        n = len(self.points)
        return ("none", "point", "segment", "polyline")[min(n, 3)] if n <= 3 else "polyline"


@dataclass(frozen=True)
class DiCase:
    """一个 Di 测试用例。"""

    scenario_id: str
    description: str
    can: tuple[CanSignal, ...] = ()
    someip_fields: tuple[SomeipField, ...] = ()
    someip_links: tuple[SomeipLink, ...] = ()
    mem: tuple[MemField, ...] = ()
    expected: ExpectedOutput = field(default_factory=ExpectedOutput)
    wait_ms: int = 100
    path: Path | None = None
    extra: dict = field(default_factory=dict)          # 未识别的字段（向前兼容）

    # ---- 便捷视图 ----
    @property
    def can_ids(self) -> tuple[int, ...]:
        return tuple(sorted({s.can_id for s in self.can}))

    @property
    def encodable_ids(self) -> tuple[int, ...]:
        """能够编码下发的报文 ID（至少有一个信号给了位域）。"""
        return tuple(sorted({s.can_id for s in self.can if s.bit_range}))

    def input_lines(self) -> list[str]:
        lines = [s.describe() for s in self.can]
        lines += [f"SOME/IP 字段 {f.key} = {f.value}" for f in self.someip_fields]
        lines += [l.describe() for l in self.someip_links]
        lines += [f"MEM {m.field} = {m.value}" for m in self.mem]
        return lines


@dataclass(frozen=True)
class Support:
    """该用例能否被自动化程序直接执行（用于挑选可跑用例）。

    · auto     —— 输入全部可下发（CAN 信号 / SOME/IP 链路 / 可结构化发送的 SOME/IP 字段）
    · partial  —— 有可下发输入，但还含必须由台架/桩注入的部分（mem 字段、Opaque 载荷）
    · external —— 完全没有可下发输入（只能靠台架注入）
    """

    level: str
    reasons: tuple[str, ...] = ()

    def describe(self) -> str:
        text = {"auto": "可自动执行", "partial": "部分可执行", "external": "需台架注入"}[self.level]
        return text + (f"（{'；'.join(self.reasons)}）" if self.reasons else "")


# --------------------------------------------------------------------------- 解析
def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip(), 0)
    except (TypeError, ValueError):
        return default


def _clean_bit_range(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if text and _BIT_RANGE_RE.match(text) else None


def _parse_can_entry(raw: dict) -> CanSignal:
    sub_id = str(raw.get("sub_id", "") or "").strip()
    bit_range = _clean_bit_range(raw.get("bit_range"))
    # 样例中存在把位域写进 sub_id 的个例（1/497）：此时以 sub_id 作为位域，避免丢信息
    if bit_range is None and _BIT_RANGE_RE.match(sub_id):
        bit_range, sub_id = sub_id, ""
    return CanSignal(signal_id=str(raw.get("signal_id", "")).strip(),
                     value=_as_int(raw.get("value")),
                     bit_range=bit_range,
                     sub_id=sub_id,
                     desc=str(raw.get("desc", "") or ""))


def _parse_someip_entry(raw: dict) -> SomeipField | SomeipLink:
    service_id = str(raw.get("service_id", "") or "").strip()
    if service_id or "online" in raw:
        return SomeipLink(service_id=service_id,
                          instance_id=str(raw.get("instance_id", "") or "").strip(),
                          online=_as_int(raw.get("online"), 0),
                          desc=str(raw.get("desc", "") or ""))
    return SomeipField(key=str(raw.get("key", "") or "").strip(),
                       value=raw.get("value"),
                       desc=str(raw.get("desc", "") or ""))


def _parse_expected(raw: dict) -> ExpectedOutput:
    location = str(raw.get("location_constraint", "") or "").strip()
    if location and not _LOCATION_RE.match(location) and len(location.split(",")) % 2:
        logging_setup.warning(LOGGER_NAME, f"位置约束格式异常，按「不约束」处理：{location!r}")
        location = ""
    try:
        confidence = float(raw.get("min_confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return ExpectedOutput(primary_label=str(raw.get("primary_label", "") or "").strip(),
                          negative_label=str(raw.get("negative_label", "") or "").strip(),
                          location_constraint=location,
                          min_confidence=confidence)


def parse_case_obj(data: dict, path: Path | None = None) -> DiCase:
    """把已读出的 JSON dict 解析成 `DiCase`（缺字段时按默认值容错）。"""
    if not isinstance(data, dict):
        raise DiCaseParseError("用例根节点必须是对象")
    scenario_id = str(data.get("scenario_id", "") or "").strip()
    if not scenario_id:
        raise DiCaseParseError(f"缺少 scenario_id（{path}）")

    # 注意不能写 `data.get(...) or {}`：空列表/空串会被 falsy 回退成 {}，校验就失效了
    combo = data.get("input_combination")
    if combo is None:
        combo = {}
    elif not isinstance(combo, dict):
        raise DiCaseParseError(f"input_combination 必须是对象，实际 {type(combo).__name__}（{path}）")

    fields_: list[SomeipField] = []
    links: list[SomeipLink] = []
    for raw in combo.get("someip") or []:
        entry = _parse_someip_entry(raw if isinstance(raw, dict) else {})
        (links if isinstance(entry, SomeipLink) else fields_).append(entry)

    known = {"scenario_id", "description", "input_combination", "expected_output", "wait_ms"}
    return DiCase(
        scenario_id=scenario_id,
        description=str(data.get("description", "") or "").strip(),
        can=tuple(_parse_can_entry(r) for r in (combo.get("can") or []) if isinstance(r, dict)),
        someip_fields=tuple(fields_),
        someip_links=tuple(links),
        mem=tuple(MemField(field=str(r.get("field", "") or "").strip(),
                           value=r.get("value"),
                           desc=str(r.get("desc", "") or ""))
                  for r in (combo.get("mem") or []) if isinstance(r, dict)),
        expected=_parse_expected(data.get("expected_output") or {}),
        wait_ms=_as_int(data.get("wait_ms"), 100),
        path=path,
        extra={k: v for k, v in data.items() if k not in known},
    )


def load_case(path: Path | str) -> DiCase:
    """读取并解析单个用例文件。"""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DiCaseParseError(f"JSON 解析失败：{p}（{exc}）") from exc
    return parse_case_obj(data, p)


def load_cases(target: Path | str | Iterable[Path | str]) -> list[DiCase]:
    """加载用例：可以是目录、单个文件或文件列表。返回按 scenario_id 排序的列表。"""
    if isinstance(target, (str, Path)) and Path(target).is_dir():
        paths = sorted(Path(target).glob("*.json"))
    elif isinstance(target, (str, Path)):
        paths = [Path(target)]
    else:
        paths = [Path(p) for p in target]

    cases: list[DiCase] = []
    for p in paths:
        try:
            cases.append(load_case(p))
        except DiCaseParseError as exc:
            logging_setup.error(LOGGER_NAME, str(exc))
    return sorted(cases, key=lambda c: c.scenario_id)


# --------------------------------------------------------------------------- 分类
def gate_only_ids(case: DiCase) -> tuple[int, ...]:
    """只写了"门控有效"却没有位域的报文 ID（无法据此编码，除非补 gate_frame.json）。"""
    ranged = {s.can_id for s in case.can if s.bit_range}
    return tuple(sorted({s.can_id for s in case.can if not s.bit_range} - ranged))


def classify(case: DiCase, someip_field_support: dict[str, bool] | None = None,
             gate_ids: Iterable[int] | None = None) -> Support:
    """判断用例能否被自动化程序执行（见 `Support`）。

    :param someip_field_support: `{key: 是否可由本项目回放库结构化发送}`；
                                 缺省时按 `someip_field_map` 的解析表推断
    :param gate_ids: 已由 gate_frame.json 补齐默认位的报文 ID（这些报文可编码）
    """
    reasons: list[str] = []
    gate_ids = set(gate_ids or ())
    drivable = bool(case.can or case.someip_links)

    unencodable = [i for i in gate_only_ids(case) if i not in gate_ids]
    if unencodable:
        reasons.append("报文仅有门控说明、无位域：" +
                       ", ".join(f"0x{i:X}" for i in unencodable))
    if case.mem:
        reasons.append(f"{len(case.mem)} 个 mem 内部状态量需台架注入")
    if case.someip_fields:
        support = someip_field_support if someip_field_support is not None else default_field_support()
        unsupported = [f.key for f in case.someip_fields if not support.get(f.key, False)]
        if unsupported:
            reasons.append(f"SOME/IP 字段无法结构化下发：{', '.join(sorted(set(unsupported)))}")
        else:
            drivable = True

    if not drivable:
        return Support("external", tuple(reasons) or ("没有任何可下发输入",))
    return Support("partial" if reasons else "auto", tuple(reasons))


def default_field_support() -> dict[str, bool]:
    """默认的 SOME/IP「字段型」键支持表（惰性依赖 someip_core，缺库时全部视为不支持）。"""
    from .someip_field_map import field_support_map
    return field_support_map()


# --------------------------------------------------------------------------- 汇总
def summarize(cases: Sequence[DiCase]) -> dict:
    """统计用例集特征（自检/报告用）。"""
    levels: dict[str, int] = {}
    labels: dict[str, int] = {}
    someip_keys: dict[str, int] = {}
    links: dict[str, int] = {}
    anomalies: dict[str, int] = {}
    for case in cases:
        support = classify(case)
        levels[support.level] = levels.get(support.level, 0) + 1
        label = case.expected.primary_label or "(negative-only)"
        labels[label] = labels.get(label, 0) + 1
        for f in case.someip_fields:
            someip_keys[f.key] = someip_keys.get(f.key, 0) + 1
        for l in case.someip_links:
            key = f"{l.service_id}:{l.instance_id}={'on' if l.online else 'off'}"
            links[key] = links.get(key, 0) + 1
        for sig in case.can:
            if sig.bit_range is None:
                anomalies["CAN 条目缺少 bit_range"] = anomalies.get("CAN 条目缺少 bit_range", 0) + 1
    return {
        "cases": len(cases),
        "support": levels,
        "can_entries": sum(len(c.can) for c in cases),
        "someip_field_entries": sum(len(c.someip_fields) for c in cases),
        "someip_link_entries": sum(len(c.someip_links) for c in cases),
        "mem_entries": sum(len(c.mem) for c in cases),
        "expect_visible": sum(1 for c in cases if c.expected.expect_visible),
        "expect_hidden": sum(1 for c in cases if not c.expected.expect_visible),
        "labels": dict(sorted(labels.items(), key=lambda kv: -kv[1])),
        "someip_keys": dict(sorted(someip_keys.items(), key=lambda kv: -kv[1])),
        "someip_links": dict(sorted(links.items(), key=lambda kv: -kv[1])),
        "anomalies": anomalies,
    }


__all__ = [
    "CanSignal", "SomeipField", "SomeipLink", "MemField", "ExpectedOutput",
    "DiCase", "Support", "DiCaseParseError",
    "parse_case_obj", "load_case", "load_cases", "classify", "gate_only_ids",
    "default_field_support",
    "summarize", "DEFAULT_CASE_DIR",
]
