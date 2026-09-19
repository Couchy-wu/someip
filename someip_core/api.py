# -*- coding: utf-8 -*-
"""someip_core.api —— C++ 服务端库的 ctypes 绑定（惰性加载）

对应 C++ 库 `libarhud_server.so`（源：arhud_python_server/src/arhud_server.h），
提供：创建/销毁、服务与事件注册、启停、单条发送、pcap 回放、订阅回调、序列化辅助。

与原工程 `arhud_python.py` 的差异（改进点）：
  · **惰性加载**：库在首次使用时才 dlopen（原实现在 import 时加载，库缺失即导入失败）；
  · 库路径由 `hudcore.someip` 统一探测（环境变量 → 项目目录 → 系统路径），
    不再把路径硬编码为"与本文件同目录"；
  · 结构体与绑定集中在本模块，便于单元测试用假库替换。
"""
from __future__ import annotations

import ctypes
import socket
from typing import Any

from hudcore.someip import describe_library_status, load_someip_library

from .models import KIND_SERVICE_EVENT, STRUCT_TYPES

# ---------------- ctypes 基础类型 ----------------
U8 = ctypes.POINTER(ctypes.c_uint8)
U32 = ctypes.POINTER(ctypes.c_uint32)


# ---------------- 结构体（与 arhud_types.h 对齐，#pragma pack(1)） ----------------
class RTK(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Checksum", ctypes.c_uint32), ("Counter", ctypes.c_uint16),
                ("rtk_status", ctypes.c_uint32),
                ("utc_time_us", ctypes.c_double), ("sys_time_us", ctypes.c_double),
                ("longitude", ctypes.c_double), ("latitude", ctypes.c_double),
                ("altitude", ctypes.c_double),
                ("longitude_acc", ctypes.c_double), ("latitude_acc", ctypes.c_double),
                ("altitude_acc", ctypes.c_double),
                ("heading_move", ctypes.c_double), ("heading_double_ant", ctypes.c_double),
                ("heading_move_acc", ctypes.c_double),
                ("speed_2d", ctypes.c_double), ("speed_acc", ctypes.c_double),
                ("speed_n", ctypes.c_double), ("speed_e", ctypes.c_double),
                ("speed_u", ctypes.c_double),
                ("g_dop", ctypes.c_double), ("h_dop", ctypes.c_double), ("v_dop", ctypes.c_double),
                ("satellite_num", ctypes.c_uint32), ("satellite_used", ctypes.c_uint32),
                ("snr_max", ctypes.c_double), ("snr_mix", ctypes.c_double),
                ("snr_avr", ctypes.c_double)]


class IMU(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Checksum", ctypes.c_uint32), ("Counter", ctypes.c_uint16),
                ("angular_velocity_x", ctypes.c_double), ("angular_velocity_y", ctypes.c_double),
                ("angular_velocity_z", ctypes.c_double),
                ("acc_speed_x", ctypes.c_double), ("acc_speed_y", ctypes.c_double),
                ("acc_speed_z", ctypes.c_double),
                ("IMU_status", ctypes.c_uint8),
                ("IMU_current_temperature", ctypes.c_double), ("sys_time_us", ctypes.c_double),
                ("is_calibrated", ctypes.c_uint8)]


class ChangeLane(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Checksum", ctypes.c_uint32), ("Counter", ctypes.c_uint16),
                ("ChangeLaneState", ctypes.c_uint32),
                ("ChangeLaneDirection", ctypes.c_uint8), ("is_change_safety", ctypes.c_uint8),
                ("ChangeLane_timestamp", ctypes.c_uint32), ("change_ratio", ctypes.c_double),
                ("change_termi", ctypes.c_uint32),
                ("landing_center_X", ctypes.c_double), ("landing_center_Y", ctypes.c_double),
                ("landing_center_Z", ctypes.c_double),
                ("landing_box_length", ctypes.c_double), ("landing_box__width", ctypes.c_double),
                ("landing_box_height", ctypes.c_double)]


class PilotStatus(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Checksum", ctypes.c_uint32), ("Counter", ctypes.c_uint16),
                ("ACCStatus", ctypes.c_uint8), ("ICCStatus", ctypes.c_uint8),
                ("DNPStatus", ctypes.c_uint8), ("TakeoverStatus", ctypes.c_uint8),
                ("driving_time", ctypes.c_uint32)]


class PilotAlarm(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Checksum", ctypes.c_uint32), ("Counter", ctypes.c_uint16),
                ("PilotAlarmReason", ctypes.c_uint32), ("alarm_distance", ctypes.c_uint32),
                ("alarm_stage", ctypes.c_uint32), ("alarm_timestamp", ctypes.c_double),
                ("PilotNotice", ctypes.c_uint32), ("notice_distance", ctypes.c_uint32),
                ("notice_timestamp", ctypes.c_double)]


class Broadcast(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Checksum", ctypes.c_uint32), ("Counter", ctypes.c_uint16),
                ("driver_attention", ctypes.c_uint8), ("large_vehicles", ctypes.c_uint8),
                ("dangerous_vehicle", ctypes.c_uint8), ("pedestrians", ctypes.c_uint8)]


class HudMappath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Checksum", ctypes.c_uint32), ("Counter", ctypes.c_uint16),
                ("is_on_the_path", ctypes.c_uint8), ("road_angle", ctypes.c_uint8),
                ("road_slope", ctypes.c_float),
                ("all_EHP_v2_info", ctypes.c_char * 512)]


class HudNavmap(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Checksum", ctypes.c_uint32), ("Counter", ctypes.c_uint16),
                ("Navigation_map", ctypes.c_char * 2048)]


class VehiclePosition(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Checksum", ctypes.c_uint32), ("Counter", ctypes.c_uint16),
                ("Longitude", ctypes.c_double), ("Latitude", ctypes.c_double),
                ("altitude", ctypes.c_double), ("Heading", ctypes.c_double),
                ("hd_lane_left_angle", ctypes.c_double), ("Hd_lane_right_angle", ctypes.c_double),
                ("VehicleSpeed", ctypes.c_double), ("acceleration", ctypes.c_double),
                ("x_speed", ctypes.c_double), ("y_speed", ctypes.c_double),
                ("z_speed", ctypes.c_double), ("timestamp", ctypes.c_double),
                ("hd_link_id", ctypes.c_uint32), ("hd_lane_id", ctypes.c_uint32),
                ("hd_lane_type", ctypes.c_uint32), ("on_lane_offset", ctypes.c_double),
                ("hd_lane_seq", ctypes.c_uint32), ("hd_lane_num", ctypes.c_uint32),
                ("hd_lane_left_lateral_offset", ctypes.c_double),
                ("hd_lane_right_lateral_offset", ctypes.c_double),
                ("roll", ctypes.c_double), ("pitch", ctypes.c_double),
                ("HdStatus", ctypes.c_uint8), ("hdmap_version", ctypes.c_uint8),
                ("fusion_status", ctypes.c_uint8), ("pos_confidence", ctypes.c_double),
                ("position_type", ctypes.c_uint8), ("break_light", ctypes.c_uint8),
                ("indicator_light", ctypes.c_uint8), ("Lights", ctypes.c_uint8),
                ("Weather", ctypes.c_uint8), ("target_cruise_speed", ctypes.c_float)]


# 类型名 → 结构体（VehiclePosition 走专用序列化接口，不在此表）
STRUCT_CLASSES: dict[str, type[ctypes.Structure]] = {
    "RTK": RTK,
    "IMU": IMU,
    "ChangeLane": ChangeLane,
    "PilotStatus": PilotStatus,
    "PilotAlarm": PilotAlarm,
    "Broadcast": Broadcast,
    "HudMappath": HudMappath,
    "HudNavmap": HudNavmap,
}

# 类型名 → 可编辑结构体（界面字段表用；VehiclePosition 由专用接口序列化，
# 但字段定义同样是 ctypes 结构体，因此也纳入可编辑集合）
EDITABLE_CLASSES: dict[str, type[ctypes.Structure]] = dict(STRUCT_CLASSES)
EDITABLE_CLASSES["VehiclePosition"] = VehiclePosition

# 类型名 → C 序列化函数名
_SERIALIZER_NAMES: dict[str, str] = {
    "RTK": "arhud_serialize_rtk",
    "IMU": "arhud_serialize_imu",
    "ChangeLane": "arhud_serialize_changelane",
    "PilotStatus": "arhud_serialize_pilot_status",
    "PilotAlarm": "arhud_serialize_pilot_alarm",
    "Broadcast": "arhud_serialize_broadcast",
    "HudMappath": "arhud_serialize_hud_mappath",
    "HudNavmap": "arhud_serialize_hud_navmap",
}


def default_ip() -> str:
    """探测本机对外 IP（用于 SD 单播地址）；失败时回退 127.0.0.1。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class SomeipLib:
    """C++ 服务端库的绑定封装（一个实例对应一个已加载的库）。"""

    def __init__(self, handle: Any) -> None:
        self._lib = handle
        self._bind()

    # ---------------- 绑定 ----------------
    def _bind(self) -> None:
        lib = self._lib
        lib.arhud_server_create.restype = ctypes.c_void_p
        lib.arhud_server_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.arhud_server_destroy.argtypes = [ctypes.c_void_p]
        # 注意：签名必须与 arhud_server.h 完全一致（参数错位会导致 rc=-1 的隐性失败）
        #   add_service(srv, service, instance, port, major, minor)
        #   add_event  (srv, service, instance, event, group)
        lib.arhud_server_add_service.restype = ctypes.c_int
        lib.arhud_server_add_service.argtypes = [
            ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16,
            ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint16]
        lib.arhud_server_add_event.restype = ctypes.c_int
        lib.arhud_server_add_event.argtypes = [
            ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16,
            ctypes.c_uint16, ctypes.c_uint16]
        lib.arhud_server_start.restype = ctypes.c_int
        lib.arhud_server_start.argtypes = [ctypes.c_void_p]
        lib.arhud_server_stop.argtypes = [ctypes.c_void_p]
        lib.arhud_server_notify.restype = ctypes.c_int
        lib.arhud_server_notify.argtypes = [ctypes.c_void_p, ctypes.c_uint16,
                                           ctypes.c_uint16, U8, ctypes.c_uint32]
        lib.arhud_server_replay_start.restype = ctypes.c_int
        lib.arhud_server_replay_start.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                                 ctypes.c_int, ctypes.c_uint32]
        lib.arhud_server_replay_stop.argtypes = [ctypes.c_void_p]
        lib.arhud_server_replay_sent.restype = ctypes.c_uint64
        lib.arhud_server_replay_sent.argtypes = [ctypes.c_void_p]
        for fn_name in _SERIALIZER_NAMES.values():
            fn = getattr(lib, fn_name)
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, U8, ctypes.POINTER(ctypes.c_uint32)]
        lib.arhud_serialize_vehicle.restype = ctypes.c_int
        lib.arhud_serialize_vehicle.argtypes = [
            ctypes.c_void_p, U32, ctypes.c_uint32, U32, ctypes.c_uint32,
            ctypes.c_uint8, U8, ctypes.POINTER(ctypes.c_uint32)]

    @property
    def raw(self) -> Any:
        """底层库句柄（测试或特殊场景可直接使用）。"""
        return self._lib

    # ---------------- 生命周期 ----------------
    def create(self, unicast: str | None = None, config_path: str | None = None) -> int:
        handle = self._lib.arhud_server_create(
            (unicast or default_ip()).encode(),
            config_path.encode() if config_path else None)
        if not handle:
            raise RuntimeError("arhud_server_create 失败（检查 unicast 地址与 vsomeip 配置）")
        return handle

    def destroy(self, handle: int) -> None:
        self._lib.arhud_server_destroy(ctypes.c_void_p(handle))

    def start(self, handle: int) -> int:
        return int(self._lib.arhud_server_start(ctypes.c_void_p(handle)))

    def stop(self, handle: int) -> None:
        self._lib.arhud_server_stop(ctypes.c_void_p(handle))

    # ---------------- 注册 ----------------
    def add_service(self, handle: int, service: int, instance: int,
                    port: int = 0, major: int = 1, minor: int = 0) -> int:
        """注册服务（覆盖库内置注册表中的该服务）。"""
        return int(self._lib.arhud_server_add_service(
            ctypes.c_void_p(handle), service, instance, port, major, minor))

    def add_event(self, handle: int, service: int, instance: int,
                  event: int, group: int = 0x1101) -> int:
        """注册事件（必须在 start() 之前调用）。"""
        return int(self._lib.arhud_server_add_event(
            ctypes.c_void_p(handle), service, instance, event, group))

    # ---------------- 发送 ----------------
    def notify_raw(self, handle: int, service: int, event: int, data: bytes) -> int:
        """发送原始字节载荷。

        注意：C 侧形参是 `const uint8_t*`，因此必须传 uint8 数组；
        早期写成 create_string_buffer（c_char 数组）会抛
        `expected LP_c_ubyte instance instead of c_char_Array_N`。
        """
        payload = bytes(data)
        buf = (ctypes.c_uint8 * max(1, len(payload))).from_buffer_copy(payload or b"\x00")
        return int(self._lib.arhud_server_notify(
            ctypes.c_void_p(handle), service, event, buf, len(payload)))

    def serialize(self, handle: int, kind: str, fields: dict) -> bytes:
        """结构化字段 → C++ 序列化（大端 + CRC32）→ 载荷字节。"""
        if kind == "VehiclePosition":
            return self._serialize_vehicle(handle, fields)
        if kind not in _SERIALIZER_NAMES:
            raise ValueError(f"不支持结构化发送的类型：{kind}")
        st = STRUCT_CLASSES[kind]()
        st.Checksum = 0
        for key, value in fields.items():
            if not hasattr(st, key):
                raise ValueError(f"{kind} 没有字段 {key!r}")
            cur = getattr(st, key)
            if isinstance(cur, bytes):
                setattr(st, key, str(value).encode("utf-8"))
            else:
                setattr(st, key, value)
        out = (ctypes.c_uint8 * 4096)()
        out_len = ctypes.c_uint32(4096)
        fn = getattr(self._lib, _SERIALIZER_NAMES[kind])
        rc = fn(ctypes.byref(st), out, ctypes.byref(out_len))
        if rc != 0:
            raise RuntimeError(f"序列化 {kind} 失败 rc={rc}")
        return bytes(out[:out_len.value])

    def _serialize_vehicle(self, handle: int, fields: dict) -> bytes:
        lanes = tuple(fields.pop("lanes", ()) or ())
        segs = tuple(fields.pop("segs", ()) or ())
        loc_offset = int(fields.pop("loc_offset", 0))
        st = VehiclePosition()
        st.Checksum = 0
        for key, value in fields.items():
            if not hasattr(st, key):
                raise ValueError(f"VehiclePosition 没有字段 {key!r}")
            setattr(st, key, value)
        lanes_arr = (ctypes.c_uint32 * max(1, len(lanes)))()
        for i, v in enumerate(lanes):
            lanes_arr[i] = v
        segs_arr = (ctypes.c_uint32 * max(1, len(segs)))()
        for i, v in enumerate(segs):
            segs_arr[i] = v
        out = (ctypes.c_uint8 * 4096)()
        out_len = ctypes.c_uint32(4096)
        rc = self._lib.arhud_serialize_vehicle(
            ctypes.byref(st), lanes_arr, len(lanes), segs_arr, len(segs),
            loc_offset, out, ctypes.byref(out_len))
        if rc != 0:
            raise RuntimeError(f"序列化 VehiclePosition 失败 rc={rc}")
        return bytes(out[:out_len.value])

    # ---------------- pcap 回放 ----------------
    def replay_start(self, handle: int, pcap_path: str, loop: bool = True,
                     interval_ms: int = 10) -> int:
        return int(self._lib.arhud_server_replay_start(
            ctypes.c_void_p(handle), str(pcap_path).encode(),
            1 if loop else 0, int(interval_ms)))

    def replay_stop(self, handle: int) -> None:
        self._lib.arhud_server_replay_stop(ctypes.c_void_p(handle))

    def replay_sent(self, handle: int) -> int:
        return int(self._lib.arhud_server_replay_sent(ctypes.c_void_p(handle)))


def open_library() -> SomeipLib | None:
    """按 hudcore 探测结果加载库并返回绑定封装；不可用时返回 None。"""
    handle = load_someip_library()
    if handle is None:
        return None
    return SomeipLib(handle)


def library_status() -> str:
    """库状态（供界面状态栏显示）。"""
    return describe_library_status()


__all__ = [
    "SomeipLib", "open_library", "library_status", "default_ip",
    "STRUCT_CLASSES", "EDITABLE_CLASSES", "STRUCT_TYPES", "KIND_SERVICE_EVENT",
    "RTK", "IMU", "ChangeLane", "PilotStatus", "PilotAlarm", "Broadcast",
    "HudMappath", "HudNavmap", "VehiclePosition",
]
