# -*- coding: utf-8 -*-
"""someip_core.models —— SOME/IP 服务/事件定义与数据类型表（支持两代服务表）

两代服务表并存，用开关选择（`HUD_SOMEIP_TABLE` / `set_table()`）：

| 代号 | 服务/事件 | 来源 | 回放服务端是否可注册 |
|------|-----------|------|----------------------|
| `old`（默认） | 11 服务 / 23 事件 | 参考实现 `old/someip_arhud01_pcap_server.json`（与 C++ 库 `arhud_server_sp.cpp` 内置注册表一致） | ✅ 可以（已实测） |
| `bplus` | 6 服务 / 38 事件 | 参考实现 `BPlus/someip_arhud01_pcap_server_B+.json`（新一代接口：0x001A/0x001B/0x001C/0x001D/0x8000/0x010A） | ❌ 暂不可（参考实现亦标注"B+ 还不能用"，本项目库只注册 old 代） |

表结构：(service, instance, event, name, event_group, port, kind)
    kind 为"数据类型"，决定能否用结构化赋值发送（见 api.STRUCT_TYPES）；
    未知/未收录的类型标记为 "Opaque"（只能按原始字节回放或发送）。
    B+ 代当前全部为 "Opaque"（HUD 侧未提供结构体定义），因此**不能结构化下发**，
    但服务/事件号与端口是准确的，可用于用例解析、pcap 归属判断与后续扩展。
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

# --------------------------------------------------------------------------- 服务表"代"
TABLE_OLD = "old"          # 当前回放服务端（C++ 库）实际注册的服务表
TABLE_BPLUS = "bplus"      # 新一代接口服务表（参考实现 B+ 配置；服务端暂不支持注册）
ENV_TABLE = "HUD_SOMEIP_TABLE"

# B+ 代：(service, instance, event, name, event_group, port, kind)
# 由参考配置 BPlus/someip_arhud01_pcap_server_B+.json 生成（tools 侧脚本生成，逐条可追溯）
HUD_EVENTS_BPLUS: list[tuple[int, int, int, str, int, int, str]] = [
    (0x001A, 0x001A, 0x8001, "vehiclePositionInfoNotify", 0x1101, 51211, "Opaque"),
    (0x001A, 0x001A, 0x8002, "rtkNotify", 0x1102, 51211, "Opaque"),
    (0x001A, 0x001A, 0x8003, "imuNotify", 0x1103, 51211, "Opaque"),
    (0x001B, 0x001B, 0x8001, "obstacleNotify", 0x1101, 51240, "Opaque"),
    (0x001B, 0x001B, 0x8002, "laneLineDataNotify", 0x1101, 51240, "Opaque"),
    (0x001B, 0x001B, 0x8003, "changeLaneDataNotify", 0x1101, 51240, "Opaque"),
    (0x001B, 0x001B, 0x8004, "pilotStatusNotify", 0x1102, 51240, "Opaque"),
    (0x001B, 0x001B, 0x8005, "pilotAlarmAndNoticeNotify", 0x1102, 51240, "Opaque"),
    (0x001B, 0x001B, 0x8006, "broadcastNotify", 0x1102, 51240, "Opaque"),
    (0x001B, 0x001B, 0x8007, "planningLineNotify", 0x1101, 51240, "Opaque"),
    (0x001B, 0x001B, 0x8008, "drivingAreaIdentification_notify", 0x1101, 51240, "Opaque"),
    (0x001B, 0x001B, 0x8009, "parkingDataNotify", 0x1103, 51240, "Opaque"),
    (0x001B, 0x001B, 0x800A, "hpaMapDataNotify", 0x1103, 51240, "Opaque"),
    (0x001B, 0x001B, 0x800B, "commonObstaclesInMapDataNotify", 0x1103, 51240, "Opaque"),
    (0x001B, 0x001B, 0x800C, "notifyMediaHPAPath", 0x1104, 51240, "Opaque"),
    (0x001B, 0x001B, 0x800D, "drivingJourneyDataNotify", 0x1105, 51240, "Opaque"),
    (0x001C, 0x001C, 0x8001, "navigationPathMatchStatusNotify", 0x1101, 51237, "Opaque"),
    (0x001C, 0x001C, 0x8002, "naviPathUserSelectStsConfirmNotify", 0x1102, 51237, "Opaque"),
    (0x001C, 0x001C, 0x8003, "navigationPathMatchP2PStatusNotify", 0x1104, 51237, "Opaque"),
    (0x001D, 0x001D, 0x8001, "sWSaleablecheckStatusNotify", 0x1101, 51246, "Opaque"),
    (0x010A, 0x0001, 0x8001, "HudRoadInfoNotify", 0x1101, 52001, "Opaque"),
    (0x010A, 0x0001, 0x8002, "HudMappathInfoNotify", 0x1101, 52001, "Opaque"),
    (0x010A, 0x0001, 0x8003, "HudNavigationmap", 0x1101, 52001, "Opaque"),
    (0x010A, 0x0001, 0x8004, "OverseasHudRoadInfoNotify", 0x1101, 52001, "Opaque"),
    (0x8000, 0x8000, 0x8001, "naviGlobalInfoNotify", 0x1101, 51534, "Opaque"),
    (0x8000, 0x8000, 0x8002, "naviPositionInfoNotify", 0x1102, 51534, "Opaque"),
    (0x8000, 0x8000, 0x8003, "naviRouteInfoNotify", 0x1103, 51534, "Opaque"),
    (0x8000, 0x8000, 0x8004, "naviPathInfoNotify", 0x1103, 51534, "Opaque"),
    (0x8000, 0x8000, 0x8005, "aheadIntersectionsLanesInfoNotify", 0x1104, 51534, "Opaque"),
    (0x8000, 0x8000, 0x8006, "mixForkInfolistNotify", 0x1104, 51534, "Opaque"),
    (0x8000, 0x8000, 0x8007, "naviGuideInfoNotify", 0x1105, 51534, "Opaque"),
    (0x8000, 0x8000, 0x8008, "nextCrossLaneInfoNotify", 0x1105, 51534, "Opaque"),
    (0x8000, 0x8000, 0x8009, "facilityInfoNotify", 0x1105, 51534, "Opaque"),
    (0x8000, 0x8000, 0x800A, "cameraInMapInfoNotify", 0x1105, 51534, "Opaque"),
    (0x8000, 0x8000, 0x800B, "naviHighwayGuideInfoNotify", 0x1105, 51534, "Opaque"),
    (0x8000, 0x8000, 0x800C, "naviTrafficLightNotify", 0x1106, 51534, "Opaque"),
    (0x8000, 0x8000, 0x800D, "trafficJamNotify", 0x1106, 51534, "Opaque"),
    (0x8000, 0x8000, 0x800E, "trafficEventInfoNotify", 0x1106, 51534, "Opaque"),
]

TABLES: dict[str, list[tuple[int, int, int, str, int, int, str]]] = {
    TABLE_OLD: HUD_EVENTS,
    TABLE_BPLUS: HUD_EVENTS_BPLUS,
}

# 各代表述（界面/文档/报告共用）
TABLE_INFO: dict[str, dict] = {
    TABLE_OLD: {
        "label": "old（当前）",
        "config": "someip_arhud01_pcap_server.json",
        "registrable": True,
        "note": "参考实现 old 配置；回放服务端已实测可注册并能回放 pcap",
    },
    TABLE_BPLUS: {
        "label": "bplus（新一代）",
        "config": "someip_arhud01_pcap_server_B+.json",
        "registrable": False,
        "note": "参考实现标注「B+ 还不能用」；本项目已收录服务表与配置，库侧待 HUD 提供可注册 B+ 表的版本",
    },
}

_active_table: str | None = None


def available_tables() -> dict[str, dict]:
    """{代号: 信息}（含事件数、配置文件名、是否可注册）。"""
    out = {}
    for name, info in TABLE_INFO.items():
        rows = TABLES[name]
        out[name] = {**info,
                     "services": len({r[0] for r in rows}),
                     "events": len(rows)}
    return out


def normalize_table(name: str | None) -> str:
    """把任意写法归一到代号（非法值回退默认 old）。"""
    import os
    text = str(name or "").strip().lower()
    if text in (TABLE_BPLUS, "b+", "bplus_table", "new"):
        return TABLE_BPLUS
    if text in (TABLE_OLD, "legacy", "current"):
        return TABLE_OLD
    if not text:
        env = os.environ.get(ENV_TABLE, "").strip()
        if env:
            return normalize_table(env)
    return TABLE_OLD


def active_table() -> str:
    """当前生效的服务表代号（进程内设置 → 环境变量 → 默认 old）。"""
    return _active_table or normalize_table(None)


def set_table(name: str | None) -> str:
    """设置进程内服务表（None 恢复跟随环境变量/默认）；返回设置后的代号。"""
    global _active_table
    _active_table = None if name is None else normalize_table(name)
    return active_table()


def table_events(table: str | None = None) -> list[tuple[int, int, int, str, int, int, str]]:
    """取某代的事件行（默认当前代）。"""
    return TABLES[normalize_table(table) if table else active_table()]


def table_meta(table: str | None = None) -> dict:
    """取某代的信息（含 label/services/events/registrable/note）。"""
    name = normalize_table(table) if table else active_table()
    return available_tables()[name] | {"name": name}


def registrable(table: str | None = None) -> bool:
    """该代的服务是否可由当前回放服务端（C++ 库）注册。"""
    return bool(table_meta(table).get("registrable"))


def describe_tables() -> str:
    """一句话描述两代服务表与当前选择（自检/日志用）。"""
    lines = []
    for name, info in available_tables().items():
        mark = "←当前" if name == active_table() else ""
        ok = "可注册" if info["registrable"] else "暂不可注册"
        lines.append(f"  {name:6s} {info['services']} 服务/{info['events']} 事件  "
                     f"{ok}  {info['label']} {mark}")
    return "SOME/IP 服务表：\n" + "\n".join(lines)


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


def all_events(table: str | None = None) -> list[EventDef]:
    """全部事件定义（默认当前代；按服务、事件号排序）。"""
    return [EventDef(*row) for row in sorted(table_events(table), key=lambda r: (r[0], r[2]))]


def services(only: Iterable[str] | None = None, table: str | None = None) -> list[ServiceDef]:
    """按服务聚合的事件定义；`only` 可传类型名筛选（如 {"RTK", "IMU"}）。"""
    keep = set(only) if only else None
    out: dict[int, ServiceDef] = {}
    for ev in all_events(table):
        if keep is not None and ev.kind not in keep:
            continue
        svc = out.setdefault(ev.service, ServiceDef(ev.service, ev.instance, ev.port))
        svc.events.append(ev)
    return [out[k] for k in sorted(out)]


def find_event(service: int, event: int, table: str | None = None) -> EventDef | None:
    """按 (service, event) 查找定义（默认当前代；找不到返回 None）。"""
    for ev in all_events(table):
        if ev.service == service and ev.event == event:
            return ev
    return None


def summarize() -> str:
    """一行摘要（界面/日志用）。"""
    svcs = services()
    return (f"{len(svcs)} 个服务 / {len(all_events())} 个事件"
            f"（可结构化发送 {len(STRUCT_TYPES)} 类，需 TP 分段 {len(TP_EVENTS)} 个事件）")
