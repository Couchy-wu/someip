# -*- coding: utf-8 -*-
"""someip_core.config —— SOME/IP 回放的配置读写

配置内容（`data/someip/replay_config.json`）：
    unicast        本机 SD 单播地址（留空则自动探测）
    network        vsomeip 配置里的 network 名（默认 arhud01，与板端/示例一致）
    config_path    vsomeip 配置 JSON 路径（留空则由 C++ 库使用内置默认）
    pcap_path      上次使用的 pcap 路径
    loop           是否循环回放
    interval_ms    回放节流间隔（加速回放，0=按原始时序）
    auto_start     打开窗口时是否自动启动服务
    selected       勾选要注册的服务（服务号字符串列表；空=全部）

设计：配置与代码分离（放 data/ 下，随仓库分发），读写失败不抛异常而是回退默认值，
保证界面在配置损坏时仍能启动。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from hudcore.platform.paths import paths

from .models import all_events, services

CONFIG_DIR_NAME = "someip"
CONFIG_FILE_NAME = "replay_config.json"
TABLE_FILE_NAME = "services.json"


def data_dir() -> Path:
    """SOME/IP 数据目录（data/someip）。"""
    d = paths.data_dir / CONFIG_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return data_dir() / CONFIG_FILE_NAME


def table_path() -> Path:
    return data_dir() / TABLE_FILE_NAME


@dataclass
class ReplayConfig:
    """回放界面的持久化配置。"""

    unicast: str = ""
    network: str = "arhud01"
    config_path: str = ""
    pcap_path: str = ""
    loop: bool = True
    interval_ms: int = 10
    auto_start: bool = False
    selected: list[str] = field(default_factory=list)     # 服务号，如 ["0x000B", "0x000D"]
    last_event_kind: str = "RTK"                          # 上次结构化发送的类型

    # ---------------- 读写 ----------------
    @classmethod
    def load(cls, path: Path | None = None) -> "ReplayConfig":
        """读取配置；文件缺失/损坏时返回默认值（不抛异常）。"""
        p = Path(path) if path else config_path()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        known = {f for f in cls.__dataclass_fields__}          # type: ignore[attr-defined]
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path | None = None) -> Path:
        """保存配置（自动建目录）。"""
        p = Path(path) if path else config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    def normalized(self) -> "ReplayConfig":
        """修正非法取值（供界面直接使用）。"""
        self.interval_ms = max(0, min(5000, int(self.interval_ms or 0)))
        self.network = (self.network or "arhud01").strip()
        return self


def export_service_table(path: Path | None = None) -> Path:
    """把内置的服务/事件表导出为 JSON（便于核对与外部工具读取）。"""
    p = Path(path) if path else table_path()
    table = {
        "summary": f"{len(services())} 服务 / {len(all_events())} 事件",
        "services": [
            {
                "service": f"0x{svc.service:04X}",
                "instance": f"0x{svc.instance:04X}",
                "port": svc.port,
                "events": [
                    {
                        "event": f"0x{ev.event:04X}",
                        "name": ev.name,
                        "group": f"0x{ev.group:04X}",
                        "kind": ev.kind,
                        "need_tp": ev.need_tp,
                        "struct_sendable": ev.struct_sendable,
                    }
                    for ev in svc.events
                ],
            }
            for svc in services()
        ],
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
