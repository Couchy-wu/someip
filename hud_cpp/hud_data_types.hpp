// AR-HUD 23 服务数据类型 —— C++ 大端(网络序)编解码（"sp" 序列化层等价物）
// =====================================================================
// 对应 Python 端 hud/hud_data_types.py：字段顺序、字节序(大端)、字符串格式
// （长度4+BOM3+内容）、动态数组长度(字节数) 完全一致。
// 若你有项目自研的 sp 库，本模块的 serialize_xxx/deserialize_xxx 就是替换点：
//   客户端 on_message 里调用 deserialize_xxx(...)，换成 sp 的解析即可。
#pragma once

#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>

namespace hud {

// ---------------- 事件注册表 ----------------
enum class Kind : int {
    VehiclePosition, RTK, IMU, Obstacle, LaneLine, ChangeLane,
    PilotStatus, PilotAlarm, Broadcast, HudRoad, HudMappath, HudNavmap,
    Opaque
};

struct EventInfo {
    uint16_t service;
    uint16_t instance;
    uint16_t event;
    uint16_t group;
    uint16_t port;
    const char* name;
    Kind kind;
};

extern const EventInfo HUD_EVENTS[23];
extern const int HUD_EVENTS_COUNT;

// ---------------- 大端编解码基础 ----------------
void put_u16(std::vector<uint8_t>& b, uint16_t v);
void put_u32(std::vector<uint8_t>& b, uint32_t v);
void put_u64(std::vector<uint8_t>& b, uint64_t v);
void put_f32(std::vector<uint8_t>& b, float v);
void put_f64(std::vector<uint8_t>& b, double v);
void put_bytes(std::vector<uint8_t>& b, const uint8_t* p, size_t n);
void put_string(std::vector<uint8_t>& b, const std::string& s);   // 长度4 + BOM3 + 内容

// 读侧（顺序读取）
struct Reader {
    const uint8_t* p;
    size_t size;
    size_t off;
    Reader(const uint8_t* _p, size_t _size) : p(_p), size(_size), off(0) {}
    bool ok() const { return off <= size; }
    uint16_t u16();
    uint32_t u32();
    double f64();
    float f32();
    uint8_t u8();
    std::string str();                       // 长度4+BOM3+内容
    template <typename T>
    bool arr(size_t elem_size, std::vector<T>& out,
             bool (*read)(Reader&, T&));     // 长度(字节数)+元素
};

// ---------------- 12 种已定义类型结构体 ----------------
struct VehiclePositionInfoNotify {
    uint32_t Checksum; uint16_t Counter;
    double Longitude, Latitude, altitude, Heading, hd_lane_left_angle, Hd_lane_right_angle,
           VehicleSpeed, acceleration, x_speed, y_speed, z_speed, timestamp;
    uint32_t hd_link_id, hd_lane_id, hd_lane_type; double on_lane_offset;
    uint32_t hd_lane_seq, hd_lane_num;
    double hd_lane_left_lateral_offset, hd_lane_right_lateral_offset, roll, pitch;
    uint8_t HdStatus, hdmap_version, fusion_status; double pos_confidence;
    uint8_t position_type, break_light, indicator_light, Lights, Weather;
    float target_cruise_speed;
    std::vector<uint32_t> target_lane_id, target_lane_id_segment;
    uint8_t localization_output_offset;
};

struct RTKInfoNotify {
    uint32_t Checksum; uint16_t Counter; uint32_t rtk_status;
    double utc_time_us, sys_time_us, longitude, latitude, altitude, longitude_acc,
           latitude_acc, altitude_acc, heading_move, heading_double_ant, heading_move_acc,
           speed_2d, speed_acc, speed_n, speed_e, speed_u, g_dop, h_dop, v_dop;
    uint32_t satellite_num, satellite_used;
    double snr_max, snr_mix, snr_avr;
};

struct IMUInfoNotify {
    uint32_t Checksum; uint16_t Counter;
    double angular_velocity_x, angular_velocity_y, angular_velocity_z,
           acc_speed_x, acc_speed_y, acc_speed_z;
    uint8_t IMU_status; double IMU_current_temperature, sys_time_us; uint8_t is_calibrated;
};

struct ObstacleItem {   // 97 字节
    uint32_t ObstacleType; double confidence; uint32_t Obstacle_Id_i;
    double ObstacleDistance_X_i, ObstacleDistance_Y_i, ObstacleDistance_Z_i;
    float Bounding_box_length_i, Bounding_box_width_i, Bounding_box_height_i;
    uint8_t break_light, indicator_light; double obj_speed;
    uint8_t ObstacleState; double obstacle_timestamp, obstacle_camera_timestamp;
    uint8_t moving; double obj_heading, Obj_direction; uint8_t ObstacleWarningBrakeState;
};
struct ObstacleInfoNotify {
    uint32_t Checksum; uint16_t Counter; uint8_t target_flag;
    std::vector<ObstacleItem> FieldLength_Object;
};

struct LaneLineFLL {     // 66 字节
    int32_t LineID; uint8_t LineType, LineColor; float LineWidth; double Line_confidence;
    float CurvatureEquation_c0, CurvatureEquation_c1, CurvatureEquation_c2, CurvatureEquation_c3;
    float Line_Startpoint_x, Line_Startpoint_y, Line_Startpoint_z;
    float Line_Endpoint_x, Line_Endpoint_y, Line_Endpoint_z; double sys_time_us;
};
struct LaneLineFLRM {    // 57 字节
    uint32_t RoadMarkingID_i; uint8_t RoadMarkingType_i; double RoadMarkingType_confidence_i;
    float RoadMarking_length_i, RoadMarking_width_i, RoadMarking_height_i;
    double RoadMarking_Distance_X_i, RoadMarking_Distance_Y_i, RoadMarking_Distance_Z_i,
           RoadMarkingPosition_confidence;
};
struct LaneLineFLTLA {   // 42 字节
    uint32_t TLAID_i; double TLA_Distance_X, TLA_Distance_Y, TLA_Distance_Z, TLAPosition_confidence;
    uint8_t LeftTLA_Color, LeftTLA_Type, StraightTLA_Color, StraightTLA_Type,
            RightTLA_Color, RightTLA_Type;
};
struct LaneLineDataNotify {
    uint32_t Checksum; uint16_t Counter;
    std::vector<LaneLineFLL> FieldLength_Line;
    std::vector<LaneLineFLRM> FieldLength_RoadMarking;
    std::vector<LaneLineFLTLA> FieldLength_TLA;
};

struct ChangeLaneDataNotify {
    uint32_t Checksum; uint16_t Counter; uint32_t ChangeLaneState; uint8_t ChangeLaneDirection;
    uint8_t is_change_safety; uint32_t ChangeLane_timestamp; double change_ratio;
    uint32_t change_termi;
    double landing_center_X, landing_center_Y, landing_center_Z,
           landing_box_length, landing_box__width, landing_box_height;
};

struct PilotStatusNotify {
    uint32_t Checksum; uint16_t Counter;
    uint8_t ACCStatus, ICCStatus, DNPStatus, TakeoverStatus; uint32_t driving_time;
};

struct PilotAlarmAndNoticeInfoNotify {
    uint32_t Checksum; uint16_t Counter; uint32_t PilotAlarmReason, alarm_distance, alarm_stage;
    double alarm_timestamp; uint32_t PilotNotice, notice_distance; double notice_timestamp;
};

struct BroadcastInfoNotify {
    uint32_t Checksum; uint16_t Counter;
    uint8_t driver_attention, large_vehicles, dangerous_vehicle, pedestrians;
};

struct HudRoadInfoNotify {
    uint32_t Checksum; uint16_t Counter; uint32_t car_2_dest, time_of_car_2_dest;
    uint8_t Num_of_lanes, Current_road_level;
    std::vector<uint8_t> Permissible_direction;
    std::vector<uint8_t> Recommended_driving_directions_for_AJOTP;
    uint32_t distance_2_intersection; std::string next_road_name;
    uint8_t Current_max_speed_limit, Current_speed;
    uint16_t Distance_2_speed_limit_zone, length_of_speed_limit;
    uint8_t speed_limit, navigating_status, camera_ahead_status;
    uint16_t The_distance_2_camera;
    double vehicle_coordinates_Longitude, vehicle_coordinates_Latitude;
    uint8_t vehicle_speed; uint16_t vehicle_altitude; uint8_t Danger_signs;
    std::string POI_information, reach_the_destination, ETA_info_time, ETA_info_remain_time;
    uint16_t RecommendedDrivingDirectionsId;
    std::string lanesPermissibleDirectionId, guideLine, guidePoint;
    double vehicleHeading, Navigating_ratio;
};

struct HudMappathInfo_EG {
    uint32_t Checksum; uint16_t Counter; uint8_t is_on_the_path, road_angle; float road_slope;
    std::string all_EHP_v2_info;
};

struct HudNavigationmap {
    uint32_t Navigation_map_len; std::string Navigation_map;
};

// ---------------- 序列化 / 反序列化 ----------------
// 返回写入字节数 / 读取是否成功（失败返回 false 并置 off=size 防越界）
size_t serialize_vehicle(const VehiclePositionInfoNotify& v, std::vector<uint8_t>& out);
bool deserialize_vehicle(Reader& r, VehiclePositionInfoNotify& v);

size_t serialize_rtk(const RTKInfoNotify& v, std::vector<uint8_t>& out);
bool deserialize_rtk(Reader& r, RTKInfoNotify& v);

size_t serialize_imu(const IMUInfoNotify& v, std::vector<uint8_t>& out);
bool deserialize_imu(Reader& r, IMUInfoNotify& v);

size_t serialize_obstacle(const ObstacleInfoNotify& v, std::vector<uint8_t>& out);
bool deserialize_obstacle(Reader& r, ObstacleInfoNotify& v);

size_t serialize_laneline(const LaneLineDataNotify& v, std::vector<uint8_t>& out);
bool deserialize_laneline(Reader& r, LaneLineDataNotify& v);

size_t serialize_changelane(const ChangeLaneDataNotify& v, std::vector<uint8_t>& out);
bool deserialize_changelane(Reader& r, ChangeLaneDataNotify& v);

size_t serialize_pilot_status(const PilotStatusNotify& v, std::vector<uint8_t>& out);
bool deserialize_pilot_status(Reader& r, PilotStatusNotify& v);

size_t serialize_pilot_alarm(const PilotAlarmAndNoticeInfoNotify& v, std::vector<uint8_t>& out);
bool deserialize_pilot_alarm(Reader& r, PilotAlarmAndNoticeInfoNotify& v);

size_t serialize_broadcast(const BroadcastInfoNotify& v, std::vector<uint8_t>& out);
bool deserialize_broadcast(Reader& r, BroadcastInfoNotify& v);

size_t serialize_hud_road(const HudRoadInfoNotify& v, std::vector<uint8_t>& out);
bool deserialize_hud_road(Reader& r, HudRoadInfoNotify& v);

size_t serialize_hud_mappath(const HudMappathInfo_EG& v, std::vector<uint8_t>& out);
bool deserialize_hud_mappath(Reader& r, HudMappathInfo_EG& v);

size_t serialize_hud_navmap(const HudNavigationmap& v, std::vector<uint8_t>& out);
bool deserialize_hud_navmap(Reader& r, HudNavigationmap& v);

// 按 kind 分发解析；kind 未实现(或 Opaque)返回 false
bool deserialize_by_kind(Kind kind, const uint8_t* data, size_t len, std::string& summary);

// 自测：12 种类型 序列化→反序列化 往返 + 固定字节校验
bool self_test();

} // namespace hud
