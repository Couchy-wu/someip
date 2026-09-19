# -*- coding: utf-8 -*-
"""someip_core —— SOME/IP 回放与发送（业务层，不含界面）

能力来源：C++ 服务端库 `libarhud_server`（arhud_python_server 工程），
通过 ctypes 调用；本包只做业务编排与数据处理，界面见 `someip_gui`。

模块划分：
    models.py    服务/事件定义表（两代：old 11 服务/23 事件、bplus 6 服务/38 事件）与数据类型
    api.py       ctypes 绑定（惰性加载；结构体、序列化、回放、发送）
    pcap_info.py pcap 解析与摘要（TP 分片重组；供界面展示与预检）
    config.py    回放配置读写（data/someip/replay_config.json）+ 随仓库分发的 vsomeip 配置
    replay.py    回放控制器（会话/注册/启动/回放/单条发送/状态）

依赖约束：可依赖 hudcore（平台与路径）与标准库；不依赖任何界面层。
"""
from .config import (
    ReplayConfig, available_shipped_configs, config_path, export_service_table,
    shipped_config_dir, shipped_config_path, table_path,
)
from .models import (
    TABLE_BPLUS, TABLE_OLD,
    active_table, available_tables, describe_tables, normalize_table, registrable, set_table,
    table_events, table_meta,
    HUD_EVENTS, KIND_SERVICE_EVENT, STRUCT_TYPES, TP_EVENTS,
    EventDef, ServiceDef, all_events, find_event, services, summarize,
)
from .pcap_info import EventStat, PcapSummary, decode_pcap, parse_summary
from .replay import ReplayController, ReplayState, SomeipUnavailable

__all__ = [
    # 定义表
    "HUD_EVENTS", "KIND_SERVICE_EVENT", "STRUCT_TYPES", "TP_EVENTS",
    "EventDef", "ServiceDef", "all_events", "services", "find_event", "summarize",
    # 服务表代（old / bplus）
    "TABLE_OLD", "TABLE_BPLUS", "active_table", "set_table", "available_tables",
    "table_events", "table_meta", "registrable", "describe_tables", "normalize_table",
    # pcap
    "PcapSummary", "EventStat", "parse_summary", "decode_pcap",
    # 配置
    "ReplayConfig", "config_path", "table_path", "export_service_table",
    "shipped_config_path", "shipped_config_dir", "available_shipped_configs",
    # 控制器
    "ReplayController", "ReplayState", "SomeipUnavailable",
]
