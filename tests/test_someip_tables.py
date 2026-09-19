# -*- coding: utf-8 -*-
"""tests/test_someip_tables.py —— SOME/IP 服务表代与随仓库配置（参考实现对齐）

覆盖：
  · 两代服务表（old 11 服务/23 事件、bplus 6 服务/38 事件）与切换开关
  · **随仓库分发的 vsomeip 配置与服务表逐条一致**（防止文档/表/配置三者漂移）
  · 配置默认值（`ReplayConfig.effective_config_path()`）与"哪些代可注册"
  · Di 用例解析的代际感知（服务属于哪一代、当前代能否下发）
  · 仓库自带样例 pcap 可用
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hudcore.platform.paths import paths
from someip_core import (
    TABLE_BPLUS, TABLE_OLD, ReplayConfig, active_table, all_events, available_tables,
    describe_tables, find_event, normalize_table, registrable, services, set_table,
    shipped_config_path, table_events, table_path,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "data" / "someip" / "config"


@pytest.fixture(autouse=True)
def _reset_table():
    set_table(None)
    yield
    set_table(None)


# =========================================================================== 代际
def test_two_generations_available_with_expected_sizes():
    info = available_tables()
    assert set(info) == {TABLE_OLD, TABLE_BPLUS}
    assert (info[TABLE_OLD]["services"], info[TABLE_OLD]["events"]) == (11, 23)
    assert (info[TABLE_BPLUS]["services"], info[TABLE_BPLUS]["events"]) == (6, 38)
    assert info[TABLE_OLD]["registrable"] is True
    # 2026-02 起服务端库（arhud_python_server）两代都能注册：profile 由库侧
    # ARHUD_SERVICE_PROFILE 选择，实测 B+ 可注册 6 服务/38 事件并完整回放其 pcap
    assert info[TABLE_BPLUS]["registrable"] is True


def test_table_switch_and_env(monkeypatch):
    assert active_table() == TABLE_OLD, "默认必须是 old（回放库实际注册的那一代）"
    assert set_table(TABLE_BPLUS) == TABLE_BPLUS
    assert len(all_events()) == 38 and len(services()) == 6
    assert set_table(None) == TABLE_OLD

    monkeypatch.setenv("HUD_SOMEIP_TABLE", "bplus")
    assert active_table() == TABLE_BPLUS
    monkeypatch.setenv("HUD_SOMEIP_TABLE", "乱七八糟")
    assert active_table() == TABLE_OLD, "非法值回退 old"
    monkeypatch.delenv("HUD_SOMEIP_TABLE", raising=False)


def test_normalize_and_registrable():
    assert normalize_table("B+") == TABLE_BPLUS
    assert normalize_table("old") == TABLE_OLD
    assert normalize_table(None) == TABLE_OLD
    assert registrable(TABLE_OLD) is True and registrable(TABLE_BPLUS) is True


def test_tables_can_be_queried_independently():
    """查询接口可显式指定代，不受当前选择影响。"""
    assert len(all_events(table=TABLE_OLD)) == 23
    assert len(all_events(table=TABLE_BPLUS)) == 38
    assert len(table_events(TABLE_BPLUS)) == 38
    bplus_events = {f"0x{e.event:04X}" for e in all_events(table=TABLE_BPLUS)}
    assert "0x800E" in bplus_events, "B+ 的 0x8000 服务有 14 个事件（到 0x800E）"
    assert find_event(0x001B, 0x8001, table=TABLE_BPLUS).name == "obstacleNotify"
    assert find_event(0x001B, 0x8001, table=TABLE_OLD) is None, "该服务只在 bplus 代"


def test_describe_tables_mentions_both():
    text = describe_tables()
    assert "old" in text and "bplus" in text
    assert "11 服务/23 事件" in text and "6 服务/38 事件" in text
    assert "可注册" in text


def test_service_table_files_exist_per_generation():
    assert table_path(TABLE_OLD).name == "services.json"
    assert table_path(TABLE_BPLUS).name == "services_bplus.json"
    assert table_path(TABLE_OLD).is_file() and table_path(TABLE_BPLUS).is_file()


# =========================================================================== 配置一致性
SERVICE_TABLE_FILES = {TABLE_OLD: "someip_arhud01_pcap_server.json",
                       TABLE_BPLUS: "someip_arhud01_pcap_server_B+.json"}


@pytest.mark.parametrize("table, config_name", list(SERVICE_TABLE_FILES.items()))
def test_shipped_config_matches_service_table(table, config_name):
    """随仓库分发的参考配置与我们代码里的服务表**必须逐条一致**。

    这条断言把"文档/表/配置"三者钉在一起：任何一侧改动而另一侧没跟上都会失败。
    """
    path = CONFIG_DIR / config_name
    assert path.is_file(), f"缺少随仓库配置：{path}"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg_set = {(int(s["service"], 16), int(s["instance"], 16), int(e["event"], 16))
               for s in cfg["services"] for e in s["events"]}
    code_set = {(r[0], r[1], r[2]) for r in table_events(table)}
    assert cfg_set == code_set, (f"{table} 代服务表与 {config_name} 不一致："
                                f"只在配置 {sorted(cfg_set - code_set)}；"
                                f"只在代码 {sorted(code_set - cfg_set)}")


@pytest.mark.parametrize("table, config_name", list(SERVICE_TABLE_FILES.items()))
def test_shipped_config_keeps_reference_sd_settings(table, config_name):
    """参考实现的 SD 关键参数要保持一致（组播/端口/重复次数）。"""
    cfg = json.loads((CONFIG_DIR / config_name).read_text(encoding="utf-8"))
    sd = cfg["service-discovery"]
    assert sd["multicast"] == "224.0.2.4" and sd["port"] == "30490"
    assert sd["protocol"] == "udp" and sd["enable"] == "true"
    assert cfg["applications"][0]["name"] == "arhud01"
    assert cfg["routing"] == "arhud01"
    assert int(cfg.get("max-payload-size-unreliable", 0)) == 3_000_000


def test_shipped_config_selection_and_defaults():
    old_cfg = shipped_config_path(TABLE_OLD)
    bplus_cfg = shipped_config_path(TABLE_BPLUS)
    assert old_cfg is not None and old_cfg.is_file()
    assert bplus_cfg is not None and bplus_cfg.name.endswith("B+.json")

    cfg = ReplayConfig()
    assert cfg.service_table == TABLE_OLD
    assert Path(cfg.effective_config_path()).name == old_cfg.name, "留空时应落到当前代的随仓库配置"
    cfg.service_table = TABLE_BPLUS
    assert Path(cfg.effective_config_path()).name == bplus_cfg.name
    cfg.config_path = "/tmp/explicit.json"
    assert cfg.effective_config_path() == "/tmp/explicit.json", "显式指定优先"


def test_replay_config_roundtrip_keeps_table(tmp_path):
    cfg = ReplayConfig(service_table=TABLE_BPLUS, unicast="192.168.1.9")
    path = cfg.save(tmp_path / "cfg.json")
    loaded = ReplayConfig.load(path).normalized()
    assert loaded.service_table == TABLE_BPLUS
    assert loaded.unicast == "192.168.1.9"
    bad = ReplayConfig(service_table="不存在")
    assert bad.normalized().service_table == TABLE_OLD


# =========================================================================== Di 解析代际感知
def test_someip_field_map_reports_generation():
    from can_data_tools import someip_field_map as M

    set_table(TABLE_OLD)
    target_old = M.resolve("hnmap_s.navigation_map")
    assert target_old.supported and target_old.table == TABLE_OLD and target_old.registrable

    set_table(TABLE_BPLUS)
    target_bplus = M.resolve("hnmap_s.navigation_map")
    assert target_bplus.supported, "0x010A 两代都有，字段映射仍然成立"
    assert target_bplus.table == TABLE_BPLUS and target_bplus.registrable is True

    assert M.service_generation("0x010A") == (TABLE_OLD, TABLE_BPLUS)
    assert M.service_generation("0x000C") == (TABLE_OLD,)
    assert M.service_generation("0x001B") == (TABLE_BPLUS,)
    assert M.service_generation("0x9999") == ()


def test_di_case_classification_is_generation_aware():
    """用例引用的 SOME/IP 服务不属于当前代时，必须明确报出来（而不是静默通过）。"""
    from can_data_tools import di_case_parser as parser

    case_dir = PROJECT_ROOT / parser.DEFAULT_CASE_DIR
    if not case_dir.is_dir():
        pytest.skip("未找到 Di 用例目录")
    cases = parser.load_cases(case_dir)
    old_only = next((c for c in cases
                     if any(l.service_id == "0x000C" for l in c.someip_links)), None)
    assert old_only is not None, "样例里应有引用 0x000C 的用例"

    old_support = parser.classify(old_only, someip_table=TABLE_OLD)
    assert "0x000C" not in " ".join(old_support.reasons), "old 代下该服务可下发，不该报缺失"

    bplus_support = parser.classify(old_only, someip_table=TABLE_BPLUS)
    assert any("0x000C" in r for r in bplus_support.reasons), "bplus 代下应报「服务不在当前服务表」"


def test_describe_inputs_mentions_table():
    from can_data_tools import di_case_parser as parser
    from can_data_tools.someip_field_map import describe_inputs

    case_dir = PROJECT_ROOT / parser.DEFAULT_CASE_DIR
    if not case_dir.is_dir():
        pytest.skip("未找到 Di 用例目录")
    case = next(c for c in parser.load_cases(case_dir) if c.someip_links)
    lines = describe_inputs(case, table=TABLE_OLD)
    assert lines and "old" in lines[0]


def test_open_syncs_service_table_to_library(monkeypatch):
    """`ReplayController.open()` 必须把当前服务表代同步给 C++ 库（ARHUD_SERVICE_PROFILE）。

    不同步会出现"Python 注册了 38 个事件、库只注册 23 个"的不一致：Python 侧按自己的表逐条
    调用 add_service/add_event，而库在 create() 时按环境变量决定内置表。
    这里用假库替身验证，无需真实库。
    """
    from someip_core import ReplayController

    class _FakeLib:
        def __init__(self):
            self.created = []

        def create(self, unicast, config_path):
            self.created.append((unicast, config_path))
            return 0x1234

    logs: list[str] = []
    fake = _FakeLib()
    monkeypatch.delenv("ARHUD_SERVICE_PROFILE", raising=False)
    monkeypatch.setattr(ReplayController, "_require_lib", lambda self: fake)

    ctl = ReplayController(on_log=logs.append)
    set_table(TABLE_BPLUS)
    ctl.open()
    assert os.environ.get("ARHUD_SERVICE_PROFILE") == TABLE_BPLUS
    assert fake.created, "open() 应真正调用库的 create()"
    monkeypatch.delenv("ARHUD_SERVICE_PROFILE", raising=False)

    set_table(TABLE_OLD)
    ReplayController().open()
    assert os.environ.get("ARHUD_SERVICE_PROFILE") == TABLE_OLD, "以 Python 侧服务表代为准"


def test_env_var_of_library_is_recognised_as_table(monkeypatch):
    """只设库侧开关（ARHUD_SERVICE_PROFILE）时，Python 侧也应认它为当前代。"""
    monkeypatch.delenv("HUD_SOMEIP_TABLE", raising=False)
    monkeypatch.setenv("ARHUD_SERVICE_PROFILE", "bplus")
    assert active_table() == TABLE_BPLUS


def test_open_warns_when_library_env_conflicts(monkeypatch):
    """库侧环境变量与服务表代冲突时：以服务表代为准，并给出明确告警（不静默改）。"""
    from someip_core import ReplayController

    class _FakeLib:
        def create(self, unicast, config_path):
            return 0x1234

    monkeypatch.setattr(ReplayController, "_require_lib", lambda self: _FakeLib())
    monkeypatch.setenv("ARHUD_SERVICE_PROFILE", "bplus")
    set_table(TABLE_OLD)
    logs: list[str] = []
    ReplayController(on_log=logs.append).open()
    assert os.environ["ARHUD_SERVICE_PROFILE"] == TABLE_OLD, "以服务表代为准"
    assert any("不一致" in m for m in logs), f"应记录冲突告警，实际日志：{logs}"


# =========================================================================== 自带样例 pcap
def test_sample_pcap_shipped_and_parsable():
    from someip_core import parse_summary

    sample = PROJECT_ROOT / "data" / "someip" / "sample" / "out_sample.pcap"
    assert sample.is_file(), "仓库应自带小样例 pcap（供 offline 检查脚本使用）"
    assert sample.stat().st_size < 2 * 1024 * 1024, "样例 pcap 应保持精简（进 git）"
    summary = parse_summary(str(sample))
    assert summary.replayable > 0
    assert summary.total_packets > 100


def test_replay_check_script_importable():
    """检查脚本必须能在无设备时被导入（不产生副作用）。"""
    import importlib
    mod = importlib.import_module("scripts.someip_replay_check")
    assert callable(mod.main)
    assert mod._default_pcap() is not None, "默认应能找到随仓库分发的样例 pcap"
