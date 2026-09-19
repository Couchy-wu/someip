# -*- coding: utf-8 -*-
"""docker/can-sim/loopback_demo.py —— 业务层回环演示（跑在 VCI 桩库上）

用途：把 **项目自身的设备层**（`can_core.device` / `can_state` / `receive.py` /
`transmit.py`）接到 `vci_stub.c` 编译出的 VCI 桩库上，走完整链路：

    探测驱动库 → 判定接口形态(vci) → VciCanDriver 适配 → 打开设备(2 通道)
    → 按项目波特率(500k/2M)初始化 → 起接收线程 → 发送 → 接收线程取回 → 关闭

这能证明"没有 ZLG 硬件时，Linux 上也能把整套 CAN 功能跑起来"，而不仅是单测层面的翻译正确。

运行（由 run_check.sh 调用，也可单独跑）：
    HUD_ZLG_LIB=<桩库路径> python docker/can-sim/loopback_demo.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from can_core import device                                    # noqa: E402
from can_core.can_state import state                           # noqa: E402


def main() -> int:
    print("== 业务层回环演示（VCI 桩库） ==")
    print("驱动库:", os.environ.get("HUD_ZLG_LIB", "(未设置)"))
    print("适配后端:", type(state.zcanlib).__name__)

    dev, chn_handles, threads = device.Initialize_Canfd_Device()
    if not dev or not chn_handles:
        print("[失败] Initialize_Canfd_Device 返回空")
        return 1
    print(f"设备句柄=0x{dev:08X} 通道={[hex(c) for c in chn_handles]} 接收线程={len(threads)}")
    assert len(chn_handles) == 2, "桩库报告 2 个通道"

    chn = chn_handles[0]

    # ---- CANFD 回环 ----
    assert device.Send_Canfd(chn, 0, 0x123, [0x11, 0x22, 0x33, 0x44], 1) == 1, "CANFD 发送应返回 1"
    frame = _wait_for("0x123", timeout=5)
    assert frame is not None, "接收线程未取回 CANFD 回环帧"
    assert frame["data_list"] == [0x11, 0x22, 0x33, 0x44], f"数据应为原样，实际 {frame['data_list']}"
    assert frame["type"] == "CANFD" and frame["channel"] == 0
    print(f"[通过] CANFD 回环：{frame}")

    # ---- 扩展帧（0x18FF50E5 超过 11 位 → 适配层按扩展帧发出） ----
    assert device.Send_Canfd(chn, 1, 0x18FF50E5, [0xAA, 0xBB], 1) == 1
    frame = _wait_for("0x18ff50e5", timeout=5)
    assert frame is not None, "扩展帧未取回（ID 高位可能被截断）"
    print(f"[通过] 扩展帧回环：{frame}")

    # ---- 经典 CAN 回环 ----
    assert device.Send_Can(chn, 0, 0x0A1, [0x01, 0x02], 1) == 1
    frame = _wait_for("0xa1", timeout=5)
    assert frame is not None and frame["type"] == "CAN", "经典 CAN 未取回"
    print(f"[通过] CAN 回环：{frame}")

    # ---- 关闭 ----
    device.Close_Canfd_Device(dev, chn_handles, threads)
    state.thread_flag = True
    print("[通过] 设备已正常关闭")
    print("结论: PASS")
    return 0


def _wait_for(can_id: str, timeout: float):
    """等接收线程把指定 ID 的报文写进缓存。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with state.received_messages_lock:
            for msg in state.received_messages:
                if msg["can_id"] == can_id:
                    return dict(msg)
        time.sleep(0.02)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
