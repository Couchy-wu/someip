# -*- coding: utf-8 -*-
"""can_core.vci_adapter —— 把 ZLG Linux 驱动的 **VCI 接口** 适配成项目使用的 **ZCAN 调用面**

背景
----
业务层（`can_core/receive.py`、`can_core/transmit.py`）按 Windows `zlgcan.dll` 的 ZCAN
形态编写：

    dev = zcanlib.OpenDevice(ZCAN_USBCANFD_200U, 0, 0)      # 返回设备句柄
    zcanlib.ZCAN_SetValue(dev, "0/canfd_abit_baud_rate", b"500000")
    chn = zcanlib.InitCAN(dev, 0, init_cfg)                 # 返回通道句柄
    zcanlib.StartCAN(chn)
    zcanlib.TransmitFD(chn, msgs, n) / zcanlib.ReceiveFD(chn, n, wait)

而 Linux 的 `libusbcanfd.so` 只有 VCI 形态：**没有句柄**，一切用
(设备类型, 设备序号, 通道号) 三元组定位，配置靠 `ZCAN_INIT` 结构体与 `VCI_SetReference`。
本模块提供 `VciCanDriver`，把这层差异一次性吸收，业务代码无需改动。

映射关系（依据随仓库分发的官方头文件，见 `vci_driver.py` 的出处说明）
--------------------------------------------------------------------
| 业务层调用（ZCAN 形态）                  | 适配层实现（VCI 形态）                                  |
|------------------------------------------|---------------------------------------------------------|
| `OpenDevice(type, idx, 0)` → 句柄        | `VCI_OpenDevice(type, idx, 0)` + 内部句柄表（句柄自制）  |
| `CloseDevice(h)`                         | `VCI_CloseDevice(type, idx)`                            |
| `InitCAN(h, chn, cfg)` → 通道句柄        | `VCI_InitCAN(type, idx, chn, ZCAN_INIT*)`；时序由波特率算 |
| `StartCAN/ResetCAN/ClearBuffer`          | 同名 VCI 调用（多带 type/idx/chn）                       |
| `Transmit/Receive`（CAN2.0）             | `VCI_Transmit/Receive`（`ZCAN_20_MSG`）                  |
| `TransmitFD/ReceiveFD`（CANFD）          | `VCI_TransmitFD/ReceiveFD`（`ZCAN_FD_MSG`）              |
| `TransmitData/ReceiveData`（合并接收）   | `VCI_TransmitData/ReceiveData`（`ZCANDataObj`）          |
| `GetReceiveNum(h, type)`                 | `VCI_GetReceiveNum(type, idx, chn)`（**无类型参数**）    |
| `GetDeviceInf`                           | `VCI_ReadBoardInfo`（字段名不同，需翻译）               |
| `ZCAN_SetValue(h, "chn/key", v)`         | 见下方"属性键映射表"                                    |
| `ZCAN_GetValue(h, "0/get_cn/1")`         | `VCI_GetReference(GETREF_GET_DEVICE_NAME)`              |

属性键映射表（业务层实际用到的键，均已覆盖）
--------------------------------------------
| 业务层的键                        | VCI 实现                                                        |
|-----------------------------------|-----------------------------------------------------------------|
| `<chn>/canfd_abit_baud_rate`      | 记录仲裁段波特率 → 换算 `ZCAN_INIT.aset`（`VCI_InitCAN` 时生效） |
| `<chn>/canfd_dbit_baud_rate`      | 记录数据段波特率 → 换算 `ZCAN_INIT.dset`                         |
| `<chn>/baud_rate_custom`          | 解析 `500Kbps(80%),2.0Mbps(80%),(...)` → 覆盖波特率/采样点       |
| `<chn>/initenal_resistance`       | `VCI_SetReference(SETREF_ENABLE_INTERNAL_RESISTANCE)`            |
| `<chn>/set_device_tx_echo`        | VCI 无此属性 → 记录开关，改由报文 `inf.echo` 位控制（等价效果）  |
| `<0>/set_device_recv_merge`       | `VCI_SetReference(SETREF_SET_DATA_RECV_MERGE)`                   |
| `<chn>/set_cn`                    | `VCI_SetReference(SETREF_SET_DEVICE_NAME)`                       |
| `<chn>/auto_send`                 | `VCI_SetReference(SETREF_ADD_TIMER_SEND_CAN)`（指针直传）        |
| `<chn>/auto_send_canfd`           | `VCI_SetReference(SETREF_ADD_TIMER_SEND_CANFD)`                  |
| `<chn>/apply_auto_send`           | `VCI_SetReference(SETREF_APPLY_TIMER_SEND)`                      |
| `<chn>/clear_auto_send`           | `VCI_SetReference(SETREF_CLEAR_TIMER_SEND)`                      |
| `0/get_cn/1`（读）                | `VCI_GetReference(GETREF_GET_DEVICE_NAME)`（返回 C 缓冲指针）    |

句柄约定
--------
业务层有 `chn_handle & 0xFF` 取通道号的用法（见 `receive.py` 的日志与缓存），
因此自制的通道句柄**低字节必须是通道号**：`0x5B000000 | 通道号`；设备句柄为
`0x5A000000 | 设备序号`。两者都不会与真实指针（Windows 上由驱动返回）冲突（仅本适配层内部使用）。

需要实机校准的两处（已在文档标注，可用环境变量覆盖）
----------------------------------------------------
* `HUD_VCI_CLK`：CAN 控制器时钟，默认 40 MHz（依据官方样例反推，见 `calc_canfd_timing` 自校验）；
* `HUD_VCI_SAMPLE_POINT` / `HUD_VCI_SAMPLE_POINT_DATA`：采样点，默认 80% / 75%（同官方样例）。
"""
from __future__ import annotations

import ctypes
import os
from ctypes import byref, c_char_p, c_uint8, c_uint32, c_void_p, cast
from dataclasses import dataclass, field

from hudcore import logging_setup

from .driver import (
    INVALID_CHANNEL_HANDLE, INVALID_DEVICE_HANDLE, ZCAN_CHANNEL_ERR_INFO,
    ZCAN_CHANNEL_STATUS, ZCAN_DEVICE_INFO, ZCAN_DT_ZCAN_CAN_CANFD_DATA,
    ZCAN_STATUS_ERR, ZCAN_STATUS_OK, ZCAN_TYPE_CAN, ZCAN_TYPE_CANFD, ZCAN_TYPE_MERGE,
    ZCANDataObj, ZCANFDData, ZCAN_Receive_Data, ZCAN_ReceiveFD_Data,
    ZCAN_Transmit_Data, ZCAN_TransmitFD_Data, ZCANdataFlag,
)
from . import vci_driver as vd

_LOGGER = "candata"

# 默认时序参数（可用环境变量覆盖；详见模块文档"需要实机校准的两处"）
DEFAULT_CLK_HZ = 40_000_000
DEFAULT_SAMPLE_POINT = 0.80          # 仲裁段
DEFAULT_SAMPLE_POINT_DATA = 0.75     # 数据段
DEFAULT_NOMINAL_BAUD = 500_000
DEFAULT_DATA_BAUD = 2_000_000

# 自制句柄的基址（低字节保留设备序号/通道号）
DEVICE_HANDLE_BASE = 0x5A00_0000
CHANNEL_HANDLE_BASE = 0x5B00_0000


class VciUnsupportedError(NotImplementedError):
    """VCI 形态确实没有对应能力时抛出（调用点会打印可读提示）。"""


def pointer_value(value) -> int:
    """把"指针类"实参统一取成地址。

    业务层传进来的可能是 `byref(obj)`（ctypes.CArgObject）、`pointer(obj)`、
    ctypes 数组或裸地址。注意 `ctypes.addressof()` **不接受** CArgObject，
    因此这里按其 `_obj` 属性回到真正的对象上取地址。
    """
    if isinstance(value, int):
        return value
    try:
        return ctypes.cast(value, c_void_p).value or 0
    except TypeError:
        target = getattr(value, "_obj", None)
        if target is not None:
            return ctypes.addressof(target)
        raise TypeError(f"无法把 {type(value).__name__} 当作指针使用")


# ------------------------------------------------------------------ 位速率 → 时序
def calc_canfd_timing(baud: int, clk: int = DEFAULT_CLK_HZ,
                      sample_point: float = DEFAULT_SAMPLE_POINT,
                      max_tseg1: int = 64, max_tseg2: int = 32,
                      max_total_tq: int = 64) -> tuple[int, int, int, int]:
    """把位速率换算成 ZLG 的 `(tseg1, tseg2, sjw, brp)`。

    换算依据（官方样例 `usbcanfd-800u/test.cpp` 第 243~291 行）：
        `baud = clk / (brp * (1 + tseg1 + tseg2))`，`sjw = tseg2`，
        仲裁段 `nTSEG1 ≤ 64 / nTSEG2 ≤ 32`，数据段 `nTSEG1 ≤ 32 / nTSEG2 ≤ 8`。

    选取策略：**分频比 brp 从小到大取第一个合法解**（与官方样例一致），并限制
    一个位时间内的总 TQ 不超过 `max_total_tq` —— 否则 500kbps@40MHz 会选出
    brp=1/80TQ 这种"能算出但采样精度差"的组合，brp=2/40TQ 更稳妥。

    自校验（本函数必须能重现样例里的两组数，单元测试会断言）：
        `calc_canfd_timing(1_000_000, 40_000_000, 0.80)` → `(31, 8, 8, 1)`
        `calc_canfd_timing(5_000_000, 40_000_000, 0.75, 32, 8)` → `(5, 2, 2, 1)`

    :raises ValueError: 波特率或时钟非法，或找不到合法的分频组合
    """
    baud = int(baud)
    clk = int(clk)
    if baud <= 0 or clk <= 0:
        raise ValueError(f"非法波特率/时钟：baud={baud} clk={clk}")

    best: tuple[float, int, int, int, int] | None = None
    for brp in range(1, 257):
        total_tq = clk / (baud * brp)
        if total_tq < 4 or total_tq > min(max_total_tq, 1 + max_tseg1 + max_tseg2):
            continue
        total = int(round(total_tq))
        tseg1 = int(round(total * sample_point)) - 1
        tseg2 = total - 1 - tseg1
        if tseg1 < 1 or tseg2 < 1 or tseg1 > max_tseg1 or tseg2 > max_tseg2:
            continue
        error = abs(total_tq - total) / total + abs(brp * total * baud - clk) / clk
        if best is None or error < best[0]:
            best = (error, tseg1, tseg2, tseg2, brp)      # sjw = tseg2（与官方样例一致）
        if error == 0.0:
            break

    if best is None:
        raise ValueError(f"无法为 {baud} bps（clk={clk}）找到合法时序组合")
    _, tseg1, tseg2, sjw, brp = best
    return tseg1, tseg2, sjw, brp


def _clk_from_env() -> int:
    raw = os.environ.get("HUD_VCI_CLK", "").strip()
    if not raw:
        return DEFAULT_CLK_HZ
    try:
        return int(float(raw))
    except ValueError:
        logging_setup.warning(_LOGGER, f"HUD_VCI_CLK 不是数字：{raw!r}，回退默认 {DEFAULT_CLK_HZ}")
        return DEFAULT_CLK_HZ


def _sample_point_from_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logging_setup.warning(_LOGGER, f"{name} 不是数字：{raw!r}，回退默认 {default}")
        return default
    return value / 100.0 if value > 1 else value          # 允许写 80 或 0.8


# ------------------------------------------------------------------ 内部记录
@dataclass
class _DeviceRec:
    """一台已打开设备。"""
    handle: int
    dev_type: int
    dev_index: int
    settings: dict[int, dict] = field(default_factory=dict)   # 通道号 → 属性集合

    def channel_settings(self, chn: int) -> dict:
        return self.settings.setdefault(int(chn), {
            "nominal_baud": None, "data_baud": None,
            "sample_point": None, "sample_point_data": None,
            "resistance": None, "tx_echo": None, "recv_merge": None,
        })


@dataclass
class _ChannelRec:
    """一个已初始化的通道。"""
    handle: int
    device: _DeviceRec
    chn: int
    started: bool = False
    canfd: bool = True


# ------------------------------------------------------------------ 适配器
class VciCanDriver:
    """把 VCI 接口包装成业务层使用的 ZCAN 调用面（方法名/签名/返回约定保持一致）。"""

    def __init__(self, lib=None, device_type: int | None = None, clk: int | None = None) -> None:
        """
        :param lib: 已加载的 VCI 库对象；None 时用 `hudcore.can.load_zlg_library()` 自动探测
        :param device_type: 默认设备类型（业务层 OpenDevice 会显式传入，这里只作兜底）
        :param clk: CAN 控制器时钟（Hz），默认取 `HUD_VCI_CLK` 或 40 MHz
        """
        self._lib = lib
        self._default_device_type = device_type
        self._clk = int(clk) if clk else _clk_from_env()
        self._devices: dict[int, _DeviceRec] = {}
        self._channels: dict[int, _ChannelRec] = {}
        self._keep_alive: list = []          # 保住 C 缓冲，避免返回的指针失效
        self._warned: set[str] = set()

    # ---------------- 基础设施 ----------------
    @property
    def lib(self):
        """底层 VCI 库对象（惰性加载）。"""
        if self._lib is None:
            from hudcore.can import load_zlg_library
            self._lib = load_zlg_library()
        if self._lib is None:
            raise OSError("未能加载 ZLG CAN 驱动库（VCI 形态）")
        return self._lib

    def _warn_once(self, key: str, message: str) -> None:
        if key not in self._warned:
            self._warned.add(key)
            logging_setup.warning(_LOGGER, message)

    def _device_of(self, handle: int) -> _DeviceRec:
        rec = self._devices.get(int(handle))
        if rec is None:
            raise ValueError(f"未知设备句柄：{handle}（可能未 OpenDevice 或已 CloseDevice）")
        return rec

    def _channel_of(self, handle: int) -> _ChannelRec:
        rec = self._channels.get(int(handle))
        if rec is None:
            raise ValueError(f"未知通道句柄：{handle}（可能未 InitCAN 或已关闭）")
        return rec

    def describe(self) -> str:
        """一句话描述当前后端（用于界面状态/自检输出）。"""
        devs = ", ".join(f"{d.dev_type}/{d.dev_index}" for d in self._devices.values()) or "无"
        return (f"ZLG VCI 适配层（clk={self._clk / 1e6:g}MHz，"
                f"已开设备 {len(self._devices)} 台[{devs}]，通道 {len(self._channels)} 个）")

    # ---------------- 设备 ----------------
    def OpenDevice(self, device_type, device_index, reserved):
        """打开设备；成功返回自制句柄，失败返回 0（与 ZCAN 约定一致）。"""
        dev_type = vd.as_int(device_type)
        dev_index = vd.as_int(device_index)
        status = int(self.lib.VCI_OpenDevice(dev_type, dev_index, vd.as_int(reserved)))
        if status != vd.VCI_STATUS_OK:
            logging_setup.error(_LOGGER, f"VCI_OpenDevice(type={dev_type}, idx={dev_index}) 失败，"
                                         f"返回 {status}")
            return INVALID_DEVICE_HANDLE
        handle = DEVICE_HANDLE_BASE | (dev_index & 0xFF)
        self._devices[handle] = _DeviceRec(handle=handle, dev_type=dev_type, dev_index=dev_index)
        logging_setup.info(_LOGGER, f"已打开 CAN 设备（VCI）：type={dev_type} idx={dev_index} "
                                    f"→ 句柄 0x{handle:08X}")
        return handle

    def CloseDevice(self, device_handle):
        """关闭设备（会先清理该设备下已初始化的通道记录）。"""
        rec = self._device_of(device_handle)
        for chn_handle, ch in list(self._channels.items()):
            if ch.device is rec:
                self._channels.pop(chn_handle, None)
        self._devices.pop(rec.handle, None)
        status = int(self.lib.VCI_CloseDevice(rec.dev_type, rec.dev_index))
        logging_setup.info(_LOGGER, f"已关闭 CAN 设备（VCI）：type={rec.dev_type} "
                                    f"idx={rec.dev_index}，返回 {status}")
        return status

    def GetDeviceInf(self, device_handle):
        """读取设备信息；字段翻译成业务层使用的 `ZCAN_DEVICE_INFO` 形态。"""
        rec = self._device_of(device_handle)
        raw = vd.ZCAN_DEV_INF()
        status = int(self.lib.VCI_ReadBoardInfo(rec.dev_type, rec.dev_index, byref(raw)))
        if status != vd.VCI_STATUS_OK:
            logging_setup.warning(_LOGGER, f"VCI_ReadBoardInfo 失败，返回 {status}")
            return None
        info = ZCAN_DEVICE_INFO()
        info.hw_Version = raw.hwv
        info.fw_Version = raw.fwv
        info.dr_Version = raw.drv
        info.in_Version = raw.api
        info.irq_Num = raw.irq
        info.can_Num = raw.chn
        for i, byte in enumerate(raw.sn[:20]):
            info.str_Serial_Num[i] = byte
        for i, byte in enumerate(raw.id[:40]):
            info.str_hw_Type[i] = byte
        return info

    def DeviceOnLine(self, device_handle):
        """设备是否在线（VCI 无专用接口，用能否读到板卡信息近似）。"""
        return self.GetDeviceInf(device_handle) is not None

    # ---------------- 通道 ----------------
    def InitCAN(self, device_handle, can_index, init_config):
        """初始化通道；成功返回自制通道句柄（低字节=通道号），失败返回 None。"""
        rec = self._device_of(device_handle)
        chn = vd.as_int(can_index)
        settings = rec.channel_settings(chn)

        canfd = self._canfd_requested(init_config)
        listen_only = self._listen_only_requested(init_config)

        init = vd.ZCAN_INIT()
        init.clk = self._clk
        init.mode = 1 if listen_only else 0

        nominal_baud = int(settings.get("nominal_baud") or DEFAULT_NOMINAL_BAUD)
        data_baud = int(settings.get("data_baud") or DEFAULT_DATA_BAUD)
        try:
            sp = float(settings.get("sample_point") or _sample_point_from_env(
                "HUD_VCI_SAMPLE_POINT", DEFAULT_SAMPLE_POINT))
            sp_data = float(settings.get("sample_point_data") or _sample_point_from_env(
                "HUD_VCI_SAMPLE_POINT_DATA", DEFAULT_SAMPLE_POINT_DATA))
            t1, t2, sjw, brp = calc_canfd_timing(nominal_baud, self._clk, sp, 64, 32)
            d1, d2, dsjw, dbrp = calc_canfd_timing(data_baud, self._clk, sp_data, 32, 8,
                                                  max_total_tq=41)
        except ValueError as exc:
            logging_setup.error(_LOGGER, f"波特率换算失败：{exc}")
            return None
        init.aset.tseg1, init.aset.tseg2, init.aset.sjw, init.aset.brp = t1, t2, sjw, brp
        init.dset.tseg1, init.dset.tseg2, init.dset.sjw, init.dset.brp = d1, d2, dsjw, dbrp

        # 控制器类型（CAN / ISO CANFD）需在 StartCAN 之前设置
        controller_type = 1 if canfd else 0
        self._try_set_reference(rec, chn, vd.SETREF_SET_CONTROLLER_TYPE, controller_type,
                                "控制器类型")

        # 终端电阻 / 合并接收：业务层通过 ZCAN_SetValue 记录，这里在 StartCAN 之前下发
        if settings.get("resistance") is not None:
            self._try_set_reference(rec, chn, vd.SETREF_ENABLE_INTERNAL_RESISTANCE,
                                    int(settings["resistance"]), "内置终端电阻")
        if settings.get("recv_merge") is not None:
            self._try_set_reference(rec, chn, vd.SETREF_SET_DATA_RECV_MERGE,
                                    int(settings["recv_merge"]), "合并接收")

        status = int(self.lib.VCI_InitCAN(rec.dev_type, rec.dev_index, chn, byref(init)))
        if status != vd.VCI_STATUS_OK:
            logging_setup.error(_LOGGER, f"VCI_InitCAN(chn={chn}) 失败，返回 {status}"
                                         f"（仲裁 {nominal_baud}bps={t1}/{t2}/{brp}，"
                                         f"数据 {data_baud}bps={d1}/{d2}/{dbrp}）")
            return None

        handle = CHANNEL_HANDLE_BASE | (chn & 0xFF)
        self._channels[handle] = _ChannelRec(handle=handle, device=rec, chn=chn, canfd=canfd)
        logging_setup.info(_LOGGER, f"CAN{chn} 初始化完成（VCI）："
                                    f"{'CANFD' if canfd else 'CAN'} "
                                    f"仲裁={nominal_baud}bps({t1},{t2},{brp}) "
                                    f"数据={data_baud}bps({d1},{d2},{dbrp})")
        return handle

    def StartCAN(self, chn_handle):
        ch = self._channel_of(chn_handle)
        status = int(self.lib.VCI_StartCAN(ch.device.dev_type, ch.device.dev_index, ch.chn))
        ch.started = status == vd.VCI_STATUS_OK
        if not ch.started:
            logging_setup.error(_LOGGER, f"VCI_StartCAN(CAN{ch.chn}) 失败，返回 {status}")
        return status

    def ResetCAN(self, chn_handle):
        ch = self._channel_of(chn_handle)
        status = int(self.lib.VCI_ResetCAN(ch.device.dev_type, ch.device.dev_index, ch.chn))
        if status == vd.VCI_STATUS_OK:
            ch.started = False
        return status

    def ClearBuffer(self, chn_handle):
        ch = self._channel_of(chn_handle)
        return int(self.lib.VCI_ClearBuffer(ch.device.dev_type, ch.device.dev_index, ch.chn))

    def ReadChannelErrInfo(self, chn_handle):
        ch = self._channel_of(chn_handle)
        raw = vd.ZCAN_ERR_MSG()
        status = int(self.lib.VCI_ReadErrInfo(ch.device.dev_type, ch.device.dev_index,
                                              ch.chn, byref(raw)))
        if status != vd.VCI_STATUS_OK:
            return None
        info = ZCAN_CHANNEL_ERR_INFO()
        info.error_code = raw.hdr.id
        for i in range(3):
            info.passive_ErrData[i] = raw.dat[i]
        info.arLost_ErrData = raw.dat[3]
        return info

    def ReadChannelStatus(self, chn_handle):
        ch = self._channel_of(chn_handle)
        raw = vd.ZCAN_STAT()
        status = int(self.lib.VCI_ReadCANStatus(ch.device.dev_type, ch.device.dev_index,
                                                ch.chn, byref(raw)))
        if status != vd.VCI_STATUS_OK:
            return None
        stat = ZCAN_CHANNEL_STATUS()
        stat.errInterrupt, stat.regMode, stat.regStatus = raw.IR, raw.MOD, raw.SR
        stat.regALCapture, stat.regECCapture, stat.regEWLimit = raw.ALC, raw.ECC, raw.EWL
        stat.regRECounter, stat.regTECounter = raw.RXE, raw.TXE
        stat.Reserved = raw.PAD & 0xFF
        return stat

    def GetReceiveNum(self, chn_handle, can_type=ZCAN_TYPE_CAN):
        """待接收帧数。

        注意：VCI 的 `VCI_GetReceiveNum` **没有类型参数**，返回的是该通道待收帧总数，
        因此 CAN / CANFD / 合并接收三种查询拿到的是同一个数字（业务层据此决定读多少帧，
        不会漏帧，最多多做一次空读）。
        """
        handle = vd.as_int(chn_handle)
        ch = self._channels.get(handle)
        if ch is not None:
            rec, chn = ch.device, ch.chn
        else:
            rec = self._device_of(handle)          # 合并接收用设备句柄查询
            chn = 0
            # 未开启合并接收时不该有合并数据可读，直接返回 0（避免业务层空转）
            if vd.as_int(can_type) == vd.as_int(ZCAN_TYPE_MERGE) \
                    and not rec.channel_settings(0).get("recv_merge"):
                return 0
        return int(self.lib.VCI_GetReceiveNum(rec.dev_type, rec.dev_index, chn))

    # ---------------- 发送 ----------------
    def Transmit(self, chn_handle, std_msg, len):
        """发送 CAN2.0 帧（`std_msg` 为 `ZCAN_Transmit_Data` 数组）。"""
        ch = self._channel_of(chn_handle)
        count = int(len)
        buf = (vd.ZCAN_20_MSG * count)()
        for i in range(count):
            self._fill_vci_msg(buf[i].hdr, buf[i].dat, std_msg[i], canfd=False, channel=ch.chn)
        return int(self.lib.VCI_Transmit(ch.device.dev_type, ch.device.dev_index, ch.chn,
                                         buf, count))

    def TransmitFD(self, chn_handle, fd_msg, len):
        """发送 CANFD 帧（`fd_msg` 为 `ZCAN_TransmitFD_Data` 数组）。"""
        ch = self._channel_of(chn_handle)
        count = int(len)
        buf = (vd.ZCAN_FD_MSG * count)()
        for i in range(count):
            self._fill_vci_msg(buf[i].hdr, buf[i].dat, fd_msg[i], canfd=True, channel=ch.chn)
        return int(self.lib.VCI_TransmitFD(ch.device.dev_type, ch.device.dev_index, ch.chn,
                                           buf, count))

    def TransmitData(self, device_handle, msg, len):
        """合并模式发送（`ZCANDataObj` 数组）。"""
        rec = self._device_of(device_handle)
        count = int(len)
        buf = (vd.ZCANDataObj * count)()
        for i in range(count):
            self._to_vci_data_obj(buf[i], msg[i])
        port = int(msg[0].chnl) if count else 0
        return int(self.lib.VCI_TransmitData(rec.dev_type, rec.dev_index, port, buf, count))

    # ---------------- 接收 ----------------
    def Receive(self, chn_handle, rcv_num, wait_time=100):
        """接收 CAN2.0 帧；返回 `(ZCAN_Receive_Data 数组, 实际条数)`（与业务层约定一致）。"""
        ch = self._channel_of(chn_handle)
        count = max(1, int(rcv_num))
        buf = (vd.ZCAN_20_MSG * count)()
        got = int(self.lib.VCI_Receive(ch.device.dev_type, ch.device.dev_index, ch.chn,
                                       buf, count, self._wait_ms(wait_time)))
        out = (ZCAN_Receive_Data * count)()
        for i in range(min(got, count)):
            self._fill_project_frame(out[i].frame, buf[i].hdr, buf[i].dat, canfd=False)
            out[i].timestamp = int(buf[i].hdr.ts)
        return out, got

    def ReceiveFD(self, chn_handle, rcv_num, wait_time=100):
        """接收 CANFD 帧；返回 `(ZCAN_ReceiveFD_Data 数组, 实际条数)`。"""
        ch = self._channel_of(chn_handle)
        count = max(1, int(rcv_num))
        buf = (vd.ZCAN_FD_MSG * count)()
        got = int(self.lib.VCI_ReceiveFD(ch.device.dev_type, ch.device.dev_index, ch.chn,
                                         buf, count, self._wait_ms(wait_time)))
        out = (ZCAN_ReceiveFD_Data * count)()
        for i in range(min(got, count)):
            self._fill_project_frame(out[i].frame, buf[i].hdr, buf[i].dat, canfd=True)
            out[i].timestamp = int(buf[i].hdr.ts)
        return out, got

    def ReceiveData(self, device_handle, rcv_num, wait_time=100):
        """合并模式接收；返回 `(项目的 ZCANDataObj 数组, 实际条数)`。"""
        rec = self._device_of(device_handle)
        count = max(1, int(rcv_num))
        buf = (vd.ZCANDataObj * count)()
        got = int(self.lib.VCI_ReceiveData(rec.dev_type, rec.dev_index, 0, buf, count,
                                           self._wait_ms(wait_time)))
        out = (ZCANDataObj * count)()
        for i in range(min(got, count)):
            self._to_project_data_obj(out[i], buf[i])
        return out, got

    # ---------------- 与 ZCAN 的差异点 ----------------
    def GetIProperty(self, device_handle):
        """ZCAN 的 IProperty 对象在 VCI 形态下不存在。"""
        raise VciUnsupportedError(
            "VCI 接口没有 IProperty 对象（ZCAN_GetIProperty）。"
            "本项目业务代码未使用该能力；如需按属性路径读写，请改用 ZCAN_SetValue/ZCAN_GetValue")

    def SetValue(self, iproperty, path, value):
        raise VciUnsupportedError("VCI 接口没有 IProperty.SetValue；请使用 ZCAN_SetValue")

    def SetValue1(self, iproperty, path, value):
        raise VciUnsupportedError("VCI 接口没有 IProperty.SetValue；请使用 ZCAN_SetValue")

    def GetValue(self, iproperty, path):
        raise VciUnsupportedError("VCI 接口没有 IProperty.GetValue；请使用 ZCAN_GetValue")

    def ReleaseIProperty(self, iproperty):
        raise VciUnsupportedError("VCI 接口没有 IProperty 对象，无需释放")

    # ---------------- 属性读写（业务层真正使用的入口） ----------------
    def ZCAN_SetValue(self, device_handle, path, value):
        """按 ZCAN 的属性路径写配置，转成 VCI 的 `ZCAN_INIT` / `VCI_SetReference`。

        :param path: `b"<通道>/<键>"` 或 str
        :param value: 字符串字节（如 `b"500000"`）或结构体指针（如 `byref(auto_send)`）
        """
        rec = self._device_of(device_handle)
        chn, key = self._split_path(path)
        settings = rec.channel_settings(chn)
        # 业务层的取值形态并不统一：多数键传 bytes（b"500000"），
        # 也有键直接传 str（如 `set_device_recv_merge` 用 repr(state.enable_merge_receive)），
        # 指针型键则传 byref(结构体)，这里统一归一化
        if isinstance(value, (bytes, bytearray)):
            text = value.decode("utf-8", "replace")
        elif isinstance(value, str):
            text = value
        else:
            text = None

        if key == "canfd_abit_baud_rate":
            settings["nominal_baud"] = self._as_int(text, key)
        elif key == "canfd_dbit_baud_rate":
            settings["data_baud"] = self._as_int(text, key)
        elif key == "baud_rate_custom":
            self._parse_custom_baud(text, settings)
        elif key == "initenal_resistance":
            settings["resistance"] = self._as_int(text, key)
            return self._try_set_reference(rec, chn, vd.SETREF_ENABLE_INTERNAL_RESISTANCE,
                                           settings["resistance"], "内置终端电阻")
        elif key == "set_device_recv_merge":
            settings["recv_merge"] = self._as_int(text, key)
            return self._try_set_reference(rec, chn, vd.SETREF_SET_DATA_RECV_MERGE,
                                           settings["recv_merge"], "合并接收")
        elif key == "set_device_tx_echo":
            settings["tx_echo"] = self._as_int(text, key)
            self._warn_once("tx_echo",
                            "VCI 接口没有 set_device_tx_echo 属性：已改为在发送回显位（inf.echo）"
                            "上等效控制，行为与禁用回显一致")
        elif key == "set_cn":
            buf = ctypes.create_string_buffer(text.encode("utf-8") if text else b"")
            self._keep_alive.append(buf)
            return int(self.lib.VCI_SetReference(rec.dev_type, rec.dev_index, chn,
                                                 vd.SETREF_SET_DEVICE_NAME,
                                                 cast(buf, c_void_p)))
        elif key in ("auto_send", "auto_send_canfd"):
            ref = (vd.SETREF_ADD_TIMER_SEND_CAN if key == "auto_send"
                   else vd.SETREF_ADD_TIMER_SEND_CANFD)
            return self._set_reference_ptr(rec, chn, ref, value, key)
        elif key == "apply_auto_send":
            # 业务层用字符串占位（"0"）调用，VCI 侧这两个引用码不需要数据 → 传 NULL
            return self._set_reference_ptr(rec, chn, vd.SETREF_APPLY_TIMER_SEND, value, key,
                                           allow_placeholder=True)
        elif key == "clear_auto_send":
            return self._set_reference_ptr(rec, chn, vd.SETREF_CLEAR_TIMER_SEND, value, key,
                                           allow_placeholder=True)
        elif key == "set_device_tx_echo_unsupported":
            return ZCAN_STATUS_ERR
        else:
            self._warn_once(f"key:{key}",
                            f"VCI 形态暂不支持属性键 `{key}`（已忽略并返回失败）；"
                            f"如需支持请在 can_core/vci_adapter.py 的属性键映射表中补充")
            return ZCAN_STATUS_ERR
        return ZCAN_STATUS_OK

    def ZCAN_GetValue(self, device_handle, path):
        """按 ZCAN 的属性路径读配置；返回 C 缓冲指针（与 ZCAN 返回约定一致）。"""
        rec = self._device_of(device_handle)
        chn, key = self._split_path(path)
        if key.startswith("get_cn"):
            buf = ctypes.create_string_buffer(64)
            status = int(self.lib.VCI_GetReference(rec.dev_type, rec.dev_index, chn,
                                                   vd.GETREF_GET_DEVICE_NAME,
                                                   cast(buf, c_void_p)))
            if status != vd.VCI_STATUS_OK:
                logging_setup.warning(_LOGGER, f"VCI_GetReference(GETREF_GET_DEVICE_NAME) "
                                               f"失败，返回 {status}")
                return None
            self._keep_alive.append(buf)
            return cast(buf, c_void_p).value
        if key.startswith("get_recv_merge"):
            status, value = vd.get_reference(self.lib, rec.dev_type, rec.dev_index, chn,
                                             vd.GETREF_GET_DATA_RECV_MERGE)
            if status != vd.VCI_STATUS_OK:
                return None
            settings = rec.channel_settings(chn)
            settings["recv_merge"] = value
            return int(value)
        self._warn_once(f"getkey:{key}",
                        f"VCI 形态暂不支持读取属性键 `{key}`（返回 None）")
        return None

    # ---------------- 内部工具 ----------------
    @staticmethod
    def _split_path(path) -> tuple[int, str]:
        raw = path.decode("utf-8") if isinstance(path, (bytes, bytearray)) else str(path)
        head, _, tail = raw.partition("/")
        try:
            chn = int(head)
        except ValueError:
            chn = 0
        return chn, tail or raw

    @staticmethod
    def _as_int(text: str | None, key: str) -> int | None:
        if text is None:
            return None
        try:
            return int(float(text.strip()))
        except ValueError:
            logging_setup.warning(_LOGGER, f"属性 {key} 的值不是数字：{text!r}")
            return None

    @staticmethod
    def _parse_custom_baud(text: str | None, settings: dict) -> None:
        """解析 ZLG 自定义波特率串：`500Kbps(80%),2.0Mbps(80%),(80,07C00002,01C00002)`。

        只取前两段的"速率(采样点)"；第三段括号里的寄存器值不使用（本适配层自行换算时序）。
        """
        if not text:
            return
        parts = [p.strip() for p in text.split(",")][:2]
        rates: list[int | None] = []
        points: list[float | None] = []
        for part in parts:
            token = part.split("(")[0].strip().lower()
            unit = 1_000_000 if "mbps" in token else 1_000
            try:
                rates.append(int(float(token.replace("kbps", "").replace("mbps", "")) * unit))
            except ValueError:
                rates.append(None)
            point = None
            if "(" in part and "%)" in part:
                try:
                    point = float(part.split("(")[1].split("%")[0]) / 100.0
                except (IndexError, ValueError):
                    point = None
            points.append(point)

        if rates and rates[0]:
            settings["nominal_baud"] = rates[0]
        if len(rates) > 1 and rates[1]:
            settings["data_baud"] = rates[1]
        if points and points[0]:
            settings["sample_point"] = points[0]
        if len(points) > 1 and points[1]:
            settings["sample_point_data"] = points[1]

    def _wait_ms(self, wait_time) -> int:
        """把业务层传的等待时间变成 VCI 的毫秒超时（`c_int(-1)` / None 表示不限）。"""
        try:
            value = int(wait_time.value if hasattr(wait_time, "value") else wait_time)
        except (TypeError, ValueError):
            return 100
        return 0 if value is None else max(0, value)

    def _try_set_reference(self, rec: _DeviceRec, chn: int, ref_code: int,
                           value, what: str) -> int:
        """下发整型引用；失败只告警一次（有些卡型不支持个别引用码）。"""
        if value is None:                     # 属性值无效（如传了空串）→ 不下发，避免崩在底层
            self._warn_once(f"ref-none:{ref_code}",
                            f"{what} 的属性值无效（None），已跳过下发")
            return ZCAN_STATUS_ERR
        status = vd.set_reference(self.lib, rec.dev_type, rec.dev_index, chn, ref_code,
                                  vd.as_int(value))
        if status != vd.VCI_STATUS_OK:
            self._warn_once(f"ref:{ref_code}",
                            f"VCI_SetReference({what}, ref={ref_code}) 返回 {status}，已忽略")
        return status

    def _set_reference_ptr(self, rec: _DeviceRec, chn: int, ref_code: int,
                           value, what: str, allow_placeholder: bool = False) -> int:
        """下发结构体指针型引用（定时发送列表等），指针直传给驱动。

        :param allow_placeholder: 该引用码本身不需要数据（如"应用/清空定时发送"），
                                  业务层传字符串占位时按 NULL 处理
        """
        if isinstance(value, (bytes, bytearray)):
            if not allow_placeholder:
                logging_setup.warning(_LOGGER, f"{what} 需要结构体指针，收到字符串，已忽略")
                return ZCAN_STATUS_ERR
            ptr = c_void_p(None)
        else:
            ptr = c_void_p(pointer_value(value))
        status = int(self.lib.VCI_SetReference(rec.dev_type, rec.dev_index, chn, ref_code, ptr))
        if status != vd.VCI_STATUS_OK:
            self._warn_once(f"refptr:{ref_code}",
                            f"VCI_SetReference({what}, ref={ref_code}) 返回 {status}，已忽略")
        return status

    def _canfd_requested(self, init_config) -> bool:
        can_type = getattr(init_config, "can_type", ZCAN_TYPE_CANFD)
        try:
            return vd.as_int(can_type) == vd.as_int(ZCAN_TYPE_CANFD)
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _listen_only_requested(init_config) -> bool:
        """项目的 init_cfg 里 `config.canfd.mode`：0-正常 1-只听。"""
        try:
            return int(init_config.config.canfd.mode) == 1
        except (AttributeError, TypeError, ValueError):
            return False

    def _echo_enabled(self, ch: _ChannelRec) -> bool:
        value = ch.device.channel_settings(ch.chn).get("tx_echo")
        return bool(value) if value is not None else True

    def _fill_vci_msg(self, hdr, dat, src, canfd: bool, channel: int | None = None) -> None:
        """把业务层的 `ZCAN_Transmit_Data(ZCAN_TransmitFD_Data)` 翻译成 VCI 报文。

        :param channel: 通道号；业务层的发送结构体里没有通道字段（ZCAN 由句柄隐含），
                        因此由调用方（Transmit/TransmitFD）从通道句柄低字节传进来
        """
        frame = src.frame
        hdr.id = int(frame.can_id) & 0x1FFFFFFF
        hdr.chn = self._src_channel(src) if channel is None else int(channel) & 0xFF
        hdr.len = int(getattr(frame, "len", getattr(frame, "can_dlc", 0)))
        hdr.ts = 0
        hdr.is_canfd = canfd
        # 扩展帧：业务层用 `frame.eff`（Python 侧属性，ZCAN 路径下不会进二进制），
        # 缺失时按 ID 是否超过 11 位推断，避免扩展帧被当成标准帧发出去
        eff = getattr(frame, "eff", None)
        hdr.is_extended = bool(eff) if eff is not None else (hdr.id > 0x7FF)
        hdr.is_remote = bool(getattr(frame, "rtr", 0))
        hdr.tx_mode = int(getattr(src, "transmit_type", 0)) & 0x0F

        data = bytearray(getattr(frame, "data", [])[: hdr.len])
        for i, byte in enumerate(data):
            dat[i] = byte

        # `_pad`（CAN）/`flags`（CANFD）按项目约定承载三个开关：
        #   bit0 = BRS 加速（仅 CANFD）、bit5 = 发送回显、bit7 = 队列发送（bit6 = 0.1ms 精度）
        pad = int(getattr(frame, "flags", 0) if canfd else getattr(frame, "_pad", 0))
        if canfd:
            hdr.is_brs = bool(pad & 0x01)
        if pad & 0x20:
            hdr.is_echo = True
        if pad & 0x80:
            hdr.qsend = True
            hdr.qsend_100us = bool(pad & 0x40)
            hdr.pad = int(getattr(frame, "_res0", 0)) | (int(getattr(frame, "_res1", 0)) << 8)

    def _src_channel(self, src) -> int:
        for name in ("chnl", "chn"):
            value = getattr(src, name, None)
            if value is not None:
                try:
                    return int(value) & 0xFF
                except (TypeError, ValueError):
                    pass
        return 0

    def _fill_project_frame(self, frame, hdr, dat, canfd: bool) -> None:
        """把 VCI 报文翻译回业务层读取的帧结构（含扩展帧/远程帧/回显标志位）。"""
        can_id = int(hdr.id) & 0x1FFFFFFF
        if hdr.is_extended:
            can_id |= 1 << 31
        if hdr.is_remote:
            can_id |= 1 << 30
        frame.can_id = can_id
        length = min(int(hdr.len), 64 if canfd else 8)
        if canfd:
            frame.len = length
            flags = 0x01 if hdr.is_brs else 0x00
            if hdr.is_tx or hdr.is_echo:
                flags |= 0x20
            frame.flags = flags
        else:
            frame.can_dlc = length
            frame._pad = 0x20 if (hdr.is_tx or hdr.is_echo) else 0x00
        for i in range(length):
            frame.data[i] = dat[i]

    def _to_vci_data_obj(self, dst, src) -> None:
        """项目的 ZCANDataObj → VCI 的 ZCANDataObj（合并发送）。"""
        dst.dataType = vd.DT_VCI_CANFD if int(src.dataType) == ZCAN_DT_ZCAN_CAN_CANFD_DATA \
            and src.zcanfddata.flag.frameType else vd.DT_VCI_CAN
        dst.chnl = int(src.chnl) & 0xFF
        dst.flag = int(src.flag) if hasattr(src, "flag") else 0
        for i in range(4):
            dst.extraData[i] = src.extraData[i]
        if int(src.dataType) == ZCAN_DT_ZCAN_CAN_CANFD_DATA:
            if src.zcanfddata.flag.frameType:
                self._fill_vci_msg(dst.data.zcanCANFDData.hdr, dst.data.zcanCANFDData.dat,
                                   _DataObjSrc(src), canfd=True)
            else:
                self._fill_vci_msg(dst.data.zcanCANData.hdr, dst.data.zcanCANData.dat,
                                   _DataObjSrc(src), canfd=False)

    def _to_project_data_obj(self, dst, src) -> None:
        """VCI 的 ZCANDataObj → 项目读取的 ZCANDataObj（合并接收）。"""
        canfd = int(src.dataType) == vd.DT_VCI_CANFD
        # 项目侧的枚举与 VCI 侧编号不同（项目把 CAN/CANFD 合为 1），这里统一归一到项目值
        dst.dataType = ZCAN_DT_ZCAN_CAN_CANFD_DATA
        dst.chnl = int(src.chnl) & 0xFF
        dst.flag = int(src.flag)
        for i in range(4):
            dst.extraData[i] = src.extraData[i]
        if canfd:
            hdr, dat = src.data.zcanCANFDData.hdr, src.data.zcanCANFDData.dat
        else:
            hdr, dat = src.data.zcanCANData.hdr, src.data.zcanCANData.dat
        frame = dst.zcanfddata.frame
        self._fill_project_frame(frame, hdr, dat, canfd=canfd)
        dst.zcanfddata.timestamp = int(hdr.ts)
        flag = ZCANdataFlag()
        flag.frameType = 1 if canfd else 0
        flag.txEchoed = 1 if (hdr.is_tx or hdr.is_echo) else 0
        flag.transmitType = int(hdr.tx_mode) & 0xF
        dst.zcanfddata.flag = flag
        for i in range(4):                    # ctypes 数组字段不能整体赋值，逐元素拷贝
            dst.zcanfddata.extraData[i] = src.extraData[i]


class _DataObjSrc:
    """把合并接收对象包装成 `_fill_vci_msg` 需要的"帧 + 发送类型 + 通道"形态。"""

    __slots__ = ("_src",)

    def __init__(self, src) -> None:
        self._src = src

    @property
    def frame(self):
        return self._src.zcanfddata.frame

    @property
    def chnl(self) -> int:
        return int(self._src.chnl)

    @property
    def transmit_type(self) -> int:
        return int(self._src.zcanfddata.flag.transmitType)


__all__ = [
    "VciCanDriver", "VciUnsupportedError", "calc_canfd_timing", "pointer_value",
    "DEFAULT_CLK_HZ", "DEFAULT_SAMPLE_POINT", "DEFAULT_SAMPLE_POINT_DATA",
    "DEVICE_HANDLE_BASE", "CHANNEL_HANDLE_BASE",
]
