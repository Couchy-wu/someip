# -*- coding: utf-8 -*-
"""tests/test_core_behaviour.py —— 核心行为的单元测试（无需硬件、无需显示器）

覆盖：
  · 位/字节工具（纯函数）
  · CAN 层共享状态（单例跨模块一致、驱动实例惰性、可复位）
  · CAN 信号 → 数据字节（真实 5.9 万行信号矩阵；含"与当前工作目录无关"回归）
  · 日志解析器的 Mixin 组合与用例切分
  · 平台/路径层约定（绝对路径、项目根定位、Python 版本策略）
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- 位工具

def test_bit_utils_bit_length():
    from can_core.bit_utils import calculate_bit_length
    assert calculate_bit_length("0.0-0.7") == 8
    assert calculate_bit_length("1.0-1.1") == 2
    assert calculate_bit_length("2.0-2.15") == 16


def test_bit_utils_extract_bit_range():
    """位表示法为 1 基字节：`1.0-1.7` 对应 data[0]，`2.0` 对应 data[1]。"""
    from can_core.bit_utils import extract_bits_from_data
    assert extract_bits_from_data([0x01, 0, 0, 0, 0, 0, 0, 0], "1.0-1.0") == 1
    assert extract_bits_from_data([0x00, 0, 0, 0, 0, 0, 0, 0], "1.0-1.0") == 0
    assert extract_bits_from_data([0x0C, 0, 0, 0, 0, 0, 0, 0], "1.2-1.3") == 0b11
    # 跨字节：byte1 全部 8 位 + byte2 第 0 位
    assert extract_bits_from_data([0xFF, 0x01, 0, 0, 0, 0, 0, 0], "1.0-2.0") == 0x1FF
    # 同一输入重复调用结果稳定
    assert extract_bits_from_data([0x0C, 0], "1.0-1.1") == extract_bits_from_data([0x0C, 0], "1.0-1.1")


def test_bit_utils_reports_insufficient_data():
    """数据长度不足时返回 -1（调用方据此判断解析失败）。"""
    from can_core.bit_utils import extract_bits_from_data
    assert extract_bits_from_data([0x00], "1.0-2.0") == -1


# --------------------------------------------------------------------------- CAN 状态

def test_can_state_is_shared_across_modules():
    from can_core import device, receive, transmit
    from can_core.can_state import state
    assert receive.state is transmit.state is device.state is state, \
        "拆分后各模块必须共享同一个状态对象，否则线程开关/接收缓存会状态分裂"


def test_can_state_mutation_visible_everywhere():
    from can_core import receive, transmit
    from can_core.can_state import state
    state.reset_for_tests()
    transmit.state.thread_flag = False
    assert receive.state.thread_flag is False
    state.transmit_type = 2
    assert transmit.state.transmit_type == 2
    state.received_messages.append({"id": "0x123"})
    assert len(receive.state.received_messages) == 1
    state.reset_for_tests()
    assert state.thread_flag is True and len(state.received_messages) == 0


def test_zcanlib_is_lazy():
    """导入 CAN 层不应尝试加载驱动库（原实现在导入时就 ZCAN()）。"""
    import importlib
    import can_core.can_state as cs
    importlib.reload(cs)
    assert cs.state._zcanlib is None, "驱动实例应为惰性创建"


def test_device_facade_api_surface():
    """device 门面必须保留原有公共函数（既有调用点不受拆分影响）。"""
    from can_core import device
    expected = [
        "Send_Can", "Send_Canfd", "Send_Can_Signal", "Send_Can_Or_Canfd",
        "Auto_Send_Can", "Auto_Send_Canfd", "Auto_Send_Can_Or_Canfd",
        "Remove_Auto_Send_By_Index", "Send_Can_With_Dynamic_Interval",
        "Initialize_Canfd_Device", "Close_Canfd_Device", "USBCANFD_Start",
        "receive_thread", "check_signal_received", "wait_for_check_signal_received",
        "wait_for_check_signal_by_bit_enum", "Read_Device_Info", "Set_Device_Name",
        "extract_bits_from_data", "calculate_bit_length",
    ]
    missing = [n for n in expected if not hasattr(device, n)]
    assert not missing, f"device 门面缺少：{missing}"


# --------------------------------------------------------------------------- CAN 信号编解码

def test_can_signal_encoding_from_real_matrix():
    pytest.importorskip("pandas")
    from can_data_tools.find_can_id_from_csv import create_can_data_by_signal
    r0 = create_can_data_by_signal("0x095", "Eng_Start_Result_Fdbk_Info_S", 0)
    r1 = create_can_data_by_signal("0x095", "Eng_Start_Result_Fdbk_Info_S", 1)
    assert r0.get("success") and r1.get("success")
    assert len(r0["can_data"]) == 8, "报文长度应为 8 字节"
    assert r0["can_data"] != r1["can_data"], "不同枚举值应生成不同数据"


def test_matrix_default_path_is_cwd_independent(tmp_path, monkeypatch):
    """回归：默认信号矩阵路径必须基于项目根，而不是当前工作目录。"""
    pytest.importorskip("pandas")
    from can_data_tools.find_can_id_from_csv import (
        _default_matrix_csv, create_can_data_by_signal)
    assert Path(_default_matrix_csv()).is_file(), "默认矩阵应能定位到项目内文件"
    monkeypatch.chdir(tmp_path)                # 换到别的工作目录再调用
    r = create_can_data_by_signal("0x095", "Eng_Start_Result_Fdbk_Info_S", 1)
    assert r.get("success"), "切换工作目录后仍应能读到默认信号矩阵"


# --------------------------------------------------------------------------- 日志解析

def test_log_parser_mixin_composition():
    pytest.importorskip("pandas")
    from can_data_tools.case_log_parser import CaseLogParserMixin
    from can_data_tools.can_step_runner import CanStepRunnerMixin
    from can_data_tools.testcase_runner import LogParser, TestcaseRunnerMixin
    for cls in (CaseLogParserMixin, CanStepRunnerMixin, TestcaseRunnerMixin):
        assert cls in LogParser.__mro__, f"{cls.__name__} 未参与组合"
    for name in ("load_log", "split_test_cases", "parse_all_cases", "_handle_output_can_with_context",
                 "run", "close_test", "_set_state", "get_current_state"):
        assert hasattr(LogParser, name), f"拆分后缺少方法 {name}"


def test_log_parser_splits_cases(tmp_path):
    pytest.importorskip("pandas")
    from can_data_tools.testcase_runner import LogParser
    log = tmp_path / "case.log"
    log.write_text("用例1\n状态: 初始化\n动作: 等待 10 ms\n响应: 输出CAN\n", encoding="utf-8")
    parser = LogParser(str(log))
    parser.load_log()
    parser.split_test_cases()
    assert isinstance(parser.test_cases, list)
    assert parser.get_current_state()          # 状态机有初值


# --------------------------------------------------------------------------- 平台/路径

def test_paths_are_absolute_and_inside_project():
    from hudcore.platform import paths
    for name in ("project_root", "logs_dir", "drivers_dir", "bin_dir", "testcase_dir"):
        p = Path(getattr(paths, name))
        assert p.is_absolute(), f"{name} 应为绝对路径"
    assert Path(paths.project_root).resolve() == ROOT


def test_platform_version_policy():
    from hudcore.platform.system import (
        PYTHON_MAX_TESTED, PYTHON_MIN, exe_suffix, python_status)
    level, note = python_status()
    assert level in ("ok", "warn", "error") and note
    assert PYTHON_MIN <= PYTHON_MAX_TESTED
    if os.name == "nt":
        assert exe_suffix == ".exe"
