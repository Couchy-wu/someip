# -*- coding: utf-8 -*-
"""someip_core.models —— SOME/IP 服务/事件定义与数据类型表

数据来源：原 someip 工程 `hud/hud_data_types.py` 的 HUD_EVENTS 表（11 服务 / 23 事件），
与 C++ 库 `arhud_server_sp.cpp` 内置注册表一致。

表结构：(service, instance, event, name, event_group, port, kind)
    kind 为"数据类型"，决定能否用结构化赋值发送（见 api.STRUCT_TYPES）；
    未知/未收录的类型标记为 "Opaque"（只能按原始字节回放或发送）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# 类型名 → (service, event)：与 C++ 库内置的 KIND 映射一致，供"结构化发送"使用
KIND_SERVICE_EVENT: dict[str, tuple[int, int]] = {
    "VehiclePosition": (0x000A, 0x8001),
    "RTK": (0x000B, 0x8001),
    "IMU": (0x000B, 0x8002),
    "ChangeLane": (0x000D, 0x8001),
    "PilotStatus": (0x000D, 0x8002),
    "PilotAlarm": (0x000D, 0x8003),
    "Broadcast": (0x000D, 0x8004),
    "HudMappath": (0x010A, 0x8002),
    "HudNavmap": (0x010A, 0x8003),
}

# 可结构化赋值发送的类型（其余为 Opaque：仅原始字节）
STRUCT_TYPES: tuple[str, ...] = tuple(KIND_SERVICE_EVENT)

# (service, instance, event, name, event_group, port, kind)
HUD_EVENTS: list[tuple[int, int, int, str, int, int, str]] = [
    (0x000A, 0x000A, 0x8001, "VehiclePositionInfoNotify",        0x1101, 51400, "VehiclePosition"),
    (0x000B, 0x000B, 0x8001, "RTKInfoNotify",                    0x1101, 51401, "RTK"),
    (0x000B, 0x000B, 0x8002, "IMUInfoNotify",                    0x1101, 51401, "IMU"),
    (0x000C, 0x000C, 0x8001, "ObstacleInfoNotify",               0x1101, 51402, "Opaque"),
    (0x000C, 0x000C, 0x8002, "LaneLineDataNotify",               0x1101, 51402, "Opaque"),
    (0x000C, 0x000C, 0x8003, "NewLanelineDataNotify",            0x1101, 51402, "Opaque"),
    (0x000D, 0x000D, 0x8001, "ChangeLaneDataNotify",             0x1101, 51403, "ChangeLane"),
    (0x000D, 0x000D, 0x8002, "PilotStatusNotify",                0x1101, 51403, "PilotStatus"),
    (0x000D, 0x000D, 0x8003, "PilotAlarmAndNoticeInfoNotify",    0x1101, 51403, "PilotAlarm"),
    (0x000D, 0x000D, 0x8004, "BroadcastInfoNotify",              0x1101, 51403, "Broadcast"),
    (0x000D, 0x000D, 0x8005, "NewBroadcastInfoNotify",           0x1101, 51403, "Opaque"),
    (0x000E, 0x000E, 0x8001, "PlanningLineInfoNotify",           0x1101, 51404, "Opaque"),
    (0x000E, 0x000E, 0x8002, "newPlanningLineInfo",              0x1102, 51404, "Opaque"),
    (0x000E, 0x000E, 0x8003, "drivingAreaIdentification",        0x1103, 51404, "Opaque"),
    (0x0007, 0x0007, 0x8001, "NavigationStatus_LinkInfoNotify",  0x1101, 51405, "Opaque"),
    (0x0017, 0x0017, 0x8003, "NewParkingRealTimeDataNotify",     0x1101, 51406, "Opaque"),
    (0x0018, 0x0018, 0x8001, "hpaMapDataNotify",                 0x1101, 51409, "Opaque"),
    (0x002B, 0x002B, 0x8001, "NavigationHDLink2Info",            0x1101, 51407, "Opaque"),
    (0x010A, 0x0001, 0x8001, "HudRoadInfoNotify",                0x1101, 52001, "Opaque"),
    (0x010A, 0x0001, 0x8002, "HudMappathInfo_EG",                0x1101, 52001, "HudMappath"),
    (0x010A, 0x0001, 0x8003, "HudNavigationmap",                 0x1101, 52001, "HudNavmap"),
    (0x010A, 0x0001, 0x8004, "OverseasHudRoadInfoNotify",        0x1101, 52001, "Opaque"),
    (0x8202, 0x8202, 0x8002, "sdTraffiIncident",                 0x1101, 51408, "Opaque"),
]

# 需要 SOME/IP-TP 分段的事件（大帧）：与 C++ 库/原 Python 服务端配置一致
TP_EVENTS: frozenset[tuple[int, int]] = frozenset({
    (0x000C, 0x8002), (0x000C, 0x8003),      # 车道线（约 51KB）
    (0x010A, 0x8001), (0x010A, 0x8003),      # HUD 道路 / 导航地图
})

# 事件组 → 事件列表（供界面分组展示；同一事件可能属于多个组）
# 注意：原 Python 服务端为兼容"固定配置客户端"额外在 eventgroup 0x0000 下 offer 0x000E，
#       这里仅作为参考信息展示，实际注册由 C++ 库内部处理。
FIXED_CFG_EXTRA_GROUPS: dict[int, tuple[int, ...]] = {0x0000: (0x000E,)}


@dataclass(frozen=True)
class EventDef:
    """单个事件的定义。"""

    service: int
    instance: int
    event: int
    name: str
    group: int
    port: int
    kind: str

    @property
    def need_tp(self) -> bool:
        """是否需要 SOME/IP-TP 分段（大帧）。"""
        return (self.service, self.event) in TP_EVENTS

    @property
    def struct_sendable(self) -> bool:
        """是否支持结构化赋值发送（否则只能发原始字节）。"""
        return self.kind in KIND_SERVICE_EVENT

    @property
    def key(self) -> str:
        return f"0x{self.service:04X}/0x{self.event:04X}"

    def describe(self) -> str:
        tp = " · TP" if self.need_tp else ""
        return (f"0x{self.service:04X}:{self.event:04X} {self.name} "
                f"[{self.kind}{tp}] port={self.port} group=0x{self.group:04X}")


@dataclass
class ServiceDef:
    """单个服务的定义（聚合其事件）。"""

    service: int
    instance: int
    port: int
    events: list[EventDef] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"0x{self.service:04X}"

    def describe(self) -> str:
        return f"0x{self.service:04X} (instance=0x{self.instance:04X}, port={self.port}, {len(self.events)} 事件)"


def all_events() -> list[EventDef]:
    """全部事件定义（按服务、事件号排序）。"""
    return [EventDef(*row) for row in sorted(HUD_EVENTS, key=lambda r: (r[0], r[2]))]


def services(only: Iterable[str] | None = None) -> list[ServiceDef]:
    """按服务聚合的事件定义；`only` 可传类型名筛选（如 {"RTK", "IMU"}）。"""
    keep = set(only) if only else None
    out: dict[int, ServiceDef] = {}
    for ev in all_events():
        if keep is not None and ev.kind not in keep:
            continue
        svc = out.setdefault(ev.service, ServiceDef(ev.service, ev.instance, ev.port))
        svc.events.append(ev)
    return [out[k] for k in sorted(out)]


def find_event(service: int, event: int) -> EventDef | None:
    """按 (service, event) 查找定义。"""
    for ev in all_events():
        if ev.service == service and ev.event == event:
            return ev
    return None


def summarize() -> str:
    """一行摘要（界面/日志用）。"""
    svcs = services()
    return (f"{len(svcs)} 个服务 / {len(all_events())} 个事件"
            f"（可结构化发送 {len(STRUCT_TYPES)} 类，需 TP 分段 {len(TP_EVENTS)} 个事件）")
