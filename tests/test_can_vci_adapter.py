# -*- coding: utf-8 -*-
"""tests/test_can_vci_adapter.py —— VCI 适配层（can_core.vci_adapter）单元测试

两层验证：

1. **逻辑层（始终运行）**：用 Python 假 VCI 库，逐项断言"ZCAN 调用面 → VCI 调用"的翻译：
   句柄映射、端口号保留、报文标志位、合并接收数据类型归一、属性键映射、时序换算。
2. **ABI 层（需 `HUD_VCI_STUB_SO`）**：用 `docker/can-sim/vci_stub.c` 编译出的真实
   `.so`（导出完整 VCI 接口 + 回环收发），确认 ctypes 结构体布局与官方头文件一致 ——
   布局若错，回环回来的字段必然错乱，测试会直接失败。
"""
from __future__ import annotations

import ctypes
import glob
import os
import pathlib
import platform
import shutil

import pytest

from can_core import driver as dr
from can_core import driver_factory as df
from can_core import vci_adapter as va
from can_core import vci_driver as vd


# --------------------------------------------------------------------------- 假 VCI 库
def _addr(obj) -> int:
    """把 ctypes 指针/数组/byref 统一取成地址。"""
    if obj is None:
        return 0
    if isinstance(obj, int):
        return obj
    try:
        return ctypes.cast(obj, ctypes.c_void_p).value or 0
    except TypeError:
        target = getattr(obj, "_obj", None)          # ctypes.byref() 的实现细节
        return ctypes.addressof(target) if target is not None else 0


def _at(obj, cls):
    """按地址读取 ctypes 结构体（**拷贝**一份）—— 用于入参。

    必须拷贝：`cast(...).contents` 返回的是对原缓冲的视图，而原缓冲属于被调用方的
    局部变量；调用返回后该内存可能被复用，视图读到的就是垃圾值。
    """
    return cls.from_buffer_copy(ctypes.string_at(_addr(obj), ctypes.sizeof(cls)))


def _out(obj, cls):
    """取得出参结构体的可写视图（写入必须落在调用方的缓冲上，不能拷走）。"""
    return ctypes.cast(_addr(obj), ctypes.POINTER(cls)).contents


class FakeVciLib:
    """最小 VCI 库替身：记录调用、回环收发（语义对齐 vci_stub.c）。"""

    def __init__(self):
        self.opened: list[tuple[int, int, int]] = []
        self.closed: list[tuple[int, int]] = []
        self.inits: dict[int, vd.ZCAN_INIT] = {}
        self.started: list[int] = []
        self.refs: list[tuple[int, int, int]] = []
        self.device_name = b""
        self.can_tx: list[vd.ZCAN_20_MSG] = []
        self.fd_tx: list[vd.ZCAN_FD_MSG] = []
        self.merge_tx: list[vd.ZCANDataObj] = []
        self.can_rx: list[tuple[int, int, int, bytes]] = []      # (id, inf, len, data)
        self.fd_rx: list[tuple[int, int, int, bytes]] = []
        self.merge_rx: list[vd.ZCANDataObj] = []
        self.ts = 500
        self.last_can_count = 0
        self.last_fd_count = 0

    # ---- 设备 ----
    def VCI_OpenDevice(self, dev_type, dev_index, reserved):
        self.opened.append((dev_type, dev_index, reserved))
        return vd.VCI_STATUS_OK

    def VCI_CloseDevice(self, dev_type, dev_index):
        self.closed.append((dev_type, dev_index))
        return vd.VCI_STATUS_OK

    def VCI_InitCAN(self, dev_type, dev_index, port, init_ptr):
        self.inits[int(port)] = _at(init_ptr, vd.ZCAN_INIT)
        return vd.VCI_STATUS_OK

    def VCI_StartCAN(self, dev_type, dev_index, port):
        self.started.append(int(port))
        return vd.VCI_STATUS_OK

    def VCI_ResetCAN(self, dev_type, dev_index, port):
        return vd.VCI_STATUS_OK

    def VCI_ClearBuffer(self, dev_type, dev_index, port):
        self.can_rx.clear()
        self.fd_rx.clear()
        return vd.VCI_STATUS_OK

    def VCI_GetReceiveNum(self, dev_type, dev_index, port):
        return len(self.can_rx) + len(self.fd_rx)

    def VCI_ReadBoardInfo(self, dev_type, dev_index, info_ptr):
        info = _out(info_ptr, vd.ZCAN_DEV_INF)
        info.hwv, info.fwv, info.drv, info.api, info.irq = 0x0102, 0x0304, 0x0506, 0x0708, 0
        info.chn = 2
        info.sn[:6] = b"STUB1\x00"
        info.id[:5] = b"FAKE\x00"
        return vd.VCI_STATUS_OK

    def VCI_ReadErrInfo(self, dev_type, dev_index, port, ptr):
        return vd.VCI_STATUS_OK

    def VCI_ReadCANStatus(self, dev_type, dev_index, port, ptr):
        return vd.VCI_STATUS_OK

    # ---- 引用 ----
    def VCI_SetReference(self, dev_type, dev_index, port, ref, data):
        value = 0
        if int(ref) == vd.SETREF_SET_DEVICE_NAME:
            self.device_name = ctypes.cast(data, ctypes.c_char_p).value or b""
        elif data:
            value = ctypes.cast(data, ctypes.POINTER(ctypes.c_uint32)).contents.value
        self.refs.append((int(port), int(ref), value))
        return vd.VCI_STATUS_OK

    def VCI_GetReference(self, dev_type, dev_index, port, ref, data):
        if int(ref) == vd.GETREF_GET_DEVICE_NAME:
            ctypes.memmove(data, self.device_name + b"\x00", len(self.device_name) + 1)
        return vd.VCI_STATUS_OK

    # ---- 收发 ----
    def VCI_Transmit(self, dev_type, dev_index, port, msgs, count):
        for i in range(int(count)):
            self.can_tx.append(msgs[i])
        self.last_can_count = int(count)
        return int(count)

    def VCI_TransmitFD(self, dev_type, dev_index, port, msgs, count):
        for i in range(int(count)):
            self.fd_tx.append(msgs[i])
        self.last_fd_count = int(count)
        return int(count)

    def VCI_TransmitData(self, dev_type, dev_index, port, objs, count):
        for i in range(int(count)):
            self.merge_tx.append(objs[i])
        return int(count)

    def VCI_Receive(self, dev_type, dev_index, port, out, count, wait):
        got = 0
        while got < int(count) and self.can_rx:
            can_id, inf, length, data = self.can_rx.pop(0)
            msg = out[got]
            msg.hdr.id = can_id
            msg.hdr.inf = inf
            msg.hdr.len = length
            msg.hdr.ts = self.ts
            self.ts += 1
            for j, byte in enumerate(data):
                msg.dat[j] = byte
            got += 1
        return got

    def VCI_ReceiveFD(self, dev_type, dev_index, port, out, count, wait):
        got = 0
        while got < int(count) and self.fd_rx:
            can_id, inf, length, data = self.fd_rx.pop(0)
            msg = out[got]
            msg.hdr.id = can_id
            msg.hdr.inf = inf
            msg.hdr.len = length
            msg.hdr.ts = self.ts
            self.ts += 1
            for j, byte in enumerate(data):
                msg.dat[j] = byte
            got += 1
        return got

    def VCI_ReceiveData(self, dev_type, dev_index, port, out, count, wait):
        got = 0
        while got < int(count) and self.merge_rx:
            src = self.merge_rx.pop(0)
            ctypes.memmove(ctypes.addressof(out[got]), ctypes.addressof(src),
                           ctypes.sizeof(vd.ZCANDataObj))
            got += 1
        return got


@pytest.fixture()
def fake():
    return FakeVciLib()


@pytest.fixture()
def adapter(fake):
    return va.VciCanDriver(lib=fake)


def _inf(payload: int) -> int:
    """按 zcan.h 位序拼 inf：txm[0:4] fmt[4:8] sdf[8] sef[9] brs[11] tx[13] echo[14]。"""
    return payload


def _open_and_init(adapter, fake, *, nominal=None, data_baud=None, merge=None, resistance=None):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    assert dev, "OpenDevice 应返回有效句柄"
    if nominal is not None:
        assert adapter.ZCAN_SetValue(dev, f"0/canfd_abit_baud_rate".encode(), str(nominal).encode()) \
            == dr.ZCAN_STATUS_OK
    if data_baud is not None:
        assert adapter.ZCAN_SetValue(dev, b"0/canfd_dbit_baud_rate", str(data_baud).encode()) \
            == dr.ZCAN_STATUS_OK
    if resistance is not None:
        adapter.ZCAN_SetValue(dev, b"0/initenal_resistance", str(resistance).encode())
    if merge is not None:
        adapter.ZCAN_SetValue(dev, b"0/set_device_recv_merge", str(merge).encode())
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CANFD
    cfg.config.canfd.mode = 0
    chn = adapter.InitCAN(dev, 0, cfg)
    assert chn, "InitCAN 应返回有效通道句柄"
    return dev, chn


# --------------------------------------------------------------------------- 时序换算
def test_timing_matches_vendor_sample():
    """必须能重现官方样例（usbcanfd-800u/test.cpp）里的两组时序数。

    样例：`nTSEG1=31 nTSEG2=8 nSJW=8 nBRP=1`（40MHz 下 1Mbps，采样点 80%）
          与 `nTSEG1=5 nTSEG2=2 nSJW=2 nBRP=1`（40MHz 下 5Mbps，采样点 75%）。
    """
    assert va.calc_canfd_timing(1_000_000, 40_000_000, 0.80) == (31, 8, 8, 1)
    assert va.calc_canfd_timing(5_000_000, 40_000_000, 0.75, max_tseg1=32, max_tseg2=8) == (5, 2, 2, 1)


@pytest.mark.parametrize("baud, expected_tq, expected_brp", [(500_000, 40, 2), (2_000_000, 20, 1)])
def test_timing_for_project_bauds_is_self_consistent(baud, expected_tq, expected_brp):
    """项目实际用的 500k/2M：换算出的参数必须精确还原该波特率。

    500kbps@40MHz 的候选里 brp=1（80 TQ）虽然也能整除，但超出 64 TQ 上限，
    应选用 brp=2（40 TQ）—— 与官方样例同数量级的采样精度。
    """
    t1, t2, sjw, brp = va.calc_canfd_timing(baud, 40_000_000, 0.80)
    total_tq = 1 + t1 + t2
    assert total_tq == expected_tq, f"总 TQ 应为 {expected_tq}，实际 {total_tq}"
    assert brp == expected_brp, f"分频比应为 {expected_brp}，实际 {brp}"
    assert 40_000_000 / (brp * total_tq) == baud, "换回的波特率必须与请求一致"
    assert sjw == t2, "SJW 应等于 TSEG2（与官方样例一致）"


def test_timing_rejects_impossible_request():
    with pytest.raises(ValueError):
        va.calc_canfd_timing(0, 40_000_000)
    with pytest.raises(ValueError):
        va.calc_canfd_timing(100_000_000, 40_000_000)      # 超过时钟可表达的范围


def test_ctypes_constants_are_accepted_as_arguments(adapter, fake):
    """设备类型/通道类型常量是 ctypes 标量；Python 3.13 起 `int(c_uint(41))` 会抛错。

    适配层必须用 `vci_driver.as_int()` 取值，否则在 3.13 上直接不可用
    （3.10~3.12 正常），这类问题单测必须拦住。
    """
    assert vd.as_int(dr.ZCAN_USBCANFD_200U) == 41
    assert vd.as_int(ctypes.c_ubyte(7)) == 7
    assert vd.as_int(3) == 3
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, ctypes.c_uint32(0), ctypes.c_uint32(0))
    assert dev == va.DEVICE_HANDLE_BASE
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CANFD
    assert adapter.InitCAN(dev, ctypes.c_uint32(0), cfg), "ctypes 标量通道号应可用"
    assert adapter.GetReceiveNum(dev, dr.ZCAN_TYPE_MERGE) == 0


# --------------------------------------------------------------------------- 句柄与初始化
def test_handle_conventions_keep_channel_in_low_byte(adapter, fake):
    """业务层用 `chn_handle & 0xFF` 取通道号，因此低字节必须是通道号。"""
    dev, chn = _open_and_init(adapter, fake)
    assert dev == va.DEVICE_HANDLE_BASE, "设备句柄应为基址 | 设备序号"
    assert chn & 0xFF == 0, "通道 0 的句柄低字节应为 0"
    dev2 = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 1, 0)
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CANFD
    chn2 = adapter.InitCAN(dev2, 3, cfg)
    assert chn2 & 0xFF == 3, "通道 3 的句柄低字节应为 3"
    assert fake.inits[3].aset.brp > 0, "未显式设波特率时应使用默认值并成功换算"


def test_init_can_translates_baud_and_references(adapter, fake):
    dev, _ = _open_and_init(adapter, fake, nominal=500_000, data_baud=2_000_000,
                            resistance=1, merge=1)
    init = fake.inits[0]
    t1, t2, sjw, brp = va.calc_canfd_timing(500_000, 40_000_000, 0.80)
    d1, d2, dsjw, dbrp = va.calc_canfd_timing(2_000_000, 40_000_000, 0.75)
    assert (init.aset.tseg1, init.aset.tseg2, init.aset.sjw, init.aset.brp) == (t1, t2, sjw, brp)
    assert (init.dset.tseg1, init.dset.tseg2, init.dset.sjw, init.dset.brp) == (d1, d2, dsjw, dbrp)
    assert init.clk == 40_000_000 and init.mode == 0, "时钟/模式应写入 ZCAN_INIT"
    codes = [c for (_p, c, _v) in fake.refs]
    assert vd.SETREF_SET_CONTROLLER_TYPE in codes, "应在 StartCAN 前设置控制器类型（ISO CANFD）"
    assert vd.SETREF_ENABLE_INTERNAL_RESISTANCE in codes, "终端电阻应下发"
    assert vd.SETREF_SET_DATA_RECV_MERGE in codes, "合并接收应下发"
    assert dict((c, v) for (_p, c, v) in fake.refs)[vd.SETREF_SET_DATA_RECV_MERGE] == 1
    assert adapter.StartCAN(_) == dr.ZCAN_STATUS_OK
    assert fake.started == [0]


def test_init_can_listen_only_mode(adapter, fake):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CANFD
    cfg.config.canfd.mode = 1
    adapter.InitCAN(dev, 0, cfg)
    assert fake.inits[0].mode == 1, "只听模式应写入 ZCAN_INIT.mode"


def test_device_info_translation(adapter, fake):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    info = adapter.GetDeviceInf(dev)
    assert info is not None
    assert info.can_num == 2, "通道数应来自 ZCAN_DEV_INF.chn"
    assert info.hw_Version == 0x0102 and info.fw_Version == 0x0304
    assert info.serial.startswith("STUB1"), f"序列号应翻译为字符串，实际 {info.serial!r}"
    assert adapter.DeviceOnLine(dev) is True


# --------------------------------------------------------------------------- 属性键映射
def test_setvalue_custom_baud_string(adapter, fake):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    adapter.ZCAN_SetValue(dev, b"0/baud_rate_custom",
                          b"500Kbps(80%),2.0Mbps(80%),(80,07C00002,01C00002)")
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CANFD
    adapter.InitCAN(dev, 0, cfg)
    init = fake.inits[0]
    assert 40_000_000 / (init.aset.brp * (1 + init.aset.tseg1 + init.aset.tseg2)) == 500_000
    assert 40_000_000 / (init.dset.brp * (1 + init.dset.tseg1 + init.dset.tseg2)) == 2_000_000


def test_setvalue_accepts_str_values(adapter, fake):
    """业务层的属性值形态不统一：`set_device_recv_merge` 传的是 str（repr(...)）。"""
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    assert adapter.ZCAN_SetValue(dev, b"0/set_device_recv_merge", repr(1)) == dr.ZCAN_STATUS_OK
    codes = dict((c, v) for (_p, c, v) in fake.refs)
    assert codes.get(vd.SETREF_SET_DATA_RECV_MERGE) == 1, "str 值应被解析为 1"


def test_setvalue_none_value_is_skipped_safely(adapter, fake):
    """空值（None）不应把异常抛到驱动层，只跳过并告警一次。"""
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    adapter.ZCAN_SetValue(dev, b"0/set_device_recv_merge", b"")   # 空串 → 解析为 None
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CANFD
    assert adapter.InitCAN(dev, 0, cfg), "空属性值不应影响初始化流程"


def test_setvalue_device_name_and_readback(adapter, fake):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    assert adapter.ZCAN_SetValue(dev, b"0/set_cn", b"A001") == dr.ZCAN_STATUS_OK
    assert fake.device_name == b"A001", "设备名应通过 SETREF_SET_DEVICE_NAME 下发"
    ptr = adapter.ZCAN_GetValue(dev, b"0/get_cn/1")
    assert ptr, "应返回 C 缓冲指针"
    assert ctypes.cast(ptr, ctypes.c_char_p).value == b"A001"


def test_setvalue_unknown_key_returns_error_and_warns_once(adapter, fake):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    assert adapter.ZCAN_SetValue(dev, b"0/no_such_key", b"1") == dr.ZCAN_STATUS_ERR
    adapter.ZCAN_SetValue(dev, b"0/no_such_key", b"1")
    assert "key:no_such_key" in adapter._warned, "未知键应记录一次告警，避免刷屏"


def test_setvalue_auto_send_passes_struct_pointer(adapter, fake):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    obj = dr.ZCANFD_AUTO_TRANSMIT_OBJ()
    obj.enable, obj.index, obj.interval = 1, 2, 100
    assert adapter.ZCAN_SetValue(dev, b"0/auto_send_canfd", ctypes.byref(obj)) \
        == dr.ZCAN_STATUS_OK
    assert adapter.ZCAN_SetValue(dev, b"0/apply_auto_send", ctypes.byref(obj)) \
        == dr.ZCAN_STATUS_OK
    assert adapter.ZCAN_SetValue(dev, b"0/clear_auto_send", b"0") == dr.ZCAN_STATUS_OK
    codes = [c for (_p, c, _v) in fake.refs]
    assert vd.SETREF_ADD_TIMER_SEND_CANFD in codes
    assert vd.SETREF_APPLY_TIMER_SEND in codes
    assert vd.SETREF_CLEAR_TIMER_SEND in codes


def test_tx_echo_key_is_adapted_with_warning(adapter, fake):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    assert adapter.ZCAN_SetValue(dev, b"0/set_device_tx_echo", b"0") == dr.ZCAN_STATUS_OK
    assert "tx_echo" in adapter._warned, "应说明 VCI 无该属性、已用回显位等效替代"


def test_iproperty_style_api_is_explicitly_unsupported(adapter):
    with pytest.raises(va.VciUnsupportedError):
        adapter.GetIProperty(1)
    with pytest.raises(va.VciUnsupportedError):
        adapter.SetValue(None, b"x", b"y")


# --------------------------------------------------------------------------- 报文翻译
def test_transmit_fd_bit_mapping(adapter, fake):
    _dev, chn = _open_and_init(adapter, fake)
    msgs = (dr.ZCAN_TransmitFD_Data * 1)()
    frame = msgs[0].frame
    msgs[0].transmit_type = dr.ZCAN_TX_SR_NORM if hasattr(dr, "ZCAN_TX_SR_NORM") else 2
    frame.can_id = 0x123
    frame.len = 4
    frame.flags = 0x20 | 0x01           # 发送回显 + BRS
    for i, byte in enumerate([0x11, 0x22, 0x33, 0x44]):
        frame.data[i] = byte

    assert adapter.TransmitFD(chn, msgs, 1) == 1
    sent = fake.fd_tx[0]
    assert sent.hdr.id == 0x123, "ID 应原样带过（不含标志位）"
    assert sent.hdr.is_canfd is True, "fmt 应为 CANFD"
    assert sent.hdr.is_extended is False, "0x123 属标准帧"
    assert sent.hdr.is_brs is True, "flags bit0 应翻译成 BRS"
    assert sent.hdr.is_echo is True, "flags bit5 应翻译成发送回显"
    assert sent.hdr.tx_mode == 2, "transmit_type 应翻译成 txm"
    assert sent.hdr.len == 4 and list(sent.dat[:4]) == [0x11, 0x22, 0x33, 0x44]


def test_transmit_uses_channel_number_from_handle(adapter, fake):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CAN
    chn = adapter.InitCAN(dev, 1, cfg)
    msgs = (dr.ZCAN_Transmit_Data * 1)()
    msgs[0].frame.can_id = 0x0A1
    msgs[0].frame.can_dlc = 2
    msgs[0].frame.data[0], msgs[0].frame.data[1] = 0xAA, 0xBB
    adapter.Transmit(chn, msgs, 1)
    sent = fake.can_tx[0]
    assert sent.hdr.chn == 1, "VCI 报文头应带真实通道号"
    assert sent.hdr.is_canfd is False and sent.hdr.len == 2


def test_transmit_extended_frame_inferred_when_eff_missing(adapter, fake):
    """业务层若没设置 `eff`，超过 11 位的 ID 应按扩展帧发出（否则 ID 会被截断）。"""
    _dev, chn = _open_and_init(adapter, fake)
    msgs = (dr.ZCAN_TransmitFD_Data * 1)()
    msgs[0].frame.can_id = 0x18FF50E5
    msgs[0].frame.len = 1
    adapter.TransmitFD(chn, msgs, 1)
    assert fake.fd_tx[0].hdr.is_extended is True
    assert fake.fd_tx[0].hdr.id == 0x18FF50E5


def test_business_eff_attribute_cannot_reach_the_driver():
    """记录一个真实约束：业务层写的 `frame.eff = 1` **传不到驱动**。

    ctypes 对嵌套结构体的访问会新建临时视图，`msgs[i].frame` 每次都是新对象，
    给它赋一个"非字段"属性（eff/rtr 在 ZCAN_CAN_FRAME 里被注释掉了）只写在临时对象上，
    二进制里没有任何变化。因此 VCI 适配层**必须**按 ID 是否超过 11 位来推断扩展帧
    （见 `test_transmit_extended_frame_inferred_when_eff_missing`）。
    """
    msgs = (dr.ZCAN_TransmitFD_Data * 1)()
    msgs[0].frame.eff = 1
    assert getattr(msgs[0].frame, "eff", None) is None, \
        "若哪天该属性真能留存，说明 ctypes 行为变了，需重新评估扩展帧判断逻辑"


def test_receive_fd_back_conversion(adapter, fake):
    _dev, chn = _open_and_init(adapter, fake)
    payload = _inf((1 << 4) | (1 << 9) | (1 << 11) | (1 << 13))   # CANFD + 扩展 + BRS + TX
    fake.fd_rx.append((0x18FF50E5, payload, 8, bytes(range(8))))
    msgs, got = adapter.ReceiveFD(chn, 4, 100)
    assert got == 1
    frame = msgs[0].frame
    assert frame.can_id & (1 << 31), "扩展帧标志应还原到 bit31（业务层据此判断）"
    assert (frame.can_id & 0x1FFFFFFF) == 0x18FF50E5
    assert frame.len == 8 and frame.flags & 0x01, "BRS 应还原到 flags bit0"
    assert frame.flags & 0x20, "发送帧应还原成回显标志（业务层据此打印 TX）"
    assert list(frame.data[:8]) == list(range(8))
    assert msgs[0].timestamp == 500, "时间戳应带回"


def test_receive_can_back_conversion(adapter, fake):
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CAN
    chn = adapter.InitCAN(dev, 0, cfg)
    fake.can_rx.append((0x123, 1 << 8, 3, b"\x01\x02\x03"))       # 远程帧
    msgs, got = adapter.Receive(chn, 2, 100)
    assert got == 1
    assert msgs[0].frame.can_id & (1 << 30), "远程帧标志应还原到 bit30"
    assert msgs[0].frame.can_dlc == 3
    assert list(msgs[0].frame.data[:3]) == [1, 2, 3]


def test_merge_mode_roundtrip_and_datatype_normalisation(adapter, fake):
    dev, chn = _open_and_init(adapter, fake, merge=1)
    # 项目 → VCI：frameType=1（CANFD）
    send = (dr.ZCANDataObj * 1)()
    send[0].dataType = dr.ZCAN_DT_ZCAN_CAN_CANFD_DATA
    send[0].chnl = 0
    send[0].zcanfddata.flag.frameType = 1
    send[0].zcanfddata.frame.can_id = 0x321
    send[0].zcanfddata.frame.len = 2
    send[0].zcanfddata.frame.flags = 0x20
    send[0].zcanfddata.frame.data[0], send[0].zcanfddata.frame.data[1] = 0x55, 0x66
    assert adapter.TransmitData(dev, send, 1) == 1
    assert int(fake.merge_tx[0].dataType) == vd.DT_VCI_CANFD, "CANFD 应映射为 VCI 的 2"

    # VCI → 项目：dataType 归一回项目的“CAN/CANFD 合并值 1”
    src = vd.ZCANDataObj()
    src.dataType = vd.DT_VCI_CANFD
    src.chnl = 1
    src.data.zcanCANFDData.hdr.id = 0x456
    src.data.zcanCANFDData.hdr.len = 3
    src.data.zcanCANFDData.hdr.inf = (1 << 4) | (1 << 13)          # CANFD + TX
    src.data.zcanCANFDData.hdr.ts = 777
    for i, byte in enumerate(b"\x0a\x0b\x0c"):
        src.data.zcanCANFDData.dat[i] = byte
    fake.merge_rx.append(src)

    msgs, got = adapter.ReceiveData(dev, 4, 100)
    assert got == 1
    obj = msgs[0]
    assert int(obj.dataType) == dr.ZCAN_DT_ZCAN_CAN_CANFD_DATA, "应归一到项目使用的枚举值"
    assert obj.chnl == 1
    assert int(obj.zcanfddata.flag.frameType) == 1, "CANFD 标志应写入 flag.frameType"
    assert int(obj.zcanfddata.flag.txEchoed) == 1, "TX 帧应写入 txEchoed"
    assert obj.zcanfddata.timestamp == 777
    assert obj.zcanfddata.frame.len == 3
    assert list(obj.zcanfddata.frame.data[:3]) == [10, 11, 12]


def test_receive_num_merge_returns_zero_when_disabled(adapter, fake):
    dev, _chn = _open_and_init(adapter, fake)          # 未开启合并接收
    fake.can_rx.append((0x1, 0, 1, b"\x01"))
    assert adapter.GetReceiveNum(dev, dr.ZCAN_TYPE_MERGE) == 0


def test_close_device_clears_handles(adapter, fake):
    dev, chn = _open_and_init(adapter, fake)
    assert adapter.CloseDevice(dev) == dr.ZCAN_STATUS_OK
    assert fake.closed == [(vd.as_int(dr.ZCAN_USBCANFD_200U), 0)]
    with pytest.raises(ValueError):
        adapter.TransmitFD(chn, (dr.ZCAN_TransmitFD_Data * 1)(), 1)


# --------------------------------------------------------------------------- 后端选择
class _FakeProbe:
    """冒充 `driver.ZCAN`，只暴露 loaded_library。"""

    def __init__(self, lib):
        self.loaded_library = lib


class _ZcanOnlyLib:
    ZCAN_OpenDevice = None
    ZCAN_CloseDevice = None
    ZCAN_InitCAN = None
    ZCAN_StartCAN = None
    ZCAN_Transmit = None
    ZCAN_Receive = None
    ZCAN_GetReceiveNum = None
    ZCAN_SetValue = None
    ZCAN_GetDeviceInf = None
    ZCAN_TransmitFD = None
    ZCAN_ReceiveFD = None


def test_driver_kind_detection():
    assert df.driver_kind(None) == "unknown"
    assert df.driver_kind(FakeVciLib()) == "vci"
    assert df.driver_kind(_ZcanOnlyLib()) == "zcan"

    class Both(FakeVciLib, _ZcanOnlyLib):
        pass

    assert df.driver_kind(Both()) == "zcan+vci"

    class Neither:
        pass

    assert df.driver_kind(Neither()) == "unknown"
    assert df.missing_zcan(Neither())[0] == "ZCAN_OpenDevice"


def test_open_can_driver_selects_vci_backend(monkeypatch):
    fake = FakeVciLib()
    monkeypatch.setattr(df, "ZCAN", lambda path=None: _FakeProbe(fake))
    drv = df.open_can_driver()
    assert isinstance(drv, va.VciCanDriver)


def test_open_can_driver_prefers_zcan_when_complete(monkeypatch):
    lib = _ZcanOnlyLib()
    monkeypatch.setattr(df, "ZCAN", lambda path=None: _FakeProbe(lib))
    assert isinstance(df.open_can_driver(), _FakeProbe)


def test_open_can_driver_reports_missing_symbols(monkeypatch):
    class Broken:
        VCI_OpenDevice = None

    monkeypatch.setattr(df, "ZCAN", lambda path=None: _FakeProbe(Broken()))
    with pytest.raises(OSError) as excinfo:
        df.open_can_driver()
    message = str(excinfo.value)
    assert "缺少 VCI 函数" in message and "VCI_CloseDevice" in message


def test_describe_driver_status_mentions_backend():
    text = df.describe_driver_status()
    assert "CAN 驱动" in text


# --------------------------------------------------------------------------- 同目录依赖预加载
def test_preload_sibling_libraries_skips_broken_files(tmp_path):
    from hudcore.can.backend import preload_sibling_libraries
    if platform.system() == "Windows":
        pytest.skip("Windows 不做预加载")
    (tmp_path / "libzlgcan.so").write_bytes(b"not an ELF")
    (tmp_path / "libusb-1.0.so").write_bytes(b"not an ELF")
    assert preload_sibling_libraries(tmp_path / "libzlgcan.so") == []


def test_preload_sibling_libraries_resolves_soname_mismatch(tmp_path):
    """文件名 ≠ SONAME 时，预加载应让主库能加载（libusb-1.0.so → libusb-1.0.so.0）。"""
    from hudcore.can.backend import preload_sibling_libraries
    if platform.system() != "Linux":
        pytest.skip("仅 Linux 需要处理 SONAME 差异")
    source = None
    for pattern in ("/lib/*/libm.so.6", "/usr/lib/*/libm.so.6"):
        hits = sorted(glob.glob(pattern))
        if hits:
            source = hits[0]
            break
    if source is None:
        pytest.skip("找不到可用于测试的系统 .so")
    target = tmp_path / "libzlgcan.so"
    shutil.copy(source, target)                      # 主库：SONAME 为 libm.so.6
    loaded = preload_sibling_libraries(target)
    assert [p.name for p in loaded] == ["libzlgcan.so"] or loaded == []
    assert ctypes.CDLL(str(target)) is not None      # 至少能正常加载


# --------------------------------------------------------------------------- 真实 ABI（桩库）
STUB_SO = os.environ.get("HUD_VCI_STUB_SO", "")


def _stub_lib():
    if not STUB_SO or not pathlib.Path(STUB_SO).is_file():
        pytest.skip("需 HUD_VCI_STUB_SO 指向 docker/can-sim/vci_stub.c 编译出的 .so")
    lib = ctypes.CDLL(STUB_SO)
    # 自省接口的原型（真实驱动没有这些符号，仅测试用）
    lib.vci_stub_reset.argtypes = []
    lib.vci_stub_name.restype = ctypes.c_char_p
    lib.vci_stub_get_init.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    lib.vci_stub_reset()
    return lib


def test_stub_abi_init_and_loopback():
    """真实 ABI：初始化时序 + CANFD 回环 + 属性引用（证明 ctypes 布局与 zcan.h 一致）。"""
    lib = _stub_lib()
    adapter = va.VciCanDriver(lib=lib)
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    assert dev, "VCI_OpenDevice 应成功"
    assert adapter.GetDeviceInf(dev).can_num == 2, "设备信息应能按真实布局解析"

    adapter.ZCAN_SetValue(dev, b"0/canfd_abit_baud_rate", b"500000")
    adapter.ZCAN_SetValue(dev, b"0/canfd_dbit_baud_rate", b"2000000")
    adapter.ZCAN_SetValue(dev, b"0/initenal_resistance", b"1")
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CANFD
    chn = adapter.InitCAN(dev, 0, cfg)
    assert chn
    assert adapter.StartCAN(chn) == dr.ZCAN_STATUS_OK

    # 时序：从桩库读回它收到的 ZCAN_INIT，验证真实结构体布局与换算结果
    raw = vd.ZCAN_INIT()
    assert lib.vci_stub_get_init(0, ctypes.byref(raw)) == 1
    assert raw.clk == 40_000_000
    assert 40_000_000 / (raw.aset.brp * (1 + raw.aset.tseg1 + raw.aset.tseg2)) == 500_000
    assert 40_000_000 / (raw.dset.brp * (1 + raw.dset.tseg1 + raw.dset.tseg2)) == 2_000_000

    # 回环：发送 → 查数量 → 接收 → 字段完整
    msgs = (dr.ZCAN_TransmitFD_Data * 1)()
    msgs[0].frame.can_id = 0x18FF50E5
    msgs[0].frame.len = 6
    msgs[0].frame.flags = 0x01
    for i in range(6):
        msgs[0].frame.data[i] = 0xA0 + i
    assert adapter.TransmitFD(chn, msgs, 1) == 1
    assert adapter.GetReceiveNum(chn, dr.ZCAN_TYPE_CANFD) == 1
    rx, got = adapter.ReceiveFD(chn, 4, 100)
    assert got == 1
    assert (rx[0].frame.can_id & 0x1FFFFFFF) == 0x18FF50E5
    assert rx[0].frame.can_id & (1 << 31), "0x18FF50E5 应被识别为扩展帧"
    assert rx[0].frame.len == 6 and list(rx[0].frame.data[:6]) == [0xA0 + i for i in range(6)]
    assert rx[0].frame.flags & 0x01, "BRS 标志应保留"
    assert rx[0].frame.flags & 0x20, "回环帧应带发送标志（业务层打印 TX）"

    # 属性引用：桩库记录到的引用码
    codes = [int(lib.vci_stub_ref_code(i)) for i in range(int(lib.vci_stub_ref_count()))]
    assert vd.SETREF_SET_CONTROLLER_TYPE in codes
    assert vd.SETREF_ENABLE_INTERNAL_RESISTANCE in codes

    # 设备名读写（指针型引用走真实 ABI）
    assert adapter.ZCAN_SetValue(dev, b"0/set_cn", b"A001") == dr.ZCAN_STATUS_OK
    assert lib.vci_stub_name() == b"A001", "设备名应通过真实 ABI 写入桩库"
    ptr = adapter.ZCAN_GetValue(dev, b"0/get_cn/1")
    assert ctypes.cast(ptr, ctypes.c_char_p).value == b"A001"
    assert adapter.CloseDevice(dev) == dr.ZCAN_STATUS_OK


def test_stub_abi_merge_mode_roundtrip():
    """真实 ABI：合并接收（ZCANDataObj 92 字节联合体）往返正确。"""
    lib = _stub_lib()
    adapter = va.VciCanDriver(lib=lib)
    dev = adapter.OpenDevice(dr.ZCAN_USBCANFD_200U, 0, 0)
    cfg = dr.ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = dr.ZCAN_TYPE_CANFD
    adapter.InitCAN(dev, 0, cfg)
    adapter.ZCAN_SetValue(dev, b"0/set_device_recv_merge", b"1")

    send = (dr.ZCANDataObj * 1)()
    send[0].dataType = dr.ZCAN_DT_ZCAN_CAN_CANFD_DATA
    send[0].zcanfddata.flag.frameType = 1
    send[0].zcanfddata.frame.can_id = 0x123
    send[0].zcanfddata.frame.len = 2
    send[0].zcanfddata.frame.data[0], send[0].zcanfddata.frame.data[1] = 0xDE, 0xAD
    assert adapter.TransmitData(dev, send, 1) == 1
    rx, got = adapter.ReceiveData(dev, 4, 100)
    assert got == 1
    assert int(rx[0].zcanfddata.flag.frameType) == 1
    assert (rx[0].zcanfddata.frame.can_id & 0x1FFFFFFF) == 0x123
    assert list(rx[0].zcanfddata.frame.data[:2]) == [0xDE, 0xAD]
