# to_longjie_demo_20250625 项目 Python 复现详细指南

**注意**: 经核实，原始配置文件存在一些问题，使用时需要修正。详见文末"附录A:配置文件修正说明"章节。

## 一、项目概述

本项目是比亚迪车载AR-HUD的SOME/IP通信实现，包含C++服务端（PCAP回放）和客户端两大部分。

- **服务端** (`hud_pcap_huifang_server.cpp`): 从PCAP文件读取SOME/IP数据包并回放
- **客户端** (`hud_huifang_client.cpp`): 订阅23种不同的HUD数据服务

---

## 二、支持的23种服务/事件列表

| 序号 | Service ID | Instance ID | Event ID | Event Group | 类型名称 |
|-----|------------|-------------|----------|-------------|----------|
| 0 | 0x000A | 0x000A | 0x8001 | 0x1101 | VehiclePositionInfoNotify |
| 1 | 0x000B | 0x000B | 0x8001 | 0x1101 | RTKInfoNotify |
| 2 | 0x000B | 0x000B | 0x8002 | 0x1101 | IMUInfoNotify |
| 3 | 0x000C | 0x000C | 0x8001 | 0x1101 | ObstacleInfoNotify |
| 4 | 0x000C | 0x000C | 0x8002 | 0x1101 | LaneLineDataNotify |
| 5 | 0x000D | 0x000D | 0x8001 | 0x1101 | ChangeLaneDataNotify |
| 6 | 0x000D | 0x000D | 0x8002 | 0x1101 | PilotStatusNotify |
| 7 | 0x000D | 0x000D | 0x8003 | 0x1101 | PilotAlarmAndNoticeInfoNotify |
| 8 | 0x000D | 0x000D | 0x8004 | 0x1101 | BroadcastInfoNotify |
| 9 | 0x010A | 0x0001 | 0x8001 | 0x1101 | HudRoadInfoNotify |
| 10 | 0x010A | 0x0001 | 0x8002 | 0x1101 | HudMappathInfo_EG |
| 11 | 0x010A | 0x0001 | 0x8003 | 0x1101 | HudNavigationmap |
| 12 | 0x010A | 0x0001 | 0x8004 | 0x1101 | OverseasHudRoadInfoNotify |
| 13 | 0x000C | 0x000C | 0x8003 | 0x1101 | NewLanelineDataNotify |
| 14 | 0x000D | 0x000D | 0x8005 | 0x1101 | NewBroadcastInfoNotify |
| 15 | 0x000E | 0x000E | 0x8001 | 0x1101 | PlanningLineInfoNotify |
| 16 | 0x0007 | 0x0007 | 0x8001 | 0x1101 | NavigationStatus_LinkInfoNotify |
| 17 | 0x0017 | 0x0017 | 0x8003 | 0x1101 | NewParkingRealTimeDataNotify |
| 18 | 0x002B | 0x002B | 0x8001 | 0x1101 | NavigationHDLink2Info |
| 19 | 0x8202 | 0x8202 | 0x8002 | 0x1101 | sdTraffiIncident |
| 20 | 0x000E | 0x000E | 0x8002 | 0x1102 | newPlanningLineInfo |
| 21 | 0x000E | 0x000E | 0x8003 | 0x1103 | drivingAreaIdentification |
| 22 | 0x0018 | 0x0018 | 0x8001 | 0x1101 | hpaMapDataNotify |

---

## 三、网络配置

### 3.1 服务发现配置
- **多播地址**: 224.0.2.4
- **端口**: 30490
- **协议**: UDP
- **TTL**: 3

### 3.2 服务端口映射

| Service ID | 服务端口 |
|------------|----------|
| 0x000A | 51400 / 52001 |
| 0x000B | 51401 / 52002 |
| 0x000C | 51402 / 52003 |
| 0x000D | 51403 / 52005 |
| 0x000E | 51404 / 52006 |
| 0x010A | 52001 |
| 0x0007 | 51405 |
| 0x0017 | 51406 |
| 0x002B | 51407 |
| 0x8202 | 51408 |
| 0x0018 | 51409 |

### 3.3 应用配置
- **应用名称**: arhud01
- **应用ID**: 0x1443
- **网络名称**: arhud01

---

## 四、SOME/IP 协议格式

### 4.1 SOME/IP 头部 (16字节)

| 偏移 | 大小 | 字段名 | 类型 | 说明 |
|------|------|--------|------|------|
| 0 | 2 | service_id | uint16 | 服务ID |
| 2 | 2 | method_id | uint16 | 方法/事件ID |
| 4 | 4 | length | uint32 | 载荷长度 |
| 8 | 2 | client_id | uint16 | 客户端ID |
| 10 | 2 | session_id | uint16 | 会话ID |
| 12 | 1 | someip_version | uint8 | SOME/IP版本 (0x01) |
| 13 | 1 | interface_version | uint8 | 接口版本 (0x01) |
| 14 | 1 | message_type | uint8 | 消息类型 |
| 15 | 1 | return_code | uint8 | 返回码 |

### 4.2 消息类型 (message_type)
- `0x00`: Request (请求)
- `0x01`: Request No Return (无返回请求)
- `0x02`: Notification (通知/事件) **主要使用**
- `0x20`: Request Ack
- `0x21`: Request No Return Ack
- `0x22`: SOME/IP-TP (分片传输)
- `0x80`: Error Response (错误响应)

### 4.3 数据序列化规则
**重要**: 所有多字节数据使用大端序（Big Endian/网络字节序）

```python
import struct

# 序列化函数示例
def serialize_uint32(value):
    return struct.pack('>I', value)  # 大端序

def serialize_uint16(value):
    return struct.pack('>H', value)  # 大端序

def serialize_double(value):
    return struct.pack('>d', value)  # 大端序 8字节

def serialize_float(value):
    return struct.pack('>f', value)  # 大端序 4字节
```

---

## 五、完整数据类型定义 (23种)

### 5.1 数据类型公共头部

所有消息都以以下字段开头：
- `Checksum`: uint32 (4字节)
- `Counter`: uint16 (2字节)

---

### 5.2 类型0: VehiclePositionInfoNotify (0x000A, 0x000A, 0x8001)

**总大小**: 约160字节 + 动态数组

```c
struct st_VehiclePositionInfoNotify {
    uint32_t    Checksum;                           // +4  偏移0
    uint16_t    Counter;                            // +2  偏移4
    double      Longitude;                          // +8  偏移6
    double      Latitude;                           // +8  偏移14
    double      altitude;                           // +8  偏移22
    double      Heading;                            // +8  偏移30
    double      hd_lane_left_angle;                 // +8  偏移38
    double      Hd_lane_right_angle;                // +8  偏移46
    double      VehicleSpeed;                       // +8  偏移54
    double      acceleration;                       // +8  偏移62
    double      x_speed;                            // +8  偏移70
    double      y_speed;                            // +8  偏移78
    double      z_speed;                            // +8  偏移86
    double      timestamp;                          // +8  偏移94
    uint32_t    hd_link_id;                         // +4  偏移102
    uint32_t    hd_lane_id;                         // +4  偏移106
    uint32_t    hd_lane_type;                       // +4  偏移110
    double      on_lane_offset;                     // +8  偏移114
    uint32_t    hd_lane_seq;                        // +4  偏移122
    uint32_t    hd_lane_num;                        // +4  偏移126
    double      hd_lane_left_lateral_offset;        // +8  偏移130
    double      hd_lane_right_lateral_offset;       // +8  偏移138
    double      roll;                               // +8  偏移146
    double      pitch;                              // +8  偏移154
    uint8_t     HdStatus;                           // +1  偏移162
    uint8_t     hdmap_version;                      // +1  偏移163
    uint8_t     fusion_status;                      // +1  偏移164
    double      pos_confidence;                     // +8  偏移165
    uint8_t     position_type;                       // +1  偏移173
    uint8_t     break_light;                        // +1  偏移174
    uint8_t     indicator_light;                    // +1  偏移175
    uint8_t     Lights;                             // +1  偏移176
    uint8_t     Weather;                            // +1  偏移177
    float       target_cruise_speed;                 // +4  偏移178
    uint32_t    FieldLength_target_lane;             // +4  偏移182
    uint32_t*   target_lane_id;                      // 动态数组
    uint32_t    FieldLength_target_lane_id_segment; // +4
    uint32_t*   target_lane_id_segment;              // 动态数组
    uint8_t     localization_output_offset;         // +1
};
```

**序列化顺序** (Python等效):
```python
def serialize_VehiclePositionInfoNotify(data):
    result = b''
    result += struct.pack('>I', data['Checksum'])                                    # 4
    result += struct.pack('>H', data['Counter'])                                     # 2
    result += struct.pack('>d', data['Longitude'])                                   # 8
    result += struct.pack('>d', data['Latitude'])                                    # 8
    result += struct.pack('>d', data['altitude'])                                   # 8
    result += struct.pack('>d', data['Heading'])                                    # 8
    result += struct.pack('>d', data['hd_lane_left_angle'])                         # 8
    result += struct.pack('>d', data['Hd_lane_right_angle'])                        # 8
    result += struct.pack('>d', data['VehicleSpeed'])                               # 8
    result += struct.pack('>d', data['acceleration'])                              # 8
    result += struct.pack('>d', data['x_speed'])                                   # 8
    result += struct.pack('>d', data['y_speed'])                                   # 8
    result += struct.pack('>d', data['z_speed'])                                   # 8
    result += struct.pack('>d', data['timestamp'])                                  # 8
    result += struct.pack('>I', data['hd_link_id'])                                 # 4
    result += struct.pack('>I', data['hd_lane_id'])                                 # 4
    result += struct.pack('>I', data['hd_lane_type'])                                # 4
    result += struct.pack('>d', data['on_lane_offset'])                             # 8
    result += struct.pack('>I', data['hd_lane_seq'])                                # 4
    result += struct.pack('>I', data['hd_lane_num'])                                # 4
    result += struct.pack('>d', data['hd_lane_left_lateral_offset'])                # 8
    result += struct.pack('>d', data['hd_lane_right_lateral_offset'])               # 8
    result += struct.pack('>d', data['roll'])                                       # 8
    result += struct.pack('>d', data['pitch'])                                      # 8
    result += struct.pack('>B', data['HdStatus'])                                    # 1
    result += struct.pack('>B', data['hdmap_version'])                              # 1
    result += struct.pack('>B', data['fusion_status'])                               # 1
    result += struct.pack('>d', data['pos_confidence'])                             # 8
    result += struct.pack('>B', data['position_type'])                               # 1
    result += struct.pack('>B', data['break_light'])                                 # 1
    result += struct.pack('>B', data['indicator_light'])                             # 1
    result += struct.pack('>B', data['Lights'])                                      # 1
    result += struct.pack('>B', data['Weather'])                                    # 1
    result += struct.pack('>f', data['target_cruise_speed'])                        # 4
    result += struct.pack('>I', data['FieldLength_target_lane'])                     # 4
    
    # 动态数组 target_lane_id
    lane_count = data['FieldLength_target_lane'] // 4
    for i in range(lane_count):
        result += struct.pack('>I', data['target_lane_id'][i])
    
    result += struct.pack('>I', data['FieldLength_target_lane_id_segment'])
    lane_count2 = data['FieldLength_target_lane_id_segment'] // 4
    for i in range(lane_count2):
        result += struct.pack('>I', data['target_lane_id_segment'][i])
    
    result += struct.pack('>B', data['localization_output_offset'])
    return result
```

---

### 5.3 类型1: RTKInfoNotify (0x000B, 0x000B, 0x8001)

**总大小**: 136字节

```c
struct st_RTKInfoNotify {
    uint32_t    Checksum;              // +4
    uint16_t    Counter;               // +2
    uint32_t    rtk_status;            // +4
    float64     utc_time_us;           // +8
    float64     sys_time_us;           // +8
    float64     longitude;             // +8
    float64     latitude;              // +8
    float64     altitude;              // +8
    float64     longitude_acc;         // +8
    float64     latitude_acc;          // +8
    float64     altitude_acc;          // +8
    float64     heading_move;          // +8
    float64     heading_double_ant;    // +8
    float64     heading_move_acc;       // +8
    float64     speed_2d;              // +8
    float64     speed_acc;              // +8
    float64     speed_n;                // +8
    float64     speed_e;                // +8
    float64     speed_u;                // +8
    float64     g_dop;                 // +8
    float64     h_dop;                 // +8
    float64     v_dop;                 // +8
    uint32_t    satellite_num;          // +4
    uint32_t    satellite_used;         // +4
    float64     snr_max;               // +8
    float64     snr_mix;               // +8
    float64     snr_avr;                // +8
};
```

---

### 5.4 类型2: IMUInfoNotify (0x000B, 0x000B, 0x8002)

**总大小**: 70字节

```c
struct st_IMUInfoNotify {
    uint32_t    Checksum;                      // +4
    uint16_t    Counter;                       // +2
    double      angular_velocity_x;            // +8
    double      angular_velocity_y;            // +8
    double      angular_velocity_z;            // +8  
    double      acc_speed_x;                   // +8
    double      acc_speed_y;                   // +8
    double      acc_speed_z;                   // +8
    uint8_t     IMU_status;                    // +1
    double      IMU_current_temperature;       // +8
    double      sys_time_us;                   // +8
    bool        is_calibrated;                 // +1 (实际1字节)
};
```

---

### 5.5 类型3: ObstacleInfoNotify (0x000C, 0x000C, 0x8001)

**总大小**: 11字节 + 动态数组 (每个元素97字节)

```c
struct stObstacleInfoNotifyFLO {  // 单个障碍物 97字节
    uint32_t    ObstacleType;              // +4
    double      confidence;                 // +8
    uint32_t    Obstacle_Id_i;             // +4
    double      ObstacleDistance_X_i;      // +8
    double      ObstacleDistance_Y_i;      // +8
    double      ObstacleDistance_Z_i;      // +8
    float       Bounding_box_length_i;      // +4
    float       Bounding_box_width_i;      // +4
    float       Bounding_box_height_i;     // +4
    uint8_t     break_light;                // +1
    uint8_t     indicator_light;            // +1
    double      obj_speed;                 // +8
    uint8_t     ObstacleState;              // +1
    double      obstacle_timestamp;         // +8
    double      obstacle_camera_timestamp;  // +8
    bool        moving;                     // +1
    double      obj_heading;                // +8
    double      Obj_direction;              // +8
    uint8_t     ObstacleWarningBrakeState;  // +1
};  // = 97字节

struct st_ObstacleInfoNotify {
    uint32_t    Checksum;                   // +4
    uint16_t    Counter;                    // +2
    bool        target_flag;                // +1
    uint32_t    FieldLength_Object_len;     // +4
    stObstacleInfoNotifyFLO* FieldLength_Object;  // 动态数组
};
```

---

### 5.6 类型4: LanelineDataNotify (0x000C, 0x000C, 0x8002)

**固定部分**: 10字节

**动态数组1**: FieldLength_Line (每个元素66字节)
```c
struct stLanelineDataNotifyFLL {
    int32_t     LineID;                     // 4
    uint8_t     LineType;                   // 1
    uint8_t     LineColor;                  // 1
    float       LineWidth;                  // 4
    double      Line_confidence;             // 8
    float       CurvatureEquation_c0;        // 4
    float       CurvatureEquation_c1;        // 4
    float       CurvatureEquation_c2;        // 4
    float       CurvatureEquation_c3;        // 4
    float       Line_Startpoint_x;           // 4
    float       Line_Startpoint_y;           // 4
    float       Line_Startpoint_z;           // 4
    float       Line_Endpoint_x;             // 4
    float       Line_Endpoint_y;             // 4
    float       Line_Endpoint_z;             // 4
    double      sys_time_us;                 // 8
};  // = 66字节
```

**动态数组2**: FieldLength_RoadMarking (每个元素57字节)
```c
struct stLanelineDataNotifyFLRM {
    uint32_t    RoadMarkingID_i;            // 4
    uint8_t     RoadMarkingType_i;           // 1
    double      RoadMarkingType_confidence_i;// 8
    float       RoadMarking_length_i;        // 4
    float       RoadMarking_width_i;         // 4
    float       RoadMarking_height_i;        // 4
    double      RoadMarking_Distance_X_i;    // 8
    double      RoadMarking_Distance_Y_i;    // 8
    double      RoadMarking_Distance_Z_i;    // 8
    double      RoadMarkingPosition_confidence;//8
};  // = 57字节
```

**动态数组3**: FieldLength_TLA (每个元素42字节)
```c
struct stLanelineDataNotifyFLTLA {
    uint32_t    TLAID_i;                    // 4
    double      TLA_Distance_X;             // 8
    double      TLA_Distance_Y;             // 8
    double      TLA_Distance_Z;             // 8
    double      TLAPosition_confidence;     // 8
    uint8_t     LeftTLA_Color;              // 1
    uint8_t     LeftTLA_Type;               // 1
    uint8_t     StraightTLA_Color;          // 1
    uint8_t     StraightTLA_Type;           // 1
    uint8_t     RightTLA_Color;              // 1
    uint8_t     RightTLA_Type;               // 1
};  // = 42字节
```

---

### 5.7 类型5: ChangeLaneDataNotify (0x000D, 0x000D, 0x8001)

**总大小**: 56字节

```c
struct st_ChangeLaneDataNotify {
    uint32_t    Checksum;               // +4
    uint16_t    Counter;                // +2
    uint32_t    ChangeLaneState;        // +4
    uint8_t     ChangeLaneDirection;    // +1
    bool        is_change_safety;       // +1
    uint32_t    ChangeLane_timestamp;   // +4
    double      change_ratio;            // +8
    uint32_t    change_termi;           // +4
    double      landing_center_X;        // +8
    double      landing_center_Y;        // +8
    double      landing_center_Z;        // +8
    double      landing_box_length;      // +8
    double      landing_box__width;      // +8
    double      landing_box_height;      // +8
};
```

---

### 5.8 类型6: PilotStatusNotify (0x000D, 0x000D, 0x8002)

**总大小**: 14字节

```c
struct st_PilotStatusNotify {
    uint32_t    Checksum;          // +4
    uint16_t    Counter;           // +2
    uint8_t     ACCStatus;         // +1
    uint8_t     ICCStatus;         // +1
    uint8_t     DNPStatus;         // +1
    bool        TakeoverStatus;    // +1
    uint32_t    driving_time;      // +4
};
```

---

### 5.9 类型7: PilotAlarmAndNoticeInfoNotify (0x000D, 0x000D, 0x8003)

**总大小**: 40字节

```c
struct st_PilotAlarmAndNoticeInfoNotify {
    uint32_t    Checksum;              // +4
    uint16_t    Counter;               // +2
    uint32_t    PilotAlarmReason;      // +4
    uint32_t    alarm_distance;        // +4
    uint32_t    alarm_stage;           // +4
    double      alarm_timestamp;        // +8
    uint32_t    PilotNotice;           // +4
    uint32_t    notice_distance;       // +4
    double      notice_timestamp;       // +8
};
```

---

### 5.10 类型8: BroadcastInfoNotify (0x000D, 0x000D, 0x8004)

**总大小**: 11字节

```c
struct st_BroadcastInfoNotify {
    uint32_t    Checksum;            // +4
    uint16_t    Counter;             // +2
    bool        driver_attention;    // +1
    bool        large_vehicles;      // +1
    bool        dangerous_vehicle;    // +1
    bool        pedestrians;         // +1
};
```

---

### 5.11 类型9: HudRoadInfoNotify (0x010A, 0x0001, 0x8001)

**固定部分**: 约40字节 + 多个动态数组 + 多个字符串

```c
struct st_HudRoadInfoNotify {
    uint32_t    Checksum;                                   // +4
    uint16_t    Counter;                                    // +2
    uint32_t    car_2_dest;                                 // +4
    uint32_t    time_of_car_2_dest;                         // +4
    uint8_t     Num_of_lanes;                               // +1
    uint8_t     Current_road_level;                         // +1
    uint32_t    Permissible_direction_len;                  // +4
    uint8_t*    Permissible_direction;                       // 动态数组
    uint32_t    Recommended_driving_directions_for_AJOTP_len;// +4
    uint8_t*    Recommended_driving_directions_for_AJOTP;   // 动态数组
    uint32_t    distance_2_intersection;                     // +4
    string      next_road_name;                            // 字符串(见下文)
    uint8_t     Current_max_speed_limit;                    // +1
    uint8_t     Current_speed;                              // +1
    uint16_t    Distance_2_speed_limit_zone;               // +2
    uint16_t    length_of_speed_limit;                      // +2
    uint8_t     speed_limit;                               // +1
    uint8_t     navigating_status;                         // +1
    uint8_t     camera_ahead_status;                       // +1
    uint16_t    The_distance_2_camera;                     // +2
    float64     vehicle_coordinates_Longitude;              // +8
    float64     vehicle_coordinates_Latitude;               // +8
    uint8_t     vehicle_speed;                              // +1
    uint16_t    vehicle_altitude;                          // +2
    uint8_t     Danger_signs;                              // +1
    string      POI_information;                           // 字符串
    string      reach_the_destination;                     // 字符串
    string      ETA_info_time;                             // 字符串
    string      ETA_info_remain_time;                      // 字符串
    uint16_t    RecommendedDrivingDirectionsId;             // +2
    string      lanesPermissibleDirectionId;               // 字符串
    string      guideLine;                                 // 字符串
    string      guidePoint;                                // 字符串
    double      vehicleHeading;                            // +8
    double      Navigating_ratio;                          // +8
};
```

---

### 5.12 字符串序列化格式

字符串使用特殊格式：
```python
def serialize_string(s):
    """
    字符串序列化格式:
    1. 长度(4字节) - 包含BOM(3字节) + 内容的长度
    2. UTF-8 BOM (3字节): 0xEF 0xBB 0xBF
    3. 字符串内容
    """
    if not s:
        return struct.pack('>I', 0)  # 空字符串
    
    content = s.encode('utf-8')
    total_length = 3 + len(content)  # BOM(3) + 内容
    
    result = struct.pack('>I', total_length)  # 4字节长度
    result += b'\xEF\xBB\xBF'                  # 3字节BOM
    result += content                          # 内容
    
    return result
```

**字符串反序列化**:
```python
def deserialize_string(data, offset):
    length = struct.unpack('>I', data[offset:offset+4])[0]
    offset += 4
    
    if length == 0:
        return "", offset
    
    # 跳过BOM (3字节)
    if length >= 3 and data[offset:offset+3] == b'\xEF\xBB\xBF':
        offset += 3
        length -= 3
    
    content = data[offset:offset+length]
    offset += length
    return content.decode('utf-8'), offset
```

---

### 5.13 类型10: HudMappathInfo_EG (0x010A, 0x0001, 0x8002)

**总大小**: 11字节 + 字符串

```c
struct st_HudMappathInfo_EG {
    uint32_t    Checksum;           // +4
    uint16_t    Counter;            // +2
    uint8_t     is_on_the_path;     // +1
    uint8_t     road_angle;         // +1
    float32     road_slope;         // +4
    string      all_EHP_v2_info;    // 字符串
};
```

---

### 5.14 类型11: HudNavigationmap (0x010A, 0x0001, 0x8003)

**总大小**: 4字节 + 字符串

```c
struct st_HudNavigationmap {
    uint32_t    Navigation_map_len;  // +4
    string      Navigation_map;      // 字符串
};
```

---

### 5.15 类型12: OverseasHudRoadInfoNotify (0x010A, 0x0001, 0x8004)

与HudRoadInfoNotify类似，但增加了一些额外字段:
- `uint8_t mapProviders`
- `string carToDestDistance`
- `string distanceToIntersection`  
- `string timeToDest`
- `uint16_t recommendedDrivingDirectionsIdOverseas`
- 5个reserved动态数组

---

### 5.16 类型13-22: 其他类型

由于篇幅限制，其他类型的详细信息见下表：

| 类型 | Service ID | Event ID | 特点 |
|------|------------|----------|------|
| NewLanelineDataNotify | 0x000C | 0x8003 | 包含LinePoints动态数组 |
| NewBroadcastInfoNotify | 0x000D | 0x8005 | 包含5个double reserved |
| PlanningLineInfoNotify | 0x000E | 0x8001 | 包含PlanningLinePoints动态数组 |
| NavigationStatus_LinkInfoNotify | 0x0007 | 0x8001 | 包含LinkID动态数组 |
| NewParkingRealTimeDataNotify | 0x0017 | 0x8003 | 包含4个动态数组(Object/ParkingSlot/RealTimeTrackPoint/HistoryTrackPoint) |
| NavigationHDLink2Info | 0x002B | 0x8001 | 包含6个动态数组(LinkItemInfo/PntItemInfo等) |
| sdTraffiIncident | 0x8202 | 0x8002 | 包含TraffiIncident动态数组 |
| newPlanningLineInfo | 0x000E | 0x8002 | 包含5个reserved动态数组 |
| drivingAreaIdentification | 0x000E | 0x8003 | 包含drivingAreaIdentificationPoints和5个reserved数组 |
| hpaMapDataNotify | 0x0018 | 0x8001 | 包含6个动态数组(GlobalTrackPoint/Rampway/SpeedBumps等) |

---

## 附录: 配置文件修正说明

### 一、问题概述

原始配置文件 `to_longjie_demo_20250625/config/someip_arhud01.json` (客户端配置) 存在端口配置错误。

### 二、服务端实际发送逻辑

查看 `hud_pcap_huifang_server.cpp` 第396-405行：

```cpp
// 服务端发送通知的逻辑
if (current_packet.service_id == 0x010a)
{
    // Service 0x010A: instance=0x0001, 端口=52001
    SPServerSendNotify(&spi, current_packet.service_id, 0x0001, current_packet.method_id, ...);
}
else
{
    // 其他Services: instance=service_id, 端口=51400-51409
    SPServerSendNotify(&spi, current_packet.service_id, current_packet.service_id, ...);
}
```

### 三、端口映射修正表

| Service ID | Instance ID | 服务端发送端口 | 原始配置(错误) | 需改为 |
|------------|-------------|---------------|---------------|--------|
| 0x000A | 0x000A | **51400** | 52001 | 51400 |
| 0x000B | 0x000B | **51401** | 52002 | 51401 |
| 0x000C | 0x000C | **51402** | 52003 | 51402 |
| 0x000D | 0x000D | **51403** | 52005 | 51403 |
| **0x010A** | **0x0001** | **52001** | 52011 | **52001** (正确) |
| 0x000E | 0x000E | **51404** | 52006 | 51404 |
| 0x0007 | 0x0007 | **51405** | 52007 | 51405 |
| 0x0017 | 0x0017 | **51406** | 52008 | 51406 |
| 0x002B | 0x002B | **51407** | 52009 | 51407 |
| 0x8202 | 0x8202 | **51408** | 52010 | 51408 |
| 0x0018 | 0x0018 | **51409** | 52012 | 51409 |

### 四、关键要点

1. **Service 0x010A 是特殊的**：
   - 端口: **52001** (不是51400系列)
   - Instance ID: **0x0001** (不是0x010A)

2. **其他Services**:
   - 端口: **51400-51409**
   - Instance ID = Service ID

3. **服务端配置 (someip_arhud01_pcap_server.json) 是正确的**

### 五、修正后的客户端配置 JSON

```json
{
    "unicast": "192.168.195.11",
    "network": "arhud01",
    "routing": "arhud01",
    "service-discovery": {
        "multicast": "224.0.2.4",
        "port": 30490,
        "protocol": "udp"
    },
    "clients": [
        {"service": "0x000A", "instance": "0x000A", "unreliable": ["51400"], "events": [{"name": "VehiclePositionInfoNotify", "event": "0x8001"}], "event_group": "0x1101"}],
        {"service": "0x000B", "instance": "0x000B", "unreliable": ["51401"], "events": [{"name": "RTKInfoNotify", "event": "0x8001"}, {"name": "IMUInfoNotify", "event": "0x8002"}], "event_group": "0x1101"}],
        {"service": "0x000C", "instance": "0x000C", "unreliable": ["51402"], "events": [{"name": "ObstacleInfoNotify", "event": "0x8001"}, {"name": "LaneLineDataNotify", "event": "0x8002"}, {"name": "NewLaneLineDataNotify", "event": "0x8003"}], "event_group": "0x1101"}],
        {"service": "0x000D", "instance": "0x000D", "unreliable": ["51403"], "events": [{"name": "ChangeLaneDataNotify", "event": "0x8001"}, {"name": "PilotStatusNofity", "event": "0x8002"}, {"name": "PilotAlarmAndNoticeInfoNotify", "event": "0x8003"}, {"name": "BroadcastInfoNotify", "event": "0x8004"}, {"name": "NewBroadcastInfoNotify", "event": "0x8005"}], "event_group": "0x1101"}],
        {"service": "0x010A", "instance": "0x0001", "unreliable": ["52001"], "events": [{"name": "HudRoadInfo_EG", "event": "0x8001"}, {"name": "HudMappathInfo_EG", "event": "0x8002"}, {"name": "HudNavigationmap", "event": "0x8003"}, {"name": "OverseasHudRoadInfoNotify", "event": "0x8004"}], "event_group": "0x1101"}],
        {"service": "0x000E", "instance": "0x000E", "unreliable": ["51404"], "events": [{"name": "PlanningLineInfoNotify", "event": "0x8001"}, {"name": "newPlanningLineInfo", "event": "0x8002"}, {"name": "drivingAreaIdentification", "event": "0x8003"}]},
        {"service": "0x0007", "instance": "0x0007", "unreliable": ["51405"], "events": [{"name": "NavigationStatus_LinkInfoNotify", "event": "0x8001"}], "event_group": "0x1101"}],
        {"service": "0x0017", "instance": "0x0017", "unreliable": ["51406"], "events": [{"name": "NewParkingRealTimeDataNotify", "event": "0x8003"}], "event_group": "0x1101"}],
        {"service": "0x002B", "instance": "0x002B", "unreliable": ["51407"], "events": [{"name": "NavigationHDLink2Info", "event": "0x8001"}], "event_group": "0x1101"}],
        {"service": "0x8202", "instance": "0x8202", "unreliable": ["51408"], "events": [{"name": "sdTraffiIncident", "event": "0x8002"}], "event_group": "0x1101"}],
        {"service": "0x0018", "instance": "0x0018", "unreliable": ["51409"], "events": [{"name": "hpaMapDataNotify", "event": "0x8001"}], "event_group": "0x1101"}]
    ]
}
```

---

## 六、PCAP回放实现细节

### 6.1 PCAP数据包解析流程

服务端 (`hud_pcap_huifang_server.cpp`) 实现:

```python
def parse_pcap_packet(packet_data):
    """
    PCAP解析流程:
    1. 解析Ethernet头 (14字节, 或18字节带VLAN)
    2. 解析IP头 (可变, 最小20字节)
    3. 解析UDP/TCP头 (UDP固定8字节, TCP可变)
    4. 解析SOME/IP头 (16字节)
    5. 提取payload
    """
    pass
```

### 6.2 SOME/IP-TP分片处理

代码中处理SOME/IP-TP (分片传输):
- message_type = 0x22 表示分片
- 需要重组多个分片

---

## 七、Python实现框架

### 7.1 核心模块结构

```
your_python_project/
├── someip/
│   ├── __init__.py
│   ├── protocol.py       # SOME/IP头部定义和解析
│   ├── serialization.py  # 序列化/反序列化实现
│   ├── data_types.py     # 23种数据类型定义
│   ├── udp_socket.py     # UDP socket封装
│   └── service_manager.py # 服务管理
├── config/
│   └── vsomeip.json     # 配置文件
├── client.py            # 客户端主程序
└── server.py            # 服务端主程序
```

### 7.2 关键实现要点

1. **字节序**: 必须使用大端序 (Big Endian)
2. **结构体对齐**: 1字节对齐 (`#pragma pack(1)`)
3. **字符串格式**: 长度(4字节) + BOM(3字节) + 内容
4. **动态数组**: 需要先读取长度字段,再读取数据
5. **网络通信**: UDP多播, 需要加入224.0.2.4组

---

## 八、配置文件格式

### 8.1 客户端配置 (someip_arhud01.json)

```json
{
    "unicast": "192.168.195.11",
    "network": "arhud01",
    "routing": "arhud01",
    "service-discovery": {
        "multicast": "224.0.2.4",
        "port": 30490,
        "protocol": "udp"
    },
    "clients": [
        {"service": "0x000A", "instance": "0x000A", "unreliable": ["52001"], "events": [...], "event_group": "0x1101"},
        ...
    ]
}
```

### 8.2 服务端配置 (someip_arhud01_pcap_server.json)

```json
{
    "unicast": "192.168.195.11",
    "network": "arhud01",
    "applications": [{"name": "arhud01", "id": "0x1443"}],
    "services": [
        {
            "service": "0x000A",
            "instance": "0x000A",
            "unreliable": "51400",
            "events": [{"event": "0x8001"}],
            "eventgroups": [{"eventgroup": "0x1101", "events": ["0x8001"]}]
        },
        ...
    ],
    "service-discovery": {...}
}
```

---

## 附录B: Python服务端实现注意事项

### 一、客户端订阅机制分析

C++客户端使用 `clientSubscribeCallbackFuncRegist()` 函数订阅事件，参数格式为：
```cpp
clientSubscribeCallbackFuncRegist(service_id, instance_id, event_id, event_group_id, callback, param)
```

### 二、完整订阅列表 (23个事件)

| 序号 | Service ID | Instance ID | Event ID | Event Group |
|------|------------|-------------|----------|-------------|
| 0 | 0x000A | 0x000A | 0x8001 | 0x1101 |
| 1 | 0x000B | 0x000B | 0x8001 | 0x1101 |
| 2 | 0x000B | 0x000B | 0x8002 | 0x1101 |
| 3 | 0x000C | 0x000C | 0x8001 | 0x1101 |
| 4 | 0x000C | 0x000C | 0x8002 | 0x1101 |
| 5 | 0x000D | 0x000D | 0x8001 | 0x1101 |
| 6 | 0x000D | 0x000D | 0x8002 | 0x1101 |
| 7 | 0x000D | 0x000D | 0x8003 | 0x1101 |
| 8 | 0x000D | 0x000D | 0x8004 | 0x1101 |
| 9 | 0x010A | 0x0001 | 0x8001 | 0x1101 |
| 10 | 0x010A | 0x0001 | 0x8002 | 0x1101 |
| 11 | 0x010A | 0x0001 | 0x8003 | 0x1101 |
| 12 | 0x010A | 0x0001 | 0x8004 | 0x1101 |
| 13 | 0x000C | 0x000C | 0x8003 | 0x1101 |
| 14 | 0x000D | 0x000D | 0x8005 | 0x1101 |
| 15 | 0x000E | 0x000E | 0x8001 | 0x1101 |
| 16 | 0x0007 | 0x0007 | 0x8001 | 0x1101 |
| 17 | 0x0017 | 0x0017 | 0x8003 | 0x1101 |
| 18 | 0x002B | 0x002B | 0x8001 | 0x1101 |
| 19 | 0x8202 | 0x8202 | 0x8002 | 0x1101 |
| 20 | 0x000E | 0x000E | 0x8002 | **0x1102** |
| 21 | 0x000E | 0x000E | 0x8003 | **0x1103** |
| 22 | 0x0018 | 0x0018 | 0x8001 | 0x1101 |

### 三、关键注意事项

#### 3.1 Instance ID 特殊处理

- **Service 0x010A**: Instance ID = **0x0001** (不是0x010A!)
- **其他Services**: Instance ID = Service ID

#### 3.2 Event Group 特殊处理

- **0x000E (PlanningLineInfo)** 服务有3个不同的Event Group：
  - Event 0x8001 -> Event Group 0x1101
  - Event 0x8002 -> Event Group **0x1102**
  - Event 0x8003 -> Event Group **0x1103**

#### 3.3 服务端配置关键点

服务端需要为每个Service配置正确的Instance ID和端口：

```json
{
    "services": [
        {
            "service": "0x000A",
            "instance": "0x000A",
            "unreliable": "51400",
            "events": [{"event": "0x8001"}],
            "event_group": "0x1101"
        },
        {
            "service": "0x010A",
            "instance": "0x0001",
            "unreliable": "52001",
            "events": [
                {"event": "0x8001"},
                {"event": "0x8002"},
                {"event": "0x8003"},
                {"event": "0x8004"}
            ],
            "event_group": "0x1101"
        },
        {
            "service": "0x000E",
            "instance": "0x000E",
            "unreliable": "51404",
            "events": [
                {"event": "0x8001", "event_groups": ["0x1101"]},
                {"event": "0x8002", "event_groups": ["0x1102"]},
                {"event": "0x8003", "event_groups": ["0x1103"]}
            ]
        }
    ]
}
```

#### 3.4 SOME/IP-TP 配置

Service 0x010A 配置了 `someip-tp` (SOME/IP Transport Protocol)，用于大帧分片：
```json
"someip-tp": {"client-to-service": ["0x8001", "0x8003"]}
```

### 四、数据序列化要求

#### 4.1 字符串格式

- 带BOM的UTF-8: 0xEF 0xBB 0xBF + 内容 + 空终止符
- 长度字段 = 字符串长度 + 4 (包含BOM的3字节 + 终止符1字节)

#### 4.2 动态数组

动态数组前面需要4字节的长度字段(小端序)，表示数组元素个数。

#### 4.3 字节序

所有多字节数值采用小端序(Little Endian)。

### 五、服务发现配置

服务端需要正确配置Service Discovery：

```json
"service-discovery": {
    "enable": true,
    "multicast": "224.0.2.4",
    "port": 30490,
    "protocol": "udp",
    "initial_delay_min": "0",
    "initial_delay_max": "100",
    "repetitions_base_delay": "100",
    "repetitions_max": "3",
    "ttl": "3"
}
```

### 六、Python服务端实现要点

```python
import vsomeip

# 关键配置
SERVICE_CONFIG = {
    "unicast": "192.168.195.11",      # 服务端IP
    "routing": "arhud01",
    "service-discovery": {
        "multicast": "224.0.2.4",
        "port": 30490
    }
}

# 23个事件的订阅配置
SUBSCRIPTIONS = [
    {"service": 0x000A, "instance": 0x000A, "event": 0x8001, "event_group": 0x1101},
    {"service": 0x000B, "instance": 0x000B, "event": 0x8001, "event_group": 0x1101},
    {"service": 0x000B, "instance": 0x000B, "event": 0x8002, "event_group": 0x1101},
    # ... 完整23个事件
    # 特别注意 0x000E 服务的不同Event Group!
    {"service": 0x000E, "instance": 0x000E, "event": 0x8002, "event_group": 0x1102},
    {"service": 0x000E, "instance": 0x000E, "event": 0x8003, "event_group": 0x1103},
]
```

### 七、调试建议

1. **启用SD日志**: 配置中设置 "logging": {"level": "debug"}
2. **使用Wireshark**: 过滤条件 someip || sdp
3. **检查多播**: 确认网络支持 224.0.2.4 多播
4. **端口检查**: 确保服务端端口未被占用

---

## 九、注意事项

1. **所有数据使用大端序**: 无论是序列化还是反序列化
2. **PCAP文件路径**: 服务端从可执行文件同目录的 `out.pcap` 读取
3. **循环播放**: 代码中 `LOOP_HUIFANG` 默认为1,会循环播放
4. **VLAN标签**: 需要处理0x8100 VLAN标签
5. **SOME/IP-SD**: 跳过service_id=0xFFFF的SD数据包

---

*文档基于 to_longjie_demo_20250625 的C++代码编写*
*创建时间: 2025年6月25日*