#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AR-HUD 23 服务 SOME/IP 数据类型：序列化 / 反序列化
===================================================
依据 new_describe.md（to_longjie_demo_20250625）：
  - 所有载荷 = 先 Checksum(uint32) + Counter(uint16)，再按各类型字段
  - 类型 0..11 有完整结构定义，实现 parse/serialize
  - 类型 12..22 仅有概要 → 按 Opaque 处理（框架级：帧正确、载荷 hex 展示）

【文档矛盾点的实现决策】（详见 SOLUTION_HUD.md）
  1) 字节序：主文档 4.3/九.1 与 SOME/IP 标准 = 大端(网络序)。附录B 的"小端"未采纳。
     若真实 PCAP 载荷是小端，把 ENDIAN 改为 '<' 即可（一处修改）。
  2) 字符串：长度(uint32) + UTF-8 BOM(3字节 0xEF 0xBB 0xBF) + 内容（按 5.12 的 Python 代码）。
  3) 动态数组长度字段 = 字节数（元素数 = 长度 // 元素大小，按 5.2 VehiclePosition 的代码）。
  4) "总大小"标注与字段不符处，以字段序列为准。
"""

import struct

# ---------- 可切换格式常量 ----------
ENDIAN = ">"          # 大端（网络字节序）；若实测载荷为小端改为 "<"
STRING_BOM = b"\xEF\xBB\xBF"
ARRAY_LENGTH_IS_BYTES = True   # True: 长度=字节数; False: 长度=元素个数


# ---------- 23 个事件注册表 ----------
# (service, instance, event, name, event_group, port, kind)
# kind: 已实现类型名 或 "Opaque"
HUD_EVENTS = [
    (0x000A, 0x000A, 0x8001, "VehiclePositionInfoNotify",       0x1101, 51400, "VehiclePosition"),
    (0x000B, 0x000B, 0x8001, "RTKInfoNotify",                   0x1101, 51401, "RTK"),
    (0x000B, 0x000B, 0x8002, "IMUInfoNotify",                   0x1101, 51401, "IMU"),
    (0x000C, 0x000C, 0x8001, "ObstacleInfoNotify",              0x1101, 51402, "Obstacle"),
    (0x000C, 0x000C, 0x8002, "LaneLineDataNotify",             0x1101, 51402, "LaneLine"),
    (0x000D, 0x000D, 0x8001, "ChangeLaneDataNotify",           0x1101, 51403, "ChangeLane"),
    (0x000D, 0x000D, 0x8002, "PilotStatusNotify",              0x1101, 51403, "PilotStatus"),
    (0x000D, 0x000D, 0x8003, "PilotAlarmAndNoticeInfoNotify",  0x1101, 51403, "PilotAlarm"),
    (0x000D, 0x000D, 0x8004, "BroadcastInfoNotify",            0x1101, 51403, "Broadcast"),
    (0x010A, 0x0001, 0x8001, "HudRoadInfoNotify",              0x1101, 52001, "HudRoad"),
    (0x010A, 0x0001, 0x8002, "HudMappathInfo_EG",              0x1101, 52001, "HudMappath"),
    (0x010A, 0x0001, 0x8003, "HudNavigationmap",               0x1101, 52001, "HudNavmap"),
    (0x010A, 0x0001, 0x8004, "OverseasHudRoadInfoNotify",      0x1101, 52001, "Opaque"),
    (0x000C, 0x000C, 0x8003, "NewLanelineDataNotify",          0x1101, 51402, "Opaque"),
    (0x000D, 0x000D, 0x8005, "NewBroadcastInfoNotify",         0x1101, 51403, "Opaque"),
    (0x000E, 0x000E, 0x8001, "PlanningLineInfoNotify",         0x1101, 51404, "Opaque"),
    (0x0007, 0x0007, 0x8001, "NavigationStatus_LinkInfoNotify", 0x1101, 51405, "Opaque"),
    (0x0017, 0x0017, 0x8003, "NewParkingRealTimeDataNotify",   0x1101, 51406, "Opaque"),
    (0x002B, 0x002B, 0x8001, "NavigationHDLink2Info",          0x1101, 51407, "Opaque"),
    (0x8202, 0x8202, 0x8002, "sdTraffiIncident",               0x1101, 51408, "Opaque"),
    (0x000E, 0x000E, 0x8002, "newPlanningLineInfo",            0x1102, 51404, "Opaque"),
    (0x000E, 0x000E, 0x8003, "drivingAreaIdentification",      0x1103, 51404, "Opaque"),
    (0x0018, 0x0018, 0x8001, "hpaMapDataNotify",               0x1101, 51409, "Opaque"),
]

# 按 service 分组（每个 service 一个 vsomeip 应用）
def services_map():
    m = {}
    for svc, inst, event, name, group, port, kind in HUD_EVENTS:
        m.setdefault(svc, {"instance": inst, "port": port, "events": []})
        m[svc]["events"].append((event, name, group, kind))
    return m


# ---------- 基础工具 ----------

def _pack(fmt, value):
    return struct.pack(ENDIAN + fmt, value)


def _unpack(fmt, data, offset):
    return struct.unpack_from(ENDIAN + fmt, data, offset)[0], offset + struct.calcsize(ENDIAN + fmt)


def pack_fields(fields, data):
    return b"".join(_pack(fmt, data[name]) for name, fmt in fields)


def unpack_fields(fields, data, offset):
    out = {}
    for name, fmt in fields:
        out[name], offset = _unpack(fmt, data, offset)
    return out, offset


def serialize_string(s: str) -> bytes:
    """字符串：长度(4) + BOM(3) + 内容（按 5.12；空串只写长度 0）"""
    if not s:
        return _pack("I", 0)
    content = s.encode("utf-8")
    return _pack("I", 3 + len(content)) + STRING_BOM + content


def deserialize_string(data: bytes, offset: int):
    length, offset = _unpack("I", data, offset)
    if length == 0:
        return "", offset
    if data[offset:offset + 3] == STRING_BOM:
        offset += 3
        length -= 3
    content = data[offset:offset + length]
    return content.decode("utf-8", "replace"), offset + length


def serialize_array(elements: list, elem_size: int, elem_bytes_factory) -> bytes:
    """动态数组：长度字段(字节数 或 元素数) + 元素序列"""
    body = b"".join(elem_bytes_factory(e) for e in elements)
    n = len(body) if ARRAY_LENGTH_IS_BYTES else len(elements)
    return _pack("I", n) + body


def deserialize_array(data: bytes, offset: int, elem_size: int, elem_parse):
    n, offset = _unpack("I", data, offset)
    count = n // elem_size if ARRAY_LENGTH_IS_BYTES else n
    out = []
    for _ in range(count):
        elem, offset = elem_parse(data, offset)
        out.append(elem)
    return out, offset


# ---------- 类型 0: VehiclePositionInfoNotify (0x000A/0x000A/0x8001) ----------
VEHICLE_FIELDS = [
    ("Checksum", "I"), ("Counter", "H"),
    ("Longitude", "d"), ("Latitude", "d"), ("altitude", "d"), ("Heading", "d"),
    ("hd_lane_left_angle", "d"), ("Hd_lane_right_angle", "d"), ("VehicleSpeed", "d"),
    ("acceleration", "d"), ("x_speed", "d"), ("y_speed", "d"), ("z_speed", "d"), ("timestamp", "d"),
    ("hd_link_id", "I"), ("hd_lane_id", "I"), ("hd_lane_type", "I"), ("on_lane_offset", "d"),
    ("hd_lane_seq", "I"), ("hd_lane_num", "I"),
    ("hd_lane_left_lateral_offset", "d"), ("hd_lane_right_lateral_offset", "d"),
    ("roll", "d"), ("pitch", "d"),
    ("HdStatus", "B"), ("hdmap_version", "B"), ("fusion_status", "B"), ("pos_confidence", "d"),
    ("position_type", "B"), ("break_light", "B"), ("indicator_light", "B"),
    ("Lights", "B"), ("Weather", "B"), ("target_cruise_speed", "f"),
]


def serialize_vehicle(data) -> bytes:
    r = pack_fields(VEHICLE_FIELDS, data)
    r += serialize_array(data["target_lane_id"], 4, lambda v: _pack("I", v))
    r += serialize_array(data["target_lane_id_segment"], 4, lambda v: _pack("I", v))
    r += _pack("B", data["localization_output_offset"])
    return r


def deserialize_vehicle(data, offset=0):
    out, offset = unpack_fields(VEHICLE_FIELDS, data, offset)
    out["target_lane_id"], offset = deserialize_array(data, offset, 4, lambda d, o: _unpack("I", d, o))
    out["target_lane_id_segment"], offset = deserialize_array(data, offset, 4, lambda d, o: _unpack("I", d, o))
    out["localization_output_offset"], offset = _unpack("B", data, offset)
    return out, offset


# ---------- 类型 1: RTKInfoNotify (0x000B/0x000B/0x8001) ----------
RTK_FIELDS = [
    ("Checksum", "I"), ("Counter", "H"), ("rtk_status", "I"),
    ("utc_time_us", "d"), ("sys_time_us", "d"), ("longitude", "d"), ("latitude", "d"),
    ("altitude", "d"), ("longitude_acc", "d"), ("latitude_acc", "d"), ("altitude_acc", "d"),
    ("heading_move", "d"), ("heading_double_ant", "d"), ("heading_move_acc", "d"),
    ("speed_2d", "d"), ("speed_acc", "d"), ("speed_n", "d"), ("speed_e", "d"), ("speed_u", "d"),
    ("g_dop", "d"), ("h_dop", "d"), ("v_dop", "d"),
    ("satellite_num", "I"), ("satellite_used", "I"),
    ("snr_max", "d"), ("snr_mix", "d"), ("snr_avr", "d"),
]


def serialize_rtk(data): return pack_fields(RTK_FIELDS, data)


def deserialize_rtk(data, offset=0): return unpack_fields(RTK_FIELDS, data, offset)


# ---------- 类型 2: IMUInfoNotify (0x000B/0x000B/0x8002) ----------
IMU_FIELDS = [
    ("Checksum", "I"), ("Counter", "H"),
    ("angular_velocity_x", "d"), ("angular_velocity_y", "d"), ("angular_velocity_z", "d"),
    ("acc_speed_x", "d"), ("acc_speed_y", "d"), ("acc_speed_z", "d"),
    ("IMU_status", "B"), ("IMU_current_temperature", "d"), ("sys_time_us", "d"),
    ("is_calibrated", "B"),
]


def serialize_imu(data): return pack_fields(IMU_FIELDS, data)


def deserialize_imu(data, offset=0): return unpack_fields(IMU_FIELDS, data, offset)


# ---------- 类型 3: ObstacleInfoNotify (0x000C/0x000C/0x8001) ----------
OBSTACLE_FIELDS = [("Checksum", "I"), ("Counter", "H"), ("target_flag", "B")]
OBSTACLE_ITEM_FIELDS = [
    ("ObstacleType", "I"), ("confidence", "d"), ("Obstacle_Id_i", "I"),
    ("ObstacleDistance_X_i", "d"), ("ObstacleDistance_Y_i", "d"), ("ObstacleDistance_Z_i", "d"),
    ("Bounding_box_length_i", "f"), ("Bounding_box_width_i", "f"), ("Bounding_box_height_i", "f"),
    ("break_light", "B"), ("indicator_light", "B"), ("obj_speed", "d"),
    ("ObstacleState", "B"), ("obstacle_timestamp", "d"), ("obstacle_camera_timestamp", "d"),
    ("moving", "B"), ("obj_heading", "d"), ("Obj_direction", "d"), ("ObstacleWarningBrakeState", "B"),
]


def serialize_obstacle(data):
    r = pack_fields(OBSTACLE_FIELDS, data)
    r += serialize_array(data["FieldLength_Object"], 97, lambda o: pack_fields(OBSTACLE_ITEM_FIELDS, o))
    return r


def deserialize_obstacle(data, offset=0):
    out, offset = unpack_fields(OBSTACLE_FIELDS, data, offset)
    out["FieldLength_Object"], offset = deserialize_array(
        data, offset, 97, lambda d, o: unpack_fields(OBSTACLE_ITEM_FIELDS, d, o))
    return out, offset


# ---------- 类型 4: LaneLineDataNotify (0x000C/0x000C/0x8002) ----------
LANELINE_HEAD = [("Checksum", "I"), ("Counter", "H")]
FLL_FIELDS = [
    ("LineID", "i"), ("LineType", "B"), ("LineColor", "B"), ("LineWidth", "f"),
    ("Line_confidence", "d"), ("CurvatureEquation_c0", "f"), ("CurvatureEquation_c1", "f"),
    ("CurvatureEquation_c2", "f"), ("CurvatureEquation_c3", "f"),
    ("Line_Startpoint_x", "f"), ("Line_Startpoint_y", "f"), ("Line_Startpoint_z", "f"),
    ("Line_Endpoint_x", "f"), ("Line_Endpoint_y", "f"), ("Line_Endpoint_z", "f"),
    ("sys_time_us", "d"),
]
FLRM_FIELDS = [
    ("RoadMarkingID_i", "I"), ("RoadMarkingType_i", "B"), ("RoadMarkingType_confidence_i", "d"),
    ("RoadMarking_length_i", "f"), ("RoadMarking_width_i", "f"), ("RoadMarking_height_i", "f"),
    ("RoadMarking_Distance_X_i", "d"), ("RoadMarking_Distance_Y_i", "d"),
    ("RoadMarking_Distance_Z_i", "d"), ("RoadMarkingPosition_confidence", "d"),
]
FLTLA_FIELDS = [
    ("TLAID_i", "I"), ("TLA_Distance_X", "d"), ("TLA_Distance_Y", "d"), ("TLA_Distance_Z", "d"),
    ("TLAPosition_confidence", "d"),
    ("LeftTLA_Color", "B"), ("LeftTLA_Type", "B"), ("StraightTLA_Color", "B"),
    ("StraightTLA_Type", "B"), ("RightTLA_Color", "B"), ("RightTLA_Type", "B"),
]


def serialize_laneline(data):
    r = pack_fields(LANELINE_HEAD, data)
    r += serialize_array(data["FieldLength_Line"], 66, lambda e: pack_fields(FLL_FIELDS, e))
    r += serialize_array(data["FieldLength_RoadMarking"], 57, lambda e: pack_fields(FLRM_FIELDS, e))
    r += serialize_array(data["FieldLength_TLA"], 42, lambda e: pack_fields(FLTLA_FIELDS, e))
    return r


def deserialize_laneline(data, offset=0):
    out, offset = unpack_fields(LANELINE_HEAD, data, offset)
    out["FieldLength_Line"], offset = deserialize_array(data, offset, 66, lambda d, o: unpack_fields(FLL_FIELDS, d, o))
    out["FieldLength_RoadMarking"], offset = deserialize_array(data, offset, 57, lambda d, o: unpack_fields(FLRM_FIELDS, d, o))
    out["FieldLength_TLA"], offset = deserialize_array(data, offset, 42, lambda d, o: unpack_fields(FLTLA_FIELDS, d, o))
    return out, offset


# ---------- 类型 5: ChangeLaneDataNotify (0x000D/0x000D/0x8001) ----------
CHANGELANE_FIELDS = [
    ("Checksum", "I"), ("Counter", "H"), ("ChangeLaneState", "I"), ("ChangeLaneDirection", "B"),
    ("is_change_safety", "B"), ("ChangeLane_timestamp", "I"), ("change_ratio", "d"),
    ("change_termi", "I"), ("landing_center_X", "d"), ("landing_center_Y", "d"),
    ("landing_center_Z", "d"), ("landing_box_length", "d"), ("landing_box__width", "d"),
    ("landing_box_height", "d"),
]


def serialize_changelane(data): return pack_fields(CHANGELANE_FIELDS, data)


def deserialize_changelane(data, offset=0): return unpack_fields(CHANGELANE_FIELDS, data, offset)


# ---------- 类型 6: PilotStatusNotify (0x000D/0x000D/0x8002) ----------
PILOT_STATUS_FIELDS = [
    ("Checksum", "I"), ("Counter", "H"), ("ACCStatus", "B"), ("ICCStatus", "B"),
    ("DNPStatus", "B"), ("TakeoverStatus", "B"), ("driving_time", "I"),
]


def serialize_pilot_status(data): return pack_fields(PILOT_STATUS_FIELDS, data)


def deserialize_pilot_status(data, offset=0): return unpack_fields(PILOT_STATUS_FIELDS, data, offset)


# ---------- 类型 7: PilotAlarmAndNoticeInfoNotify (0x000D/0x000D/0x8003) ----------
PILOT_ALARM_FIELDS = [
    ("Checksum", "I"), ("Counter", "H"), ("PilotAlarmReason", "I"), ("alarm_distance", "I"),
    ("alarm_stage", "I"), ("alarm_timestamp", "d"), ("PilotNotice", "I"),
    ("notice_distance", "I"), ("notice_timestamp", "d"),
]


def serialize_pilot_alarm(data): return pack_fields(PILOT_ALARM_FIELDS, data)


def deserialize_pilot_alarm(data, offset=0): return unpack_fields(PILOT_ALARM_FIELDS, data, offset)


# ---------- 类型 8: BroadcastInfoNotify (0x000D/0x000D/0x8004) ----------
BROADCAST_FIELDS = [
    ("Checksum", "I"), ("Counter", "H"), ("driver_attention", "B"), ("large_vehicles", "B"),
    ("dangerous_vehicle", "B"), ("pedestrians", "B"),
]


def serialize_broadcast(data): return pack_fields(BROADCAST_FIELDS, data)


def deserialize_broadcast(data, offset=0): return unpack_fields(BROADCAST_FIELDS, data, offset)


# ---------- 类型 9: HudRoadInfoNotify (0x010A/0x0001/0x8001) ----------
def serialize_hud_road(data):
    r = b""
    r += pack_fields([("Checksum", "I"), ("Counter", "H"), ("car_2_dest", "I"),
                      ("time_of_car_2_dest", "I"), ("Num_of_lanes", "B"), ("Current_road_level", "B")], data)
    r += serialize_array(data["Permissible_direction"], 1, lambda v: bytes([v]))
    r += serialize_array(data["Recommended_driving_directions_for_AJOTP"], 1, lambda v: bytes([v]))
    r += _pack("I", data["distance_2_intersection"])
    r += serialize_string(data["next_road_name"])
    r += pack_fields([("Current_max_speed_limit", "B"), ("Current_speed", "B"),
                      ("Distance_2_speed_limit_zone", "H"), ("length_of_speed_limit", "H"),
                      ("speed_limit", "B"), ("navigating_status", "B"), ("camera_ahead_status", "B"),
                      ("The_distance_2_camera", "H"),
                      ("vehicle_coordinates_Longitude", "d"), ("vehicle_coordinates_Latitude", "d"),
                      ("vehicle_speed", "B"), ("vehicle_altitude", "H"), ("Danger_signs", "B")], data)
    for key in ("POI_information", "reach_the_destination", "ETA_info_time", "ETA_info_remain_time"):
        r += serialize_string(data[key])
    r += _pack("H", data["RecommendedDrivingDirectionsId"])
    for key in ("lanesPermissibleDirectionId", "guideLine", "guidePoint"):
        r += serialize_string(data[key])
    r += pack_fields([("vehicleHeading", "d"), ("Navigating_ratio", "d")], data)
    return r


def deserialize_hud_road(data, offset=0):
    out = {}
    out, offset = unpack_fields([("Checksum", "I"), ("Counter", "H"), ("car_2_dest", "I"),
                                 ("time_of_car_2_dest", "I"), ("Num_of_lanes", "B"),
                                 ("Current_road_level", "B")], data, offset)
    out["Permissible_direction"], offset = deserialize_array(data, offset, 1, lambda d, o: (d[o], o + 1))
    out["Recommended_driving_directions_for_AJOTP"], offset = deserialize_array(data, offset, 1, lambda d, o: (d[o], o + 1))
    out["distance_2_intersection"], offset = _unpack("I", data, offset)
    out["next_road_name"], offset = deserialize_string(data, offset)
    f, offset = unpack_fields([("Current_max_speed_limit", "B"), ("Current_speed", "B"),
                               ("Distance_2_speed_limit_zone", "H"), ("length_of_speed_limit", "H"),
                               ("speed_limit", "B"), ("navigating_status", "B"),
                               ("camera_ahead_status", "B"), ("The_distance_2_camera", "H"),
                               ("vehicle_coordinates_Longitude", "d"),
                               ("vehicle_coordinates_Latitude", "d"), ("vehicle_speed", "B"),
                               ("vehicle_altitude", "H"), ("Danger_signs", "B")], data, offset)
    out.update(f)
    for key in ("POI_information", "reach_the_destination", "ETA_info_time", "ETA_info_remain_time"):
        out[key], offset = deserialize_string(data, offset)
    out["RecommendedDrivingDirectionsId"], offset = _unpack("H", data, offset)
    for key in ("lanesPermissibleDirectionId", "guideLine", "guidePoint"):
        out[key], offset = deserialize_string(data, offset)
    f, offset = unpack_fields([("vehicleHeading", "d"), ("Navigating_ratio", "d")], data, offset)
    out.update(f)
    return out, offset


# ---------- 类型 10: HudMappathInfo_EG (0x010A/0x0001/0x8002) ----------
def serialize_hud_mappath(data):
    r = pack_fields([("Checksum", "I"), ("Counter", "H"), ("is_on_the_path", "B"),
                     ("road_angle", "B"), ("road_slope", "f")], data)
    r += serialize_string(data["all_EHP_v2_info"])
    return r


def deserialize_hud_mappath(data, offset=0):
    out, offset = unpack_fields([("Checksum", "I"), ("Counter", "H"), ("is_on_the_path", "B"),
                                 ("road_angle", "B"), ("road_slope", "f")], data, offset)
    out["all_EHP_v2_info"], offset = deserialize_string(data, offset)
    return out, offset


# ---------- 类型 11: HudNavigationmap (0x010A/0x0001/0x8003) ----------
def serialize_hud_navmap(data):
    body = serialize_string(data["Navigation_map"])
    return _pack("I", len(body)) + body   # Navigation_map_len + string


def deserialize_hud_navmap(data, offset=0):
    nav_len, offset = _unpack("I", data, offset)
    out = {"Navigation_map_len": nav_len}
    out["Navigation_map"], offset = deserialize_string(data, offset)
    return out, offset


# ---------- 序列化/反序列化注册表 ----------
SERIALIZERS = {
    "VehiclePosition": serialize_vehicle, "RTK": serialize_rtk, "IMU": serialize_imu,
    "Obstacle": serialize_obstacle, "LaneLine": serialize_laneline,
    "ChangeLane": serialize_changelane, "PilotStatus": serialize_pilot_status,
    "PilotAlarm": serialize_pilot_alarm, "Broadcast": serialize_broadcast,
    "HudRoad": serialize_hud_road, "HudMappath": serialize_hud_mappath,
    "HudNavmap": serialize_hud_navmap,
}
DESERIALIZERS = {
    "VehiclePosition": deserialize_vehicle, "RTK": deserialize_rtk, "IMU": deserialize_imu,
    "Obstacle": deserialize_obstacle, "LaneLine": deserialize_laneline,
    "ChangeLane": deserialize_changelane, "PilotStatus": deserialize_pilot_status,
    "PilotAlarm": deserialize_pilot_alarm, "Broadcast": deserialize_broadcast,
    "HudRoad": deserialize_hud_road, "HudMappath": deserialize_hud_mappath,
    "HudNavmap": deserialize_hud_navmap,
}


def kind_of(service, event):
    for svc, _, ev, _, _, _, kind in HUD_EVENTS:
        if svc == service and ev == event:
            return kind
    return "Opaque"


def event_info(service, event):
    for svc, inst, ev, name, group, port, kind in HUD_EVENTS:
        if svc == service and ev == event:
            return {"instance": inst, "name": name, "group": group, "port": port, "kind": kind}
    return None


def summarize(kind, parsed):
    """把解析结果压缩成一行，便于客户端打印/测试断言"""
    if not isinstance(parsed, dict):
        return str(parsed)
    def f(k):
        return parsed.get(k)
    try:
        if kind == "VehiclePosition":
            return f"Counter={f('Counter')} Lon={f('Longitude'):.6f} Lat={f('Latitude'):.6f} lanes={len(parsed['target_lane_id'])}"
        if kind == "RTK":
            return f"Counter={f('Counter')} rtk_status={f('rtk_status')} sv_used={f('satellite_used')}"
        if kind == "IMU":
            return f"Counter={f('Counter')} temp={f('IMU_current_temperature'):.1f}"
        if kind == "Obstacle":
            return f"Counter={f('Counter')} obstacles={len(parsed['FieldLength_Object'])}"
        if kind == "LaneLine":
            return f"Counter={f('Counter')} lines={len(parsed['FieldLength_Line'])} roadm={len(parsed['FieldLength_RoadMarking'])} tla={len(parsed['FieldLength_TLA'])}"
        if kind == "ChangeLane":
            return f"Counter={f('Counter')} state={f('ChangeLaneState')}"
        if kind == "PilotStatus":
            return f"Counter={f('Counter')} ACC={f('ACCStatus')} ICC={f('ICCStatus')}"
        if kind == "PilotAlarm":
            return f"Counter={f('Counter')} reason={f('PilotAlarmReason')} stage={f('alarm_stage')}"
        if kind == "Broadcast":
            return f"Counter={f('Counter')} attention={f('driver_attention')}"
        if kind == "HudRoad":
            return f"Counter={f('Counter')} next_road={f('next_road_name')!r} speed_limit={f('speed_limit')}"
        if kind == "HudMappath":
            return f"Counter={f('Counter')} info={f('all_EHP_v2_info')!r}"
        if kind == "HudNavmap":
            return f"Navigation_map={str(f('Navigation_map'))[:24]!r}"
    except Exception:
        pass
    return f"({len(str(parsed))} fields)"


# ---------- 样例数据（供服务端发送 / 单元测试） ----------

def make_sample(kind: str, counter: int) -> bytes:
    """按类型构造样例载荷（已定义类型用序列化器；Opaque 用固定短载荷）"""
    if kind == "VehiclePosition":
        d = dict(Checksum=0, Counter=counter, Longitude=116.397, Latitude=39.908, altitude=50.0,
                 Heading=90.0, hd_lane_left_angle=1.0, Hd_lane_right_angle=-1.0, VehicleSpeed=60.0,
                 acceleration=0.5, x_speed=1.0, y_speed=0.0, z_speed=0.0, timestamp=0x12345678,
                 hd_link_id=100, hd_lane_id=2, hd_lane_type=1, on_lane_offset=0.1,
                 hd_lane_seq=3, hd_lane_num=4, hd_lane_left_lateral_offset=1.5,
                 hd_lane_right_lateral_offset=1.5, roll=0.0, pitch=0.0, HdStatus=1,
                 hdmap_version=1, fusion_status=2, pos_confidence=0.99, position_type=0,
                 break_light=0, indicator_light=1, Lights=1, Weather=0,
                 target_cruise_speed=80.0, target_lane_id=[1, 2, 3],
                 target_lane_id_segment=[10, 20], localization_output_offset=0)
        return SERIALIZERS[kind](d)
    if kind == "RTK":
        d = dict(Checksum=0, Counter=counter, rtk_status=1, utc_time_us=1000.0, sys_time_us=2000.0,
                 longitude=116.397, latitude=39.908, altitude=50.0, longitude_acc=0.01,
                 latitude_acc=0.01, altitude_acc=0.02, heading_move=90.0, heading_double_ant=90.1,
                 heading_move_acc=0.1, speed_2d=60.0, speed_acc=0.1, speed_n=1.0, speed_e=2.0,
                 speed_u=0.0, g_dop=1.1, h_dop=0.9, v_dop=1.2, satellite_num=20,
                 satellite_used=18, snr_max=45.0, snr_mix=30.0, snr_avr=38.5)
        return SERIALIZERS[kind](d)
    if kind == "IMU":
        d = dict(Checksum=0, Counter=counter, angular_velocity_x=0.01, angular_velocity_y=0.02,
                 angular_velocity_z=0.03, acc_speed_x=0.1, acc_speed_y=0.2, acc_speed_z=9.8,
                 IMU_status=1, IMU_current_temperature=35.5, sys_time_us=3000.0, is_calibrated=1)
        return SERIALIZERS[kind](d)
    if kind == "Obstacle":
        items = [dict(ObstacleType=1, confidence=0.9, Obstacle_Id_i=i + 1,
                      ObstacleDistance_X_i=10.0 + i, ObstacleDistance_Y_i=0.5,
                      ObstacleDistance_Z_i=0.0, Bounding_box_length_i=4.0,
                      Bounding_box_width_i=1.8, Bounding_box_height_i=1.5,
                      break_light=0, indicator_light=0, obj_speed=5.0, ObstacleState=0,
                      obstacle_timestamp=4000.0, obstacle_camera_timestamp=4001.0,
                      moving=1, obj_heading=90.0, Obj_direction=0.0,
                      ObstacleWarningBrakeState=0) for i in range(2)]
        return SERIALIZERS[kind](dict(Checksum=0, Counter=counter, target_flag=1,
                                      FieldLength_Object=items))
    if kind == "LaneLine":
        fll = [dict(LineID=i + 1, LineType=1, LineColor=0, LineWidth=0.1, Line_confidence=0.95,
                    CurvatureEquation_c0=0.0, CurvatureEquation_c1=0.1, CurvatureEquation_c2=0.01,
                    CurvatureEquation_c3=0.0, Line_Startpoint_x=0.0, Line_Startpoint_y=0.0,
                    Line_Startpoint_z=0.0, Line_Endpoint_x=10.0, Line_Endpoint_y=1.0,
                    Line_Endpoint_z=0.0, sys_time_us=5000.0) for i in range(3)]
        flrm = [dict(RoadMarkingID_i=i + 1, RoadMarkingType_i=2, RoadMarkingType_confidence_i=0.8,
                     RoadMarking_length_i=3.0, RoadMarking_width_i=0.3, RoadMarking_height_i=0.1,
                     RoadMarking_Distance_X_i=5.0, RoadMarking_Distance_Y_i=1.0,
                     RoadMarking_Distance_Z_i=0.0, RoadMarkingPosition_confidence=0.9) for i in range(2)]
        fltla = [dict(TLAID_i=1, TLA_Distance_X=50.0, TLA_Distance_Y=0.0, TLA_Distance_Z=0.0,
                      TLAPosition_confidence=0.85, LeftTLA_Color=3, LeftTLA_Type=1,
                      StraightTLA_Color=3, StraightTLA_Type=1, RightTLA_Color=3, RightTLA_Type=1)]
        return SERIALIZERS[kind](dict(Checksum=0, Counter=counter, FieldLength_Line=fll,
                                      FieldLength_RoadMarking=flrm, FieldLength_TLA=fltla))
    if kind == "ChangeLane":
        d = dict(Checksum=0, Counter=counter, ChangeLaneState=1, ChangeLaneDirection=2,
                 is_change_safety=1, ChangeLane_timestamp=0x11223344, change_ratio=0.5,
                 change_termi=0, landing_center_X=10.0, landing_center_Y=0.0, landing_center_Z=0.0,
                 landing_box_length=4.0, landing_box__width=1.8, landing_box_height=1.5)
        return SERIALIZERS[kind](d)
    if kind == "PilotStatus":
        return SERIALIZERS[kind](dict(Checksum=0, Counter=counter, ACCStatus=1, ICCStatus=1,
                                      DNPStatus=0, TakeoverStatus=0, driving_time=3600))
    if kind == "PilotAlarm":
        d = dict(Checksum=0, Counter=counter, PilotAlarmReason=1, alarm_distance=30,
                 alarm_stage=2, alarm_timestamp=6000.0, PilotNotice=2, notice_distance=50,
                 notice_timestamp=6001.0)
        return SERIALIZERS[kind](d)
    if kind == "Broadcast":
        return SERIALIZERS[kind](dict(Checksum=0, Counter=counter, driver_attention=0,
                                      large_vehicles=1, dangerous_vehicle=0, pedestrians=1))
    if kind == "HudRoad":
        d = dict(Checksum=0, Counter=counter, car_2_dest=5000, time_of_car_2_dest=300,
                 Num_of_lanes=4, Current_road_level=2, Permissible_direction=[1, 2, 3],
                 Recommended_driving_directions_for_AJOTP=[1, 2], distance_2_intersection=100,
                 next_road_name="G6 Expressway", Current_max_speed_limit=120, Current_speed=60,
                 Distance_2_speed_limit_zone=200, length_of_speed_limit=1000, speed_limit=80,
                 navigating_status=1, camera_ahead_status=0, The_distance_2_camera=50,
                 vehicle_coordinates_Longitude=116.397, vehicle_coordinates_Latitude=39.908,
                 vehicle_speed=60, vehicle_altitude=50, Danger_signs=0,
                 POI_information="Toll Station", reach_the_destination="30min",
                 ETA_info_time="12:30", ETA_info_remain_time="00:30",
                 RecommendedDrivingDirectionsId=1, lanesPermissibleDirectionId="L1,L2",
                 guideLine="G6", guidePoint="S1", vehicleHeading=90.0, Navigating_ratio=0.6)
        return SERIALIZERS[kind](d)
    if kind == "HudMappath":
        return SERIALIZERS[kind](dict(Checksum=0, Counter=counter, is_on_the_path=1,
                                      road_angle=15, road_slope=0.03,
                                      all_EHP_v2_info="EHP:path-info-json"))
    if kind == "HudNavmap":
        return SERIALIZERS[kind](dict(Navigation_map_len=0,
                                      Navigation_map="navigation-map-image-base64"))
    return bytes([0x41, 0x52, 0x48, 0x55, 0x44, counter & 0xFF])
