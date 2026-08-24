#include "arhud_types.h"

#include <cstring>
#include <zlib.h>

namespace {

/* 大端写入 */
void put_u8(uint8_t*& p, uint8_t v) { *p++ = v; }
void put_u16(uint8_t*& p, uint16_t v) { *p++ = v >> 8; *p++ = v & 0xff; }
void put_u32(uint8_t*& p, uint32_t v) {
    *p++ = v >> 24; *p++ = (v >> 16) & 0xff; *p++ = (v >> 8) & 0xff; *p++ = v & 0xff;
}
void put_f32(uint8_t*& p, float v) {
    uint32_t u; std::memcpy(&u, &v, 4); put_u32(p, u);
}
void put_f64(uint8_t*& p, double v) {
    uint64_t u; std::memcpy(&u, &v, 8);
    for (int i = 7; i >= 0; --i) *p++ = (u >> (i * 8)) & 0xff;
}

/* 字符串：len(4, 含BOM) + BOM(3) + 内容 */
uint32_t put_string(uint8_t*& p, const char* s, uint32_t cap) {
    size_t n = s ? strlen(s) : 0;
    if (n > cap) n = cap;
    put_u32(p, (uint32_t)(3 + n));  // BOM + 内容
    *p++ = 0xEF; *p++ = 0xBB; *p++ = 0xBF;
    if (n) { std::memcpy(p, s, n); p += n; }
    return (uint32_t)(4 + 3 + n);
}

/* 序列化结束后把前 4 字节替换为 CRC32(payload[4:]) */
void finalize_crc(uint8_t* out, uint32_t len) {
    if (len < 4) return;
    uint32_t crc = (uint32_t)crc32(0, out + 4, len - 4);
    out[0] = crc >> 24; out[1] = (crc >> 16) & 0xff;
    out[2] = (crc >> 8) & 0xff; out[3] = crc & 0xff;
}

struct Writer {
    uint8_t* p;
    uint8_t* begin;
    Writer(uint8_t* o) : p(o), begin(o) {}
    uint32_t len() const { return (uint32_t)(p - begin); }
};

}  // namespace

#define CRC_FINALIZE(out, len) finalize_crc((out), (len))

int arhud_serialize_rtk(const arhud_rtk_t* s, uint8_t* out, uint32_t* out_len) {
    if (!s || !out || !out_len || *out_len < 200) return -1;
    uint8_t* p = out;
    put_u32(p, 0); put_u16(p, s->Counter);           // Checksum 占位
    put_u32(p, s->rtk_status);
    put_f64(p, s->utc_time_us); put_f64(p, s->sys_time_us);
    put_f64(p, s->longitude); put_f64(p, s->latitude); put_f64(p, s->altitude);
    put_f64(p, s->longitude_acc); put_f64(p, s->latitude_acc); put_f64(p, s->altitude_acc);
    put_f64(p, s->heading_move); put_f64(p, s->heading_double_ant); put_f64(p, s->heading_move_acc);
    put_f64(p, s->speed_2d); put_f64(p, s->speed_acc);
    put_f64(p, s->speed_n); put_f64(p, s->speed_e); put_f64(p, s->speed_u);
    put_f64(p, s->g_dop); put_f64(p, s->h_dop); put_f64(p, s->v_dop);
    put_u32(p, s->satellite_num); put_u32(p, s->satellite_used);
    put_f64(p, s->snr_max); put_f64(p, s->snr_mix); put_f64(p, s->snr_avr);
    *out_len = (uint32_t)(p - out); CRC_FINALIZE(out, *out_len);
    return 0;
}

int arhud_serialize_imu(const arhud_imu_t* s, uint8_t* out, uint32_t* out_len) {
    if (!s || !out || !out_len || *out_len < 200) return -1;
    uint8_t* p = out;
    put_u32(p, 0); put_u16(p, s->Counter);
    put_f64(p, s->angular_velocity_x); put_f64(p, s->angular_velocity_y); put_f64(p, s->angular_velocity_z);
    put_f64(p, s->acc_speed_x); put_f64(p, s->acc_speed_y); put_f64(p, s->acc_speed_z);
    put_u8(p, s->IMU_status);
    put_f64(p, s->IMU_current_temperature); put_f64(p, s->sys_time_us);
    put_u8(p, s->is_calibrated);
    *out_len = (uint32_t)(p - out); CRC_FINALIZE(out, *out_len);
    return 0;
}

int arhud_serialize_changelane(const arhud_changelane_t* s, uint8_t* out, uint32_t* out_len) {
    if (!s || !out || !out_len || *out_len < 200) return -1;
    uint8_t* p = out;
    put_u32(p, 0); put_u16(p, s->Counter);
    put_u32(p, s->ChangeLaneState);
    put_u8(p, s->ChangeLaneDirection); put_u8(p, s->is_change_safety);
    put_u32(p, s->ChangeLane_timestamp);
    put_f64(p, s->change_ratio);
    put_u32(p, s->change_termi);
    put_f64(p, s->landing_center_X); put_f64(p, s->landing_center_Y); put_f64(p, s->landing_center_Z);
    put_f64(p, s->landing_box_length); put_f64(p, s->landing_box__width); put_f64(p, s->landing_box_height);
    *out_len = (uint32_t)(p - out); CRC_FINALIZE(out, *out_len);
    return 0;
}

int arhud_serialize_pilot_status(const arhud_pilot_status_t* s, uint8_t* out, uint32_t* out_len) {
    if (!s || !out || !out_len || *out_len < 64) return -1;
    uint8_t* p = out;
    put_u32(p, 0); put_u16(p, s->Counter);
    put_u8(p, s->ACCStatus); put_u8(p, s->ICCStatus); put_u8(p, s->DNPStatus); put_u8(p, s->TakeoverStatus);
    put_u32(p, s->driving_time);
    *out_len = (uint32_t)(p - out); CRC_FINALIZE(out, *out_len);
    return 0;
}

int arhud_serialize_pilot_alarm(const arhud_pilot_alarm_t* s, uint8_t* out, uint32_t* out_len) {
    if (!s || !out || !out_len || *out_len < 128) return -1;
    uint8_t* p = out;
    put_u32(p, 0); put_u16(p, s->Counter);
    put_u32(p, s->PilotAlarmReason); put_u32(p, s->alarm_distance); put_u32(p, s->alarm_stage);
    put_f64(p, s->alarm_timestamp);
    put_u32(p, s->PilotNotice); put_u32(p, s->notice_distance);
    put_f64(p, s->notice_timestamp);
    *out_len = (uint32_t)(p - out); CRC_FINALIZE(out, *out_len);
    return 0;
}

int arhud_serialize_broadcast(const arhud_broadcast_t* s, uint8_t* out, uint32_t* out_len) {
    if (!s || !out || !out_len || *out_len < 32) return -1;
    uint8_t* p = out;
    put_u32(p, 0); put_u16(p, s->Counter);
    put_u8(p, s->driver_attention); put_u8(p, s->large_vehicles);
    put_u8(p, s->dangerous_vehicle); put_u8(p, s->pedestrians);
    *out_len = (uint32_t)(p - out); CRC_FINALIZE(out, *out_len);
    return 0;
}

int arhud_serialize_hud_mappath(const arhud_hud_mappath_t* s, uint8_t* out, uint32_t* out_len) {
    if (!s || !out || !out_len || *out_len < 1024) return -1;
    uint8_t* p = out;
    put_u32(p, 0); put_u16(p, s->Counter);
    put_u8(p, s->is_on_the_path); put_u8(p, s->road_angle);
    put_f32(p, s->road_slope);
    put_string(p, s->all_EHP_v2_info, sizeof(s->all_EHP_v2_info) - 1);
    *out_len = (uint32_t)(p - out); CRC_FINALIZE(out, *out_len);
    return 0;
}

int arhud_serialize_hud_navmap(const arhud_hud_navmap_t* s, uint8_t* out, uint32_t* out_len) {
    if (!s || !out || !out_len || *out_len < 4096) return -1;
    /* HudNavigationmap: Navigation_map_len(4) + 字符串（字符串本身 4+3+内容） */
    uint8_t* p = out + 4;  // 预留长度字段
    uint32_t before = (uint32_t)(p - out);
    put_string(p, s->Navigation_map, sizeof(s->Navigation_map) - 1);
    uint32_t body_len = (uint32_t)(p - out) - before;
    out[0] = body_len >> 24; out[1] = (body_len >> 16) & 0xff;
    out[2] = (body_len >> 8) & 0xff; out[3] = body_len & 0xff;
    *out_len = (uint32_t)(p - out);
    /* 此类型无 Checksum/Counter 头，不补 CRC */
    return 0;
}

int arhud_serialize_vehicle(const arhud_vehicle_t* s,
                            const uint32_t* lanes, uint32_t n_lanes,
                            const uint32_t* segs, uint32_t n_segs,
                            uint8_t localization_output_offset,
                            uint8_t* out, uint32_t* out_len) {
    if (!s || !out || !out_len || *out_len < 4096) return -1;
    uint8_t* p = out;
    put_u32(p, 0); put_u16(p, s->Counter);
    put_f64(p, s->Longitude); put_f64(p, s->Latitude); put_f64(p, s->altitude); put_f64(p, s->Heading);
    put_f64(p, s->hd_lane_left_angle); put_f64(p, s->Hd_lane_right_angle);
    put_f64(p, s->VehicleSpeed); put_f64(p, s->acceleration);
    put_f64(p, s->x_speed); put_f64(p, s->y_speed); put_f64(p, s->z_speed); put_f64(p, s->timestamp);
    put_u32(p, s->hd_link_id); put_u32(p, s->hd_lane_id); put_u32(p, s->hd_lane_type);
    put_f64(p, s->on_lane_offset);
    put_u32(p, s->hd_lane_seq); put_u32(p, s->hd_lane_num);
    put_f64(p, s->hd_lane_left_lateral_offset); put_f64(p, s->hd_lane_right_lateral_offset);
    put_f64(p, s->roll); put_f64(p, s->pitch);
    put_u8(p, s->HdStatus); put_u8(p, s->hdmap_version); put_u8(p, s->fusion_status);
    put_f64(p, s->pos_confidence);
    put_u8(p, s->position_type); put_u8(p, s->break_light); put_u8(p, s->indicator_light);
    put_u8(p, s->Lights); put_u8(p, s->Weather);
    put_f32(p, s->target_cruise_speed);
    /* target_lane_id: 长度字段=字节数 */
    put_u32(p, n_lanes * 4);
    for (uint32_t i = 0; i < n_lanes; ++i) put_u32(p, lanes[i]);
    /* target_lane_id_segment */
    put_u32(p, n_segs * 4);
    for (uint32_t i = 0; i < n_segs; ++i) put_u32(p, segs[i]);
    put_u8(p, localization_output_offset);
    *out_len = (uint32_t)(p - out); CRC_FINALIZE(out, *out_len);
    return 0;
}
