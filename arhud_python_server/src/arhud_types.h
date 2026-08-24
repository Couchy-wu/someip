/*
 * arhud_types.h —— AR-HUD 数据结构定义与序列化（大端，与客户端 ArHudSomeipDataType.h 对齐）
 * 每个类型 = 固定字段结构体(#pragma pack(1)) + 序列化函数（输出不含 SOME/IP 头，自动补
 * Checksum = CRC32(payload[4:])，Counter 由调用方填写）。
 * 序列化函数签名统一：int arhud_serialize_xxx(const xxx_t* s, uint8_t* out, uint32_t* out_len);
 */
#ifndef ARHUD_TYPES_H
#define ARHUD_TYPES_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#pragma pack(push, 1)

/* ---------- RTKInfoNotify (0x000B/0x000B/0x8001) ---------- */
typedef struct {
    uint32_t Checksum; uint16_t Counter;
    uint32_t rtk_status;
    double utc_time_us, sys_time_us, longitude, latitude, altitude;
    double longitude_acc, latitude_acc, altitude_acc;
    double heading_move, heading_double_ant, heading_move_acc;
    double speed_2d, speed_acc, speed_n, speed_e, speed_u;
    double g_dop, h_dop, v_dop;
    uint32_t satellite_num, satellite_used;
    double snr_max, snr_mix, snr_avr;
} arhud_rtk_t;

/* ---------- IMUInfoNotify (0x000B/0x000B/0x8002) ---------- */
typedef struct {
    uint32_t Checksum; uint16_t Counter;
    double angular_velocity_x, angular_velocity_y, angular_velocity_z;
    double acc_speed_x, acc_speed_y, acc_speed_z;
    uint8_t IMU_status;
    double IMU_current_temperature, sys_time_us;
    uint8_t is_calibrated;
} arhud_imu_t;

/* ---------- ChangeLaneDataNotify (0x000D/0x000D/0x8001) ---------- */
typedef struct {
    uint32_t Checksum; uint16_t Counter;
    uint32_t ChangeLaneState;
    uint8_t ChangeLaneDirection, is_change_safety;
    uint32_t ChangeLane_timestamp;
    double change_ratio;
    uint32_t change_termi;
    double landing_center_X, landing_center_Y, landing_center_Z;
    double landing_box_length, landing_box__width, landing_box_height;
} arhud_changelane_t;

/* ---------- PilotStatusNotify (0x000D/0x000D/0x8002) ---------- */
typedef struct {
    uint32_t Checksum; uint16_t Counter;
    uint8_t ACCStatus, ICCStatus, DNPStatus, TakeoverStatus;
    uint32_t driving_time;
} arhud_pilot_status_t;

/* ---------- PilotAlarmAndNoticeInfoNotify (0x000D/0x000D/0x8003) ---------- */
typedef struct {
    uint32_t Checksum; uint16_t Counter;
    uint32_t PilotAlarmReason, alarm_distance, alarm_stage;
    double alarm_timestamp;
    uint32_t PilotNotice, notice_distance;
    double notice_timestamp;
} arhud_pilot_alarm_t;

/* ---------- BroadcastInfoNotify (0x000D/0x000D/0x8004) ---------- */
typedef struct {
    uint32_t Checksum; uint16_t Counter;
    uint8_t driver_attention, large_vehicles, dangerous_vehicle, pedestrians;
} arhud_broadcast_t;

/* ---------- HudMappathInfo_EG (0x010A/0x0001/0x8002) ---------- */
typedef struct {
    uint32_t Checksum; uint16_t Counter;
    uint8_t is_on_the_path, road_angle;
    float road_slope;
    /* 字符串：all_EHP_v2_info，长度<=512 */
    char all_EHP_v2_info[512];
} arhud_hud_mappath_t;

/* ---------- HudNavigationmap (0x010A/0x0001/0x8003) ---------- */
typedef struct {
    uint32_t Checksum; uint16_t Counter;
    /* 字符串：Navigation_map，长度<=2048 */
    char Navigation_map[2048];
} arhud_hud_navmap_t;

/* ---------- VehiclePositionInfoNotify (0x000A/0x000A/0x8001) ---------- */
typedef struct {
    uint32_t Checksum; uint16_t Counter;
    double Longitude, Latitude, altitude, Heading;
    double hd_lane_left_angle, Hd_lane_right_angle, VehicleSpeed, acceleration;
    double x_speed, y_speed, z_speed, timestamp;
    uint32_t hd_link_id, hd_lane_id, hd_lane_type;
    double on_lane_offset;
    uint32_t hd_lane_seq, hd_lane_num;
    double hd_lane_left_lateral_offset, hd_lane_right_lateral_offset, roll, pitch;
    uint8_t HdStatus, hdmap_version, fusion_status;
    double pos_confidence;
    uint8_t position_type, break_light, indicator_light, Lights, Weather;
    float target_cruise_speed;
} arhud_vehicle_t;

#pragma pack(pop)

/* ---------- 序列化函数（out 容量建议 4096；返回 0 成功） ---------- */
int arhud_serialize_rtk(const arhud_rtk_t* s, uint8_t* out, uint32_t* out_len);
int arhud_serialize_imu(const arhud_imu_t* s, uint8_t* out, uint32_t* out_len);
int arhud_serialize_changelane(const arhud_changelane_t* s, uint8_t* out, uint32_t* out_len);
int arhud_serialize_pilot_status(const arhud_pilot_status_t* s, uint8_t* out, uint32_t* out_len);
int arhud_serialize_pilot_alarm(const arhud_pilot_alarm_t* s, uint8_t* out, uint32_t* out_len);
int arhud_serialize_broadcast(const arhud_broadcast_t* s, uint8_t* out, uint32_t* out_len);
int arhud_serialize_hud_mappath(const arhud_hud_mappath_t* s, uint8_t* out, uint32_t* out_len);
int arhud_serialize_hud_navmap(const arhud_hud_navmap_t* s, uint8_t* out, uint32_t* out_len);
/* VehiclePosition：动态数组用指针+数量传入（target_lane_id / target_lane_id_segment） */
int arhud_serialize_vehicle(const arhud_vehicle_t* s,
                            const uint32_t* lanes, uint32_t n_lanes,
                            const uint32_t* segs, uint32_t n_segs,
                            uint8_t localization_output_offset,
                            uint8_t* out, uint32_t* out_len);

#ifdef __cplusplus
}
#endif

#endif /* ARHUD_TYPES_H */
