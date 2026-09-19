# -*- coding: utf-8 -*-
"""can_data_tools.someip_field_map —— Di 用例 SOME/IP「字段型」键 → 回放库结构体映射

Di 用例里的 SOME/IP 输入有两种写法，本模块负责**第二种**（字段型）：

    {"key": "hnmap_s.navigation_map", "value": 1}     → 服务 0x010A 事件 0x8003（kind=HudNavmap）
    {"key": "hrinfo_s.next_road_name", "value": "…"}  → 服务 0x010A 事件 0x8001（kind=Opaque）
    {"key": "PlanningLinePointCount", "value": 12}    → 未提供结构体，无法下发

映射依据（不臆造，全部来自随仓库分发的库与配置）：

| 用例前缀        | 目标服务:事件                 | 数据类型       | 能否结构化下发 |
|-----------------|-------------------------------|----------------|----------------|
| `hnmap_s.*`     | `0x010A`:`0x8003` HudNavigationmap | `HudNavmap` | ✅（字段名大小写不敏感匹配，如 `navigation_map` → `Navigation_map`） |
| `hrinfo_s.*`    | `0x010A`:`0x8001` HudRoadInfoNotify | `Opaque`   | ❌（Opaque 原始载荷，库未提供结构体布局） |
| 其它（无前缀）  | 全结构体字段名搜索             | 视命中而定     | 命中则可下发，否则 ❌ |

服务表来自 `someip_core.models`（11 服务 / 23 事件），结构体字段来自 `someip_core.api` 的 ctypes 定义，
因此库一旦更新（新增结构体/字段），这里会自动跟着变。
"""
from __future__ import annotations

from dataclasses import dataclass

from hudcore import logging_setup

LOGGER_NAME = "di_case"

# 前缀 → (服务, 实例, 事件, 说明)；仅收录样例中真实出现、且与库服务表对得上的前缀
PREFIX_TARGETS: dict[str, tuple[str, str, str, str]] = {
    "hnmap_s": ("0x010A", "0x0001", "0x8003", "HudNavigationmap（kind=HudNavmap，需 TP）"),
    "hrinfo_s": ("0x010A", "0x0001", "0x8001", "HudRoadInfoNotify（kind=Opaque，需 TP）"),
}


@dataclass(frozen=True)
class FieldTarget:
    """一个「字段型」键的解析结果。"""

    key: str
    kind: str | None = None            # 可结构化发送的数据类型名（None=不可下发）
    field: str | None = None           # 结构体字段名（保留库里的原始大小写）
    service: str = ""
    instance: str = ""
    event: str = ""
    reason: str = ""                   # 不可下发时的原因（给报告用）

    @property
    def supported(self) -> bool:
        return self.kind is not None and self.field is not None

    def describe(self) -> str:
        if self.supported:
            return (f"{self.key} → {self.kind}.{self.field}"
                    f"（服务 {self.service}:{self.event}）")
        return f"{self.key} → 无法下发：{self.reason}"


def _struct_field_map() -> dict[str, list[tuple[str, str]]]:
    """{字段名小写: [(kind, 原始字段名), ...]}，来自库的 ctypes 结构体定义。"""
    table: dict[str, list[tuple[str, str]]] = {}
    try:
        from someip_core import api, models
    except Exception as exc:                      # noqa: BLE001 - 缺库时退化为"不支持"
        logging_setup.warning(LOGGER_NAME, f"读取 SOME/IP 结构体失败（按不支持处理）：{exc}")
        return table
    for kind in getattr(models, "STRUCT_TYPES", ()):        # 可结构化发送的数据类型
        cls = getattr(api, kind, None)
        for name, *_ in getattr(cls, "_fields_", ()):
            table.setdefault(str(name).lower(), []).append((kind, str(name)))
    return table


def _event_of(service: str, event: str) -> tuple[str, str]:
    """返回 (服务原始写法, 事件原始写法)；找不到时返回空串。"""
    try:
        from someip_core import models
    except Exception:                             # noqa: BLE001
        return "", ""
    want_svc, want_ev = int(service, 16), int(event, 16)
    for svc in models.services():
        if svc.service == want_svc:
            for ev in svc.events:
                if ev.event == want_ev:
                    return f"{svc.service:#06x}", f"{ev.event:#06x}"
            return f"{svc.service:#06x}", ""
    return "", ""


def resolve(key: str, *, check_library: bool = True) -> FieldTarget:
    """解析一个「字段型」键。

    :param check_library: True 时确认目标服务/事件确实在本项目回放库的服务表里
    """
    text = str(key or "").strip()
    if not text:
        return FieldTarget(key=text, reason="键为空")

    prefix, sep, field_name = text.partition(".")
    if not sep:                                   # 无前缀：整体当作字段名
        prefix, field_name = "", text

    service = instance = event = ""
    kind: str | None = None
    real_field: str | None = None
    label: str | None = None

    # 1) 已知前缀 → 直接定位服务/事件（并给后续报错一个可读的目标名）
    if prefix in PREFIX_TARGETS:
        service, instance, event, label = PREFIX_TARGETS[prefix]

    # 2) 用字段名在库的可发送结构体里查找（大小写不敏感，如 navigation_map → Navigation_map）
    candidates = _struct_field_map().get(field_name.lower(), [])
    if candidates:
        kind, real_field = candidates[0]
    elif label:
        reason = (f"前缀 {prefix} 指向 {label}，但库中没有含字段 {field_name!r} 的可发送结构体"
                  f"（Opaque 原始载荷需自行拼字节）")
        return FieldTarget(key=text, service=service, instance=instance, event=event, reason=reason)
    else:
        reason = f"字段 {field_name!r} 不在库的可发送结构体中"
        if prefix:
            reason = f"未知前缀 {prefix!r}，" + reason
        return FieldTarget(key=text, reason=reason)

    # 3) 校验该类型对应的服务/事件确实在库里
    svc_hex, ev_hex = _kind_service_event(kind)
    if check_library and not svc_hex:
        return FieldTarget(key=text, reason=f"{kind} 对应的服务/事件不在库的服务表中")
    service = service or svc_hex
    event = event or ev_hex
    return FieldTarget(key=text, kind=kind, field=real_field,
                       service=service, instance=instance, event=event)


def _kind_service_event(kind: str) -> tuple[str, str]:
    """kind → (服务, 事件)，取自库的类型映射表。"""
    try:
        from someip_core import KIND_SERVICE_EVENT
    except Exception:                             # noqa: BLE001
        return "", ""
    pair = KIND_SERVICE_EVENT.get(kind)
    if not pair:
        return "", ""
    return f"{pair[0]:#06x}", f"{pair[1]:#06x}"


def field_support_map(keys: list[str] | None = None) -> dict[str, bool]:
    """{键: 是否可由本项目回放库结构化下发}（给 `di_case_parser.classify` 用）。

    :param keys: 需要判断的键；None/空 → 用样例中出现过的全部键
    """
    return {k: resolve(k).supported for k in (keys or list(_KNOWN_KEYS))}


# 样例中出现过的「字段型」键（497 个用例实测去重；库更新后可再生成）
_KNOWN_KEYS: tuple[str, ...] = (
    "hnmap_s.navigation_map",
    "hrinfo_s.next_road_name",
    "hrinfo_s.navigating_status",
    "hrinfo_s.distance_2_intersection",
    "hrinfo_s.eta_info_remain_time",
    "PlanningLinePointCount",
)


__all__ = ["FieldTarget", "resolve", "field_support_map", "PREFIX_TARGETS"]
