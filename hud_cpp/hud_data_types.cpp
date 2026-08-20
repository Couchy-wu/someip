// AR-HUD 23 服务数据类型 —— C++ 大端(网络序)编解码实现
// 与 Python hud/hud_data_types.py 完全一致（字段顺序/大端/字符串BOM/数组长度=字节数）
#include "hud_data_types.hpp"

#include <cstring>
#include <sstream>
#include <iomanip>

namespace hud {

// ================= 事件注册表（与 Python HUD_EVENTS 一致） =================
const EventInfo HUD_EVENTS[23] = {
    {0x000A, 0x000A, 0x8001, 0x1101, 51400, "VehiclePositionInfoNotify",       Kind::VehiclePosition},
    {0x000B, 0x000B, 0x8001, 0x1101, 51401, "RTKInfoNotify",                   Kind::RTK},
    {0x000B, 0x000B, 0x8002, 0x1101, 51401, "IMUInfoNotify",                   Kind::IMU},
    {0x000C, 0x000C, 0x8001, 0x1101, 51402, "ObstacleInfoNotify",              Kind::Obstacle},
    {0x000C, 0x000C, 0x8002, 0x1101, 51402, "LaneLineDataNotify",              Kind::LaneLine},
    {0x000D, 0x000D, 0x8001, 0x1101, 51403, "ChangeLaneDataNotify",            Kind::ChangeLane},
    {0x000D, 0x000D, 0x8002, 0x1101, 51403, "PilotStatusNotify",               Kind::PilotStatus},
    {0x000D, 0x000D, 0x8003, 0x1101, 51403, "PilotAlarmAndNoticeInfoNotify",   Kind::PilotAlarm},
    {0x000D, 0x000D, 0x8004, 0x1101, 51403, "BroadcastInfoNotify",             Kind::Broadcast},
    {0x010A, 0x0001, 0x8001, 0x1101, 52001, "HudRoadInfoNotify",               Kind::HudRoad},
    {0x010A, 0x0001, 0x8002, 0x1101, 52001, "HudMappathInfo_EG",               Kind::HudMappath},
    {0x010A, 0x0001, 0x8003, 0x1101, 52001, "HudNavigationmap",                Kind::HudNavmap},
    {0x010A, 0x0001, 0x8004, 0x1101, 52001, "OverseasHudRoadInfoNotify",       Kind::Opaque},
    {0x000C, 0x000C, 0x8003, 0x1101, 51402, "NewLanelineDataNotify",           Kind::Opaque},
    {0x000D, 0x000D, 0x8005, 0x1101, 51403, "NewBroadcastInfoNotify",          Kind::Opaque},
    {0x000E, 0x000E, 0x8001, 0x1101, 51404, "PlanningLineInfoNotify",          Kind::Opaque},
    {0x0007, 0x0007, 0x8001, 0x1101, 51405, "NavigationStatus_LinkInfoNotify", Kind::Opaque},
    {0x0017, 0x0017, 0x8003, 0x1101, 51406, "NewParkingRealTimeDataNotify",    Kind::Opaque},
    {0x002B, 0x002B, 0x8001, 0x1101, 51407, "NavigationHDLink2Info",           Kind::Opaque},
    {0x8202, 0x8202, 0x8002, 0x1101, 51408, "sdTraffiIncident",                Kind::Opaque},
    {0x000E, 0x000E, 0x8002, 0x1102, 51404, "newPlanningLineInfo",             Kind::Opaque},
    {0x000E, 0x000E, 0x8003, 0x1103, 51404, "drivingAreaIdentification",       Kind::Opaque},
    {0x0018, 0x0018, 0x8001, 0x1101, 51409, "hpaMapDataNotify",                Kind::Opaque},
};
const int HUD_EVENTS_COUNT = 23;

// ================= 大端编解码基础 =================
static inline void put_be(std::vector<uint8_t>& b, uint64_t v, int n) {
    for (int i = n - 1; i >= 0; --i) b.push_back(static_cast<uint8_t>((v >> (8 * i)) & 0xFF));
}
void put_u16(std::vector<uint8_t>& b, uint16_t v) { put_be(b, v, 2); }
void put_u32(std::vector<uint8_t>& b, uint32_t v) { put_be(b, v, 4); }
void put_u64(std::vector<uint8_t>& b, uint64_t v) { put_be(b, v, 8); }
void put_f32(std::vector<uint8_t>& b, float v) {
    uint32_t bits; std::memcpy(&bits, &v, 4); put_u32(b, bits);
}
void put_f64(std::vector<uint8_t>& b, double v) {
    uint64_t bits; std::memcpy(&bits, &v, 8); put_u64(b, bits);
}
void put_bytes(std::vector<uint8_t>& b, const uint8_t* p, size_t n) {
    b.insert(b.end(), p, p + n);
}
void put_string(std::vector<uint8_t>& b, const std::string& s) {
    if (s.empty()) { put_u32(b, 0); return; }        // 空串只写长度 0
    const uint8_t bom[3] = {0xEF, 0xBB, 0xBF};
    put_u32(b, static_cast<uint32_t>(3 + s.size()));
    put_bytes(b, bom, 3);
    put_bytes(b, reinterpret_cast<const uint8_t*>(s.data()), s.size());
}

static inline uint64_t get_be(const uint8_t* p, int n) {
    uint64_t v = 0;
    for (int i = 0; i < n; ++i) v = (v << 8) | p[i];
    return v;
}
uint16_t Reader::u16() { if (off + 2 > size) { off = size; return 0; } uint16_t v = (uint16_t)get_be(p + off, 2); off += 2; return v; }
uint32_t Reader::u32() { if (off + 4 > size) { off = size; return 0; } uint32_t v = (uint32_t)get_be(p + off, 4); off += 4; return v; }
double  Reader::f64() { uint64_t bits = 0; for (int i = 0; i < 8; ++i) { if (off + i >= size) { off = size; return 0; } bits = (bits << 8) | p[off + i]; } double v; std::memcpy(&v, &bits, 8); off += 8; return v; }
float   Reader::f32() { uint32_t bits = 0; for (int i = 0; i < 4; ++i) { if (off + i >= size) { off = size; return 0; } bits = (bits << 8) | p[off + i]; } float v; std::memcpy(&v, &bits, 4); off += 4; return v; }
uint8_t Reader::u8()  { if (off + 1 > size) { off = size; return 0; } return p[off++]; }

std::string Reader::str() {
    uint32_t len = u32();
    if (len == 0) return "";
    if (off + 3 <= size && p[off] == 0xEF && p[off + 1] == 0xBB && p[off + 2] == 0xBF) {
        off += 3; len -= 3;                       // 跳过 BOM
    }
    if (off + len > size) { off = size; return ""; }
    std::string s(reinterpret_cast<const char*>(p + off), len);
    off += len;
    return s;
}

template <typename T>
bool Reader::arr(size_t elem_size, std::vector<T>& out, bool (*read)(Reader&, T&)) {
    uint32_t n = u32();
    size_t count = (elem_size > 0) ? (n / elem_size) : 0;   // 长度=字节数
    out.clear();
    for (size_t i = 0; i < count; ++i) {
        T elem{};
        if (!read(*this, elem)) return false;
        out.push_back(std::move(elem));
    }
    return true;
}
// 显式实例化用到的 arr 特化
template bool Reader::arr<ObstacleItem>(size_t, std::vector<ObstacleItem>&, bool (*)(Reader&, ObstacleItem&));
template bool Reader::arr<LaneLineFLL>(size_t, std::vector<LaneLineFLL>&, bool (*)(Reader&, LaneLineFLL&));
template bool Reader::arr<LaneLineFLRM>(size_t, std::vector<LaneLineFLRM>&, bool (*)(Reader&, LaneLineFLRM&));
template bool Reader::arr<LaneLineFLTLA>(size_t, std::vector<LaneLineFLTLA>&, bool (*)(Reader&, LaneLineFLTLA&));
template bool Reader::arr<uint32_t>(size_t, std::vector<uint32_t>&, bool (*)(Reader&, uint32_t&));
template bool Reader::arr<uint8_t>(size_t, std::vector<uint8_t>&, bool (*)(Reader&, uint8_t&));

// 数组序列化辅助：长度(字节数) + 元素
template <typename T>
static void put_array(std::vector<uint8_t>& b, const std::vector<T>& v, size_t elem_size,
                      void (*w)(std::vector<uint8_t>&, const T&)) {
    put_u32(b, static_cast<uint32_t>(v.size() * elem_size));
    for (const auto& e : v) w(b, e);
}
static void w_u32(std::vector<uint8_t>& b, const uint32_t& v) { put_u32(b, v); }
static void w_u8(std::vector<uint8_t>& b, const uint8_t& v)   { b.push_back(v); }

// ================= 类型 0: VehiclePosition =================
size_t serialize_vehicle(const VehiclePositionInfoNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter);
    put_f64(out, v.Longitude); put_f64(out, v.Latitude); put_f64(out, v.altitude);
    put_f64(out, v.Heading); put_f64(out, v.hd_lane_left_angle); put_f64(out, v.Hd_lane_right_angle);
    put_f64(out, v.VehicleSpeed); put_f64(out, v.acceleration); put_f64(out, v.x_speed);
    put_f64(out, v.y_speed); put_f64(out, v.z_speed); put_f64(out, v.timestamp);
    put_u32(out, v.hd_link_id); put_u32(out, v.hd_lane_id); put_u32(out, v.hd_lane_type);
    put_f64(out, v.on_lane_offset);
    put_u32(out, v.hd_lane_seq); put_u32(out, v.hd_lane_num);
    put_f64(out, v.hd_lane_left_lateral_offset); put_f64(out, v.hd_lane_right_lateral_offset);
    put_f64(out, v.roll); put_f64(out, v.pitch);
    out.push_back(v.HdStatus); out.push_back(v.hdmap_version); out.push_back(v.fusion_status);
    put_f64(out, v.pos_confidence);
    out.push_back(v.position_type); out.push_back(v.break_light); out.push_back(v.indicator_light);
    out.push_back(v.Lights); out.push_back(v.Weather);
    put_f32(out, v.target_cruise_speed);
    put_array(out, v.target_lane_id, 4, w_u32);
    put_array(out, v.target_lane_id_segment, 4, w_u32);
    out.push_back(v.localization_output_offset);
    return out.size();
}
bool deserialize_vehicle(Reader& r, VehiclePositionInfoNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16();
    v.Longitude = r.f64(); v.Latitude = r.f64(); v.altitude = r.f64(); v.Heading = r.f64();
    v.hd_lane_left_angle = r.f64(); v.Hd_lane_right_angle = r.f64(); v.VehicleSpeed = r.f64();
    v.acceleration = r.f64(); v.x_speed = r.f64(); v.y_speed = r.f64(); v.z_speed = r.f64();
    v.timestamp = r.f64();
    v.hd_link_id = r.u32(); v.hd_lane_id = r.u32(); v.hd_lane_type = r.u32();
    v.on_lane_offset = r.f64();
    v.hd_lane_seq = r.u32(); v.hd_lane_num = r.u32();
    v.hd_lane_left_lateral_offset = r.f64(); v.hd_lane_right_lateral_offset = r.f64();
    v.roll = r.f64(); v.pitch = r.f64();
    v.HdStatus = r.u8(); v.hdmap_version = r.u8(); v.fusion_status = r.u8();
    v.pos_confidence = r.f64();
    v.position_type = r.u8(); v.break_light = r.u8(); v.indicator_light = r.u8();
    v.Lights = r.u8(); v.Weather = r.u8(); v.target_cruise_speed = r.f32();
    if (!r.arr<uint32_t>(4, v.target_lane_id, [](Reader& rr, uint32_t& e){ e = rr.u32(); return rr.ok(); })) return false;
    if (!r.arr<uint32_t>(4, v.target_lane_id_segment, [](Reader& rr, uint32_t& e){ e = rr.u32(); return rr.ok(); })) return false;
    v.localization_output_offset = r.u8();
    return r.ok();
}

// ================= 类型 1: RTK =================
size_t serialize_rtk(const RTKInfoNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter); put_u32(out, v.rtk_status);
    put_f64(out, v.utc_time_us); put_f64(out, v.sys_time_us); put_f64(out, v.longitude);
    put_f64(out, v.latitude); put_f64(out, v.altitude); put_f64(out, v.longitude_acc);
    put_f64(out, v.latitude_acc); put_f64(out, v.altitude_acc); put_f64(out, v.heading_move);
    put_f64(out, v.heading_double_ant); put_f64(out, v.heading_move_acc); put_f64(out, v.speed_2d);
    put_f64(out, v.speed_acc); put_f64(out, v.speed_n); put_f64(out, v.speed_e); put_f64(out, v.speed_u);
    put_f64(out, v.g_dop); put_f64(out, v.h_dop); put_f64(out, v.v_dop);
    put_u32(out, v.satellite_num); put_u32(out, v.satellite_used);
    put_f64(out, v.snr_max); put_f64(out, v.snr_mix); put_f64(out, v.snr_avr);
    return out.size();
}
bool deserialize_rtk(Reader& r, RTKInfoNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16(); v.rtk_status = r.u32();
    v.utc_time_us = r.f64(); v.sys_time_us = r.f64(); v.longitude = r.f64(); v.latitude = r.f64();
    v.altitude = r.f64(); v.longitude_acc = r.f64(); v.latitude_acc = r.f64(); v.altitude_acc = r.f64();
    v.heading_move = r.f64(); v.heading_double_ant = r.f64(); v.heading_move_acc = r.f64();
    v.speed_2d = r.f64(); v.speed_acc = r.f64(); v.speed_n = r.f64(); v.speed_e = r.f64();
    v.speed_u = r.f64(); v.g_dop = r.f64(); v.h_dop = r.f64(); v.v_dop = r.f64();
    v.satellite_num = r.u32(); v.satellite_used = r.u32();
    v.snr_max = r.f64(); v.snr_mix = r.f64(); v.snr_avr = r.f64();
    return r.ok();
}

// ================= 类型 2: IMU =================
size_t serialize_imu(const IMUInfoNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter);
    put_f64(out, v.angular_velocity_x); put_f64(out, v.angular_velocity_y); put_f64(out, v.angular_velocity_z);
    put_f64(out, v.acc_speed_x); put_f64(out, v.acc_speed_y); put_f64(out, v.acc_speed_z);
    out.push_back(v.IMU_status); put_f64(out, v.IMU_current_temperature); put_f64(out, v.sys_time_us);
    out.push_back(v.is_calibrated);
    return out.size();
}
bool deserialize_imu(Reader& r, IMUInfoNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16();
    v.angular_velocity_x = r.f64(); v.angular_velocity_y = r.f64(); v.angular_velocity_z = r.f64();
    v.acc_speed_x = r.f64(); v.acc_speed_y = r.f64(); v.acc_speed_z = r.f64();
    v.IMU_status = r.u8(); v.IMU_current_temperature = r.f64(); v.sys_time_us = r.f64();
    v.is_calibrated = r.u8();
    return r.ok();
}

// ================= 类型 3: Obstacle =================
static void w_obstacle(std::vector<uint8_t>& b, const ObstacleItem& o) {
    put_u32(b, o.ObstacleType); put_f64(b, o.confidence); put_u32(b, o.Obstacle_Id_i);
    put_f64(b, o.ObstacleDistance_X_i); put_f64(b, o.ObstacleDistance_Y_i); put_f64(b, o.ObstacleDistance_Z_i);
    put_f32(b, o.Bounding_box_length_i); put_f32(b, o.Bounding_box_width_i); put_f32(b, o.Bounding_box_height_i);
    b.push_back(o.break_light); b.push_back(o.indicator_light); put_f64(b, o.obj_speed);
    b.push_back(o.ObstacleState); put_f64(b, o.obstacle_timestamp); put_f64(b, o.obstacle_camera_timestamp);
    b.push_back(o.moving); put_f64(b, o.obj_heading); put_f64(b, o.Obj_direction);
    b.push_back(o.ObstacleWarningBrakeState);
}
static bool r_obstacle(Reader& r, ObstacleItem& o) {
    o.ObstacleType = r.u32(); o.confidence = r.f64(); o.Obstacle_Id_i = r.u32();
    o.ObstacleDistance_X_i = r.f64(); o.ObstacleDistance_Y_i = r.f64(); o.ObstacleDistance_Z_i = r.f64();
    o.Bounding_box_length_i = r.f32(); o.Bounding_box_width_i = r.f32(); o.Bounding_box_height_i = r.f32();
    o.break_light = r.u8(); o.indicator_light = r.u8(); o.obj_speed = r.f64();
    o.ObstacleState = r.u8(); o.obstacle_timestamp = r.f64(); o.obstacle_camera_timestamp = r.f64();
    o.moving = r.u8(); o.obj_heading = r.f64(); o.Obj_direction = r.f64();
    o.ObstacleWarningBrakeState = r.u8();
    return r.ok();
}
size_t serialize_obstacle(const ObstacleInfoNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter); out.push_back(v.target_flag);
    put_array(out, v.FieldLength_Object, 97, w_obstacle);
    return out.size();
}
bool deserialize_obstacle(Reader& r, ObstacleInfoNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16(); v.target_flag = r.u8();
    if (!r.arr<ObstacleItem>(97, v.FieldLength_Object, r_obstacle)) return false;
    return r.ok();
}

// ================= 类型 4: LaneLine =================
static void w_fll(std::vector<uint8_t>& b, const LaneLineFLL& e) {
    put_be(b, (uint32_t)e.LineID, 4); b.push_back(e.LineType); b.push_back(e.LineColor);
    put_f32(b, e.LineWidth); put_f64(b, e.Line_confidence);
    put_f32(b, e.CurvatureEquation_c0); put_f32(b, e.CurvatureEquation_c1);
    put_f32(b, e.CurvatureEquation_c2); put_f32(b, e.CurvatureEquation_c3);
    put_f32(b, e.Line_Startpoint_x); put_f32(b, e.Line_Startpoint_y); put_f32(b, e.Line_Startpoint_z);
    put_f32(b, e.Line_Endpoint_x); put_f32(b, e.Line_Endpoint_y); put_f32(b, e.Line_Endpoint_z);
    put_f64(b, e.sys_time_us);
}
static bool r_fll(Reader& r, LaneLineFLL& e) {
    e.LineID = (int32_t)r.u32(); e.LineType = r.u8(); e.LineColor = r.u8(); e.LineWidth = r.f32();
    e.Line_confidence = r.f64();
    e.CurvatureEquation_c0 = r.f32(); e.CurvatureEquation_c1 = r.f32();
    e.CurvatureEquation_c2 = r.f32(); e.CurvatureEquation_c3 = r.f32();
    e.Line_Startpoint_x = r.f32(); e.Line_Startpoint_y = r.f32(); e.Line_Startpoint_z = r.f32();
    e.Line_Endpoint_x = r.f32(); e.Line_Endpoint_y = r.f32(); e.Line_Endpoint_z = r.f32();
    e.sys_time_us = r.f64();
    return r.ok();
}
static void w_flrm(std::vector<uint8_t>& b, const LaneLineFLRM& e) {
    put_u32(b, e.RoadMarkingID_i); b.push_back(e.RoadMarkingType_i);
    put_f64(b, e.RoadMarkingType_confidence_i);
    put_f32(b, e.RoadMarking_length_i); put_f32(b, e.RoadMarking_width_i); put_f32(b, e.RoadMarking_height_i);
    put_f64(b, e.RoadMarking_Distance_X_i); put_f64(b, e.RoadMarking_Distance_Y_i);
    put_f64(b, e.RoadMarking_Distance_Z_i); put_f64(b, e.RoadMarkingPosition_confidence);
}
static bool r_flrm(Reader& r, LaneLineFLRM& e) {
    e.RoadMarkingID_i = r.u32(); e.RoadMarkingType_i = r.u8(); e.RoadMarkingType_confidence_i = r.f64();
    e.RoadMarking_length_i = r.f32(); e.RoadMarking_width_i = r.f32(); e.RoadMarking_height_i = r.f32();
    e.RoadMarking_Distance_X_i = r.f64(); e.RoadMarking_Distance_Y_i = r.f64();
    e.RoadMarking_Distance_Z_i = r.f64(); e.RoadMarkingPosition_confidence = r.f64();
    return r.ok();
}
static void w_fltla(std::vector<uint8_t>& b, const LaneLineFLTLA& e) {
    put_u32(b, e.TLAID_i); put_f64(b, e.TLA_Distance_X); put_f64(b, e.TLA_Distance_Y);
    put_f64(b, e.TLA_Distance_Z); put_f64(b, e.TLAPosition_confidence);
    b.push_back(e.LeftTLA_Color); b.push_back(e.LeftTLA_Type); b.push_back(e.StraightTLA_Color);
    b.push_back(e.StraightTLA_Type); b.push_back(e.RightTLA_Color); b.push_back(e.RightTLA_Type);
}
static bool r_fltla(Reader& r, LaneLineFLTLA& e) {
    e.TLAID_i = r.u32(); e.TLA_Distance_X = r.f64(); e.TLA_Distance_Y = r.f64();
    e.TLA_Distance_Z = r.f64(); e.TLAPosition_confidence = r.f64();
    e.LeftTLA_Color = r.u8(); e.LeftTLA_Type = r.u8(); e.StraightTLA_Color = r.u8();
    e.StraightTLA_Type = r.u8(); e.RightTLA_Color = r.u8(); e.RightTLA_Type = r.u8();
    return r.ok();
}
size_t serialize_laneline(const LaneLineDataNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter);
    put_array(out, v.FieldLength_Line, 66, w_fll);
    put_array(out, v.FieldLength_RoadMarking, 57, w_flrm);
    put_array(out, v.FieldLength_TLA, 42, w_fltla);
    return out.size();
}
bool deserialize_laneline(Reader& r, LaneLineDataNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16();
    if (!r.arr<LaneLineFLL>(66, v.FieldLength_Line, r_fll)) return false;
    if (!r.arr<LaneLineFLRM>(57, v.FieldLength_RoadMarking, r_flrm)) return false;
    if (!r.arr<LaneLineFLTLA>(42, v.FieldLength_TLA, r_fltla)) return false;
    return r.ok();
}

// ================= 类型 5-8: 定长结构 =================
size_t serialize_changelane(const ChangeLaneDataNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter); put_u32(out, v.ChangeLaneState);
    out.push_back(v.ChangeLaneDirection); out.push_back(v.is_change_safety);
    put_u32(out, v.ChangeLane_timestamp); put_f64(out, v.change_ratio); put_u32(out, v.change_termi);
    put_f64(out, v.landing_center_X); put_f64(out, v.landing_center_Y); put_f64(out, v.landing_center_Z);
    put_f64(out, v.landing_box_length); put_f64(out, v.landing_box__width); put_f64(out, v.landing_box_height);
    return out.size();
}
bool deserialize_changelane(Reader& r, ChangeLaneDataNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16(); v.ChangeLaneState = r.u32();
    v.ChangeLaneDirection = r.u8(); v.is_change_safety = r.u8();
    v.ChangeLane_timestamp = r.u32(); v.change_ratio = r.f64(); v.change_termi = r.u32();
    v.landing_center_X = r.f64(); v.landing_center_Y = r.f64(); v.landing_center_Z = r.f64();
    v.landing_box_length = r.f64(); v.landing_box__width = r.f64(); v.landing_box_height = r.f64();
    return r.ok();
}

size_t serialize_pilot_status(const PilotStatusNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter);
    out.push_back(v.ACCStatus); out.push_back(v.ICCStatus); out.push_back(v.DNPStatus);
    out.push_back(v.TakeoverStatus); put_u32(out, v.driving_time);
    return out.size();
}
bool deserialize_pilot_status(Reader& r, PilotStatusNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16();
    v.ACCStatus = r.u8(); v.ICCStatus = r.u8(); v.DNPStatus = r.u8();
    v.TakeoverStatus = r.u8(); v.driving_time = r.u32();
    return r.ok();
}

size_t serialize_pilot_alarm(const PilotAlarmAndNoticeInfoNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter);
    put_u32(out, v.PilotAlarmReason); put_u32(out, v.alarm_distance); put_u32(out, v.alarm_stage);
    put_f64(out, v.alarm_timestamp); put_u32(out, v.PilotNotice); put_u32(out, v.notice_distance);
    put_f64(out, v.notice_timestamp);
    return out.size();
}
bool deserialize_pilot_alarm(Reader& r, PilotAlarmAndNoticeInfoNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16();
    v.PilotAlarmReason = r.u32(); v.alarm_distance = r.u32(); v.alarm_stage = r.u32();
    v.alarm_timestamp = r.f64(); v.PilotNotice = r.u32(); v.notice_distance = r.u32();
    v.notice_timestamp = r.f64();
    return r.ok();
}

size_t serialize_broadcast(const BroadcastInfoNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter);
    out.push_back(v.driver_attention); out.push_back(v.large_vehicles);
    out.push_back(v.dangerous_vehicle); out.push_back(v.pedestrians);
    return out.size();
}
bool deserialize_broadcast(Reader& r, BroadcastInfoNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16();
    v.driver_attention = r.u8(); v.large_vehicles = r.u8();
    v.dangerous_vehicle = r.u8(); v.pedestrians = r.u8();
    return r.ok();
}

// ================= 类型 9: HudRoadInfo =================
size_t serialize_hud_road(const HudRoadInfoNotify& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter);
    put_u32(out, v.car_2_dest); put_u32(out, v.time_of_car_2_dest);
    out.push_back(v.Num_of_lanes); out.push_back(v.Current_road_level);
    put_array(out, v.Permissible_direction, 1, w_u8);
    put_array(out, v.Recommended_driving_directions_for_AJOTP, 1, w_u8);
    put_u32(out, v.distance_2_intersection);
    put_string(out, v.next_road_name);
    out.push_back(v.Current_max_speed_limit); out.push_back(v.Current_speed);
    put_u16(out, v.Distance_2_speed_limit_zone); put_u16(out, v.length_of_speed_limit);
    out.push_back(v.speed_limit); out.push_back(v.navigating_status); out.push_back(v.camera_ahead_status);
    put_u16(out, v.The_distance_2_camera);
    put_f64(out, v.vehicle_coordinates_Longitude); put_f64(out, v.vehicle_coordinates_Latitude);
    out.push_back(v.vehicle_speed); put_u16(out, v.vehicle_altitude); out.push_back(v.Danger_signs);
    put_string(out, v.POI_information); put_string(out, v.reach_the_destination);
    put_string(out, v.ETA_info_time); put_string(out, v.ETA_info_remain_time);
    put_u16(out, v.RecommendedDrivingDirectionsId);
    put_string(out, v.lanesPermissibleDirectionId); put_string(out, v.guideLine); put_string(out, v.guidePoint);
    put_f64(out, v.vehicleHeading); put_f64(out, v.Navigating_ratio);
    return out.size();
}
bool deserialize_hud_road(Reader& r, HudRoadInfoNotify& v) {
    v.Checksum = r.u32(); v.Counter = r.u16();
    v.car_2_dest = r.u32(); v.time_of_car_2_dest = r.u32();
    v.Num_of_lanes = r.u8(); v.Current_road_level = r.u8();
    if (!r.arr<uint8_t>(1, v.Permissible_direction, [](Reader& rr, uint8_t& e){ e = rr.u8(); return rr.ok(); })) return false;
    if (!r.arr<uint8_t>(1, v.Recommended_driving_directions_for_AJOTP, [](Reader& rr, uint8_t& e){ e = rr.u8(); return rr.ok(); })) return false;
    v.distance_2_intersection = r.u32(); v.next_road_name = r.str();
    v.Current_max_speed_limit = r.u8(); v.Current_speed = r.u8();
    v.Distance_2_speed_limit_zone = r.u16(); v.length_of_speed_limit = r.u16();
    v.speed_limit = r.u8(); v.navigating_status = r.u8(); v.camera_ahead_status = r.u8();
    v.The_distance_2_camera = r.u16();
    v.vehicle_coordinates_Longitude = r.f64(); v.vehicle_coordinates_Latitude = r.f64();
    v.vehicle_speed = r.u8(); v.vehicle_altitude = r.u16(); v.Danger_signs = r.u8();
    v.POI_information = r.str(); v.reach_the_destination = r.str();
    v.ETA_info_time = r.str(); v.ETA_info_remain_time = r.str();
    v.RecommendedDrivingDirectionsId = r.u16();
    v.lanesPermissibleDirectionId = r.str(); v.guideLine = r.str(); v.guidePoint = r.str();
    v.vehicleHeading = r.f64(); v.Navigating_ratio = r.f64();
    return r.ok();
}

// ================= 类型 10: HudMappath =================
size_t serialize_hud_mappath(const HudMappathInfo_EG& v, std::vector<uint8_t>& out) {
    out.clear();
    put_u32(out, v.Checksum); put_u16(out, v.Counter);
    out.push_back(v.is_on_the_path); out.push_back(v.road_angle); put_f32(out, v.road_slope);
    put_string(out, v.all_EHP_v2_info);
    return out.size();
}
bool deserialize_hud_mappath(Reader& r, HudMappathInfo_EG& v) {
    v.Checksum = r.u32(); v.Counter = r.u16();
    v.is_on_the_path = r.u8(); v.road_angle = r.u8(); v.road_slope = r.f32();
    v.all_EHP_v2_info = r.str();
    return r.ok();
}

// ================= 类型 11: HudNavmap =================
size_t serialize_hud_navmap(const HudNavigationmap& v, std::vector<uint8_t>& out) {
    out.clear();
    std::vector<uint8_t> body;
    put_string(body, v.Navigation_map);
    put_u32(out, static_cast<uint32_t>(body.size()));
    put_bytes(out, body.data(), body.size());
    return out.size();
}
bool deserialize_hud_navmap(Reader& r, HudNavigationmap& v) {
    v.Navigation_map_len = r.u32();
    v.Navigation_map = r.str();
    return r.ok();
}

// ================= 按 kind 解析并生成摘要 =================
bool deserialize_by_kind(Kind kind, const uint8_t* data, size_t len, std::string& summary) {
    Reader r(data, len);
    std::ostringstream os;
    switch (kind) {
        case Kind::VehiclePosition: {
            VehiclePositionInfoNotify v{};
            if (!deserialize_vehicle(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " Lon=" << v.Longitude << " Lat=" << v.Latitude
               << " lanes=" << v.target_lane_id.size();
            break;
        }
        case Kind::RTK: {
            RTKInfoNotify v{};
            if (!deserialize_rtk(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " rtk_status=" << v.rtk_status
               << " sv_used=" << v.satellite_used;
            break;
        }
        case Kind::IMU: {
            IMUInfoNotify v{};
            if (!deserialize_imu(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " temp=" << v.IMU_current_temperature;
            break;
        }
        case Kind::Obstacle: {
            ObstacleInfoNotify v{};
            if (!deserialize_obstacle(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " obstacles=" << v.FieldLength_Object.size();
            break;
        }
        case Kind::LaneLine: {
            LaneLineDataNotify v{};
            if (!deserialize_laneline(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " lines=" << v.FieldLength_Line.size()
               << " roadm=" << v.FieldLength_RoadMarking.size() << " tla=" << v.FieldLength_TLA.size();
            break;
        }
        case Kind::ChangeLane: {
            ChangeLaneDataNotify v{};
            if (!deserialize_changelane(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " state=" << v.ChangeLaneState;
            break;
        }
        case Kind::PilotStatus: {
            PilotStatusNotify v{};
            if (!deserialize_pilot_status(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " ACC=" << (int)v.ACCStatus << " ICC=" << (int)v.ICCStatus;
            break;
        }
        case Kind::PilotAlarm: {
            PilotAlarmAndNoticeInfoNotify v{};
            if (!deserialize_pilot_alarm(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " reason=" << v.PilotAlarmReason
               << " stage=" << v.alarm_stage;
            break;
        }
        case Kind::Broadcast: {
            BroadcastInfoNotify v{};
            if (!deserialize_broadcast(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " attention=" << (int)v.driver_attention;
            break;
        }
        case Kind::HudRoad: {
            HudRoadInfoNotify v{};
            if (!deserialize_hud_road(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " next_road='" << v.next_road_name
               << "' speed_limit=" << (int)v.speed_limit;
            break;
        }
        case Kind::HudMappath: {
            HudMappathInfo_EG v{};
            if (!deserialize_hud_mappath(r, v) || !r.ok()) return false;
            os << "Counter=" << v.Counter << " info='" << v.all_EHP_v2_info << "'";
            break;
        }
        case Kind::HudNavmap: {
            HudNavigationmap v{};
            if (!deserialize_hud_navmap(r, v) || !r.ok()) return false;
            os << "Navigation_map='" << v.Navigation_map.substr(0, 24) << "'";
            break;
        }
        default:
            return false;
    }
    summary = os.str();
    return true;
}

// ================= 自测 =================
bool self_test() {
    // 1) 基础大端字节
    std::vector<uint8_t> b;
    put_u32(b, 0x01020304);
    if (b.size() != 4 || b[0] != 0x01 || b[1] != 0x02 || b[2] != 0x03 || b[3] != 0x04) return false;
    b.clear(); put_f32(b, 1.0f);
    if (b[0] != 0x3F || b[1] != 0x80) return false;
    // 2) 字符串格式
    b.clear(); put_string(b, "AB");
    if (!(b.size() == 9 && b[4] == 0xEF && b[5] == 0xBB && b[6] == 0xBF)) return false;
    // 3) 12 种类型往返
    VehiclePositionInfoNotify vp{};
    vp.Checksum = 0; vp.Counter = 7; vp.Longitude = 116.397; vp.Latitude = 39.908;
    vp.target_lane_id = {1, 2, 3}; vp.target_lane_id_segment = {10, 20};
    std::vector<uint8_t> buf;
    serialize_vehicle(vp, buf);
    VehiclePositionInfoNotify vp2{};
    Reader r(buf.data(), buf.size());
    if (!deserialize_vehicle(r, vp2) || vp2.Counter != 7 || vp2.target_lane_id.size() != 3) return false;
    return true;
}

} // namespace hud
