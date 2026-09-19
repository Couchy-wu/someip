# -*- coding: utf-8 -*-
"""someip_core.replay —— SOME/IP 回放与发送控制器

职责：把 C++ 库的裸接口包装成界面可直接使用的"高层动作"，并统一处理：
    · 库不可用（Windows 暂无 DLL 等）→ 抛出带修复提示的 `SomeipUnavailable`
    · 服务/事件注册（默认注册全部 11 服务 / 23 事件，可只注册勾选项）
    · pcap 回放（循环、节流间隔、已发送计数）
    · 结构化单条发送（字段赋值 → C++ 序列化 → 发送）
    · 日志回调（供界面把每步操作显示到日志区）
    · 状态查询（供界面刷新按钮/计数）

本模块**不依赖 tkinter**，可在无显示器/自动化测试中使用（用假库替换 api 即可）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from hudcore.someip import is_library_available
from hudcore.someip.backend import _not_found_hint

from . import api as api_mod
from .models import (
    KIND_SERVICE_EVENT, STRUCT_TYPES, active_table, all_events, find_event, services,
)
from .pcap_info import parse_summary

LogFn = Callable[[str], None]

# 单次回放"连续多少次计数不变"判定为播完（界面刷新间隔 800ms → 约 2.4s 抖动容忍）
_STALL_TICKS = 3


class SomeipUnavailable(RuntimeError):
    """SOME/IP 库不可用（未找到或加载失败）。"""


@dataclass
class ReplayState:
    """当前状态快照（界面定时刷新用）。"""

    library_ok: bool = False
    opened: bool = False
    started: bool = False
    replaying: bool = False
    replay_sent: int = 0
    registered_services: int = 0
    registered_events: int = 0
    last_error: str = ""
    pcap_path: str = ""
    extra: dict = field(default_factory=dict)


class ReplayController:
    """SOME/IP 回放控制器（一次会话对应一个 C++ 服务端实例）。"""

    def __init__(self, on_log: LogFn | None = None,
                 lib: api_mod.SomeipLib | None = None) -> None:
        self._log_fn = on_log or (lambda msg: None)
        self._lib = lib                       # 可注入（测试用假库）
        self._handle: int | None = None
        self._loop = True                     # 当前回放是否循环（用于判断"是否已播完"）
        self._stall = 0                       # 计数连续未增长的刷新次数
        self.expected = 0                     # 最近一次回放的预期条数（由本包解析 pcap 得出）
        self.state = ReplayState(library_ok=lib is not None or is_library_available())

    # ---------------- 基础设施 ----------------
    def _log(self, msg: str) -> None:
        self._log_fn(msg)

    def _require_lib(self) -> api_mod.SomeipLib:
        if self._lib is not None:
            return self._lib
        lib = api_mod.open_library()
        if lib is None:
            self.state.library_ok = False
            raise SomeipUnavailable(
                "SOME/IP 服务端库不可用。\n" + _not_found_hint())
        self._lib = lib
        self.state.library_ok = True
        return lib

    @staticmethod
    def library_hint() -> str:
        """库不可用时的修复提示（界面直接展示）。"""
        return _not_found_hint()

    @staticmethod
    def structure_types() -> tuple[str, ...]:
        """支持结构化发送的类型名。"""
        return STRUCT_TYPES

    # ---------------- 会话 ----------------
    def open(self, unicast: str | None = None, config_path: str | None = None) -> None:
        """创建服务端实例（未启动）。"""
        lib = self._require_lib()
        if self._handle is not None:
            self._log("服务端已打开，忽略重复打开")
            return
        # 未显式指定时，用"当前服务表代"随仓库分发的 vsomeip 配置（参考实现同款配置）
        from .config import shipped_config_path
        cfg = config_path or (str(shipped_config_path()) or None)
        self._handle = lib.create(unicast or None, cfg)
        self.state.opened = True
        self._log(f"服务端已创建：unicast={unicast or api_mod.default_ip()}"
                  f"{'，配置=' + cfg if cfg else '（使用库内置默认配置）'}"
                  f"｜服务表={active_table()}")

    def register(self, only_kinds: Iterable[str] | None = None,
                 selected_services: Iterable[str] | None = None) -> tuple[int, int]:
        """注册服务与事件；返回 (服务数, 事件数)。

        :param only_kinds: 仅注册这些数据类型（如 {"RTK","IMU"}）；None=全部
        :param selected_services: 仅注册这些服务号（"0x000B" 形式）；优先于 only_kinds
        """
        lib = self._require_lib()
        if self._handle is None:
            raise RuntimeError("请先 open() 再注册服务")
        svcs = services(only_kinds)
        if selected_services:
            wanted = {s.upper() for s in selected_services}
            svcs = [s for s in svcs if s.key.upper() in wanted or f"0x{s.service:04X}" in wanted]
        n_svc = n_evt = 0
        for svc in svcs:
            rc = lib.add_service(self._handle, svc.service, svc.instance, svc.port)
            if rc != 0:
                self._log(f"注册服务 0x{svc.service:04X} 失败 rc={rc}")
                continue
            n_svc += 1
            for ev in svc.events:
                rc = lib.add_event(self._handle, ev.service, ev.instance, ev.event, ev.group)
                if rc != 0:
                    self._log(f"注册事件 {ev.key} 失败 rc={rc}")
                else:
                    n_evt += 1
        self.state.registered_services = n_svc
        self.state.registered_events = n_evt
        self._log(f"已注册 {n_svc} 个服务 / {n_evt} 个事件")
        return n_svc, n_evt

    def start(self) -> None:
        """启动服务（offer + SD）。"""
        lib = self._require_lib()
        if self._handle is None:
            raise RuntimeError("请先 open()")
        rc = lib.start(self._handle)
        if rc != 0:
            self.state.last_error = f"arhud_server_start rc={rc}"
            raise RuntimeError(f"启动失败 rc={rc}（检查网络地址/权限/SD 配置）")
        self.state.started = True
        self._log("服务已启动（开始 offer 与 SD 应答）")

    def stop(self) -> None:
        """停止服务（不销毁实例）。"""
        if self._lib is None or self._handle is None:
            return
        self._lib.stop(self._handle)
        self.state.started = False
        self.state.replaying = False
        self._log("服务已停止")

    def close(self) -> None:
        """销毁实例（释放 vsomeip 资源）。"""
        if self._lib is None or self._handle is None:
            self._handle = None
            self.state.opened = False
            return
        try:
            if self.state.replaying:
                self._lib.replay_stop(self._handle)
            self._lib.destroy(self._handle)
        finally:
            self._handle = None
            self.state.opened = False
            self.state.started = False
            self.state.replaying = False
            self._log("服务端已关闭")

    # ---------------- 回放 ----------------
    def play_pcap(self, pcap_path: str | Path, loop: bool = True,
                  interval_ms: int = 10) -> int:
        """开始 pcap 回放（C++ 库后台线程，含 TP 重组）；返回库解析出的消息数。"""
        lib = self._require_lib()
        if self._handle is None:
            raise RuntimeError("请先 open() 并 start()")
        path = Path(pcap_path)
        if not path.is_file():
            raise FileNotFoundError(f"pcap 文件不存在：{path}")
        # 先做一次本地解析，得到"预期条数"（库的返回值只是状态码：0=成功，-1=失败）
        summary = parse_summary(path)
        self.expected = summary.replayable
        rc = lib.replay_start(self._handle, str(path), loop, interval_ms)
        if rc < 0:
            raise RuntimeError(
                f"回放启动失败 rc={rc}（pcap 无法解析或服务未启动）"
                + (f"；本地解析：{summary.error}" if summary.error else ""))
        self.state.replaying = True
        self.state.pcap_path = str(path)
        self._loop = bool(loop)
        self._stall = 0
        self._log(f"开始回放 {path.name}（{'循环' if loop else '单次'}，间隔 {interval_ms}ms）；"
                  f"该 pcap 本地解析到 {self.expected} 条可回放通知"
                  + (f"｜{summary.describe()}" if self.expected else ""))
        return self.expected

    def stop_replay(self) -> None:
        if self._lib is None or self._handle is None:
            return
        self._lib.replay_stop(self._handle)
        self.state.replaying = False
        self._log(f"回放已停止（累计发送 {self.state.replay_sent} 条）")

    def refresh_sent(self) -> int:
        """刷新已回放条数（界面定时调用）。

        附带"回放完成"检测：单次回放时若计数连续多次不再增长，判定已播完并记录日志
        （库本身不提供完成标志，只能靠计数稳定来判断）。
        """
        if self._lib is None or self._handle is None:
            return self.state.replay_sent
        try:
            sent = self._lib.replay_sent(self._handle)
        except Exception as exc:                      # 库内状态异常不应打断界面
            self.state.last_error = str(exc)
            return self.state.replay_sent

        if sent == self.state.replay_sent and self.state.replaying and sent > 0:
            self._stall += 1
            if not self._loop and self._stall >= _STALL_TICKS:
                self.state.replaying = False
                self._log(f"回放完成：共发送 {sent} 条"
                          + (f"（预期 {self.expected} 条）" if self.expected else ""))
        else:
            self._stall = 0
        self.state.replay_sent = sent
        return sent

    # ---------------- 单条发送 ----------------
    def send_struct(self, kind: str, **fields) -> tuple[int, int, int]:
        """结构化赋值发送；返回 (service, event, 载荷字节数)。"""
        lib = self._require_lib()
        if self._handle is None:
            raise RuntimeError("请先 open()")
        if kind not in KIND_SERVICE_EVENT:
            raise ValueError(f"不支持的类型：{kind}（可选：{', '.join(STRUCT_TYPES)}）")
        payload = lib.serialize(self._handle, kind, dict(fields))
        service, event = KIND_SERVICE_EVENT[kind]
        rc = lib.notify_raw(self._handle, service, event, payload)
        if rc != 0:
            raise RuntimeError(f"发送失败 rc={rc}（该事件可能未注册或未启动）")
        ev = find_event(service, event)
        self._log(f"已发送 {kind} → 0x{service:04X}:0x{event:04X}"
                  f"{'（' + ev.name + '）' if ev else ''}，{len(payload)} 字节")
        return service, event, len(payload)

    def send_raw(self, service: int, event: int, data: bytes) -> int:
        """按原始字节发送；返回载荷长度。"""
        lib = self._require_lib()
        if self._handle is None:
            raise RuntimeError("请先 open()")
        rc = lib.notify_raw(self._handle, service, event, data)
        if rc != 0:
            raise RuntimeError(f"发送失败 rc={rc}")
        self._log(f"已发送原始载荷 → 0x{service:04X}:0x{event:04X}，{len(data)} 字节")
        return len(data)

    # ---------------- 摘要 ----------------
    def summary(self) -> str:
        """界面状态栏文本。"""
        st = self.state
        lib = "库就绪" if st.library_ok else "库不可用"
        sess = "已启动" if st.started else ("已打开" if st.opened else "未打开")
        rp = f"回放中（已发 {st.replay_sent}）" if st.replaying else "未回放"
        return (f"{lib}｜{sess}｜{rp}｜已注册 {st.registered_services} 服务/"
                f"{st.registered_events} 事件")
