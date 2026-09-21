# -*- coding: utf-8 -*-
"""tests/test_can_device_probe.py —— CAN 设备子进程探测（can_core.device_probe）

背景（实测）：Linux 未插卡时 `libusbcanfd.so` 的 OpenDevice 会让进程**段错误**
（rc=139），try/except 拦不住。因此在子进程里探测，只看退出码：

  · 0            → 可用
  · 非 0 / 信号  → 不可用（信号号写进说明，例如 SIGSEGV）
  · 超时         → 不可用

测试通过替换 `subprocess.run` 模拟上述各种退出情形，不依赖真实硬件。
"""
from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

from can_core import device_probe


@pytest.fixture(autouse=True)
def _clean_cache():
    device_probe.reset_cache()
    yield
    device_probe.reset_cache()


def _fake_run(returncode=0, stdout="", stderr="", raise_timeout=False):
    def _run(*_a, **_k):
        if raise_timeout:
            raise subprocess.TimeoutExpired(cmd="probe", timeout=1)
        return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    return _run


def test_probe_available_on_zero_exit(monkeypatch):
    monkeypatch.setattr(device_probe.subprocess, "run",
                        _fake_run(0, stdout="PROBE_OK: 设备句柄=1 通道=2\n"))
    result = device_probe.probe_can_device(use_cache=False)
    assert result.available is True
    assert "设备句柄=1" in result.detail
    assert result.exit_code == 0


def test_probe_reports_signal_when_driver_crashes(monkeypatch):
    """未插卡时底层驱动段错误 → 只能靠退出码判断，说明里要带信号名。"""
    monkeypatch.setattr(device_probe.subprocess, "run",
                        _fake_run(-11, stderr="usbcanfd log path:/work\n"))
    result = device_probe.probe_can_device(use_cache=False)
    assert result.available is False
    assert result.exit_code == -11
    assert "SIGSEGV" in result.detail, f"应指出是被信号终止：{result.detail}"
    assert "不可用" in result.describe()


def test_probe_reports_failure_line_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(device_probe.subprocess, "run",
                        _fake_run(3, stdout="PROBE_FAIL: 设备未就绪（未插卡或驱动未加载）\n"))
    result = device_probe.probe_can_device(use_cache=False)
    assert result.available is False and result.exit_code == 3
    assert "PROBE_FAIL" in result.detail and "退出码 3" in result.detail


def test_probe_treats_timeout_as_unavailable(monkeypatch):
    monkeypatch.setattr(device_probe.subprocess, "run", _fake_run(raise_timeout=True))
    result = device_probe.probe_can_device(timeout_s=5, use_cache=False)
    assert result.available is False and result.exit_code is None
    assert "超时" in result.detail


def test_probe_caches_result(monkeypatch):
    calls = {"n": 0}

    def _run(*_a, **_k):
        calls["n"] += 1
        return types.SimpleNamespace(returncode=0, stdout="PROBE_OK: x\n", stderr="")

    monkeypatch.setattr(device_probe.subprocess, "run", _run)
    first = device_probe.probe_can_device()
    second = device_probe.probe_can_device()
    assert calls["n"] == 1, "TTL 内不应重复起子进程"
    assert first.cached is False and second.cached is True

    device_probe.reset_cache()
    device_probe.probe_can_device()
    assert calls["n"] == 2, "reset_cache 后应重新探测"


def test_probe_child_runs_in_project_root(monkeypatch):
    """子进程要能 import 到项目包：cwd 与 sys.path 都指向项目根。"""
    seen = {}

    def _run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["cwd"] = kwargs.get("cwd")
        return types.SimpleNamespace(returncode=0, stdout="PROBE_OK: x\n", stderr="")

    monkeypatch.setattr(device_probe.subprocess, "run", _run)
    device_probe.probe_can_device(use_cache=False)
    assert seen["cmd"][0] == sys.executable
    assert "can_core" in seen["cmd"][-1] and "Initialize_Canfd_Device" in seen["cmd"][-1]
    assert Path(seen["cwd"]) == Path(__file__).resolve().parents[1]


def test_probe_result_describe_is_readable():
    ok = device_probe.ProbeResult(True, "设备可用", 0, 1.2)
    bad = device_probe.ProbeResult(False, "被信号 SIGSEGV 终止", -11, 0.3)
    assert "可用" in ok.describe() and "耗时 1.2s" in ok.describe()
    assert "不可用" in bad.describe()
