# -*- coding: utf-8 -*-
"""can_core.vci_driver —— ZLG Linux 驱动的 **VCI 接口** ctypes 绑定

为什么需要这个模块
------------------
ZLG 在不同平台上给出的 CAN 库是**两套不同形态的接口**：

    Windows  zlgcan.dll          → ZCAN 接口：ZCAN_OpenDevice() 返回"句柄"，
                                    配置走 ZCAN_SetValue(handle, "0/canfd_abit_baud_rate", "500000")
    Linux    libusbcanfd.so      → VCI 接口：没有句柄，一律用 (设备类型, 设备序号, 通道号)
                                    三元组定位；配置走 ZCAN_INIT 结构体 + VCI_SetReference()

本项目业务层（`can_core/receive.py` / `transmit.py`）按 Windows 的 ZCAN 形态编写，
因此 Linux 上直接用会"探测到库却调不通"。本模块只负责**把 VCI 接口如实绑定出来**
（结构体布局 + 函数原型），把"翻译"工作留给 `can_core/vci_adapter.py`。

结构体与原型来源
----------------
与随仓库分发的官方头文件一一对应，**不臆造布局**：

    thirdparty/zlg_can/include/usbcanfd/zcan.h     VCI_* 原型 + ZCAN_INIT / ZCAN_20_MSG /
                                                   ZCAN_FD_MSG / ZCAN_DEV_INF / ZCAN_STAT /
                                                   ZCANDataObj 定义（第 60~300、408~440 行）
    thirdparty/zlg_can/include/usbcanfd-800u/USBCANFD800U.h
                                                   SETREF_* / GETREF_* 引用码
    thirdparty/zlg_can/include/usbcanfd-800u/test.cpp
                                                   官方样例：时序位域语义（第 243~291 行）

与 ZCAN 的对应关系见 `vci_adapter.py` 头部表格。
"""
from __future__ import annotations

import ctypes
from ctypes import POINTER, Structure, Union, byref, c_int32, c_ubyte, c_uint16, c_uint32, c_void_p

# ------------------------------------------------------------------ 状态码 / 常量
# ZCAN 与 VCI 的状态码一致：1 = 成功（见 thirdparty .../zcan.h 与 controlcan.h）
VCI_STATUS_OK = 1
VCI_STATUS_ERR = 0

# 报文标志位（ZCAN_MSG_INF）取值
ZCAN_FMT_CAN2 = 0        # hdr.inf.fmt：0 = CAN2.0
ZCAN_FMT_CANFD = 1       # hdr.inf.fmt：1 = CANFD

# ZCAN_TX_MODE（thirdparty .../zcan.h 第 46~50 行）
ZCAN_TX_NORM = 0         # 正常发送
ZCAN_TX_ONCE = 1         # 单次发送
ZCAN_TX_SR_NORM = 2      # 自发自收
ZCAN_TX_SR_ONCE = 3      # 单次自发自收

# VCI_SetReference / VCI_GetReference 引用码（USBCANFD800U.h，0 表示"不指定通道"）
SETREF_SET_CONTROLLER_TYPE = 1          # uint32: 0-CAN, 1-ISO CANFD, 2-Non-ISO CANFD
SETREF_ENABLE_INTERNAL_RESISTANCE = 11   # uint32: 0-断开 1-接入内置终端电阻（StartCAN 之前）
SETREF_ADD_TIMER_SEND_CAN = 7            # pData → ZCAN_AUTO_TRANSMIT_OBJ（定时发送列表）
SETREF_ADD_TIMER_SEND_CANFD = 8          # pData → ZCANFD_AUTO_TRANSMIT_OBJ
SETREF_APPLY_TIMER_SEND = 9              # 启动定时发送
SETREF_CLEAR_TIMER_SEND = 10             # 停止并清空定时发送列表
SETREF_SET_DEVICE_NAME = 12              # char*
GETREF_GET_DEVICE_NAME = 13              # char*（调用方提供缓冲）
SETREF_SET_DATA_RECV_MERGE = 17          # uint32: 0-关闭 1-开启合并接收
GETREF_GET_DATA_RECV_MERGE = 18          # uint32

# 合并接收里的数据类型（usbcanfd/zcan.h，与旧版 Windows 头文件的编号不同，见适配层说明）
DT_VCI_CAN = 1
DT_VCI_CANFD = 2
DT_VCI_ERROR = 3
DT_VCI_LIN = 4

INVALID_DEVICE_HANDLE = 0
INVALID_CHANNEL_HANDLE = 0


def as_int(value) -> int:
    """把 `ctypes` 标量（`c_uint(41)` 等）或普通数值统一取成 Python int。

    为什么需要：项目里的设备类型/通道类型常量是 `ctypes.c_uint` 实例
    （如 `ZCAN_USBCANFD_200U = c_uint(41)`）。**Python 3.13 起**对 ctypes 标量
    调用内置 `int()` 会走缓冲区协议，得到 `b')'` 这样的字节串再解析，
    于是 `int(c_uint(41))` 直接抛 `ValueError`（3.10~3.12 则返回 41）。
    本项目要兼容 3.10~3.13，因此一律用本函数取值，不直接 `int()`。
    """
    if isinstance(value, bool) or isinstance(value, int):
        return int(value)
    inner = getattr(value, "value", None)      # ctypes 标量都有 .value
    if inner is not None and not isinstance(value, (bytes, bytearray, str)):
        return int(inner)
    if value is None:
        raise TypeError("as_int(None)：拿到空的属性值（调用方应先判空）")
    return int(value)


# ------------------------------------------------------------------ 结构体
class ZCAN_MSG_HDR(Structure):
    """CAN 报文头（zcan.h 第 101~109 行），16 字节。

    `inf` 是 32 位位域（zcan.h 第 86~99 行），ctypes 位域会引入平台差异，
    这里按 32 位整数承载，用下面的位常量读写，ABI 完全一致。
    """
    _fields_ = [("ts", c_uint32),        # 时间戳（0.1ms 或 ms，由固件决定）
                ("id", c_uint32),        # CAN ID（不含扩展帧标志）
                ("inf", c_uint32),       # ZCAN_MSG_INF 位域
                ("pad", c_uint16),       # 发送队列延时
                ("chn", c_ubyte),        # 通道号
                ("len", c_ubyte)]        # 数据长度

    # ---- inf 位域读写（位序与 zcan.h 一致：txm[0:4] fmt[4:8] sdf[8] sef[9]
    #      err[10] brs[11] est[12] tx[13] echo[14] qsend_100us[15] qsend[16]）----
    def _get_bit(self, shift: int, width: int = 1) -> int:
        return (self.inf >> shift) & ((1 << width) - 1)

    def _set_bit(self, shift: int, width: int, value: int) -> None:
        mask = ((1 << width) - 1) << shift
        self.inf = (self.inf & ~mask) | ((int(value) << shift) & mask)

    @property
    def tx_mode(self) -> int:
        return self._get_bit(0, 4)

    @tx_mode.setter
    def tx_mode(self, value: int) -> None:
        self._set_bit(0, 4, value)

    @property
    def is_canfd(self) -> bool:
        return bool(self._get_bit(4, 4))

    @is_canfd.setter
    def is_canfd(self, value: bool) -> None:
        self._set_bit(4, 4, ZCAN_FMT_CANFD if value else ZCAN_FMT_CAN2)

    @property
    def is_remote(self) -> bool:
        return bool(self._get_bit(8))

    @is_remote.setter
    def is_remote(self, value: bool) -> None:
        self._set_bit(8, 1, bool(value))

    @property
    def is_extended(self) -> bool:
        return bool(self._get_bit(9))

    @is_extended.setter
    def is_extended(self, value: bool) -> None:
        self._set_bit(9, 1, bool(value))

    @property
    def is_error(self) -> bool:
        return bool(self._get_bit(10))

    @property
    def is_brs(self) -> bool:
        return bool(self._get_bit(11))

    @is_brs.setter
    def is_brs(self, value: bool) -> None:
        self._set_bit(11, 1, bool(value))

    @property
    def is_tx(self) -> bool:
        """本帧是否为发送帧（回显）。"""
        return bool(self._get_bit(13))

    @property
    def is_echo(self) -> bool:
        return bool(self._get_bit(14))

    @is_echo.setter
    def is_echo(self, value: bool) -> None:
        self._set_bit(14, 1, bool(value))

    @property
    def qsend_100us(self) -> bool:
        return bool(self._get_bit(15))

    @qsend_100us.setter
    def qsend_100us(self, value: bool) -> None:
        self._set_bit(15, 1, bool(value))

    @property
    def qsend(self) -> bool:
        return bool(self._get_bit(16))

    @qsend.setter
    def qsend(self, value: bool) -> None:
        self._set_bit(16, 1, bool(value))


class ZCAN_20_MSG(Structure):
    """CAN2.0 帧（24 字节）。"""
    _fields_ = [("hdr", ZCAN_MSG_HDR), ("dat", c_ubyte * 8)]


class ZCAN_FD_MSG(Structure):
    """CANFD 帧（80 字节）。"""
    _fields_ = [("hdr", ZCAN_MSG_HDR), ("dat", c_ubyte * 64)]


class ZCAN_ERR_MSG(Structure):
    """错误帧（24 字节）。"""
    _fields_ = [("hdr", ZCAN_MSG_HDR), ("dat", c_ubyte * 8)]


class _ZCANTimingSeg(Structure):
    """一段位时序（仲裁段 aset / 数据段 dset）。"""
    _fields_ = [("tseg1", c_ubyte), ("tseg2", c_ubyte),
                ("sjw", c_ubyte), ("smp", c_ubyte), ("brp", c_uint16)]


class ZCAN_INIT(Structure):
    """控制器初始化参数（zcan.h 第 66~83 行），20 字节。

    位速率换算：`baud = clk / (brp * (1 + tseg1 + tseg2))`
    （语义由官方样例 `usbcanfd-800u/test.cpp` 反推并做了自校验，见 vci_adapter.calc_canfd_timing）
    """
    _fields_ = [("clk", c_uint32),        # 时钟频率 Hz
                ("mode", c_uint32),       # bit0 0-正常 1-只听；bit1 0-ISO 1-Non-ISO
                ("aset", _ZCANTimingSeg),  # 仲裁段
                ("dset", _ZCANTimingSeg)]  # 数据段


class ZCAN_DEV_INF(Structure):
    """设备信息（zcan.h 第 143~154 行）。

    注意：与 Windows ZCAN 的 ZCAN_DEVICE_INFO 字段名不同（hwv/chn/sn/id），
    适配层会翻译成业务层使用的字段。
    """
    _fields_ = [("hwv", c_uint16), ("fwv", c_uint16), ("drv", c_uint16), ("api", c_uint16),
                ("irq", c_uint16), ("chn", c_ubyte),
                ("sn", c_ubyte * 20), ("id", c_ubyte * 40),
                ("pad", c_uint16 * 4)]


class ZCAN_STAT(Structure):
    """控制器状态（zcan.h 第 156~167 行）。"""
    _fields_ = [("IR", c_ubyte), ("MOD", c_ubyte), ("SR", c_ubyte), ("ALC", c_ubyte),
                ("ECC", c_ubyte), ("EWL", c_ubyte), ("RXE", c_ubyte), ("TXE", c_ubyte),
                ("PAD", c_uint32)]


class ZCANDataObj(Structure):
    """合并接收数据单元（zcan.h 第 268~290 行），data 联合体固定 92 字节。"""

    class _Data(Union):
        _fields_ = [("zcanCANData", ZCAN_20_MSG),
                    ("zcanCANFDData", ZCAN_FD_MSG),
                    ("zcanErrData", ZCAN_ERR_MSG),
                    ("raw", c_ubyte * 92)]

    _fields_ = [("dataType", c_ubyte),
                ("chnl", c_ubyte),
                ("flag", c_uint16),
                ("extraData", c_ubyte * 4),
                ("data", _Data)]


# ------------------------------------------------------------------ 函数原型
# (名称, restype, argtypes)；Time/count 均为无符号 32 位
_PROTOTYPES = {
    "VCI_OpenDevice": (c_uint32, [c_uint32, c_uint32, c_uint32]),
    "VCI_CloseDevice": (c_uint32, [c_uint32, c_uint32]),
    "VCI_InitCAN": (c_uint32, [c_uint32, c_uint32, c_uint32, POINTER(ZCAN_INIT)]),
    "VCI_StartCAN": (c_uint32, [c_uint32, c_uint32, c_uint32]),
    "VCI_ResetCAN": (c_uint32, [c_uint32, c_uint32, c_uint32]),
    "VCI_ClearBuffer": (c_uint32, [c_uint32, c_uint32, c_uint32]),
    "VCI_GetReceiveNum": (c_uint32, [c_uint32, c_uint32, c_uint32]),
    "VCI_Transmit": (c_uint32, [c_uint32, c_uint32, c_uint32, POINTER(ZCAN_20_MSG), c_uint32]),
    "VCI_Receive": (c_uint32, [c_uint32, c_uint32, c_uint32, POINTER(ZCAN_20_MSG),
                               c_uint32, c_uint32]),
    "VCI_TransmitFD": (c_uint32, [c_uint32, c_uint32, c_uint32, POINTER(ZCAN_FD_MSG), c_uint32]),
    "VCI_ReceiveFD": (c_uint32, [c_uint32, c_uint32, c_uint32, POINTER(ZCAN_FD_MSG),
                                 c_uint32, c_uint32]),
    "VCI_TransmitData": (c_uint32, [c_uint32, c_uint32, c_uint32, POINTER(ZCANDataObj), c_uint32]),
    "VCI_ReceiveData": (c_uint32, [c_uint32, c_uint32, c_uint32, POINTER(ZCANDataObj),
                                   c_uint32, c_uint32]),
    "VCI_ReadBoardInfo": (c_uint32, [c_uint32, c_uint32, POINTER(ZCAN_DEV_INF)]),
    "VCI_ReadErrInfo": (c_uint32, [c_uint32, c_uint32, c_uint32, POINTER(ZCAN_ERR_MSG)]),
    "VCI_ReadCANStatus": (c_uint32, [c_uint32, c_uint32, c_uint32, POINTER(ZCAN_STAT)]),
    "VCI_SetReference": (c_uint32, [c_uint32, c_uint32, c_uint32, c_uint32, c_void_p]),
    "VCI_GetReference": (c_uint32, [c_uint32, c_uint32, c_uint32, c_uint32, c_void_p]),
    "VCI_Debug": (c_uint32, [c_uint32]),
}

# 适配层必须有的函数：缺任意一个都说明该库不是 USBCANFD 的 VCI 形态
REQUIRED_SYMBOLS: tuple[str, ...] = (
    "VCI_OpenDevice", "VCI_CloseDevice", "VCI_InitCAN", "VCI_StartCAN",
    "VCI_Transmit", "VCI_Receive", "VCI_GetReceiveNum",
)

# CANFD 相关（libusbcanfd / libusbcanfd800u 有；纯 CAN 的 libusbcan 没有）
CANFD_SYMBOLS: tuple[str, ...] = ("VCI_TransmitFD", "VCI_ReceiveFD")


def missing_symbols(lib, names: tuple[str, ...] = REQUIRED_SYMBOLS) -> list[str]:
    """返回库中**缺失**的函数名列表（用于判断接口形态并给出可读报错）。"""
    return [n for n in names if not hasattr(lib, n)]


def has_canfd(lib) -> bool:
    """该库是否支持 CANFD 收发。"""
    return not missing_symbols(lib, CANFD_SYMBOLS)


def bind_prototypes(lib) -> list[str]:
    """给库对象绑定 argtypes/restype；返回实际绑定的函数名列表。

    未出现在库里的函数会被跳过（例如纯 CAN 库没有 VCI_TransmitFD）。
    """
    bound: list[str] = []
    for name, (restype, argtypes) in _PROTOTYPES.items():
        func = getattr(lib, name, None)
        if func is None:
            continue
        func.restype = restype
        func.argtypes = argtypes
        bound.append(name)
    return bound


def set_reference(lib, dev_type: int, dev_index: int, channel: int,
                  ref_code: int, value: int) -> int:
    """`VCI_SetReference` 的整型封装（pData 指向 uint32）。

    VCI 的 SetReference 取的是**指针**，每次都要临时分配，这里集中处理避免调用点重复。
    """
    data = c_uint32(as_int(value))
    return int(lib.VCI_SetReference(as_int(dev_type), as_int(dev_index), as_int(channel),
                                    as_int(ref_code), ctypes.cast(byref(data), c_void_p)))


def get_reference(lib, dev_type: int, dev_index: int, channel: int, ref_code: int) -> tuple[int, int]:
    """`VCI_GetReference` 的整型封装；返回 (状态码, 值)。"""
    data = c_uint32(0)
    status = int(lib.VCI_GetReference(as_int(dev_type), as_int(dev_index), as_int(channel),
                                      as_int(ref_code), ctypes.cast(byref(data), c_void_p)))
    return status, int(data.value)


__all__ = [
    "ZCAN_MSG_HDR", "ZCAN_20_MSG", "ZCAN_FD_MSG", "ZCAN_ERR_MSG",
    "ZCAN_INIT", "ZCAN_DEV_INF", "ZCAN_STAT", "ZCANDataObj",
    "VCI_STATUS_OK", "VCI_STATUS_ERR",
    "ZCAN_FMT_CAN2", "ZCAN_FMT_CANFD",
    "ZCAN_TX_NORM", "ZCAN_TX_ONCE", "ZCAN_TX_SR_NORM", "ZCAN_TX_SR_ONCE",
    "SETREF_SET_CONTROLLER_TYPE", "SETREF_ENABLE_INTERNAL_RESISTANCE",
    "SETREF_ADD_TIMER_SEND_CAN", "SETREF_ADD_TIMER_SEND_CANFD",
    "SETREF_APPLY_TIMER_SEND", "SETREF_CLEAR_TIMER_SEND",
    "SETREF_SET_DEVICE_NAME", "GETREF_GET_DEVICE_NAME",
    "SETREF_SET_DATA_RECV_MERGE", "GETREF_GET_DATA_RECV_MERGE",
    "DT_VCI_CAN", "DT_VCI_CANFD", "DT_VCI_ERROR", "DT_VCI_LIN",
    "INVALID_DEVICE_HANDLE", "INVALID_CHANNEL_HANDLE",
    "REQUIRED_SYMBOLS", "CANFD_SYMBOLS",
    "missing_symbols", "has_canfd", "bind_prototypes", "set_reference", "get_reference",
    "as_int",
]
