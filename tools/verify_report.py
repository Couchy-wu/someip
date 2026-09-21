# -*- coding: utf-8 -*-
"""tools.verify_report —— 功能验证报告生成（Markdown + JSON）

被 `docker/windows-sim/verify_windows.py`（Linux / Windows 两套套件共用）调用，
把"逐项验证结果"渲染成人类可读的 Markdown 与机器可读的 JSON。

设计要点（都是上一版报告的痛点）：
  1. **平台/标签自适应**：同一套脚本在 Ubuntu 与 Windows(Wine) 上都跑，报告标题与环境块
     必须按实际运行环境写，而不是固定"Windows 验证报告"；
  2. **耗时与判定**：每项记录耗时，报告给出总耗时、通过率、失败/跳过清单（原因）；
  3. **Markdown 安全**：证据里的 `|`、换行、控制字符会破坏表格 —— 统一转义与折叠，
     超长证据截断并指向 JSON（JSON 里保留全文）；
  4. **新旧对比**：上一次的 JSON 存在时，报告给出"新增失败/已修复/持续失败"等回归差异；
  5. **零依赖、纯函数**：渲染部分不碰 IO/时间/平台，便于单测（时间与环境由调用方注入）。

调用方（verify_windows.py）负责：逐项执行 → `Item(...)` → `write_reports(...)`。
"""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

SCHEMA = "hudautotest.verify-report/2"
STATUSES = ("PASS", "FAIL", "SKIP")
STATUS_ICON = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}

# Markdown 单元格里的证据长度上限（超过则截断并在 JSON 中保留全文）
CELL_LIMIT = 400


# ---------------------------------------------------------------- 数据结构
@dataclass
class Item:
    """一条验证项的结果。"""

    name: str
    status: str
    detail: str = ""
    duration_s: float = 0.0
    index: int = 0                     # 报告中的序号（1 起）
    reproduce: str = ""                # 复现命令（可选）

    @property
    def ok(self) -> bool:
        return self.status == "PASS"


@dataclass
class ReportMeta:
    """一次运行的元信息（由调用方收集）。"""

    label: str = ""                    # 报告标题后缀，如 "Windows（Wine）"
    title: str = ""                    # 完整标题（留空则按 label 生成）
    command: str = ""                  # 复现本次验证的命令
    environment: dict = field(default_factory=dict)
    generated_at: str = ""
    notes: Sequence[str] = ()          # 额外说明（如"容器内无法验证真实硬件"）


# ---------------------------------------------------------------- 工具
def md_cell(text: str, limit: int = CELL_LIMIT) -> str:
    """把任意文本变成安全的 Markdown 单元格内容。

    · `|` → `\\|`（否则会把表格切列）；
    · 换行/回车/制表 → 空格（否则整张表断行）；
    · 其它控制字符丢弃；
    · 超长截断为 `…（截断，全文见 JSON）`。
    """
    raw = str(text or "")
    cleaned = "".join(ch if ch >= " " or ch == "\t" else " " for ch in raw)
    cleaned = cleaned.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    cleaned = cleaned.replace("|", "\\|")
    while "  " in cleaned:                       # 压掉折叠换行造成的重复空格
        cleaned = cleaned.replace("  ", " ")
    cleaned = cleaned.strip()
    if len(cleaned) > limit:
        suffix = "…（截断，全文见 JSON）"
        keep = max(0, limit - len(suffix))
        cleaned = cleaned[:keep].rstrip() + suffix
    return cleaned


def summarize(items: Sequence[Item]) -> dict:
    """统计：通过/失败/跳过、通过率、总耗时。"""
    passed = sum(1 for i in items if i.status == "PASS")
    failed = sum(1 for i in items if i.status == "FAIL")
    skipped = sum(1 for i in items if i.status == "SKIP")
    total = len(items)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": round(100.0 * passed / total, 1) if total else 0.0,
        "duration_s": round(sum(max(0.0, i.duration_s) for i in items), 2),
        "verdict": "FAIL" if failed else "PASS",
    }


def diff_status_maps(previous: dict, current: dict,
                     failure_statuses: Iterable[str] = ("FAIL",)) -> dict:
    """通用状态对比：`{名称: 状态}` × `{名称: 状态}` → 回归差异（两种报告共用）。

    :param failure_statuses: 视为"失败"的状态集合。验证套件只有 FAIL；
                             Di 用例报告还要算上 ERROR，因此可传入 {"FAIL", "ERROR"}
    :return: regressions（新增失败）/ fixed（已修复）/ still_failing（持续失败）/
             added（本次新增）/ removed（上次有本次没有）
    """
    failures = {str(x).upper() for x in failure_statuses}
    regressions, fixed, still_failing, added = [], [], [], []
    for name, status in current.items():
        old = previous.get(name)
        now_bad = str(status).upper() in failures
        was_bad = str(old).upper() in failures if old is not None else False
        if old is None:
            added.append(name)
        elif now_bad and not was_bad:
            regressions.append(name)
        elif was_bad and not now_bad:
            fixed.append(name)
        elif now_bad and was_bad:
            still_failing.append(name)
    removed = [name for name in previous if name not in current]
    return {"regressions": regressions, "fixed": fixed, "still_failing": still_failing,
            "added": added, "removed": removed}


def diff_section_lines(diff: dict) -> list[str]:
    """把对比结果渲染成 Markdown 列表项（两个报告渲染器共用）。"""
    lines = [f"- 上次运行: `{diff.get('previous_at') or '未知时间'}`"
             f"（判定 {diff.get('previous_verdict') or '未知'}）"]
    if diff.get("legacy_previous"):
        lines.append(f"- 上次报告为旧格式（`{diff.get('previous_schema')}`），"
                     f"仅按「名称 + 状态」对比，不含耗时/环境差异")
    for key, text in (("regressions", "新增失败"), ("fixed", "已修复"),
                      ("still_failing", "持续失败"), ("added", "本次新增"),
                      ("removed", "上次有、本次没有")):
        names = diff.get(key) or []
        if names:
            lines.append(f"- {text}（{len(names)}）：" + "、".join(f"`{n}`" for n in names))
    if not any(diff.get(k) for k in ("regressions", "fixed", "still_failing",
                                    "added", "removed")):
        lines.append("- 无变化（与上次逐项一致）")
    return lines


def diff_runs(previous: dict | None, items: Sequence[Item]) -> dict:
    """与上一次运行对比（按验证项名称匹配）。

    :param previous: 上一次的 JSON 报告（`load_previous()` 的返回值）；None/空 → 无对比
    :return: {"available": bool, "regressions": [...], "fixed": [...], "still_failing": [...],
              "added": [...], "removed": [...], "previous_at": str}
    """
    if not previous or not previous.get("results"):
        return {"available": False}
    prev = {r.get("name"): r.get("status") for r in previous["results"]}
    cur = {i.name: i.status for i in items}
    prev_schema = previous.get("schema", "")
    return {
        "available": True,
        "previous_schema": prev_schema,
        "legacy_previous": bool(prev_schema) and prev_schema != SCHEMA,
        "previous_at": previous.get("generated_at", ""),
        "previous_verdict": (previous.get("summary") or {}).get("verdict", ""),
        **diff_status_maps(prev, cur),
    }


def load_previous(json_path: str | Path) -> dict | None:
    """读取上一次的 JSON 报告；不存在/损坏 → None（不抛异常）。"""
    path = Path(json_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------- 渲染
def _title(meta: ReportMeta) -> str:
    if meta.title:
        return meta.title
    label = meta.label or platform.platform()
    return f"HudAutoTest — 环境功能验证报告（{label}）"


def render_markdown(meta: ReportMeta, items: Sequence[Item],
                    previous: dict | None = None) -> str:
    """渲染 Markdown 报告。"""
    stats = summarize(items)
    diff = diff_runs(previous, items)
    out: list[str] = [f"# {_title(meta)}", ""]

    # ---- 结论先行：评审人第一眼看到判定 ----
    verdict_icon = STATUS_ICON["PASS"] if stats["verdict"] == "PASS" else STATUS_ICON["FAIL"]
    out += [f"**{verdict_icon} 结果：{stats['passed']} 通过 / {stats['failed']} 失败 / "
            f"{stats['skipped']} 跳过**（共 {stats['total']} 项，通过率 "
            f"{stats['pass_rate']}%，耗时 {stats['duration_s']}s）", ""]
    if meta.generated_at:
        out += [f"- 生成时间: `{meta.generated_at}`"]
    if meta.command:
        out += [f"- 复现命令: `{meta.command}`"]
    out += [""]

    # ---- 环境块 ----
    if meta.environment:
        out += ["## 运行环境", "", "| 项 | 值 |", "|----|----|"]
        for key, value in meta.environment.items():
            out.append(f"| {md_cell(key, 40)} | {md_cell(value, CELL_LIMIT)} |")
        out += [""]

    # ---- 失败 / 跳过清单（带原因） ----
    failures = [i for i in items if i.status == "FAIL"]
    skips = [i for i in items if i.status == "SKIP"]
    if failures:
        out += ["## 失败项", ""]
        for i in failures:
            out.append(f"- **{md_cell(i.name, 120)}**：{md_cell(i.detail, 600)}")
        out += [""]
    if skips:
        out += ["## 跳过项", ""]
        for i in skips:
            out.append(f"- {md_cell(i.name, 120)}：{md_cell(i.detail, 300) or '（未说明原因）'}")
        out += [""]

    # ---- 与上次对比 ----
    if diff.get("available"):
        out += ["## 与上次运行对比", "",
                f"- 上次运行: `{diff.get('previous_at') or '未知时间'}`"
                f"（判定 {diff.get('previous_verdict') or '未知'}）"]
        out += diff_section_lines(diff) + [""]

    # ---- 逐项明细 ----
    out += ["## 逐项结果", "",
            "| # | 验证项 | 结果 | 耗时(s) | 证据 |",
            "|---|--------|------|---------|------|"]
    for i in items:
        icon = STATUS_ICON.get(i.status, "")
        out.append(f"| {i.index} | {md_cell(i.name, 80)} | {icon} {i.status} | "
                   f"{i.duration_s:.1f} | {md_cell(i.detail)} |")
    out += [""]

    if meta.notes:
        out += ["## 说明", ""]
        out += [f"- {md_cell(n, 600)}" for n in meta.notes]
        out += [""]
    return "\n".join(out).rstrip() + "\n"


def render_json(meta: ReportMeta, items: Sequence[Item],
                previous: dict | None = None) -> dict:
    """渲染 JSON 报告（证据保留全文，供程序比对）。"""
    stats = summarize(items)
    return {
        "schema": SCHEMA,
        "generated_at": meta.generated_at,
        "label": meta.label,
        "title": _title(meta),
        "command": meta.command,
        "environment": dict(meta.environment),
        "summary": stats,
        "failures": [{"index": i.index, "name": i.name, "detail": i.detail}
                     for i in items if i.status == "FAIL"],
        "skips": [{"index": i.index, "name": i.name, "detail": i.detail}
                  for i in items if i.status == "SKIP"],
        "diff": diff_runs(previous, items),
        "notes": list(meta.notes),
        "results": [{**asdict(i)} for i in items],
    }


# ---------------------------------------------------------------- 入口
def write_reports(meta: ReportMeta, items: Sequence[Item], md_path: str | Path,
                  json_path: str | Path, previous: dict | None = None) -> tuple[Path, Path]:
    """写出 Markdown 与 JSON；返回两个路径。"""
    md = Path(md_path)
    js = Path(json_path)
    md.parent.mkdir(parents=True, exist_ok=True)
    js.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(render_markdown(meta, items, previous), encoding="utf-8")
    js.write_text(json.dumps(render_json(meta, items, previous),
                             ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return md, js


def collect_environment(project_root: Path, extra: dict | None = None) -> dict:
    """收集报告里的环境信息（缺什么就跳过什么，绝不抛异常）。"""
    env: dict = {
        "平台": platform.platform(),
        "系统": f"{platform.system()} {platform.release()}",
        "机器": platform.machine(),
        "Python": sys.version.split()[0],
        "解释器": sys.executable,
        "项目根": str(project_root),
    }
    env.update(_wine_info())
    env.update(_git_info(project_root))
    env.update(_library_info())
    if extra:
        env.update({k: v for k, v in extra.items() if v})
    return env


def _wine_info() -> dict:
    """Wine 容器里补一条明确说明（否则报告的"系统"看着像真 Windows）。"""
    import os
    if not os.environ.get("WINEPREFIX") and "wine" not in platform.platform().lower():
        return {}
    version = ""
    try:
        out = subprocess.run(["wine", "--version"], capture_output=True, text=True, timeout=10)
        version = (out.stdout or out.stderr).strip()
    except Exception:                                  # noqa: BLE001 - 没有 wine 命令也不影响
        version = ""
    return {"运行方式": "Wine 容器内运行 Windows 版 CPython" + (f"（{version}）" if version else "")}


def _git_info(project_root: Path) -> dict:
    """当前提交（便于把报告与代码版本对上）。"""
    try:
        out = subprocess.run(["git", "-C", str(project_root), "log", "-1",
                              "--pretty=%h %s"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return {"提交": out.stdout.strip()}
    except Exception:                                  # noqa: BLE001
        pass
    return {}


def _library_info() -> dict:
    """CAN 驱动与 SOME/IP 库状态（现场最常见的两类环境问题，报告里直接给结论）。"""
    info: dict = {}
    try:
        from can_core import describe_driver_status
        info["CAN 驱动"] = _strip_prefix(describe_driver_status().replace("\n", "；"), "CAN 驱动")
    except Exception as exc:                           # noqa: BLE001
        info["CAN 驱动"] = f"检测跳过（{type(exc).__name__}）"
    try:
        from hudcore.someip import describe_library_status
        info["SOME/IP 库"] = _strip_prefix(describe_library_status().replace("\n", "；"), "SOME/IP 库")
    except Exception as exc:                           # noqa: BLE001
        info["SOME/IP 库"] = f"检测跳过（{type(exc).__name__}）"
    return info


def _strip_prefix(text: str, key: str) -> str:
    """去掉状态文本里与行键重复的前缀（如 "CAN 驱动：xxx" → "xxx"）。"""
    for sep in ("：", ":"):
        prefix = key + sep
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def collect_previous(json_path: str | Path) -> dict | None:
    """读取上一次报告（给"与上次对比"用）。"""
    return load_previous(json_path)


__all__ = [
    "Item", "ReportMeta", "SCHEMA", "STATUS_ICON", "CELL_LIMIT",
    "md_cell", "summarize", "diff_runs", "diff_status_maps", "diff_section_lines",
    "load_previous",
    "render_markdown", "render_json", "write_reports",
    "collect_environment", "collect_previous",
]
