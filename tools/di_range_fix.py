# -*- coding: utf-8 -*-
"""tools.di_range_fix —— Di 用例"值超出位域"问题的修复建议（扫描 → CSV）

用途：`python -m scripts.run_di_cases` 的报告会把"值超出位域范围"的用例判为 `error`
（不截断不掩码）。本工具把这些用例逐条列出来，并给出**最小改动建议**，交给用例作者改：

    信号 0x2FD 位域 4.4-5.0（5 位，上限 31）取值 38 → 建议位域 4.4-5.1（6 位）
    并检查加宽后是否与同用例内其它信号**重叠**（重叠时给出警告，人工确认）

用法（项目根目录执行）：

    python -m tools.di_range_fix                                  # 扫描随仓库分发的用例集
    python -m tools.di_range_fix --out logs/di_range_fix.csv       # 写到指定路径
    python -m tools.di_range_fix --cases <目录或文件> --include-ok  # 连"放得下但贴边"的也列出

输出 CSV 列：`scenario_id, signal_id, sub_id, bit_range, width, value, max_value, needed_bits,
suggested_range, overlap, desc, action`
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from can_data_tools import can_bit_writer as bitw
from can_data_tools import di_case_parser as parser

CSV_COLUMNS = ("scenario_id", "signal_id", "sub_id", "bit_range", "width", "value", "max_value",
               "needed_bits", "suggested_range", "overlap", "desc", "action")


@dataclass(frozen=True)
class RangeIssue:
    """一条"值放不进位域"的记录 + 修复建议。"""

    scenario_id: str
    signal_id: str
    sub_id: str
    bit_range: str
    width: int
    value: int
    max_value: int
    needed_bits: int
    suggested_range: str
    overlap: str
    desc: str
    action: str

    @property
    def fits(self) -> bool:
        """严格说：放得下就不算问题（但贴边的情况用 --include-ok 也会列出供复核）。"""
        return self.value <= self.max_value


def _to_absolute(bit_range: str) -> tuple[int, int]:
    """位域 → `(起始绝对位, 位数)`（绝对位 = 字节号*8 + 位号，与位序无关，仅用于算宽度）。"""
    sb, sbit, _eb, _ebit = bitw.parse_bit_range(bit_range, base=bitw.DI_BASE)
    return sb * 8 + sbit, bitw.bit_length(bit_range, base=bitw.DI_BASE)


def _from_absolute(start_bit: int, width: int) -> str:
    """`(起始绝对位, 位数)` → 位域写法（0 起，如 4.4-5.1）。"""
    end_abs = start_bit + width - 1
    return f"{start_bit // 8}.{start_bit % 8}-{end_abs // 8}.{end_abs % 8}"


def suggest_range(bit_range: str, value: int) -> str:
    """给出"保持起始位不变、刚好放下该取值"的最小位域写法。

    :raises ValueError: 位域非法，或加宽后超出 64 字节 CANFD 帧
    """
    start_abs, _width = _to_absolute(bit_range)
    needed = max(1, int(value).bit_length())
    if start_abs + needed > bitw.MAX_CANFD_BYTES * 8:
        raise ValueError(f"加宽到 {needed} 位会超出 64 字节帧：{bit_range} 值 {value}")
    return _from_absolute(start_abs, needed)


def _overlaps(case, signal, suggested: str) -> str:
    """加宽后是否与同用例内同一报文的其它信号重叠（重叠需人工确认）。"""
    start_abs, width = _to_absolute(suggested)
    new_start, new_end = start_abs, start_abs + width - 1
    hits: list[str] = []
    for other in case.can:
        if other.can_id != signal.can_id or not other.bit_range:
            continue
        if other is signal:
            continue
        other_start, other_width = _to_absolute(other.bit_range)
        other_end = other_start + other_width - 1
        if new_start <= other_end and other_start <= new_end:
            bits = f"{other.bit_range}" + (f"（{other.desc[:24]}）" if other.desc else "")
            hits.append(bits)
    return "；".join(sorted(set(hits))) if hits else ""


def scan_case(case, include_edge: bool = False) -> list[RangeIssue]:
    """扫描单个用例。

    :param include_edge: True 时，"放得下但正好用掉位域最高位"的记录也会列出（供复核）
    """
    issues: list[RangeIssue] = []
    for signal in case.can:
        if not signal.bit_range:
            continue
        try:
            width = bitw.bit_length(signal.bit_range, base=bitw.DI_BASE)
        except bitw.BitRangeError:
            continue                                   # 位域本身非法 → 执行器已单独报错，这里跳过
        max_value = (1 << width) - 1
        needed = max(1, int(signal.value).bit_length())
        if int(signal.value) <= max_value:
            if not (include_edge and int(signal.value) == max_value and width > 0):
                continue
            issues.append(RangeIssue(
                scenario_id=case.scenario_id, signal_id=signal.signal_id, sub_id=signal.sub_id,
                bit_range=signal.bit_range, width=width, value=int(signal.value),
                max_value=max_value, needed_bits=needed, suggested_range="",
                overlap="", desc=(signal.desc or "")[:120],
                action="取值恰为位域上限（贴边），建议复核是否需要留余量或信号位宽是否更宽"))
            continue
        try:
            suggested = suggest_range(signal.bit_range, signal.value)
            action = (f"位域加宽到 {suggested}（{needed} 位）"
                      + ("；⚠ 与同报文其它信号重叠，需确认" if _overlaps(case, signal, suggested) else ""))
        except ValueError as exc:
            suggested, action = "", f"无法自动建议：{exc}"
        issues.append(RangeIssue(
            scenario_id=case.scenario_id, signal_id=signal.signal_id, sub_id=signal.sub_id,
            bit_range=signal.bit_range, width=width, value=int(signal.value),
            max_value=max_value, needed_bits=needed, suggested_range=suggested,
            overlap=_overlaps(case, signal, suggested) if suggested else "",
            desc=(signal.desc or "")[:120], action=action))
    return issues


def scan_cases(cases, include_edge: bool = False) -> list[RangeIssue]:
    """扫描一批用例（按 scenario_id 排序）。"""
    issues: list[RangeIssue] = []
    for case in cases:
        issues.extend(scan_case(case, include_edge=include_edge))
    return sorted(issues, key=lambda i: (i.scenario_id, i.signal_id, i.bit_range))


def render_markdown(issues, cases_count: int = 0, case_dir: str = "",
                    command: str = "") -> str:
    """把扫描结果渲染成「给用例作者的一页说明」（结论 + 汇总表 + 逐条 + 验证方法）。"""
    from tools.verify_report import md_cell

    bad = [i for i in issues if not i.fits]
    cases_hit = len({i.scenario_id for i in bad})
    out: list[str] = ["# Di 用例位域问题说明（给用例作者）", "",
                      f"**结论**：扫描 {cases_count or '?'} 个用例，发现 **{cases_hit} 个用例 / "
                      f"{len(bad)} 条记录**的取值**超出其声明位域**。执行器对这种用例判 `error`，"
                      f"**不会截断或掩码**（避免把数据问题伪装成通过），因此这些用例当前跑不出正确画面。", ""]
    if command:
        out.append(f"- 复现命令: `{command}`")
    if case_dir:
        out.append(f"- 用例目录: `{case_dir}`")
    out += ["", "## 汇总", "",
            "| 用例 | 信号 | 现位域 | 位数 | 上限 | 取值 | 建议位域 | 是否重叠 |",
            "|------|------|--------|------|------|------|----------|----------|"]
    for i in bad:
        out.append(f"| {md_cell(i.scenario_id, 60)} | {i.signal_id} | `{i.bit_range}` | {i.width} | "
                   f"{i.max_value} | {i.value} | `{i.suggested_range or '-'}` | "
                   f"{'⚠ 是' if i.overlap else '否'} |")
    out += ["", "## 逐条明细", ""]
    for i in bad:
        out += [f"### {i.scenario_id} — {i.signal_id} `{i.bit_range}`", "",
                f"- 取值 `{i.value}`（需要 {i.needed_bits} 位；现位域 {i.width} 位，上限 {i.max_value}）",
                f"- 原始说明：{md_cell(i.desc or '（无）', 300)}",
                f"- 建议动作：{i.action}"]
        if i.overlap:
            out.append(f"- ⚠ 加宽后与同报文信号重叠：`{i.overlap}` —— 需确认位域划分，不能只看宽度")
        out.append("")
    out += ["## 改完怎么验证", "",
            "1. 改用例位域后跑一次体检：`python -m scripts.run_di_cases --report logs/di_run.json`；",
            "2. 报告的「失败与错误」里应不再出现「值超出位域范围（用例与位域定义矛盾）」；",
            "3. 本工具复查：`python -m tools.di_range_fix`（应输出 0 条）；",
            "4. 单测含一致性断言：`python -m pytest tests/test_di_range_fix.py -q`。",
            ""]
    return "\n".join(out).rstrip() + "\n"


def write_markdown(issues, path: str | Path, cases_count: int = 0, case_dir: str = "",
                   command: str = "") -> Path:
    """写一页说明 Markdown。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_markdown(issues, cases_count, case_dir, command),
                 encoding="utf-8")
    return p


def write_csv(issues, path: str | Path) -> Path:
    """写 CSV（UTF-8 with BOM，Excel 直接打开不乱码）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for issue in issues:
            writer.writerow({k: v for k, v in asdict(issue).items() if k in CSV_COLUMNS})
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Di 用例：值超出位域的修复建议（扫描 → CSV）")
    ap.add_argument("--cases", default=str(parser.DEFAULT_CASE_DIR),
                    help="用例目录或单个文件（默认 TestcaseCollection/Di_testcases）")
    ap.add_argument("--out", default="logs/di_range_fix.csv", help="CSV 输出路径")
    ap.add_argument("--md", default=None,
                    help="同时写一份「给用例作者的一页说明」Markdown"
                         "（建议 logs/di_range_issues.md）")
    ap.add_argument("--include-ok", action="store_true",
                    help="连「放得下但贴边（用掉位域最高位）」的记录也列出")
    args = ap.parse_args(argv)

    cases = parser.load_cases(args.cases)
    if not cases:
        print(f"[错误] 未从 {args.cases} 解析出任何用例")
        return 2
    issues = scan_cases(cases, include_edge=args.include_ok)
    path = write_csv(issues, args.out)
    print(f"扫描用例 {len(cases)} 个｜发现『值超出位域』{sum(1 for i in issues if not i.fits)} 条")
    for issue in issues[:10]:
        print(f"  {issue.scenario_id} {issue.signal_id} {issue.bit_range}（{issue.width} 位，上限 "
              f"{issue.max_value}）取值 {issue.value} → {issue.action}")
    if len(issues) > 10:
        print(f"  …（其余 {len(issues) - 10} 条见 CSV）")
    print(f"修复建议已写入：{path}")
    if args.md:
        md = write_markdown(issues, args.md, cases_count=len(cases), case_dir=str(args.cases),
                            command="python -m tools.di_range_fix --md " + str(args.md))
        print(f"一页说明已写入：{md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
