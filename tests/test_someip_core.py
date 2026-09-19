# -*- coding: utf-8 -*-
"""tests/test_someip_core.py —— SOME/IP 回放核心层单元测试

覆盖：
  · 服务/事件定义表（11 服务 / 23 事件）与 KIND 映射的一致性
  · pcap 解析与 SOME/IP-TP 分片重组（用合成 pcap，不依赖真实 pcap 文件）
  · 回放配置读写（含损坏文件回退）
  · 回放控制器：用**假库**驱动完整会话流程（打开/注册/启动/回放/发送/关闭），
    以及库不可用、文件缺失等异常路径
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

import someip_core as sc
from someip_core import api as api_mod


# --------------------------------------------------------------------------- 定义表

def test_service_table_counts_and_consistency():
    svcs = sc.services()
    events = sc.all_events()
    assert len(svcs) == 11, "应为 11 个服务"
    assert len(events) == 23, "应为 23 个事件"
    # KIND 映射中的 (service, event) 必须都在定义表里
    table = {(e.service, e.event) for e in events}
    for kind, pair in sc.KIND_SERVICE_EVENT.items():
        assert pair in table, f"{kind} 映射 {pair} 不在事件表中"
    # 每个 service 的 instance/port 与事件表一致
    for svc in svcs:
        for ev in svc.events:
            assert ev.service == svc.service and ev.instance == svc.instance and ev.port == svc.port


def test_event_flags():
    tp = [e for e in sc.all_events() if e.need_tp]
    assert {(e.service, e.event) for e in tp} == set(sc.TP_EVENTS)
    rtk = sc.find_event(0x000B, 0x8001)
    assert rtk and rtk.kind == "RTK" and rtk.struct_sendable and not rtk.need_tp
    lane = sc.find_event(0x000C, 0x8002)
    assert lane and lane.need_tp and not lane.struct_sendable
    assert sc.find_event(0x9999, 0x8001) is None


def test_services_filter_by_kind():
    only = sc.services({"RTK", "IMU"})
    assert [s.service for s in only] == [0x000B]
    assert {e.kind for e in only[0].events} == {"RTK", "IMU"}


# --------------------------------------------------------------------------- pcap 解析

def _write_pcap(path: Path, frames: list[bytes]) -> None:
    """写一个最小 pcap（微秒、小端），frames 为以太网帧字节。"""
    with open(path, "wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for i, frame in enumerate(frames):
            f.write(struct.pack("<IIII", 1700000000 + i, 0, len(frame), len(frame)))
            f.write(frame)


def _eth_udp(payload: bytes, sport: int = 30490, dport: int = 30490) -> bytes:
    """构造 Ethernet + IPv4 + UDP 帧（承载 SOME/IP 消息）。"""
    udp = struct.pack(">HHHH", sport, dport, 8 + len(payload), 0) + payload
    total = 20 + len(udp)
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, total, 0, 0, 64, 17, 0,
                     bytes([192, 168, 1, 1]), bytes([224, 0, 2, 4])) + udp
    return bytes(12) + struct.pack(">H", 0x0800) + ip


def _someip(service: int, method: int, payload: bytes, mtype: int = 0x02,
            session: int = 1, tp_more: bool = False) -> bytes:
    """构造 SOME/IP 消息（含 Notification 与 TP 分片两种）。"""
    if mtype == 0x22:
        tp = struct.pack(">I", (0 if not tp_more else 1))
        body = tp + payload
        length = 8 + len(body)
    else:
        body = payload
        length = 8 + len(body)
    return struct.pack(">HHIHHBBBB", service, method, length, 1, session,
                       0x01, 0x01, mtype, 0x00) + body


def test_pcap_parse_and_tp_reassembly(tmp_path):
    pcap = tmp_path / "sample.pcap"
    _write_pcap(pcap, [
        _eth_udp(_someip(0xFFFF, 0x8100, b"sd-offer")),                    # SD → 计入 sd
        _eth_udp(_someip(0x000B, 0x8001, b"rtk-payload")),                 # 普通通知
        _eth_udp(_someip(0x000B, 0x8002, b"imu-1")),                       # 普通通知（同服务另一事件）
        _eth_udp(_someip(0x000C, 0x8002, b"A" * 100, mtype=0x22, tp_more=True)),   # TP 第 1 片
        _eth_udp(_someip(0x000C, 0x8002, b"B" * 50, mtype=0x22, tp_more=False,
                         session=1)),                                       # TP 第 2 片
        b"\x00" * 20,                                                       # 非 IPv4/UDP → others
    ])
    summary = sc.parse_summary(pcap)
    assert summary.error is None
    assert summary.total_packets == 6
    assert summary.sd_packets == 1
    assert summary.plain_notifications == 2
    assert summary.tp_segments == 2
    assert summary.others == 1
    # TP 两片按偏移重组为 150 字节
    assert len(summary.payloads[(0x000C, 0x8002)]) == 1
    assert len(summary.payloads[(0x000C, 0x8002)][0]) == 150
    assert summary.payloads[(0x000B, 0x8001)] == [b"rtk-payload"]
    # 事件统计
    stats = summary.events[(0x000C, 0x8002)]
    assert stats.count == 1 and stats.max_len == 150 and stats.tp_segments == 1
    assert summary.replayable == 3
    assert "SD 1" in summary.describe()


def test_pcap_missing_file_and_bad_format(tmp_path):
    missing = tmp_path / "none.pcap"
    s = sc.parse_summary(missing)
    assert s.error and "不存在" in s.error and s.replayable == 0

    bad = tmp_path / "bad.pcap"
    bad.write_bytes(b"not a pcap at all" * 4)
    s2 = sc.parse_summary(bad)
    assert s2.error and "pcap" in s2.error


# --------------------------------------------------------------------------- 配置

def test_config_roundtrip_and_corruption(tmp_path):
    p = tmp_path / "cfg.json"
    cfg = sc.ReplayConfig(unicast="192.168.1.10", pcap_path="/tmp/a.pcap",
                          loop=False, interval_ms=-5, selected=["0x000B"])
    cfg.normalized()
    assert cfg.interval_ms == 0, "非法间隔应被修正为 0"
    cfg.save(p)
    loaded = sc.ReplayConfig.load(p)
    assert loaded.unicast == "192.168.1.10" and loaded.loop is False
    assert loaded.selected == ["0x000B"]

    p.write_text("{ 这不是 JSON", encoding="utf-8")
    fallback = sc.ReplayConfig.load(p)
    assert fallback.network == "arhud01" and fallback.loop is True, "损坏配置应回退默认值"


# --------------------------------------------------------------------------- 控制器（假库）

class FakeLib:
    """模拟 SomeipLib：记录调用，返回可预期的结果。"""

    def __init__(self):
        self.calls: list[tuple] = []
        self.sent_payloads: list[tuple[int, int, bytes]] = []
        self._sent = 0

    def create(self, unicast=None, config_path=None):
        self.calls.append(("create", unicast, config_path))
        return 0x1000

    def destroy(self, handle):
        self.calls.append(("destroy", handle))

    def start(self, handle):
        self.calls.append(("start", handle))
        return 0

    def stop(self, handle):
        self.calls.append(("stop", handle))

    def add_service(self, handle, service, instance, port=0, major=1, minor=0):
        self.calls.append(("add_service", service, instance, port, major, minor))
        return 0

    def add_event(self, handle, service, instance, event, group=0x1101):
        self.calls.append(("add_event", service, instance, event, group))
        return 0

    def notify_raw(self, handle, service, event, data):
        self.sent_payloads.append((service, event, bytes(data)))
        self._sent += 1
        return 0

    def serialize(self, handle, kind, fields):
        # 用字段个数与类型名模拟序列化结果（真实库返回大端+CRC32 载荷）
        return f"{kind}:{len(fields)}".encode()

    def replay_start(self, handle, pcap_path, loop=True, interval_ms=10):
        self.calls.append(("replay_start", str(pcap_path), loop, interval_ms))
        return 5

    def replay_stop(self, handle):
        self.calls.append(("replay_stop",))

    def replay_sent(self, handle):
        return 7


def _controller(fake: FakeLib, logs: list[str]) -> sc.ReplayController:
    ctl = sc.ReplayController(on_log=logs.append, lib=fake)
    ctl.state.library_ok = True
    return ctl


def test_controller_full_session(tmp_path):
    fake, logs = FakeLib(), []
    ctl = _controller(fake, logs)
    ctl.open(unicast="192.168.1.20")
    n_svc, n_evt = ctl.register()
    assert (n_svc, n_evt) == (11, 23), "默认应注册全部服务与事件"
    ctl.start()

    pcap = tmp_path / "x.pcap"
    _write_pcap(pcap, [_eth_udp(_someip(0x000B, 0x8001, b"rtk"))])   # 含 1 条通知
    parsed = ctl.play_pcap(pcap, loop=True, interval_ms=5)
    assert parsed == 1 == ctl.expected, "应返回本地解析出的预期条数"
    assert ctl.state.replaying, "循环回放不应因计数稳定而判定完成"
    assert ctl.refresh_sent() == 7

    svc, evt, size = ctl.send_struct("RTK", Counter=3, longitude=116.4, latitude=39.9)
    assert (svc, evt) == sc.KIND_SERVICE_EVENT["RTK"]
    assert size == len("RTK:3".encode()) and fake.sent_payloads[-1][0] == svc

    ctl.send_raw(0x000A, 0x8001, b"\x01\x02\x03")
    assert fake.sent_payloads[-1] == (0x000A, 0x8001, b"\x01\x02\x03")

    ctl.stop_replay()
    ctl.close()
    assert not ctl.state.opened and not ctl.state.replaying
    assert any(c[0] == "destroy" for c in fake.calls)
    assert any("已注册" in m for m in logs) and any("回放" in m for m in logs)


def test_replay_completion_detection(tmp_path):
    """单次回放：计数连续不变后应判定完成并写入日志。"""
    fake, logs = FakeLib(), []
    ctl = _controller(fake, logs)
    ctl.open()
    pcap = tmp_path / "x.pcap"
    _write_pcap(pcap, [_eth_udp(_someip(0x000B, 0x8001, b"rtk"))])
    ctl.play_pcap(pcap, loop=False)
    assert ctl.state.replaying is True
    for _ in range(5):                       # 首次建基线 + 连续 3 次不变 → 判定播完
        ctl.refresh_sent()
    assert ctl.state.replaying is False
    assert any("回放完成" in m for m in logs), logs
    ctl.close()


def test_controller_selected_services_and_errors(tmp_path):
    fake, logs = FakeLib(), []
    ctl = _controller(fake, logs)
    ctl.open()
    n_svc, n_evt = ctl.register(selected_services=["0x000B"])
    assert n_svc == 1 and n_evt == 2, "只注册 0x000B（RTK + IMU）"

    # 未注册/未启动时的错误提示应明确
    with pytest.raises(FileNotFoundError):
        ctl.play_pcap(tmp_path / "missing.pcap")
    with pytest.raises(ValueError):
        ctl.send_struct("不存在的类型")
    ctl.close()


def test_controller_reports_graceful_error_without_library(monkeypatch):
    """库不可用时：抛出带修复提示的 SomeipUnavailable（而不是崩溃/静默）。"""
    monkeypatch.setattr(api_mod, "open_library", lambda: None)
    ctl = sc.ReplayController(on_log=lambda m: None)
    ctl._lib = None
    with pytest.raises(sc.SomeipUnavailable) as ei:
        ctl._require_lib()
    msg = str(ei.value)
    assert "未找到 SOME/IP 服务端库" in msg
    assert "drivers/someip" in msg
    # 状态摘要也应反映"库不可用"
    ctl.state.library_ok = False
    assert "库不可用" in ctl.summary()


# --------------------------------------------------------------------------- 库探测优先级

def test_library_probe_priority(tmp_path, monkeypatch):
    """库探测顺序：环境变量 > thirdparty/arhud_someip/<平台> > drivers/someip（旧位置）。"""
    import hudcore.someip.backend as be

    class StubPaths:
        project_root = tmp_path
        thirdparty_dir = tmp_path / "thirdparty"
        platform_dir_name = "linux"
        platform_arch_dir_name = "linux-x86_64"

        @property
        def drivers_dir(self):
            return tmp_path / "drivers" / "linux"

    monkeypatch.setattr(be, "paths", StubPaths())
    monkeypatch.delenv("HUD_SOMEIP_LIB", raising=False)
    monkeypatch.delenv("ARHUD_LIB_PATH", raising=False)
    monkeypatch.delenv("HUD_SOMEIP_LIB_DIR", raising=False)
    monkeypatch.delenv("ARHUD_LIB_DIR", raising=False)
    lib_name = be.LIB_CANDIDATES[0]

    assert be.find_someip_library() is None, "任何位置都没有库时应返回 None"

    legacy = tmp_path / "drivers" / "linux" / "someip"
    legacy.mkdir(parents=True)
    (legacy / lib_name).write_bytes(b"")
    assert be.find_someip_library() == legacy / lib_name, "旧位置应可作为兜底命中"

    preferred = tmp_path / "thirdparty" / "arhud_someip" / "linux"
    preferred.mkdir(parents=True)
    (preferred / lib_name).write_bytes(b"")
    assert be.find_someip_library() == preferred / lib_name, "thirdparty 位置优先于旧位置"

    override = tmp_path / "custom" / lib_name
    override.parent.mkdir()
    override.write_bytes(b"")
    monkeypatch.setenv("HUD_SOMEIP_LIB", str(override))
    assert be.find_someip_library() == override, "环境变量应优先于所有项目内位置"


def test_not_found_hint_points_to_thirdparty(monkeypatch):
    """修复提示应指向 thirdparty/arhud_someip/<平台>/。"""
    import hudcore.someip.backend as be
    hint = be._not_found_hint()
    assert "thirdparty/arhud_someip" in hint
    assert "drivers/someip" in hint, "同时说明旧位置兼容"
