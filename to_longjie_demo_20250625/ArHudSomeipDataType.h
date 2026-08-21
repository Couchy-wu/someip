/******************************************************************************
*brief:     autosar SOME/IP serialization and deserialization
*version:   1.0
*author:    li.peng89
*time:      2023/06/09
******************************************************************************/

#ifndef AR_HUD_SOMEIP_DATA_TYPE_H
#define AR_HUD_SOMEIP_DATA_TYPE_H

#include <stdio.h>
#include <stdint.h>
#include <string>
#include <string.h>
using std::string;

#ifndef float64
#define float64 double
#endif

#ifndef float32
#define float32 float
#endif

#pragma pack(1)
//VehiclePositionInfoNotify
typedef struct st_VehiclePositionInfoNotify
{
    uint32_t    Checksum;                          
    uint16_t    Counter;                           
    double      Longitude;                         
    double      Latitude;                          
    double      altitude;                          
    double      Heading;                           
    double      hd_lane_left_angle;                
    double      Hd_lane_right_angle;               
    double      VehicleSpeed;                      
    double      acceleration;                      
    double      x_speed;                           
    double      y_speed;                           
    double      z_speed;                           
    double      timestamp;                         
    uint32_t    hd_link_id;                        
    uint32_t    hd_lane_id;                        
    uint32_t    hd_lane_type;                      
    double      on_lane_offset;                    
    uint32_t    hd_lane_seq;                       
    uint32_t    hd_lane_num;                       
    double      hd_lane_left_lateral_offset;       
    double      hd_lane_right_lateral_offset;      
    double      roll;                              
    double      pitch;                             
    uint8_t     HdStatus;                          
    uint32_t    hdmap_version;                     
    uint32_t    fusion_status;                     
    double      pos_confidence;                    
    uint8_t     position_type;                     
    uint8_t     break_light;                       
    uint8_t     indicator_light;                   
    uint8_t     Lights;                            
    uint8_t     Weather;                           
    float       target_cruise_speed;               
    uint32_t    FieldLength_target_lane;           
    uint32_t*   target_lane_id;                    
    uint32_t    FieldLength_target_lane_id_segment;
    uint32_t*   target_lane_id_segment;            
    uint8_t     localization_output_offset;   

    st_VehiclePositionInfoNotify()
    {
        target_lane_id = target_lane_id_segment = nullptr;
    }

    st_VehiclePositionInfoNotify(const st_VehiclePositionInfoNotify &other)
    {
        *this = other;
    }

    st_VehiclePositionInfoNotify& operator=(const st_VehiclePositionInfoNotify &other)
    {
        if (target_lane_id != nullptr){delete[] target_lane_id; target_lane_id = nullptr;}
        if (target_lane_id_segment != nullptr){delete[] target_lane_id_segment; target_lane_id_segment = nullptr;}
        memset(this, 0, sizeof(st_VehiclePositionInfoNotify));
        memcpy(this, &other, sizeof(st_VehiclePositionInfoNotify));

        if (FieldLength_target_lane > 0)
        {
            target_lane_id = new uint32_t[FieldLength_target_lane];
            memset(target_lane_id, 0, sizeof(uint32_t)*FieldLength_target_lane);
            memcpy(target_lane_id, other.target_lane_id, sizeof(uint32_t)*FieldLength_target_lane);
        }

        if (FieldLength_target_lane_id_segment > 0)
        {
            target_lane_id_segment = new uint32_t[FieldLength_target_lane_id_segment];
            memset(target_lane_id_segment, 0, sizeof(uint32_t)*FieldLength_target_lane_id_segment);
            memcpy(target_lane_id_segment, other.target_lane_id_segment, sizeof(uint32_t)*FieldLength_target_lane_id_segment);
        }
        return (*this);
    }

    ~st_VehiclePositionInfoNotify()
    {
        if (target_lane_id != nullptr){delete[] target_lane_id; target_lane_id = nullptr;}
        if (target_lane_id_segment != nullptr){delete[] target_lane_id_segment; target_lane_id_segment = nullptr;}
    }
}stVehiclePositionInfoNotify;

//RTKInfoNotify
typedef struct st_RTKInfoNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    uint32_t    rtk_status;
    float64     utc_time_us;
    float64     sys_time_us;
    float64     longitude;
    float64     latitude;
    float64     altitude;
    float64     longitude_acc;
    float64     latitude_acc;
    float64     altitude_acc;
    float64     heading_move;
    float64     heading_double_ant;
    float64     heading_move_acc;
    float64     speed_2d;
    float64     speed_acc;
    float64     speed_n;
    float64     speed_e;
    float64     speed_u;
    float64     g_dop;
    float64     h_dop;
    float64     v_dop;
    uint32_t    satellite_num;
    uint32_t    satellite_used;
    float64     snr_max;
    float64     snr_mix;
    float64     snr_avr;

    st_RTKInfoNotify()
    {
    }
}stRTKInfoNotify;

//IMUInfoNotify
typedef struct st_IMUInfoNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    double      angular_velocity_x;
    double      angular_velocity_y;
    double      angular_velocity_z;
    double      acc_speed_x;
    double      acc_speed_y;
    double      acc_speed_z;
    uint8_t     IMU_status;
    double      IMU_current_temperature;
    double      sys_time_us;
    bool        is_calibrated;

    st_IMUInfoNotify()
    {
    }
}stIMUInfoNotify;

//ObstacleInfoNotify
typedef struct st_ObstacleInfoNotify_FLO
{
    uint32_t    ObstacleType;
    double      confidence;
    uint32_t    Obstacle_Id_i;
    double      ObstacleDistance_X_i;
    double      ObstacleDistance_Y_i;
    double      ObstacleDistance_Z_i;
    float       Bounding_box_length_i;
    float       Bounding_box_width_i;
    float       Bounding_box_height_i;
    uint8_t     break_light;
    uint8_t     indicator_light;
    double      obj_speed;
    uint8_t     ObstacleState;
    double      obstacle_timestamp;
    double      obstacle_camera_timestamp;
    bool        moving;
    double      obj_heading;
    double      Obj_direction;
    uint8_t     ObstacleWarningBrakeState;
}stObstacleInfoNotifyFLO;

typedef struct st_ObstacleInfoNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    bool        target_flag;
    uint32_t    FieldLength_Object_len;
    stObstacleInfoNotifyFLO* FieldLength_Object;

    st_ObstacleInfoNotify()
    {
        FieldLength_Object_len = 0;
        FieldLength_Object = nullptr;
    }     

    st_ObstacleInfoNotify(const st_ObstacleInfoNotify &other)
    {
        *this = other;
    }

    st_ObstacleInfoNotify& operator=(const st_ObstacleInfoNotify &other)
    {
        if (FieldLength_Object != nullptr){delete[] FieldLength_Object; FieldLength_Object = nullptr;}
        memset(this, 0, sizeof(st_ObstacleInfoNotify));
        memcpy(this, &other, sizeof(st_ObstacleInfoNotify));

        if (FieldLength_Object_len >= 97)
        {
            FieldLength_Object = new stObstacleInfoNotifyFLO[FieldLength_Object_len/97];
            memset(FieldLength_Object, 0, FieldLength_Object_len);
            memcpy(FieldLength_Object, other.FieldLength_Object, FieldLength_Object_len);
        }

        return (*this);
    }

    ~st_ObstacleInfoNotify()
    {
        FieldLength_Object_len = 0;
        if (FieldLength_Object != nullptr){delete[] FieldLength_Object; FieldLength_Object = nullptr;}
    }
}stObstacleInfoNotify;


//LanelineDataNotify
typedef struct st_LanelineDataNotify_FLL
{
    int32_t     LineID;
    uint8_t     LineType;
    uint8_t     LineColor;
    float       LineWidth;
    double      Line_confidence;
    float       CurvatureEquation_c0;
    float       CurvatureEquation_c1;
    float       CurvatureEquation_c2;
    float       CurvatureEquation_c3;
    float       Line_Startpoint_x;
    float       Line_Startpoint_y;
    float       Line_Startpoint_z;
    float       Line_Endpoint_x;
    float       Line_Endpoint_y;
    float       Line_Endpoint_z;
    double      sys_time_us;
    //uint64_t      sys_time_us;
}stLanelineDataNotifyFLL;

typedef struct st_LanelineDataNotify_FLRM
{
    uint32_t    RoadMarkingID_i;
    uint8_t     RoadMarkingType_i;
    double      RoadMarkingType_confidence_i;
    float       RoadMarking_length_i;
    float       RoadMarking_width_i;
    float       RoadMarking_height_i;
    double      RoadMarking_Distance_X_i;
    double      RoadMarking_Distance_Y_i;
    double      RoadMarking_Distance_Z_i;
    double      RoadMarkingPosition_confidence;
}stLanelineDataNotifyFLRM;

typedef struct st_LanelineDataNotify_FLTLA
{
    uint32_t    TLAID_i;
    double      TLA_Distance_X;
    double      TLA_Distance_Y;
    double      TLA_Distance_Z;
    double      TLAPosition_confidence;
    uint8_t     LeftTLA_Color;
    uint8_t     LeftTLA_Type;
    uint8_t     StraightTLA_Color;
    uint8_t     StraightTLA_Type;
    uint8_t     RightTLA_Color;
    uint8_t     RightTLA_Type;
}stLanelineDataNotifyFLTLA;

typedef struct st_LanelineDataNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    uint32_t    FieldLength_Line_len;
    stLanelineDataNotifyFLL* FieldLength_Line;
    uint32_t    FieldLength_RoadMarking_len;
    stLanelineDataNotifyFLRM* FieldLength_RoadMarking;
    uint32_t    FieldLength_TLA_len;
    stLanelineDataNotifyFLTLA* FieldLength_TLA;

    st_LanelineDataNotify()
    {
        FieldLength_Line_len = 0;
        FieldLength_Line = nullptr;
        FieldLength_RoadMarking_len = 0;
        FieldLength_RoadMarking = nullptr;
        FieldLength_TLA_len = 0;
        FieldLength_TLA = nullptr;
    }

    st_LanelineDataNotify(const st_LanelineDataNotify &other)
    {
        *this = other;
    }

    st_LanelineDataNotify& operator=(const st_LanelineDataNotify &other)
    {
        if (FieldLength_Line != nullptr){delete[] FieldLength_Line; FieldLength_Line = nullptr;}
        if (FieldLength_RoadMarking != nullptr){delete[] FieldLength_RoadMarking; FieldLength_RoadMarking = nullptr;}
        if (FieldLength_TLA != nullptr){delete[] FieldLength_TLA; FieldLength_TLA = nullptr;}
        memset(this, 0, sizeof(st_LanelineDataNotify));
        memcpy(this, &other, sizeof(st_LanelineDataNotify));

        FieldLength_Line = new stLanelineDataNotifyFLL[FieldLength_Line_len/66];
        memset(FieldLength_Line, 0, FieldLength_Line_len);
        memcpy(FieldLength_Line, other.FieldLength_Line, FieldLength_Line_len);

        FieldLength_RoadMarking = new stLanelineDataNotifyFLRM[FieldLength_RoadMarking_len/57];
        memset(FieldLength_RoadMarking, 0, FieldLength_RoadMarking_len);
        memcpy(FieldLength_RoadMarking, other.FieldLength_RoadMarking, FieldLength_RoadMarking_len);

        FieldLength_TLA = new stLanelineDataNotifyFLTLA[FieldLength_TLA_len/42];
        memset(FieldLength_TLA, 0, FieldLength_TLA_len);
        memcpy(FieldLength_TLA, other.FieldLength_TLA, FieldLength_TLA_len);

        return (*this);
    }

    ~st_LanelineDataNotify()
    {
        FieldLength_Line_len = FieldLength_RoadMarking_len = FieldLength_TLA_len = 0;
        if (FieldLength_Line != nullptr){delete[] FieldLength_Line; FieldLength_Line = nullptr;}
        if (FieldLength_RoadMarking != nullptr){delete[] FieldLength_RoadMarking; FieldLength_RoadMarking = nullptr;}
        if (FieldLength_TLA != nullptr){delete[] FieldLength_TLA; FieldLength_TLA = nullptr;}
    }
}stLanelineDataNotify;

//14.NewLanelineDataNotify
typedef struct st_NLLDN_New_FieldLength_LinePoints
{
    uint32_t    New_LinePointsID_i;
    double      New_LinePoints_X;
    double      New_LinePoints_Y;
    double      New_LinePoints_Z;
}stNLLDN_New_FieldLength_LinePoints;

typedef struct st_NLLDN_FieldLength_Line
{
    int32_t     New_LineID;
    int32_t     LineID;
    uint8_t     LineType;
    uint8_t     New_LineWarningColor;
    uint8_t     LineColor;
    float       LineWidth;
    double      Line_confidence;
    float       CurvatureEquation_c0;
    float       CurvatureEquation_c1;
    float       CurvatureEquation_c2;
    float       CurvatureEquation_c3;
    float       Line_Startpoint_x;
    float       Line_Startpoint_y;
    float       Line_Startpoint_z;
    float       Line_Endpoint_x;
    float       Line_Endpoint_y;
    float       Line_Endpoint_z;

    uint32_t    New_FieldLength_LinePoints_len;
    stNLLDN_New_FieldLength_LinePoints* New_FieldLength_LinePoints;

    double sys_time_us;
    //uint64_t sys_time_us;
    double lineI_Reserved1;
    double lineI_Reserved2;
    double lineI_Reserved3;
    double lineI_Reserved4;
    double lineI_Reserved5;
    int32_t     len;
}stNLLDN_FieldLength_Line;

typedef struct st_NLLDN_FieldLength_TLA
{
    uint32_t    TLAID_i;
    double      TLA_Distance_X;
    double      TLA_Distance_Y;
    double      TLA_Distance_Z;
    double      TLAPosition_confidence;
    uint8_t     LeftTLA_Color;
    uint8_t     LeftTLA_Type;
    uint8_t     StraightTLA_Color;
    uint8_t     StraightTLA_Type;
    uint8_t     RightTLA_Color;
    uint8_t     RightTLA_Type;
    uint8_t     New_LeftTLA_Second;
    uint8_t     New_StraightTLA_Second;
    uint8_t     New_RightTLA_Second;
    double      TLA_Reserved1;
    double      TLA_Reserved2;
    double      TLA_Reserved3;
    double      TLA_Reserved4;
    double      TLA_Reserved5;
}stNLLDN_FieldLength_TLA;

typedef struct st_NLLDN_New_FieldLength_TSR
{
    uint32_t    New_TSRID_i;
    double      New_TSR_Distance_X;
    double      New_TSR_Distance_Y;
    double      New_TSR_Distance_Z;
    double      New_TSRPosition_confidence;
    uint8_t     New_TSR_Type;
    uint8_t     New_Speed_Limit;
    double      tolColor;
    double      tsrHeading;
    double      TSR_Reserved3;
    double      TSR_Reserved4;
    double      TSR_Reserved5;
}stNLLDN_New_FieldLength_TSR;

typedef struct st_NLLDN_FieldLength_LanelineReserved
{
    uint8_t     Reserved1;
}stNLLDN_FieldLength_LanelineReserved;

typedef struct st_NewLanelineDataNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    uint32_t    FieldLength_Line_len;
    stNLLDN_FieldLength_Line* FieldLength_Line;
    uint32_t    FieldLength_TLA_len;
    stNLLDN_FieldLength_TLA* FieldLength_TLA;
    uint32_t    New_FieldLength_TSR_len;
    stNLLDN_New_FieldLength_TSR* New_FieldLength_TSR;
    uint32_t    FieldLength_LanelineReserved_len;
    stNLLDN_FieldLength_LanelineReserved* FieldLength_LanelineReserved;

    st_NewLanelineDataNotify()
    {
        FieldLength_Line_len = 0;
        FieldLength_Line = nullptr;
        FieldLength_TLA_len = 0;
        FieldLength_TLA = nullptr;
        New_FieldLength_TSR_len = 0;
        New_FieldLength_TSR = nullptr;
        FieldLength_LanelineReserved_len = 0;
        FieldLength_LanelineReserved = nullptr;
    }

    st_NewLanelineDataNotify(const st_NewLanelineDataNotify &other)
    {
        *this = other;
    }

    st_NewLanelineDataNotify& operator=(const st_NewLanelineDataNotify &other)
    {
        if (FieldLength_Line != nullptr){delete[] FieldLength_Line; FieldLength_Line = nullptr;}
        if (FieldLength_TLA != nullptr){delete[] FieldLength_TLA; FieldLength_TLA = nullptr;}
        if (New_FieldLength_TSR != nullptr){delete[] New_FieldLength_TSR; New_FieldLength_TSR = nullptr;}
        if (FieldLength_LanelineReserved != nullptr){delete[] FieldLength_LanelineReserved; FieldLength_LanelineReserved = nullptr;}
        memset(this, 0, sizeof(st_NewLanelineDataNotify));
        memcpy(this, &other, sizeof(st_NewLanelineDataNotify));

        if (FieldLength_Line_len >= sizeof(stNLLDN_FieldLength_Line))
        {
            FieldLength_Line = new stNLLDN_FieldLength_Line[FieldLength_Line_len/66];
            memset(FieldLength_Line, 0, FieldLength_Line_len);
            memcpy(FieldLength_Line, other.FieldLength_Line, FieldLength_Line_len);
        }

        if (FieldLength_TLA_len >= sizeof(stNLLDN_FieldLength_TLA))
        {
            FieldLength_TLA = new stNLLDN_FieldLength_TLA[FieldLength_TLA_len/42];
            memset(FieldLength_TLA, 0, FieldLength_TLA_len);
            memcpy(FieldLength_TLA, other.FieldLength_TLA, FieldLength_TLA_len);
        }

        if (New_FieldLength_TSR_len >= sizeof(stNLLDN_New_FieldLength_TSR))
        {
            New_FieldLength_TSR = new stNLLDN_New_FieldLength_TSR[New_FieldLength_TSR_len/85];
            memset(New_FieldLength_TSR, 0, New_FieldLength_TSR_len);
            memcpy(New_FieldLength_TSR, other.New_FieldLength_TSR, New_FieldLength_TSR_len);
        }

        if (FieldLength_LanelineReserved_len >= sizeof(stNLLDN_FieldLength_LanelineReserved))
        {
            FieldLength_LanelineReserved = new stNLLDN_FieldLength_LanelineReserved[FieldLength_LanelineReserved_len/1];
            memset(FieldLength_LanelineReserved, 0, FieldLength_LanelineReserved_len);
            memcpy(FieldLength_LanelineReserved, other.FieldLength_LanelineReserved, FieldLength_LanelineReserved_len);
        }

        return (*this);
    }

    ~st_NewLanelineDataNotify()
    {
        FieldLength_Line_len  = FieldLength_TLA_len = 0;
        if (FieldLength_Line != nullptr){delete[] FieldLength_Line; FieldLength_Line = nullptr;}
        if (FieldLength_TLA != nullptr){delete[] FieldLength_TLA; FieldLength_TLA = nullptr;}
        if (New_FieldLength_TSR != nullptr){delete[] New_FieldLength_TSR; New_FieldLength_TSR = nullptr;}
    }
}stNewLanelineDataNotify;

//ChangeLaneDataNotify
typedef struct st_ChangeLaneDataNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    uint32_t    ChangeLaneState;
    uint8_t     ChangeLaneDirection;
    bool        is_change_safety;
    uint32_t    ChangeLane_timestamp;
    double      change_ratio;
    uint32_t    change_termi;
    double      landing_center_X;
    double      landing_center_Y;
    double      landing_center_Z;
    double      landing_box_length;
    double      landing_box__width;
    double      landing_box_height;

    st_ChangeLaneDataNotify()
    {
    }
}stChangeLaneDataNotify;

//PilotStatusNotify
typedef struct st_PilotStatusNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    uint8_t     ACCStatus;
    uint8_t     ICCStatus;
    uint8_t     DNPStatus;
    bool        TakeoverStatus;
    uint32_t    driving_time;

    st_PilotStatusNotify()
    {
    }
}stPilotStatusNotify;

//PilotAlarmAndNoticeInfoNotify
typedef struct st_PilotAlarmAndNoticeInfoNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    uint32_t    PilotAlarmReason;
    uint32_t    alarm_distance;
    uint32_t    alarm_stage;
    double      alarm_timestamp;
    uint32_t    PilotNotice;
    uint32_t    notice_distance;
    double      notice_timestamp;

    st_PilotAlarmAndNoticeInfoNotify()
    {
    }
}stPilotAlarmAndNoticeInfoNotify;

//BroadcastInfoNotify
typedef struct st_BroadcastInfoNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    bool        driver_attention;
    bool        large_vehicles;
    bool        dangerous_vehicle;
    bool        pedestrians;

    st_BroadcastInfoNotify()
    {
    }
}stBroadcastInfoNotify;

//NewBroadcastInfoNotify
typedef struct st_NewBroadcastInfoNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    uint16_t    NOAMode;
    uint16_t    notice;
    double      Info_Reserved1;
    double      Info_Reserved2;
    double      Info_Reserved3;
    double      Info_Reserved4;
    double      Info_Reserved5;

    st_NewBroadcastInfoNotify()
    {
    }
}stNewBroadcastInfoNotify;


//PlanningLineInfoNotify
typedef struct st_PlanningLineInfoNotify_FPLP
{
    uint32_t    PlanningLinePointsID_i;
    double      points_X;
    double      points_Y;
    double      points_Z;
}stPlanningLineInfoNotifyFPLP;

typedef struct st_PlanningLineInfoNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    bool        PlanningLineStatus;
    double      planning_timestamp;
    uint32_t    FieldLength_PlanningLinePoints_len;
    stPlanningLineInfoNotifyFPLP* FieldLength_PlanningLinePoints;

    st_PlanningLineInfoNotify()
    {
        FieldLength_PlanningLinePoints_len = 0;
        FieldLength_PlanningLinePoints = nullptr;
    }    

    st_PlanningLineInfoNotify(const st_PlanningLineInfoNotify &other)
    {
        *this = other;
    }

    st_PlanningLineInfoNotify& operator=(const st_PlanningLineInfoNotify &other)
    {
        if (FieldLength_PlanningLinePoints != nullptr){delete[] FieldLength_PlanningLinePoints; FieldLength_PlanningLinePoints = nullptr;}
        memset(this, 0, sizeof(st_PlanningLineInfoNotify));
        memcpy(this, &other, sizeof(st_PlanningLineInfoNotify));
        
        FieldLength_PlanningLinePoints = new stPlanningLineInfoNotifyFPLP[FieldLength_PlanningLinePoints_len/28];
        memset(FieldLength_PlanningLinePoints, 0, FieldLength_PlanningLinePoints_len);
        memcpy(FieldLength_PlanningLinePoints, other.FieldLength_PlanningLinePoints, FieldLength_PlanningLinePoints_len);

        return (*this);
    } 

    ~st_PlanningLineInfoNotify()
    {
        FieldLength_PlanningLinePoints_len = 0;
        if (FieldLength_PlanningLinePoints != nullptr){delete[] FieldLength_PlanningLinePoints; FieldLength_PlanningLinePoints = nullptr;}
    }
}stPlanningLineInfoNotify;

//NavigationStatus_LinkInfoNotify
typedef struct st_NavigationStatus_LinkInfoNotify
{
    uint32_t      Checksum;
    uint16_t      Counter;
    double        timestamp;
    uint8_t       NavigationStatus;
    uint8_t       MatchingTableStatus;
    uint32_t      RemainDistance;
    uint32_t      ViaPointDistance;
    uint32_t      HDStartDistance;
    uint8_t       DNP_Switch;
    uint8_t       ANP_road;
    uint32_t      MapVersion;
    uint32_t      FieldLength_LinK;
    uint64_t*     LinkID;
    // uint64_t      reserve1;
    // uint32_t      reserve2;
    // float         reserve3;

    st_NavigationStatus_LinkInfoNotify()
    {
        FieldLength_LinK = 0;
        LinkID = nullptr;
    }

        st_NavigationStatus_LinkInfoNotify(const st_NavigationStatus_LinkInfoNotify &other)
    {
        *this = other;
    }

    st_NavigationStatus_LinkInfoNotify& operator=(const st_NavigationStatus_LinkInfoNotify &other)
    {
        if (LinkID != nullptr){delete[] LinkID; LinkID = nullptr;}
        memset(this, 0, sizeof(st_NavigationStatus_LinkInfoNotify));
        memcpy(this, &other, sizeof(st_NavigationStatus_LinkInfoNotify));
        
        LinkID = new uint64_t[FieldLength_LinK/sizeof(uint64_t)];
        memset(LinkID, 0, FieldLength_LinK);
        memcpy(LinkID, other.LinkID, FieldLength_LinK);

        return (*this);
    }

    ~st_NavigationStatus_LinkInfoNotify()
    {
        LinkID = 0;
        if (LinkID != nullptr){delete[] LinkID; LinkID = nullptr;}
    }

}stNavigationStatus_LinkInfoNotify;


//NewParkingRealTimeDataNotify
typedef struct st_FieldLength_Object_NPRTDN
{
    uint64_t      ObjectID_i;
    double        shape_height_i;
    double        shape_length_i;
    double        shape_width_i;
    double        position_x_i;
    double        position_y_i;
    double        position_z_i;
    float32       Heading_i;
    uint8_t       TypeInfo;
    uint8_t       CrashRisk;
    uint8_t       NewMoveST;
    uint16_t      NewAbsoluteVelocity;
    uint8_t       NewTurnSignalLampSt;
    uint8_t       NewHigh_lowBeamLampsSt;
    uint8_t       NewBrakeLightSt;
    uint8_t       NewReversingLightSt;
    double        ParkingObjectInfo_Reserved1;
    double        blockingBarStatus;
    double        blockingBarTypeInfo;
    double        blockingBarDirInfo;
    double        ParkingObjectInfo_Reserved5;
}stFieldLength_ObjectNPRTDN;

typedef struct st_FieldLength_ParkingSlot_NPRTDN
{
    uint32_t      ParkngSpcID_i;
    uint8_t       ParkngSpcSts;
    uint8_t       ParkngSpcCode_i;
    float32       x1_i;
    float32       y1_i;
    float32       x2_i;
    float32       y2_i;
    float32       x3_i;
    float32       y3_i;
    float32       x4_i;
    float32       y4_i;
    uint8_t       ParkngSpcType;
    uint64_t      ParkngSpcNum;
    uint8_t       E4CornerMark;
    double        parkngSlotNumber;
    double        ParkingSlotInfo_Reserved2;
    double        ParkingSlotInfo_Reserved3;
    double        ParkingSlotInfo_Reserved4;
    double        ParkingSlotInfo_Reserved5;
}stFieldLength_ParkingSlotNPRTDN;

typedef struct st_FieldLength_RealTimeTrackPoint_NPRTDN
{
    uint32_t      RealTimeTrackPointID_i;
    double        x_i;
    double        y_i;
    double        heading_i;
    double        stopLine;
    double        GuideLineInfo_Reserved2;
    double        GuideLineInfo_Reserved3;
    double        GuideLineInfo_Reserved4;
    double        GuideLineInfo_Reserved5;
}stFieldLength_RealTimeTrackPointNPRTDN;

typedef struct st_FieldLength_HistoryTrackPoint_NPRTDN
{
    uint32_t      HistoryTrackPointID_i;
    double        x_i;
    double        y_i;
    double        z_i;
    uint32_t      Width_Learning;
    double        cruiseHistoryTrackPointID_i;
    double        cruiseHistoryX;
    double        cruiseHistoryY;
    double        cruiseHistoryZ;
    double        parkinglotLevel;
}stFieldLength_HistoryTrackPointNPRTDN;

typedef struct st_NewParkingRealTimeDataNotify
{
    uint32_t      Checksum;
    uint16_t      Counter;
    double        timestamp;

    uint32_t    FieldLength_Object_len;
    stFieldLength_ObjectNPRTDN* FieldLength_Object;

    uint32_t    FieldLength_ParkingSlot_len;
    stFieldLength_ParkingSlotNPRTDN* FieldLength_ParkingSlot;

    double  Position_x;
    double  Position_y;
    double  Position_z;
    double  Roll;
    double  Yaw;
    double  Pitch;

    uint32_t    FieldLength_RealTimeTrackPoint_len;
    stFieldLength_RealTimeTrackPointNPRTDN* FieldLength_RealTimeTrackPoint;

    uint32_t    FieldLength_HistoryTrackPoint_len;
    stFieldLength_HistoryTrackPointNPRTDN* FieldLength_HistoryTrackPoint;

    float32       Parking_distance_left;
    float32       Cruising_distance_left;
    float32       Learning_distance;
    uint8_t       PathVeriRate;
    uint16_t      Avoid_pedestrians_number;
    uint16_t      Avoid_vehicles_number;
    uint8_t       PathLearnFailDisp;
    uint16_t      Speed_Bump_Number;
    uint8_t       ViewAngleReq;
    double        NRPX1NoPassing;
    double        NRPY1NoPassing;
    double        NRPX2NoPassing;
    double        NRPY2NoPassing;
    double        ParkingRealTimeData_Reserved5;

    st_NewParkingRealTimeDataNotify()
    {
        FieldLength_Object_len = 0;
        FieldLength_Object = nullptr;
        FieldLength_ParkingSlot_len = 0;
        FieldLength_ParkingSlot = nullptr;
        FieldLength_RealTimeTrackPoint_len = 0;
        FieldLength_RealTimeTrackPoint = nullptr;
        FieldLength_HistoryTrackPoint_len = 0;
        FieldLength_HistoryTrackPoint = nullptr;
    }

    st_NewParkingRealTimeDataNotify(const st_NewParkingRealTimeDataNotify &other)
    {
        *this = other;
    }

    st_NewParkingRealTimeDataNotify& operator=(const st_NewParkingRealTimeDataNotify &other)
    {
        if (FieldLength_Object != nullptr){delete[] FieldLength_Object; FieldLength_Object = nullptr;}
        if (FieldLength_ParkingSlot != nullptr){delete[] FieldLength_ParkingSlot; FieldLength_ParkingSlot = nullptr;}
        if (FieldLength_RealTimeTrackPoint != nullptr){delete[] FieldLength_RealTimeTrackPoint; FieldLength_RealTimeTrackPoint = nullptr;}
        if (FieldLength_HistoryTrackPoint != nullptr){delete[] FieldLength_HistoryTrackPoint; FieldLength_HistoryTrackPoint = nullptr;}
        memset(this, 0, sizeof(st_NewParkingRealTimeDataNotify));
        memcpy(this, &other, sizeof(st_NewParkingRealTimeDataNotify));

        if (FieldLength_Object_len >= sizeof(stFieldLength_ObjectNPRTDN))
        {
            FieldLength_Object = new stFieldLength_ObjectNPRTDN[FieldLength_Object_len/sizeof(stFieldLength_ObjectNPRTDN)];
            memset(FieldLength_Object, 0, FieldLength_Object_len);
            memcpy(FieldLength_Object, other.FieldLength_Object, FieldLength_Object_len);
        }

        if (FieldLength_ParkingSlot_len >= sizeof(stFieldLength_ParkingSlotNPRTDN))
        {
            FieldLength_ParkingSlot = new stFieldLength_ParkingSlotNPRTDN[FieldLength_ParkingSlot_len/sizeof(stFieldLength_ParkingSlotNPRTDN)];
            memset(FieldLength_ParkingSlot, 0, FieldLength_ParkingSlot_len);
            memcpy(FieldLength_ParkingSlot, other.FieldLength_ParkingSlot, FieldLength_ParkingSlot_len);
        }

        if (FieldLength_RealTimeTrackPoint_len >= sizeof(stFieldLength_RealTimeTrackPointNPRTDN))
        {
            FieldLength_RealTimeTrackPoint = new stFieldLength_RealTimeTrackPointNPRTDN[FieldLength_RealTimeTrackPoint_len/sizeof(stFieldLength_RealTimeTrackPointNPRTDN)];
            memset(FieldLength_RealTimeTrackPoint, 0, FieldLength_RealTimeTrackPoint_len);
            memcpy(FieldLength_RealTimeTrackPoint, other.FieldLength_RealTimeTrackPoint, FieldLength_RealTimeTrackPoint_len);
        }

        if (FieldLength_HistoryTrackPoint_len >= sizeof(stFieldLength_HistoryTrackPointNPRTDN))
        {
            FieldLength_HistoryTrackPoint = new stFieldLength_HistoryTrackPointNPRTDN[FieldLength_HistoryTrackPoint_len/sizeof(stFieldLength_HistoryTrackPointNPRTDN)];
            memset(FieldLength_HistoryTrackPoint, 0, FieldLength_HistoryTrackPoint_len);
            memcpy(FieldLength_HistoryTrackPoint, other.FieldLength_HistoryTrackPoint, FieldLength_HistoryTrackPoint_len);
        }

        return (*this);
    }

    ~st_NewParkingRealTimeDataNotify()
    {
        FieldLength_Object_len = FieldLength_ParkingSlot_len = FieldLength_RealTimeTrackPoint_len = FieldLength_HistoryTrackPoint_len = 0;
        if (FieldLength_Object != nullptr){delete[] FieldLength_Object; FieldLength_Object = nullptr;}
        if (FieldLength_ParkingSlot != nullptr){delete[] FieldLength_ParkingSlot; FieldLength_ParkingSlot = nullptr;}
        if (FieldLength_RealTimeTrackPoint != nullptr){delete[] FieldLength_RealTimeTrackPoint; FieldLength_RealTimeTrackPoint = nullptr;}
        if (FieldLength_HistoryTrackPoint != nullptr){delete[] FieldLength_HistoryTrackPoint; FieldLength_HistoryTrackPoint = nullptr;}
    }
}stNewParkingRealTimeDataNotify;


//NavigationHDLink2Info
typedef struct st_LinkItemInfo_NHDLI
{
    int32_t         LinkItemFormway1;
    int32_t         LinkItemLinktype1;
    int32_t         LinkItemRoadclass1;
    int32_t         LinkItemBegIdx1;
    int32_t         LinkItemPntCnt1;
    string          LinkItemRoadname_1;
    float           LinkItemLen1;
}stLinkItemInfoNHDLI;

typedef struct st_PntItemInfo_NHDLI
{
    double          PntItem_X1;
    double          PntItem_Y1;
}stPntItemInfoNHDLI;

typedef struct st_LinkItemInfo2_NHDLI
{
    int32_t         LinkItemFormway2;
    int32_t         LinkItemLinktype2;
    int32_t         LinkItemRoadclass2;
    int32_t         LinkItemBegIdx2;
    int32_t         LinkItemPntCnt2;
    string          LinkItemRoadname_2;
    float           LinkItemLen2;
}stLinkItemInfo2NHDLI;

typedef struct st_PntItemInfo2_NHDLI
{
    double          PntItem_X2;
    double          PntItem_Y2;
}stPntItemInfo2NHDLI;

typedef struct st_LinkItemInfo3_NHDLI
{
    int32_t         LinkItemFormway3;
    int32_t         LinkItemLinktype3;
    int32_t         LinkItemRoadclass3;
    int32_t         LinkItemBegIdx3;
    int32_t         LinkItemPntCnt3;
    string          LinkItemRoadname3;
    float           LinkItemLen3;
}stLinkItemInfo3NHDLI;

typedef struct st_PntItemInfo3_NHDLI
{
    double          PntItem_X3;
    double          PntItem_Y3;
}stPntItemInfo3NHDLI;


typedef struct st_NavigationHDLink2Info
{
    
    uint32_t      Checksum;
    uint16_t      Counter;
    uint8_t       NavigationPathValid1;
    uint32_t      RoutePntCnt1;
    int32_t       RouteLinkCnt1;
    uint64_t      RoutePathID1;

    uint32_t                LinkItemInfo_len;
    stLinkItemInfoNHDLI*    LinkItemInfo;
    uint32_t                PntItemInfo_len;
    stPntItemInfoNHDLI*     PntItemInfo;

    uint64_t        reserve1_9;
    uint32_t        reserve2_10;
    float           reserve3_11;
    uint8_t         NavigationPathValid2;
    int32_t         RoutePntCnt2;
    int32_t         RouteLinkCnt2;
    uint64_t        RoutePathID2;

    uint32_t                LinkItemInfo2_len;
    stLinkItemInfo2NHDLI*   LinkItemInfo2;
    uint32_t                PntItemInfo2_len;
    stPntItemInfo2NHDLI*    PntItemInfo2;

    uint64_t        reserve1_18;
    uint32_t        reserve2_25;
    float           reserve3_20;
    uint8_t         NavigationPathValid3;
    int32_t         RoutePntCnt3;
    int32_t         RouteLinkCnt3;
    uint64_t        RoutePathID3;

    uint32_t                LinkItemInfo3_len;
    stLinkItemInfo3NHDLI*   LinkItemInfo3;
    uint32_t                PntItemInfo3_len;
    stPntItemInfo3NHDLI*    PntItemInfo3;

    uint64_t        reserve1_27;
    uint32_t        reserve2_28;
    float           reserve3_29;

    st_NavigationHDLink2Info()
    {
        LinkItemInfo_len = 0;
        LinkItemInfo = nullptr;
        PntItemInfo_len = 0;
        PntItemInfo = nullptr;
        LinkItemInfo2_len = 0;
        LinkItemInfo2 = nullptr;
        PntItemInfo2_len = 0;
        PntItemInfo2 = nullptr;
        LinkItemInfo3_len = 0;
        LinkItemInfo3 = nullptr;
        PntItemInfo3_len = 0;
        PntItemInfo3 = nullptr;
    }

    st_NavigationHDLink2Info(const st_NavigationHDLink2Info &other)
    {
        *this = other;
    }

    st_NavigationHDLink2Info& operator=(const st_NavigationHDLink2Info &other)
    {
        if (LinkItemInfo != nullptr){delete[] LinkItemInfo; LinkItemInfo = nullptr;}
        if (PntItemInfo != nullptr){delete[] PntItemInfo; PntItemInfo = nullptr;}
        if (LinkItemInfo2 != nullptr){delete[] LinkItemInfo2; LinkItemInfo2 = nullptr;}
        if (PntItemInfo2 != nullptr){delete[] PntItemInfo2; PntItemInfo2 = nullptr;}
        if (LinkItemInfo3 != nullptr){delete[] LinkItemInfo3; LinkItemInfo3 = nullptr;}
        if (PntItemInfo3 != nullptr){delete[] PntItemInfo3; PntItemInfo2 = nullptr;}
        memset(this, 0, sizeof(st_NavigationHDLink2Info));
        memcpy(this, &other, sizeof(st_NavigationHDLink2Info));

        if (LinkItemInfo_len >= sizeof(stLinkItemInfoNHDLI))
        {
            LinkItemInfo = new stLinkItemInfoNHDLI[LinkItemInfo_len/sizeof(stLinkItemInfoNHDLI)];
            memset(LinkItemInfo, 0, LinkItemInfo_len);
            memcpy(LinkItemInfo, other.LinkItemInfo, LinkItemInfo_len);
        }

        if (PntItemInfo_len >= sizeof(stPntItemInfoNHDLI))
        {
            PntItemInfo = new stPntItemInfoNHDLI[PntItemInfo_len/sizeof(stPntItemInfoNHDLI)];
            memset(PntItemInfo, 0, PntItemInfo_len);
            memcpy(PntItemInfo, other.PntItemInfo, PntItemInfo_len);
        }

        if (LinkItemInfo2_len >= sizeof(stLinkItemInfo2NHDLI))
        {
            LinkItemInfo2 = new stLinkItemInfo2NHDLI[LinkItemInfo2_len/sizeof(stLinkItemInfo2NHDLI)];
            memset(LinkItemInfo2, 0, LinkItemInfo2_len);
            memcpy(LinkItemInfo2, other.LinkItemInfo2, LinkItemInfo2_len);
        }

        if (PntItemInfo2_len >= sizeof(stPntItemInfo2NHDLI))
        {
            PntItemInfo2 = new stPntItemInfo2NHDLI[PntItemInfo2_len/sizeof(stPntItemInfo2NHDLI)];
            memset(PntItemInfo2, 0, PntItemInfo2_len);
            memcpy(PntItemInfo2, other.PntItemInfo2, PntItemInfo2_len);
        }

        if (LinkItemInfo3_len >= sizeof(stLinkItemInfo3NHDLI))
        {
            LinkItemInfo3 = new stLinkItemInfo3NHDLI[LinkItemInfo3_len/sizeof(stLinkItemInfo3NHDLI)];
            memset(LinkItemInfo3, 0, LinkItemInfo3_len);
            memcpy(LinkItemInfo3, other.LinkItemInfo3, LinkItemInfo3_len);
        }

        if (PntItemInfo3_len >= sizeof(stPntItemInfo3NHDLI))
        {
            PntItemInfo3 = new stPntItemInfo3NHDLI[PntItemInfo3_len/sizeof(stPntItemInfo3NHDLI)];
            memset(PntItemInfo3, 0, PntItemInfo3_len);
            memcpy(PntItemInfo3, other.PntItemInfo3, PntItemInfo3_len);
        }

        return (*this);
    }

    ~st_NavigationHDLink2Info()
    {
        LinkItemInfo_len = PntItemInfo_len = LinkItemInfo2_len = PntItemInfo2_len = 0;
        if (LinkItemInfo != nullptr){delete[] LinkItemInfo; LinkItemInfo = nullptr;}
        if (PntItemInfo != nullptr){delete[] PntItemInfo; PntItemInfo = nullptr;}
        if (LinkItemInfo2 != nullptr){delete[] LinkItemInfo2; LinkItemInfo2 = nullptr;}
        if (PntItemInfo2 != nullptr){delete[] PntItemInfo2; PntItemInfo2 = nullptr;}
        if (LinkItemInfo3 != nullptr){delete[] LinkItemInfo3; LinkItemInfo3 = nullptr;}
        if (PntItemInfo3 != nullptr){delete[] PntItemInfo3; PntItemInfo3 = nullptr;}
    }
}stNavigationHDLink2Info;



//sdTraffiIncident
typedef struct st_TraffiIncident_TI
{
    uint8_t     naviCongestionInfo;
    uint8_t     occupiedLane;
    double      cnstrctnCrdLatitude;
    double      cnstrctnCrdLongitude;
    uint64_t    naviCongestionDistLen;
    uint32_t    occupiedLaneDtl;
    float       reserve3;
}stTraffiIncidentTI;

typedef struct st_sdTraffiIncident
{
    uint32_t               TraffiIncident_len;
    stTraffiIncidentTI*    TraffiIncident;

    st_sdTraffiIncident()
    {
        TraffiIncident_len = 0;
        TraffiIncident = nullptr;
    }

    st_sdTraffiIncident(const st_sdTraffiIncident &other)
    {
        *this = other;
    }

    st_sdTraffiIncident& operator=(const st_sdTraffiIncident &other)
    {
        if (TraffiIncident != nullptr){delete[] TraffiIncident; TraffiIncident = nullptr;}
        memset(this, 0, sizeof(st_sdTraffiIncident));
        memcpy(this, &other, sizeof(st_sdTraffiIncident));

        if (TraffiIncident_len >= sizeof(stTraffiIncidentTI))
        {
            TraffiIncident = new stTraffiIncidentTI[TraffiIncident_len/sizeof(stTraffiIncidentTI)];
            memset(TraffiIncident, 0, TraffiIncident_len);
            memcpy(TraffiIncident, other.TraffiIncident, TraffiIncident_len);
        }

        return (*this);
    }

    ~st_sdTraffiIncident()
    {
        TraffiIncident_len = 0;
        if (TraffiIncident != nullptr){delete[] TraffiIncident; TraffiIncident = nullptr;}
    }
}stsdTraffiIncident;


//newPlanningLineInfo
typedef struct st_fieldLengthPlanningLinePoints_NPLI
{
    uint32_t        PlanningLinePointsID;
    double          pointsX;
    double          pointsY;
    double          pointsZ;
}stfieldLengthPlanningLinePointsNPLI;

typedef struct st_navFieldLengthNavigationPlanningLinePoints_NPLI
{
    uint32_t        navPlanningLinePointsID;
    double          navPointsX;
    double          navPointsY;
    double          navPointsZ;
}stnavFieldLengthNavigationPlanningLinePointsNPLI;

typedef struct st_newPlanningLineInfo
{
    uint32_t        checksum;
    uint16_t        counter;
    bool            planningLineStatus;
    double          planningTimestamp;

    uint32_t        fieldLengthPlanningLinePoints_len;
    stfieldLengthPlanningLinePointsNPLI*    fieldLengthPlanningLinePoints;

    double          accelerationDeceleration;
    bool            navigationPlanningLineStatus;
    double          navigationPlanningTimestamp;

    uint32_t        navFieldLengthNavigationPlanningLinePoints_len;
    stnavFieldLengthNavigationPlanningLinePointsNPLI*    navFieldLengthNavigationPlanningLinePoints;

    uint32_t        reservedDataLength1;
    uint8_t*        reserved1;
    uint32_t        reservedDataLength2;
    uint16_t*       reserved2;
    uint32_t        reservedDataLength3;
    uint32_t*       reserved3;
    uint32_t        reservedDataLength4;
    double*         reserved4;
    uint32_t        reservedDataLength5;
    float32*        reserved5;

    st_newPlanningLineInfo()
    {
        fieldLengthPlanningLinePoints_len = 0;
        fieldLengthPlanningLinePoints = nullptr;
        navFieldLengthNavigationPlanningLinePoints_len = 0;
        navFieldLengthNavigationPlanningLinePoints = nullptr;
        reservedDataLength1 = reservedDataLength2 = reservedDataLength3 = reservedDataLength4 = reservedDataLength5 = 0;
        reserved1 = nullptr;
        reserved2 = nullptr;
        reserved3 = nullptr;
        reserved4 = nullptr;
        reserved5 = nullptr;
    }     

    st_newPlanningLineInfo(const st_newPlanningLineInfo &other)
    {
        *this = other;
    }

    st_newPlanningLineInfo& operator=(const st_newPlanningLineInfo &other)
    {
        if (fieldLengthPlanningLinePoints != nullptr){delete[] fieldLengthPlanningLinePoints; fieldLengthPlanningLinePoints = nullptr;}
        if (navFieldLengthNavigationPlanningLinePoints != nullptr){delete[] navFieldLengthNavigationPlanningLinePoints; navFieldLengthNavigationPlanningLinePoints = nullptr;}
        if (reserved1 != nullptr){delete[] reserved1; reserved1 = nullptr;}
        if (reserved2 != nullptr){delete[] reserved2; reserved2 = nullptr;}
        if (reserved3 != nullptr){delete[] reserved3; reserved3 = nullptr;}
        if (reserved4 != nullptr){delete[] reserved4; reserved4 = nullptr;}
        if (reserved5 != nullptr){delete[] reserved5; reserved5 = nullptr;}
        memset(this, 0, sizeof(st_newPlanningLineInfo));
        memcpy(this, &other, sizeof(st_newPlanningLineInfo));

        if (fieldLengthPlanningLinePoints_len >= sizeof(stfieldLengthPlanningLinePointsNPLI))
        {
            fieldLengthPlanningLinePoints = new stfieldLengthPlanningLinePointsNPLI[sizeof(stfieldLengthPlanningLinePointsNPLI)];
            memset(fieldLengthPlanningLinePoints, 0, fieldLengthPlanningLinePoints_len);
            memcpy(fieldLengthPlanningLinePoints, other.fieldLengthPlanningLinePoints, fieldLengthPlanningLinePoints_len);
        }


        if (navFieldLengthNavigationPlanningLinePoints_len >= sizeof(stnavFieldLengthNavigationPlanningLinePointsNPLI))
        {
            navFieldLengthNavigationPlanningLinePoints = new stnavFieldLengthNavigationPlanningLinePointsNPLI[sizeof(stnavFieldLengthNavigationPlanningLinePointsNPLI)];
            memset(navFieldLengthNavigationPlanningLinePoints, 0, navFieldLengthNavigationPlanningLinePoints_len);
            memcpy(navFieldLengthNavigationPlanningLinePoints, other.navFieldLengthNavigationPlanningLinePoints, navFieldLengthNavigationPlanningLinePoints_len);
        }

        if (reservedDataLength1 >= sizeof(uint8_t))
        {
            reserved1 = new uint8_t[sizeof(uint8_t)];
            memset(reserved1, 0, reservedDataLength1);
            memcpy(reserved1, other.reserved1, reservedDataLength1);
        }

        if (reservedDataLength2 >= sizeof(uint16_t))
        {
            reserved2 = new uint16_t[sizeof(uint16_t)];
            memset(reserved2, 0, reservedDataLength2);
            memcpy(reserved2, other.reserved1, reservedDataLength2);
        }

        if (reservedDataLength3 >= sizeof(uint32_t))
        {
            reserved3 = new uint32_t[sizeof(uint32_t)];
            memset(reserved3, 0, reservedDataLength3);
            memcpy(reserved3, other.reserved3, reservedDataLength3);
        }

        if (reservedDataLength4 >= sizeof(double))
        {
            reserved4 = new double[sizeof(double)];
            memset(reserved4, 0, reservedDataLength4);
            memcpy(reserved4, other.reserved4, reservedDataLength4);
        }

        if (reservedDataLength5 >= sizeof(float32))
        {
            reserved5 = new float32[sizeof(float32)];
            memset(reserved5, 0, reservedDataLength5);
            memcpy(reserved5, other.reserved5, reservedDataLength5);
        }
        return (*this);
    }

    ~st_newPlanningLineInfo()
    {
        fieldLengthPlanningLinePoints_len = navFieldLengthNavigationPlanningLinePoints_len = 0;
        if (fieldLengthPlanningLinePoints != nullptr){delete[] fieldLengthPlanningLinePoints; fieldLengthPlanningLinePoints = nullptr;}
        if (navFieldLengthNavigationPlanningLinePoints != nullptr){delete[] navFieldLengthNavigationPlanningLinePoints; navFieldLengthNavigationPlanningLinePoints = nullptr;}
        if (reserved1 != nullptr){delete[] reserved1; reserved1 = nullptr;}
        if (reserved2 != nullptr){delete[] reserved2; reserved2 = nullptr;}
        if (reserved3 != nullptr){delete[] reserved3; reserved3 = nullptr;}
        if (reserved4 != nullptr){delete[] reserved4; reserved4 = nullptr;}
        if (reserved5 != nullptr){delete[] reserved5; reserved5 = nullptr;}
    }
}stnewPlanningLineInfo;



//drivingAreaIdentification
typedef struct st_drivingAreaIdentification
{
    uint32_t        checksum;
    uint16_t        counter;
    bool            drivingAreaIdentificationStatus;

    uint32_t        drivingAreaIdentificationPoints_len;
    uint8_t*        drivingAreaIdentificationPoints;

    uint32_t        sizetBevh;
    uint32_t        sizetBevw;
    double          xBoundMin;
    double          xBoundMax;
    double          yBoundMin;
    double          yBoundMax;
    double          meterPerPixelX;
    double          meterPerPixelY;
    double          maskThreshold;

    uint32_t        reservedDataLength1;
    uint8_t*        reserved1;
    uint32_t        reservedDataLength2;
    uint16_t*       reserved2;
    uint32_t        reservedDataLength3;
    uint32_t*       reserved3;
    uint32_t        reservedDataLength4;
    double*         reserved4;
    uint32_t        reservedDataLength5;
    float32*        reserved5;

    st_drivingAreaIdentification()
    {
        drivingAreaIdentificationPoints_len = 0;
        drivingAreaIdentificationPoints = nullptr;
        reservedDataLength1 = reservedDataLength2 = reservedDataLength3 = reservedDataLength4 = reservedDataLength5 = 0;
        reserved1 = nullptr;
        reserved2 = nullptr;
        reserved3 = nullptr;
        reserved4 = nullptr;
        reserved5 = nullptr;
    }     

    st_drivingAreaIdentification(const st_drivingAreaIdentification &other)
    {
        *this = other;
    }

    st_drivingAreaIdentification& operator=(const st_drivingAreaIdentification &other)
    {
        if (drivingAreaIdentificationPoints != nullptr){delete[] drivingAreaIdentificationPoints; drivingAreaIdentificationPoints = nullptr;}
        if (reserved1 != nullptr){delete[] reserved1; reserved1 = nullptr;}
        if (reserved2 != nullptr){delete[] reserved2; reserved2 = nullptr;}
        if (reserved3 != nullptr){delete[] reserved3; reserved3 = nullptr;}
        if (reserved4 != nullptr){delete[] reserved4; reserved4 = nullptr;}
        if (reserved5 != nullptr){delete[] reserved5; reserved5 = nullptr;}
        memset(this, 0, sizeof(st_drivingAreaIdentification));
        memcpy(this, &other, sizeof(st_drivingAreaIdentification));

        if (drivingAreaIdentificationPoints_len >= sizeof(uint8_t))
        {
            drivingAreaIdentificationPoints = new uint8_t[drivingAreaIdentificationPoints_len*sizeof(uint8_t)];
            memset(drivingAreaIdentificationPoints, 0, drivingAreaIdentificationPoints_len);
            memcpy(drivingAreaIdentificationPoints, other.drivingAreaIdentificationPoints, drivingAreaIdentificationPoints_len);
        }

        if (reservedDataLength1 >= sizeof(uint8_t))
        {
            reserved1 = new uint8_t[sizeof(uint8_t)];
            memset(reserved1, 0, reservedDataLength1);
            memcpy(reserved1, other.reserved1, reservedDataLength1);
        }

        if (reservedDataLength2 >= sizeof(uint16_t))
        {
            reserved2 = new uint16_t[sizeof(uint16_t)];
            memset(reserved2, 0, reservedDataLength2);
            memcpy(reserved2, other.reserved1, reservedDataLength2);
        }

        if (reservedDataLength3 >= sizeof(uint32_t))
        {
            reserved3 = new uint32_t[sizeof(uint32_t)];
            memset(reserved3, 0, reservedDataLength3);
            memcpy(reserved3, other.reserved3, reservedDataLength3);
        }

        if (reservedDataLength4 >= sizeof(double))
        {
            reserved4 = new double[sizeof(double)];
            memset(reserved4, 0, reservedDataLength4);
            memcpy(reserved4, other.reserved4, reservedDataLength4);
        }

        if (reservedDataLength5 >= sizeof(float32))
        {
            reserved5 = new float32[sizeof(float32)];
            memset(reserved5, 0, reservedDataLength5);
            memcpy(reserved5, other.reserved5, reservedDataLength5);
        }
        return (*this);
    }

    ~st_drivingAreaIdentification()
    {
        drivingAreaIdentificationPoints_len = 0;
        if (drivingAreaIdentificationPoints != nullptr){delete[] drivingAreaIdentificationPoints; drivingAreaIdentificationPoints = nullptr;}
        if (reserved1 != nullptr){delete[] reserved1; reserved1 = nullptr;}
        if (reserved2 != nullptr){delete[] reserved2; reserved2 = nullptr;}
        if (reserved3 != nullptr){delete[] reserved3; reserved3 = nullptr;}
        if (reserved4 != nullptr){delete[] reserved4; reserved4 = nullptr;}
        if (reserved5 != nullptr){delete[] reserved5; reserved5 = nullptr;}
    }
}stdrivingAreaIdentification;

//23.HPAMapDataNotify
typedef struct st_FieldLength_GlobalTrackPoint_HPAMDN
{
    uint32_t		GlobalTrackPointID_i;
    float32		    x_i;
    float32		    y_i;
    float32		    z_i;
    float32		    Width;
}stFieldLength_GlobalTrackPointHPAMDN;

typedef struct st_BuildMapStartPoint_HPAMDN
{
    float32		    x_start;
    float32		    y_start;
    float32		    z_start;
    float32		    x_stop;
    float32		    y_stop;
    float32		    z_stop;
}stBuildMapStartPointHPAMDN;

typedef struct st_FieldLength_Rampway_HPAMDN
{
    uint32_t		RampwayID_i;
    float32		    x1_i;
    float32		    y1_i;
    float32		    z1_i;
    float32		    x2_i;
    float32		    y2_i;
    float32		    z2_i;
}stFieldLength_RampwayHPAMDN;

typedef struct st_FieldLength_SpeedBumps_HPAMDN
{
    uint32_t	    SpeedBumpsID_i;
    float32		    x_i_Left;
    float32		    y_i_Left;
    float32		    z_i_Left;
    float32		    x_i_Right;
    float32		    y_i_Right;
    float32		    z_i_Right;
    uint32_t        SpeedBumpsWidth;
}stFieldLength_SpeedBumpsHPAMDN;

typedef struct st_FieldLength_UprightColumn_HPAMDN
{
    uint32_t	    UprightColumnID_i;
    float32		    x1_i;
    float32		    y1_i;
    float32		    z1_i;
    float32		    x2_i;
    float32		    y2_i;
    float32		    z2_i;
    float32		    x3_i;
    float32		    y3_i;
    float32		    z3_i;
    float32		    x4_i;
    float32		    y4_i;
    float32		    z4_i;
    float32		    height_i;
}stFieldLength_UprightColumnHPAMDN;

typedef struct st_FieldLength_ParkngSpcI_HPAMDN
{
    uint32_t		ParkngSpcID_i;
    uint8_t		    ParkngSpcSts;
    float32		    x1_i;
    float32		    y1_i;
    float32		    z1_i;
    float32		    x2_i;
    float32		    y2_i;
    float32		    z2_i;
    float32		    x3_i;
    float32		    y3_i;
    float32		    z3_i;
    float32		    x4_i;
    float32		    y4_i;
    float32		    z4_i;
    uint32_t		TargetSlotID;
}stFieldLength_ParkngSpcIHPAMDN;

typedef struct st_HPAMapDataNotify
{
    uint32_t		Checksum;
    uint16_t		Counter;
    double		    timestamp;

    uint32_t        FieldLength_GlobalTrackPoint_len;
    stFieldLength_GlobalTrackPointHPAMDN*    FieldLength_GlobalTrackPoint;
    uint32_t        BuildMapStartPoint_len;
    stBuildMapStartPointHPAMDN* BuildMapStartPoint;
    uint32_t        FieldLength_Rampway_len;
    stFieldLength_RampwayHPAMDN*    FieldLength_Rampway;
    uint32_t        FieldLength_SpeedBumps_len;
    stFieldLength_SpeedBumpsHPAMDN*    FieldLength_SpeedBumps;
    uint32_t        FieldLength_UprightColumn_len;
    stFieldLength_UprightColumnHPAMDN*    FieldLength_UprightColumn;
    uint32_t        FieldLength_ParkngSpcI_len;
    stFieldLength_ParkngSpcIHPAMDN*    FieldLength_ParkngSpcI;

    st_HPAMapDataNotify()
    {
        FieldLength_GlobalTrackPoint_len = BuildMapStartPoint_len = FieldLength_Rampway_len = FieldLength_SpeedBumps_len = FieldLength_UprightColumn_len = FieldLength_ParkngSpcI_len = 0;
        FieldLength_GlobalTrackPoint    = nullptr;
        BuildMapStartPoint              = nullptr;
        FieldLength_Rampway             = nullptr;
        FieldLength_SpeedBumps          = nullptr;
        FieldLength_UprightColumn       = nullptr;
        FieldLength_ParkngSpcI          = nullptr;
    }     

    st_HPAMapDataNotify(const st_HPAMapDataNotify &other)
    {
        *this = other;
    }

    st_HPAMapDataNotify& operator=(const st_HPAMapDataNotify &other)
    {
        if (FieldLength_GlobalTrackPoint != nullptr){delete[] FieldLength_GlobalTrackPoint; FieldLength_GlobalTrackPoint = nullptr;}
        if (BuildMapStartPoint           != nullptr){delete[] BuildMapStartPoint          ; BuildMapStartPoint           = nullptr;}
        if (FieldLength_Rampway          != nullptr){delete[] FieldLength_Rampway         ; FieldLength_Rampway          = nullptr;}
        if (FieldLength_SpeedBumps       != nullptr){delete[] FieldLength_SpeedBumps      ; FieldLength_SpeedBumps       = nullptr;}
        if (FieldLength_UprightColumn    != nullptr){delete[] FieldLength_UprightColumn   ; FieldLength_UprightColumn    = nullptr;}
        if (FieldLength_ParkngSpcI       != nullptr){delete[] FieldLength_ParkngSpcI      ; FieldLength_ParkngSpcI       = nullptr;}
        memset(this, 0, sizeof(st_HPAMapDataNotify));
        memcpy(this, &other, sizeof(st_HPAMapDataNotify));

        if (FieldLength_GlobalTrackPoint_len >= sizeof(stFieldLength_GlobalTrackPointHPAMDN))
        {
            FieldLength_GlobalTrackPoint = new stFieldLength_GlobalTrackPointHPAMDN[sizeof(stFieldLength_GlobalTrackPointHPAMDN)];
            memset(FieldLength_GlobalTrackPoint, 0, FieldLength_GlobalTrackPoint_len);
            memcpy(FieldLength_GlobalTrackPoint, other.FieldLength_GlobalTrackPoint, FieldLength_GlobalTrackPoint_len);
        }

        if (BuildMapStartPoint_len >= sizeof(stBuildMapStartPointHPAMDN))
        {
            BuildMapStartPoint = new stBuildMapStartPointHPAMDN[sizeof(stBuildMapStartPointHPAMDN)];
            memset(BuildMapStartPoint, 0, BuildMapStartPoint_len);
            memcpy(BuildMapStartPoint, other.BuildMapStartPoint, BuildMapStartPoint_len);
        }

        if (FieldLength_Rampway_len >= sizeof(stFieldLength_RampwayHPAMDN))
        {
            FieldLength_Rampway = new stFieldLength_RampwayHPAMDN[sizeof(stFieldLength_RampwayHPAMDN)];
            memset(FieldLength_Rampway, 0, FieldLength_Rampway_len);
            memcpy(FieldLength_Rampway, other.FieldLength_Rampway, FieldLength_Rampway_len);
        }

        if (FieldLength_SpeedBumps_len >= sizeof(stFieldLength_SpeedBumpsHPAMDN))
        {
            FieldLength_SpeedBumps = new stFieldLength_SpeedBumpsHPAMDN[sizeof(stFieldLength_SpeedBumpsHPAMDN)];
            memset(FieldLength_SpeedBumps, 0, FieldLength_SpeedBumps_len);
            memcpy(FieldLength_SpeedBumps, other.FieldLength_SpeedBumps, FieldLength_SpeedBumps_len);
        }

        if (FieldLength_UprightColumn_len >= sizeof(stFieldLength_UprightColumnHPAMDN))
        {
            FieldLength_UprightColumn = new stFieldLength_UprightColumnHPAMDN[sizeof(stFieldLength_UprightColumnHPAMDN)];
            memset(FieldLength_UprightColumn, 0, FieldLength_UprightColumn_len);
            memcpy(FieldLength_UprightColumn, other.FieldLength_UprightColumn, FieldLength_UprightColumn_len);
        }

        if (FieldLength_ParkngSpcI_len >= sizeof(stFieldLength_ParkngSpcIHPAMDN))
        {
            FieldLength_ParkngSpcI = new stFieldLength_ParkngSpcIHPAMDN[sizeof(stFieldLength_ParkngSpcIHPAMDN)];
            memset(FieldLength_ParkngSpcI, 0, FieldLength_ParkngSpcI_len);
            memcpy(FieldLength_ParkngSpcI, other.FieldLength_ParkngSpcI, FieldLength_ParkngSpcI_len);
        }

        return (*this);
    }

    ~st_HPAMapDataNotify()
    {
        if (FieldLength_GlobalTrackPoint != nullptr){delete[] FieldLength_GlobalTrackPoint; FieldLength_GlobalTrackPoint = nullptr;}
        if (BuildMapStartPoint           != nullptr){delete[] BuildMapStartPoint          ; BuildMapStartPoint           = nullptr;}
        if (FieldLength_Rampway          != nullptr){delete[] FieldLength_Rampway         ; FieldLength_Rampway          = nullptr;}
        if (FieldLength_SpeedBumps       != nullptr){delete[] FieldLength_SpeedBumps      ; FieldLength_SpeedBumps       = nullptr;}
        if (FieldLength_UprightColumn    != nullptr){delete[] FieldLength_UprightColumn   ; FieldLength_UprightColumn    = nullptr;}
        if (FieldLength_ParkngSpcI       != nullptr){delete[] FieldLength_ParkngSpcI      ; FieldLength_ParkngSpcI       = nullptr;}
    }
}stHPAMapDataNotify;


// typedef struct st_NavigationStatus_LinkInfoNotify
// {
//     uint32_t                LinkItemInfo_len;
//     stLinkItemInfoNHDLI*    LinkItemInfo;

//     st_NavigationStatus_LinkInfoNotify()
//     {
//         LinkItemInfo_len = 0;
//         LinkItemInfo = nullptr;
//     }

//     st_NavigationStatus_LinkInfoNotify(const st_NavigationStatus_LinkInfoNotify &other)
//     {
//         *this = other;
//     }

//     st_NavigationStatus_LinkInfoNotify& operator=(const st_NavigationStatus_LinkInfoNotify &other)
//     {
//         if (LinkItemInfo != nullptr){delete[] LinkItemInfo; LinkItemInfo = nullptr;}
//         memset(this, 0, sizeof(st_NavigationStatus_LinkInfoNotify));
//         memcpy(this, &other, sizeof(st_NavigationStatus_LinkInfoNotify));

//         if (LinkItemInfo_len >= sizeof(stLinkItemInfoNHDLI))
//         {
//             LinkItemInfo = new stLinkItemInfoNHDLI[LinkItemInfo_len/sizeof(stLinkItemInfoNHDLI)];
//             memset(LinkItemInfo, 0, LinkItemInfo_len);
//             memcpy(LinkItemInfo, other.LinkItemInfo, LinkItemInfo_len);
//         }

//         return (*this);
//     }

//     ~st_NavigationStatus_LinkInfoNotify()
//     {
//         LinkItemInfo_len = 0;
//         if (LinkItemInfo != nullptr){delete[] LinkItemInfo; LinkItemInfo = nullptr;}
//     }
// }stNavigationStatus_LinkInfoNotify;



//HudRoadInfoNotify
typedef struct st_HudRoadInfoNotify
{
    uint32_t    Checksum;
    uint16_t    Counter;
    uint32_t    car_2_dest;
    uint32_t    time_of_car_2_dest;
    uint8_t     Num_of_lanes;
    uint8_t     Current_road_level;
    uint32_t    Permissible_direction_len;
    uint8_t*    Permissible_direction;
    uint32_t    Recommended_driving_directions_for_AJOTP_len;
    uint8_t*    Recommended_driving_directions_for_AJOTP;
    uint32_t    distance_2_intersection;
    string      next_road_name;
    uint8_t     Current_max_speed_limit;
    uint8_t     Current_speed;
    uint16_t    Distance_2_speed_limit_zone;
    uint16_t    length_of_speed_limit;
    uint8_t     speed_limit;
    uint8_t     navigating_status;
    uint8_t     camera_ahead_status;
    uint16_t    The_distance_2_camera;
    float64     vehicle_coordinates_Longitude;
    float64     vehicle_coordinates_Latitude;
    uint8_t     vehicle_speed;
    uint16_t    vehicle_altitude;
    uint8_t     Danger_signs;
    string      POI_information;
    string      reach_the_destination;
    string      ETA_info_time;
    string      ETA_info_remain_time;
    uint16_t    RecommendedDrivingDirectionsId;
    string      lanesPermissibleDirectionId;
    string      guideLine;
    string      guidePoint;
    double      vehicleHeading;
    double      Navigating_ratio;

    st_HudRoadInfoNotify()
    {
        Permissible_direction_len = Recommended_driving_directions_for_AJOTP_len = 0;
        Permissible_direction = Recommended_driving_directions_for_AJOTP = nullptr;
    }     

    st_HudRoadInfoNotify(const st_HudRoadInfoNotify &other)
    {
        *this = other;
    }

    st_HudRoadInfoNotify& operator=(const st_HudRoadInfoNotify &other)
    {
        if (Permissible_direction != nullptr){delete[] Permissible_direction; Permissible_direction = nullptr;}
        if (Recommended_driving_directions_for_AJOTP != nullptr){delete[] Recommended_driving_directions_for_AJOTP; Recommended_driving_directions_for_AJOTP = nullptr;}
        memset(this, 0, sizeof(st_HudRoadInfoNotify));
        memcpy(this, &other, sizeof(st_HudRoadInfoNotify));

        Permissible_direction = new uint8_t[Permissible_direction_len];
        memset(Permissible_direction, 0, Permissible_direction_len);
        memcpy(Permissible_direction, other.Permissible_direction, Permissible_direction_len);

        Recommended_driving_directions_for_AJOTP = new uint8_t[Recommended_driving_directions_for_AJOTP_len];
        memset(Recommended_driving_directions_for_AJOTP, 0, Recommended_driving_directions_for_AJOTP_len);
        memcpy(Recommended_driving_directions_for_AJOTP, other.Recommended_driving_directions_for_AJOTP, Recommended_driving_directions_for_AJOTP_len);

        return (*this);
    }

    ~st_HudRoadInfoNotify()
    {
        Permissible_direction_len = Recommended_driving_directions_for_AJOTP_len = 0;
        if (Permissible_direction != nullptr){delete[] Permissible_direction; Permissible_direction = nullptr;}
        if (Recommended_driving_directions_for_AJOTP != nullptr){delete[] Recommended_driving_directions_for_AJOTP; Recommended_driving_directions_for_AJOTP = nullptr;}
    }
}stHudRoadInfoNotify;



// 海外车型导航信息
typedef struct OSHRinfo {
    uint32_t        Checksum;
    uint16_t        Counter;
    uint32_t        car_2_dest;
    uint32_t        time_of_car_2_dest;
    uint8_t         Num_of_lanes;
    uint8_t         Current_road_level;

    uint32_t        Permissible_direction_len;
    uint8_t*        Permissible_direction;
    uint32_t        Recommended_driving_directions_for_AJOTP_len;
    uint8_t*        Recommended_driving_directions_for_AJOTP;

    uint32_t        distance_2_intersection;
    string          next_road_name;
    uint8_t         Current_max_speed_limit;
    uint8_t         Current_speed;
    uint16_t        Distance_2_speed_limit_zone;
    uint16_t        length_of_speed_limit;
    uint8_t         speed_limit;
    uint8_t         navigating_status;
    uint8_t         camera_ahead_status;
    uint16_t        The_distance_2_camera;
    double          vehicle_coordinates_Longitude;
    double          vehicle_coordinates_Latitude;
    uint8_t         vehicle_speed;
    uint16_t        vehicle_altitude;
    uint8_t         Danger_signs;
    string          POI_information;
    string          reach_the_destination;
    string          ETA_info_time;
    string          ETA_info_remain_time;
    uint16_t        RecommendedDrivingDirectionsId;
    string          lanesPermissibleDirectionId;
    string          guideLine;
    string          guidePoint;
    double          vehicleHeading;
    double          Navigating_ratio;
    uint8_t         mapProviders;
    string          carToDestDistance;
    string          distanceToIntersection;
    string          timeToDest;
    uint16_t        recommendedDrivingDirectionsIdOverseas;

    uint32_t        reservedDataLength1;
    uint8_t*        reserved1;

    uint32_t        reservedDataLength2;
    uint16_t*       reserved2;

    uint32_t        reservedDataLength3;
    uint32_t*       reserved3;

    uint32_t        reservedDataLength4;
    double*         reserved4;

    uint32_t        reservedDataLength5;
    float*          reserved5;
} oshrinfo_t;

//HudMappathInfo_EG
typedef struct st_HudMappathInfo_EG
{
    uint32_t    Checksum;
    uint16_t    Counter;
    uint8_t     is_on_the_path;
    uint8_t     road_angle;
    float32     road_slope;
    string      all_EHP_v2_info;

    st_HudMappathInfo_EG()
    {
    }
}stHudMappathInfo_EG;

//HudNavigationmap
typedef struct st_HudNavigationmap
{
    uint32_t    Navigation_map_len;
    string      Navigation_map;
}stHudNavigationmap;
#pragma pack()

#endif



// //VehiclePositionInfoNotify
// IMUInfoNotify*
// //ObstacleInfoNotify
// //LanelineDataNotify
// NewLanelineDataNotify*
// //ChangeLaneDataNotify
// NewBroadcastInfoNotify*
// PlanningLineInfoNotify*
// NavigationStatus_LinkInfoNotify*
// NewParkingRealTimeDataNotify*
// NavigationHDLink2Info*
// sdTraffiIncident*
// newPlanningLineInfo*
// drivingAreaIdentification*


//14.NewLanelineDataNotify
//15.NewBroadcastInfoNotify
//16.PlanningLineInfoNotify
//17.NavigationStatus_LinkInfoNotify
//18.NewParkingRealTimeDataNotify
//19.NavigationHDLink2Info
//20.sdTraffiIncident
//21.newPlanningLineInfo
//22.drivingAreaIdentification
//23.HPAMapDataNotify