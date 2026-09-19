# -*- coding: utf-8 -*-
"""can_data_tools.di_case_runner —— Di 测试用例自动化执行器

把 `di_case_parser` 解析出的用例真正跑起来：

    CAN 信号（报文+位域+值） → 合成帧 → 下发
    SOME/IP 链路型（service/instance/online） → 注册/不注册该服务
    SOME/IP 字段型（hnmap_s.navigation_map 之类） → 结构化发送（能解析到结构体时）
    mem 字段 / Opaque 载荷 → 记为「需台架注入」，不假装支持
    wait_ms → 等画面稳定
    画面校验 → 用 label_verify 判定标贴是否出现（没有参考图时明确记为 unverifiable）

两种运行模式：
    · dry_run=True（默认）—— 只做解析/分类/合成帧，**不碰设备**，用于批量体检用例集；
    · dry_run=False        —— 真下发（需已初始化的 CAN 设备；SOME/IP 需回放库可用）。

所有外部依赖都可注入（`can_sender` / `someip_controller` / `frame_provider` / `verifier`），
因此本模块可在没有设备的 CI 里用假实现完整回归。
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

from hudcore import logging_setup

from . import can_bit_writer as bitw
from . import di_case_parser as parser
from .label_verify import LabelVerifier, LabelVerifierError
from .someip_field_map import resolve as resolve_someip_key

LOGGER_NAME = "di_case"

# 用例执行结论
STATUS_PASS = "pass"                     # 输入下发完成且画面校验通过
STATUS_FAIL = "fail"                     # 画面校验不通过
STATUS_INPUTS_OK = "inputs-ok"           # 输入下发完成，但画面无法校验（无参考图/无画面）
STATUS_SKIPPED = "skipped"               # 没有可下发输入（需台架注入）
STATUS_ERROR = "error"                   # 执行期间出错
STATUS_DRY_RUN = "dry-run"               # 仅解析与合成，未下发


# --------------------------------------------------------------------------- 结果结构
@dataclass
class CaseResult:
    scenario_id: str
    status: str
    support: str = ""
    sent_can: tuple[str, ...] = ()
    sent_someip: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()
    frame_status: str = "not_attempted"
    elapsed_ms: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (STATUS_PASS, STATUS_INPUTS_OK, STATUS_DRY_RUN)

    def describe(self) -> str:
        extra = f"｜{self.detail}" if self.detail else ""
        return (f"{self.scenario_id:38s} {self.status:10s} 支持度={self.support or '-':8s}"
                f" CAN={len(self.sent_can)} SOME/IP={len(self.sent_someip)}"
                f" 画面={self.frame_status}{extra}")


@dataclass
class RunReport:
    mode: str
    results: list[CaseResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    case_dir: str = ""

    # ---- 统计 ----
    @property
    def summary(self) -> dict:
        status: dict[str, int] = {}
        frames: dict[str, int] = {}
        for r in self.results:
            status[r.status] = status.get(r.status, 0) + 1
            frames[r.frame_status] = frames.get(r.frame_status, 0) + 1
        return {"cases": len(self.results), "status": status, "frame_status": frames,
                "sent_can_total": sum(len(r.sent_can) for r in self.results),
                "sent_someip_total": sum(len(r.sent_someip) for r in self.results),
                "unsupported_total": sum(len(r.unsupported) for r in self.results)}

    def describe(self, limit: int = 12) -> str:
        s = self.summary
        lines = [f"=== Di 用例执行报告（{self.mode}）===",
                 f"用例 {s['cases']} 个｜结论 {s['status']}",
                 f"下发 CAN {s['sent_can_total']} 条、SOME/IP {s['sent_someip_total']} 项；"
                 f"需台架注入 {s['unsupported_total']} 项",
                 f"画面校验 {s['frame_status']}"]
        shown = [r for r in self.results if r.status in (STATUS_FAIL, STATUS_ERROR)]
        shown += [r for r in self.results if r.status not in (STATUS_FAIL, STATUS_ERROR)]
        for r in shown[:limit]:
            lines.append("  " + r.describe())
        if len(shown) > limit:
            lines.append(f"  …（其余 {len(shown) - limit} 条省略，详见 JSON 报告）")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"mode": self.mode, "started_at": self.started_at, "finished_at": self.finished_at,
                "case_dir": self.case_dir, "summary": self.summary,
                "results": [asdict(r) for r in self.results]}

    def dump(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return p


# --------------------------------------------------------------------------- 门控默认位
GATE_CONFIG = Path("data") / "DI_Config" / "gate_frame.json"


def load_gate_defaults(path: str | Path | None = None) -> dict[int, dict]:
    """读取"门控帧默认位"：`{CAN ID: {位域: 值}}`（键按 base=0 的位域写法）。

    用途：Di 用例里有 403 条报文只写了"门控信号有效"却没给位域（无法编码）。
    若已从 CAN 矩阵确认这些门控位，写进 `data/DI_Config/gate_frame.json` 即可让执行器套用；
    留空则这些报文会被如实记为"无法编码"，不会被当成已下发。
    """
    config_path = Path(path) if path else paths_project_root() / GATE_CONFIG
    if not config_path.is_file():
        return {}
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logging_setup.error(LOGGER_NAME, f"门控配置解析失败：{config_path}（{exc}）")
        return {}
    defaults: dict[int, dict] = {}
    for key, bits in (raw.get("defaults") or {}).items():
        try:
            can_id = int(str(key), 0)
        except ValueError:
            logging_setup.warning(LOGGER_NAME, f"门控配置里 CAN ID 非法，已跳过：{key!r}")
            continue
        if isinstance(bits, dict) and bits:
            defaults[can_id] = {str(k): int(v) for k, v in bits.items()}
    if defaults:
        logging_setup.info(LOGGER_NAME, f"已载入门控默认位：{len(defaults)} 个报文")
    return defaults


def paths_project_root() -> Path:
    from hudcore.platform.paths import paths
    return paths.project_root


# --------------------------------------------------------------------------- 默认实现
class DeviceCanSender:
    """默认 CAN 下发：用项目现有的 `can_core.device.Send_Can_Or_Canfd()`。

    需要设备已由 `Initialize_Canfd_Device()` 初始化（`can_core.state.chn_handles` 之类由调用方给）。
    """

    def __init__(self, chn_handle, msg_type: str = "canfd", on_log: Callable[[str], None] | None = None):
        self.chn_handle = chn_handle
        self.msg_type = msg_type
        self._log = on_log or (lambda m: logging_setup.info(LOGGER_NAME, m))

    def __call__(self, can_id: int, data: list[int], extended: bool) -> int:
        from can_core import device
        sent = device.Send_Can_Or_Canfd(self.chn_handle, 1 if extended else 0, can_id,
                                        self.msg_type, data)
        self._log(f"CAN 下发 0x{can_id:X}（{'扩展' if extended else '标准'}帧，"
                  f"{self.msg_type}）data={[f'{b:02X}' for b in data]} → 返回 {sent}")
        return int(sent or 0)


class SomeipReplayController:
    """默认 SOME/IP 实现：链路型 = 注册/不注册服务；字段型 = 结构化发送。

    注意：会真正打开 vsomeip 服务端（现场环境才应使用；容器/CI 里请注入假实现）。
    """

    def __init__(self, unicast: str | None = None,
                 on_log: Callable[[str], None] | None = None) -> None:
        from someip_core import ReplayController
        self._log = on_log or (lambda m: logging_setup.info(LOGGER_NAME, m))
        self._ctl = ReplayController(on_log=self._log)
        self._unicast = unicast
        self._opened = False
        self._links: dict[str, str] = {}          # 用例声明的服务在线状态

    # ---- 链路型 ----
    def apply_links(self, links: Sequence[parser.SomeipLink]) -> tuple[str, ...]:
        """按用例声明准备服务注册（online=0 的服务不注册）。"""
        online: list[str] = []
        for link in links:
            key = f"{link.service_id}:{link.instance_id}"
            self._links[key] = "on" if link.online else "off"
            if link.online:
                online.append(link.service_id)
            self._log(f"SOME/IP 链路 {key} → {'在线' if link.online else '离线'}")
        if not self._opened:
            self._ctl.open(unicast=self._unicast)
            self._opened = True
        n_svc, n_evt = self._ctl.register(selected_services=online or None)
        self._ctl.start()
        self._log(f"已注册 {n_svc} 个服务 / {n_evt} 个事件（在线服务 {online or '全部'}）")
        return tuple(f"{k}={v}" for k, v in self._links.items())

    # ---- 字段型 ----
    def send_field(self, kind: str, field_name: str, value) -> int:
        _svc, _evt, size = self._ctl.send_struct(kind, **{field_name: value})
        self._log(f"SOME/IP 字段下发 {kind}.{field_name}={value} → {size} 字节")
        return int(size)

    def close(self) -> None:
        if self._opened:
            try:
                self._ctl.stop()
                self._ctl.close()
            finally:
                self._opened = False


# --------------------------------------------------------------------------- 执行器
class DiCaseRunner:
    """Di 用例执行器（可注入全部外部依赖，便于无设备回归）。"""

    def __init__(self, *, can_sender: Callable[[int, list[int], bool], int] | None = None,
                 someip_controller=None,
                 frame_provider: Callable[[], object] | None = None,
                 verifier: LabelVerifier | None = None,
                 dry_run: bool = True, wait_scale: float = 1.0,
                 gate_defaults: dict[int, dict] | None = None,
                 on_log: Callable[[str], None] | None = None) -> None:
        self.can_sender = can_sender
        self.someip_controller = someip_controller
        self.frame_provider = frame_provider
        self.verifier = verifier
        self.dry_run = dry_run
        self.wait_scale = float(wait_scale)
        # 门控默认位：{} 表示未配置（此时"只有门控说明"的报文会记为无法编码）
        self.gate_defaults = load_gate_defaults() if gate_defaults is None else dict(gate_defaults)
        self._log = on_log or (lambda m: logging_setup.info(LOGGER_NAME, m))

    # ---- 单条用例 ----
    def run_case(self, case: parser.DiCase) -> CaseResult:
        started = time.time()
        support = parser.classify(case, gate_ids=self.gate_defaults)
        gate_only = [i for i in parser.gate_only_ids(case) if i not in self.gate_defaults]
        sent_can: list[str] = []
        sent_someip: list[str] = []
        unsupported: list[str] = []

        # 需要台架注入的部分：如实记录，不假装支持
        unsupported += [f"mem.{m.field}={m.value}" for m in case.mem]
        unsupported += [f"CAN 0x{i:X} 仅门控说明、无位域（可在 data/DI_Config/gate_frame.json 补默认位）"
                        for i in gate_only]
        for f in case.someip_fields:
            target = resolve_someip_key(f.key)
            if not target.supported:
                unsupported.append(f"SOME/IP {f.key}：{target.reason}")

        try:
            # ① CAN：同 ID 的信号合成一帧
            for can_id, signals in sorted(bitw.group_by_can_id(case.can).items()):
                data = bitw.build_frame(signals, gate_defaults=self.gate_defaults.get(can_id))
                label = (f"0x{can_id:X} ← " +
                         "；".join(f"{s.bit_range or '整帧'}={s.value}" for s in signals))
                if self.dry_run:
                    sent_can.append(label)
                    continue
                if self.can_sender is None:
                    raise RuntimeError("未提供 CAN 下发实现（can_sender），无法执行")
                self.can_sender(can_id, data, any(s.is_extended for s in signals))
                sent_can.append(label)

            # ② SOME/IP：链路型 + 字段型
            if case.someip_links or case.someip_fields:
                for link in case.someip_links:
                    sent_someip.append(link.describe())
                if not self.dry_run:
                    if self.someip_controller is None:
                        raise RuntimeError("未提供 SOME/IP 实现（someip_controller），无法执行")
                    if case.someip_links:
                        self.someip_controller.apply_links(case.someip_links)
                    for f in case.someip_fields:
                        target = resolve_someip_key(f.key)
                        if target.supported:
                            self.someip_controller.send_field(target.kind, target.field, f.value)
                for f in case.someip_fields:
                    target = resolve_someip_key(f.key)
                    sent_someip.append(f"{f.key}={f.value}" +
                                       (f"→{target.kind}.{target.field}" if target.supported
                                        else "（不可下发）"))

            # ③ 等待画面稳定 + ④ 画面校验
            frame_status, detail = self._settle_and_verify(case)

            if self.dry_run:
                status = STATUS_DRY_RUN
            elif not (case.can or case.someip_links or
                      any(resolve_someip_key(f.key).supported for f in case.someip_fields)):
                status = STATUS_SKIPPED
            elif frame_status == "fail":
                status = STATUS_FAIL
            elif frame_status == "pass":
                status = STATUS_PASS
            else:
                status = STATUS_INPUTS_OK
        except Exception as exc:                       # noqa: BLE001 - 单条用例失败不该中断整批
            logging_setup.error(LOGGER_NAME, f"{case.scenario_id} 执行出错：{exc}")
            return CaseResult(case.scenario_id, STATUS_ERROR, support.level,
                              tuple(sent_can), tuple(sent_someip), tuple(unsupported),
                              "error", int((time.time() - started) * 1000), str(exc))

        return CaseResult(case.scenario_id, status, support.level, tuple(sent_can),
                          tuple(sent_someip), tuple(unsupported), frame_status,
                          int((time.time() - started) * 1000), detail)

    def _settle_and_verify(self, case: parser.DiCase) -> tuple[str, str]:
        """等到画面稳定后校验标贴；返回 (frame_status, detail)。"""
        expected = case.expected
        if not expected.expect_visible and not expected.negative_label:
            return "not_attempted", "用例未声明标贴"
        if self.dry_run:
            return "not_attempted", "dry-run 不下发也不取画面"
        if not (self.frame_provider or self.verifier):
            return "unverifiable", "未提供画面来源（frame_provider）与校验器"

        if case.wait_ms > 0:
            time.sleep(max(0.0, case.wait_ms / 1000.0 * self.wait_scale))

        frame = self.frame_provider() if self.frame_provider else None
        verifier = self.verifier
        if verifier is None:
            try:
                verifier = LabelVerifier()
            except LabelVerifierError as exc:
                return "unverifiable", f"校验器不可用：{exc}"
        try:
            verdict = verifier.verify_frame(frame, expected)
        except LabelVerifierError as exc:
            return "unverifiable", f"校验失败：{exc}"
        detail = verdict.describe().replace("\n", " ")
        return verdict.status, detail

    # ---- 批量 ----
    def run_cases(self, cases: Iterable[parser.DiCase], *, limit: int | None = None,
                  only: str | None = None, only_auto: bool = False) -> RunReport:
        """批量执行。

        :param only: 只跑 scenario_id 含该子串的用例
        :param only_auto: 只跑"输入可全部下发"的用例（`Support.level == "auto"`）
        """
        selected = list(cases)
        if only:
            selected = [c for c in selected if only in c.scenario_id]
        if only_auto:
            selected = [c for c in selected
                        if parser.classify(c, gate_ids=self.gate_defaults).level == "auto"]
        if limit is not None:
            selected = selected[:limit]

        report = RunReport(mode="dry-run" if self.dry_run else "execute",
                           case_dir=str(selected[0].path.parent) if selected and selected[0].path else "")
        report.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
        for case in selected:
            result = self.run_case(case)
            report.results.append(result)
            self._log(result.describe())
        report.finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
        return report


__all__ = ["DiCaseRunner", "CaseResult", "RunReport", "DeviceCanSender",
           "SomeipReplayController", "load_gate_defaults", "GATE_CONFIG",
           "STATUS_PASS", "STATUS_FAIL", "STATUS_INPUTS_OK", "STATUS_SKIPPED",
           "STATUS_ERROR", "STATUS_DRY_RUN"]
