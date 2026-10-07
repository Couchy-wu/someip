#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arhud_py.py —— Python 调用 C++ 服务端库（libarhud_server.so，ctypes）
=========================================================================
C++ 库负责通信内核（offer 服务/事件、发送、pcap 流式回放、TP 重组），
Python 负责业务：指定 pcap 回放/发布、对数据结构赋值后组包发送。

用法：
    from arhud_py import ArHudServer

    srv = ArHudServer(unicast="192.168.1.10")     # 自动探测 IP
    srv.start()
    srv.notify_fields("RTK", counter=1, longitude=116.397, latitude=39.908)  # 结构化赋值
    srv.notify_raw(0x000A, 0x8001, b"...")        # 原始字节

    # ① 指定 pcap 回放（timing="capture" = 按抓包原始节奏，与参考实现一致）
    srv.replay("out.pcap", timing="capture")
    # ② 目录：目录下所有 *.pcap（out.pcap 优先）循环回放 + 发布
    srv.replay_dir("/path/to/pcap_dir", loop=True, timing="capture", speed=1.0)
    # ③ 回放前先看 pcap 里有什么、服务表覆不覆盖得住
    print(ArHudServer.pcap_events(["/path/to/out.pcap"]))

结构化类型（C++ 序列化，大端 + CRC32 自动补齐）：
    RTK / IMU / ChangeLane / PilotStatus / PilotAlarm / Broadcast /
    HudMappath / HudNavmap / VehiclePosition

服务表代（profile）：
    old          默认，11 服务/23 事件，与参考配置 old/someip_arhud01_pcap_server.json 逐条一致
    old-capture  old + 抓包实测的 10 个事件（11 服务/33 事件），用于"完整回放/发布"参考抓包
    bplus        新一代接口，6 服务/38 事件
    auto         按 pcap 自动挑一个能覆盖住的最小的表（见 ArHudServer.for_pcaps）
"""
import ctypes
import glob
import json
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
# 2026-02 新增：回放尝试计数（含失败）与服务表代诊断
_lib.arhud_server_replay_attempted.restype = ctypes.c_uint64
_lib.arhud_server_replay_attempted.argtypes = [ctypes.c_void_p]
_lib.arhud_server_profile.restype = ctypes.c_char_p
_lib.arhud_server_profile.argtypes = [ctypes.c_void_p]
_lib.arhud_server_service_count.restype = ctypes.c_int
_lib.arhud_server_service_count.argtypes = [ctypes.c_void_p]
_lib.arhud_server_event_count.restype = ctypes.c_int
_lib.arhud_server_event_count.argtypes = [ctypes.c_void_p]


# ---------------- 扩展接口（多文件/目录、按抓包节奏、统计报告、pcap 体检） ----------------

class ReplayOpts(ctypes.Structure):
    """与 C 的 arhud_replay_opts 对齐"""
    _fields_ = [("loop", ctypes.c_int),
                ("timing", ctypes.c_int),          # 0=固定间隔 1=按抓包时间戳
                ("interval_ms", ctypes.c_uint32),
                ("speed", ctypes.c_double),
                ("max_loops", ctypes.c_uint32),
                ("start_delay_ms", ctypes.c_uint32),
                ("log_every", ctypes.c_int)]


_lib.arhud_replay_opts_default.restype = None
_lib.arhud_replay_opts_default.argtypes = [ctypes.POINTER(ReplayOpts)]
_lib.arhud_server_replay_start_ex.restype = ctypes.c_int
_lib.arhud_server_replay_start_ex.argtypes = [ctypes.c_void_p,
                                              ctypes.POINTER(ctypes.c_char_p),
                                              ctypes.c_int,
                                              ctypes.POINTER(ReplayOpts)]
_lib.arhud_server_replay_parsed.restype = ctypes.c_uint64
_lib.arhud_server_replay_parsed.argtypes = [ctypes.c_void_p]
_lib.arhud_server_replay_unregistered.restype = ctypes.c_uint64
_lib.arhud_server_replay_unregistered.argtypes = [ctypes.c_void_p]
_lib.arhud_server_replay_running.restype = ctypes.c_int
_lib.arhud_server_replay_running.argtypes = [ctypes.c_void_p]
_lib.arhud_server_replay_report.restype = ctypes.c_int
_lib.arhud_server_replay_report.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]

_lib.arhud_pcap_events.restype = ctypes.c_int
_lib.arhud_pcap_events.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_int,
                                   ctypes.c_char_p, ctypes.c_uint32]
_lib.arhud_pcap_error.restype = ctypes.c_char_p
_lib.arhud_pcap_error.argtypes = []
_lib.arhud_profile_events.restype = ctypes.c_int
_lib.arhud_profile_events.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
_lib.arhud_profile_name.restype = ctypes.c_char_p
_lib.arhud_profile_name.argtypes = []

_BUF = 1 << 22  # 4MB：足够放服务表/事件表 JSON


def pcap_events(paths):
    """扫一组 pcap（可传文件/目录/列表），返回出现过的 [(service, event), ...]（不发送数据）"""
    if isinstance(paths, str):
        paths = find_pcaps(paths)
    paths = list(paths)
    if not paths:
        return []
    arr = (ctypes.c_char_p * len(paths))(*[p.encode() for p in paths])
    buf = ctypes.create_string_buffer(_BUF)
    n = _lib.arhud_pcap_events(arr, len(paths), buf, _BUF)
    if n < 0:
        raise RuntimeError("arhud_pcap_events 失败: %s" % _lib.arhud_pcap_error().decode())
    data = json.loads(buf.value.decode())
    return [(e["service"], e["event"]) for e in data["events"]]


def profile_events(profile=None):
    """返回某个服务表代定义的全部 [(service, event), ...]"""
    buf = ctypes.create_string_buffer(_BUF)
    n = _lib.arhud_profile_events(profile.encode() if profile else None, buf, _BUF)
    if n < 0:
        raise RuntimeError("arhud_profile_events 失败（缓冲区不足？）")
    data = json.loads(buf.value.decode())
    out = []
    for s in data["services"]:
        for e in s["events"]:
            out.append((s["service"], e["event"]))
    return out


def profile_name():
    """当前环境变量归一化后的服务表代（old / old-capture / bplus）"""
    return _lib.arhud_profile_name().decode()


def find_pcaps(path):
    """
    路径展开：文件 → [文件]；目录 → 目录下 *.pcap（out.pcap 排最前，其余按名字排序）。
    参考实现只读 <目录>/out.pcap；这里保留"out.pcap 优先"，并支持一个目录多个 pcap。
    """
    if os.path.isfile(path):
        return [path]
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    files = sorted(glob.glob(os.path.join(path, "*.pcap")))
    files += sorted(glob.glob(os.path.join(path, "*.pcapng")))
    prio = [f for f in files if os.path.basename(f) == "out.pcap"]
    rest = [f for f in files if os.path.basename(f) != "out.pcap"]
    return prio + rest


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

    # 按 pcap 自动挑表时的候选顺序（越靠前越"保守"：表越小越好）
    PROFILE_CANDIDATES = ("old", "old-capture", "bplus")

    def __init__(self, unicast=None, config_path=None, profile=None):
        """
        profile: None=用环境变量（默认 old）/ "old" / "old-capture" / "bplus"。
                 必须在 create 之前设置，因为 C++ 侧在 create 时读 ARHUD_SERVICE_PROFILE
                 并据此生成 SP 配置（服务/事件表要在 SPInit 时就固定下来）。
        """
        if profile:
            os.environ["ARHUD_SERVICE_PROFILE"] = str(profile)
        self.profile = profile_name()
        self._handle = _lib.arhud_server_create(
            (unicast or _default_ip()).encode(), config_path.encode() if config_path else None)
        if not self._handle:
            raise RuntimeError("arhud_server_create failed (profile=%s)" % self.profile)

    # ---------- 服务表 / pcap 体检（静态方法，不需要已创建服务端） ----------

    @staticmethod
    def pcap_events(paths):
        """扫 pcap，返回出现过的 [(service, event), ...]"""
        return pcap_events(find_pcaps(paths) if isinstance(paths, str) else paths)

    @staticmethod
    def profile_events(profile=None):
        """返回某个 profile 定义的全部 [(service, event), ...]"""
        return profile_events(profile)

    @classmethod
    def best_profile_for_pcaps(cls, paths):
        """
        挑一个"能覆盖住这些 pcap 里所有事件"的最小的表。
        返回 (profile, missing)：missing 是非空 set 时表示没有哪个表能全覆盖（已选覆盖最好的）。
        """
        if isinstance(paths, str):
            paths = find_pcaps(paths)
        used = set(cls.pcap_events(paths))
        best, best_missing = None, None
        for cand in cls.PROFILE_CANDIDATES:
            missing = used - set(profile_events(cand))
            if not missing:
                return cand, set()
            if best is None or len(missing) < len(best_missing):
                best, best_missing = cand, missing
        return best, best_missing

    @classmethod
    def for_pcaps(cls, paths, unicast=None, config_path=None):
        """
        按 pcap 内容自动选表并创建服务端（profile="auto" 的落地实现）。
        用法：srv = ArHudServer.for_pcaps("/path/to/pcap_dir"); srv.start(); srv.replay_dir(...)
        """
        prof, missing = cls.best_profile_for_pcaps(paths)
        if missing:
            print("[arhud] 警告：没有哪个服务表能覆盖 pcap 里全部事件，缺少 %d 个：%s"
                  % (len(missing), sorted("0x%04X:0x%04X" % m for m in missing)), file=sys.stderr)
        srv = cls(unicast=unicast, config_path=config_path, profile=prof)
        srv.profile = prof
        return srv

    def start(self):
        if _lib.arhud_server_start(self._handle) != 0:
            raise RuntimeError("arhud_server_start failed")
        return self

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

    def replay(self, pcap_path, loop=True, interval_ms=10, timing="interval",
               speed=1.0, max_loops=0, start_delay_ms=0, log_every=0):
        """
        回放并发布 pcap（后台线程，C++ 流式解析 + SOME/IP-TP 重组）。

        pcap_path : pcap 文件 **或目录**（目录→目录下所有 *.pcap，out.pcap 优先）
        loop      : 是否循环
        timing    : "capture" = 按抓包原始时间戳节奏（与参考实现一致）；
                    "interval" = 固定 interval_ms 间隔（默认，兼容老行为）
        speed     : timing="capture" 时的倍速（2.0=两倍速，0.5=放慢一半）
        max_loops : 最大轮数（0=不限；loop=False 时只跑 1 轮）
        start_delay_ms: 起播前等待（等客户端订阅稳定，建议 15000~25000）
        log_every : >0 时每 N 条打印一行进度

        返回 0 成功，其它失败（错误信息见 replay_status()）。
        """
        paths = find_pcaps(pcap_path) if isinstance(pcap_path, str) else list(pcap_path)
        if not paths:
            raise ValueError("没有找到 pcap 文件: %s" % pcap_path)
        return self._replay_paths(paths, loop, interval_ms, timing, speed,
                                  max_loops, start_delay_ms, log_every)

    def replay_dir(self, directory, pattern="*.pcap", loop=True, **kw):
        """回放一个目录下的 pcap（out.pcap 优先，其余按名字排序）。"""
        import glob as _glob
        paths = sorted(_glob.glob(os.path.join(directory, pattern)))
        if not paths:
            raise ValueError("目录下没有 %s: %s" % (pattern, directory))
        paths = [p for p in paths if os.path.basename(p) == "out.pcap"] + \
                [p for p in paths if os.path.basename(p) != "out.pcap"]
        return self._replay_paths(paths, loop, kw.pop("interval_ms", 10),
                                  kw.pop("timing", "capture"), kw.pop("speed", 1.0),
                                  kw.pop("max_loops", 0), kw.pop("start_delay_ms", 0),
                                  kw.pop("log_every", 0))

    def _replay_paths(self, paths, loop, interval_ms, timing, speed, max_loops,
                      start_delay_ms, log_every):
        opts = ReplayOpts()
        _lib.arhud_replay_opts_default(ctypes.byref(opts))
        opts.loop = 1 if loop else 0
        opts.timing = 1 if str(timing).lower() in ("capture", "pcap", "realtime", "real") else 0
        opts.interval_ms = int(interval_ms)
        opts.speed = float(speed)
        opts.max_loops = int(max_loops)
        opts.start_delay_ms = int(start_delay_ms)
        opts.log_every = int(log_every)
        arr = (ctypes.c_char_p * len(paths))(*[p.encode() for p in paths])
        return _lib.arhud_server_replay_start_ex(self._handle, arr, len(paths),
                                                 ctypes.byref(opts))

    def replay_stop(self):
        _lib.arhud_server_replay_stop(self._handle)

    def replay_running(self):
        return bool(_lib.arhud_server_replay_running(self._handle))

    def replay_status(self):
        """回放进度：{parsed, sent, attempted, unregistered, running}"""
        return {
            "parsed": _lib.arhud_server_replay_parsed(self._handle),
            "sent": _lib.arhud_server_replay_sent(self._handle),
            "attempted": _lib.arhud_server_replay_attempted(self._handle),
            "unregistered": _lib.arhud_server_replay_unregistered(self._handle),
            "running": self.replay_running(),
        }

    def replay_report(self):
        """回放报告（dict）：总数 + 逐事件 attempted/sent/unregistered"""
        buf = ctypes.create_string_buffer(_BUF)
        n = _lib.arhud_server_replay_report(self._handle, buf, _BUF)
        if n < 0:
            raise RuntimeError("replay_report 失败（缓冲区不足）")
        return json.loads(buf.value.decode())

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
