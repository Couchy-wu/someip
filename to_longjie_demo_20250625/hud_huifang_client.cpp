#include <chrono>
#include <thread>
#include <fstream>
#include <sstream>
#include <mutex>
#include <numeric>
#include <string.h>
#include <sys/stat.h>
#if _WIN32
#else
#include <sys/time.h>
#include <libgen.h>
#include <unistd.h>
#endif
#include <sys/types.h>
#include "vsomeip/SomeipCom.hpp"
#include "ArHudSomeipDataType.h"
#include "ArHudSomeipDataConversion.h"
#include "CppCommon.h"

#define MAX_EVENT_CNT 23	//支持的最大事件个数
uint32_t g_Cnt[MAX_EVENT_CNT] = { 0 };
int g_SendCount = 0;


//获取通知回调
std::mutex gMtx;
std::chrono::system_clock::time_point g_when;
int32_t DefaultClientNotifyRegistCallback(uint16_t snServiceId, uint16_t snInstanceId, uint16_t snMethodId, uint8_t* pcInput, uint32_t nInLen, void* pParam)//pcInput指向获取到的数据
{
    if (pcInput == NULL || nInLen == 0)
        return 0;
    // 打印时间戳
    std::lock_guard<std::mutex> its_lock(gMtx);
    int idx = -1;
    // if ((snServiceId == 0x000C && snInstanceId == 0x000C && snMethodId == 0x8002) ||
    // (snServiceId == 0x000C && snInstanceId == 0x000C && snMethodId == 0x8003))
    // {
    //     auto its_time_t = std::chrono::system_clock::to_time_t(g_when);
    //     auto its_time = std::localtime(&its_time_t);
    //     auto its_ms = (std::chrono::duration_cast<std::chrono::milliseconds>(g_when.time_since_epoch()))%1000;
    //     printf("\r\n%02d:%02d:%02d:%03ld: ", its_time->tm_hour, its_time->tm_min, its_time->tm_sec, its_ms.count());
    //     g_when = std::chrono::system_clock::now();
    // }

    //打印十六进制数据
    // unsigned char* pch = nullptr;
    // if (nInLen > 0)
    // {
    //     pch = new unsigned char[nInLen*2+1];
    //     memset(pch, 0, nInLen*2+1);
    //     SPHexToStr(pch, (unsigned char*)pcInput, nInLen);
    //     printf("收:<--");
    //     for (int i = 0; i <= nInLen*2; ++i)
    //     {
    //         if (i %2 == 0 && i != nInLen - 1 && i != 0)
    //             printf(" ");
    //         printf("%c", pch[i]);
    //         if ((i+1) % 40 == 0)
    //             printf("\r\n");
    //     }
    //     printf("\r\n");
    //     if (pch != nullptr)
    //     {
    //         delete[] pch;
    //         pch = nullptr;
    //     }
    //     printf("\r\nlen = %d\r\n\r\n", nInLen);     
    // }

    g_SendCount = std::accumulate(g_Cnt, g_Cnt + MAX_EVENT_CNT, 0);
    printf("收<--:total_count:%u event_cnt:%u serviceID:%04X instanceID:%04X eventID:%04X len:%u\r\n",
        g_SendCount, g_Cnt[idx], snServiceId, snInstanceId, snMethodId, nInLen);

    // 反序列化
         if (snServiceId == 0x000A && snInstanceId == 0x000A && snMethodId == 0x8001){++g_Cnt[0];  std::shared_ptr<stVehiclePositionInfoNotify>       stDy=std::make_shared<stVehiclePositionInfoNotify        >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000B && snInstanceId == 0x000B && snMethodId == 0x8001){++g_Cnt[1];  std::shared_ptr<stRTKInfoNotify>                   stDy=std::make_shared<stRTKInfoNotify                    >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000B && snInstanceId == 0x000B && snMethodId == 0x8002){++g_Cnt[2];  std::shared_ptr<stIMUInfoNotify>                   stDy=std::make_shared<stIMUInfoNotify                    >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000C && snInstanceId == 0x000C && snMethodId == 0x8001){++g_Cnt[3];  std::shared_ptr<stObstacleInfoNotify>              stDy=std::make_shared<stObstacleInfoNotify               >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000C && snInstanceId == 0x000C && snMethodId == 0x8002){++g_Cnt[4];  std::shared_ptr<stLanelineDataNotify>              stDy=std::make_shared<stLanelineDataNotify               >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8001){++g_Cnt[5];  std::shared_ptr<stChangeLaneDataNotify>            stDy=std::make_shared<stChangeLaneDataNotify             >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8002){++g_Cnt[6];  std::shared_ptr<stPilotStatusNotify>               stDy=std::make_shared<stPilotStatusNotify                >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8003){++g_Cnt[7];  std::shared_ptr<stPilotAlarmAndNoticeInfoNotify>   stDy=std::make_shared<stPilotAlarmAndNoticeInfoNotify    >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8004){++g_Cnt[8];  std::shared_ptr<stBroadcastInfoNotify>             stDy=std::make_shared<stBroadcastInfoNotify              >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x010A && snInstanceId == 0x0001 && snMethodId == 0x8001){++g_Cnt[9];  std::shared_ptr<stHudRoadInfoNotify>               stDy=std::make_shared<stHudRoadInfoNotify                >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x010A && snInstanceId == 0x0001 && snMethodId == 0x8002){++g_Cnt[10]; std::shared_ptr<stHudMappathInfo_EG>               stDy=std::make_shared<stHudMappathInfo_EG                >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x010A && snInstanceId == 0x0001 && snMethodId == 0x8003){++g_Cnt[11]; std::shared_ptr<stHudNavigationmap>                stDy=std::make_shared<stHudNavigationmap                 >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x010A && snInstanceId == 0x0001 && snMethodId == 0x8004){++g_Cnt[12]; std::shared_ptr<oshrinfo_t>                        stDy=std::make_shared<oshrinfo_t                         >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000C && snInstanceId == 0x000C && snMethodId == 0x8003){++g_Cnt[13]; std::shared_ptr<stNewLanelineDataNotify>           stDy=std::make_shared<stNewLanelineDataNotify            >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8005){++g_Cnt[14]; std::shared_ptr<stNewBroadcastInfoNotify>          stDy=std::make_shared<stNewBroadcastInfoNotify           >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000E && snInstanceId == 0x000E && snMethodId == 0x8001){++g_Cnt[15]; std::shared_ptr<stPlanningLineInfoNotify>          stDy=std::make_shared<stPlanningLineInfoNotify           >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x0007 && snInstanceId == 0x0007 && snMethodId == 0x8001){++g_Cnt[16]; std::shared_ptr<stNavigationStatus_LinkInfoNotify> stDy=std::make_shared<stNavigationStatus_LinkInfoNotify  >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x0017 && snInstanceId == 0x0017 && snMethodId == 0x8003){++g_Cnt[17]; std::shared_ptr<stNewParkingRealTimeDataNotify>    stDy=std::make_shared<stNewParkingRealTimeDataNotify     >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x002B && snInstanceId == 0x002B && snMethodId == 0x8001){++g_Cnt[18]; std::shared_ptr<stNavigationHDLink2Info>           stDy=std::make_shared<stNavigationHDLink2Info            >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x8202 && snInstanceId == 0x8202 && snMethodId == 0x8002){++g_Cnt[19]; std::shared_ptr<stsdTraffiIncident>                stDy=std::make_shared<stsdTraffiIncident                 >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000E && snInstanceId == 0x000E && snMethodId == 0x8002){++g_Cnt[20]; std::shared_ptr<stnewPlanningLineInfo>             stDy=std::make_shared<stnewPlanningLineInfo              >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x000E && snInstanceId == 0x000E && snMethodId == 0x8003){++g_Cnt[21]; std::shared_ptr<stdrivingAreaIdentification>       stDy=std::make_shared<stdrivingAreaIdentification        >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else if (snServiceId == 0x0018 && snInstanceId == 0x0018 && snMethodId == 0x8001){++g_Cnt[22]; std::shared_ptr<stHPAMapDataNotify>                stDy=std::make_shared<stHPAMapDataNotify                 >(); SPDeserialization((const char*)pcInput, stDy);  SPDisplay(stDy);}
    else{printf("\r\nother event\r\n");}

    return 0;
}


#include <csignal>

// SIGINT 信号处理函数
void signalHandler(int signal) {
    
    g_SendCount = std::accumulate(g_Cnt, g_Cnt + MAX_EVENT_CNT, 0);
    // 在这里添加您希望在程序关闭之前执行的操作代码
			printf("\r\n\
       event_type                      recv_count\r\n\
Total_count:                                                              %u\r\n\
0. (0x000A, 0x000A, 0x8001, 0x1101): VehiclePositionInfoNotify:           %u\r\n\
1. (0x000B, 0x000B, 0x8001, 0x1101): RTKInfoNotify:                       %u\r\n\
2. (0x000B, 0x000B, 0x8002, 0x1101): IMUInfoNotify:                       %u\r\n\
3. (0x000C, 0x000C, 0x8001, 0x1101): ObstacleInfoNotify:                  %u\r\n\
4. (0x000C, 0x000C, 0x8002, 0x1101): LaneLineDataNotify:                  %u\r\n\
5. (0x000D, 0x000D, 0x8001, 0x1101): ChangeLaneDataNotify:                %u\r\n\
6. (0x000D, 0x000D, 0x8002, 0x1101): PilotStatusNofity:                   %u\r\n\
7. (0x000D, 0x000D, 0x8003, 0x1101): PilotAlarmAndNoticeInfoNotify:       %u\r\n\
8. (0x000D, 0x000D, 0x8004, 0x1101): BroadcastInfoNotify:                 %u\r\n\
9. (0x010A, 0x0001, 0x8001, 0x1101): PlanningLineInfoNotify:              %u\r\n\
10.(0x010A, 0x0001, 0x8002, 0x1101): HudRoadInfo_EG:                      %u\r\n\
11.(0x010A, 0x0001, 0x8003, 0x1101): HudMappathInfoNotify:                %u\r\n\
12.(0x010A, 0x0001, 0x8004, 0x1101): HudNavigationmapNotify:              %u\r\n\
\
13.(0x000C, 0x000C, 0x8003, 0x1101): NewLanelineDataNotify                %u\r\n\
14.(0x000D, 0x000D, 0x8005, 0x1101): NewBroadcastInfoNotify               %u\r\n\
15.(0x000E, 0x000E, 0x8001, 0x1101): PlanningLineInfoNotify               %u\r\n\
16.(0x0007, 0x0007, 0x8001, 0x1101): NavigationStatus_LinkInfoNotify      %u\r\n\
17.(0x0017, 0x0017, 0x8003, 0x1101): NewParkingRealTimeDataNotify         %u\r\n\
18.(0x002B, 0x002B, 0x8001, 0x1101): NavigationHDLink2Info                %u\r\n\
19.(0x8202, 0x8202, 0x8002, 0x1101): sdTraffiIncident                     %u\r\n\
20.(0x000E, 0x000E, 0x8002, 0x1102): newPlanningLineInfo                  %u\r\n\
21.(0x000E, 0x000E, 0x8003, 0x1103): drivingAreaIdentification            %u\r\n\
22.(0x0018, 0x0018, 0x8001, 0x1101): hpaMapDataNotify                     %u\r\n",
g_SendCount, g_Cnt[0], g_Cnt[1], g_Cnt[2], g_Cnt[3], g_Cnt[4], g_Cnt[5],g_Cnt[6], g_Cnt[7], g_Cnt[8], g_Cnt[9], g_Cnt[10], 
g_Cnt[11], g_Cnt[12], g_Cnt[13],g_Cnt[14], g_Cnt[15], g_Cnt[16], g_Cnt[17], g_Cnt[18], g_Cnt[19], g_Cnt[20], g_Cnt[21], g_Cnt[22]);

    // 退出程序
    exit(signal);
}


int main()
{
    // 注册 SIGINT 信号处理函数
    signal(SIGINT, signalHandler);

#if _WIN32
#else
    char path[256] = {0};
    readlink("/proc/self/exe", path, sizeof(path));
    dirname(path);
    gpath = path;
    gpath += "/";
#endif


    uint8_t* pData = nullptr;
    uint32_t len = 0, iCount = 0u;

    SomeipNS::SomeipCom *pClient = new SomeipNS::SomeipCom("");
    pClient->setConfigurePath("./someip_arhud01.json");
    //pClient->setConfigurePath("/etc/bydos2/com/someipC.json");
    (pClient)->init();
    //为通知绑定回调处理函数
    pClient->clientSubscribeCallbackFuncRegist(0x000A, 0x000A, 0x8001, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //0.VehiclePositionInfoNotify
    pClient->clientSubscribeCallbackFuncRegist(0x000B, 0x000B, 0x8001, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //1.RTKInfoNotify
    pClient->clientSubscribeCallbackFuncRegist(0x000B, 0x000B, 0x8002, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //2.IMUInfoNotify
    pClient->clientSubscribeCallbackFuncRegist(0x000C, 0x000C, 0x8001, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //3.ObstacleInfoNotify
    pClient->clientSubscribeCallbackFuncRegist(0x000C, 0x000C, 0x8002, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //4.LaneLineDataNotify
    pClient->clientSubscribeCallbackFuncRegist(0x000D, 0x000D, 0x8001, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //5.ChangeLaneDataNotify
    pClient->clientSubscribeCallbackFuncRegist(0x000D, 0x000D, 0x8002, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //6.PilotStatusNofity
    pClient->clientSubscribeCallbackFuncRegist(0x000D, 0x000D, 0x8003, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //7.PilotAlarmAndNoticeInfoNotify
    pClient->clientSubscribeCallbackFuncRegist(0x000D, 0x000D, 0x8004, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //8.BroadcastInfoNotify
    pClient->clientSubscribeCallbackFuncRegist(0x010A, 0x0001, 0x8001, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //9.HudRoadInfo_EG
    pClient->clientSubscribeCallbackFuncRegist(0x010A, 0x0001, 0x8002, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //10.HudMappathInfo_EG
    pClient->clientSubscribeCallbackFuncRegist(0x010A, 0x0001, 0x8003, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //11.HudNavigationmap
    pClient->clientSubscribeCallbackFuncRegist(0x010A, 0x0001, 0x8004, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //12.overseasHudRoadInfoNotify

    pClient->clientSubscribeCallbackFuncRegist(0x000C, 0x000C, 0x8003, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //13.NewLanelineDataNotify
    pClient->clientSubscribeCallbackFuncRegist(0x000D, 0x000D, 0x8005, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //14.NewBroadcastInfoNotify
    pClient->clientSubscribeCallbackFuncRegist(0x000E, 0x000E, 0x8001, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //15.PlanningLineInfoNotify
    pClient->clientSubscribeCallbackFuncRegist(0x0007, 0x0007, 0x8001, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //16.NavigationStatus_LinkInfoNotify
    pClient->clientSubscribeCallbackFuncRegist(0x0017, 0x0017, 0x8003, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //17.NewParkingRealTimeDataNotify
    pClient->clientSubscribeCallbackFuncRegist(0x002B, 0x002B, 0x8001, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //18.NavigationHDLink2Info
    pClient->clientSubscribeCallbackFuncRegist(0x8202, 0x8202, 0x8002, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //19.sdTraffiIncident
    pClient->clientSubscribeCallbackFuncRegist(0x000E, 0x000E, 0x8002, 0x1102, DefaultClientNotifyRegistCallback, NULL);    //20.newPlanningLineInfo
    pClient->clientSubscribeCallbackFuncRegist(0x000E, 0x000E, 0x8003, 0x1103, DefaultClientNotifyRegistCallback, NULL);    //21.drivingAreaIdentification
    pClient->clientSubscribeCallbackFuncRegist(0x0018, 0x0018, 0x8001, 0x1101, DefaultClientNotifyRegistCallback, NULL);    //22.hpaMapDataNotify
    (pClient)->start();

    while(1)
    {
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    }
    
    if (pClient != nullptr){
        delete pClient;
        pClient = nullptr;
    }

    return 0;
}
