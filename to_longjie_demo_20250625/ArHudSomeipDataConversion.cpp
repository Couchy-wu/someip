/******************************************************************************
*brief:     autosar SOME/IP serialization and deserialization
*version:   1.0
*author:    li.peng89
*time:      2023/06/09
******************************************************************************/

#include "ArHudSomeipDataConversion.h"
#include "CppCommon.h"
#include <stdint.h>
#include <string.h>

void SPStringserialization(string &strIn, char* pcOut, int& n)
{
    uint32_t iLen = 0u;
    sp_big_reverse_copy(strIn.length()+4, pcOut + n, 4);  n += 4;   //4byte   uint32    string length
    *(pcOut + n) = 0xEF;    n += 1; // BOM
    *(pcOut + n) = 0xBB;    n += 1;
    *(pcOut + n) = 0xBF;    n += 1;
    memcpy(pcOut + n, (void*)strIn.c_str(), strIn.length()+1);    n += strIn.length() + 1;   //4byte   uint32    string data
}

void SPStringDeserialization(const char* pcIn, string &strOut, int& n)
{
    if(pcIn == nullptr) 
        return;

    int iBom = 0;
    uint32_t iLen = 0u;
    const uint8_t* ppcIn = (const uint8_t*)pcIn;

    strOut.clear();
    if (ppcIn[n+2]==0xef && ppcIn[n+3]==0xbb && ppcIn[n+4]==0xbf)       //兼容旧的2字节长度
    {
        uint16_t tilen = 0u;
        big_reverse_copy((const char*)(ppcIn + n), tilen);      n += 2;
        iLen = tilen;
        iBom = 1;
    }
    else if (ppcIn[n+4]==0xef && ppcIn[n+5]==0xbb && ppcIn[n+6]==0xbf) //4字节长度
    {
        big_reverse_copy((const char*)(ppcIn + n),  iLen);      n += 4;
        iBom = 2;
    }
    if (iBom == 0)
    {
        return;
    }
    
    if (iLen > 3)
    {
        char* ptemp = new char[iLen - 3]; // BOM EF BB BF
        memset(ptemp, 0, iLen - 3);
        memcpy(ptemp, ppcIn + n + 3, iLen - 3);
        strOut.assign(ptemp);
        if (ptemp != nullptr)
        {
            delete[] ptemp;
            ptemp = nullptr;
        }
        n += iLen;
    }
}

// Serialization
void VehiclePositionInfoNotifySerialization(std::shared_ptr<stVehiclePositionInfoNotify> pIn, char* pcOut)
{
    int n = 0, count = 0;
    sp_big_reverse_copy(pIn->Checksum                           ,pcOut + n, 4);      n += 4;    //4byte   uint32  Checksum
    sp_big_reverse_copy(pIn->Counter                            ,pcOut + n, 2);      n += 2;    //2byte   uint16  Counter
    sp_big_reverse_copy(pIn->Longitude                          ,pcOut + n, 8);      n += 8;    //8byte   double  Longitude
    sp_big_reverse_copy(pIn->Latitude                           ,pcOut + n, 8);      n += 8;    //8byte   double  Latitude
    sp_big_reverse_copy(pIn->altitude                           ,pcOut + n, 8);      n += 8;    //8byte   double  altitude
    sp_big_reverse_copy(pIn->Heading                            ,pcOut + n, 8);      n += 8;    //8byte   double  Heading
    sp_big_reverse_copy(pIn->hd_lane_left_angle                 ,pcOut + n, 8);      n += 8;    //8byte   double  hd_lane_left_angle
    sp_big_reverse_copy(pIn->Hd_lane_right_angle                ,pcOut + n, 8);      n += 8;    //8byte   double  Hd_lane_right_angle
    sp_big_reverse_copy(pIn->VehicleSpeed                       ,pcOut + n, 8);      n += 8;    //8byte   double  VehicleSpeed
    sp_big_reverse_copy(pIn->acceleration                       ,pcOut + n, 8);      n += 8;    //8byte   double  acceleration
    sp_big_reverse_copy(pIn->x_speed                            ,pcOut + n, 8);      n += 8;    //8byte   double  x_speed
    sp_big_reverse_copy(pIn->y_speed                            ,pcOut + n, 8);      n += 8;    //8byte   double  y_speed
    sp_big_reverse_copy(pIn->z_speed                            ,pcOut + n, 8);      n += 8;    //8byte   double  z_speed
    sp_big_reverse_copy(pIn->timestamp                          ,pcOut + n, 8);      n += 8;    //8byte   double  timestamp
    sp_big_reverse_copy(pIn->hd_link_id                         ,pcOut + n, 4);      n += 4;    //4byte   uint32  hd_link_id
    sp_big_reverse_copy(pIn->hd_lane_id                         ,pcOut + n, 4);      n += 4;    //4byte   uint32  hd_lane_id
    sp_big_reverse_copy(pIn->hd_lane_type                       ,pcOut + n, 4);      n += 4;    //4byte   uInt32  hd_lane_type
    sp_big_reverse_copy(pIn->on_lane_offset                     ,pcOut + n, 8);      n += 8;    //8byte   double  on_lane_offset
    sp_big_reverse_copy(pIn->hd_lane_seq                        ,pcOut + n, 4);      n += 4;    //4byte   uint32  hd_lane_seq
    sp_big_reverse_copy(pIn->hd_lane_num                        ,pcOut + n, 4);      n += 4;    //4byte   uint32  hd_lane_num
    sp_big_reverse_copy(pIn->hd_lane_left_lateral_offset        ,pcOut + n, 8);      n += 8;    //8byte   double  hd_lane_left_lateral_offset
    sp_big_reverse_copy(pIn->hd_lane_right_lateral_offset       ,pcOut + n, 8);      n += 8;    //8byte   double  hd_lane_right_lateral_offset
    sp_big_reverse_copy(pIn->roll                               ,pcOut + n, 8);      n += 8;    //8byte   double  roll
    sp_big_reverse_copy(pIn->pitch                              ,pcOut + n, 8);      n += 8;    //8byte   double  pitch
    sp_big_reverse_copy(pIn->HdStatus                           ,pcOut + n, 1);      n += 1;    //1byte   uint8   HdStatus
    sp_big_reverse_copy(pIn->hdmap_version                      ,pcOut + n, 1);      n += 1;    //1byte   uint8   hdmap_version
    sp_big_reverse_copy(pIn->fusion_status                      ,pcOut + n, 1);      n += 1;    //1byte   uint8   fusion_status
    sp_big_reverse_copy(pIn->pos_confidence                     ,pcOut + n, 8);      n += 8;    //8byte   double  pos_confidence
    sp_big_reverse_copy(pIn->position_type                      ,pcOut + n, 1);      n += 1;    //1byte   uint8   position_type
    sp_big_reverse_copy(pIn->break_light                        ,pcOut + n, 1);      n += 1;    //1byte   uint8   break_light
    sp_big_reverse_copy(pIn->indicator_light                    ,pcOut + n, 1);      n += 1;    //1byte   uint8   indicator_light
    sp_big_reverse_copy(pIn->Lights                             ,pcOut + n, 1);      n += 1;    //1byte   uint8   Lights
    sp_big_reverse_copy(pIn->Weather                            ,pcOut + n, 1);      n += 1;    //1byte   uint8   Weather
    sp_big_reverse_copy(pIn->target_cruise_speed                ,pcOut + n, 4);      n += 4;    //4byte   float   target_cruise_speed
    sp_big_reverse_copy(pIn->FieldLength_target_lane            ,pcOut + n, 4);      n += 4;    //4byte   uint32  FieldLength_target_lane
    count = pIn->FieldLength_target_lane /4;//sizeof(uint32_t);
    for (int i = 0; i < count; ++i)
    {
         sp_big_reverse_copy(pIn->target_lane_id[i]             ,pcOut + n, 4);      n += 4;    //4byte   uint32  target_lane_id
    }

    sp_big_reverse_copy(pIn->FieldLength_target_lane_id_segment ,pcOut + n, 4);      n += 4;   //4byte   uint32  FieldLength_target_lane_id_segment
    count = pIn->FieldLength_target_lane_id_segment /4;//sizeof(uint32_t);
    for (int i = 0; i < count; ++i)
    {
         sp_big_reverse_copy(pIn->target_lane_id_segment[i]     ,pcOut + n, 4);      n += 4;   //4byte   uint32  target_lane_id
    }
    sp_big_reverse_copy(pIn->localization_output_offset         ,pcOut + n, 1);      n += 1;   //1byte   uint8   localization_output_offset
}

// RTKInfoNotify
 void RTKInfoNotifySerialization(std::shared_ptr<stRTKInfoNotify> pIn, char* pcOut)
 {
    int n = 0;
    sp_big_reverse_copy(pIn->Checksum             ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum  
    sp_big_reverse_copy(pIn->Counter              ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter  
    sp_big_reverse_copy(pIn->rtk_status               ,pcOut + n, 4);      n += 4;   //4byte   uint32    rtk_status  
    sp_big_reverse_copy(pIn->utc_time_us              ,pcOut + n, 8);      n += 8;   //8byte   float64   utc_time_us  
    sp_big_reverse_copy(pIn->sys_time_us          ,pcOut + n, 8);      n += 8;   //8byte   float64   sys_time_us  
    sp_big_reverse_copy(pIn->longitude               ,pcOut + n, 8);      n += 8;   //8byte   float64   longitude  
    sp_big_reverse_copy(pIn->latitude                ,pcOut + n, 8);      n += 8;   //8byte   float64   latitude  
    sp_big_reverse_copy(pIn->altitude                ,pcOut + n, 8);      n += 8;   //8byte   float64   altitude  
    sp_big_reverse_copy(pIn->longitude_acc           ,pcOut + n, 8);      n += 8;   //8byte   float64   longitude_acc  
    sp_big_reverse_copy(pIn->latitude_acc            ,pcOut + n, 8);      n += 8;   //8byte   float64   latitude_acc  
    sp_big_reverse_copy(pIn->altitude_acc            ,pcOut + n, 8);      n += 8;   //8byte   float64   altitude_acc  
    sp_big_reverse_copy(pIn->heading_move             ,pcOut + n, 8);      n += 8;   //8byte   float64   heading_move  
    sp_big_reverse_copy(pIn->heading_double_ant       ,pcOut + n, 8);      n += 8;   //8byte   float64   heading_double_ant  
    sp_big_reverse_copy(pIn->heading_move_acc         ,pcOut + n, 8);      n += 8;   //8byte   float64   heading_move_acc  
    sp_big_reverse_copy(pIn->speed_2d                 ,pcOut + n, 8);      n += 8;   //8byte   float64   speed_2d  
    sp_big_reverse_copy(pIn->speed_acc                ,pcOut + n, 8);      n += 8;   //8byte   float64   speed_acc  
    sp_big_reverse_copy(pIn->speed_n                  ,pcOut + n, 8);      n += 8;   //8byte   float64   speed_n  
    sp_big_reverse_copy(pIn->speed_e                  ,pcOut + n, 8);      n += 8;   //8byte   float64   speed_e  
    sp_big_reverse_copy(pIn->speed_u                  ,pcOut + n, 8);      n += 8;   //8byte   float64   speed_u  
    sp_big_reverse_copy(pIn->g_dop                    ,pcOut + n, 8);      n += 8;   //8byte   float64   g_dop  
    sp_big_reverse_copy(pIn->h_dop                    ,pcOut + n, 8);      n += 8;   //8byte   float64   h_dop  
    sp_big_reverse_copy(pIn->v_dop                    ,pcOut + n, 8);      n += 8;   //8byte   float64   v_dop  
    sp_big_reverse_copy(pIn->satellite_num            ,pcOut + n, 4);      n += 4;   //4byte   uint32    satellite_num  
    sp_big_reverse_copy(pIn->satellite_used           ,pcOut + n, 4);      n += 4;   //4byte   uint32    satellite_used  
    sp_big_reverse_copy(pIn->snr_max                  ,pcOut + n, 8);      n += 8;   //8byte   float64   snr_max  
    sp_big_reverse_copy(pIn->snr_mix                  ,pcOut + n, 8);      n += 8;   //8byte   float64   snr_mix  
    sp_big_reverse_copy(pIn->snr_avr                  ,pcOut + n, 8);      n += 8;   //8byte   float64   snr_avr      
 }

 // IMUInfoNotify
void IMUInfoNotifySerialization(std::shared_ptr<stIMUInfoNotify> pIn, char* pcOut)
{
    int n = 0;
    sp_big_reverse_copy(pIn->Checksum                         ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum
    sp_big_reverse_copy(pIn->Counter                          ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter
    sp_big_reverse_copy(pIn->angular_velocity_x               ,pcOut + n, 8);      n += 8;   //8byte   double    angular_velocity_x
    sp_big_reverse_copy(pIn->angular_velocity_y               ,pcOut + n, 8);      n += 8;   //8byte   double    angular_velocity_y
    sp_big_reverse_copy(pIn->angular_velocity_z               ,pcOut + n, 8);      n += 8;   //8byte   double    angular_velocity_z  
    sp_big_reverse_copy(pIn->acc_speed_x                      ,pcOut + n, 8);      n += 8;   //8byte   double    acc_speed_x
    sp_big_reverse_copy(pIn->acc_speed_y                      ,pcOut + n, 8);      n += 8;   //8byte   double    acc_speed_y
    sp_big_reverse_copy(pIn->acc_speed_z                      ,pcOut + n, 8);      n += 8;   //8byte   double    acc_speed_z
    sp_big_reverse_copy(pIn->IMU_status                       ,pcOut + n, 1);      n += 1;   //1byte   uint8     IMU_status
    sp_big_reverse_copy(pIn->IMU_current_temperature          ,pcOut + n, 8);      n += 8;   //8byte   double    IMU current temperature
    sp_big_reverse_copy(pIn->sys_time_us                      ,pcOut + n, 8);      n += 8;   //8byte   double    sys_time_us
    sp_big_reverse_copy(pIn->is_calibrated                    ,pcOut + n, 1);      n += 1;   //1byte   bool      is_calibrated
}

// ObstacleInfoNotify
void ObstacleInfoNotifySerialization(std::shared_ptr<stObstacleInfoNotify> pIn, char* pcOut)
{
    int n = 0, count = 0;
    sp_big_reverse_copy(pIn->Checksum                 ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum
    sp_big_reverse_copy(pIn->Counter                  ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter
    sp_big_reverse_copy(pIn->target_flag              ,pcOut + n, 1);      n += 1;   //1byte   bool      target_flag
    sp_big_reverse_copy(pIn->FieldLength_Object_len   ,pcOut + n, 4);      n += 4;   //4byte   uint32    FieldLength_Object
    if (pIn->FieldLength_Object_len > 0)
    {
        count = pIn->FieldLength_Object_len / 97;//sizeof(stObstacleInfoNotifyFLO);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->ObstacleType                    ,pcOut + n, 4);      n += 4;   //4byte   uint32    ObstacleType
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->confidence                      ,pcOut + n, 8);      n += 8;   //8byte   double    confidence
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->Obstacle_Id_i                   ,pcOut + n, 4);      n += 4;   //4byte   uint32    Obstacle Id_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->ObstacleDistance_X_i            ,pcOut + n, 8);      n += 8;   //8byte   double    ObstacleDistance_X_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->ObstacleDistance_Y_i            ,pcOut + n, 8);      n += 8;   //8byte   double    ObstacleDistance_Y_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->ObstacleDistance_Z_i            ,pcOut + n, 8);      n += 8;   //8byte   double    ObstacleDistance_Z_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->Bounding_box_length_i           ,pcOut + n, 4);      n += 4;   //4byte   float     Bounding_box_length_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->Bounding_box_width_i            ,pcOut + n, 4);      n += 4;   //4byte   float     Bounding_box_width_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->Bounding_box_height_i           ,pcOut + n, 4);      n += 4;   //4byte   float     Bounding_box_height_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->break_light                     ,pcOut + n, 1);      n += 1;   //1byte   uint8     break_light
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->indicator_light                 ,pcOut + n, 1);      n += 1;   //1byte   uint8     indicator_light
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->obj_speed                       ,pcOut + n, 8);      n += 8;   //8byte   double    obj_speed
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->ObstacleState                   ,pcOut + n, 1);      n += 1;   //1byte   uint8     ObstacleState
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->obstacle_timestamp              ,pcOut + n, 8);      n += 8;   //8byte   double    obstacle_timestamp
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->obstacle_camera_timestamp       ,pcOut + n, 8);      n += 8;   //8byte   double    obstacle_camera_timestamp
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->moving                          ,pcOut + n, 1);      n += 1;   //1byte   bool      moving
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->obj_heading                     ,pcOut + n, 8);      n += 8;   //8byte   double    obj_heading
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->Obj_direction                   ,pcOut + n, 8);      n += 8;   //8byte   double    Obj_direction
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->ObstacleWarningBrakeState       ,pcOut + n, 1);      n += 1;   //1byte   uint8     ObstacleWarningBrakeState
        }
    }
}

// LanelineDataNotify
void LanelineDataNotifySerialization(std::shared_ptr<stLanelineDataNotify> pIn, char* pcOut)
{
    int n = 0, count = 0;
    sp_big_reverse_copy(pIn->Checksum                          ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum
    sp_big_reverse_copy(pIn->Counter                           ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter
    sp_big_reverse_copy(pIn->FieldLength_Line_len              ,pcOut + n, 4);      n += 4;   //4byte   uint32    FieldLength_Line
    if (pIn->FieldLength_Line_len > 0)
    {
        count = pIn->FieldLength_Line_len / 66;
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->LineID                     ,pcOut + n, 4);      n += 4;   //4byte   int32   LineID
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->LineType                   ,pcOut + n, 1);      n += 1;   //1byte   uint8   LineType
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->LineColor                  ,pcOut + n, 1);      n += 1;   //1byte   uint8   LineColor
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->LineWidth                  ,pcOut + n, 4);      n += 4;   //4byte   float   LineWidth
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_confidence            ,pcOut + n, 8);      n += 8;   //8byte   double  Line_confidence
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->CurvatureEquation_c0       ,pcOut + n, 4);      n += 4;   //4byte   float   CurvatureEquation_c0
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->CurvatureEquation_c1       ,pcOut + n, 4);      n += 4;   //4byte   float   CurvatureEquation_c1
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->CurvatureEquation_c2       ,pcOut + n, 4);      n += 4;   //4byte   float   CurvatureEquation_c2
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->CurvatureEquation_c3       ,pcOut + n, 4);      n += 4;   //4byte   float   CurvatureEquation_c3
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Startpoint_x          ,pcOut + n, 4);      n += 4;   //4byte   float   Line_Startpoint_x
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Startpoint_y          ,pcOut + n, 4);      n += 4;   //4byte   float   Line_Startpoint_y
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Startpoint_z          ,pcOut + n, 4);      n += 4;   //4byte   float   Line_Startpoint_z
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Endpoint_x            ,pcOut + n, 4);      n += 4;   //4byte   float   Line_Endpoint_x
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Endpoint_y            ,pcOut + n, 4);      n += 4;   //4byte   float   Line_Endpoint_y
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Endpoint_z            ,pcOut + n, 4);      n += 4;   //4byte   float   Line_Endpoint_z
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->sys_time_us                ,pcOut + n, 8);      n += 8;   //8byte   double  sys_time_us
        }
    }

    sp_big_reverse_copy(pIn->FieldLength_RoadMarking_len    ,pcOut + n, 4);         n += 4;   //4byte   uint32    FieldLength_Line
    if (pIn->FieldLength_RoadMarking_len > 0)
    {
        count = pIn->FieldLength_RoadMarking_len / 57;
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarkingID_i                      ,pcOut + n, 4);      n += 4;   //4byte   uint32  RoadMarkingID_i
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarkingType_i                    ,pcOut + n, 1);      n += 1;   //1byte   uint8   RoadMarkingType_i
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarkingType_confidence_i         ,pcOut + n, 8);      n += 8;   //8byte   double  RoadMarkingType_confidence_i
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarking_length_i                 ,pcOut + n, 4);      n += 4;   //4byte   float   RoadMarking_length_i
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarking_width_i                  ,pcOut + n, 4);      n += 4;   //4byte   float   RoadMarking_width_i
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarking_height_i                 ,pcOut + n, 4);      n += 4;   //4byte   float   RoadMarking_height_i
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarking_Distance_X_i             ,pcOut + n, 8);      n += 8;   //8byte   double  RoadMarking_Distance_X_i
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarking_Distance_Y_i             ,pcOut + n, 8);      n += 8;   //8byte   double  RoadMarking_Distance_Y_i
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarking_Distance_Z_i             ,pcOut + n, 8);      n += 8;   //8byte   double  RoadMarking_Distance_Z_i
            sp_big_reverse_copy((pIn->FieldLength_RoadMarking+i)->RoadMarkingPosition_confidence       ,pcOut + n, 8);      n += 8;   //8byte   double  RoadMarkingPosition_confidence
        }
    }

    sp_big_reverse_copy(pIn->FieldLength_TLA_len    ,pcOut + n, 4);         n += 4;   //4byte   uint32    FieldLength_TLA_len
    if (pIn->FieldLength_TLA_len > 0)
    {
        count = pIn->FieldLength_TLA_len / 42;
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLAID_i                      ,pcOut + n, 4);      n += 4;   //4byte   uint32  TLAID_i
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Distance_X               ,pcOut + n, 8);      n += 8;   //8byte   double  TLA_Distance_X
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Distance_Y               ,pcOut + n, 8);      n += 8;   //8byte   double  TLA_Distance_Y
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Distance_Z               ,pcOut + n, 8);      n += 8;   //8byte   double  TLA_Distance_Z
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLAPosition_confidence       ,pcOut + n, 8);      n += 8;   //8byte   double  TLAPosition_confidence
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->LeftTLA_Color                ,pcOut + n, 1);      n += 1;   //1byte   uint8   LeftTLA_Color
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->LeftTLA_Type                 ,pcOut + n, 1);      n += 1;   //1byte   uint8   LeftTLA_Type
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->StraightTLA_Color            ,pcOut + n, 1);      n += 1;   //1byte   uint8   StraightTLA_Color
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->StraightTLA_Type             ,pcOut + n, 1);      n += 1;   //1byte   uint8   StraightTLA_Type
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->RightTLA_Color               ,pcOut + n, 1);      n += 1;   //1byte   uint8   RightTLA_Color
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->RightTLA_Type                ,pcOut + n, 1);      n += 1;   //1byte   uint8   RightTLA_Type
        }
    }
}

// ChangeLaneDataNotify
 void ChangeLaneDataNotifySerialization(std::shared_ptr<stChangeLaneDataNotify> pIn, char* pcOut)
 {
    int n = 0;
    sp_big_reverse_copy(pIn->Checksum                   ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum
    sp_big_reverse_copy(pIn->Counter                    ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter
    sp_big_reverse_copy(pIn->ChangeLaneState            ,pcOut + n, 4);      n += 4;   //4byte   uint32    ChangeLaneState
    sp_big_reverse_copy(pIn->ChangeLaneDirection        ,pcOut + n, 1);      n += 1;   //1byte   uint8     ChangeLaneDirection
    sp_big_reverse_copy(pIn->is_change_safety           ,pcOut + n, 1);      n += 1;   //1byte   bool      is_change_safety
    sp_big_reverse_copy(pIn->ChangeLane_timestamp       ,pcOut + n, 4);      n += 4;   //4byte   uint32    ChangeLane_timestamp
    sp_big_reverse_copy(pIn->change_ratio               ,pcOut + n, 8);      n += 8;   //8byte   double    change_ratio
    sp_big_reverse_copy(pIn->change_termi               ,pcOut + n, 4);      n += 4;   //4byte   uint32    change_termi
    sp_big_reverse_copy(pIn->landing_center_X           ,pcOut + n, 8);      n += 8;   //8byte   double    landing_center_X
    sp_big_reverse_copy(pIn->landing_center_Y           ,pcOut + n, 8);      n += 8;   //8byte   double    landing_center_Y
    sp_big_reverse_copy(pIn->landing_center_Z           ,pcOut + n, 8);      n += 8;   //8byte   double    landing_center_Z
    sp_big_reverse_copy(pIn->landing_box_length         ,pcOut + n, 8);      n += 8;   //8byte   double    landing_box_length
    sp_big_reverse_copy(pIn->landing_box__width         ,pcOut + n, 8);      n += 8;   //8byte   double    landing_box__width
    sp_big_reverse_copy(pIn->landing_box_height         ,pcOut + n, 8);      n += 8;   //8byte   double    landing_box_height
 }

// PilotStatusNotify
void PilotStatusNotifySerialization(std::shared_ptr<stPilotStatusNotify> pIn, char* pcOut)
{
    int n = 0;
    sp_big_reverse_copy(pIn->Checksum             ,pcOut + n, 4);      n += 4;   //4byte    uint32   Checksum
    sp_big_reverse_copy(pIn->Counter              ,pcOut + n, 2);      n += 2;   //2byte    uint16   Counter
    sp_big_reverse_copy(pIn->ACCStatus            ,pcOut + n, 1);      n += 1;   //1byte    uint8    ACCStatus
    sp_big_reverse_copy(pIn->ICCStatus            ,pcOut + n, 1);      n += 1;   //1byte    uint8    ICCStatus
    sp_big_reverse_copy(pIn->DNPStatus            ,pcOut + n, 1);      n += 1;   //1byte    uint8    DNPStatus
    sp_big_reverse_copy(pIn->TakeoverStatus       ,pcOut + n, 1);      n += 1;   //1byte    bool     TakeoverStatus
    sp_big_reverse_copy(pIn->driving_time         ,pcOut + n, 4);      n += 4;   //4byte    uint32   driving_time
}

// PilotAlarmAndNoticeInfoNotify
void PilotAlarmAndNoticeInfoNotifySerialization(std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> pIn, char* pcOut)
{
    int n = 0;
    sp_big_reverse_copy(pIn->Checksum               ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum
    sp_big_reverse_copy(pIn->Counter                ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter
    sp_big_reverse_copy(pIn->PilotAlarmReason       ,pcOut + n, 4);      n += 4;   //4byte   uint32    PilotAlarmReason
    sp_big_reverse_copy(pIn->alarm_distance         ,pcOut + n, 4);      n += 4;   //4byte   uint32    alarm_distance
    sp_big_reverse_copy(pIn->alarm_stage            ,pcOut + n, 4);      n += 4;   //4byte   uint32    alarm_stage
    sp_big_reverse_copy(pIn->alarm_timestamp        ,pcOut + n, 8);      n += 8;   //8byte   double    alarm_timestamp
    sp_big_reverse_copy(pIn->PilotNotice            ,pcOut + n, 4);      n += 4;   //4byte   uint32    PilotNotice
    sp_big_reverse_copy(pIn->notice_distance        ,pcOut + n, 4);      n += 4;   //4byte   uint32    notice_distance
    sp_big_reverse_copy(pIn->notice_timestamp       ,pcOut + n, 8);      n += 8;   //8byte   double    notice_timestamp
}

// BroadcastInfoNotify
void BroadcastInfoNotifySerialization(std::shared_ptr<stBroadcastInfoNotify> pIn, char* pcOut)
{
    int n = 0;
    sp_big_reverse_copy(pIn->Checksum                ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum
    sp_big_reverse_copy(pIn->Counter                 ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter
    sp_big_reverse_copy(pIn->driver_attention        ,pcOut + n, 1);      n += 1;   //1byte   bool      target_flag
    sp_big_reverse_copy(pIn->large_vehicles          ,pcOut + n, 1);      n += 1;   //1byte   bool      FieldLength_Object
    sp_big_reverse_copy(pIn->dangerous_vehicle       ,pcOut + n, 1);      n += 1;   //1byte   bool      ObstacleType
    sp_big_reverse_copy(pIn->pedestrians             ,pcOut + n, 1);      n += 1;   //1byte   bool      confidence
}

// // PlanningLineInfoNotify
// void PlanningLineInfoNotifySerialization(std::shared_ptr<stPlanningLineInfoNotify> pIn, char* pcOut)
// {
//     int n = 0, count = 0;
//     sp_big_reverse_copy(pIn->Checksum                                 ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum
//     sp_big_reverse_copy(pIn->Counter                                  ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter
//     sp_big_reverse_copy(pIn->PlanningLineStatus                       ,pcOut + n, 1);      n += 1;   //1byte   bool      PlanningLineStatus
//     sp_big_reverse_copy(pIn->planning_timestamp                       ,pcOut + n, 8);      n += 8;   //8byte   double    planning_timestamp
//     sp_big_reverse_copy(pIn->FieldLength_PlanningLinePoints_len       ,pcOut + n, 4);      n += 4;   //4byte   uint32    FieldLength_PlanningLinePoints

//     if (pIn->FieldLength_PlanningLinePoints_len > 0)
//     {
//         count = pIn->FieldLength_PlanningLinePoints_len / 28;//sizeof(stPlanningLineInfoNotifyFPLP);
//         for (int i = 0; i < count; ++i)
//         {
//             sp_big_reverse_copy((pIn->FieldLength_PlanningLinePoints+i)->PlanningLinePointsID_i       ,pcOut + n, 4);      n += 4;     //4byte   uint32  target_lane_id
//             sp_big_reverse_copy((pIn->FieldLength_PlanningLinePoints+i)->points_X                     ,pcOut + n, 8);      n += 8;     //8byte   double  points_X
//             sp_big_reverse_copy((pIn->FieldLength_PlanningLinePoints+i)->points_Y                     ,pcOut + n, 8);      n += 8;     //8byte   double  points_Y
//             sp_big_reverse_copy((pIn->FieldLength_PlanningLinePoints+i)->points_Z                     ,pcOut + n, 8);      n += 8;     //8byte   double  points_Z
//         }
//     }
// }

// HudRoadInfoNotify
void HudRoadInfoNotifySerialization(std::shared_ptr<stHudRoadInfoNotify> pIn, char* pcOut)
{
    int n = 0, count = 0;
    sp_big_reverse_copy(pIn->Checksum                        ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum
    sp_big_reverse_copy(pIn->Counter                         ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter
    sp_big_reverse_copy(pIn->car_2_dest                      ,pcOut + n, 4);      n += 4;   //4byte   uint32    car_2_dest
    sp_big_reverse_copy(pIn->time_of_car_2_dest              ,pcOut + n, 4);      n += 4;   //4byte   uint32    time_of_car_2_dest
    sp_big_reverse_copy(pIn->Num_of_lanes                    ,pcOut + n, 1);      n += 1;   //1byte   uint8     Num_of_lanes
    sp_big_reverse_copy(pIn->Current_road_level              ,pcOut + n, 1);      n += 1;   //1byte   uint8     Current_road_level
    sp_big_reverse_copy(pIn->Permissible_direction_len       ,pcOut + n, 4);      n += 4;   //4byte   uint32    Permissible_direction_len
    if (pIn->Permissible_direction_len > 0)
    {
        count = pIn->Permissible_direction_len / 1;//sizeof(uint8_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy(*(pIn->Permissible_direction+i),pcOut + n, 1);      n += 1;    //1byte    uint8    Permissible_direction
        }
        if (pIn->Permissible_direction != nullptr)
        {
            delete[] pIn->Permissible_direction;
            pIn->Permissible_direction = nullptr;
        }
    }
    sp_big_reverse_copy(pIn->Recommended_driving_directions_for_AJOTP_len,pcOut + n, 4);   n += 4;   //4byte   uint32    Recommended_driving_directions_for_AJOTP_len
    if (pIn->Recommended_driving_directions_for_AJOTP_len > 0)
    {
        count = pIn->Recommended_driving_directions_for_AJOTP_len / 1;//sizeof(uint8_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy(pIn->Recommended_driving_directions_for_AJOTP+i,pcOut + n, 1);      n += 1;    //1byte    uint8    Recommended_driving_directions_for_AJOTP
        }
        if (pIn->Recommended_driving_directions_for_AJOTP != nullptr)
        {
            delete[] pIn->Recommended_driving_directions_for_AJOTP;
            pIn->Recommended_driving_directions_for_AJOTP = nullptr;
        }
    }
    sp_big_reverse_copy(pIn->distance_2_intersection,pcOut + n, 4);   n += 4;   //4byte   uint32    distance_2_intersection
    SPStringserialization(pIn->next_road_name, pcOut, n);                   //        string    next_road_name
    sp_big_reverse_copy(pIn->Current_max_speed_limit             ,pcOut + n, 1);      n += 1;   //1byte   uint8     Current_max_speed_limit
    sp_big_reverse_copy(pIn->Current_speed                       ,pcOut + n, 1);      n += 1;   //1byte   uint8     Current_speed
    sp_big_reverse_copy(pIn->Distance_2_speed_limit_zone         ,pcOut + n, 2);      n += 2;   //2byte   uint16    Distance_2_speed_limit_zone
    sp_big_reverse_copy(pIn->length_of_speed_limit               ,pcOut + n, 2);      n += 2;   //2byte   uint16    length_of_speed_limit
    sp_big_reverse_copy(pIn->speed_limit                         ,pcOut + n, 1);      n += 1;   //1byte   uint8     speed_limit
    sp_big_reverse_copy(pIn->navigating_status                   ,pcOut + n, 1);      n += 1;   //1byte   uint8     navigating_status
    sp_big_reverse_copy(pIn->camera_ahead_status                 ,pcOut + n, 1);      n += 1;   //1byte   uint8     camera_ahead_status
    sp_big_reverse_copy(pIn->The_distance_2_camera               ,pcOut + n, 2);      n += 2;   //2byte   uint16    The_distance_2_camera
    sp_big_reverse_copy(pIn->vehicle_coordinates_Longitude       ,pcOut + n, 8);      n += 8;   //8byte   float64   vehicle_coordinates_Longitude
    sp_big_reverse_copy(pIn->vehicle_coordinates_Latitude        ,pcOut + n, 8);      n += 8;   //8byte   float64   vehicle_coordinates_Latitude
    sp_big_reverse_copy(pIn->vehicle_speed                       ,pcOut + n, 1);      n += 1;   //1byte   uint8     vehicle_speed
    sp_big_reverse_copy(pIn->vehicle_altitude                    ,pcOut + n, 2);      n += 2;   //2byte   uint16    vehicle_altitude
    sp_big_reverse_copy(pIn->Danger_signs                        ,pcOut + n, 1);      n += 1;   //1byte   uint8     Danger_signs
    SPStringserialization(pIn->POI_information, pcOut, n);                  //        string    POI_information
    SPStringserialization(pIn->reach_the_destination, pcOut, n);            //        string    reach_the_destination
    SPStringserialization(pIn->ETA_info_time, pcOut, n);                    //        string    ETA_info_time
    SPStringserialization(pIn->ETA_info_remain_time, pcOut, n);             //        string    ETA_info_remain_time
    sp_big_reverse_copy(pIn->RecommendedDrivingDirectionsId,pcOut + n, 2);   n += 2;  //2byte   uint16    RecommendedDrivingDirectionsId
    SPStringserialization(pIn->lanesPermissibleDirectionId, pcOut, n);      //        string    lanesPermissibleDirectionId
    SPStringserialization(pIn->guideLine, pcOut, n);                        //        string    guideLine
    SPStringserialization(pIn->guidePoint, pcOut, n);                       //        string    guidePoint
    sp_big_reverse_copy(pIn->vehicleHeading                     ,pcOut + n, 8);      n += 8;   //8byte   double    vehicleHeading
    sp_big_reverse_copy(pIn->Navigating_ratio                   ,pcOut + n, 8);      n += 8;   //8byte   double    Navigating_ratio
}


// OverseasHudRoadInfoNotify
void OverseasHudRoadInfoNotifySerialization(std::shared_ptr<oshrinfo_t> pIn, char* pcOut)
{
    int n = 0, count = 0;

    sp_big_reverse_copy(pIn->Checksum           ,pcOut + n, 4);      n += 4;   //4byte    uint32_t        Checksum
    sp_big_reverse_copy(pIn->Counter            ,pcOut + n, 2);      n += 2;   //2byte    uint16_t        Counter
    sp_big_reverse_copy(pIn->car_2_dest         ,pcOut + n, 4);      n += 4;   //4byte    uint32_t        car_2_dest
    sp_big_reverse_copy(pIn->time_of_car_2_dest ,pcOut + n, 4);      n += 4;   //4byte    uint32_t        time_of_car_2_dest
    sp_big_reverse_copy(pIn->Num_of_lanes       ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         Num_of_lanes
    sp_big_reverse_copy(pIn->Current_road_level ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         Current_road_level
    
    sp_big_reverse_copy(pIn->Permissible_direction_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     Permissible_direction_len
    if (pIn->Permissible_direction_len > 0) //Permissible_direction
    {
        count = pIn->Permissible_direction_len / sizeof(uint8_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->Permissible_direction+i)     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t		    Permissible_direction
        }
    }

    sp_big_reverse_copy(pIn->Recommended_driving_directions_for_AJOTP_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     Recommended_driving_directions_for_AJOTP_len
    if (pIn->Recommended_driving_directions_for_AJOTP_len > 0) //Recommended_driving_directions_for_AJOTP
    {
        count = pIn->Recommended_driving_directions_for_AJOTP_len / sizeof(uint8_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->Recommended_driving_directions_for_AJOTP+i)     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t		    Recommended_driving_directions_for_AJOTP
        }
    }

    sp_big_reverse_copy(pIn->distance_2_intersection                ,pcOut + n, 4);      n += 4;   //4byte    uint32_t        distance_2_intersection
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    next_road_name
    sp_big_reverse_copy(pIn->Current_max_speed_limit                ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         Current_max_speed_limit
    sp_big_reverse_copy(pIn->Current_speed                          ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         Current_speed
    sp_big_reverse_copy(pIn->Distance_2_speed_limit_zone            ,pcOut + n, 2);      n += 2;   //2byte    uint16_t        Distance_2_speed_limit_zone
    sp_big_reverse_copy(pIn->length_of_speed_limit                  ,pcOut + n, 2);      n += 2;   //2byte    uint16_t        length_of_speed_limit
    sp_big_reverse_copy(pIn->speed_limit                            ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         speed_limit
    sp_big_reverse_copy(pIn->navigating_status                      ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         navigating_status
    sp_big_reverse_copy(pIn->camera_ahead_status                    ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         camera_ahead_status
    sp_big_reverse_copy(pIn->The_distance_2_camera                  ,pcOut + n, 2);      n += 2;   //2byte    uint16_t        The_distance_2_camera
    sp_big_reverse_copy(pIn->vehicle_coordinates_Longitude          ,pcOut + n, 8);      n += 8;   //8byte    double          vehicle_coordinates_Longitude
    sp_big_reverse_copy(pIn->vehicle_coordinates_Latitude           ,pcOut + n, 8);      n += 8;   //8byte    double          vehicle_coordinates_Latitude
    sp_big_reverse_copy(pIn->vehicle_speed                          ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         vehicle_speed
    sp_big_reverse_copy(pIn->vehicle_altitude                       ,pcOut + n, 2);      n += 2;   //2byte    uint16_t        vehicle_altitude
    sp_big_reverse_copy(pIn->Danger_signs                           ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         Danger_signs
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    POI_information
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    reach_the_destination
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    ETA_info_time
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    ETA_info_remain_time
    sp_big_reverse_copy(pIn->RecommendedDrivingDirectionsId         ,pcOut + n, 2);      n += 2;   //2byte    uint16_t        RecommendedDrivingDirectionsId
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    lanesPermissibleDirectionId
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    guideLine
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    guidePoint
    sp_big_reverse_copy(pIn->vehicleHeading                         ,pcOut + n, 8);      n += 8;   //8byte    double          vehicleHeading
    sp_big_reverse_copy(pIn->Navigating_ratio                       ,pcOut + n, 8);      n += 8;   //8byte    double          Navigating_ratio
    sp_big_reverse_copy(pIn->mapProviders                           ,pcOut + n, 1);      n += 1;   //1byte    uint8_t         mapProviders
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    carToDestDistance
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    distanceToIntersection
    SPStringserialization(pIn->next_road_name, pcOut, n);                  //        string    timeToDest
    sp_big_reverse_copy(pIn->recommendedDrivingDirectionsIdOverseas ,pcOut + n, 2);      n += 2;   //2byte    uint16_t        recommendedDrivingDirectionsIdOverseas

    sp_big_reverse_copy(pIn->reservedDataLength1                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength1
    if (pIn->reservedDataLength1 > 0) //reserved1
    {
        count = pIn->reservedDataLength1 / sizeof(uint8_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->reserved1+i)     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t		    reserved1
        }
    }

    sp_big_reverse_copy(pIn->reservedDataLength2                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength2
    if (pIn->reservedDataLength2 > 0) //reserved2
    {
        count = pIn->reservedDataLength2 / sizeof(uint16_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->reserved2+i)     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t		    reserved2
        }
    }

    sp_big_reverse_copy(pIn->reservedDataLength3                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength3
    if (pIn->reservedDataLength3 > 0) //reserved3
    {
        count = pIn->reservedDataLength3 / sizeof(uint32_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->reserved3+i)     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t		    reserved3
        }
    }

    sp_big_reverse_copy(pIn->reservedDataLength4                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength4
    if (pIn->reservedDataLength4 > 0) //reserved4
    {
        count = pIn->reservedDataLength4 / sizeof(double);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->reserved4+i)     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t		    reserved4
        }
    }

    sp_big_reverse_copy(pIn->reservedDataLength5                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength5
    if (pIn->reservedDataLength5 > 0) //reserved5
    {
        count = pIn->reservedDataLength5 / sizeof(float);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->reserved5+i)     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t		    reserved5
        }
    }
}

// HudMappathInfo_EG
void HudMappathInfo_EGSerialization(std::shared_ptr<stHudMappathInfo_EG> pIn, char* pcOut)
{
    int n = 0;
    sp_big_reverse_copy(pIn->Checksum             ,pcOut + n, 4);      n += 4;   //4byte   uint32    Checksum
    sp_big_reverse_copy(pIn->Counter              ,pcOut + n, 2);      n += 2;   //2byte   uint16    Counter
    sp_big_reverse_copy(pIn->is_on_the_path       ,pcOut + n, 1);      n += 1;   //1byte   uint8     is_on_the_path
    sp_big_reverse_copy(pIn->road_angle           ,pcOut + n, 1);      n += 1;   //1byte   uint8     road_angle
    sp_big_reverse_copy(pIn->road_slope           ,pcOut + n, 4);      n += 4;   //4byte   float32   road_slope
    SPStringserialization(pIn->all_EHP_v2_info, pcOut, n);
}

// HudNavigationmap
void HudNavigationmapSerialization(std::shared_ptr<stHudNavigationmap> pIn, char* pcOut)
{
    int n = 0;
    SPStringserialization(pIn->Navigation_map, pcOut, n);
    pIn->Navigation_map_len = n;
}




// Deserialization
// VehiclePositionInfoNotify
void VehiclePositionInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stVehiclePositionInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32  Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16  Counter
    big_reverse_copy(pcIn + n,  pOut->Longitude                           );      n += 8;   //8byte   double  Longitude
    big_reverse_copy(pcIn + n,  pOut->Latitude                            );      n += 8;   //8byte   double  Latitude
    big_reverse_copy(pcIn + n,  pOut->altitude                            );      n += 8;   //8byte   double  altitude
    big_reverse_copy(pcIn + n,  pOut->Heading                             );      n += 8;   //8byte   double  Heading
    big_reverse_copy(pcIn + n,  pOut->hd_lane_left_angle                  );      n += 8;   //8byte   double  hd_lane_left_angle
    big_reverse_copy(pcIn + n,  pOut->Hd_lane_right_angle                 );      n += 8;   //8byte   double  Hd_lane_right_angle
    big_reverse_copy(pcIn + n,  pOut->VehicleSpeed                        );      n += 8;   //8byte   double  VehicleSpeed
    big_reverse_copy(pcIn + n,  pOut->acceleration                        );      n += 8;   //8byte   double  acceleration
    big_reverse_copy(pcIn + n,  pOut->x_speed                             );      n += 8;   //8byte   double  x_speed
    big_reverse_copy(pcIn + n,  pOut->y_speed                             );      n += 8;   //8byte   double  y_speed
    big_reverse_copy(pcIn + n,  pOut->z_speed                             );      n += 8;   //8byte   double  z_speed
    big_reverse_copy(pcIn + n,  pOut->timestamp                           );      n += 8;   //8byte   double  timestamp
    big_reverse_copy(pcIn + n,  pOut->hd_link_id                          );      n += 4;   //4byte   uint32  hd_link_id
    big_reverse_copy(pcIn + n,  pOut->hd_lane_id                          );      n += 4;   //4byte   uint32  hd_lane_id
    big_reverse_copy(pcIn + n,  pOut->hd_lane_type                        );      n += 4;   //4byte   uInt32  hd_lane_type
    big_reverse_copy(pcIn + n,  pOut->on_lane_offset                      );      n += 8;   //8byte   double  on_lane_offset
    big_reverse_copy(pcIn + n,  pOut->hd_lane_seq                         );      n += 4;   //4byte   uint32  hd_lane_seq
    big_reverse_copy(pcIn + n,  pOut->hd_lane_num                         );      n += 4;   //4byte   uint32  hd_lane_num
    big_reverse_copy(pcIn + n,  pOut->hd_lane_left_lateral_offset         );      n += 8;   //8byte   double  hd_lane_left_lateral_offset
    big_reverse_copy(pcIn + n,  pOut->hd_lane_right_lateral_offset        );      n += 8;   //8byte   double  hd_lane_right_lateral_offset
    big_reverse_copy(pcIn + n,  pOut->roll                                );      n += 8;   //8byte   double  roll
    big_reverse_copy(pcIn + n,  pOut->pitch                               );      n += 8;   //8byte   double  pitch
    big_reverse_copy(pcIn + n,  pOut->HdStatus                            );      n += 1;   //1byte   uint8   HdStatus
    big_reverse_copy(pcIn + n,  pOut->hdmap_version                       );      n += 1;   //1byte   uint8   hdmap_version
    big_reverse_copy(pcIn + n,  pOut->fusion_status                       );      n += 1;   //1byte   uint8   fusion_status
    big_reverse_copy(pcIn + n,  pOut->pos_confidence                      );      n += 8;   //8byte   double  pos_confidence
    big_reverse_copy(pcIn + n,  pOut->position_type                       );      n += 1;   //1byte   uint8   position_type
    big_reverse_copy(pcIn + n,  pOut->break_light                         );      n += 1;   //1byte   uint8   break_light
    big_reverse_copy(pcIn + n,  pOut->indicator_light                     );      n += 1;   //1byte   uint8   indicator_light
    big_reverse_copy(pcIn + n,  pOut->Lights                              );      n += 1;   //1byte   uint8   Lights
    big_reverse_copy(pcIn + n,  pOut->Weather                             );      n += 1;   //1byte   uint8   Weather
    big_reverse_copy(pcIn + n,  pOut->target_cruise_speed                 );      n += 4;   //4byte   float   target_cruise_speed
    big_reverse_copy(pcIn + n,  pOut->FieldLength_target_lane             );      n += 4;   //4byte   uint32  FieldLength_target_lane
    
    if (pOut->FieldLength_target_lane > 0)
    {
        int lane_count = pOut->FieldLength_target_lane / 4;//sizeof(uint32_t);
        pOut->target_lane_id = new uint32_t[lane_count];
        memset(pOut->target_lane_id, 0, sizeof(uint32_t)*lane_count);
        for (int i = 0; i < lane_count; ++i)
        {
            big_reverse_copy(pcIn + n, *(pOut->target_lane_id+i)          );      n += 4;   //4byte   uint32  target_lane_id
        }
    }
    
    big_reverse_copy(pcIn + n,  pOut->FieldLength_target_lane_id_segment  );      n += 4;   //4byte   uint32  FieldLength_target_lane_id_segment
    if (pOut->FieldLength_target_lane_id_segment > 0)
    {
        int lane_count = pOut->FieldLength_target_lane_id_segment / 4;//sizeof(uint32_t);
        pOut->target_lane_id_segment = new uint32_t[lane_count];
        memset(pOut->target_lane_id_segment, 0, sizeof(uint32_t)*lane_count);
        for (int i = 0; i < lane_count; ++i)
        {
            big_reverse_copy(pcIn + n, *(pOut->target_lane_id_segment+i)  );      n += 4;   //4byte   uint32  target_lane_id
        }            
    }
    big_reverse_copy(pcIn + n,  pOut->localization_output_offset          );      n += 1;   //1byte   uint8   localization_output_offset
}


// RTKInfoNotify
void RTKInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stRTKInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                        );      n += 4;   //4byte   uint32    Checksum  
    big_reverse_copy(pcIn + n,  pOut->Counter                         );      n += 2;   //2byte   uint16    Counter  
    big_reverse_copy(pcIn + n,  pOut->rtk_status                          );      n += 4;   //4byte   uint32    rtk_status  
    big_reverse_copy(pcIn + n,  pOut->utc_time_us                         );      n += 8;   //8byte   float64   utc_time_us  
    big_reverse_copy(pcIn + n,  pOut->sys_time_us                     );      n += 8;   //8byte   float64   sys_time_us  
    big_reverse_copy(pcIn + n,  pOut->longitude                          );      n += 8;   //8byte   float64   longitude  
    big_reverse_copy(pcIn + n,  pOut->latitude                           );      n += 8;   //8byte   float64   latitude  
    big_reverse_copy(pcIn + n,  pOut->altitude                           );      n += 8;   //8byte   float64   altitude  
    big_reverse_copy(pcIn + n,  pOut->longitude_acc                      );      n += 8;   //8byte   float64   longitude_acc  
    big_reverse_copy(pcIn + n,  pOut->latitude_acc                       );      n += 8;   //8byte   float64   latitude_acc  
    big_reverse_copy(pcIn + n,  pOut->altitude_acc                       );      n += 8;   //8byte   float64   altitude_acc  
    big_reverse_copy(pcIn + n,  pOut->heading_move                        );      n += 8;   //8byte   float64   heading_move  
    big_reverse_copy(pcIn + n,  pOut->heading_double_ant                  );      n += 8;   //8byte   float64   heading_double_ant  
    big_reverse_copy(pcIn + n,  pOut->heading_move_acc                    );      n += 8;   //8byte   float64   heading_move_acc  
    big_reverse_copy(pcIn + n,  pOut->speed_2d                            );      n += 8;   //8byte   float64   speed_2d  
    big_reverse_copy(pcIn + n,  pOut->speed_acc                           );      n += 8;   //8byte   float64   speed_acc  
    big_reverse_copy(pcIn + n,  pOut->speed_n                             );      n += 8;   //8byte   float64   speed_n  
    big_reverse_copy(pcIn + n,  pOut->speed_e                             );      n += 8;   //8byte   float64   speed_e  
    big_reverse_copy(pcIn + n,  pOut->speed_u                             );      n += 8;   //8byte   float64   speed_u  
    big_reverse_copy(pcIn + n,  pOut->g_dop                               );      n += 8;   //8byte   float64   g_dop  
    big_reverse_copy(pcIn + n,  pOut->h_dop                               );      n += 8;   //8byte   float64   h_dop  
    big_reverse_copy(pcIn + n,  pOut->v_dop                               );      n += 8;   //8byte   float64   v_dop  
    big_reverse_copy(pcIn + n,  pOut->satellite_num                       );      n += 4;   //4byte   uint32    satellite_num  
    big_reverse_copy(pcIn + n,  pOut->satellite_used                      );      n += 4;   //4byte   uint32    satellite_used  
    big_reverse_copy(pcIn + n,  pOut->snr_max                             );      n += 8;   //8byte   float64   snr_max  
    big_reverse_copy(pcIn + n,  pOut->snr_mix                             );      n += 8;   //8byte   float64   snr_mix  
    big_reverse_copy(pcIn + n,  pOut->snr_avr                             );      n += 8;   //8byte   float64   snr_avr      
}


// IMUInfoNotify
void IMUInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stIMUInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32    Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16    Counter
    big_reverse_copy(pcIn + n,  pOut->angular_velocity_x                  );      n += 8;   //8byte   double    angular_velocity_x
    big_reverse_copy(pcIn + n,  pOut->angular_velocity_y                  );      n += 8;   //8byte   double    angular_velocity_y
    big_reverse_copy(pcIn + n,  pOut->angular_velocity_z                  );      n += 8;   //8byte   double    angular_velocity_z  
    big_reverse_copy(pcIn + n,  pOut->acc_speed_x                         );      n += 8;   //8byte   double    acc_speed_x
    big_reverse_copy(pcIn + n,  pOut->acc_speed_y                         );      n += 8;   //8byte   double    acc_speed_y
    big_reverse_copy(pcIn + n,  pOut->acc_speed_z                         );      n += 8;   //8byte   double    acc_speed_z
    big_reverse_copy(pcIn + n,  pOut->IMU_status                          );      n += 1;   //1byte   uint8     IMU_status
    big_reverse_copy(pcIn + n,  pOut->IMU_current_temperature             );      n += 8;   //8byte   double    IMU current temperature
    big_reverse_copy(pcIn + n,  pOut->sys_time_us                         );      n += 8;   //8byte   double    sys_time_us
    big_reverse_copy(pcIn + n,  pOut->is_calibrated                       );      n += 1;   //1byte   bool      is_calibrated
}


// ObstacleInfoNotify
void ObstacleInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stObstacleInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32    Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16    Counter
    big_reverse_copy(pcIn + n,  pOut->target_flag                         );      n += 1;   //1byte   bool      target_flag
    big_reverse_copy(pcIn + n,  pOut->FieldLength_Object_len              );      n += 4;   //4byte   uint32    FieldLength_Object

    if (pOut->FieldLength_Object_len > 0)
    {
        int count = pOut->FieldLength_Object_len / 97;//sizeof(stObstacleInfoNotifyFLO);
        int tt = sizeof(stObstacleInfoNotifyFLO);
        pOut->FieldLength_Object = new stObstacleInfoNotifyFLO[count];
        memset(pOut->FieldLength_Object, 0, sizeof(stObstacleInfoNotifyFLO)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->ObstacleType                );   n += 4;   //4byte   uint32    ObstacleType
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->confidence                  );   n += 8;   //8byte   double    confidence
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->Obstacle_Id_i               );   n += 4;   //4byte   uint32    Obstacle Id_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->ObstacleDistance_X_i        );   n += 8;   //8byte   double    ObstacleDistance_X_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->ObstacleDistance_Y_i        );   n += 8;   //8byte   double    ObstacleDistance_Y_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->ObstacleDistance_Z_i        );   n += 8;   //8byte   double    ObstacleDistance_Z_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->Bounding_box_length_i       );   n += 4;   //4byte   float     Bounding_box_length_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->Bounding_box_width_i        );   n += 4;   //4byte   float     Bounding_box_width_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->Bounding_box_height_i       );   n += 4;   //4byte   float     Bounding_box_height_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->break_light                 );   n += 1;   //1byte   uint8     break_light
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->indicator_light             );   n += 1;   //1byte   uint8     indicator_light
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->obj_speed                   );   n += 8;   //8byte   double    obj_speed
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->ObstacleState               );   n += 1;   //1byte   uint8     ObstacleState
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->obstacle_timestamp          );   n += 8;   //8byte   double    obstacle_timestamp
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->obstacle_camera_timestamp   );   n += 8;   //8byte   double    obstacle_camera_timestamp
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->moving                      );   n += 1;   //1byte   bool      moving
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->obj_heading                 );   n += 8;   //8byte   double    obj_heading
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->Obj_direction               );   n += 8;   //8byte   double    Obj_direction
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Object+i)->ObstacleWarningBrakeState   );   n += 1;   //1byte   uint8     ObstacleWarningBrakeState
        }
    }
}


// LanelineDataNotify
void LanelineDataNotifyDeserialization(const char* pcIn, std::shared_ptr<stLanelineDataNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32    Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16    Counter
    big_reverse_copy(pcIn + n,  pOut->FieldLength_Line_len                );      n += 4;   //4byte   uint32    FieldLength_Line
    if (pOut->FieldLength_Line_len > 0)
    {
        int count = pOut->FieldLength_Line_len / 66;//sizeof(stLanelineDataNotifyFLL);
        int tt = sizeof(stLanelineDataNotifyFLL);
        pOut->FieldLength_Line = new stLanelineDataNotifyFLL[count];
        memset(pOut->FieldLength_Line, 0, sizeof(stLanelineDataNotifyFLL)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->LineID                   );      n += 4;   //4byte   float64   LineID
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->LineType                 );      n += 1;   //1byte   float64   LineType
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->LineColor                );      n += 1;   //1byte   float64   LineColor
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->LineWidth                );      n += 4;   //4byte   float64   LineWidth
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->Line_confidence          );      n += 8;   //8byte   float64   Line_confidence
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->CurvatureEquation_c0     );      n += 4;   //4byte   float64   CurvatureEquation_c0
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->CurvatureEquation_c1     );      n += 4;   //4byte   float64   CurvatureEquation_c1
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->CurvatureEquation_c2     );      n += 4;   //4byte   float64   CurvatureEquation_c2
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->CurvatureEquation_c3     );      n += 4;   //4byte   float64   CurvatureEquation_c3
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->Line_Startpoint_x        );      n += 4;   //4byte   float64   Line_Startpoint_x
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->Line_Startpoint_y        );      n += 4;   //4byte   float64   Line_Startpoint_y
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->Line_Startpoint_z        );      n += 4;   //4byte   float64   Line_Startpoint_z
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->Line_Endpoint_x          );      n += 4;   //4byte   float64   Line_Endpoint_x
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->Line_Endpoint_y          );      n += 4;   //4byte   float64   Line_Endpoint_y
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->Line_Endpoint_z          );      n += 4;   //4byte   float64   Line_Endpoint_z
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_Line+i)->sys_time_us              );      n += 8;   //8byte   float64   sys_time_us
        }
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_RoadMarking_len                );      n += 4;   //4byte   uint32    FieldLength_Line
    if (pOut->FieldLength_RoadMarking_len > 0)
    {
        int count = pOut->FieldLength_RoadMarking_len / 57;//sizeof(stLanelineDataNotifyFLRM);
        int tt = sizeof(stLanelineDataNotifyFLRM);
        pOut->FieldLength_RoadMarking = new stLanelineDataNotifyFLRM[count];
        memset(pOut->FieldLength_RoadMarking, 0, sizeof(stLanelineDataNotifyFLRM)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarkingID_i                 );      n += 4;   //4byte   float64   RoadMarkingID_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarkingType_i               );      n += 1;   //1byte   float64   RoadMarkingType_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarkingType_confidence_i    );      n += 8;   //8byte   uint32    RoadMarkingType_confidence_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarking_length_i            );      n += 4;   //4byte   uint32    RoadMarking_length_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarking_width_i             );      n += 4;   //4byte   float64   RoadMarking_width_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarking_height_i            );      n += 4;   //4byte   float64   RoadMarking_height_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarking_Distance_X_i        );      n += 8;   //8byte   float64   RoadMarking_Distance_X_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarking_Distance_Y_i        );      n += 8;   //8byte   float64   RoadMarking_Distance_Y_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarking_Distance_Z_i        );      n += 8;   //8byte   float64   RoadMarking_Distance_Z_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_RoadMarking+i)->RoadMarkingPosition_confidence  );      n += 8;   //8byte   float64   RoadMarkingPosition_confidence
        }
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_TLA_len                );      n += 4;   //4byte   uint32    FieldLength_TLA_len
    if (pOut->FieldLength_TLA_len > 0)
    {
        int count = pOut->FieldLength_TLA_len / 42;//sizeof(stLanelineDataNotifyFLTLA);
        int tt = sizeof(stLanelineDataNotifyFLTLA);
        pOut->FieldLength_TLA = new stLanelineDataNotifyFLTLA[count];
        memset(pOut->FieldLength_TLA, 0, sizeof(stLanelineDataNotifyFLTLA)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->TLAID_i                   );      n += 4;   //4byte   float64   TLAID_i
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->TLA_Distance_X            );      n += 8;   //8byte   float64   TLA_Distance_X
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->TLA_Distance_Y            );      n += 8;   //8byte   float64   TLA_Distance_Y
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->TLA_Distance_Z            );      n += 8;   //8byte   float64   TLA_Distance_Z
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->TLAPosition_confidence    );      n += 8;   //8byte   float64   TLAPosition_confidence
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->LeftTLA_Color             );      n += 1;   //1byte   float64   LeftTLA_Color
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->LeftTLA_Type              );      n += 1;   //1byte   float64   LeftTLA_Type
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->StraightTLA_Color         );      n += 1;   //1byte   float64   StraightTLA_Color
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->StraightTLA_Type          );      n += 1;   //1byte   float64   StraightTLA_Type
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->RightTLA_Color            );      n += 1;   //1byte   float64   RightTLA_Color
            big_reverse_copy(pcIn + n,  (pOut->FieldLength_TLA+i)->RightTLA_Type             );      n += 1;   //1byte   float64   RightTLA_Type
        }
    }
}

// ChangeLaneDataNotify
void ChangeLaneDataNotifyDeserialization(const char* pcIn, std::shared_ptr<stChangeLaneDataNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32    Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16    Counter
    big_reverse_copy(pcIn + n,  pOut->ChangeLaneState                     );      n += 4;   //4byte   uint32    ChangeLaneState
    big_reverse_copy(pcIn + n,  pOut->ChangeLaneDirection                 );      n += 1;   //1byte   uint8     ChangeLaneDirection
    big_reverse_copy(pcIn + n,  pOut->is_change_safety                    );      n += 1;   //1byte   bool      is_change_safety
    big_reverse_copy(pcIn + n,  pOut->ChangeLane_timestamp                );      n += 4;   //4byte   uint32    ChangeLane_timestamp
    big_reverse_copy(pcIn + n,  pOut->change_ratio                        );      n += 8;   //8byte   double    change_ratio
    big_reverse_copy(pcIn + n,  pOut->change_termi                        );      n += 4;   //4byte   uint32    change_termi
    big_reverse_copy(pcIn + n,  pOut->landing_center_X                    );      n += 8;   //8byte   double    landing_center_X
    big_reverse_copy(pcIn + n,  pOut->landing_center_Y                    );      n += 8;   //8byte   double    landing_center_Y
    big_reverse_copy(pcIn + n,  pOut->landing_center_Z                    );      n += 8;   //8byte   double    landing_center_Z
    big_reverse_copy(pcIn + n,  pOut->landing_box_length                  );      n += 8;   //8byte   double    landing_box_length
    big_reverse_copy(pcIn + n,  pOut->landing_box__width                  );      n += 8;   //8byte   double    landing_box__width
    big_reverse_copy(pcIn + n,  pOut->landing_box_height                  );      n += 8;   //8byte   double    landing_box_height
}

// PilotStatusNotify
void PilotStatusNotifyDeserialization(const char* pcIn, std::shared_ptr<stPilotStatusNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte    uint32   Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte    uint16   Counter
    big_reverse_copy(pcIn + n,  pOut->ACCStatus                           );      n += 1;   //1byte    uint8    ACCStatus
    big_reverse_copy(pcIn + n,  pOut->ICCStatus                           );      n += 1;   //1byte    uint8    ICCStatus
    big_reverse_copy(pcIn + n,  pOut->DNPStatus                           );      n += 1;   //1byte    uint8    DNPStatus
    big_reverse_copy(pcIn + n,  pOut->TakeoverStatus                      );      n += 1;   //1byte    bool     TakeoverStatus
    big_reverse_copy(pcIn + n,  pOut->driving_time                        );      n += 4;   //4byte    uint32   driving_time
}

// PilotAlarmAndNoticeInfoNotify
void PilotAlarmAndNoticeInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32    Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16    Counter
    big_reverse_copy(pcIn + n,  pOut->PilotAlarmReason                    );      n += 4;   //4byte   uint32    PilotAlarmReason
    big_reverse_copy(pcIn + n,  pOut->alarm_distance                      );      n += 4;   //4byte   uint32    alarm_distance
    big_reverse_copy(pcIn + n,  pOut->alarm_stage                         );      n += 4;   //4byte   uint32    alarm_stage
    big_reverse_copy(pcIn + n,  pOut->alarm_timestamp                     );      n += 8;   //8byte   double    alarm_timestamp
    big_reverse_copy(pcIn + n,  pOut->PilotNotice                         );      n += 4;   //4byte   uint32    PilotNotice
    big_reverse_copy(pcIn + n,  pOut->notice_distance                     );      n += 4;   //4byte   uint32    notice_distance
    big_reverse_copy(pcIn + n,  pOut->notice_timestamp                    );      n += 8;   //8byte   double    notice_timestamp
}

// BroadcastInfoNotify
void BroadcastInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stBroadcastInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32    Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16    Counter
    big_reverse_copy(pcIn + n,  pOut->driver_attention                    );      n += 1;   //1byte   bool      target_flag
    big_reverse_copy(pcIn + n,  pOut->large_vehicles                      );      n += 1;   //1byte   bool      FieldLength_Object
    big_reverse_copy(pcIn + n,  pOut->dangerous_vehicle                   );      n += 1;   //1byte   bool      ObstacleType
    big_reverse_copy(pcIn + n,  pOut->pedestrians                         );      n += 1;   //1byte   bool      confidence
}

// // PlanningLineInfoNotify
// void PlanningLineInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stPlanningLineInfoNotify> pOut)
// {
//     int n = 0;
//     big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32    Checksum
//     big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16    Counter
//     big_reverse_copy(pcIn + n,  pOut->PlanningLineStatus                  );      n += 1;   //1byte   bool      PlanningLineStatus
//     big_reverse_copy(pcIn + n,  pOut->planning_timestamp                  );      n += 8;   //8byte   double    planning_timestamp
//     big_reverse_copy(pcIn + n,  pOut->FieldLength_PlanningLinePoints_len  );      n += 4;   //4byte   uint32    FieldLength_PlanningLinePoints

//     if (pOut->FieldLength_PlanningLinePoints_len > 0)
//     {
//         int count = pOut->FieldLength_PlanningLinePoints_len / 28;//sizeof(stPlanningLineInfoNotifyFPLP);
//         pOut->FieldLength_PlanningLinePoints = new stPlanningLineInfoNotifyFPLP[count];
//         memset(pOut->FieldLength_PlanningLinePoints, 0, sizeof(stPlanningLineInfoNotifyFPLP)*count);
//         for (int i = 0; i < count; ++i)
//         {
//             big_reverse_copy(pcIn + n, (pOut->FieldLength_PlanningLinePoints+i)->PlanningLinePointsID_i   );  n += 4;     //4byte   uint32  target_lane_id
//             big_reverse_copy(pcIn + n, (pOut->FieldLength_PlanningLinePoints+i)->points_X                 );  n += 8;     //8byte   double  points_X
//             big_reverse_copy(pcIn + n, (pOut->FieldLength_PlanningLinePoints+i)->points_Y                 );  n += 8;     //8byte   double  points_Y
//             big_reverse_copy(pcIn + n, (pOut->FieldLength_PlanningLinePoints+i)->points_Z                 );  n += 8;     //8byte   double  points_Z
//         }
//     }
// }

// HudRoadInfoNotify
void HudRoadInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stHudRoadInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32    Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16    Counter
    big_reverse_copy(pcIn + n,  pOut->car_2_dest                          );      n += 4;   //4byte   uint32    car_2_dest
    big_reverse_copy(pcIn + n,  pOut->time_of_car_2_dest                  );      n += 4;   //4byte   uint32    time_of_car_2_dest
    big_reverse_copy(pcIn + n,  pOut->Num_of_lanes                        );      n += 1;   //1byte   uint8     Num_of_lanes
    big_reverse_copy(pcIn + n,  pOut->Current_road_level                  );      n += 1;   //1byte   uint8     Current_road_level
    big_reverse_copy(pcIn + n,  pOut->Permissible_direction_len           );      n += 4;   //4byte   uint32    Permissible_direction_len
    if (pOut->Permissible_direction_len > 0)
    {
        int count = pOut->Permissible_direction_len / sizeof(uint8_t);
        pOut->Permissible_direction = new uint8_t[count];
        memset(pOut->Permissible_direction, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcIn + n, *(pOut->Permissible_direction+i)); n += 1; //1byte   uint8  Permissible_direction
        }
    }
    big_reverse_copy(pcIn + n,  pOut->Recommended_driving_directions_for_AJOTP_len);      n += 4;   //4byte   uint32     Recommended_driving_directions_for_AJOTP_len
    if (pOut->Recommended_driving_directions_for_AJOTP_len > 0)
    {
        int count = pOut->Recommended_driving_directions_for_AJOTP_len / sizeof(uint8_t);
        pOut->Recommended_driving_directions_for_AJOTP = new uint8_t[count];
        memset(pOut->Recommended_driving_directions_for_AJOTP, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcIn + n, *(pOut->Recommended_driving_directions_for_AJOTP+i)); n += 1; //4byte   uint32  target_lane_id
        }
    }
    big_reverse_copy(pcIn + n,  pOut->distance_2_intersection             );      n += 4;   //4byte   uint32    distance_2_intersection
    SPStringDeserialization(pcIn, pOut->next_road_name, n);                                                        //        string    next_road_name
    big_reverse_copy(pcIn + n,  pOut->Current_max_speed_limit             );      n += 1;   //1byte   uint8     Current_max_speed_limit
    big_reverse_copy(pcIn + n,  pOut->Current_speed                       );      n += 1;   //1byte   uint8     Current_speed
    big_reverse_copy(pcIn + n,  pOut->Distance_2_speed_limit_zone         );      n += 2;   //2byte   uint16    Distance_2_speed_limit_zone
    big_reverse_copy(pcIn + n,  pOut->length_of_speed_limit               );      n += 2;   //2byte   uint16    length_of_speed_limit
    big_reverse_copy(pcIn + n,  pOut->speed_limit                         );      n += 1;   //1byte   uint8     speed_limit
    big_reverse_copy(pcIn + n,  pOut->navigating_status                   );      n += 1;   //1byte   uint8     navigating_status
    big_reverse_copy(pcIn + n,  pOut->camera_ahead_status                 );      n += 1;   //1byte   uint8     camera_ahead_status
    big_reverse_copy(pcIn + n,  pOut->The_distance_2_camera               );      n += 2;   //2byte   uint16    The_distance_2_camera
    big_reverse_copy(pcIn + n,  pOut->vehicle_coordinates_Longitude       );      n += 8;   //8byte   float64   vehicle_coordinates_Longitude
    big_reverse_copy(pcIn + n,  pOut->vehicle_coordinates_Latitude        );      n += 8;   //8byte   float64   vehicle_coordinates_Latitude
    big_reverse_copy(pcIn + n,  pOut->vehicle_speed                       );      n += 1;   //1byte   uint8     vehicle_speed
    big_reverse_copy(pcIn + n,  pOut->vehicle_altitude                    );      n += 2;   //2byte   uint16    vehicle_altitude
    big_reverse_copy(pcIn + n,  pOut->Danger_signs                        );      n += 1;   //1byte   uint8     Danger_signs
    SPStringDeserialization(pcIn, pOut->POI_information, n);                                                       //        string    POI_information 
    SPStringDeserialization(pcIn, pOut->reach_the_destination, n);                                                 //        string    reach_the_destination 
    SPStringDeserialization(pcIn, pOut->ETA_info_time, n);                                                         //        string    ETA_info_time 
    SPStringDeserialization(pcIn, pOut->ETA_info_remain_time, n);                                                  //        string    ETA_info_remain_time
    big_reverse_copy(pcIn + n,  pOut->RecommendedDrivingDirectionsId      );      n += 2;   //2byte   uint16    RecommendedDrivingDirectionsId
    SPStringDeserialization(pcIn, pOut->lanesPermissibleDirectionId, n);                                           //        string    lanesPermissibleDirectionId  
    SPStringDeserialization(pcIn, pOut->guideLine, n);                                                             //        string    guideLine
    SPStringDeserialization(pcIn, pOut->guidePoint, n);                                                            //        string    guidePoint
    big_reverse_copy(pcIn + n,  pOut->vehicleHeading                      );      n += 8;   //8byte   double    vehicleHeading
    big_reverse_copy(pcIn + n,  pOut->Navigating_ratio                    );      n += 8;   //8byte   double    Navigating_ratio
}

//overseasHudRoadInfoNotify
void overseasHudRoadInfoNotifyDeserialization(const char* pcInput, std::shared_ptr<oshrinfo_t> pOut)
{
    int n = 0;
    big_reverse_copy(pcInput + n,  pOut->Checksum                         );      n += 4;   //4byte    uint32_t        Checksum
    big_reverse_copy(pcInput + n,  pOut->Counter                          );      n += 2;   //2byte    uint16_t        Counter
    big_reverse_copy(pcInput + n,  pOut->car_2_dest                       );      n += 4;   //4byte    uint32_t        car_2_dest
    big_reverse_copy(pcInput + n,  pOut->time_of_car_2_dest               );      n += 4;   //4byte    uint32_t        time_of_car_2_dest
    big_reverse_copy(pcInput + n,  pOut->Num_of_lanes                     );      n += 1;   //1byte    uint8_t         Num_of_lanes
    big_reverse_copy(pcInput + n,  pOut->Current_road_level               );      n += 1;   //1byte    uint8_t         Current_road_level

    big_reverse_copy(pcInput + n,  pOut->Permissible_direction_len        );      n += 4;   //4byte   uint32    Permissible_direction_len
    if (pOut->Permissible_direction_len > 0)
    {
        int count = pOut->Permissible_direction_len / sizeof(uint8_t);
        pOut->Permissible_direction = new uint8_t[count];
        memset(pOut->Permissible_direction, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcInput + n, *(pOut->Permissible_direction+i)); n += 1; //1byte   uint8  Permissible_direction
        }
    }
    big_reverse_copy(pcInput + n,  pOut->Recommended_driving_directions_for_AJOTP_len);      n += 4;   //4byte   uint32     Recommended_driving_directions_for_AJOTP_len
    if (pOut->Recommended_driving_directions_for_AJOTP_len > 0)
    {
        int count = pOut->Recommended_driving_directions_for_AJOTP_len / sizeof(uint8_t);
        pOut->Recommended_driving_directions_for_AJOTP = new uint8_t[count];
        memset(pOut->Recommended_driving_directions_for_AJOTP, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcInput + n, *(pOut->Recommended_driving_directions_for_AJOTP+i)); n += 1; //4byte   uint32  Recommended_driving_directions_for_AJOTP
        }
    }
    big_reverse_copy(pcInput + n,  pOut->distance_2_intersection                );      n += 4;   //4byte    uint32_t        distance_2_intersection
    SPStringDeserialization(pcInput, pOut->next_road_name,                 n);             //        string    next_road_name
    big_reverse_copy(pcInput + n,  pOut->Current_max_speed_limit                );      n += 1;   //1byte    uint8_t         Current_max_speed_limit
    big_reverse_copy(pcInput + n,  pOut->Current_speed                          );      n += 1;   //1byte    uint8_t         Current_speed
    big_reverse_copy(pcInput + n,  pOut->Distance_2_speed_limit_zone            );      n += 2;   //2byte    uint16_t        Distance_2_speed_limit_zone
    big_reverse_copy(pcInput + n,  pOut->length_of_speed_limit                  );      n += 2;   //2byte    uint16_t        length_of_speed_limit
    big_reverse_copy(pcInput + n,  pOut->speed_limit                            );      n += 1;   //1byte    uint8_t         speed_limit
    big_reverse_copy(pcInput + n,  pOut->navigating_status                      );      n += 1;   //1byte    uint8_t         navigating_status
    big_reverse_copy(pcInput + n,  pOut->camera_ahead_status                    );      n += 1;   //1byte    uint8_t         camera_ahead_status
    big_reverse_copy(pcInput + n,  pOut->The_distance_2_camera                  );      n += 2;   //2byte    uint16_t        The_distance_2_camera
    big_reverse_copy(pcInput + n,  pOut->vehicle_coordinates_Longitude          );      n += 8;   //8byte    double          vehicle_coordinates_Longitude
    big_reverse_copy(pcInput + n,  pOut->vehicle_coordinates_Latitude           );      n += 8;   //8byte    double          vehicle_coordinates_Latitude
    big_reverse_copy(pcInput + n,  pOut->vehicle_speed                          );      n += 1;   //1byte    uint8_t         vehicle_speed
    big_reverse_copy(pcInput + n,  pOut->vehicle_altitude                       );      n += 2;   //2byte    uint16_t        vehicle_altitude
    big_reverse_copy(pcInput + n,  pOut->Danger_signs                           );      n += 1;   //1byte    uint8_t         Danger_signs
    SPStringDeserialization(pcInput, pOut->POI_information,                n);             //        string    POI_information
    SPStringDeserialization(pcInput, pOut->reach_the_destination,          n);             //        string    reach_the_destination
    SPStringDeserialization(pcInput, pOut->ETA_info_time,                  n);             //        string    ETA_info_time
    SPStringDeserialization(pcInput, pOut->ETA_info_remain_time,           n);             //        string    ETA_info_remain_time
    big_reverse_copy(pcInput + n,  pOut->RecommendedDrivingDirectionsId         );      n += 2;   //2byte    uint16_t        RecommendedDrivingDirectionsId
    SPStringDeserialization(pcInput, pOut->lanesPermissibleDirectionId,    n);             //        string    lanesPermissibleDirectionId
    SPStringDeserialization(pcInput, pOut->guideLine,                      n);             //        string    guideLine
    SPStringDeserialization(pcInput, pOut->guidePoint,                     n);             //        string    guidePoint
    big_reverse_copy(pcInput + n,  pOut->vehicleHeading                         );      n += 8;   //8byte    double          vehicleHeading
    big_reverse_copy(pcInput + n,  pOut->Navigating_ratio                       );      n += 8;   //8byte    double          Navigating_ratio
    big_reverse_copy(pcInput + n,  pOut->mapProviders                           );      n += 1;   //1byte    uint8_t         mapProviders
    SPStringDeserialization(pcInput, pOut->carToDestDistance,              n);             //        string    carToDestDistance
    SPStringDeserialization(pcInput, pOut->distanceToIntersection,         n);             //        string    distanceToIntersection
    SPStringDeserialization(pcInput, pOut->timeToDest,                     n);             //        string    timeToDest
    big_reverse_copy(pcInput + n,  pOut->recommendedDrivingDirectionsIdOverseas );      n += 2;   //2byte    uint16_t        recommendedDrivingDirectionsIdOverseas

    big_reverse_copy(pcInput + n,  pOut->reservedDataLength1);      n += 4;   //4byte   uint32     reservedDataLength1
    if (pOut->reservedDataLength1 > 0)
    {
        int count = pOut->reservedDataLength1 / sizeof(uint8_t);
        pOut->reserved1 = new uint8_t[count];
        memset(pOut->reserved1, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcInput + n, *(pOut->reserved1+i)); n += 1; //4byte   uint32  reserved1
        }
    }

    big_reverse_copy(pcInput + n,  pOut->reservedDataLength2);      n += 4;   //4byte   uint32     reservedDataLength2
    if (pOut->reservedDataLength2 > 0)
    {
        int count = pOut->reservedDataLength2 / sizeof(uint16_t);
        pOut->reserved2 = new uint16_t[count];
        memset(pOut->reserved2, 0, sizeof(uint16_t)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcInput + n, *(pOut->reserved2+i)); n += 1; //4byte   uint32  reserved2
        }
    }

    big_reverse_copy(pcInput + n,  pOut->reservedDataLength3);      n += 4;   //4byte   uint32     reservedDataLength3
    if (pOut->reservedDataLength3 > 0)
    {
        int count = pOut->reservedDataLength3 / sizeof(uint32_t);
        pOut->reserved3 = new uint32_t[count];
        memset(pOut->reserved3, 0, sizeof(uint32_t)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcInput + n, *(pOut->reserved3+i)); n += 1; //4byte   uint32  reserved3
        }
    }

    big_reverse_copy(pcInput + n,  pOut->reservedDataLength4);      n += 4;   //4byte   uint32     reservedDataLength4
    if (pOut->reservedDataLength4 > 0)
    {
        int count = pOut->reservedDataLength4 / sizeof(double);
        pOut->reserved4 = new double[count];
        memset(pOut->reserved4, 0, sizeof(double)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcInput + n, *(pOut->reserved4+i)); n += 1; //4byte   uint32  reserved4
        }
    }

    big_reverse_copy(pcInput + n,  pOut->reservedDataLength5);      n += 4;   //4byte   uint32     reservedDataLength5
    if (pOut->reservedDataLength5 > 0)
    {
        int count = pOut->reservedDataLength5 / sizeof(float);
        pOut->reserved5 = new float[count];
        memset(pOut->reserved1, 0, sizeof(float)*count);
        for (int i = 0; i < count; ++i)
        {
            big_reverse_copy(pcInput + n, *(pOut->reserved5+i)); n += 1; //4byte   uint32  reserved5
        }
    }
}

// HudMappathInfo_EG
void HudMappathInfo_EGDeserialization(const char* pcIn, std::shared_ptr<stHudMappathInfo_EG> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                            );      n += 4;   //4byte   uint32    Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                             );      n += 2;   //2byte   uint16    Counter
    big_reverse_copy(pcIn + n,  pOut->is_on_the_path                      );      n += 1;   //1byte   uint8     is_on_the_path
    big_reverse_copy(pcIn + n,  pOut->road_angle                          );      n += 1;   //1byte   uint8     road_angle
    big_reverse_copy(pcIn + n,  pOut->road_slope                          );      n += 4;   //4byte   float32   road_slope
    SPStringDeserialization(pcIn, pOut->all_EHP_v2_info, n);                                //*byte   string    all_EHP_v2_info
}

// HudNavigationmap
void HudNavigationmapDeserialization(const char* pcIn, std::shared_ptr<stHudNavigationmap> pOut)
{
    int n = 0;
    if (pOut->Navigation_map_len > 0)
    {
        SPStringDeserialization(pcIn, pOut->Navigation_map, n);
        pOut->Navigation_map_len = pOut->Navigation_map.length();
    }
}



//14.NewLanelineDataNotify
void NewLanelineDataNotifySerialization(std::shared_ptr<stNewLanelineDataNotify> pIn, char* pcOut)
{
    int n = 0, count = 0;
    sp_big_reverse_copy(pIn->Checksum             ,pcOut + n, 4);      n += 4;   //4byte    uint32   Checksum
    sp_big_reverse_copy(pIn->Counter              ,pcOut + n, 2);      n += 2;   //2byte    uint16   Counter

    sp_big_reverse_copy(pIn->FieldLength_Line_len ,pcOut + n, 4);      n += 4;   //4byte    uint32_t   FieldLength_Line_len
    if (pIn->FieldLength_Line_len > 0) //FieldLength_Line
    {
        count = pIn->FieldLength_Line_len / sizeof(stNLLDN_FieldLength_Line);
        int tt = sizeof(stNLLDN_FieldLength_Line);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->New_LineID             ,pcOut + n, 4);      n += 4;   //4byte   int32_t    New_LineID          
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->LineID                 ,pcOut + n, 4);      n += 4;   //4byte   int32_t    LineID              
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->LineType               ,pcOut + n, 1);      n += 1;   //1byte   uint8_t    LineType            
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->New_LineWarningColor   ,pcOut + n, 1);      n += 1;   //1byte   uint8_t    New_LineWarningColor
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->LineColor              ,pcOut + n, 1);      n += 1;   //1byte   uint8_t    LineColor           
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->LineWidth              ,pcOut + n, 4);      n += 4;   //4byte   float      LineWidth           
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_confidence        ,pcOut + n, 8);      n += 8;   //8byte   double     Line_confidence     
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->CurvatureEquation_c0   ,pcOut + n, 4);      n += 4;   //4byte   float      CurvatureEquation_c0
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->CurvatureEquation_c1   ,pcOut + n, 4);      n += 4;   //4byte   float      CurvatureEquation_c1
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->CurvatureEquation_c2   ,pcOut + n, 4);      n += 4;   //4byte   float      CurvatureEquation_c2
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->CurvatureEquation_c3   ,pcOut + n, 4);      n += 4;   //4byte   float      CurvatureEquation_c3
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Startpoint_x      ,pcOut + n, 4);      n += 4;   //4byte   float      Line_Startpoint_x   
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Startpoint_y      ,pcOut + n, 4);      n += 4;   //4byte   float      Line_Startpoint_y   
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Startpoint_z      ,pcOut + n, 4);      n += 4;   //4byte   float      Line_Startpoint_z   
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Endpoint_x        ,pcOut + n, 4);      n += 4;   //4byte   float      Line_Endpoint_x     
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Endpoint_y        ,pcOut + n, 4);      n += 4;   //4byte   float      Line_Endpoint_y     
            sp_big_reverse_copy((pIn->FieldLength_Line+i)->Line_Endpoint_z        ,pcOut + n, 4);      n += 4;   //4byte   float      Line_Endpoint_z 

            sp_big_reverse_copy((pIn->FieldLength_Line+i)->New_FieldLength_LinePoints_len ,pcOut + n, 4);      n += 4;   //4byte    uint32_t   New_FieldLength_LinePoints_len
            if ((pIn->FieldLength_Line+i)->New_FieldLength_LinePoints_len > 0) //stNLLDN_New_FieldLength_LinePoints
            {
                count = (pIn->FieldLength_Line+i)->New_FieldLength_LinePoints_len / sizeof(stNLLDN_New_FieldLength_LinePoints);
                int tt = sizeof(stNLLDN_New_FieldLength_LinePoints);
                for (int i = 0; i < count; ++i)
                {
                    sp_big_reverse_copy(((pIn->FieldLength_Line+i)->New_FieldLength_LinePoints+i)->New_LinePointsID_i   ,pcOut + n, 4);      n += 4;   //4byte   uint32_t      New_LinePointsID_i
                    sp_big_reverse_copy(((pIn->FieldLength_Line+i)->New_FieldLength_LinePoints+i)->New_LinePoints_X     ,pcOut + n, 8);      n += 8;   //8byte   double        New_LinePoints_X  
                    sp_big_reverse_copy(((pIn->FieldLength_Line+i)->New_FieldLength_LinePoints+i)->New_LinePoints_Y     ,pcOut + n, 8);      n += 8;   //8byte   double        New_LinePoints_Y  
                    sp_big_reverse_copy(((pIn->FieldLength_Line+i)->New_FieldLength_LinePoints+i)->New_LinePoints_Z     ,pcOut + n, 8);      n += 8;   //8byte   double        New_LinePoints_Z   
                }
            }    
        }
    }



    sp_big_reverse_copy(pIn->FieldLength_TLA_len ,pcOut + n, 4);      n += 4;   //4byte    uint32_t   FieldLength_TLA_len
    if (pIn->FieldLength_TLA_len > 0) //FieldLength_TLA
    {
        count = pIn->FieldLength_TLA_len / sizeof(stNLLDN_FieldLength_TLA);
        int tt = sizeof(stNLLDN_FieldLength_TLA);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLAID_i                    ,pcOut + n, 4);      n += 4;   //4byte   uint32_t      TLAID_i
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Distance_X             ,pcOut + n, 8);      n += 8;   //8byte   double        TLA_Distance_X
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Distance_Y             ,pcOut + n, 8);      n += 8;   //8byte   double        TLA_Distance_Y
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Distance_Z             ,pcOut + n, 8);      n += 8;   //8byte   double        TLA_Distance_Z
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLAPosition_confidence     ,pcOut + n, 8);      n += 8;   //8byte   double        TLAPosition_confidence
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->LeftTLA_Color              ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       LeftTLA_Color
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->LeftTLA_Type               ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       LeftTLA_Type
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->StraightTLA_Color          ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       StraightTLA_Color
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->StraightTLA_Type           ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       StraightTLA_Type
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->RightTLA_Color             ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       RightTLA_Color
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->RightTLA_Type              ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       RightTLA_Type
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->New_LeftTLA_Second         ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       New_LeftTLA_Second
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->New_StraightTLA_Second     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       New_StraightTLA_Second
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->New_RightTLA_Second        ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       New_RightTLA_Second
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Reserved1              ,pcOut + n, 8);      n += 8;   //8byte   double        TLA_Reserved1
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Reserved2              ,pcOut + n, 8);      n += 8;   //8byte   double        TLA_Reserved2
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Reserved3              ,pcOut + n, 8);      n += 8;   //8byte   double        TLA_Reserved3
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Reserved4              ,pcOut + n, 8);      n += 8;   //8byte   double        TLA_Reserved4
            sp_big_reverse_copy((pIn->FieldLength_TLA+i)->TLA_Reserved5              ,pcOut + n, 8);      n += 8;   //8byte   double        TLA_Reserved5
        }
    }

    sp_big_reverse_copy(pIn->New_FieldLength_TSR_len ,pcOut + n, 4);      n += 4;   //4byte    uint32_t   New_FieldLength_TSR_len
    if (pIn->New_FieldLength_TSR_len > 0) //stNLLDN_New_FieldLength_TSR
    {
        count = pIn->New_FieldLength_TSR_len / sizeof(stNLLDN_New_FieldLength_TSR);
        int tt = sizeof(stNLLDN_New_FieldLength_TSR);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->New_TSRID_i                ,pcOut + n, 4);      n += 4;   //4byte   uint32_t      New_TSRID_i
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->New_TSR_Distance_X         ,pcOut + n, 8);      n += 8;   //8byte   double        New_TSR_Distance_X
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->New_TSR_Distance_Y         ,pcOut + n, 8);      n += 8;   //8byte   double        New_TSR_Distance_Y
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->New_TSR_Distance_Z         ,pcOut + n, 8);      n += 8;   //8byte   double        New_TSR_Distance_Z
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->New_TSRPosition_confidence ,pcOut + n, 8);      n += 8;   //8byte   double        New_TSRPosition_confidence
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->New_TSR_Type               ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       New_TSR_Type
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->New_Speed_Limit            ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       New_Speed_Limit
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->tolColor                   ,pcOut + n, 8);      n += 8;   //8byte   double        tolColor
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->tsrHeading                 ,pcOut + n, 8);      n += 8;   //8byte   double        tsrHeading
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->TSR_Reserved3              ,pcOut + n, 8);      n += 8;   //8byte   double        TSR_Reserved3
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->TSR_Reserved4              ,pcOut + n, 8);      n += 8;   //8byte   double        TSR_Reserved4
            sp_big_reverse_copy((pIn->New_FieldLength_TSR+i)->TSR_Reserved5              ,pcOut + n, 8);      n += 8;   //8byte   double        TSR_Reserved5
        }
    }

    sp_big_reverse_copy(pIn->FieldLength_LanelineReserved_len ,pcOut + n, 4);      n += 4;   //4byte    uint32_t   FieldLength_LanelineReserved_len
    if (pIn->FieldLength_LanelineReserved_len > 0) //stNLLDN_FieldLength_LanelineReserved
    {
        count = pIn->FieldLength_LanelineReserved_len / sizeof(stNLLDN_FieldLength_LanelineReserved);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_LanelineReserved+i)->Reserved1               ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       Reserved1
        }
    }
}

void NewLanelineDataNotifyDeserialization(const char* pcIn, std::shared_ptr<stNewLanelineDataNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                              );      n += 4;   //4byte   uint32    Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                               );      n += 2;   //2byte   uint16_t  Counter

    big_reverse_copy(pcIn + n,  pOut->FieldLength_Line_len                  );      n += 4;   //4byte   uint32     fieldLength_Line

    uint32_t count_byte = 0;
    int tt1 = 0;

    if (pOut->FieldLength_Line_len > 0)
    {
        int count = pOut->FieldLength_Line_len / sizeof(stNLLDN_FieldLength_Line);
        int tt = sizeof(stNLLDN_FieldLength_Line);
        pOut->FieldLength_Line = new stNLLDN_FieldLength_Line[count];
        memset(pOut->FieldLength_Line, 0, sizeof(stNLLDN_FieldLength_Line)*count);
        
        for (int i = 0; pOut->FieldLength_Line_len > count_byte; ++i) //new_lineidobj
        {
            uint32_t len = 0;
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->New_LineID          ); n += 4; count_byte += 4; len += 4; //4byte   int32_t    New_LineID          
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->LineID              ); n += 4; count_byte += 4; len += 4; //4byte   int32_t    LineID              
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->LineType            ); n += 1; count_byte += 1; len += 1; //1byte   uint8_t    LineType            
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->New_LineWarningColor); n += 1; count_byte += 1; len += 1; //1byte   uint8_t    New_LineWarningColor
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->LineColor           ); n += 1; count_byte += 1; len += 1; //1byte   uint8_t    LineColor           
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->LineWidth           ); n += 4; count_byte += 4; len += 4; //4byte   float      LineWidth           
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->Line_confidence     ); n += 8; count_byte += 8; len += 8; //8byte   double     Line_confidence     
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->CurvatureEquation_c0); n += 4; count_byte += 4; len += 4; //4byte   float      CurvatureEquation_c0
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->CurvatureEquation_c1); n += 4; count_byte += 4; len += 4; //4byte   float      CurvatureEquation_c1
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->CurvatureEquation_c2); n += 4; count_byte += 4; len += 4; //4byte   float      CurvatureEquation_c2
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->CurvatureEquation_c3); n += 4; count_byte += 4; len += 4; //4byte   float      CurvatureEquation_c3
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->Line_Startpoint_x   ); n += 4; count_byte += 4; len += 4; //4byte   float      Line_Startpoint_x   
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->Line_Startpoint_y   ); n += 4; count_byte += 4; len += 4; //4byte   float      Line_Startpoint_y   
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->Line_Startpoint_z   ); n += 4; count_byte += 4; len += 4; //4byte   float      Line_Startpoint_z   
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->Line_Endpoint_x     ); n += 4; count_byte += 4; len += 4; //4byte   float      Line_Endpoint_x     
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->Line_Endpoint_y     ); n += 4; count_byte += 4; len += 4; //4byte   float      Line_Endpoint_y     
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->Line_Endpoint_z     ); n += 4; count_byte += 4; len += 4; //4byte   float      Line_Endpoint_z
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->New_FieldLength_LinePoints_len); n += 4; count_byte += 4; len += 4; //4byte   uint32     fieldLength_new_LinePoints
       
            if ((pOut->FieldLength_Line+i)->New_FieldLength_LinePoints_len > 0)
            {
                int count1 = (pOut->FieldLength_Line+i)->New_FieldLength_LinePoints_len / sizeof(stNLLDN_New_FieldLength_LinePoints);
                int tt1 = sizeof(stNLLDN_New_FieldLength_LinePoints);
                (pOut->FieldLength_Line + i)->New_FieldLength_LinePoints = new stNLLDN_New_FieldLength_LinePoints[count1];
                memset((pOut->FieldLength_Line + i)->New_FieldLength_LinePoints, 0, sizeof(stNLLDN_New_FieldLength_LinePoints) * count1);

                for (int j = 0; j < count1; ++j) //new_linepoint
                {
                    big_reverse_copy(pcIn + n, ((pOut->FieldLength_Line + i)->New_FieldLength_LinePoints + j)->New_LinePointsID_i); n += 4;  count_byte += 4;  len += 4; //4byte   uint32_t      New_LinePointsID_i
                    big_reverse_copy(pcIn + n, ((pOut->FieldLength_Line + i)->New_FieldLength_LinePoints + j)->New_LinePoints_X);   n += 8;  count_byte += 8;  len += 8; //8byte   double        New_LinePoints_X
                    big_reverse_copy(pcIn + n, ((pOut->FieldLength_Line + i)->New_FieldLength_LinePoints + j)->New_LinePoints_Y);   n += 8;  count_byte += 8;  len += 8; //8byte   double        New_LinePoints_Y
                    big_reverse_copy(pcIn + n, ((pOut->FieldLength_Line + i)->New_FieldLength_LinePoints + j)->New_LinePoints_Z);   n += 8;  count_byte += 8;  len += 8; //8byte   double        New_LinePoints_Z
                }
            }

            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->sys_time_us       ); n += 8; count_byte += 8;  len += 8; //8byte   double        sys_time_us   
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->lineI_Reserved1   ); n += 8; count_byte += 8;  len += 8; //8byte   double        LineI_Reserved1                  
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->lineI_Reserved2   ); n += 8; count_byte += 8;  len += 8; //8byte   double        LineI_Reserved2   
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->lineI_Reserved3   ); n += 8; count_byte += 8;  len += 8; //8byte   double        LineI_Reserved3   
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->lineI_Reserved4   ); n += 8; count_byte += 8;  len += 8; //8byte   double        LineI_Reserved4   
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Line+i)->lineI_Reserved5   ); n += 8; count_byte += 8;  len += 8; //8byte   double        LineI_Reserved5   
            (pOut->FieldLength_Line+i)->len = len;
            tt1++;
        }        
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_TLA_len);      n += 4;   //4byte   uint32     fieldlength_tla
    if (pOut->FieldLength_TLA_len > 0)
    {
        int count = pOut->FieldLength_TLA_len / sizeof(stNLLDN_FieldLength_TLA);
        int tt = sizeof(stNLLDN_FieldLength_TLA);
        pOut->FieldLength_TLA = new stNLLDN_FieldLength_TLA[count];
        memset(pOut->FieldLength_TLA, 0, sizeof(stNLLDN_FieldLength_TLA)*count);
        for (int i = 0; i < count; ++i) //new_tlaid_i_obj
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLAID_i                   ); n += 4;   //4byte   uint32_t      TLAID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLA_Distance_X            ); n += 8;   //8byte   double        TLA_Distance_X
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLA_Distance_Y            ); n += 8;   //8byte   double        TLA_Distance_Y
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLA_Distance_Z            ); n += 8;   //8byte   double        TLA_Distance_Z
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLAPosition_confidence    ); n += 8;   //8byte   double        TLAPosition_confidence
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->LeftTLA_Color             ); n += 1;   //1byte   uint8_t       LeftTLA_Color
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->LeftTLA_Type              ); n += 1;   //1byte   uint8_t       LeftTLA_Type
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->StraightTLA_Color         ); n += 1;   //1byte   uint8_t       StraightTLA_Color
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->StraightTLA_Type          ); n += 1;   //1byte   uint8_t       StraightTLA_Type
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->RightTLA_Color            ); n += 1;   //1byte   uint8_t       RightTLA_Color
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->RightTLA_Type             ); n += 1;   //1byte   uint8_t       RightTLA_Type
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->New_LeftTLA_Second        ); n += 1;   //1byte   uint8_t       New_LeftTLA_Second
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->New_StraightTLA_Second    ); n += 1;   //1byte   uint8_t       New_StraightTLA_Second
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->New_RightTLA_Second       ); n += 1;   //1byte   uint8_t       New_RightTLA_Second
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLA_Reserved1             ); n += 8;   //8byte   double        TLA_Reserved1
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLA_Reserved2             ); n += 8;   //8byte   double        TLA_Reserved2
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLA_Reserved3             ); n += 8;   //8byte   double        TLA_Reserved3
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLA_Reserved4             ); n += 8;   //8byte   double        TLA_Reserved4
            big_reverse_copy(pcIn + n, (pOut->FieldLength_TLA+i)->TLA_Reserved5             ); n += 8;   //8byte   double        TLA_Reserved5
        }
    }

    big_reverse_copy(pcIn + n,  pOut->New_FieldLength_TSR_len);      n += 4;   //4byte   uint32     fieldlength_tsr
    if (pOut->New_FieldLength_TSR_len > 0)
    {
        int count = pOut->New_FieldLength_TSR_len / sizeof(stNLLDN_New_FieldLength_TSR);
        int tt = sizeof(stNLLDN_New_FieldLength_TSR);
        pOut->New_FieldLength_TSR = new stNLLDN_New_FieldLength_TSR[count];
        memset(pOut->New_FieldLength_TSR, 0, sizeof(stNLLDN_New_FieldLength_TSR)*count);
        for (int i = 0; i < count; ++i) //New_FieldLength_TSR
        {  
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->New_TSRID_i                   ); n += 4;   //4byte   uint32_t      New_TSRID_i
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->New_TSR_Distance_X            ); n += 8;   //8byte   double        New_TSR_Distance_X
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->New_TSR_Distance_Y            ); n += 8;   //8byte   double        New_TSR_Distance_Y
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->New_TSR_Distance_Z            ); n += 8;   //8byte   double        New_TSR_Distance_Z
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->New_TSRPosition_confidence    ); n += 8;   //8byte   double        New_TSRPosition_confidence
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->New_TSR_Type                  ); n += 1;   //1byte   uint8_t       New_TSR_Type
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->New_Speed_Limit               ); n += 1;   //1byte   uint8_t       New_Speed_Limit
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->tolColor                      ); n += 8;   //8byte   double        tolColor
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->tsrHeading                    ); n += 8;   //8byte   double        tsrHeading
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->TSR_Reserved3                 ); n += 8;   //8byte   double        TSR_Reserved3
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->TSR_Reserved4                 ); n += 8;   //8byte   double        TSR_Reserved4
            big_reverse_copy(pcIn + n, (pOut->New_FieldLength_TSR+i)->TSR_Reserved5                 ); n += 8;   //8byte   double        TSR_Reserved5
        }
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_LanelineReserved_len);      n += 4;   //4byte   uint32     fieldLength_LanelineReserved
}

//15.NewBroadcastInfoNotify
void NewBroadcastInfoNotifySerialization(std::shared_ptr<stNewBroadcastInfoNotify> pIn, char* pcOut)
{
    int n = 0;
    sp_big_reverse_copy(pIn->Checksum                   ,pcOut + n, 4);      n += 4;   //4byte    uint32_t   Checksum
    sp_big_reverse_copy(pIn->Counter                    ,pcOut + n, 2);      n += 2;   //2byte    uint16_t   Counter
    sp_big_reverse_copy(pIn->NOAMode                    ,pcOut + n, 2);      n += 2;   //2byte    uint16_t   NOAMode
    sp_big_reverse_copy(pIn->notice                     ,pcOut + n, 2);      n += 2;   //2byte    uint16_t   notice
    sp_big_reverse_copy(pIn->Info_Reserved1             ,pcOut + n, 8);      n += 8;   //8byte    double     Info_Reserved1
    sp_big_reverse_copy(pIn->Info_Reserved2             ,pcOut + n, 8);      n += 8;   //8byte    double     Info_Reserved2
    sp_big_reverse_copy(pIn->Info_Reserved3             ,pcOut + n, 8);      n += 8;   //8byte    double     Info_Reserved3
    sp_big_reverse_copy(pIn->Info_Reserved4             ,pcOut + n, 8);      n += 8;   //8byte    double     Info_Reserved4
    sp_big_reverse_copy(pIn->Info_Reserved5             ,pcOut + n, 8);      n += 8;   //8byte    double     Info_Reserved5
}

void NewBroadcastInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stNewBroadcastInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                      );      n += 4;   //4byte    uint32_t   Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                       );      n += 2;   //2byte    uint16_t   Counter
    big_reverse_copy(pcIn + n,  pOut->NOAMode                       );      n += 2;   //2byte    uint16_t   NOAMode
    big_reverse_copy(pcIn + n,  pOut->notice                        );      n += 2;   //2byte    uint16_t   notice
    big_reverse_copy(pcIn + n,  pOut->Info_Reserved1                );      n += 8;   //8byte    double     Info_Reserved1
    big_reverse_copy(pcIn + n,  pOut->Info_Reserved2                );      n += 8;   //8byte    double     Info_Reserved2
    big_reverse_copy(pcIn + n,  pOut->Info_Reserved3                );      n += 8;   //8byte    double     Info_Reserved3
    big_reverse_copy(pcIn + n,  pOut->Info_Reserved4                );      n += 8;   //8byte    double     Info_Reserved4
    big_reverse_copy(pcIn + n,  pOut->Info_Reserved5                );      n += 8;   //8byte    double     Info_Reserved5
}

//16.PlanningLineInfoNotify
void PlanningLineInfoNotifySerialization(std::shared_ptr<stPlanningLineInfoNotify> pIn, char* pcOut)
{
    int n = 0, count = 0;
    sp_big_reverse_copy(pIn->Checksum                           ,pcOut + n, 4);      n += 4;   //4byte    uint32_t   Checksum
    sp_big_reverse_copy(pIn->Counter                            ,pcOut + n, 2);      n += 2;   //2byte    uint16_t   Counter
    sp_big_reverse_copy(pIn->PlanningLineStatus                 ,pcOut + n, 1);      n += 1;   //1byte    bool       PlanningLineStatus
    sp_big_reverse_copy(pIn->planning_timestamp                 ,pcOut + n, 8);      n += 8;   //8byte    double     planning_timestamp
    
    sp_big_reverse_copy(pIn->FieldLength_PlanningLinePoints_len ,pcOut + n, 4);      n += 4;   //4byte    uint32_t   FieldLength_PlanningLinePoints_len
    if (pIn->FieldLength_PlanningLinePoints_len > 0) //FieldLength_PlanningLinePoints
    {
        count = pIn->FieldLength_PlanningLinePoints_len / sizeof(stPlanningLineInfoNotifyFPLP);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_PlanningLinePoints+i)->PlanningLinePointsID_i ,pcOut + n, 4);      n += 4;   //4byte   uint32_t    PlanningLinePointsID_i
            sp_big_reverse_copy((pIn->FieldLength_PlanningLinePoints+i)->points_X               ,pcOut + n, 8);      n += 8;   //8byte   double      points_X
            sp_big_reverse_copy((pIn->FieldLength_PlanningLinePoints+i)->points_Y               ,pcOut + n, 8);      n += 8;   //8byte   double      points_Y
            sp_big_reverse_copy((pIn->FieldLength_PlanningLinePoints+i)->points_Z               ,pcOut + n, 8);      n += 8;   //8byte   double      points_Z
        }
    }
}

void PlanningLineInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stPlanningLineInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                              );      n += 4;   //4byte    uint32_t   Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                               );      n += 2;   //2byte    uint16_t   Counter
    big_reverse_copy(pcIn + n,  pOut->PlanningLineStatus                    );      n += 1;   //2byte    uint16_t   NOAMode
    big_reverse_copy(pcIn + n,  pOut->planning_timestamp                    );      n += 8;   //2byte    uint16_t   notice
    
    big_reverse_copy(pcIn + n,  pOut->FieldLength_PlanningLinePoints_len    );      n += 4;   //4byte    uint32_t   FieldLength_PlanningLinePoints_len
    if (pOut->FieldLength_PlanningLinePoints_len > 0)
    {
        int count = pOut->FieldLength_PlanningLinePoints_len / sizeof(stPlanningLineInfoNotifyFPLP);
        int tt = sizeof(stPlanningLineInfoNotifyFPLP);
        pOut->FieldLength_PlanningLinePoints = new stPlanningLineInfoNotifyFPLP[count];
        memset(pOut->FieldLength_PlanningLinePoints, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_PlanningLinePoints
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_PlanningLinePoints+i)->PlanningLinePointsID_i  ); n += 4;   //4byte   uint32_t    PlanningLinePointsID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_PlanningLinePoints+i)->points_X                ); n += 8;   //8byte   double      points_X
            big_reverse_copy(pcIn + n, (pOut->FieldLength_PlanningLinePoints+i)->points_Y                ); n += 8;   //8byte   double      points_Y
            big_reverse_copy(pcIn + n, (pOut->FieldLength_PlanningLinePoints+i)->points_Z                ); n += 8;   //8byte   double      points_Z
        }
    }
}

//17.NavigationStatus_LinkInfoNotify
void NavigationStatus_LinkInfoNotifySerialization(std::shared_ptr<stNavigationStatus_LinkInfoNotify> pIn, char* pcOut)
{
    int n = 0;
    sp_big_reverse_copy(pIn->Checksum                    ,pcOut + n, 4);      n += 4;   //4byte    uint32_t      Checksum
    sp_big_reverse_copy(pIn->Counter                     ,pcOut + n, 2);      n += 2;   //2byte    uint16_t      Counter
    sp_big_reverse_copy(pIn->timestamp                   ,pcOut + n, 8);      n += 8;   //8byte    double        timestamp
    sp_big_reverse_copy(pIn->NavigationStatus            ,pcOut + n, 1);      n += 1;   //1byte    uint8_t       NavigationStatus
    sp_big_reverse_copy(pIn->MatchingTableStatus         ,pcOut + n, 1);      n += 1;   //1byte    uint8_t       MatchingTableStatus
    sp_big_reverse_copy(pIn->RemainDistance              ,pcOut + n, 4);      n += 4;   //4byte    uint32_t      RemainDistance
    sp_big_reverse_copy(pIn->ViaPointDistance            ,pcOut + n, 4);      n += 4;   //4byte    uint32_t      ViaPointDistance
    sp_big_reverse_copy(pIn->HDStartDistance             ,pcOut + n, 4);      n += 4;   //4byte    uint32_t      HDStartDistance
    sp_big_reverse_copy(pIn->DNP_Switch                  ,pcOut + n, 1);      n += 1;   //1byte    uint8_t       DNP_Switch
    sp_big_reverse_copy(pIn->ANP_road                    ,pcOut + n, 1);      n += 1;   //1byte    uint8_t       ANP_road
    sp_big_reverse_copy(pIn->MapVersion                  ,pcOut + n, 4);      n += 4;   //4byte    uint32_t      MapVersion
    sp_big_reverse_copy(pIn->FieldLength_LinK            ,pcOut + n, 4);      n += 4;   //4byte    uint32_t      FieldLength_LinK
    if (pIn->FieldLength_LinK > 0)
    {
        int count = pIn->FieldLength_LinK / sizeof(uint64_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy(pIn->LinkID ,pcOut + n, 8);      n += 8;   //8byte   uint64_t    LinkID
        }
    }
}

void NavigationStatus_LinkInfoNotifyDeserialization(const char* pcIn, std::shared_ptr<stNavigationStatus_LinkInfoNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                      );      n += 4;   //4byte    uint32_t      Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                       );      n += 2;   //2byte    uint16_t      Counter
    big_reverse_copy(pcIn + n,  pOut->timestamp                     );      n += 8;   //8byte    double        timestamp
    big_reverse_copy(pcIn + n,  pOut->NavigationStatus              );      n += 1;   //1byte    uint8_t       NavigationStatus
    big_reverse_copy(pcIn + n,  pOut->MatchingTableStatus           );      n += 1;   //1byte    uint8_t       MatchingTableStatus
    big_reverse_copy(pcIn + n,  pOut->RemainDistance                );      n += 4;   //4byte    uint32_t      RemainDistance
    big_reverse_copy(pcIn + n,  pOut->ViaPointDistance              );      n += 4;   //4byte    uint32_t      ViaPointDistance
    big_reverse_copy(pcIn + n,  pOut->HDStartDistance               );      n += 4;   //4byte    uint32_t      HDStartDistance
    big_reverse_copy(pcIn + n,  pOut->DNP_Switch                    );      n += 1;   //1byte    uint8_t       DNP_Switch
    big_reverse_copy(pcIn + n,  pOut->ANP_road                      );      n += 1;   //1byte    uint8_t       ANP_road
    big_reverse_copy(pcIn + n,  pOut->MapVersion                    );      n += 4;   //4byte    uint32_t      MapVersion
    big_reverse_copy(pcIn + n,  pOut->FieldLength_LinK              );      n += 4;   //4byte    uint32_t      FieldLength_LinK
    big_reverse_copy(pcIn + n,  pOut->LinkID                        );      n += 8;   //8byte    uint64_t      LinkID
    if (pOut->FieldLength_LinK > 0)
    {
        int count = pOut->FieldLength_LinK / sizeof(uint64_t);
        pOut->LinkID = new uint64_t[count];
        memset(pOut->LinkID, 0, sizeof(uint64_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_PlanningLinePoints
        {
            big_reverse_copy(pcIn + n, pOut->LinkID  ); n += 8;   //8byte   uint64_t    LinkID
        }
    }

    // big_reverse_copy(pcIn + n,  pOut->reserve1                      );      n += 8;   //8byte    uint64_t      reserve1
    // big_reverse_copy(pcIn + n,  pOut->reserve2                      );      n += 4;   //4byte    uint32_t      reserve2
    // big_reverse_copy(pcIn + n,  pOut->reserve3                      );      n += 4;   //4byte    float         reserve3
}

//18.NewParkingRealTimeDataNotify
void NewParkingRealTimeDataNotifySerialization(std::shared_ptr<stNewParkingRealTimeDataNotify> pIn, char* pcOut)
{
    int n = 0, count = 0;
    sp_big_reverse_copy(pIn->Checksum                           ,pcOut + n, 4);      n += 4;   //4byte    uint32_t      Checksum
    sp_big_reverse_copy(pIn->Counter                            ,pcOut + n, 2);      n += 2;   //2byte    uint16_t      Counter
    sp_big_reverse_copy(pIn->timestamp                          ,pcOut + n, 8);      n += 8;   //8byte    double        timestamp

    sp_big_reverse_copy(pIn->FieldLength_Object_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     FieldLength_Object_len
    if (pIn->FieldLength_Object_len > 0) //FieldLength_Object
    {
        count = pIn->FieldLength_Object_len / sizeof(stFieldLength_ObjectNPRTDN);
        int tt = sizeof(stFieldLength_ObjectNPRTDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->ObjectID_i                     ,pcOut + n, 8);      n += 8;   //8byte   uint64_t      ObjectID_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->shape_height_i                 ,pcOut + n, 8);      n += 8;   //8byte   double        shape_height_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->shape_length_i                 ,pcOut + n, 8);      n += 8;   //8byte   double        shape_length_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->shape_width_i                  ,pcOut + n, 8);      n += 8;   //8byte   double        shape_width_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->position_x_i                   ,pcOut + n, 4);      n += 4;   //4byte   double        position_x_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->position_y_i                   ,pcOut + n, 8);      n += 8;   //8byte   double        position_y_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->position_z_i                   ,pcOut + n, 8);      n += 8;   //8byte   double        position_z_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->Heading_i                      ,pcOut + n, 4);      n += 4;   //4byte   float32       Heading_i
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->TypeInfo                       ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       TypeInfo
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->CrashRisk                      ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       CrashRisk
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->NewMoveST                      ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       NewMoveST
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->NewAbsoluteVelocity            ,pcOut + n, 2);      n += 2;   //2byte   uint16_t      NewAbsoluteVelocity
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->NewTurnSignalLampSt            ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       NewTurnSignalLampSt
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->NewHigh_lowBeamLampsSt         ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       NewHigh_lowBeamLampsSt
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->NewBrakeLightSt                ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       NewBrakeLightSt
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->NewReversingLightSt            ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       NewReversingLightSt
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->ParkingObjectInfo_Reserved1    ,pcOut + n, 8);      n += 8;   //8byte   double        ParkingObjectInfo_Reserved1
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->blockingBarStatus              ,pcOut + n, 8);      n += 8;   //8byte   double        blockingBarStatus
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->blockingBarTypeInfo            ,pcOut + n, 8);      n += 8;   //8byte   double        blockingBarTypeInfo
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->blockingBarDirInfo             ,pcOut + n, 8);      n += 8;   //8byte   double        blockingBarDirInfo
            sp_big_reverse_copy((pIn->FieldLength_Object+i)->ParkingObjectInfo_Reserved5    ,pcOut + n, 8);      n += 8;   //8byte   double        ParkingObjectInfo_Reserved5
        }
    }

    sp_big_reverse_copy(pIn->FieldLength_ParkingSlot_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     FieldLength_ParkingSlot_len
    if (pIn->FieldLength_ParkingSlot_len > 0) //FieldLength_ParkingSlot
    {
        count = pIn->FieldLength_ParkingSlot_len / sizeof(stFieldLength_ParkingSlotNPRTDN);
        int tt = sizeof(stFieldLength_ParkingSlotNPRTDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->ParkngSpcID_i                 ,pcOut + n, 4);      n += 4;   //4byte   uint32_t      ParkngSpcID_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->ParkngSpcSts                  ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       ParkngSpcSts
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->ParkngSpcCode_i               ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       ParkngSpcCode_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->x1_i                          ,pcOut + n, 4);      n += 4;   //4byte   float32       x1_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->y1_i                          ,pcOut + n, 4);      n += 4;   //4byte   float32       y1_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->x2_i                          ,pcOut + n, 4);      n += 4;   //4byte   float32       x2_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->y2_i                          ,pcOut + n, 4);      n += 4;   //4byte   float32       y2_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->x3_i                          ,pcOut + n, 4);      n += 4;   //4byte   float32       x3_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->y3_i                          ,pcOut + n, 4);      n += 4;   //4byte   float32       y3_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->x4_i                          ,pcOut + n, 4);      n += 4;   //4byte   float32       x4_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->y4_i                          ,pcOut + n, 4);      n += 4;   //4byte   float32       y4_i
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->ParkngSpcType                 ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       ParkngSpcType
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->ParkngSpcNum                  ,pcOut + n, 8);      n += 8;   //8byte   uint64_t      ParkngSpcNum
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->E4CornerMark                  ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       E4CornerMark
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->parkngSlotNumber              ,pcOut + n, 8);      n += 8;   //8byte   double        parkngSlotNumber
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved2     ,pcOut + n, 8);      n += 8;   //8byte   double        ParkingSlotInfo_Reserved2
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved3     ,pcOut + n, 8);      n += 8;   //8byte   double        ParkingSlotInfo_Reserved3
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved4     ,pcOut + n, 8);      n += 8;   //8byte   double        ParkingSlotInfo_Reserved4
            sp_big_reverse_copy((pIn->FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved5     ,pcOut + n, 8);      n += 8;   //8byte   double        ParkingSlotInfo_Reserved5
        }
    }

    sp_big_reverse_copy(pIn->Position_x                    ,pcOut + n, 8);      n += 8;   //8byte   double        Position_x
    sp_big_reverse_copy(pIn->Position_y                    ,pcOut + n, 8);      n += 8;   //8byte   double        Position_y
    sp_big_reverse_copy(pIn->Position_z                    ,pcOut + n, 8);      n += 8;   //8byte   double        Position_z
    sp_big_reverse_copy(pIn->Roll                          ,pcOut + n, 8);      n += 8;   //8byte   double        Roll
    sp_big_reverse_copy(pIn->Yaw                           ,pcOut + n, 8);      n += 8;   //8byte   double        Yaw
    sp_big_reverse_copy(pIn->Pitch                         ,pcOut + n, 8);      n += 8;   //8byte   double        Pitch

    sp_big_reverse_copy(pIn->FieldLength_RealTimeTrackPoint_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     FieldLength_RealTimeTrackPoint_len
    if (pIn->FieldLength_RealTimeTrackPoint_len > 0) //FieldLength_RealTimeTrackPoint
    {
        count = pIn->FieldLength_RealTimeTrackPoint_len / sizeof(stFieldLength_RealTimeTrackPointNPRTDN);
        int tt = sizeof(stFieldLength_RealTimeTrackPointNPRTDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_RealTimeTrackPoint+i)->RealTimeTrackPointID_i        ,pcOut + n, 4);      n += 4;   //4byte   uint32_t      RealTimeTrackPointID_i
            sp_big_reverse_copy((pIn->FieldLength_RealTimeTrackPoint+i)->x_i                           ,pcOut + n, 8);      n += 8;   //8byte   double        x_i
            sp_big_reverse_copy((pIn->FieldLength_RealTimeTrackPoint+i)->y_i                           ,pcOut + n, 8);      n += 8;   //8byte   double        y_i
            sp_big_reverse_copy((pIn->FieldLength_RealTimeTrackPoint+i)->heading_i                     ,pcOut + n, 8);      n += 8;   //8byte   double        heading_i
            sp_big_reverse_copy((pIn->FieldLength_RealTimeTrackPoint+i)->stopLine                      ,pcOut + n, 8);      n += 8;   //8byte   double        stopLine
            sp_big_reverse_copy((pIn->FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved2       ,pcOut + n, 8);      n += 8;   //8byte   double        GuideLineInfo_Reserved2
            sp_big_reverse_copy((pIn->FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved3       ,pcOut + n, 8);      n += 8;   //8byte   double        GuideLineInfo_Reserved3
            sp_big_reverse_copy((pIn->FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved4       ,pcOut + n, 8);      n += 8;   //8byte   double        GuideLineInfo_Reserved4
            sp_big_reverse_copy((pIn->FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved5       ,pcOut + n, 8);      n += 8;   //8byte   double        GuideLineInfo_Reserved5
        }
    }

    sp_big_reverse_copy(pIn->FieldLength_HistoryTrackPoint_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     FieldLength_HistoryTrackPoint_len
    if (pIn->FieldLength_HistoryTrackPoint_len > 0) //FieldLength_HistoryTrackPoint
    {
        count = pIn->FieldLength_HistoryTrackPoint_len / sizeof(stFieldLength_HistoryTrackPointNPRTDN);
        int tt = sizeof(stFieldLength_HistoryTrackPointNPRTDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->HistoryTrackPointID_i           ,pcOut + n, 4);      n += 4;   //4byte   uint32_t      HistoryTrackPointID_i
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->x_i                             ,pcOut + n, 8);      n += 8;   //8byte   double        x_i
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->y_i                             ,pcOut + n, 8);      n += 8;   //8byte   double        y_i
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->z_i                             ,pcOut + n, 8);      n += 8;   //8byte   double        z_i
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->Width_Learning                  ,pcOut + n, 4);      n += 4;   //4byte   uint32_t      Width_Learning
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->cruiseHistoryTrackPointID_i     ,pcOut + n, 8);      n += 8;   //8byte   double        cruiseHistoryTrackPointID_i
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->cruiseHistoryX                  ,pcOut + n, 8);      n += 8;   //8byte   double        cruiseHistoryX
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->cruiseHistoryY                  ,pcOut + n, 8);      n += 8;   //8byte   double        cruiseHistoryY
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->cruiseHistoryZ                  ,pcOut + n, 8);      n += 8;   //8byte   double        cruiseHistoryZ
            sp_big_reverse_copy((pIn->FieldLength_HistoryTrackPoint+i)->parkinglotLevel                 ,pcOut + n, 8);      n += 8;   //8byte   double        parkinglotLevel
        }
    }
    sp_big_reverse_copy(pIn->Parking_distance_left           ,pcOut + n, 4);      n += 4;   //4byte   float32       Parking_distance_left
    sp_big_reverse_copy(pIn->Cruising_distance_left          ,pcOut + n, 4);      n += 4;   //4byte   float32       Cruising_distance_left
    sp_big_reverse_copy(pIn->Learning_distance               ,pcOut + n, 4);      n += 4;   //4byte   float32       Learning_distance
    sp_big_reverse_copy(pIn->PathVeriRate                    ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       PathVeriRate
    sp_big_reverse_copy(pIn->Avoid_pedestrians_number        ,pcOut + n, 2);      n += 2;   //2byte   uint16_t      Avoid_pedestrians_number
    sp_big_reverse_copy(pIn->Avoid_vehicles_number           ,pcOut + n, 2);      n += 2;   //2byte   uint16_t      Avoid_vehicles_number
    sp_big_reverse_copy(pIn->PathLearnFailDisp               ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       PathLearnFailDisp
    sp_big_reverse_copy(pIn->Speed_Bump_Number               ,pcOut + n, 2);      n += 2;   //2byte   uint16_t      Speed_Bump_Number
    sp_big_reverse_copy(pIn->ViewAngleReq                    ,pcOut + n, 1);      n += 1;   //1byte   uint8_t       ViewAngleReq
    sp_big_reverse_copy(pIn->NRPX1NoPassing                  ,pcOut + n, 8);      n += 8;   //8byte   double        NRPX1NoPassing
    sp_big_reverse_copy(pIn->NRPY1NoPassing                  ,pcOut + n, 8);      n += 8;   //8byte   double        NRPY1NoPassing
    sp_big_reverse_copy(pIn->NRPX2NoPassing                  ,pcOut + n, 8);      n += 8;   //8byte   double        NRPX2NoPassing
    sp_big_reverse_copy(pIn->NRPY2NoPassing                  ,pcOut + n, 8);      n += 8;   //8byte   double        NRPY2NoPassing
    sp_big_reverse_copy(pIn->ParkingRealTimeData_Reserved5   ,pcOut + n, 8);      n += 8;   //8byte   double        ParkingRealTimeData_Reserved5
}

void NewParkingRealTimeDataNotifyDeserialization(const char* pcIn, std::shared_ptr<stNewParkingRealTimeDataNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum                     );      n += 4;   //4byte    uint32_t      Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                      );      n += 2;   //2byte    uint16_t      Counter
    big_reverse_copy(pcIn + n,  pOut->timestamp                    );      n += 8;   //8byte    double        timestamp
    
    big_reverse_copy(pcIn + n,  pOut->FieldLength_Object_len    );      n += 4;   //4byte    uint32_t   FieldLength_Object_len
    if (pOut->FieldLength_Object_len > 0)
    {
        int count = pOut->FieldLength_Object_len / sizeof(stFieldLength_ObjectNPRTDN);
        int tt = sizeof(stFieldLength_ObjectNPRTDN);
        pOut->FieldLength_Object = new stFieldLength_ObjectNPRTDN[count];
        memset(pOut->FieldLength_Object, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_Object
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->ObjectID_i                   ); n += 8;   //8byte   uint64_t      ObjectID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->shape_height_i               ); n += 8;   //8byte   double        shape_height_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->shape_length_i               ); n += 8;   //8byte   double        shape_length_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->shape_width_i                ); n += 8;   //8byte   double        shape_width_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->position_x_i                 ); n += 8;   //8byte   double        position_x_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->position_y_i                 ); n += 8;   //8byte   double        position_y_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->position_z_i                 ); n += 8;   //8byte   double        position_z_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->Heading_i                    ); n += 4;   //4byte   float32       Heading_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->TypeInfo                     ); n += 1;   //1byte   uint8_t       TypeInfo
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->CrashRisk                    ); n += 1;   //1byte   uint8_t       CrashRisk
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->NewMoveST                    ); n += 1;   //1byte   uint8_t       NewMoveST
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->NewAbsoluteVelocity          ); n += 2;   //2byte   uint16_t      NewAbsoluteVelocity
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->NewTurnSignalLampSt          ); n += 1;   //1byte   uint8_t       NewTurnSignalLampSt
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->NewHigh_lowBeamLampsSt       ); n += 1;   //1byte   uint8_t       NewHigh_lowBeamLampsSt
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->NewBrakeLightSt              ); n += 1;   //1byte   uint8_t       NewBrakeLightSt
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->NewReversingLightSt          ); n += 1;   //1byte   uint8_t       NewReversingLightSt
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->ParkingObjectInfo_Reserved1  ); n += 8;   //8byte   double        ParkingObjectInfo_Reserved1
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->blockingBarStatus            ); n += 8;   //8byte   double        blockingBarStatus
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->blockingBarTypeInfo          ); n += 8;   //8byte   double        blockingBarTypeInfo
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->blockingBarDirInfo           ); n += 8;   //8byte   double        blockingBarDirInfo
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Object+i)->ParkingObjectInfo_Reserved5  ); n += 8;   //8byte   double        ParkingObjectInfo_Reserved5
        }
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_ParkingSlot_len    );      n += 4;   //4byte    uint32_t   FieldLength_ParkingSlot_len
    if (pOut->FieldLength_ParkingSlot_len > 0)
    {
        int cnt = 0;
        int count = pOut->FieldLength_ParkingSlot_len / sizeof(stFieldLength_ParkingSlotNPRTDN);
        int tt = sizeof(stFieldLength_ParkingSlotNPRTDN);
        pOut->FieldLength_ParkingSlot = new stFieldLength_ParkingSlotNPRTDN[count];
        memset(pOut->FieldLength_ParkingSlot, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_ParkingSlot
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->ParkngSpcID_i              ); n += 4;   cnt += 4; //4byte   uint32_t      ParkngSpcID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->ParkngSpcSts               ); n += 1;   cnt += 1; //1byte   uint8_t       ParkngSpcSts
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->ParkngSpcCode_i            ); n += 1;   cnt += 1; //1byte   uint8_t       ParkngSpcCode_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->x1_i                       ); n += 4;   cnt += 4; //4byte   float32       x1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->y1_i                       ); n += 4;   cnt += 4; //4byte   float32       y1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->x2_i                       ); n += 4;   cnt += 4; //4byte   float32       x2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->y2_i                       ); n += 4;   cnt += 4; //4byte   float32       y2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->x3_i                       ); n += 4;   cnt += 4; //4byte   float32       x3_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->y3_i                       ); n += 4;   cnt += 4; //4byte   float32       y3_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->x4_i                       ); n += 4;   cnt += 4; //4byte   float32       x4_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->y4_i                       ); n += 4;   cnt += 4; //4byte   float32       y4_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->ParkngSpcType              ); n += 1;   cnt += 1; //1byte   uint8_t       ParkngSpcType
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->ParkngSpcNum               ); n += 8;   cnt += 8; //8byte   uint64_t      ParkngSpcNum
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->E4CornerMark               ); n += 1;   cnt += 1; //1byte   uint8_t       E4CornerMark
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->parkngSlotNumber           ); n += 8;   cnt += 8; //8byte   double        parkngSlotNumber
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved2  ); n += 8;   cnt += 8; //8byte   double        ParkingSlotInfo_Reserved2
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved3  ); n += 8;   cnt += 8; //8byte   double        ParkingSlotInfo_Reserved3
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved4  ); n += 8;   cnt += 8; //8byte   double        ParkingSlotInfo_Reserved4
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved5  ); n += 8;   cnt += 8; //8byte   double        ParkingSlotInfo_Reserved5
        }
    }

    big_reverse_copy(pcIn + n, pOut->Position_x                 ); n += 8;     //8byte   double        Position_x
    big_reverse_copy(pcIn + n, pOut->Position_y                 ); n += 8;     //8byte   double        Position_y
    big_reverse_copy(pcIn + n, pOut->Position_z                 ); n += 8;     //8byte   double        Position_z
    big_reverse_copy(pcIn + n, pOut->Roll                       ); n += 8;     //8byte   double        Roll
    big_reverse_copy(pcIn + n, pOut->Yaw                        ); n += 8;     //8byte   double        Yaw
    big_reverse_copy(pcIn + n, pOut->Pitch                      ); n += 8;     //8byte   double        Pitch

    big_reverse_copy(pcIn + n,  pOut->FieldLength_RealTimeTrackPoint_len    );      n += 4;   //4byte    uint32_t   FieldLength_RealTimeTrackPoint_len
    if (pOut->FieldLength_RealTimeTrackPoint_len > 0)
    {
        int count = pOut->FieldLength_RealTimeTrackPoint_len / sizeof(stFieldLength_RealTimeTrackPointNPRTDN);
        int tt = sizeof(stFieldLength_RealTimeTrackPointNPRTDN);
        pOut->FieldLength_RealTimeTrackPoint = new stFieldLength_RealTimeTrackPointNPRTDN[count];
        memset(pOut->FieldLength_ParkingSlot, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_RealTimeTrackPoint
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_RealTimeTrackPoint+i)->RealTimeTrackPointID_i   ); n += 4;   //4byte   uint32_t      RealTimeTrackPointID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_RealTimeTrackPoint+i)->x_i                      ); n += 8;   //8byte   double        x_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_RealTimeTrackPoint+i)->y_i                      ); n += 8;   //8byte   double        y_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_RealTimeTrackPoint+i)->heading_i                ); n += 8;   //8byte   double        heading_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_RealTimeTrackPoint+i)->stopLine                 ); n += 8;   //8byte   double        stopLine
            big_reverse_copy(pcIn + n, (pOut->FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved2  ); n += 8;   //8byte   double        GuideLineInfo_Reserved2
            big_reverse_copy(pcIn + n, (pOut->FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved3  ); n += 8;   //8byte   double        GuideLineInfo_Reserved3
            big_reverse_copy(pcIn + n, (pOut->FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved4  ); n += 8;   //8byte   double        GuideLineInfo_Reserved4
            big_reverse_copy(pcIn + n, (pOut->FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved5  ); n += 8;   //8byte   double        GuideLineInfo_Reserved5
        }
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_HistoryTrackPoint_len    );      n += 4;   //4byte    uint32_t   FieldLength_HistoryTrackPoint_len
    if (pOut->FieldLength_HistoryTrackPoint_len > 0)
    {
        int count = pOut->FieldLength_HistoryTrackPoint_len / sizeof(stFieldLength_HistoryTrackPointNPRTDN);
        int tt = sizeof(stFieldLength_HistoryTrackPointNPRTDN);
        pOut->FieldLength_HistoryTrackPoint = new stFieldLength_HistoryTrackPointNPRTDN[count];
        memset(pOut->FieldLength_HistoryTrackPoint, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_HistoryTrackPoint
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->HistoryTrackPointID_i          ); n += 4;   //4byte   uint32_t      HistoryTrackPointID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->x_i                            ); n += 8;   //8byte   double        x_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->y_i                            ); n += 8;   //8byte   double        y_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->z_i                            ); n += 8;   //8byte   double        z_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->Width_Learning                 ); n += 4;   //4byte   uint32_t      Width_Learning
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->cruiseHistoryTrackPointID_i    ); n += 8;   //8byte   double        cruiseHistoryTrackPointID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->cruiseHistoryX                 ); n += 8;   //8byte   double        cruiseHistoryX
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->cruiseHistoryY                 ); n += 8;   //8byte   double        cruiseHistoryY
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->cruiseHistoryZ                 ); n += 8;   //8byte   double        cruiseHistoryZ
            big_reverse_copy(pcIn + n, (pOut->FieldLength_HistoryTrackPoint+i)->parkinglotLevel                ); n += 8;   //8byte   double        parkinglotLevel
        }
    }

    big_reverse_copy(pcIn + n, pOut->Parking_distance_left          ); n += 4;   //4byte   float32       Parking_distance_left
    big_reverse_copy(pcIn + n, pOut->Cruising_distance_left         ); n += 4;   //4byte   float32       Cruising_distance_left
    big_reverse_copy(pcIn + n, pOut->Learning_distance              ); n += 4;   //4byte   float32       Learning_distance
    big_reverse_copy(pcIn + n, pOut->PathVeriRate                   ); n += 1;   //1byte   uint8_t       PathVeriRate
    big_reverse_copy(pcIn + n, pOut->Avoid_pedestrians_number       ); n += 2;   //2byte   uint16_t      Avoid_pedestrians_number
    big_reverse_copy(pcIn + n, pOut->Avoid_vehicles_number          ); n += 2;   //2byte   uint16_t      Avoid_vehicles_number
    big_reverse_copy(pcIn + n, pOut->PathLearnFailDisp              ); n += 1;   //1byte   uint8_t       PathLearnFailDisp
    big_reverse_copy(pcIn + n, pOut->Speed_Bump_Number              ); n += 2;   //2byte   uint16_t      Speed_Bump_Number
    big_reverse_copy(pcIn + n, pOut->ViewAngleReq                   ); n += 1;   //1byte   uint8_t       ViewAngleReq
    big_reverse_copy(pcIn + n, pOut->NRPX1NoPassing                 ); n += 8;   //8byte   double        NRPX1NoPassing
    big_reverse_copy(pcIn + n, pOut->NRPY1NoPassing                 ); n += 8;   //8byte   double        NRPY1NoPassing
    big_reverse_copy(pcIn + n, pOut->NRPX2NoPassing                 ); n += 8;   //8byte   double        NRPX2NoPassing
    big_reverse_copy(pcIn + n, pOut->NRPY2NoPassing                 ); n += 8;   //8byte   double        NRPY2NoPassing
    big_reverse_copy(pcIn + n, pOut->ParkingRealTimeData_Reserved5  ); n += 8;   //8byte   double        ParkingRealTimeData_Reserved
}

//19.NavigationHDLink2Info
void NavigationHDLink2InfoSerialization(std::shared_ptr<stNavigationHDLink2Info> pIn, char* pcOut)
{
    int n = 0, count = 0;

    sp_big_reverse_copy(pIn->Checksum               ,pcOut + n, 4);      n += 4;   //4byte    uint32_t      Checksum
    sp_big_reverse_copy(pIn->Counter                ,pcOut + n, 2);      n += 2;   //2byte    uint16_t      Counter
    sp_big_reverse_copy(pIn->NavigationPathValid1   ,pcOut + n, 1);      n += 1;   //1byte    uint8_t       NavigationPathValid1
    sp_big_reverse_copy(pIn->RoutePntCnt1           ,pcOut + n, 4);      n += 4;   //4byte    uint32_t      RoutePntCnt1
    sp_big_reverse_copy(pIn->RouteLinkCnt1          ,pcOut + n, 4);      n += 4;   //4byte    int32_t       RouteLinkCnt1
    sp_big_reverse_copy(pIn->RoutePathID1           ,pcOut + n, 8);      n += 8;   //8byte    uint64_t      RoutePathID1
    
    sp_big_reverse_copy(pIn->LinkItemInfo_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     LinkItemInfo_len
    if (pIn->LinkItemInfo_len > 0) //stLinkItemInfoNHDLI
    {
        count = pIn->LinkItemInfo_len / sizeof(stLinkItemInfoNHDLI);
        int tt = sizeof(stLinkItemInfoNHDLI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->LinkItemInfo+i)->LinkItemFormway1     ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemFormway1
            sp_big_reverse_copy((pIn->LinkItemInfo+i)->LinkItemLinktype1    ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemLinktype1
            sp_big_reverse_copy((pIn->LinkItemInfo+i)->LinkItemRoadclass1   ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemRoadclass1
            sp_big_reverse_copy((pIn->LinkItemInfo+i)->LinkItemBegIdx1      ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemBegIdx1
            sp_big_reverse_copy((pIn->LinkItemInfo+i)->LinkItemPntCnt1      ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemPntCnt1
            SPStringserialization((pIn->LinkItemInfo+i)->LinkItemRoadname_1   , pcOut,     n);                //        string          LinkItemRoadname_1
            sp_big_reverse_copy((pIn->LinkItemInfo+i)->LinkItemLen1         ,pcOut + n, 4);      n += 4;   //4byte   float           LinkItemLen1
        }
    }

    sp_big_reverse_copy(pIn->PntItemInfo_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     PntItemInfo_len
    if (pIn->PntItemInfo_len > 0) //stPntItemInfoNHDLI
    {
        count = pIn->PntItemInfo_len / sizeof(stPntItemInfoNHDLI);
        int tt = sizeof(stPntItemInfoNHDLI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->PntItemInfo+i)->PntItem_X1               ,pcOut + n, 8);      n += 8;   //8byte   double          PntItem_X1
            sp_big_reverse_copy((pIn->PntItemInfo+i)->PntItem_Y1               ,pcOut + n, 8);      n += 8;   //8byte   double          PntItem_Y1
        }
    }

    sp_big_reverse_copy(pIn->reserve1_9               ,pcOut + n, 8);      n += 8;   //8byte   uint64_t        reserve1_9
    sp_big_reverse_copy(pIn->reserve2_10              ,pcOut + n, 4);      n += 4;   //4byte   uint32_t        reserve2_10
    sp_big_reverse_copy(pIn->reserve3_11              ,pcOut + n, 4);      n += 4;   //4byte   float           reserve3_11
    sp_big_reverse_copy(pIn->NavigationPathValid2     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t         NavigationPathValid2
    sp_big_reverse_copy(pIn->RoutePntCnt2             ,pcOut + n, 4);      n += 4;   //4byte   int32_t         RoutePntCnt2
    sp_big_reverse_copy(pIn->RouteLinkCnt2            ,pcOut + n, 4);      n += 4;   //4byte   int32_t         RouteLinkCnt2
    sp_big_reverse_copy(pIn->RoutePathID2             ,pcOut + n, 8);      n += 8;   //8byte   uint64_t        RoutePathID2

    sp_big_reverse_copy(pIn->LinkItemInfo2_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     LinkItemInfo2_len
    if (pIn->LinkItemInfo2_len > 0) //stLinkItemInfo2NHDLI
    {
        count = pIn->LinkItemInfo2_len / sizeof(stLinkItemInfo2NHDLI);
        int tt = sizeof(stLinkItemInfo2NHDLI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->LinkItemInfo2+i)->LinkItemFormway2      ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemFormway2
            sp_big_reverse_copy((pIn->LinkItemInfo2+i)->LinkItemLinktype2     ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemLinktype2
            sp_big_reverse_copy((pIn->LinkItemInfo2+i)->LinkItemRoadclass2    ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemRoadclass2
            sp_big_reverse_copy((pIn->LinkItemInfo2+i)->LinkItemBegIdx2       ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemBegIdx2
            sp_big_reverse_copy((pIn->LinkItemInfo2+i)->LinkItemPntCnt2       ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemPntCnt2
            sp_big_reverse_copy((pIn->LinkItemInfo2+i)->LinkItemRoadname_2    ,pcOut + n, 0);      n += 0;   //0byte   string          LinkItemRoadname_2
            sp_big_reverse_copy((pIn->LinkItemInfo2+i)->LinkItemLen2          ,pcOut + n, 4);      n += 4;   //4byte   float           LinkItemLen2
        }
    }

    sp_big_reverse_copy(pIn->PntItemInfo2_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     PntItemInfo2_len
    if (pIn->PntItemInfo2_len > 0) //stPntItemInfo2NHDLI
    {
        count = pIn->PntItemInfo2_len / sizeof(stPntItemInfo2NHDLI);
        int tt = sizeof(stPntItemInfo2NHDLI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->PntItemInfo2+i)->PntItem_X2           ,pcOut + n, 8);      n += 8;   //8byte   double          PntItem_X2
            sp_big_reverse_copy((pIn->PntItemInfo2+i)->PntItem_Y2           ,pcOut + n, 8);      n += 8;   //8byte   double          PntItem_Y2
        }
    }

    sp_big_reverse_copy(pIn->reserve1_18          ,pcOut + n, 8);      n += 8;   //8byte   uint64_t        reserve1_18
    sp_big_reverse_copy(pIn->reserve2_25          ,pcOut + n, 4);      n += 4;   //4byte   uint32_t        reserve2_25
    sp_big_reverse_copy(pIn->reserve3_20          ,pcOut + n, 4);      n += 4;   //4byte   float           reserve3_20
    sp_big_reverse_copy(pIn->NavigationPathValid3 ,pcOut + n, 1);      n += 1;   //1byte   uint8_t         NavigationPathValid3
    sp_big_reverse_copy(pIn->RoutePntCnt3         ,pcOut + n, 4);      n += 4;   //4byte   int32_t         RoutePntCnt3
    sp_big_reverse_copy(pIn->RouteLinkCnt3        ,pcOut + n, 4);      n += 4;   //4byte   int32_t         RouteLinkCnt3
    sp_big_reverse_copy(pIn->RoutePathID3         ,pcOut + n, 8);      n += 8;   //8byte   uint64_t        RoutePathID3

    sp_big_reverse_copy(pIn->LinkItemInfo3_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     LinkItemInfo3_len
    if (pIn->LinkItemInfo3_len > 0) //stLinkItemInfo3NHDLI
    {
        count = pIn->LinkItemInfo3_len / sizeof(stLinkItemInfo3NHDLI);
        int tt = sizeof(stLinkItemInfo3NHDLI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->LinkItemInfo3+i)->LinkItemFormway3        ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemFormway3
            sp_big_reverse_copy((pIn->LinkItemInfo3+i)->LinkItemLinktype3       ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemLinktype3
            sp_big_reverse_copy((pIn->LinkItemInfo3+i)->LinkItemRoadclass3      ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemRoadclass3
            sp_big_reverse_copy((pIn->LinkItemInfo3+i)->LinkItemBegIdx3         ,pcOut + n, 1);      n += 1;   //1byte   int32_t         LinkItemBegIdx3
            sp_big_reverse_copy((pIn->LinkItemInfo3+i)->LinkItemPntCnt3         ,pcOut + n, 4);      n += 4;   //4byte   int32_t         LinkItemPntCnt3
            SPStringserialization((pIn->LinkItemInfo3+i)->LinkItemRoadname3       ,pcOut,     n);                //        string          LinkItemRoadname3
            sp_big_reverse_copy((pIn->LinkItemInfo3+i)->LinkItemLen3            ,pcOut + n, 4);      n += 4;   //4byte   float           LinkItemLen3
        }
    }

    sp_big_reverse_copy(pIn->PntItemInfo3_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     PntItemInfo3_len
    if (pIn->PntItemInfo3_len > 0) //stPntItemInfo3NHDLI
    {
        count = pIn->PntItemInfo3_len / sizeof(stPntItemInfo3NHDLI);
        int tt = sizeof(stPntItemInfo3NHDLI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->PntItemInfo3+i)->PntItem_X3   ,pcOut + n, 8);      n += 8;   //8byte   double          PntItem_X3
            sp_big_reverse_copy((pIn->PntItemInfo3+i)->PntItem_Y3   ,pcOut + n, 8);      n += 8;   //8byte   double          PntItem_Y3
        }
    }

    sp_big_reverse_copy(pIn->reserve1_27     ,pcOut + n, 8);      n += 8;   //8byte   uint64_t        reserve1_27
    sp_big_reverse_copy(pIn->reserve2_28     ,pcOut + n, 4);      n += 4;   //4byte   uint32_t        reserve2_28
    sp_big_reverse_copy(pIn->reserve3_29     ,pcOut + n, 4);      n += 4;   //4byte   float           reserve3_29
}

void NavigationHDLink2InfoDeserialization(const char* pcIn, std::shared_ptr<stNavigationHDLink2Info> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum               );      n += 4;   //4byte    uint32_t      Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter                );      n += 2;   //2byte    uint16_t      Counter
    big_reverse_copy(pcIn + n,  pOut->NavigationPathValid1   );      n += 1;   //1byte    uint8_t       NavigationPathValid1
    big_reverse_copy(pcIn + n,  pOut->RoutePntCnt1           );      n += 4;   //4byte    uint32_t      RoutePntCnt1
    big_reverse_copy(pcIn + n,  pOut->RouteLinkCnt1          );      n += 4;   //4byte    int32_t       RouteLinkCnt1
    big_reverse_copy(pcIn + n,  pOut->RoutePathID1           );      n += 8;   //8byte    uint64_t      RoutePathID1
    
    big_reverse_copy(pcIn + n,  pOut->LinkItemInfo_len    );      n += 4;   //4byte    uint32_t     LinkItemInfo_len
    if (pOut->LinkItemInfo_len > 0)
    {
        int count = pOut->LinkItemInfo_len / sizeof(stLinkItemInfoNHDLI);
        int tt = sizeof(stLinkItemInfoNHDLI);
        pOut->LinkItemInfo = new stLinkItemInfoNHDLI[count];
        memset(pOut->LinkItemInfo, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //LinkItemInfo
        {
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo+i)->LinkItemFormway1    ); n += 4;   //4byte   int32_t         LinkItemFormway1
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo+i)->LinkItemLinktype1   ); n += 4;   //4byte   int32_t         LinkItemLinktype1
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo+i)->LinkItemRoadclass1  ); n += 4;   //4byte   int32_t         LinkItemRoadclass1
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo+i)->LinkItemBegIdx1     ); n += 4;   //4byte   int32_t         LinkItemBegIdx1
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo+i)->LinkItemPntCnt1     ); n += 4;   //4byte   int32_t         LinkItemPntCnt1
            SPStringDeserialization(pcIn, (pOut->LinkItemInfo+i)->LinkItemRoadname_1, n);   //        string          LinkItemRoadname_1
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo+i)->LinkItemLen1        ); n += 4;   //4byte   float           LinkItemLen1
        }
    }

    big_reverse_copy(pcIn + n,  pOut->PntItemInfo_len    );      n += 4;   //4byte    uint32_t     PntItemInfo_len
    if (pOut->PntItemInfo_len > 0)
    {
        int count = pOut->PntItemInfo_len / sizeof(stPntItemInfoNHDLI);
        int tt = sizeof(stPntItemInfoNHDLI);
        pOut->PntItemInfo = new stPntItemInfoNHDLI[count];
        memset(pOut->PntItemInfo, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //PntItemInfo
        {
            big_reverse_copy(pcIn + n, (pOut->PntItemInfo+i)->PntItem_X1            ); n += 8;   //8byte   double          PntItem_X1
            big_reverse_copy(pcIn + n, (pOut->PntItemInfo+i)->PntItem_Y1            ); n += 8;   //8byte   double          PntItem_Y1
        }
    }

    big_reverse_copy(pcIn + n, pOut->reserve1_9            ); n += 8;   //8byte   uint64_t        reserve1_9          
    big_reverse_copy(pcIn + n, pOut->reserve2_10           ); n += 4;   //4byte   uint32_t        reserve2_10         
    big_reverse_copy(pcIn + n, pOut->reserve3_11           ); n += 4;   //4byte   float           reserve3_11         
    big_reverse_copy(pcIn + n, pOut->NavigationPathValid2  ); n += 1;   //1byte   uint8_t         NavigationPathValid2
    big_reverse_copy(pcIn + n, pOut->RoutePntCnt2          ); n += 4;   //4byte   int32_t         RoutePntCnt2        
    big_reverse_copy(pcIn + n, pOut->RouteLinkCnt2         ); n += 4;   //4byte   int32_t         RouteLinkCnt2       
    big_reverse_copy(pcIn + n, pOut->RoutePathID2          ); n += 8;   //8byte   uint64_t        RoutePathID2        

    big_reverse_copy(pcIn + n,  pOut->LinkItemInfo2_len    );      n += 4;   //4byte    uint32_t     LinkItemInfo2_len
    if (pOut->LinkItemInfo2_len > 0)
    {
        int count = pOut->LinkItemInfo2_len / sizeof(stLinkItemInfo2NHDLI);
        int tt = sizeof(stLinkItemInfo2NHDLI);
        pOut->LinkItemInfo2 = new stLinkItemInfo2NHDLI[count];
        memset(pOut->LinkItemInfo2, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //LinkItemInfo2
        {
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo2+i)->LinkItemFormway2     ); n += 4;   //4byte   int32_t         LinkItemFormway2
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo2+i)->LinkItemLinktype2    ); n += 4;   //4byte   int32_t         LinkItemLinktype2
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo2+i)->LinkItemRoadclass2   ); n += 4;   //4byte   int32_t         LinkItemRoadclass2
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo2+i)->LinkItemBegIdx2      ); n += 4;   //4byte   int32_t         LinkItemBegIdx2
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo2+i)->LinkItemPntCnt2      ); n += 4;   //4byte   int32_t         LinkItemPntCnt2
            SPStringDeserialization(pcIn, (pOut->LinkItemInfo2+i)->LinkItemRoadname_2, n);   //        string          LinkItemRoadname_2
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo2+i)->LinkItemLen2         ); n += 4;   //4byte   float           LinkItemLen2
        }
    }

    big_reverse_copy(pcIn + n,  pOut->PntItemInfo2_len    );      n += 4;   //4byte    uint32_t     PntItemInfo2_len
    if (pOut->PntItemInfo2_len > 0)
    {
        int count = pOut->PntItemInfo2_len / sizeof(stPntItemInfo2NHDLI);
        int tt = sizeof(stPntItemInfo2NHDLI);
        pOut->PntItemInfo2 = new stPntItemInfo2NHDLI[count];
        memset(pOut->PntItemInfo2, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //PntItemInfo2
        {
            big_reverse_copy(pcIn + n, (pOut->PntItemInfo2+i)->PntItem_X2            ); n += 8;   //8byte   double          PntItem_X2
            big_reverse_copy(pcIn + n, (pOut->PntItemInfo2+i)->PntItem_Y2            ); n += 8;   //8byte   double          PntItem_Y2
        }
    }

    big_reverse_copy(pcIn + n, pOut->reserve1_18           ); n += 8;   //8byte   uint64_t        reserve1_18         
    big_reverse_copy(pcIn + n, pOut->reserve2_25           ); n += 4;   //4byte   uint32_t        reserve2_25         
    big_reverse_copy(pcIn + n, pOut->reserve3_20           ); n += 4;   //4byte   float           reserve3_20         
    big_reverse_copy(pcIn + n, pOut->NavigationPathValid3  ); n += 1;   //1byte   uint8_t         NavigationPathValid3
    big_reverse_copy(pcIn + n, pOut->RoutePntCnt3          ); n += 4;   //4byte   int32_t         RoutePntCnt3        
    big_reverse_copy(pcIn + n, pOut->RouteLinkCnt3         ); n += 4;   //4byte   int32_t         RouteLinkCnt3       
    big_reverse_copy(pcIn + n, pOut->RoutePathID3          ); n += 8;   //8byte   uint64_t        RoutePathID3        

    big_reverse_copy(pcIn + n,  pOut->LinkItemInfo3_len    );      n += 4;   //4byte    uint32_t     LinkItemInfo3_len
    if (pOut->LinkItemInfo3_len > 0)
    {
        int count = pOut->LinkItemInfo3_len / sizeof(stLinkItemInfo3NHDLI);
        int tt = sizeof(stLinkItemInfo3NHDLI);
        pOut->LinkItemInfo3 = new stLinkItemInfo3NHDLI[count];
        memset(pOut->LinkItemInfo2, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //LinkItemInfo2
        {
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo3+i)->LinkItemFormway3    ); n += 4;   //4byte   int32_t         LinkItemFormway3
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo3+i)->LinkItemLinktype3   ); n += 4;   //4byte   int32_t         LinkItemLinktype3
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo3+i)->LinkItemRoadclass3  ); n += 4;   //4byte   int32_t         LinkItemRoadclass3
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo3+i)->LinkItemBegIdx3     ); n += 1;   //1byte   int32_t         LinkItemBegIdx3
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo3+i)->LinkItemPntCnt3     ); n += 4;   //4byte   int32_t         LinkItemPntCnt3
            SPStringDeserialization(pcIn, (pOut->LinkItemInfo3+i)->LinkItemRoadname3, n);   //        string          LinkItemRoadname_2
            big_reverse_copy(pcIn + n, (pOut->LinkItemInfo3+i)->LinkItemLen3        ); n += 4;   //4byte   float           LinkItemLen3
        }
    }

    big_reverse_copy(pcIn + n,  pOut->PntItemInfo3_len    );      n += 4;   //4byte    uint32_t     PntItemInfo3_len
    if (pOut->PntItemInfo3_len > 0)
    {
        int count = pOut->PntItemInfo3_len / sizeof(stPntItemInfo3NHDLI);
        int tt = sizeof(stPntItemInfo3NHDLI);
        pOut->PntItemInfo3 = new stPntItemInfo3NHDLI[count];
        memset(pOut->PntItemInfo3, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //PntItemInfo3
        {
            big_reverse_copy(pcIn + n, (pOut->PntItemInfo3+i)->PntItem_X3   ); n += 8;   //8byte   double          PntItem_X3
            big_reverse_copy(pcIn + n, (pOut->PntItemInfo3+i)->PntItem_Y3   ); n += 8;   //8byte   double          PntItem_Y3
        }
    }

    big_reverse_copy(pcIn + n, pOut->reserve1_27     ); n += 8;   //8byte   uint64_t        reserve1_27 
    big_reverse_copy(pcIn + n, pOut->reserve2_28     ); n += 4;   //4byte   uint32_t        reserve2_28 
    big_reverse_copy(pcIn + n, pOut->reserve3_29     ); n += 4;   //4byte   float           reserve3_29 
}


//20.sdTraffiIncident
void sdTraffiIncidentSerialization(std::shared_ptr<stsdTraffiIncident> pIn, char* pcOut)
{
    int n = 0, count = 0;
    
    sp_big_reverse_copy(pIn->TraffiIncident_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     TraffiIncident_len
    if (pIn->TraffiIncident_len > 0) //stTraffiIncidentTI
    {
        count = pIn->TraffiIncident_len / sizeof(stTraffiIncidentTI);
        int tt = sizeof(stTraffiIncidentTI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->TraffiIncident+i)->naviCongestionInfo     ,pcOut + n, 1);      n += 1;   //1byte   uint8_t     naviCongestionInfo
            sp_big_reverse_copy((pIn->TraffiIncident+i)->occupiedLane           ,pcOut + n, 1);      n += 1;   //1byte   uint8_t     occupiedLane
            sp_big_reverse_copy((pIn->TraffiIncident+i)->cnstrctnCrdLatitude    ,pcOut + n, 8);      n += 8;   //8byte   double      cnstrctnCrdLatitude
            sp_big_reverse_copy((pIn->TraffiIncident+i)->cnstrctnCrdLongitude   ,pcOut + n, 8);      n += 8;   //8byte   double      cnstrctnCrdLongitude
            sp_big_reverse_copy((pIn->TraffiIncident+i)->naviCongestionDistLen  ,pcOut + n, 8);      n += 8;   //8byte   uint64_t    naviCongestionDistLen
            sp_big_reverse_copy((pIn->TraffiIncident+i)->occupiedLaneDtl        ,pcOut + n, 4);      n += 4;   //4byte   uint32_t    occupiedLaneDtl
            sp_big_reverse_copy((pIn->TraffiIncident+i)->reserve3               ,pcOut + n, 4);      n += 4;   //4byte   float       reserve3
        }
    }
}

void sdTraffiIncidentDeserialization(const char* pcIn, std::shared_ptr<stsdTraffiIncident> pOut)
{
    int n = 0;
    
    big_reverse_copy(pcIn + n,  pOut->TraffiIncident_len    );      n += 4;   //4byte    uint32_t   TraffiIncident_len
    if (pOut->TraffiIncident_len > 0)
    {
        int count = pOut->TraffiIncident_len / sizeof(stTraffiIncidentTI);
        int tt = sizeof(stTraffiIncidentTI);
        pOut->TraffiIncident = new stTraffiIncidentTI[count];
        memset(pOut->TraffiIncident, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_RealTimeTrackPoint
        {
            big_reverse_copy(pcIn + n, (pOut->TraffiIncident+i)->naviCongestionInfo     ); n += 1;   //1byte   uint8_t     naviCongestionInfo
            big_reverse_copy(pcIn + n, (pOut->TraffiIncident+i)->occupiedLane           ); n += 1;   //1byte   uint8_t     occupiedLane
            big_reverse_copy(pcIn + n, (pOut->TraffiIncident+i)->cnstrctnCrdLatitude    ); n += 8;   //8byte   double      cnstrctnCrdLatitude
            big_reverse_copy(pcIn + n, (pOut->TraffiIncident+i)->cnstrctnCrdLongitude   ); n += 8;   //8byte   double      cnstrctnCrdLongitude
            big_reverse_copy(pcIn + n, (pOut->TraffiIncident+i)->naviCongestionDistLen  ); n += 8;   //8byte   uint64_t    naviCongestionDistLen
            big_reverse_copy(pcIn + n, (pOut->TraffiIncident+i)->occupiedLaneDtl        ); n += 4;   //4byte   uint32_t    occupiedLaneDtl
            big_reverse_copy(pcIn + n, (pOut->TraffiIncident+i)->reserve3               ); n += 4;   //4byte   float       reserve3
        }
    }
}

//21.newPlanningLineInfo
void newPlanningLineInfoSerialization(std::shared_ptr<stnewPlanningLineInfo> pIn, char* pcOut)
{
    int n = 0, count = 0;

    sp_big_reverse_copy(pIn->checksum               ,pcOut + n, 4);      n += 4;   //4byte    uint32_t        checksum
    sp_big_reverse_copy(pIn->counter                ,pcOut + n, 2);      n += 2;   //2byte    uint16_t        counter
    sp_big_reverse_copy(pIn->planningLineStatus     ,pcOut + n, 1);      n += 1;   //1byte    bool            planningLineStatus
    sp_big_reverse_copy(pIn->planningTimestamp      ,pcOut + n, 8);      n += 8;   //8byte    double          planningTimestamp
    
    sp_big_reverse_copy(pIn->fieldLengthPlanningLinePoints_len  ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     fieldLengthPlanningLinePoints_len
    if (pIn->fieldLengthPlanningLinePoints_len > 0) //stfieldLengthPlanningLinePointsNPLI
    {
        count = pIn->fieldLengthPlanningLinePoints_len / sizeof(stfieldLengthPlanningLinePointsNPLI);
        int tt = sizeof(stfieldLengthPlanningLinePointsNPLI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->fieldLengthPlanningLinePoints+i)->PlanningLinePointsID            ,pcOut + n, 4);      n += 4;   //4byte   uint32_t  PlanningLinePointsID
            sp_big_reverse_copy((pIn->fieldLengthPlanningLinePoints+i)->pointsX                         ,pcOut + n, 8);      n += 8;   //8byte   double    pointsX
            sp_big_reverse_copy((pIn->fieldLengthPlanningLinePoints+i)->pointsY                         ,pcOut + n, 8);      n += 8;   //8byte   double    pointsY
            sp_big_reverse_copy((pIn->fieldLengthPlanningLinePoints+i)->pointsZ                         ,pcOut + n, 8);      n += 8;   //8byte   double    pointsZ
        }
    }

    sp_big_reverse_copy(pIn->accelerationDeceleration        ,pcOut + n, 8);      n += 8;   //8byte   double    accelerationDeceleration
    sp_big_reverse_copy(pIn->navigationPlanningLineStatus    ,pcOut + n, 1);      n += 1;   //1byte   bool      navigationPlanningLineStatus
    sp_big_reverse_copy(pIn->navigationPlanningTimestamp     ,pcOut + n, 8);      n += 8;   //8byte   double    navigationPlanningTimestamp

    sp_big_reverse_copy(pIn->navFieldLengthNavigationPlanningLinePoints_len  ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     navFieldLengthNavigationPlanningLinePoints_len
    if (pIn->navFieldLengthNavigationPlanningLinePoints_len > 0) //stnavFieldLengthNavigationPlanningLinePointsNPLI
    {
        count = pIn->navFieldLengthNavigationPlanningLinePoints_len / sizeof(stnavFieldLengthNavigationPlanningLinePointsNPLI);
        int tt = sizeof(stnavFieldLengthNavigationPlanningLinePointsNPLI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->navFieldLengthNavigationPlanningLinePoints+i)->navPlanningLinePointsID,pcOut + n, 4);      n += 4;   //4byte   uint32_t        navPlanningLinePointsID
            sp_big_reverse_copy((pIn->navFieldLengthNavigationPlanningLinePoints+i)->navPointsX             ,pcOut + n, 8);      n += 8;   //8byte   double          navPointsX
            sp_big_reverse_copy((pIn->navFieldLengthNavigationPlanningLinePoints+i)->navPointsY             ,pcOut + n, 8);      n += 8;   //8byte   double          navPointsY
            sp_big_reverse_copy((pIn->navFieldLengthNavigationPlanningLinePoints+i)->navPointsZ             ,pcOut + n, 8);      n += 8;   //8byte   double          navPointsZ
        }
    }
}

void newPlanningLineInfoDeserialization(const char* pcIn, std::shared_ptr<stnewPlanningLineInfo> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->checksum                    );      n += 4;   //4byte    uint32_t        checksum
    big_reverse_copy(pcIn + n,  pOut->counter                     );      n += 2;   //2byte    uint16_t        counter
    big_reverse_copy(pcIn + n,  pOut->planningLineStatus          );      n += 1;   //1byte    bool            planningLineStatus
    big_reverse_copy(pcIn + n,  pOut->planningTimestamp           );      n += 8;   //8byte    double          planningTimestamp
    
    big_reverse_copy(pcIn + n,  pOut->fieldLengthPlanningLinePoints_len    );      n += 4;   //4byte    uint32_t   FieldLength_RealTimeTrackPoint_len
    if (pOut->fieldLengthPlanningLinePoints_len > 0)
    {
        int count = pOut->fieldLengthPlanningLinePoints_len / sizeof(stfieldLengthPlanningLinePointsNPLI);
        int tt = sizeof(stfieldLengthPlanningLinePointsNPLI);
        pOut->fieldLengthPlanningLinePoints = new stfieldLengthPlanningLinePointsNPLI[count];
        memset(pOut->fieldLengthPlanningLinePoints, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //fieldLengthPlanningLinePoints
        {
            big_reverse_copy(pcIn + n, (pOut->fieldLengthPlanningLinePoints+i)->PlanningLinePointsID           ); n += 4;   //4byte   uint32_t  PlanningLinePointsID
            big_reverse_copy(pcIn + n, (pOut->fieldLengthPlanningLinePoints+i)->pointsX                        ); n += 8;   //8byte   double    pointsX
            big_reverse_copy(pcIn + n, (pOut->fieldLengthPlanningLinePoints+i)->pointsY                        ); n += 8;   //8byte   double    pointsY
            big_reverse_copy(pcIn + n, (pOut->fieldLengthPlanningLinePoints+i)->pointsZ                        ); n += 8;   //8byte   double    pointsZ
        }
    }

    big_reverse_copy(pcIn + n, pOut->accelerationDeceleration       ); n += 8;   //8byte   double    accelerationDeceleration
    big_reverse_copy(pcIn + n, pOut->navigationPlanningLineStatus   ); n += 1;   //1byte   bool      navigationPlanningLineStatus
    big_reverse_copy(pcIn + n, pOut->navigationPlanningTimestamp    ); n += 8;   //8byte   double    navigationPlanningTimestamp

    big_reverse_copy(pcIn + n,  pOut->navFieldLengthNavigationPlanningLinePoints_len    );      n += 4;   //4byte    uint32_t   navFieldLengthNavigationPlanningLinePoints_len
    if (pOut->navFieldLengthNavigationPlanningLinePoints_len > 0)
    {
        int count = pOut->navFieldLengthNavigationPlanningLinePoints_len / sizeof(stnavFieldLengthNavigationPlanningLinePointsNPLI);
        int tt = sizeof(stnavFieldLengthNavigationPlanningLinePointsNPLI);
        pOut->navFieldLengthNavigationPlanningLinePoints = new stnavFieldLengthNavigationPlanningLinePointsNPLI[count];
        memset(pOut->navFieldLengthNavigationPlanningLinePoints, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //navFieldLengthNavigationPlanningLinePoints
        {
            big_reverse_copy(pcIn + n, (pOut->navFieldLengthNavigationPlanningLinePoints+i)->navPlanningLinePointsID  ); n += 4;   //4byte   uint32_t        navPlanningLinePointsID
            big_reverse_copy(pcIn + n, (pOut->navFieldLengthNavigationPlanningLinePoints+i)->navPointsX               ); n += 8;   //8byte   double          navPointsX
            big_reverse_copy(pcIn + n, (pOut->navFieldLengthNavigationPlanningLinePoints+i)->navPointsY               ); n += 8;   //8byte   double          navPointsY
            big_reverse_copy(pcIn + n, (pOut->navFieldLengthNavigationPlanningLinePoints+i)->navPointsZ               ); n += 8;   //8byte   double          navPointsZ
        }
    }
}

//22.drivingAreaIdentification
void drivingAreaIdentificationsSerialization(std::shared_ptr<stdrivingAreaIdentification> pIn, char* pcOut)
{
    int n = 0, count = 0;

    sp_big_reverse_copy(pIn->checksum                           ,pcOut + n, 4);      n += 4;   //4byte    uint32_t        checksum
    sp_big_reverse_copy(pIn->counter                            ,pcOut + n, 2);      n += 2;   //2byte    uint16_t        counter
    sp_big_reverse_copy(pIn->drivingAreaIdentificationStatus    ,pcOut + n, 1);      n += 1;   //1byte    bool            drivingAreaIdentificationStatus
    
    sp_big_reverse_copy(pIn->drivingAreaIdentificationPoints_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     drivingAreaIdentificationPoints_len
    if (pIn->drivingAreaIdentificationPoints_len > 0) //stLinkItemInfoNHDLI
    {
        count = pIn->drivingAreaIdentificationPoints_len / sizeof(stLinkItemInfoNHDLI);
        int tt = sizeof(stLinkItemInfoNHDLI);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy(pIn->drivingAreaIdentificationPoints       ,pcOut + n, 1);      n += 1;   //1byte   uint8_t         drivingAreaIdentificationPoints

        }
    }

    sp_big_reverse_copy(pIn->sizetBevh                             ,pcOut + n, 4);      n += 4;   //4byte   uint32_t        sizetBevh
    sp_big_reverse_copy(pIn->sizetBevw                             ,pcOut + n, 4);      n += 4;   //4byte   uint32_t        sizetBevw
    sp_big_reverse_copy(pIn->xBoundMin                             ,pcOut + n, 8);      n += 8;   //8byte   double          xBoundMin
    sp_big_reverse_copy(pIn->xBoundMax                             ,pcOut + n, 8);      n += 8;   //8byte   double          xBoundMax
    sp_big_reverse_copy(pIn->yBoundMin                             ,pcOut + n, 8);      n += 8;   //8byte   double          yBoundMin
    sp_big_reverse_copy(pIn->yBoundMax                             ,pcOut + n, 8);      n += 8;   //8byte   double          yBoundMax
    sp_big_reverse_copy(pIn->meterPerPixelX                        ,pcOut + n, 8);      n += 8;   //8byte   double          meterPerPixelX
    sp_big_reverse_copy(pIn->meterPerPixelY                        ,pcOut + n, 8);      n += 8;   //8byte   double          meterPerPixelY
    sp_big_reverse_copy(pIn->maskThreshold                         ,pcOut + n, 8);      n += 8;   //8byte   double          maskThreshold

    sp_big_reverse_copy(pIn->reservedDataLength1                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength1
    if (pIn->reservedDataLength1 > 0) //uint8_t
    {
        count = pIn->reservedDataLength1 / sizeof(uint8_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy(*(pIn->reserved1+i),pcOut + n, 1);      n += 1;    //1byte    uint8    reserved1
        }
    }

    sp_big_reverse_copy(pIn->reservedDataLength2                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength2
    if (pIn->reservedDataLength2 > 0) //uint16_t
    {
        count = pIn->reservedDataLength2 / sizeof(uint16_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy(*(pIn->reserved2+i),pcOut + n, 1);      n += 1;    //1byte    uint8    reserved2
        }
    }

    sp_big_reverse_copy(pIn->reservedDataLength3                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength3
    if (pIn->reservedDataLength3 > 0) //uint32_t
    {
        count = pIn->reservedDataLength3 / sizeof(uint32_t);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy(*(pIn->reserved3+i),pcOut + n, 1);      n += 1;    //1byte    uint8    reserved3
        }
    }

    sp_big_reverse_copy(pIn->reservedDataLength4                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength4
    if (pIn->reservedDataLength4 > 0) //double
    {
        count = pIn->reservedDataLength4 / sizeof(double);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy(*(pIn->reserved4+i),pcOut + n, 1);      n += 1;    //1byte    uint8    reserved4
        }
    }

    sp_big_reverse_copy(pIn->reservedDataLength5                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     reservedDataLength5
    if (pIn->reservedDataLength5 > 0) //float32
    {
        count = pIn->reservedDataLength5 / sizeof(float32);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy(*(pIn->reserved5+i),pcOut + n, 1);      n += 1;    //1byte    uint8    reserved5
        }
    }
}

void drivingAreaIdentificationsDeserialization(const char* pcIn, std::shared_ptr<stdrivingAreaIdentification> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->checksum                            );      n += 4;   //4byte    uint32_t        checksum
    big_reverse_copy(pcIn + n,  pOut->counter                             );      n += 2;   //2byte    uint16_t        counter
    big_reverse_copy(pcIn + n,  pOut->drivingAreaIdentificationStatus     );      n += 1;   //1byte    bool            drivingAreaIdentificationStatus
    
    big_reverse_copy(pcIn + n,  pOut->drivingAreaIdentificationPoints_len    );      n += 4;   //4byte    uint32_t   drivingAreaIdentificationPoints_len
    if (pOut->drivingAreaIdentificationPoints_len > 0)
    {
        int count = pOut->drivingAreaIdentificationPoints_len / sizeof(uint8_t);
        int tt = sizeof(uint8_t);
        pOut->drivingAreaIdentificationPoints = new uint8_t[count];
        memset(pOut->drivingAreaIdentificationPoints, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //drivingAreaIdentificationPoints
        {
            big_reverse_copy(pcIn + n, pOut->drivingAreaIdentificationPoints        ); n += 1;   //1byte   uint8_t         drivingAreaIdentificationPoints
        }
    }

    big_reverse_copy(pcIn + n, pOut->sizetBevh                              ); n += 4;   //4byte   uint32_t        sizetBevh
    big_reverse_copy(pcIn + n, pOut->sizetBevw                              ); n += 4;   //4byte   uint32_t        sizetBevw
    big_reverse_copy(pcIn + n, pOut->xBoundMin                              ); n += 8;   //8byte   double          xBoundMin
    big_reverse_copy(pcIn + n, pOut->xBoundMax                              ); n += 8;   //8byte   double          xBoundMax
    big_reverse_copy(pcIn + n, pOut->yBoundMin                              ); n += 8;   //8byte   double          yBoundMin
    big_reverse_copy(pcIn + n, pOut->yBoundMax                              ); n += 8;   //8byte   double          yBoundMax
    big_reverse_copy(pcIn + n, pOut->meterPerPixelX                         ); n += 8;   //8byte   double          meterPerPixelX
    big_reverse_copy(pcIn + n, pOut->meterPerPixelY                         ); n += 8;   //8byte   double          meterPerPixelY
    big_reverse_copy(pcIn + n, pOut->maskThreshold                          ); n += 8;   //8byte   double          maskThreshold

    big_reverse_copy(pcIn + n,  pOut->reservedDataLength1    );      n += 4;   //4byte    uint32_t   reservedDataLength1
    if (pOut->reservedDataLength1 > 0)
    {
        int count = pOut->reservedDataLength1 / sizeof(uint8_t);
        pOut->reserved1 = new uint8_t[count];
        memset(pOut->reserved1, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //reserved1
        {
            big_reverse_copy(pcIn + n, *(pOut->reserved1+i)); n += 1; //1byte   uint8  reserved1
        }
    }

    big_reverse_copy(pcIn + n,  pOut->reservedDataLength2    );      n += 4;   //4byte    uint32_t   reservedDataLength2
    if (pOut->reservedDataLength2 > 0)
    {
        int count = pOut->reservedDataLength2 / sizeof(uint16_t);
        pOut->reserved2 = new uint16_t[count];
        memset(pOut->reserved2, 0, sizeof(uint16_t)*count);
        for (int i = 0; i < count; ++i) //reserved2
        {
            big_reverse_copy(pcIn + n, *(pOut->reserved2+i)); n += 1; //1byte   uint8  reserved2
        }
    }

    big_reverse_copy(pcIn + n,  pOut->reservedDataLength3    );      n += 4;   //4byte    uint32_t   reservedDataLength3
    if (pOut->reservedDataLength3 > 0)
    {
        int count = pOut->reservedDataLength3 / sizeof(uint32_t);
        pOut->reserved3 = new uint32_t[count];
        memset(pOut->reserved3, 0, sizeof(uint32_t)*count);
        for (int i = 0; i < count; ++i) //reserved3
        {
            big_reverse_copy(pcIn + n, *(pOut->reserved3+i)); n += 1; //1byte   uint8  reserved3
        }
    }

    big_reverse_copy(pcIn + n,  pOut->reservedDataLength4    );      n += 4;   //4byte    uint32_t   reservedDataLength4
    if (pOut->reservedDataLength4 > 0)
    {
        int count = pOut->reservedDataLength4 / sizeof(double);
        pOut->reserved4 = new double[count];
        memset(pOut->reserved4, 0, sizeof(double)*count);
        for (int i = 0; i < count; ++i) //reserved4
        {
            big_reverse_copy(pcIn + n, *(pOut->reserved4+i)); n += 1; //1byte   uint8  reserved4
        }
    }

    big_reverse_copy(pcIn + n,  pOut->reservedDataLength5    );      n += 4;   //4byte    uint32_t   reservedDataLength5
    if (pOut->reservedDataLength5 > 0)
    {
        int count = pOut->reservedDataLength5 / sizeof(float32);
        pOut->reserved5 = new float32[count];
        memset(pOut->reserved5, 0, sizeof(float32)*count);
        for (int i = 0; i < count; ++i) //reserved5
        {
            big_reverse_copy(pcIn + n, *(pOut->reserved5+i)); n += 1; //1byte   uint8  reserved5
        }
    }
}

//23.HPAMapDataNotify
void HPAMapDataNotifySerialization(std::shared_ptr<stHPAMapDataNotify> pIn, char* pcOut)
{
    int n = 0, count = 0;

    sp_big_reverse_copy(pIn->Checksum       ,pcOut + n, 4);      n += 4;   //4byte    uint32_t		Checksum
    sp_big_reverse_copy(pIn->Counter        ,pcOut + n, 2);      n += 2;   //2byte    uint16_t		Counter
    sp_big_reverse_copy(pIn->timestamp      ,pcOut + n, 8);      n += 8;   //8byte    double		timestamp
    
    sp_big_reverse_copy(pIn->FieldLength_GlobalTrackPoint_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     FieldLength_GlobalTrackPoint_len
    if (pIn->FieldLength_GlobalTrackPoint_len > 0) //stFieldLength_GlobalTrackPointHPAMDN
    {
        count = pIn->FieldLength_GlobalTrackPoint_len / sizeof(stFieldLength_GlobalTrackPointHPAMDN);
        int tt = sizeof(stFieldLength_GlobalTrackPointHPAMDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_GlobalTrackPoint+i)->GlobalTrackPointID_i     ,pcOut + n, 4);      n += 4;   //4byte   uint32_t		    GlobalTrackPointID_i
            sp_big_reverse_copy((pIn->FieldLength_GlobalTrackPoint+i)->x_i                      ,pcOut + n, 4);      n += 4;   //4byte   float32		    x_i
            sp_big_reverse_copy((pIn->FieldLength_GlobalTrackPoint+i)->y_i                      ,pcOut + n, 4);      n += 4;   //4byte   float32		    y_i
            sp_big_reverse_copy((pIn->FieldLength_GlobalTrackPoint+i)->z_i                      ,pcOut + n, 4);      n += 4;   //4byte   float32		    z_i
            sp_big_reverse_copy((pIn->FieldLength_GlobalTrackPoint+i)->Width                    ,pcOut + n, 4);      n += 4;   //4byte   float32		    Width
        }
    }

    sp_big_reverse_copy(pIn->BuildMapStartPoint_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     BuildMapStartPoint_len
    if (pIn->BuildMapStartPoint_len > 0) //stBuildMapStartPointHPAMDN
    {
        count = pIn->BuildMapStartPoint_len / sizeof(stBuildMapStartPointHPAMDN);
        int tt = sizeof(stBuildMapStartPointHPAMDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->BuildMapStartPoint+i)->x_start     ,pcOut + n, 4);      n += 4;   //4byte   float32		    x_start
            sp_big_reverse_copy((pIn->BuildMapStartPoint+i)->y_start     ,pcOut + n, 4);      n += 4;   //4byte   float32		    y_start
            sp_big_reverse_copy((pIn->BuildMapStartPoint+i)->z_start     ,pcOut + n, 4);      n += 4;   //4byte   float32		    z_start
            sp_big_reverse_copy((pIn->BuildMapStartPoint+i)->x_stop      ,pcOut + n, 4);      n += 4;   //4byte   float32		    x_stop 
            sp_big_reverse_copy((pIn->BuildMapStartPoint+i)->y_stop      ,pcOut + n, 4);      n += 4;   //4byte   float32		    y_stop 
            sp_big_reverse_copy((pIn->BuildMapStartPoint+i)->z_stop      ,pcOut + n, 4);      n += 4;   //4byte   float32		    z_stop 
        }
    }

    sp_big_reverse_copy(pIn->FieldLength_Rampway_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     FieldLength_Rampway_len
    if (pIn->FieldLength_Rampway_len > 0) //stFieldLength_RampwayHPAMDN
    {
        count = pIn->FieldLength_Rampway_len / sizeof(stFieldLength_RampwayHPAMDN);
        int tt = sizeof(stFieldLength_RampwayHPAMDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_Rampway+i)->RampwayID_i   ,pcOut + n, 4);      n += 4;   //4byte   uint32_t		    RampwayID_i
            sp_big_reverse_copy((pIn->FieldLength_Rampway+i)->x1_i          ,pcOut + n, 4);      n += 4;   //4byte   float32		    x1_i
            sp_big_reverse_copy((pIn->FieldLength_Rampway+i)->y1_i          ,pcOut + n, 4);      n += 4;   //4byte   float32		    y1_i
            sp_big_reverse_copy((pIn->FieldLength_Rampway+i)->z1_i          ,pcOut + n, 4);      n += 4;   //4byte   float32		    z1_i
            sp_big_reverse_copy((pIn->FieldLength_Rampway+i)->x2_i          ,pcOut + n, 4);      n += 4;   //4byte   float32		    x2_i
            sp_big_reverse_copy((pIn->FieldLength_Rampway+i)->y2_i          ,pcOut + n, 4);      n += 4;   //4byte   float32		    y2_i
            sp_big_reverse_copy((pIn->FieldLength_Rampway+i)->z2_i          ,pcOut + n, 4);      n += 4;   //4byte   float32		    z2_i
        }
    }

    sp_big_reverse_copy(pIn->FieldLength_SpeedBumps_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     FieldLength_SpeedBumps_len
    if (pIn->FieldLength_SpeedBumps_len > 0) //stFieldLength_SpeedBumpsHPAMDN
    {
        count = pIn->FieldLength_SpeedBumps_len / sizeof(stFieldLength_SpeedBumpsHPAMDN);
        int tt = sizeof(stFieldLength_SpeedBumpsHPAMDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_SpeedBumps+i)->SpeedBumpsID_i     ,pcOut + n, 4);      n += 4;   //4byte   uint32_t	    SpeedBumpsID_i
            sp_big_reverse_copy((pIn->FieldLength_SpeedBumps+i)->x_i_Left           ,pcOut + n, 4);      n += 4;   //4byte   float32        x_i_Left
            sp_big_reverse_copy((pIn->FieldLength_SpeedBumps+i)->y_i_Left           ,pcOut + n, 4);      n += 4;   //4byte   float32        y_i_Left
            sp_big_reverse_copy((pIn->FieldLength_SpeedBumps+i)->z_i_Left           ,pcOut + n, 4);      n += 4;   //4byte   float32        z_i_Left
            sp_big_reverse_copy((pIn->FieldLength_SpeedBumps+i)->x_i_Right          ,pcOut + n, 4);      n += 4;   //4byte   float32        x_i_Right
            sp_big_reverse_copy((pIn->FieldLength_SpeedBumps+i)->y_i_Right          ,pcOut + n, 4);      n += 4;   //4byte   float32        y_i_Right
            sp_big_reverse_copy((pIn->FieldLength_SpeedBumps+i)->z_i_Right          ,pcOut + n, 4);      n += 4;   //4byte   float32        z_i_Right
            sp_big_reverse_copy((pIn->FieldLength_SpeedBumps+i)->SpeedBumpsWidth    ,pcOut + n, 4);      n += 4;   //4byte   uint32_t       SpeedBumpsWidth
        }
    }

    sp_big_reverse_copy(pIn->FieldLength_UprightColumn_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     FieldLength_UprightColumn_len
    if (pIn->FieldLength_UprightColumn_len > 0) //stFieldLength_UprightColumnHPAMDN
    {
        count = pIn->FieldLength_UprightColumn_len / sizeof(stFieldLength_UprightColumnHPAMDN);
        int tt = sizeof(stFieldLength_UprightColumnHPAMDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->UprightColumnID_i   ,pcOut + n, 4);      n += 4;   //4byte   uint32_t	    UprightColumnID_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->x1_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    x1_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->y1_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    y1_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->z1_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    z1_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->x2_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    x2_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->y2_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    y2_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->z2_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    z2_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->x3_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    x3_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->y3_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    y3_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->z3_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    z3_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->x4_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    x4_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->y4_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    y4_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->z4_i                ,pcOut + n, 4);      n += 4;   //4byte   float32	    z4_i
            sp_big_reverse_copy((pIn->FieldLength_UprightColumn+i)->height_i            ,pcOut + n, 4);      n += 4;   //4byte   float32	    height_i
        }
    }

    sp_big_reverse_copy(pIn->FieldLength_ParkngSpcI_len                 ,pcOut + n, 4);      n += 4;   //4byte    uint32_t     FieldLength_ParkngSpcI_len
    if (pIn->FieldLength_ParkngSpcI_len > 0) //stFieldLength_ParkngSpcIHPAMDN
    {
        count = pIn->FieldLength_ParkngSpcI_len / sizeof(stFieldLength_ParkngSpcIHPAMDN);
        int tt = sizeof(stFieldLength_ParkngSpcIHPAMDN);
        for (int i = 0; i < count; ++i)
        {
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->ParkngSpcID_i  ,pcOut + n, 4);      n += 4;   //4byte   uint32_t		ParkngSpcID_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->ParkngSpcSts   ,pcOut + n, 1);      n += 1;   //1byte   uint8_t		ParkngSpcSts
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->x1_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		x1_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->y1_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		y1_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->z1_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		z1_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->x2_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		x2_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->y2_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		y2_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->z2_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		z2_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->x3_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		x3_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->y3_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		y3_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->z3_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		z3_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->x4_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		x4_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->y4_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		y4_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->z4_i           ,pcOut + n, 4);      n += 4;   //4byte   float32		z4_i
            sp_big_reverse_copy((pIn->FieldLength_ParkngSpcI+i)->TargetSlotID   ,pcOut + n, 4);      n += 4;   //4byte   uint32_t		TargetSlotID
        }
    }
}

void HPAMapDataNotifyDeserialization(const char* pcIn, std::shared_ptr<stHPAMapDataNotify> pOut)
{
    int n = 0;
    big_reverse_copy(pcIn + n,  pOut->Checksum            );      n += 4;   //4byte    uint32_t		Checksum
    big_reverse_copy(pcIn + n,  pOut->Counter             );      n += 2;   //2byte    uint16_t		Counter
    big_reverse_copy(pcIn + n,  pOut->timestamp           );      n += 8;   //8byte    double		timestamp
    
    big_reverse_copy(pcIn + n,  pOut->FieldLength_GlobalTrackPoint_len    );      n += 4;   //4byte    uint32_t     FieldLength_GlobalTrackPoint_len
    if (pOut->FieldLength_GlobalTrackPoint_len > 0)
    {
        int count = pOut->FieldLength_GlobalTrackPoint_len / sizeof(stFieldLength_GlobalTrackPointHPAMDN);
        int tt = sizeof(stFieldLength_GlobalTrackPointHPAMDN);
        pOut->FieldLength_GlobalTrackPoint = new stFieldLength_GlobalTrackPointHPAMDN[count];
        memset(pOut->FieldLength_GlobalTrackPoint, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_GlobalTrackPoint
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_GlobalTrackPoint+i)->GlobalTrackPointID_i ); n += 4;   //4byte   uint32_t		    GlobalTrackPointID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_GlobalTrackPoint+i)->x_i                  ); n += 4;   //4byte   float32		    x_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_GlobalTrackPoint+i)->y_i                  ); n += 4;   //4byte   float32		    y_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_GlobalTrackPoint+i)->z_i                  ); n += 4;   //4byte   float32		    z_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_GlobalTrackPoint+i)->Width                ); n += 4;   //4byte   float32		    Width
        }
    }

    big_reverse_copy(pcIn + n,  pOut->BuildMapStartPoint_len    );      n += 4;   //4byte    uint32_t     BuildMapStartPoint_len
    if (pOut->BuildMapStartPoint_len > 0)
    {
        int count = pOut->BuildMapStartPoint_len / sizeof(stBuildMapStartPointHPAMDN);
        int tt = sizeof(stBuildMapStartPointHPAMDN);
        pOut->BuildMapStartPoint = new stBuildMapStartPointHPAMDN[count];
        memset(pOut->BuildMapStartPoint, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //BuildMapStartPoint
        {
            big_reverse_copy(pcIn + n, (pOut->BuildMapStartPoint+i)->x_start      ); n += 4;   //4byte   float32		    x1_i
            big_reverse_copy(pcIn + n, (pOut->BuildMapStartPoint+i)->y_start      ); n += 4;   //4byte   float32		    y1_i
            big_reverse_copy(pcIn + n, (pOut->BuildMapStartPoint+i)->z_start      ); n += 4;   //4byte   float32		    z1_i
            big_reverse_copy(pcIn + n, (pOut->BuildMapStartPoint+i)->x_stop       ); n += 4;   //4byte   float32		    x2_i
            big_reverse_copy(pcIn + n, (pOut->BuildMapStartPoint+i)->y_stop       ); n += 4;   //4byte   float32		    y2_i
            big_reverse_copy(pcIn + n, (pOut->BuildMapStartPoint+i)->z_stop       ); n += 4;   //4byte   float32		    z2_i
        }
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_Rampway_len    );      n += 4;   //4byte    uint32_t     FieldLength_Rampway_len
    if (pOut->FieldLength_Rampway_len > 0)
    {
        int count = pOut->FieldLength_Rampway_len / sizeof(stFieldLength_RampwayHPAMDN);
        int tt = sizeof(stFieldLength_RampwayHPAMDN);
        pOut->FieldLength_Rampway = new stFieldLength_RampwayHPAMDN[count];
        memset(pOut->FieldLength_Rampway, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_Rampway
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Rampway+i)->RampwayID_i  ); n += 4;   //4byte   uint32_t		    RampwayID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Rampway+i)->x1_i         ); n += 4;   //4byte   float32		    x1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Rampway+i)->y1_i         ); n += 4;   //4byte   float32		    y1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Rampway+i)->z1_i         ); n += 4;   //4byte   float32		    z1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Rampway+i)->x2_i         ); n += 4;   //4byte   float32		    x2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Rampway+i)->y2_i         ); n += 4;   //4byte   float32		    y2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_Rampway+i)->z2_i         ); n += 4;   //4byte   float32		    z2_i
        }
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_SpeedBumps_len    );      n += 4;   //4byte    uint32_t     FieldLength_SpeedBumps_len
    if (pOut->FieldLength_SpeedBumps_len > 0)
    {
        int count = pOut->FieldLength_SpeedBumps_len / sizeof(stFieldLength_SpeedBumpsHPAMDN);
        int tt = sizeof(stFieldLength_SpeedBumpsHPAMDN);
        pOut->FieldLength_SpeedBumps = new stFieldLength_SpeedBumpsHPAMDN[count];
        memset(pOut->FieldLength_SpeedBumps, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //LinkItemInfo2
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_SpeedBumps+i)->SpeedBumpsID_i    ); n += 4;   //4byte   uint32_t	    SpeedBumpsID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_SpeedBumps+i)->x_i_Left          ); n += 4;   //4byte   float32        x_i_Left
            big_reverse_copy(pcIn + n, (pOut->FieldLength_SpeedBumps+i)->y_i_Left          ); n += 4;   //4byte   float32        y_i_Left
            big_reverse_copy(pcIn + n, (pOut->FieldLength_SpeedBumps+i)->z_i_Left          ); n += 4;   //4byte   float32        z_i_Left
            big_reverse_copy(pcIn + n, (pOut->FieldLength_SpeedBumps+i)->x_i_Right         ); n += 4;   //4byte   float32        x_i_Right
            big_reverse_copy(pcIn + n, (pOut->FieldLength_SpeedBumps+i)->y_i_Right         ); n += 4;   //4byte   float32        y_i_Right
            big_reverse_copy(pcIn + n, (pOut->FieldLength_SpeedBumps+i)->z_i_Right         ); n += 4;   //4byte   float32        z_i_Right
            big_reverse_copy(pcIn + n, (pOut->FieldLength_SpeedBumps+i)->SpeedBumpsWidth   ); n += 4;   //4byte   uint32_t       SpeedBumpsWidth
        }
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_UprightColumn_len    );      n += 4;   //4byte    uint32_t     FieldLength_UprightColumn_len
    if (pOut->FieldLength_UprightColumn_len > 0)
    {
        int count = pOut->FieldLength_UprightColumn_len / sizeof(stFieldLength_UprightColumnHPAMDN);
        int tt = sizeof(stFieldLength_UprightColumnHPAMDN);
        pOut->FieldLength_UprightColumn = new stFieldLength_UprightColumnHPAMDN[count];
        memset(pOut->FieldLength_UprightColumn, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //FieldLength_UprightColumn
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->UprightColumnID_i  ); n += 4;   //4byte   uint32_t	    UprightColumnID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->x1_i               ); n += 4;   //4byte   float32	    x1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->y1_i               ); n += 4;   //4byte   float32	    y1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->z1_i               ); n += 4;   //4byte   float32	    z1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->x2_i               ); n += 4;   //4byte   float32	    x2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->y2_i               ); n += 4;   //4byte   float32	    y2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->z2_i               ); n += 4;   //4byte   float32	    z2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->x3_i               ); n += 4;   //4byte   float32	    x3_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->y3_i               ); n += 4;   //4byte   float32	    y3_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->z3_i               ); n += 4;   //4byte   float32	    z3_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->x4_i               ); n += 4;   //4byte   float32	    x4_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->y4_i               ); n += 4;   //4byte   float32	    y4_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->z4_i               ); n += 4;   //4byte   float32	    z4_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_UprightColumn+i)->height_i           ); n += 4;   //4byte   float32	    height_i
        }
    }

    big_reverse_copy(pcIn + n,  pOut->FieldLength_ParkngSpcI_len    );      n += 4;   //4byte    uint32_t     FieldLength_ParkngSpcI_len
    if (pOut->FieldLength_ParkngSpcI_len > 0)
    {
        int count = pOut->FieldLength_ParkngSpcI_len / sizeof(stFieldLength_ParkngSpcIHPAMDN);
        int tt = sizeof(stFieldLength_ParkngSpcIHPAMDN);
        pOut->FieldLength_ParkngSpcI = new stFieldLength_ParkngSpcIHPAMDN[count];
        memset(pOut->FieldLength_ParkngSpcI, 0, sizeof(uint8_t)*count);
        for (int i = 0; i < count; ++i) //LinkItemInfo2
        {
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->ParkngSpcID_i   ); n += 4;   //4byte   uint32_t	ParkngSpcID_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->ParkngSpcSts    ); n += 1;   //1byte   uint8_t		ParkngSpcSts
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->x1_i            ); n += 4;   //4byte   float32		x1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->y1_i            ); n += 4;   //4byte   float32		y1_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->z1_i            ); n += 4;   //4byte   float32		z1_i(pOut->FieldLength_ParkngSpcI+i)->LinkItemFormway3    ); n += 4;   //4byte   int32_t         LinkItemFormway3
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->x2_i            ); n += 4;   //4byte   float32		x2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->y2_i            ); n += 4;   //4byte   float32		y2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->z2_i            ); n += 4;   //4byte   float32		z2_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->x3_i            ); n += 4;   //4byte   float32		x3_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->y3_i            ); n += 4;   //4byte   float32		y3_i(pOut->FieldLength_ParkngSpcI+i)->LinkItemFormway3    ); n += 4;   //4byte   int32_t         LinkItemFormway3
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->z3_i            ); n += 4;   //4byte   float32		z3_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->x4_i            ); n += 4;   //4byte   float32		x4_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->y4_i            ); n += 4;   //4byte   float32		y4_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->z4_i            ); n += 4;   //4byte   float32		z4_i
            big_reverse_copy(pcIn + n, (pOut->FieldLength_ParkngSpcI+i)->TargetSlotID    ); n += 4;   //4byte   uint32_t	TargetSlotID
        }
    }
}


// 序列化
void SPSerialization(std::shared_ptr<stVehiclePositionInfoNotify> pIn, char* pcOut)    {VehiclePositionInfoNotifySerialization(         pIn, pcOut);}
void SPSerialization(std::shared_ptr<stRTKInfoNotify> pIn, char* pcOut)                {RTKInfoNotifySerialization(                     pIn, pcOut);}
void SPSerialization(std::shared_ptr<stIMUInfoNotify> pIn, char* pcOut)                {IMUInfoNotifySerialization(                     pIn, pcOut);}
void SPSerialization(std::shared_ptr<stObstacleInfoNotify> pIn, char* pcOut)           {ObstacleInfoNotifySerialization(                pIn, pcOut);}
void SPSerialization(std::shared_ptr<stLanelineDataNotify> pIn, char* pcOut)           {LanelineDataNotifySerialization(                pIn, pcOut);}
void SPSerialization(std::shared_ptr<stChangeLaneDataNotify> pIn, char* pcOut)         {ChangeLaneDataNotifySerialization(              pIn, pcOut);}
void SPSerialization(std::shared_ptr<stPilotStatusNotify> pIn, char* pcOut)            {PilotStatusNotifySerialization(                 pIn, pcOut);}
void SPSerialization(std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> pIn, char* pcOut){PilotAlarmAndNoticeInfoNotifySerialization(     pIn, pcOut);}
void SPSerialization(std::shared_ptr<stBroadcastInfoNotify> pIn, char* pcOut)          {BroadcastInfoNotifySerialization(               pIn, pcOut);}
//void SPSerialization(std::shared_ptr<stPlanningLineInfoNotify> pIn, char* pcOut)       {PlanningLineInfoNotifySerialization(            pIn, pcOut);}
void SPSerialization(std::shared_ptr<stHudRoadInfoNotify> pIn, char* pcOut)            {HudRoadInfoNotifySerialization(                 pIn, pcOut);}
void SPSerialization(std::shared_ptr<stHudMappathInfo_EG> pIn, char* pcOut)            {HudMappathInfo_EGSerialization(                 pIn, pcOut);}
void SPSerialization(std::shared_ptr<stHudNavigationmap> pIn, char* pcOut)             {HudNavigationmapSerialization(                  pIn, pcOut);}
void SPSerialization(std::shared_ptr<oshrinfo_t> pIn, char* pcOut)                     {OverseasHudRoadInfoNotifySerialization(         pIn, pcOut);}

void SPSerialization(std::shared_ptr<stNewLanelineDataNotify>           pIn, char* pcOut)   {NewLanelineDataNotifySerialization(             pIn, pcOut);}
void SPSerialization(std::shared_ptr<stNewBroadcastInfoNotify>          pIn, char* pcOut)   {NewBroadcastInfoNotifySerialization(            pIn, pcOut);}
void SPSerialization(std::shared_ptr<stPlanningLineInfoNotify>          pIn, char* pcOut)   {PlanningLineInfoNotifySerialization(            pIn, pcOut);}
void SPSerialization(std::shared_ptr<stNavigationStatus_LinkInfoNotify> pIn, char* pcOut)   {NavigationStatus_LinkInfoNotifySerialization(   pIn, pcOut);}
void SPSerialization(std::shared_ptr<stNewParkingRealTimeDataNotify>    pIn, char* pcOut)   {NewParkingRealTimeDataNotifySerialization(      pIn, pcOut);}
void SPSerialization(std::shared_ptr<stNavigationHDLink2Info>           pIn, char* pcOut)   {NavigationHDLink2InfoSerialization(             pIn, pcOut);}
void SPSerialization(std::shared_ptr<stsdTraffiIncident>                pIn, char* pcOut)   {sdTraffiIncidentSerialization(                  pIn, pcOut);}
void SPSerialization(std::shared_ptr<stnewPlanningLineInfo>             pIn, char* pcOut)   {newPlanningLineInfoSerialization(               pIn, pcOut);}
void SPSerialization(std::shared_ptr<stdrivingAreaIdentification>       pIn, char* pcOut)   {drivingAreaIdentificationsSerialization(        pIn, pcOut);}
void SPSerialization(std::shared_ptr<stHPAMapDataNotify>                pIn, char* pcOut)   {HPAMapDataNotifySerialization(                  pIn, pcOut);}

// 反序列化
void SPDeserialization(const char* pcIn, std::shared_ptr<stVehiclePositionInfoNotify> pOut)    {VehiclePositionInfoNotifyDeserialization(    pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stRTKInfoNotify> pOut)                {RTKInfoNotifyDeserialization(                pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stIMUInfoNotify> pOut)                {IMUInfoNotifyDeserialization(                pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stObstacleInfoNotify> pOut)           {ObstacleInfoNotifyDeserialization(           pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stLanelineDataNotify> pOut)           {LanelineDataNotifyDeserialization(           pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stChangeLaneDataNotify> pOut)         {ChangeLaneDataNotifyDeserialization(         pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stPilotStatusNotify> pOut)            {PilotStatusNotifyDeserialization(            pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> pOut){PilotAlarmAndNoticeInfoNotifyDeserialization(pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stBroadcastInfoNotify> pOut)          {BroadcastInfoNotifyDeserialization(          pcIn, pOut);}
//void SPDeserialization(const char* pcIn, std::shared_ptr<stPlanningLineInfoNotify> pOut)       {PlanningLineInfoNotifyDeserialization(       pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stHudRoadInfoNotify> pOut)            {HudRoadInfoNotifyDeserialization(            pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stHudMappathInfo_EG> pOut)            {HudMappathInfo_EGDeserialization(            pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stHudNavigationmap> pOut)             {HudNavigationmapDeserialization(             pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<oshrinfo_t> pOut)                     {overseasHudRoadInfoNotifyDeserialization(    pcIn, pOut);}

void SPDeserialization(const char* pcIn, std::shared_ptr<stNewLanelineDataNotify>           pOut)  {NewLanelineDataNotifyDeserialization(              pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stNewBroadcastInfoNotify>          pOut)  {NewBroadcastInfoNotifyDeserialization(             pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stPlanningLineInfoNotify>          pOut)  {PlanningLineInfoNotifyDeserialization(             pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stNavigationStatus_LinkInfoNotify> pOut)  {NavigationStatus_LinkInfoNotifyDeserialization(    pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stNewParkingRealTimeDataNotify>    pOut)  {NewParkingRealTimeDataNotifyDeserialization(       pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stNavigationHDLink2Info>           pOut)  {NavigationHDLink2InfoDeserialization(              pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stsdTraffiIncident>                pOut)  {sdTraffiIncidentDeserialization(                   pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stnewPlanningLineInfo>             pOut)  {newPlanningLineInfoDeserialization(                pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stdrivingAreaIdentification>       pOut)  {drivingAreaIdentificationsDeserialization(         pcIn, pOut);}
void SPDeserialization(const char* pcIn, std::shared_ptr<stHPAMapDataNotify>                pOut)  {HPAMapDataNotifyDeserialization(                   pcIn, pOut);}
