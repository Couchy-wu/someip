#ifndef CPP_COMMON_H
#define CPP_COMMON_H

#include <stdint.h>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <algorithm>
#include "ArHudSomeipDataType.h"

extern std::string gpath;

unsigned int sp_reflect(unsigned int data, unsigned char nBits);
unsigned int sp_crc32(unsigned char *message, int nBytes);
void SPHexToStr(unsigned char* pOutStr, unsigned char* pInHex, int hexLen);
void SPStrToHex(unsigned char* pInStr, unsigned char* pOutHex, int strLen);
void LoadIni();
void SPSplit(const std::string str, std::vector<std::string>& vecOut, const std::string delimiters);

uint32_t SetVehiclePositionInfoNotify(stVehiclePositionInfoNotify& stDy);
uint32_t SetRTKInfoNotify(stRTKInfoNotify& stDy);
uint32_t SetIMUInfoNotify(stIMUInfoNotify& stDy);
uint32_t SetObstacleInfoNotify(stObstacleInfoNotify& stDy);
uint32_t SetLanelineDataNotify(stLanelineDataNotify& stDy);
uint32_t SetChangeLaneDataNotify(stChangeLaneDataNotify& stDy);
uint32_t SetPilotStatusNotify(stPilotStatusNotify& stDy);
uint32_t SetPilotAlarmAndNoticeInfoNotify(stPilotAlarmAndNoticeInfoNotify& stDy);
uint32_t SetBroadcastInfoNotify(stBroadcastInfoNotify& stDy);
uint32_t SetPlanningLineInfoNotify(stPlanningLineInfoNotify& stDy);
uint32_t SetHudRoadInfoNotify(stHudRoadInfoNotify& stDy);
uint32_t SetHudMappathInfo_EG(stHudMappathInfo_EG& stDy);
uint32_t SetHudNavigationmap(stHudNavigationmap& stDy);
uint32_t SetOverseasHudRoadInfoNotify(oshrinfo_t& stDy);
uint32_t SetOverseasHudRoadInfoNotify2(oshrinfo_t& stDy);

uint32_t SetNewLanelineDataNotify2(stNewLanelineDataNotify& stDy);
uint32_t SetNewBroadcastInfoNotify2(stNewBroadcastInfoNotify& stDy);
uint32_t SetPlanningLineInfoNotify2(stPlanningLineInfoNotify& stDy);
uint32_t SetNavigationStatus_LinkInfoNotify2(stNavigationStatus_LinkInfoNotify& stDy);
uint32_t SetNewParkingRealTimeDataNotify2(stNewParkingRealTimeDataNotify& stDy);
uint32_t SetNavigationHDLink2Info2(stNavigationHDLink2Info& stDy);
uint32_t SetsdTraffiIncident2(stsdTraffiIncident& stDy);
uint32_t SetnewPlanningLineInfo2(stnewPlanningLineInfo& stDy);
uint32_t SetdrivingAreaIdentification2(stdrivingAreaIdentification& stDy);
uint32_t SetHPAMapDataNotify2(stHPAMapDataNotify& stDy);

void DisplayVehiclePositionInfoNotify(stVehiclePositionInfoNotify& stDy);
void DisplayRTKInfoNotify(stRTKInfoNotify& stDy);
void DisplayIMUInfoNotify(stIMUInfoNotify& stDy);
void DisplayObstacleInfoNotify(stObstacleInfoNotify& stDy);
void DisplayLanelineDataNotify(stLanelineDataNotify& stDy);
void DisplayChangeLaneDataNotify(stChangeLaneDataNotify& stDy);
void DisplayPilotStatusNotify(stPilotStatusNotify& stDy);
void DisplayPilotAlarmAndNoticeInfoNotify(stPilotAlarmAndNoticeInfoNotify& stDy);
void DisplayBroadcastInfoNotify(stBroadcastInfoNotify& stDy);
void DisplayPlanningLineInfoNotify(stPlanningLineInfoNotify& stDy);
void DisplayHudRoadInfoNotify(stHudRoadInfoNotify& stDy);
void DisplayHudMappathInfo_EG(stHudMappathInfo_EG& stDy);
void DisplayHudNavigationmap(stHudNavigationmap& stDy);
void DisplayOverseasHudRoadInfoNotify(oshrinfo_t& stDy);

uint32_t SPSet(std::shared_ptr<stVehiclePositionInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stRTKInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stIMUInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stObstacleInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stLanelineDataNotify> stDy);
uint32_t SPSet(std::shared_ptr<stChangeLaneDataNotify> stDy);
uint32_t SPSet(std::shared_ptr<stPilotStatusNotify> stDy);
uint32_t SPSet(std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stBroadcastInfoNotify> stDy);
//uint32_t SPSet(std::shared_ptr<stPlanningLineInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stHudRoadInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stHudMappathInfo_EG> stDy);
uint32_t SPSet(std::shared_ptr<stHudNavigationmap> stDy);
uint32_t SPSet(std::shared_ptr<oshrinfo_t> stDy);

uint32_t SPSet(std::shared_ptr<stNewLanelineDataNotify> stDy);
uint32_t SPSet(std::shared_ptr<stNewBroadcastInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stPlanningLineInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stNavigationStatus_LinkInfoNotify> stDy);
uint32_t SPSet(std::shared_ptr<stNewParkingRealTimeDataNotify> stDy);
uint32_t SPSet(std::shared_ptr<stNavigationHDLink2Info> stDy);
uint32_t SPSet(std::shared_ptr<stsdTraffiIncident> stDy);
uint32_t SPSet(std::shared_ptr<stnewPlanningLineInfo> stDy);
uint32_t SPSet(std::shared_ptr<stdrivingAreaIdentification> stDy);
uint32_t SPSet(std::shared_ptr<stHPAMapDataNotify> stDy);


void SPDisplay(std::shared_ptr<stVehiclePositionInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stRTKInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stIMUInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stObstacleInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stLanelineDataNotify> stDy);
void SPDisplay(std::shared_ptr<stChangeLaneDataNotify> stDy);
void SPDisplay(std::shared_ptr<stPilotStatusNotify> stDy);
void SPDisplay(std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stBroadcastInfoNotify> stDy);
//void SPDisplay(std::shared_ptr<stPlanningLineInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stHudRoadInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stHudMappathInfo_EG> stDy);
void SPDisplay(std::shared_ptr<stHudNavigationmap> stDy);
void SPDisplay(std::shared_ptr<oshrinfo_t> stDy);

void SPDisplay(std::shared_ptr<stNewLanelineDataNotify> stDy);
void SPDisplay(std::shared_ptr<stNewBroadcastInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stPlanningLineInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stNavigationStatus_LinkInfoNotify> stDy);
void SPDisplay(std::shared_ptr<stNewParkingRealTimeDataNotify> stDy);
void SPDisplay(std::shared_ptr<stNavigationHDLink2Info> stDy);
void SPDisplay(std::shared_ptr<stsdTraffiIncident> stDy);  
void SPDisplay(std::shared_ptr<stnewPlanningLineInfo> stDy);
void SPDisplay(std::shared_ptr<stdrivingAreaIdentification> stDy);
void SPDisplay(std::shared_ptr<stHPAMapDataNotify> stDy);

void DisplayLanelineDataNotify2(stLanelineDataNotify& stDy);
void DisplayNewLanelineDataNotify2(stNewLanelineDataNotify& stDy);
char* unix_time_to_string_ms(uint64_t timeStampUs);

#endif