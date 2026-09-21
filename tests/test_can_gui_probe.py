# -*- coding: utf-8 -*-
"""tests/test_can_gui_probe.py —— CAN 界面「检测设备」入口（gui_test_flow 的探测逻辑）

不构造整个 CAN GUI（依赖相机/视频等重资源），只验证探测这条链路的编排：
  · `start_probe()` 切到"检测中"状态（按钮由状态机置灰）并起线程；
  · `probe_device()` **忽略缓存**重新探测，并把结论回主线程；
  · `_post_probe()` 结束"检测中"状态、写日志，并按结果弹提示（未插卡时给排查建议）。

按钮可用性自本次重构起由 `can_gui.gui_layout.RULES` 规则表统一决定，
因此这里用真实的 `ButtonGroup` 承载一个假按钮，断言"对外可见的状态变化"。
"""
from __future__ import annotations

import threading
import pytest

from can_core import device_probe
from can_gui import gui_test_flow
from can_gui.gui_layout import RULES, LayoutMixin
from hudcore.ui import BUSY_NONE, BUSY_PROBE, ButtonGroup


class _FakeButton:
    def __init__(self):
        self.states: list[str] = []

    def config(self, **kwargs):
        if "state" in kwargs:
            self.states.append(str(kwargs["state"]))

    configure = config                      # 状态机统一走 configure(state=...)

    @property
    def state(self) -> str:
        return self.states[-1] if self.states else "normal"


class _FakeRoot:
    """`after(0, cb)` 立即执行（模拟主线程回灌）。"""

    def __init__(self):
        self.callbacks = 0

    def after(self, _delay, callback, *a):
        self.callbacks += 1
        callback(*a)
        return "id"


class _Harness(gui_test_flow.TestFlowMixin, LayoutMixin):
    """只组合"流程 + 按钮状态机"两个 Mixin（不含相机/配置），足够覆盖探测链路。"""


def _harness():
    """只搭"探测链路"需要的部件：假按钮 + 假主线程 + 真实状态机。"""
    obj = _Harness()
    obj.probe_btn = _FakeButton()
    obj.root = _FakeRoot()
    obj._busy = BUSY_NONE
    obj.device_handle = None
    obj.buttons = ButtonGroup("can_gui_test")
    obj.buttons.add("probe", obj.probe_btn, RULES["probe"])
    obj._apply_ui_state()                  # 初始态：空闲且无设备 → 可点
    return obj


@pytest.fixture(autouse=True)
def _clean_cache():
    device_probe.reset_cache()
    yield
    device_probe.reset_cache()


def test_start_probe_disables_button_and_spawns_thread(monkeypatch):
    obj = _harness()
    done = threading.Event()
    monkeypatch.setattr(gui_test_flow.TestFlowMixin, "probe_device",
                        lambda self: done.set())
    obj.start_probe()
    assert obj.probe_btn.state == "disabled", "探测期间应禁用按钮，避免重复点击"
    assert obj._busy == BUSY_PROBE, "应进入「检测中」状态（其它按钮据此一并置灰）"
    assert done.wait(5), "应在后台线程里执行探测"


def test_probe_device_ignores_cache_and_reports_via_main_thread(monkeypatch):
    """手动检测=重新检测：必须忽略缓存（用户点了一次就该真去探一次）。"""
    calls = {"reset": 0, "probe": 0, "cache": None}

    def _reset():
        calls["reset"] += 1

    def _probe(use_cache=True, **kwargs):
        calls["probe"] += 1
        calls["cache"] = use_cache
        return device_probe.ProbeResult(False, "被信号 SIGSEGV 终止", -11, 0.2)

    monkeypatch.setattr(device_probe, "reset_cache", _reset)
    monkeypatch.setattr(device_probe, "probe_can_device", _probe)

    obj = _harness()
    posted: list[tuple] = []
    monkeypatch.setattr(gui_test_flow.TestFlowMixin, "_post_probe",
                        lambda self, ok, message: posted.append((ok, message)))

    obj.probe_device()
    assert calls == {"reset": 1, "probe": 1, "cache": False}, "应先清缓存再忽略缓存探测"
    assert obj.root.callbacks == 1, "结果应回主线程处理"
    assert posted and posted[0][0] is False and "SIGSEGV" in posted[0][1]


def test_probe_device_reports_exception_without_crashing(monkeypatch):
    def _boom(**kwargs):
        raise RuntimeError("库未加载")

    monkeypatch.setattr(device_probe, "probe_can_device", _boom)
    obj = _harness()
    posted: list[tuple] = []
    monkeypatch.setattr(gui_test_flow.TestFlowMixin, "_post_probe",
                        lambda self, ok, message: posted.append((ok, message)))
    obj.probe_device()                                   # 不应抛异常
    assert posted and posted[0][0] is False and "探测异常" in posted[0][1]


def test_post_probe_restores_button_logs_and_warns(monkeypatch, capsys):
    """不可用时：按钮恢复、日志有结论、弹窗给出排查建议。"""
    shown: list[tuple] = []
    monkeypatch.setattr(gui_test_flow.messagebox, "showwarning",
                        lambda *a, **k: shown.append(a))
    monkeypatch.setattr(gui_test_flow.messagebox, "showinfo",
                        lambda *a, **k: shown.append(a))
    obj = _harness()
    obj.buttons.force("disabled", "probe")   # 模拟"探测中"（状态机维护的置灰）

    obj._post_probe(False, "CAN 设备不可用：被信号 SIGSEGV 终止")
    assert obj.probe_btn.state == "normal", "探测结束后应恢复按钮"
    out = capsys.readouterr().out
    assert "[CAN] CAN 设备不可用" in out, "结论要打到界面日志（main.py 重定向 stdout）"
    assert shown and "排查" in shown[0][1] and "子进程隔离" in shown[0][1]


def test_post_probe_success_uses_info_dialog(monkeypatch):
    shown: list[tuple] = []
    monkeypatch.setattr(gui_test_flow.messagebox, "showinfo",
                        lambda *a, **k: shown.append(a))
    monkeypatch.setattr(gui_test_flow.messagebox, "showwarning",
                        lambda *a, **k: shown.append(("warn",) + a))
    obj = _harness()
    obj._post_probe(True, "CAN 设备可用：设备句柄=1 通道=2")
    assert shown and shown[0][0] == "设备检测" and "初始化设备" in shown[0][1]
