# -*- coding: utf-8 -*-
"""tests/test_di_cases.py —— Di 用例链路单元测试

覆盖三块：
  · `di_case_parser`   解析 497 个真实用例（结构/统计/异常容错/支持度分类）
  · `can_bit_writer`   位域写入（base=1 与项目既有 `extract_bits_from_data` 互逆；base=0 用于 Di）
  · `di_case_runner`   执行器（dry-run / 假发送器验证字节 / 标贴校验 / 报告）
  · `case_format`      格式开关（默认旧格式、可切换、可按内容识别）
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from can_data_tools import can_bit_writer as bitw
from can_data_tools import case_format
from can_data_tools import di_case_parser as parser
from can_data_tools import di_case_runner as runner
from can_data_tools.label_verify import LabelVerifier

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = PROJECT_ROOT / parser.DEFAULT_CASE_DIR

pytestmark = pytest.mark.skipif(not CASE_DIR.is_dir(),
                                reason="未找到 Di 用例目录 TestcaseCollection/Di_testcases")


# =========================================================================== 解析
def test_parse_all_shipped_cases():
    """随仓库分发的 497 个用例都应能解析，且关键统计与实测一致。"""
    cases = parser.load_cases(CASE_DIR)
    assert len(cases) == 497, f"用例数量异常：{len(cases)}"
    stats = parser.summarize(cases)
    assert stats["can_entries"] == 1771
    assert stats["someip_field_entries"] == 73
    assert stats["someip_link_entries"] == 92
    assert stats["mem_entries"] == 482
    assert stats["expect_hidden"] == 185, "185 个用例期望「不显示任何标贴」"
    assert stats["labels"]["(negative-only)"] == 185
    assert set(stats["someip_links"]) == {"0x010A:0x01=on", "0x010A:0x01=off",
                                         "0x000C:0x000C=on", "0x000C:0x000C=off"}


def test_signal_table_and_someip_links_of_one_case():
    """逐字段核对一条典型用例（CAN 位域、SOME/IP 链路、mem、期望输出、wait_ms）。"""
    case = parser.load_case(CASE_DIR / "TC-ACC-ACTIVE-HIGHSPEED.json")
    assert case.scenario_id == "TC-ACC-ACTIVE-HIGHSPEED"
    assert len(case.can) == 7
    speed = next(s for s in case.can if s.bit_range == "1.0-1.7")
    assert speed.can_id == 0x23A and speed.value == 240
    assert speed.is_extended is False and speed.data_length == 2
    assert case.expected.primary_label == "ACC"
    assert case.expected.points == ((540, 259),)
    assert case.expected.location_kind == "point"
    assert case.expected.min_confidence == 0.9
    assert case.wait_ms == 100
    assert case.someip_links == ()


def test_someip_link_and_field_entries_are_split():
    """`service_id/online` 归为链路型；`key/value` 归为字段型。"""
    link_case = parser.load_case(CASE_DIR / "TC-INDUCTION-SHOW.json")
    assert [l.service_id for l in link_case.someip_links] == ["0x010A"]
    assert link_case.someip_links[0].instance_id == "0x01"
    assert link_case.someip_links[0].online == 1
    assert "0x010A" in [l.service_id for l in link_case.someip_links]

    field_case = parser.load_case(CASE_DIR / "TC-ARBLANKET-FUSION-OFF-HIDDEN.json")
    assert [f.key for f in field_case.someip_fields] == ["PlanningLinePointCount"]
    assert field_case.someip_fields[0].value == 12


@pytest.mark.parametrize("location, kind, points", [
    ("640,240", "point", ((640, 240),)),
    ("", "none", ()),
    ("246,82,1131,82", "segment", ((246, 82), (1131, 82))),
    ("246,82,1131,82,665,142", "polyline", ((246, 82), (1131, 82), (665, 142))),
])
def test_location_constraint_forms(location, kind, points):
    """位置约束的四种形态（点/线段/折线/不约束）都要能解析。"""
    expected = parser.ExpectedOutput(location_constraint=location)
    assert expected.points == points
    assert expected.location_kind == kind


def test_tolerates_missing_bit_range_and_sub_id_range_anomaly():
    """样例容错：缺 bit_range 的"整帧在线"信号、以及把位域误写进 sub_id 的个例。"""
    raw = {"scenario_id": "X", "description": "",
           "input_combination": {"can": [
               {"signal_id": "0x4C1", "sub_id": "", "value": 1},                 # 无位域
               {"signal_id": "0x23A", "sub_id": "6.0-6.1", "value": 1},          # 位域写在 sub_id
           ]},
           "expected_output": {"primary_label": "ACC", "negative_label": "",
                               "location_constraint": "1,2", "min_confidence": 0.9},
           "wait_ms": 100}
    case = parser.parse_case_obj(raw)
    missing, patched = case.can
    assert missing.bit_range is None and missing.data_length == 8
    assert patched.bit_range == "6.0-6.1" and patched.sub_id == "", "sub_id 里的位域应被识别"


def test_parse_errors_for_bad_input():
    with pytest.raises(parser.DiCaseParseError):
        parser.parse_case_obj({"description": "缺少 scenario_id"})
    with pytest.raises(parser.DiCaseParseError):
        parser.parse_case_obj({"scenario_id": "X", "input_combination": []})


def test_support_classification_uses_mem_and_gate_frames():
    """支持度分类：全自动 / 含台架注入 / 完全靠台架。"""
    auto = parser.load_case(CASE_DIR / "TC-ACC-ACTIVE-HIGHSPEED.json")
    assert parser.classify(auto).level == "auto", "只含 CAN 位域信号的用例应可全自动"

    with_mem = parser.load_case(CASE_DIR / "TC-AR-EX01.json")
    assert with_mem.mem, "该用例含 mem 内部状态量"
    assert parser.classify(with_mem).level == "partial"
    assert any("mem" in r for r in parser.classify(with_mem).reasons)

    manual = parser.parse_case_obj({
        "scenario_id": "ONLY-MEM", "input_combination": {"can": [], "someip": [],
                                                         "mem": [{"field": "a.b", "value": 1}]},
        "expected_output": {}, "wait_ms": 0})
    assert parser.classify(manual).level == "external"

    gate_only = parser.parse_case_obj({
        "scenario_id": "GATE-ONLY", "input_combination": {
            "can": [{"signal_id": "0x4C1", "sub_id": "", "value": 1}]},
        "expected_output": {}, "wait_ms": 0})
    assert parser.gate_only_ids(gate_only) == (0x4C1,)
    assert parser.classify(gate_only).level == "partial"
    assert parser.classify(gate_only, gate_ids={0x4C1}).level == "auto", \
        "补齐门控默认位后应视为可执行"


# =========================================================================== 位写入
def test_base1_writer_is_inverse_of_project_reader():
    """base=1（旧链路约定）：写入后必须能被项目既有的 extract_bits_from_data 读回。"""
    from can_core.bit_utils import extract_bits_from_data
    for bit_range, value in [("1.0-1.7", 200), ("2.3", 1), ("6.0-6.1", 3),
                             ("1.0-2.7", 0xBEEF), ("8.0-8.7", 255)]:
        data = [0] * 8
        bitw.set_bits_in_data(data, bit_range, value, base=bitw.LEGACY_BASE)
        assert extract_bits_from_data(data, bit_range) == value, f"{bit_range} 读写不一致"


def test_base0_writer_matches_di_notation():
    """base=0（Di 约定）：`"0.0"` 落在 data[0]、`"46.0-46.7"` 落在 data[46]。"""
    data = [0] * 64
    bitw.set_bits_in_data(data, "0.0", 1)
    assert data[0] & 0x01
    bitw.set_bits_in_data(data, "46.0-46.7", 0xA5)
    assert data[46] == 0xA5
    bitw.set_bits_in_data(data, "1.0-1.7", 240)
    assert data[1] == 240 and data[2] == 0, "字节 1 的值不应溢出到字节 2"


def test_base0_equals_base1_with_shifted_bytes():
    """同一物理位：base=0 的 `n.b` 等价于 base=1 的 `n+1.b`（证明两套约定可换算）。"""
    from can_core.bit_utils import extract_bits_from_data
    data = [0] * 16
    bitw.set_bits_in_data(data, "4.2-5.1", 0b101101, base=bitw.DI_BASE)
    assert extract_bits_from_data(data, "5.2-6.1") == 0b101101


@pytest.mark.parametrize("bit_range, value, base", [
    ("0.0-0.2", 8, 0),          # 3 位放不下 8
    ("1.0-1.7", 256, 1),        # 8 位放不下 256
    ("0.0", -1, 0),             # 负值
    ("64.0", 1, 0),             # 超出 64 字节
    ("0.0", 1, 1),              # base=1 时 0 号字节非法（应为 1 起）
    ("3.0-1.0", 1, 0),          # 起止颠倒
])
def test_writer_rejects_invalid_input(bit_range, value, base):
    with pytest.raises((bitw.BitRangeError, ValueError)):
        bitw.set_bits_in_data([0] * 64, bit_range, value, base=base)


def test_build_frame_and_gate_defaults():
    """合成帧：同报文多信号合并 + 门控默认位生效。"""
    case = parser.load_case(CASE_DIR / "TC-ACC-ACTIVE-HIGHSPEED.json")
    frame_23a = bitw.build_frame([s for s in case.can if s.can_id == 0x23A])
    assert len(frame_23a) == 8, "不足 8 字节的报文按 8 字节整帧下发（总线上的常规 DLC）"
    assert frame_23a[1] == 240, "速度值 240 应落在字节 1"
    assert frame_23a[3] & 0x3F, "状态/颜色位应非零"

    gate_only = parser.parse_case_obj({
        "scenario_id": "G", "input_combination": {
            "can": [{"signal_id": "0x4C1", "sub_id": "", "value": 1}]},
        "expected_output": {}, "wait_ms": 0})
    plain = bitw.build_frame(gate_only.can)
    assert plain == [0] * 8, "没有位域时不猜测位，整帧为 0"
    gated = bitw.build_frame(gate_only.can, gate_defaults={"6.2-6.3": 1})
    assert gated[6] & 0x0C, "门控默认位应被写入"


def test_frame_length_handles_large_byte_indices():
    """Di 用例里存在字节号 46 的信号（64 字节 CANFD 帧）→ 长度应为 47。"""
    case = parser.load_case(CASE_DIR / "TC-SWS-EX01.json")
    big = [s for s in case.can if s.bit_range and int(s.bit_range.split(".")[0]) >= 40]
    assert big, "该用例含大字节号信号"
    assert bitw.frame_length([big[0]]) >= 47


# =========================================================================== 执行器
class _FakeSomeip:
    def __init__(self):
        self.links = []
        self.fields = []

    def apply_links(self, links):
        self.links = [(l.service_id, l.instance_id, l.online) for l in links]
        return tuple(f"{a}:{b}={c}" for a, b, c in self.links)

    def send_field(self, kind, field_name, value):
        self.fields.append((kind, field_name, value))
        return 8

    def close(self):
        pass


def test_dry_run_reports_planned_frames_without_touching_device():
    case = parser.load_case(CASE_DIR / "TC-ACC-ACTIVE-HIGHSPEED.json")
    report = runner.DiCaseRunner(dry_run=True).run_cases([case])
    result = report.results[0]
    assert result.status == runner.STATUS_DRY_RUN
    assert len(result.sent_can) == 3, "该用例涉及 0x4C1 / 0x23A / 0x294 三个报文"
    assert result.sent_someip == () and result.frame_status == "not_attempted"
    assert report.summary["status"] == {runner.STATUS_DRY_RUN: 1}


def test_execute_sends_expected_bytes_and_someip_fields(tmp_path):
    """真执行（注入假发送器）：核对下发字节、SOME/IP 字段与链路动作。"""
    sent: list[tuple[int, list[int], bool]] = []
    someip = _FakeSomeip()
    acc = parser.load_case(CASE_DIR / "TC-ACC-ACTIVE-HIGHSPEED.json")
    lane = parser.load_case(CASE_DIR / "TC-LANE-ON.json")          # 含链路型 SOME/IP 输入

    exec_runner = runner.DiCaseRunner(
        can_sender=lambda cid, data, ext: sent.append((cid, data, ext)) or 1,
        someip_controller=someip, dry_run=False, gate_defaults={})
    report = exec_runner.run_cases([acc, lane])

    assert len(report.results) == 2
    assert sent, "应有 CAN 帧被下发"
    assert {cid for cid, _d, _e in sent} >= set(acc.can_ids), "ACC 用例涉及的报文都应下发"
    frame_23a = next(d for cid, d, _e in sent if cid == 0x23A)
    assert frame_23a[1] == 240, "速度值 240 应落在字节 1（0 起约定）"
    assert all(len(d) >= 8 for _c, d, _e in sent)
    assert someip.links and someip.links[0][0] == "0x010A", "链路型输入应驱动服务注册"


def test_runner_records_unsupported_inputs_honestly():
    """mem 字段与"仅门控无位域"的报文必须如实记为不可下发，而不是静默忽略。"""
    case = parser.load_case(CASE_DIR / "TC-AR-EX01.json")
    result = runner.DiCaseRunner(dry_run=True, gate_defaults={}).run_cases([case]).results[0]
    assert any("mem." in u for u in result.unsupported)
    assert result.support == "partial"

    field_case = parser.load_case(CASE_DIR / "TC-ARBLANKET-FUSION-OFF-HIDDEN.json")
    result = runner.DiCaseRunner(dry_run=True).run_cases([field_case]).results[0]
    assert any("PlanningLinePointCount" in u for u in result.unsupported), \
        "库中没有该字段的结构体 → 必须报出来"


def test_report_serialisation(tmp_path):
    """JSON 报告：新旧键都在（兼容既有脚本），并带上环境/对比/归类信息。"""
    cases = parser.load_cases(CASE_DIR)[:5]
    report = runner.DiCaseRunner(dry_run=True).run_cases(cases)
    path = report.dump(tmp_path / "report.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    # 旧键（既有脚本/界面在用）
    assert data["summary"]["cases"] == 5
    assert data["mode"] == "dry-run"
    assert "dry-run" in report.describe()
    # 新键
    assert data["schema"] == "hudautotest.di-case-report/1"
    assert set(data) >= {"command", "environment", "summary", "diff", "failures",
                         "unsupported", "results"}
    assert data["environment"].get("SOME/IP 服务表代")
    assert "pass_rate" in data["summary"] and "verdict" in data["summary"]
    assert "error_breakdown" in data["summary"] and "unsupported_breakdown" in data["summary"]


def test_report_markdown_sections_and_table_integrity(tmp_path):
    """Markdown 报告：结论行 + 环境/统计/逐项章节；表格列数自洽（转义竖线不算列）。"""
    def unescaped_pipes(line: str) -> int:
        return sum(1 for i, ch in enumerate(line) if ch == "|" and (i == 0 or line[i - 1] != "\\"))

    cases = parser.load_cases(CASE_DIR)[:6]
    report = runner.DiCaseRunner(dry_run=True).run_cases(
        cases, command="python -m scripts.run_di_cases --limit 6")
    text = report.render_markdown()
    assert text.startswith("# Di 测试用例执行报告（dry-run）")
    for section in ("## 执行环境", "## 统计", "## 逐项结果", "## 说明"):
        assert section in text, f"缺少章节：{section}"
    assert "复现命令" in text and "python -m scripts.run_di_cases" in text
    assert "用例目录" in text and "SOME/IP 服务表代" in text

    body = text.split("## 逐项结果", 1)[1]
    rows = [ln for ln in body.splitlines() if ln.startswith("| ") and "---" not in ln]
    assert len(rows) == 1 + len(cases), "表头 + 每个用例一行"
    for line in rows:
        assert unescaped_pipes(line) == 10, f"逐项表应为 9 列：{line[:80]}"

    env = text.split("## 执行环境", 1)[1].split("## ", 1)[0]
    for line in [ln for ln in env.splitlines() if ln.startswith("| ") and "---" not in ln]:
        assert unescaped_pipes(line) == 3, f"环境表应为 2 列：{line[:80]}"

    written = report.write_reports(tmp_path / "di.md", tmp_path / "di.json")
    assert written.is_file() and (tmp_path / "di.json").is_file()


def test_report_groups_unsupported_and_errors():
    """不可下发项按类型聚合、错误按原因归类 —— 这是评审最需要的两处归纳。"""
    cases = parser.load_cases(CASE_DIR)
    report = runner.DiCaseRunner(dry_run=True, gate_defaults={}).run_cases(cases)
    breakdown = report.summary["unsupported_breakdown"]
    assert breakdown.get("mem 内部状态量", 0) > 400, "样例里有大量 mem 内部状态量"
    assert breakdown.get("仅门控说明、无位域报文", 0) > 100, "样例里有大量无位域的门控报文"
    assert breakdown.get("SOME/IP 字段不可下发", 0) > 0

    # 注入一条值超出位域的错误，验证归类
    bad = parser.parse_case_obj({
        "scenario_id": "TC-BAD-RANGE", "input_combination": {
            "can": [{"signal_id": "0x100", "sub_id": "", "bit_range": "0.0-0.2", "value": 9}]},
        "expected_output": {}, "wait_ms": 0})
    text = runner.DiCaseRunner(dry_run=False, can_sender=lambda *a: 1,
                               gate_defaults={}).run_cases([bad]).render_markdown()
    assert "## 失败与错误（1）" in text
    assert "值超出位域范围（用例与位域定义矛盾）" in text
    assert runner.error_kind("值 8 超出位域 6.0-6.2 的 3 位范围（<8）") == "值超出位域范围（用例与位域定义矛盾）"


def test_report_diff_against_previous_run():
    """与上次运行对比：按 scenario_id 匹配；error 也要算"失败"（Di 的 error 是执行出错）。"""
    cases = parser.load_cases(CASE_DIR)[:3]
    previous = runner.DiCaseRunner(dry_run=True).run_cases(cases).to_dict()
    previous["results"] = [{"scenario_id": c.scenario_id, "status": runner.STATUS_PASS}
                           for c in cases]

    # 让执行必然出错（不发 CAN 实现），此时应为 error → 对比里算"新增失败"
    failing = runner.DiCaseRunner(dry_run=False, can_sender=None).run_cases(
        cases, previous=previous)
    assert all(r.status == runner.STATUS_ERROR for r in failing.results)
    diff = failing.diff
    assert diff["regressions"] == [c.scenario_id for c in cases], "error 应被计为新增失败"
    assert diff["fixed"] == [] and diff["still_failing"] == []
    text = failing.render_markdown()
    assert "## 与上次运行对比" in text and "新增失败（3）" in text


def test_report_diff_marks_fixed_when_error_disappears():
    """上次 error、本次通过 → 记入"已修复"。"""
    cases = parser.load_cases(CASE_DIR)[:2]
    previous = runner.DiCaseRunner(dry_run=True).run_cases(cases).to_dict()
    previous["results"] = [{"scenario_id": c.scenario_id, "status": runner.STATUS_ERROR}
                           for c in cases]
    ok = runner.DiCaseRunner(dry_run=True).run_cases(cases, previous=previous)
    assert ok.diff["fixed"] == [c.scenario_id for c in cases]
    assert "已修复（2）" in ok.render_markdown()


def test_report_without_previous_has_no_diff_section():
    cases = parser.load_cases(CASE_DIR)[:2]
    text = runner.DiCaseRunner(dry_run=True).run_cases(cases).render_markdown()
    assert "## 与上次运行对比" not in text


# =========================================================================== 标贴校验
def _write_solid_image(path: Path, size: tuple[int, int] = (40, 20), color: str = "white") -> None:
    from PIL import Image
    Image.new("RGB", size, color).save(path)


def _write_text_image(path: Path, text: str, size: tuple[int, int] = (40, 20)) -> None:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", size, "black")
    ImageDraw.Draw(img).text((3, 4), text, fill="white")
    img.save(path)


def _verifier_fixture(tmp_path):
    """搭一套最小参考图环境：UI 配置 + 参考图 + 标签映射（隔离于项目真实配置）。"""
    cfg_dir = tmp_path / "UI_Config"
    img_dir = tmp_path / "ImageUI"
    cfg_dir.mkdir(parents=True)
    img_dir.mkdir(parents=True)

    _write_text_image(img_dir / "ACC.png", "ACC")
    _write_text_image(img_dir / "ICC.png", "ICC")
    (cfg_dir / "ui_config_test.json").write_text(json.dumps({
        "background.png": {"name": "background", "class_name": "background",
                           "width": 100, "height": 50, "top": 0, "left": 0},
        "ACC.png": {"name": "ACC巡航", "class_name": "Text_Icon_ACC",
                    "width": 40, "height": 20, "top": 10, "left": 10},
        "ICC.png": {"name": "ICC", "class_name": "Icon_ICC",
                    "width": 40, "height": 20, "top": 10, "left": 50},
    }, ensure_ascii=False), encoding="utf-8")
    map_path = tmp_path / "label_map.json"
    map_path.write_text(json.dumps({"config": "ui_config_test.json", "image_dir": str(img_dir),
                                    "aliases": {"ACC": ["ACC.png"], "ICC": ["ICC.png"]}},
                                   ensure_ascii=False), encoding="utf-8")
    return LabelVerifier(config_name="ui_config_test.json", image_dir=img_dir,
                         map_path=map_path, config_dir=cfg_dir)


def test_label_verifier_matches_expected_and_negative_labels(tmp_path):
    """画面里 ACC 图标命中 → 期望显示通过；同时命中负向标贴 → 判失败。"""
    from PIL import Image
    verifier = _verifier_fixture(tmp_path)

    frame = Image.new("RGB", (100, 50), "black")
    frame.paste(Image.open(tmp_path / "ImageUI" / "ACC.png"), (10, 10))     # 贴到 ACC 区域
    frame.paste(Image.open(tmp_path / "ImageUI" / "ICC.png"), (50, 10))     # ICC 也亮

    visible = verifier.verify_frame(frame, parser.ExpectedOutput(
        primary_label="ACC", location_constraint="30,20", min_confidence=0.9))
    assert visible.status == "pass", visible.describe()
    assert visible.verdicts[0].confidence == 100.0

    negative = verifier.verify_frame(frame, parser.ExpectedOutput(
        primary_label="ACC", negative_label="ICC", location_constraint="70,20"))
    assert negative.status == "fail", "负向标贴同时命中应判失败"
    assert negative.verdicts[1].status == "mismatch"


def test_label_verifier_reports_no_reference_and_missing_frame(tmp_path):
    """没有参考图的标贴记为 no_reference（不算通过）；没有画面记为 error。"""
    from PIL import Image
    verifier = _verifier_fixture(tmp_path)
    frame = Image.new("RGB", (100, 50), "black")

    unknown = verifier.verify_frame(frame, parser.ExpectedOutput(primary_label="TRAFFICLIGHT"))
    assert unknown.status == "unverifiable"
    assert unknown.verdicts[0].status == "no_reference"

    no_frame = verifier.verify_frame(None, parser.ExpectedOutput(primary_label="ACC"))
    assert no_frame.status == "fail"
    assert no_frame.verdicts[0].status == "error"


def test_label_verifier_coverage_counts(tmp_path):
    verifier = _verifier_fixture(tmp_path)
    coverage = verifier.coverage(["ACC", "ICC", "TRAFFICLIGHT"])
    assert coverage == {"labels": 3, "covered": 2, "uncovered": 1,
                        "uncovered_list": ["TRAFFICLIGHT"]}


def test_runner_fails_case_when_label_missing(tmp_path):
    """执行器与校验器联动：期望显示但画面没有 → 用例判 fail。"""
    from PIL import Image
    verifier = _verifier_fixture(tmp_path)
    frame_path = tmp_path / "empty.png"
    Image.new("RGB", (100, 50), "black").save(frame_path)

    case = parser.parse_case_obj({
        "scenario_id": "TC-FAKE-ACC", "input_combination": {
            "can": [{"signal_id": "0x23A", "sub_id": "", "bit_range": "1.0-1.7", "value": 1}]},
        "expected_output": {"primary_label": "ACC", "negative_label": "",
                            "location_constraint": "30,20", "min_confidence": 0.9},
        "wait_ms": 0})
    exec_runner = runner.DiCaseRunner(can_sender=lambda *a: 1, frame_provider=lambda: frame_path,
                                      verifier=verifier, dry_run=False)
    result = exec_runner.run_cases([case]).results[0]
    assert result.status == runner.STATUS_FAIL
    assert result.frame_status == "fail"


# =========================================================================== 格式开关
def test_format_switch_defaults_to_legacy(monkeypatch):
    """默认必须是旧格式：老用法与既有自动化不受影响。"""
    monkeypatch.delenv(case_format.ENV_VAR, raising=False)
    case_format.set_format(None)
    assert case_format.active_format() == case_format.LEGACY
    assert case_format.default_format() == case_format.LEGACY
    assert case_format.is_di() is False
    case_format.set_format(case_format.DI)
    assert case_format.is_di() is True
    case_format.set_format(None)


def test_format_switch_from_env(monkeypatch):
    monkeypatch.setenv(case_format.ENV_VAR, "DI")
    case_format.set_format(None)
    assert case_format.active_format() == case_format.DI
    monkeypatch.setenv(case_format.ENV_VAR, "不认识的写法")
    case_format.set_format(None)
    assert case_format.active_format() == case_format.LEGACY, "非法值应回退默认"


def test_detect_format_by_content(tmp_path):
    """按内容识别格式：Di 用例 vs 旧平台导出的中文键 JSON。"""
    di_file = next(CASE_DIR.glob("TC-*.json"))
    assert case_format.detect_format_file(di_file) == case_format.DI

    legacy = tmp_path / "legacy_data.json"
    legacy.write_text(json.dumps({"cases": [{"rows": [{"*用例编号": "1", "描述": "x"}]}]},
                                 ensure_ascii=False), encoding="utf-8")
    assert case_format.detect_format_file(legacy) == case_format.LEGACY

    other = tmp_path / "broken.json"
    other.write_text("{不是合法 json", encoding="utf-8")
    assert case_format.detect_format_file(other) == case_format.LEGACY, "读不了时保守回退"


def test_resolve_format_auto_uses_file_content(tmp_path):
    di_file = next(CASE_DIR.glob("TC-*.json"))
    assert case_format.resolve_format(case_format.AUTO, di_file) == case_format.DI
    assert case_format.resolve_format("legacy", di_file) == case_format.LEGACY
    assert case_format.resolve_format(case_format.AUTO, None) == case_format.LEGACY
