# -*- coding: utf-8 -*-
"""someip_gui.ui_rules —— SOME/IP 回放窗口的**按钮规则表**与状态栏文案（纯函数）
================================================================================

为什么单独一个模块：

  · 规则是 ``UiState -> bool`` 的**纯函数**，不 import tkinter，可直接单测
    （见 ``tests/test_someip_gui.py`` 的"规则表 + 状态流转"用例）；
  · 主窗口（``replay_window``）与控制面板（``panel_control``）都要登记按钮，
    规则集中在这里可以避免两个面板模块互相 import（循环依赖）。

状态来源（:class:`hudcore.ui.state.UiState`）：

  · ``library_ok``   SOME/IP 服务端库是否可用（不可用 → 动作按钮一律置灰）；
  · ``flags``        ``opened`` / ``started`` / ``replaying`` —— 直接映射
    :class:`someip_core.replay.ReplayState` 的三个生命周期标志；
  · ``busy``         一次性动作进行中，沿用 ``hudcore.ui.state`` 的 ``BUSY_*`` 常量
    （不新增常量，映射关系如下）：

    ================  ====================  ==========================
    ``busy``          对应动作               状态栏阶段文字
    ================  ====================  ==========================
    ``BUSY_INIT``     打开服务               打开中
    ``BUSY_ACT``      启动服务 / 发送该事件   启动中 / 发送中
    ``BUSY_CLOSE``    停止服务 / 关闭服务     停止/关闭中
    ``BUSY_EXECUTE``  开始/停止回放           回放启停中
    ``BUSY_PROBE``    重新检测库             检测库中
    ``BUSY_NONE``     空闲                   未打开 / 已打开 / 已启动 / 回放中
    ================  ====================  ==========================

规则表（本模块就是"哪个状态点亮哪个按钮"的唯一出处）：

    ==============================  ==================================================
    按钮                            可用条件
    ==============================  ==================================================
    打开服务                        库可用 且 空闲 且 **未打开**
    启动服务                        库可用 且 空闲 且 已打开 且 未启动
    停止服务                        库可用 且 空闲 且 已打开 且 已启动
    关闭服务                        库可用 且 空闲 且 已打开
    开始回放                        库可用 且 空闲 且 未在回放（**未打开时也保持可用**）
    停止回放                        库可用 且 正在回放
    发送该事件                      库可用 且 空闲（**未打开时也保持可用**）
    重新检测库 / 导出服务表 / 保存配置  空闲（**不要求库可用**，见下）
    ==============================  ==================================================

两处刻意的取舍（写进注释与 ``docs/SOMEIP_REPLAY.md``，避免下次被当成 bug 改回去）：

1. **「打开服务」在实例已打开/已启动时置灰**，而不是"保持可点、由 controller 忽略重复调用"。
   理由：打开动作的语义是"创建实例 + 按勾选注册服务/事件"；实例已存在时再点不会有任何
   变化（controller 只会记一条"服务端已打开，忽略重复打开"），留着可点会让用户误以为
   自己新勾选的服务已经生效。要重新注册请先「关闭服务」。置灰还能让用户一眼看出进度
   （配合状态栏的"阶段：已打开/已启动"）。

2. **「开始回放」「发送该事件」在未打开实例时仍可用**：这是既有的便利行为 ——
   两个动作会先自动"打开服务 + 启动服务"再执行（``on_replay_start`` / ``on_send_struct``），
   因此不按 ``opened`` 置灰。但它们仍受 ``busy`` 约束（自动开服务期间不可重复点击）。

3. **「重新检测库 / 导出服务表 / 保存配置」不要求库可用**：库一旦不可用，若把"重新检测库"
   也置灰，用户就再也点不回来（只能重启窗口）；导出服务表读的是代码里的服务表、保存配置
   写的是本地 json，都不需要库。
"""
from __future__ import annotations

from typing import Tuple

from hudcore.ui.state import (
    BUSY_ACT, BUSY_CLOSE, BUSY_EXECUTE, BUSY_INIT, BUSY_PROBE, UiState,
)

__all__ = [
    "KEY_OPEN", "KEY_START", "KEY_STOP", "KEY_CLOSE", "KEY_RECHECK", "KEY_EXPORT",
    "KEY_SAVE_CONFIG", "KEY_REPLAY_START", "KEY_REPLAY_STOP", "KEY_SEND",
    "LIBRARY_ACTION_KEYS", "LIBRARY_FREE_KEYS", "ALL_KEYS", "RULES",
    "can_open", "can_start", "can_stop", "can_close", "can_replay_start",
    "can_replay_stop", "can_send", "can_use_tool",
    "phase_text", "compose_status", "one_line_reason",
    "BUSY_BY_ACTION",
]

# ---------------------------------------------------------------- 按钮键名
KEY_OPEN = "open_service"
KEY_START = "start_service"
KEY_STOP = "stop_service"
KEY_CLOSE = "close_service"
KEY_RECHECK = "recheck_library"
KEY_EXPORT = "export_table"
KEY_SAVE_CONFIG = "save_config"
KEY_REPLAY_START = "replay_start"
KEY_REPLAY_STOP = "replay_stop"
KEY_SEND = "send_struct"

#: 需要库可用才能执行的动作按钮（库不可用 → 全部 disabled）
LIBRARY_ACTION_KEYS: Tuple[str, ...] = (
    KEY_OPEN, KEY_START, KEY_STOP, KEY_CLOSE, KEY_REPLAY_START, KEY_REPLAY_STOP, KEY_SEND,
)
#: 不依赖库的辅助按钮（只受"是否正在忙"约束，见模块头部说明 3）
LIBRARY_FREE_KEYS: Tuple[str, ...] = (KEY_RECHECK, KEY_EXPORT, KEY_SAVE_CONFIG)

ALL_KEYS: Tuple[str, ...] = LIBRARY_ACTION_KEYS + LIBRARY_FREE_KEYS

#: 动作 → busy 常量（动作方法里用 ``with self._busy(BUSY_BY_ACTION["open"]):``）
BUSY_BY_ACTION = {
    "open": BUSY_INIT,
    "start": BUSY_ACT,
    "stop": BUSY_CLOSE,
    "close": BUSY_CLOSE,
    "replay": BUSY_EXECUTE,
    "send": BUSY_ACT,
    "recheck": BUSY_PROBE,
}


# ---------------------------------------------------------------- 规则（纯函数）
def can_open(state: UiState) -> bool:
    """打开服务：库可用、空闲、且**实例尚未打开**（已打开时置灰，理由见模块头部 1）。"""
    return state.library_ok and state.idle and not state.flag("opened")


def can_start(state: UiState) -> bool:
    """启动服务：必须先"打开服务"（未打开实例时置灰），已启动则无需再启动。"""
    return (state.library_ok and state.idle
            and state.flag("opened") and not state.flag("started"))


def can_stop(state: UiState) -> bool:
    """停止服务：只在"已打开且已启动"时可用（未启动时点它没有意义）。"""
    return (state.library_ok and state.idle
            and state.flag("opened") and state.flag("started"))


def can_close(state: UiState) -> bool:
    """关闭服务：实例存在即可用（已启动也能直接关闭，controller.close() 会一并停回放）。"""
    return state.library_ok and state.idle and state.flag("opened")


def can_replay_start(state: UiState) -> bool:
    """开始回放：库可用、空闲、当前未在回放；**未打开实例时仍可用**（会自动先开服务）。"""
    return state.library_ok and state.idle and not state.flag("replaying")


def can_replay_stop(state: UiState) -> bool:
    """停止回放：只在回放中可用（未回放时置灰，避免空点）。"""
    return state.library_ok and state.flag("replaying")


def can_send(state: UiState) -> bool:
    """发送该事件：库可用、空闲；**未打开实例时仍可用**（会自动先开服务）。"""
    return state.library_ok and state.idle


def can_use_tool(state: UiState) -> bool:
    """辅助按钮（重新检测库 / 导出服务表 / 保存配置）：只要没有动作在跑就可用。"""
    return state.idle


#: 规则表：按钮键名 → 规则函数（``ButtonGroup.add(key, widget, RULES[key])``）
RULES = {
    KEY_OPEN: can_open,
    KEY_START: can_start,
    KEY_STOP: can_stop,
    KEY_CLOSE: can_close,
    KEY_REPLAY_START: can_replay_start,
    KEY_REPLAY_STOP: can_replay_stop,
    KEY_SEND: can_send,
    KEY_RECHECK: can_use_tool,
    KEY_EXPORT: can_use_tool,
    KEY_SAVE_CONFIG: can_use_tool,
}


# ---------------------------------------------------------------- 状态栏文案
def phase_text(state: UiState) -> str:
    """当前阶段（状态栏「阶段：…」/ 日志用）：忙时显示正在做的动作，空闲时显示生命周期阶段。"""
    if state.busy == BUSY_INIT:
        return "打开中"
    if state.busy == BUSY_ACT:
        # BUSY_ACT 同时用于"启动服务"与"发送该事件"：按生命周期标志区分
        return "启动中" if (state.flag("opened") and not state.flag("started")) else "发送中"
    if state.busy == BUSY_CLOSE:
        return "停止/关闭中"
    if state.busy == BUSY_EXECUTE:
        return "回放启停中"
    if state.busy == BUSY_PROBE:
        return "检测库中"
    if state.busy:                                   # 其它未映射的忙标志（防御）
        return f"{state.busy}中"
    if not state.flag("opened"):
        return "未打开"
    if state.flag("replaying"):
        return "回放中"
    if state.flag("started"):
        return "已启动"
    return "已打开"


def one_line_reason(raw: str, limit: int = 72) -> str:
    """把多行库状态/修复提示压成一行（状态栏只放得下一行；完整内容仍在日志区）。

    取**第一行非空文字**（修复提示的首行就是结论，后续行是操作步骤），再按 ``limit`` 截断。
    """
    lines = [ln.strip() for ln in str(raw or "").splitlines() if ln.strip()]
    text = lines[0] if lines else ""
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def compose_status(state: UiState, *, sent: int = 0, services: int = 0, events: int = 0,
                   reason: str = "") -> str:
    """合成**一行**状态栏文本（定时刷新与动作结束都走这里，避免互相覆盖）。

    库不可用时返回"红字提示 + 原因"，**不带阶段的库就绪前缀** —— 这正是此前被
    ``controller.summary()`` 覆盖掉的那条提示（见 ``docs/SOMEIP_REPLAY.md``）。

    例：
        · 正常       ``库就绪｜阶段：已启动｜回放中（已发 1234）｜服务 11/事件 23``
        · 库不可用   ``SOME/IP 库不可用（动作已置灰）｜原因：未找到 SOME/IP 服务端库…｜阶段：未打开``
    """
    phase = phase_text(state)
    if not state.library_ok:
        head = "SOME/IP 库不可用（动作已置灰）"
        reason = one_line_reason(reason)
        if reason:
            head += f"｜原因：{reason}"
        return f"{head}｜阶段：{phase}"
    replay = f"回放中（已发 {sent}）" if state.flag("replaying") else f"未回放（已发 {sent}）"
    return f"库就绪｜阶段：{phase}｜{replay}｜服务 {services}/事件 {events}"
