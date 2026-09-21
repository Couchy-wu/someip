# -*- coding: utf-8 -*-
"""tests/test_verify_report.py —— 验证报告生成器单测（tools.verify_report）

报告是入库产物（`docker/windows-sim/verify_report.md/json`），所以渲染逻辑必须可测：
  · Markdown 安全：`|`/换行/控制字符会破坏表格 → 必须转义与折叠，超长截断并指向 JSON；
  · 统计口径：通过/失败/跳过/通过率/总耗时/判定；
  · 回归对比：新增失败 / 已修复 / 持续失败 / 新增项 / 消失项；
  · 报告结构：结论先行、环境块、失败与跳过清单、逐项表含耗时；
  · JSON 结构：schema、summary、failures、skips、diff、results（证据保留全文）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_report import (
    CELL_LIMIT, Item, ReportMeta, collect_environment, diff_runs, load_previous, md_cell,
    render_json, render_markdown, summarize, write_reports,
)


def _items():
    return [
        Item(name="1. 环境", status="PASS", detail="ok", duration_s=0.4, index=1),
        Item(name="2. 导入", status="PASS", detail="72/72", duration_s=3.2, index=2),
        Item(name="3. 驱动", status="FAIL", detail="缺少 libzlgcan.so", duration_s=1.1, index=3),
        Item(name="4. GPU", status="SKIP", detail="容器内无 GPU", duration_s=0.0, index=4),
    ]


# --------------------------------------------------------------------------- Markdown 安全
def test_md_cell_escapes_pipes_and_newlines():
    """证据里的 `|` 与换行必须被处理，否则整张表会错列/断行。"""
    cell = md_cell("a|b\nc\r\nd\te")
    assert "\\|" in cell and "|" not in cell.replace("\\|", "")
    assert "\n" not in cell and "\r" not in cell and "\t" not in cell
    assert "a\\|b c d e" == cell


def test_md_cell_truncates_long_detail_and_points_to_json():
    long_text = "x" * (CELL_LIMIT + 50)
    cell = md_cell(long_text)
    assert len(cell) <= CELL_LIMIT
    assert cell.endswith("…（截断，全文见 JSON）")


def test_md_cell_handles_none_and_empty():
    assert md_cell("") == ""
    assert md_cell(None) == ""
    assert md_cell("  ") == ""


# --------------------------------------------------------------------------- 统计
def test_summarize_counts_and_verdict():
    stats = summarize(_items())
    assert (stats["total"], stats["passed"], stats["failed"], stats["skipped"]) == (4, 2, 1, 1)
    assert stats["verdict"] == "FAIL"
    assert stats["pass_rate"] == 50.0
    assert stats["duration_s"] == 4.7


def test_summarize_all_pass_is_pass_verdict():
    items = [Item(name="a", status="PASS", index=1), Item(name="b", status="SKIP", index=2)]
    stats = summarize(items)
    assert stats["verdict"] == "PASS", "跳过不算失败"
    assert stats["pass_rate"] == 50.0


# --------------------------------------------------------------------------- 回归对比
def _previous_json(items=None, at="2026-01-01 00:00:00"):
    items = items if items is not None else _items()
    return {"generated_at": at, "summary": {"verdict": "FAIL"},
            "results": [{"name": i.name, "status": i.status} for i in items]}


def test_diff_detects_regression_fix_and_new_items():
    previous = _previous_json([
        Item(name="1. 环境", status="PASS", index=1),
        Item(name="2. 导入", status="FAIL", index=2),      # 上次失败 → 本次通过 = 已修复
        Item(name="3. 驱动", status="PASS", index=3),      # 上次通过 → 本次失败 = 新增失败
        Item(name="9. 旧项", status="PASS", index=4),      # 本次没有 = 消失
    ])
    diff = diff_runs(previous, _items())
    assert diff["available"] is True
    assert diff["regressions"] == ["3. 驱动"]
    assert diff["fixed"] == ["2. 导入"]
    assert diff["still_failing"] == []
    assert diff["added"] == ["4. GPU"]
    assert diff["removed"] == ["9. 旧项"]
    assert diff["previous_at"] == "2026-01-01 00:00:00"


def test_diff_reports_still_failing():
    previous = _previous_json([Item(name="3. 驱动", status="FAIL", index=1)])
    diff = diff_runs(previous, _items())
    assert diff["still_failing"] == ["3. 驱动"]
    assert diff["regressions"] == []


def test_diff_without_previous_is_unavailable():
    assert diff_runs(None, _items()) == {"available": False}
    assert diff_runs({"results": []}, _items()) == {"available": False}


# --------------------------------------------------------------------------- 渲染
def _meta():
    return ReportMeta(label="Ubuntu 22.04（容器内）", command="python verify_windows.py",
                      environment={"平台": "Linux-6.1", "Python": "3.13.15",
                                   "CAN 驱动": "libusbcanfd.so|vci"},
                      generated_at="2026-02-01 10:00:00",
                      notes=["容器内无法验证真实硬件"])


def test_render_markdown_has_sections_and_escaped_cells():
    text = render_markdown(_meta(), _items(), _previous_json())
    assert text.startswith("# HudAutoTest — 环境功能验证报告（Ubuntu 22.04（容器内））")
    for section in ("## 运行环境", "## 失败项", "## 跳过项", "## 与上次运行对比", "## 逐项结果"):
        assert section in text, f"缺少章节：{section}"
    assert "**❌ 结果：2 通过 / 1 失败 / 1 跳过**" in text
    assert "通过率 50.0%" in text and "耗时 4.7s" in text
    assert "| # | 验证项 | 结果 | 耗时(s) | 证据 |" in text
    # 环境块里的管道符必须转义，表格才不会被切列
    assert "libusbcanfd.so\\|vci" in text
    # 失败项清单里能直接看到名称与原因（名称自带序号，清单里不再重复编号）
    assert "**3. 驱动**" in text and "缺少 libzlgcan.so" in text
    assert "**3. 3. 驱动**" not in text
    # 表格每行的列数一致（5 列 → 6 个竖线）
    for line in text.splitlines():
        if line.startswith("| 1 |") or line.startswith("| 3 |"):
            assert line.count("|") == 6, f"列数不一致：{line}"


def test_render_markdown_without_previous_has_no_diff_section():
    text = render_markdown(_meta(), _items(), None)
    assert "## 与上次运行对比" not in text
    assert "## 说明" in text, "notes 应出现在说明章节"


def test_render_markdown_notes_when_no_diff_changes():
    """完全一致（含失败项也一致）时，报告明确写"无变化"而不是留白。"""
    items = [Item(name="1. 环境", status="PASS", index=1),
             Item(name="2. 导入", status="PASS", index=2)]
    text = render_markdown(_meta(), items, _previous_json(items))
    assert "## 与上次运行对比" in text
    assert "无变化（与上次逐项一致）" in text


def test_render_markdown_lists_persistent_failures_not_as_no_change():
    """有持续失败项时，应列出"持续失败"，不能写成"无变化"。"""
    text = render_markdown(_meta(), _items(), _previous_json(_items()))
    assert "持续失败（1）" in text and "`3. 驱动`" in text
    assert "无变化（与上次逐项一致）" not in text


def test_render_json_schema_and_full_detail():
    long_detail = "y" * (CELL_LIMIT + 100)
    items = [Item(name="1. 长证据", status="FAIL", detail=long_detail, duration_s=1.0, index=1)]
    data = render_json(_meta(), items, None)
    assert data["schema"].startswith("hudautotest.verify-report/")
    assert data["generated_at"] == "2026-02-01 10:00:00"
    assert data["environment"]["Python"] == "3.13.15"
    assert data["summary"]["verdict"] == "FAIL"
    assert data["failures"][0]["name"] == "1. 长证据"
    assert data["failures"][0]["detail"] == long_detail, "JSON 必须保留证据全文（不截断）"
    assert data["results"][0]["duration_s"] == 1.0
    assert data["diff"] == {"available": False}


# --------------------------------------------------------------------------- 落盘与读取
def test_write_and_load_previous_roundtrip(tmp_path):
    md_path = tmp_path / "r.md"
    json_path = tmp_path / "r.json"
    write_reports(_meta(), _items(), md_path, json_path)
    assert md_path.is_file() and json_path.is_file()
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["summary"]["total"] == 4
    assert load_previous(json_path)["summary"]["verdict"] == "FAIL", "应能读回上次报告做对比"


def test_write_reports_creates_missing_dirs(tmp_path):
    md_path = tmp_path / "deep" / "dir" / "r.md"
    json_path = tmp_path / "deep" / "dir" / "r.json"
    write_reports(_meta(), _items(), md_path, json_path)
    assert md_path.is_file() and json_path.is_file()


def test_load_previous_handles_missing_and_broken(tmp_path):
    assert load_previous(tmp_path / "nope.json") is None
    broken = tmp_path / "broken.json"
    broken.write_text("{不是 json", encoding="utf-8")
    assert load_previous(broken) is None


# --------------------------------------------------------------------------- 入库报告格式自检
REPORT_MD = Path(__file__).resolve().parents[1] / "docker" / "windows-sim" / "verify_report.md"
REPORT_JSON = REPORT_MD.with_suffix(".json")


@pytest.mark.skipif(not REPORT_MD.is_file(), reason="仓库内还没有验证报告")
def test_committed_report_is_wellformed():
    """入库的验证报告必须格式良好：结论行、章节齐全、表格列数自洽、JSON 可解析。

    这条用例把"报告产物"和"渲染规则"绑在一起：改了渲染却忘记重新生成报告时会失败。
    注意：统计竖线时**必须排除转义后的 `\\|`**，否则证据里的管道符会被误判为多出一列。
    """
    def unescaped_pipes(line: str) -> int:
        return sum(1 for i, ch in enumerate(line) if ch == "|" and (i == 0 or line[i - 1] != "\\"))

    text = REPORT_MD.read_text(encoding="utf-8")
    assert text.startswith("# HudAutoTest — 环境功能验证报告（"), "标题应为自适应环境标签"
    assert "结果：" in text and "通过率" in text and "耗时" in text
    for section in ("## 运行环境", "## 逐项结果"):
        assert section in text, f"缺少章节：{section}"

    body = text.split("## 逐项结果", 1)[1]
    rows = [ln for ln in body.splitlines() if ln.startswith("| ") and "---" not in ln]
    assert rows, "逐项结果表应有内容"
    for line in rows:
        assert unescaped_pipes(line) == 6, f"逐项表列数应为 5 列：{line[:70]}"
    assert len(rows) - 1 == 19, "应有 19 条验证项（表头 + 19 行）"

    env = text.split("## 运行环境", 1)[1].split("## ", 1)[0]
    for line in [ln for ln in env.splitlines() if ln.startswith("| ") and "---" not in ln]:
        assert unescaped_pipes(line) == 3, f"环境表列数应为 2 列：{line[:70]}"

    data = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    assert data["schema"].startswith("hudautotest.verify-report/")
    assert data["summary"]["total"] == len(data["results"]) == 19
    assert all("duration_s" in r for r in data["results"])
    assert data["environment"] and "Python" in data["environment"]


# --------------------------------------------------------------------------- 环境收集
def test_collect_environment_has_expected_keys():
    env = collect_environment(Path(__file__).resolve().parents[1])
    for key in ("平台", "系统", "Python", "解释器", "项目根", "CAN 驱动", "SOME/IP 库"):
        assert key in env, f"环境块缺少 {key}"
    assert env["Python"].startswith("3.")
    assert str(env["项目根"]).startswith("/") or ":" in str(env["项目根"]), \
        "项目根应为绝对路径（容器内是 /work，本机是源码目录）"
