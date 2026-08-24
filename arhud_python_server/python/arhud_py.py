#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arhud_py.py —— Python 调用 C++ 服务端库（libarhud_server.so，ctypes）
=========================================================================
C++ 库负责 vsomeip 通信内核（offer 11 服务/23 事件、发送、pcap 回放、TP 重组），
Python 负责业务：指定 pcap 回放、对数据结构赋值后组包发送。

用法：
    from arhud_py import ArHudServer
    srv = ArHudServer(unicast="192.168.1.10")     # 自动探测 IP
    srv.start()
    srv.notify_fields("RTK", counter=1, longitude=116.397, latitude=39.908)  # 结构化赋值
    srv.notify_raw(0x000A, 0x8001, b"...")        # 原始字节
    srv.replay("out.pcap", loop=True, interval_ms=10)   # 指定 pcap 回放
    srv.replay_sent()                             # 已回放条数
    srv.stop()

结构化类型（C++ 序列化，大端 + CRC32 自动补齐）：
    RTK / IMU / ChangeLane / PilotStatus / PilotAlarm / Broadcast /
    HudMappath / HudNavmap / VehiclePosition
"""
import ctypes
import os
import socket
import sys

def _default_lib_name():
    return "libarhud_server.dll" if sys.platform == "win32" else "libarhud_server.so"

LIB_PATH = os.environ.get("ARHUD_LIB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), _default_lib_name())
_lib = ctypes.CDLL(LIB_PATH)

# ---------------- ctypes 结构体（与 arhud_types.h 对齐，#pragma pack(1)） ----------------

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

# ---------------- C 接口绑定 ----------------

_lib.arhud_server_create.restype = ctypes.c_void_p
_lib.arhud_server_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
_lib.arhud_server_destroy.argtypes = [ctypes.c_void_p]
_lib.arhud_server_start.restype = ctypes.c_int
_lib.arhud_server_start.argtypes = [ctypes.c_void_p]
_lib.arhud_server_stop.argtypes = [ctypes.c_void_p]
_lib.arhud_server_notify.restype = ctypes.c_int
_lib.arhud_server_notify.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16,
                                     ctypes.c_void_p, ctypes.c_uint32]
_lib.arhud_server_replay_start.restype = ctypes.c_int
_lib.arhud_server_replay_start.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                           ctypes.c_int, ctypes.c_uint32]
_lib.arhud_server_replay_stop.argtypes = [ctypes.c_void_p]
_lib.arhud_server_replay_sent.restype = ctypes.c_uint64
_lib.arhud_server_replay_sent.argtypes = [ctypes.c_void_p]

U8 = ctypes.POINTER(ctypes.c_uint8)
U32 = ctypes.POINTER(ctypes.c_uint32)


def _bind_serializer(name):
    fn = getattr(_lib, name)
    fn.restype = ctypes.c_int
    fn.argtypes = [ctypes.c_void_p, U8, ctypes.POINTER(ctypes.c_uint32)]
    return fn


_SERIALIZERS = {
    "RTK": (RTK, _bind_serializer("arhud_serialize_rtk")),
    "IMU": (IMU, _bind_serializer("arhud_serialize_imu")),
    "ChangeLane": (ChangeLane, _bind_serializer("arhud_serialize_changelane")),
    "PilotStatus": (PilotStatus, _bind_serializer("arhud_serialize_pilot_status")),
    "PilotAlarm": (PilotAlarm, _bind_serializer("arhud_serialize_pilot_alarm")),
    "Broadcast": (Broadcast, _bind_serializer("arhud_serialize_broadcast")),
    "HudMappath": (HudMappath, _bind_serializer("arhud_serialize_hud_mappath")),
    "HudNavmap": (HudNavmap, _bind_serializer("arhud_serialize_hud_navmap")),
}
_lib.arhud_serialize_vehicle.restype = ctypes.c_int
_lib.arhud_serialize_vehicle.argtypes = [ctypes.c_void_p, U32, ctypes.c_uint32,
                                         U32, ctypes.c_uint32, ctypes.c_uint8,
                                         U8, ctypes.POINTER(ctypes.c_uint32)]


def _default_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class ArHudServer:
    """C++ 服务端库的 Python 封装"""

    def __init__(self, unicast=None, config_path=None):
        self._handle = _lib.arhud_server_create(
            (unicast or _default_ip()).encode(), config_path.encode() if config_path else None)
        if not self._handle:
            raise RuntimeError("arhud_server_create failed")

    def start(self):
        if _lib.arhud_server_start(self._handle) != 0:
            raise RuntimeError("arhud_server_start failed")

    def stop(self):
        _lib.arhud_server_stop(self._handle)

    def close(self):
        self.stop()
        _lib.arhud_server_destroy(self._handle)
        self._handle = None

    def __del__(self):
        try:
            if self._handle:
                self.close()
        except Exception:
            pass

    # ---------- 发送 ----------

    def notify_raw(self, service, event, data: bytes):
        """发送原始字节载荷"""
        buf = ctypes.create_string_buffer(data)
        return _lib.arhud_server_notify(self._handle, service, event, buf, len(data))

    def notify_fields(self, kind, counter=1, **fields):
        """
        结构化赋值 → C++ 序列化（大端 + CRC32）→ 发送。
        kind: RTK/IMU/ChangeLane/PilotStatus/PilotAlarm/Broadcast/HudMappath/HudNavmap/VehiclePosition
        返回 (service, event, payload)。
        """
        if kind == "VehiclePosition":
            return self._notify_vehicle(counter, **fields)
        if kind not in _SERIALIZERS:
            raise ValueError(f"unknown kind: {kind}")
        st_cls, ser = _SERIALIZERS[kind]
        st = st_cls()
        st.Checksum = 0
        if "counter" in fields:
            fields = dict(fields)
            fields["Counter"] = fields.pop("counter")
        for k, v in fields.items():
            if not hasattr(st, k):
                raise ValueError(f"{kind} has no field '{k}'")
            if isinstance(getattr(st, k), bytes):
                setattr(st, k, str(v).encode())
            else:
                setattr(st, k, v)
        out = (ctypes.c_uint8 * 4096)()
        out_len = ctypes.c_uint32(4096)
        rc = ser(ctypes.byref(st), out, ctypes.byref(out_len))
        if rc != 0:
            raise RuntimeError(f"serialize {kind} failed rc={rc}")
        payload = bytes(out[: out_len.value])
        service, event = KIND_SERVICE_EVENT[kind]
        self.notify_raw(service, event, payload)
        return service, event, payload

    def _notify_vehicle(self, counter, lanes=(), segs=(), loc_offset=0, **fields):
        st = VehiclePosition()
        st.Checksum = 0
        st.Counter = counter
        for k, v in fields.items():
            if not hasattr(st, k):
                raise ValueError(f"VehiclePosition has no field '{k}'")
            setattr(st, k, v)
        lanes_arr = (ctypes.c_uint32 * max(1, len(lanes)))()
        for i, v in enumerate(lanes):
            lanes_arr[i] = v
        segs_arr = (ctypes.c_uint32 * max(1, len(segs)))()
        for i, v in enumerate(segs):
            segs_arr[i] = v
        out = (ctypes.c_uint8 * 4096)()
        out_len = ctypes.c_uint32(4096)
        rc = _lib.arhud_serialize_vehicle(ctypes.byref(st), lanes_arr, len(lanes),
                                          segs_arr, len(segs), loc_offset, out,
                                          ctypes.byref(out_len))
        if rc != 0:
            raise RuntimeError(f"serialize VehiclePosition failed rc={rc}")
        payload = bytes(out[: out_len.value])
        self.notify_raw(0x000A, 0x8001, payload)
        return 0x000A, 0x8001, payload

    # ---------- pcap 回放 ----------

    def replay(self, pcap_path, loop=True, interval_ms=10):
        """指定 pcap 文件回放（后台线程，C++ 内做 SOME/IP-TP 重组）。返回已解析消息数。"""
        return _lib.arhud_server_replay_start(self._handle, pcap_path.encode(),
                                             1 if loop else 0, interval_ms)

    def replay_stop(self):
        _lib.arhud_server_replay_stop(self._handle)

    def replay_sent(self):
        return _lib.arhud_server_replay_sent(self._handle)


# 类型 → (service, event) 映射（与内置注册表一致）
KIND_SERVICE_EVENT = {
    "RTK": (0x000B, 0x8001),
    "IMU": (0x000B, 0x8002),
    "ChangeLane": (0x000D, 0x8001),
    "PilotStatus": (0x000D, 0x8002),
    "PilotAlarm": (0x000D, 0x8003),
    "Broadcast": (0x000D, 0x8004),
    "HudMappath": (0x010A, 0x8002),
    "HudNavmap": (0x010A, 0x8003),
    "VehiclePosition": (0x000A, 0x8001),
}
