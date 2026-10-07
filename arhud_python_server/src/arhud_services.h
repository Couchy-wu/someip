/*
 * arhud_services.h —— AR-HUD SOME/IP 服务/事件表（单一来源，供 SP 版与标准版共用）
 * ==============================================================================
 * 两代服务表并存，用环境变量选择（默认 old）：

 *   ARHUD_SERVICE_PROFILE=old     当前 HUD 接口（11 服务 / 23 事件）—— 与参考实现
 *                                 lipeng20260228/old/someip_arhud01_pcap_server.json 一致
 *   ARHUD_SERVICE_PROFILE=bplus   新一代接口（6 服务 / 38 事件）—— 与参考实现
 *                                 lipeng20260228/BPlus/someip_arhud01_pcap_server_B+.json 一致
 *
 * 说明：
 *  · 本文件是**唯一**的服务表定义处，SP 版（arhud_server_sp.cpp）与标准 vsomeip 版
 *    （arhud_server.cpp）都从这里取表，避免两份表各改一半导致行为不一致；
 *  · 事件名、事件组、TP 事件与参考实现逐条对齐（由脚本从参考 json 生成，可追溯）；
 *  · B+ 代在参考实现里标注为"还不能用"（其服务端未调通）；本库按同一张表注册，
 *    是否可用取决于协议栈与对端，故 profile 只是**能力开关**，不代表已联调通过。
 */
#ifndef ARHUD_SERVICES_H
#define ARHUD_SERVICES_H

#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace arhud {

struct EventRow {
    uint16_t event;
    uint16_t group;
    const char* name;
};

struct ServiceRow {
    uint16_t service;
    uint16_t instance;
    uint16_t port;
    uint16_t major;
    uint16_t minor;
    std::vector<EventRow> events;
    const char* tp_events;      // SOME/IP-TP 事件（逗号分隔，空=不需要）
};

/* 每代的应用级参数（生成 vsomeip 配置时用；取自参考实现对应配置） */
struct ProfileMeta {
    const char* name;
    const char* app_id;         // applications[0].id
    int max_dispatchers;
    int threads;
    const char* log_path;
    const char* source;         // 参考实现里的配置文件名（可追溯）
};

/* ---------------- 当前接口（old）：11 服务 / 23 事件 ---------------- */
inline const std::vector<ServiceRow>& services_old() {
    static const std::vector<ServiceRow> svcs = {
        {0x000A, 0x000A, 51400, 1, 0, {{0x8001, 0x1101, "VehiclePositionInfoNotify"}}, ""},
        {0x000B, 0x000B, 51401, 1, 0, {{0x8001, 0x1101, "RTKInfoNotify"},
                                       {0x8002, 0x1101, "IMUInfoNotify"}}, ""},
        {0x000C, 0x000C, 51402, 1, 0, {{0x8001, 0x1101, "ObstacleInfoNotify"},
                                       {0x8002, 0x1101, "LaneLineDataNotify"},
                                       {0x8003, 0x1101, "NewLaneLineDataNotify"}}, "0x8002,0x8003"},
        {0x000D, 0x000D, 51403, 1, 0, {{0x8001, 0x1101, "ChangeLaneDataNotify"},
                                       {0x8002, 0x1101, "PilotStatusNofity"},
                                       {0x8003, 0x1101, "PilotAlarmAndNoticeInfoNotify"},
                                       {0x8004, 0x1101, "BroadcastInfoNotify"},
                                       {0x8005, 0x1101, "NewBroadcastInfoNotify"}}, ""},
        {0x000E, 0x000E, 51404, 1, 0, {{0x8001, 0x1101, "PlanningLineInfoNotify"},
                                       {0x8002, 0x1102, "newPlanningLineInfo"},
                                       {0x8003, 0x1103, "drivingAreaIdentification"}}, ""},
        {0x010A, 0x0001, 52001, 1, 0, {{0x8001, 0x1101, "HudRoadInfo_EG"},
                                       {0x8002, 0x1101, "HudMappathInfo_EG"},
                                       {0x8003, 0x1101, "HudNavigationmap"},
                                       {0x8004, 0x1101, "OverseasHudRoadInfoNotify"}}, "0x8001,0x8003"},
        {0x0007, 0x0007, 51405, 1, 0, {{0x8001, 0x1101, "NavigationStatus_LinkInfoNotify"}}, ""},
        {0x0017, 0x0017, 51406, 1, 0, {{0x8003, 0x1101, "NewParkingRealTimeDataNotify"}}, ""},
        {0x002B, 0x002B, 51407, 1, 0, {{0x8001, 0x1101, "NavigationHDLink2Info"}}, ""},
        {0x8202, 0x8202, 51408, 1, 0, {{0x8002, 0x1101, "sdTraffiIncident"}}, ""},
        {0x0018, 0x0018, 51409, 1, 0, {{0x8001, 0x1101, "hpaMapDataNotify"}}, ""},
    };
    return svcs;
}

/* ---------------- old + 抓包实测事件（11 服务 / 33 事件）----------------
 * 背景：参考配置 old/someip_arhud01_pcap_server.json 只声明了 23 个事件，
 * 但该目录里的真实抓包（out.pcap / output3.pcap / outputblanket.pcap）里还出现
 * 另外 10 个**已 offer 服务上**的事件（服务都在表里，只是事件没登记）：
 *     0x0007:8003/8004   0x0017:8002   0x8202:8001/8006/8007/8008/8009/800A/800B
 * 不登记它们，回放时这些数据就"发不出去"（协议栈侧没有对应事件，拿不到订阅者）。
 *
 * 这是**可选扩展**，默认不开（`ARHUD_SERVICE_PROFILE` 不设或 =old 时与参考配置逐条一致），
 * 需要完整回放抓包时设 `ARHUD_SERVICE_PROFILE=old-capture`（别名 old+pcap / capture）。
 * 事件名参考配置里没有，故用 ext_<service>_<event> 记号；事件组按同服务既有事件取 0x1101。
 * 详见 PCAP_REPLAY.md。 */
inline const std::vector<ServiceRow>& services_old_capture() {
    static const std::vector<ServiceRow> svcs = [] {
        std::vector<ServiceRow> v = services_old();
        struct Extra { uint16_t service; uint16_t event; const char* name; };
        static const Extra extra[] = {
            {0x0007, 0x8003, "ext_0007_8003"},
            {0x0007, 0x8004, "ext_0007_8004"},
            {0x0017, 0x8002, "ext_0017_8002"},
            {0x8202, 0x8001, "ext_8202_8001"},
            {0x8202, 0x8006, "ext_8202_8006"},
            {0x8202, 0x8007, "ext_8202_8007"},
            {0x8202, 0x8008, "ext_8202_8008"},
            {0x8202, 0x8009, "ext_8202_8009"},
            {0x8202, 0x800A, "ext_8202_800A"},
            {0x8202, 0x800B, "ext_8202_800B"},
        };
        for (const Extra& e : extra) {
            for (auto& s : v) {
                if (s.service != e.service) continue;
                bool exists = false;
                for (const auto& row : s.events)
                    if (row.event == e.event) exists = true;
                if (!exists) s.events.push_back({e.event, 0x1101, e.name});
                break;
            }
        }
        return v;
    }();
    return svcs;
}

/* ---------------- 新一代接口（bplus）：6 服务 / 38 事件 ---------------- */inline const std::vector<ServiceRow>& services_bplus() {
    static const std::vector<ServiceRow> svcs = {
        {0x001A, 0x001A, 51211, 1, 0, {{0x8001, 0x1101, "vehiclePositionInfoNotify"},
                                       {0x8002, 0x1102, "rtkNotify"},
                                       {0x8003, 0x1103, "imuNotify"}}, ""},
        {0x001B, 0x001B, 51240, 1, 0, {{0x8001, 0x1101, "obstacleNotify"},
                                       {0x8002, 0x1101, "laneLineDataNotify"},
                                       {0x8003, 0x1101, "changeLaneDataNotify"},
                                       {0x8004, 0x1102, "pilotStatusNotify"},
                                       {0x8005, 0x1102, "pilotAlarmAndNoticeNotify"},
                                       {0x8006, 0x1102, "broadcastNotify"},
                                       {0x8007, 0x1101, "planningLineNotify"},
                                       {0x8008, 0x1101, "drivingAreaIdentification_notify"},
                                       {0x8009, 0x1103, "parkingDataNotify"},
                                       {0x800A, 0x1103, "hpaMapDataNotify"},
                                       {0x800B, 0x1103, "commonObstaclesInMapDataNotify"},
                                       {0x800C, 0x1104, "notifyMediaHPAPath"},
                                       {0x800D, 0x1105, "drivingJourneyDataNotify"}}, ""},
        {0x001C, 0x001C, 51237, 1, 0, {{0x8001, 0x1101, "navigationPathMatchStatusNotify"},
                                       {0x8002, 0x1102, "naviPathUserSelectStsConfirmNotify"},
                                       {0x8003, 0x1104, "navigationPathMatchP2PStatusNotify"}}, ""},
        {0x001D, 0x001D, 51246, 1, 0, {{0x8001, 0x1101, "sWSaleablecheckStatusNotify"}}, ""},
        {0x8000, 0x8000, 51534, 1, 0, {{0x8001, 0x1101, "naviGlobalInfoNotify"},
                                       {0x8002, 0x1102, "naviPositionInfoNotify"},
                                       {0x8003, 0x1103, "naviRouteInfoNotify"},
                                       {0x8004, 0x1103, "naviPathInfoNotify"},
                                       {0x8005, 0x1104, "aheadIntersectionsLanesInfoNotify"},
                                       {0x8006, 0x1104, "mixForkInfolistNotify"},
                                       {0x8007, 0x1105, "naviGuideInfoNotify"},
                                       {0x8008, 0x1105, "nextCrossLaneInfoNotify"},
                                       {0x8009, 0x1105, "facilityInfoNotify"},
                                       {0x800A, 0x1105, "cameraInMapInfoNotify"},
                                       {0x800B, 0x1105, "naviHighwayGuideInfoNotify"},
                                       {0x800C, 0x1106, "naviTrafficLightNotify"},
                                       {0x800D, 0x1106, "trafficJamNotify"},
                                       {0x800E, 0x1106, "trafficEventInfoNotify"}}, ""},
        {0x010A, 0x0001, 52001, 1, 0, {{0x8001, 0x1101, "HudRoadInfoNotify"},
                                       {0x8002, 0x1101, "HudMappathInfoNotify"},
                                       {0x8003, 0x1101, "HudNavigationmap"},
                                       {0x8004, 0x1101, "OverseasHudRoadInfoNotify"}}, "0x8001,0x8003"},
    };
    return svcs;
}

inline const std::vector<ServiceRow>& services_by_name(const std::string& name) {
    if (name == "bplus") return services_bplus();
    if (name == "old-capture") return services_old_capture();
    return services_old();
}

/* 环境变量选择 profile（默认 old）；非法值回退 old。
 * 取值：old / bplus / old-capture（别名 old+pcap、old+pcap-capture、capture、old-ext） */
inline std::string profile_from_env() {
    const char* env = std::getenv("ARHUD_SERVICE_PROFILE");
    std::string name = (env && *env) ? env : "old";
    for (auto& c : name) c = (char)std::tolower((unsigned char)c);
    if (name == "bplus" || name == "b+" || name == "new") return "bplus";
    if (name == "old-capture" || name == "old+capture" || name == "old+pcap" ||
        name == "capture" || name == "old-ext" || name == "old_full" || name == "full")
        return "old-capture";
    return "old";
}

inline const std::vector<ServiceRow>& services_for(const std::string& profile) {
    return services_by_name(profile);
}

inline ProfileMeta meta_for(const std::string& profile) {
    if (profile == "bplus")
        return {"bplus", "0x1443", 25, 13, "/tmp/someip_arhud01_bplus.log",
                "BPlus/someip_arhud01_pcap_server_B+.json"};
    if (profile == "old-capture")
        return {"old-capture", "0x1001", 25, 13, "/tmp/someip_arhud01_capture.log",
                "old/someip_arhud01_pcap_server.json + 抓包实测事件（PCAP_REPLAY.md）"};
    return {"old", "0x1001", 25, 13, "/tmp/someip_arhud01.log",
            "old/someip_arhud01_pcap_server.json"};
}

inline size_t event_count(const std::vector<ServiceRow>& svcs) {
    size_t n = 0;
    for (const auto& s : svcs) n += s.events.size();
    return n;
}

/* 表里是否有该事件（回放前可用来判断"这条数据发得出去吗"） */
inline bool has_event(const std::vector<ServiceRow>& svcs, uint16_t service, uint16_t event) {
    for (const auto& s : svcs) {
        if (s.service != service) continue;
        for (const auto& e : s.events)
            if (e.event == event) return true;
    }
    return false;
}

/* 把服务表导出成 JSON（Python 侧做覆盖率核对用） */
inline std::string services_json(const std::vector<ServiceRow>& svcs) {
    std::string out = "{\"services\":[";
    for (size_t i = 0; i < svcs.size(); ++i) {
        const ServiceRow& s = svcs[i];
        char b[256];
        if (i) out += ",";
        std::snprintf(b, sizeof(b), "{\"service\":%u,\"instance\":%u,\"port\":%u,\"major\":%u,\"events\":[",
                      s.service, s.instance, s.port, s.major);
        out += b;
        for (size_t j = 0; j < s.events.size(); ++j) {
            if (j) out += ",";
            std::snprintf(b, sizeof(b), "{\"event\":%u,\"group\":%u,\"name\":\"%s\"}",
                          s.events[j].event, s.events[j].group, s.events[j].name);
            out += b;
        }
        out += "]}";
    }
    out += "]}";
    return out;
}

}  // namespace arhud

#endif  // ARHUD_SERVICES_H
