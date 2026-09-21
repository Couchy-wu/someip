# -*- coding: utf-8 -*-
"""can_core.device_probe —— 在**子进程**里探测 CAN 设备是否可用

为什么需要（实测问题）：Linux 上公开的 ZLG VCI 驱动（`libusbcanfd.so`）在**没有插卡**时
调用 `VCI_OpenDevice` 会让进程**直接段错误退出**（实测 rc=139 / SIGSEGV）。父进程里做
try/except 也拦不住段错误 —— 上层（CAN 测试界面、Di 用例窗口）点一下"初始化设备/执行"就会
把整个上位机带走。

做法：把"打开设备再关闭"放进**子进程**跑一遍，只看子进程的退出码：

    · 正常退出（0）        → 设备可用
    · 非 0 / 被信号杀死    → 设备不可用（把信号号一并写进说明，便于现场定位）
    · 超时                 → 视为不可用（底层库卡住同样不能放进主进程）

结果带短 TTL 缓存，避免每次点击都起子进程；`reset_cache()` 供测试与"重新检测"使用。
"""
from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from hudcore import logging_setup

LOGGER_NAME = "candata"

DEFAULT_TIMEOUT_S = 20.0
DEFAULT_CACHE_TTL_S = 30.0

# 子进程里执行的探测脚本：打开设备→读设备信息→关闭，全程打印到 stdout 供排障
_CHILD_CODE = r"""
import sys
sys.path.insert(0, {root!r})
from can_core import device
dev, chns, threads = device.Initialize_Canfd_Device()
if not dev or not chns:
    print("PROBE_FAIL: 设备未就绪（未插卡或驱动未加载）")
    sys.exit(3)
print("PROBE_OK: 设备句柄=%s 通道=%d" % (dev, len(chns)))
try:
    device.Close_Canfd_Device(dev, chns, threads)
except Exception as exc:                      # noqa: BLE001
    print("PROBE_WARN: 关闭设备异常 %s" % exc)
sys.exit(0)
"""


@dataclass(frozen=True)
class ProbeResult:
    """探测结果。"""

    available: bool
    detail: str
    exit_code: Optional[int] = None
    elapsed_s: float = 0.0
    cached: bool = False

    def describe(self) -> str:
        mark = "可用" if self.available else "不可用"
        return f"CAN 设备{mark}：{self.detail}（耗时 {self.elapsed_s:.1f}s）"


_CACHE: dict[str, object] = {"at": 0.0, "result": None}


def _signal_hint(code: int) -> str:
    import signal as _signal
    if code >= 0:
        return f"退出码 {code}"
    signum = -code
    name = _signal.Signals(signum).name if signum in [s.value for s in _signal.Signals] else str(signum)
    return f"被信号 {name} 终止（底层驱动异常，例如未插卡时 libusbcanfd.so 段错误）"


def probe_can_device(timeout_s: float = DEFAULT_TIMEOUT_S,
                     use_cache: bool = True, cache_ttl_s: float = DEFAULT_CACHE_TTL_S) -> ProbeResult:
    """在子进程中探测 CAN 设备是否可用（绝不把底层崩溃带进主进程）。"""
    now = time.time()
    cached = _CACHE.get("result")
    if use_cache and isinstance(cached, ProbeResult) and now - float(_CACHE["at"]) < cache_ttl_s:
        return ProbeResult(cached.available, cached.detail, cached.exit_code, 0.0, cached=True)

    root = str(Path(__file__).resolve().parents[1])
    code = _CHILD_CODE.format(root=root)
    started = time.time()
    try:
        proc = subprocess.run([sys.executable, "-u", "-c", code],
                              capture_output=True, text=True, timeout=timeout_s, cwd=root)
    except subprocess.TimeoutExpired:
        result = ProbeResult(False, f"探测超时（>{timeout_s:.0f}s，底层库可能卡住）",
                             None, time.time() - started)
    else:
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            line = next((ln for ln in output.splitlines() if ln.startswith("PROBE_OK")), "")
            result = ProbeResult(True, line or "设备可用", 0, time.time() - started)
        else:
            line = next((ln for ln in output.splitlines()
                         if ln.startswith(("PROBE_FAIL", "PROBE_WARN"))), "")
            detail = f"{_signal_hint(proc.returncode)}" + (f"；{line}" if line else "")
            result = ProbeResult(False, detail, proc.returncode, time.time() - started)

    _CACHE["at"] = now
    _CACHE["result"] = result
    logging_setup.info(LOGGER_NAME, "设备探测：" + result.describe())
    return result


def reset_cache() -> None:
    """清空缓存（"重新检测设备"或测试用）。"""
    _CACHE["at"] = 0.0
    _CACHE["result"] = None


__all__ = ["ProbeResult", "probe_can_device", "reset_cache",
           "DEFAULT_TIMEOUT_S", "DEFAULT_CACHE_TTL_S"]
