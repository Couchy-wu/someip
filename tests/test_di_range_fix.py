# -*- coding: utf-8 -*-
"""tests/test_di_range_fix.py —— "值超出位域"修复建议工具单测（tools.di_range_fix）

报告的 `error` 只告诉"哪个用例有问题"，本工具给出**最小改动建议**：
  · 位宽与建议位域的计算（保持起始位不变，刚好放下取值）；
  · 加宽后与同报文其它信号是否重叠（重叠必须人工确认，工具只提示不改）；
  · CSV 列与编码（Excel 直接打开不乱码）；
  · 与 Di 执行报告的错误数**互相印证**（同一用例集：7 个用例 / 11 条记录）。
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from can_data_tools import di_case_parser as parser
from tools.di_range_fix import CSV_COLUMNS, scan_case, scan_cases, suggest_range, write_csv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = PROJECT_ROOT / parser.DEFAULT_CASE_DIR

pytestmark = pytest.mark.skipif(not CASE_DIR.is_dir(), reason="未找到 Di 用例目录")


def _case(can_entries, scenario_id="TC-T"):
    return parser.parse_case_obj({
        "scenario_id": scenario_id,
        "input_combination": {"can": can_entries},
        "expected_output": {}, "wait_ms": 0})


# --------------------------------------------------------------------------- 位宽与建议
@pytest.mark.parametrize("bit_range, value, suggested", [
    ("6.0-6.2", 8, "6.0-6.3"),      # 3 位放不下 8（需要 4 位）
    ("6.0-6.2", 9, "6.0-6.3"),
    ("2.0-2.1", 7, "2.0-2.2"),      # 2 位放不下 7（需要 3 位）
    ("4.4-5.0", 38, "4.4-5.1"),     # 5 位放不下 38（需要 6 位，跨到下一字节）
    ("4.4-5.0", 40, "4.4-5.1"),
    ("0.0-0.3", 255, "0.0-0.7"),    # 需要 8 位 → 正好占满首字节
])
def test_suggest_range_keeps_start_bit(bit_range, value, suggested):
    assert suggest_range(bit_range, value) == suggested


def test_suggest_range_rejects_beyond_frame():
    with pytest.raises(ValueError):
        suggest_range("63.7", 1 << 32)          # 加宽会超出 64 字节 CANFD 帧


# --------------------------------------------------------------------------- 扫描
def test_scan_case_reports_only_overflowing_entries():
    case = _case([
        {"signal_id": "0x100", "sub_id": "", "bit_range": "6.0-6.2", "value": 8,
         "desc": "too big"},
        {"signal_id": "0x100", "sub_id": "", "bit_range": "0.0-0.7", "value": 200,
         "desc": "fits"},
        {"signal_id": "0x101", "sub_id": "", "value": 1, "desc": "no bit range"},
    ])
    issues = scan_case(case)
    assert len(issues) == 1
    issue = issues[0]
    assert (issue.signal_id, issue.bit_range, issue.value, issue.max_value) == \
        ("0x100", "6.0-6.2", 8, 7)
    assert issue.suggested_range == "6.0-6.3" and issue.needed_bits == 4
    assert issue.fits is False


def test_scan_case_detects_overlap_with_neighbour_signal():
    """加宽后与同报文其它信号重叠时必须提示（避免建议本身越界占用别人的位）。"""
    case = _case([
        {"signal_id": "0x2FD", "sub_id": "", "bit_range": "4.4-5.0", "value": 38, "desc": "pattern"},
        {"signal_id": "0x2FD", "sub_id": "", "bit_range": "5.1", "value": 0, "desc": "flag"},
    ])
    issue = scan_case(case)[0]
    assert issue.suggested_range == "4.4-5.1"
    assert "5.1" in issue.overlap and "重叠" in issue.action


def test_scan_case_skips_illegal_bit_range():
    """位域本身非法（执行器会单独报"位域写法非法"）时不重复计入本工具。"""
    case = _case([{"signal_id": "0x100", "sub_id": "", "bit_range": "9.0-9.1", "value": 3}])
    assert scan_case(case) == []


def test_scan_case_include_edge_lists_top_bit_values():
    """--include-ok：取值恰好用满位域最高位时也列出，供复核是否留余量。"""
    case = _case([{"signal_id": "0x100", "sub_id": "", "bit_range": "0.0-0.2", "value": 7}])
    assert scan_case(case) == []
    edge = scan_case(case, include_edge=True)
    assert len(edge) == 1 and "贴边" in edge[0].action


def test_scan_real_corpus_matches_report_error_count():
    """与 Di 执行报告互相印证：同一用例集应为 7 个用例、11 条超范围记录。

    报告侧（`RunReport.summary["error_breakdown"]`）按**用例**计数，本工具按**条目**计数，
    因为个别用例里同一信号（如 0x2FD 的 sub_id 0x01 与空子 ID）重复出现。
    """
    cases = parser.load_cases(CASE_DIR)
    issues = scan_cases(cases)
    assert len({i.scenario_id for i in issues}) == 7, "报告里也是 7 个 error 用例"
    assert len(issues) == 11, "个别用例同一信号出现两次，故条目数为 11"
    assert {i.signal_id for i in issues} == {"0x29C", "0x1B6", "0x2FD"}
    assert all(i.suggested_range for i in issues), "每条都应给出建议位域"


def test_write_csv_columns_and_bom(tmp_path):
    issues = scan_cases(parser.load_cases(CASE_DIR))[:3]
    path = write_csv(issues, tmp_path / "fix.csv")
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "应带 UTF-8 BOM，Excel 打开不乱码"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    assert list(rows[0]) == list(CSV_COLUMNS)
    assert len(rows) == 3
    assert rows[0]["suggested_range"] and rows[0]["action"]


def test_write_csv_creates_missing_dirs(tmp_path):
    path = write_csv([], tmp_path / "deep" / "fix.csv")
    assert path.is_file()
    assert path.read_text(encoding="utf-8-sig").strip().startswith("scenario_id")
