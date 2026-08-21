
/******************************************************************************
*brief:     autosar SOME/IP serialization and deserialization
*version:   1.0
*author:    li.peng89
*time:      2023/06/09
******************************************************************************/

#ifndef AR_HUD_SOMEIP_DATA_CONVERSION_H
#define AR_HUD_SOMEIP_DATA_CONVERSION_H

#include "ArHudSomeipDataType.h"
#include <memory>
#include <algorithm>
using std::shared_ptr;

template <class T>
inline void big_reverse_copy(T from, char* to)
{
#     ifdef BOOST_BIG_ENDIAN
  std::memcpy(to, reinterpret_cast<const char*>(&from), sizeof(T));
#     else
  std::reverse_copy(reinterpret_cast<const char*>(&from),
    reinterpret_cast<const char*>(&from) + sizeof(T), to);
#     endif
}

template <class T>
inline void big_reverse_copy(const char* from, T& to)
{
#     ifdef BOOST_BIG_ENDIAN
  std::memcpy(reinterpret_cast<char*>(&to), from, sizeof(T));
#     else
  std::reverse_copy(from, from + sizeof(T), reinterpret_cast<char*>(&to));
#     endif
}

template <class T>
inline void sp_big_reverse_copy(T from, char* to, int len)
{    
#     ifdef BOOST_BIG_ENDIAN
    memcpy(to, reinterpret_cast<const char*>(&from), len);
#     else
    std::reverse_copy(reinterpret_cast<const char*>(&from),
    reinterpret_cast<const char*>(&from) + len, to);
#     endif
}

// 序列化
void VehiclePositionInfoNotifySerialization(        std::shared_ptr<stVehiclePositionInfoNotify> pIn, char* pcOut);
void RTKInfoNotifySerialization(                    std::shared_ptr<stRTKInfoNotify> pIn, char* pcOut);
void IMUInfoNotifySerialization(                    std::shared_ptr<stIMUInfoNotify> pIn, char* pcOut);
void ObstacleInfoNotifySerialization(               std::shared_ptr<stObstacleInfoNotify> pIn, char* pcOut);
void LanelineDataNotifySerialization(               std::shared_ptr<stLanelineDataNotify> pIn, char* pcOut);
void ChangeLaneDataNotifySerialization(             std::shared_ptr<stChangeLaneDataNotify> pIn, char* pcOut);
void PilotStatusNotifySerialization(                std::shared_ptr<stPilotStatusNotify> pIn, char* pcOut);
void PilotAlarmAndNoticeInfoNotifySerialization(    std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> pIn, char* pcOut);
void BroadcastInfoNotifySerialization(              std::shared_ptr<stBroadcastInfoNotify> pIn, char* pcOut);
//void PlanningLineInfoNotifySerialization(           std::shared_ptr<stPlanningLineInfoNotify> pIn, char* pcOut);
void HudRoadInfoNotifySerialization(                std::shared_ptr<stHudRoadInfoNotify> pIn, char* pcOut);
void HudMappathInfo_EGSerialization(                std::shared_ptr<stHudMappathInfo_EG> pIn, char* pcOut);
void HudNavigationmapSerialization(                 std::shared_ptr<stHudNavigationmap> pIn, char* pcOut);
void OverseasHudRoadInfoNotifySerialization(        std::shared_ptr<oshrinfo_t> pIn, char* pcOut);

void stNewLanelineDataNotifySerialization(        std::shared_ptr<stNewLanelineDataNotify> pIn, char* pcOut);
void stNewBroadcastInfoNotifySerialization(        std::shared_ptr<stNewBroadcastInfoNotify> pIn, char* pcOut);
void stPlanningLineInfoNotifySerialization(        std::shared_ptr<stPlanningLineInfoNotify> pIn, char* pcOut);
void stNavigationStatus_LinkInfoNotifySerialization(        std::shared_ptr<stNavigationStatus_LinkInfoNotify> pIn, char* pcOut);
void stNewParkingRealTimeDataNotifySerialization(        std::shared_ptr<stNewParkingRealTimeDataNotify> pIn, char* pcOut);
void stNavigationHDLink2InfoSerialization(        std::shared_ptr<stNavigationHDLink2Info> pIn, char* pcOut);
void stsdTraffiIncidentSerialization(        std::shared_ptr<stsdTraffiIncident> pIn, char* pcOut);
void stnewPlanningLineInfoSerialization(        std::shared_ptr<stnewPlanningLineInfo> pIn, char* pcOut);
void stdrivingAreaIdentificationSerialization(        std::shared_ptr<stdrivingAreaIdentification> pIn, char* pcOut);
void stHPAMapDataNotifySerialization(        std::shared_ptr<stHPAMapDataNotify> pIn, char* pcOut);

// 反序列化
void VehiclePositionInfoNotifyDeserialization(      const char* pcInput, std::shared_ptr<stVehiclePositionInfoNotify> pOut);
void RTKInfoNotifyDeserialization(                  const char* pcInput, std::shared_ptr<stRTKInfoNotify> pOut);
void IMUInfoNotifyDeserialization(                  const char* pcInput, std::shared_ptr<stIMUInfoNotify> pOut);
void ObstacleInfoNotifyDeserialization(             const char* pcInput, std::shared_ptr<stObstacleInfoNotify> pOut);
void LanelineDataNotifyDeserialization(             const char* pcInput, std::shared_ptr<stLanelineDataNotify> pOut);
void ChangeLaneDataNotifyDeserialization(           const char* pcInput, std::shared_ptr<stChangeLaneDataNotify> pOut);
void PilotStatusNotifyDeserialization(              const char* pcInput, std::shared_ptr<stPilotStatusNotify> pOut);
void PilotAlarmAndNoticeInfoNotifyDeserialization(  const char* pcInput, std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> pOut);
void BroadcastInfoNotifyDeserialization(            const char* pcInput, std::shared_ptr<stBroadcastInfoNotify> pOut);
//void PlanningLineInfoNotifyDeserialization(         const char* pcInput, std::shared_ptr<stPlanningLineInfoNotify> pOut);
void HudRoadInfoNotifyDeserialization(              const char* pcInput, std::shared_ptr<stHudRoadInfoNotify> pOut);
void HudMappathInfo_EGDeserialization(              const char* pcInput, std::shared_ptr<stHudMappathInfo_EG> pOut);
void HudNavigationmapDeserialization(               const char* pcInput, std::shared_ptr<stHudNavigationmap> pOut);
void OverseasHudRoadInfoNotifyDeserialization(      const char* pcIn,    std::shared_ptr<oshrinfo_t> pOut);

void stNewLanelineDataNotifyDeserialization(      const char* pcIn,    std::shared_ptr<stNewLanelineDataNotify> pOut);
void stNewBroadcastInfoNotifyDeserialization(      const char* pcIn,    std::shared_ptr<stNewBroadcastInfoNotify> pOut);
void stPlanningLineInfoNotifyDeserialization(      const char* pcIn,    std::shared_ptr<stPlanningLineInfoNotify> pOut);
void stNavigationStatus_LinkInfoNotifyDeserialization(      const char* pcIn,    std::shared_ptr<stNavigationStatus_LinkInfoNotify> pOut);
void stNewParkingRealTimeDataNotifyDeserialization(      const char* pcIn,    std::shared_ptr<stNewParkingRealTimeDataNotify> pOut);
void stNavigationHDLink2InfoDeserialization(      const char* pcIn,    std::shared_ptr<stNavigationHDLink2Info> pOut);
void stsdTraffiIncidentDeserialization(      const char* pcIn,    std::shared_ptr<stsdTraffiIncident> pOut);
void stnewPlanningLineInfoDeserialization(      const char* pcIn,    std::shared_ptr<stnewPlanningLineInfo> pOut);
void stdrivingAreaIdentificationDeserialization(      const char* pcIn,    std::shared_ptr<stdrivingAreaIdentification> pOut);
void stHPAMapDataNotifyDeserialization(      const char* pcIn,    std::shared_ptr<stHPAMapDataNotify> pOut);




void SPSerialization(std::shared_ptr<stVehiclePositionInfoNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stRTKInfoNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stIMUInfoNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stObstacleInfoNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stLanelineDataNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stChangeLaneDataNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stPilotStatusNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stBroadcastInfoNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stPlanningLineInfoNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stHudRoadInfoNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stHudMappathInfo_EG> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stHudNavigationmap> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<oshrinfo_t> pIn, char* pcOut);

void SPSerialization(std::shared_ptr<stNewLanelineDataNotify>           pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stNewBroadcastInfoNotify>          pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stPlanningLineInfoNotify>          pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stNavigationStatus_LinkInfoNotify> pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stNewParkingRealTimeDataNotify>    pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stNavigationHDLink2Info>           pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stsdTraffiIncident>                pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stnewPlanningLineInfo>             pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stdrivingAreaIdentification>       pIn, char* pcOut);
void SPSerialization(std::shared_ptr<stHPAMapDataNotify>                pIn, char* pcOut);

void SPDeserialization(const char* pcIn, std::shared_ptr<stVehiclePositionInfoNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stRTKInfoNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stIMUInfoNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stObstacleInfoNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stLanelineDataNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stChangeLaneDataNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stPilotStatusNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stBroadcastInfoNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stPlanningLineInfoNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stHudRoadInfoNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stHudMappathInfo_EG> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stHudNavigationmap> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<oshrinfo_t> pOut);

void SPDeserialization(const char* pcIn, std::shared_ptr<stNewLanelineDataNotify>           pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stNewBroadcastInfoNotify>          pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stPlanningLineInfoNotify>          pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stNavigationStatus_LinkInfoNotify> pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stNewParkingRealTimeDataNotify>    pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stNavigationHDLink2Info>           pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stsdTraffiIncident>                pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stnewPlanningLineInfo>             pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stdrivingAreaIdentification>       pOut);
void SPDeserialization(const char* pcIn, std::shared_ptr<stHPAMapDataNotify>                pOut);

#endif