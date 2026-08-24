/*
 * arhud_server_sp.cpp —— AR-HUD SOME/IP 服务端库（SP 分支协议栈）
 * =========================================================================
 * 与板端示例 C++ 服务端（hud_pcap_huifang_server）使用同一个 SOME/IP 协议栈
 * （SP 分支 libsomeip.so），协议行为与原始部署完全一致：
 *   SPInit(配置) → SPServerNotifyCallbackFuncRegist(23 事件) → SPStart
 *   → SPServerSendNotify(svc, inst, event, data, len) 发送
 * 优势：避免标准 vsomeip 与 SP 分支的兼容性问题；0x000E 组 0 订阅等行为
 * 与原始部署一致（SP 栈对事件组处理更宽松）。
 *
 * C 接口见 arhud_server.h（与标准版一致，Python 封装无需改动）。
 * 编译：make libarhud_server.so（链接 SP 分支库，见 Makefile SP_LIBS）
 */
#include "arhud_server.h"
#include "arhud_types.h"
#include "arhud_pcap.h"
#include "vsomeip/someip_com.h"
#include <zlib.h>

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>
#ifdef _WIN32
#include <process.h>
#define GETPID _getpid
#else
#include <unistd.h>
#define GETPID getpid
#endif

namespace {

struct EventDef { uint16_t event; uint16_t group; const char* name; };
struct ServiceDef {
    uint16_t service, instance, port, major, minor;
    std::vector<EventDef> events;
    std::string tp_events;
};

/* 内置服务注册表（事件名与板端配置一致） */
const std::vector<ServiceDef>& default_services() {
    static const std::vector<ServiceDef> svcs = {
        {0x000A, 0x000A, 51400, 1, 0, {{0x8001, 0x1101, "VehiclePositionInfoNotify"}}, ""},
        {0x000B, 0x000B, 51401, 1, 0, {{0x8001, 0x1101, "RTKInfoNotify"}, {0x8002, 0x1101, "IMUInfoNotify"}}, ""},
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

std::string to_hex(uint16_t v) {
    char b[8];
    std::snprintf(b, sizeof(b), "0x%04X", v);
    return b;
}

/* 生成 SP 分支配置（与板端 someip_arhud01_pcap_server.json 同格式） */
std::string gen_sp_config(const std::string& unicast,
                          const std::vector<ServiceDef>& svcs) {
    std::ostringstream o;
    o << "{\n";
    o << "  \"unicast\": \"" << unicast << "\",\n";
    o << "  \"netmask\": \"255.255.255.0\",\n";
    o << "  \"network\": \"arhud01\",\n";
    o << "  \"logging\": { \"level\": \"info\", \"console\": \"true\", "
         "\"file\": { \"enable\": \"false\", \"path\": \"/tmp/arhud_server_sp.log\" }, \"dlt\": \"false\" },\n";
    o << "  \"applications\": [ { \"name\": \"arhud01\", \"id\": \"0x1443\" } ],\n";
    o << "  \"services\": [\n";
    for (size_t i = 0; i < svcs.size(); ++i) {
        const ServiceDef& s = svcs[i];
        o << "    { \"service\": \"" << to_hex(s.service)
          << "\", \"instance\": \"" << to_hex(s.instance)
          << "\", \"unreliable\": \"" << s.port
          << "\", \"major\": \"" << s.major << "\", \"minor\": \"" << s.minor << "\",\n";
        o << "      \"events\": [\n";
        for (size_t j = 0; j < s.events.size(); ++j) {
            o << "        { \"name\": \"" << s.events[j].name
              << "\", \"event\": \"" << to_hex(s.events[j].event)
              << "\", \"is_field\": \"false\", \"is_reliable\": \"false\", \"notify-period\": \"0xFFFFFFFF\" }";
            if (j + 1 < s.events.size()) o << ",";
            o << "\n";
        }
        o << "      ],\n      \"eventgroups\": [\n";
        /* 按组聚合 */
        {
            std::map<uint16_t, std::vector<uint16_t>> by_group;
            for (const auto& e : s.events) by_group[e.group].push_back(e.event);
            size_t gi = 0;
            for (const auto& kv : by_group) {
                o << "        { \"eventgroup\": \"" << to_hex(kv.first) << "\", \"events\": [";
                for (size_t k = 0; k < kv.second.size(); ++k) {
                    if (k) o << ", ";
                    o << "\"" << to_hex(kv.second[k]) << "\"";
                }
                o << "] }";
                if (++gi < by_group.size()) o << ",";
                o << "\n";
            }
        }
        o << "      ]";
        if (!s.tp_events.empty()) {
            o << ",\n      \"someip-tp\": { \"service-to-client\": [\"";
            std::string tmp = s.tp_events;
            size_t pos = 0;
            while (pos < tmp.size()) {
                size_t comma = tmp.find(',', pos);
                std::string tok = tmp.substr(pos, comma == std::string::npos ? tmp.size() - pos : comma - pos);
                o << tok;
                if (comma != std::string::npos) o << "\", \"";
                if (comma == std::string::npos) break;
                pos = comma + 1;
            }
            o << "\"] }";
        }
        o << " }";
        if (i + 1 < svcs.size()) o << ",";
        o << "\n";
    }
    o << "  ],\n";
    o << "  \"routing\": \"arhud01\",\n";
    o << "  \"service-discovery\": { \"enable\": \"true\", \"multicast\": \"224.0.2.4\", "
         "\"port\": \"30490\", \"protocol\": \"udp\", "
         "\"initial_delay_min\": \"0\", \"initial_delay_max\": \"100\", "
         "\"repetitions_base_delay\": \"100\", \"repetitions_max\": \"3\", "
         "\"ttl\": \"3\", \"cyclic_offer_delay\": \"1000\", \"request_response_delay\": \"0\" }\n";
    o << "}\n";
    return o.str();
}

}  // namespace

struct arhud_server {
    SPInstance spi;
    bool spi_initialized = false;
    std::string config_path;
    std::vector<ServiceDef> services;
    std::map<std::pair<uint16_t, uint16_t>, uint16_t> inst_map;
    std::atomic<bool> started{false};

    std::thread replay_thread;
    std::atomic<bool> replay_running{false};
    std::atomic<uint64_t> replay_sent{0};

    std::mutex mtx;

    uint16_t instance_of(uint16_t svc, uint16_t event) const {
        auto it = inst_map.find({svc, event});
        return it != inst_map.end() ? it->second : svc;
    }
};

/* SP 事件回调（占位：周期性模式由 SPServerSendNotify 主动发送，回调不提供数据） */
static int32_t sp_notify_cb(uint16_t /*svc*/, uint16_t /*inst*/, uint16_t /*method*/,
                            uint8_t** /*data*/, uint32_t* len, void* /*param*/) {
    if (len) *len = 0;  // 不发送
    return 0;
}

extern "C" {

arhud_server_t* arhud_server_create(const char* unicast, const char* config_path) {
    if (!unicast || !*unicast) return nullptr;
    auto* srv = new arhud_server();
    srv->services = default_services();
    for (const auto& s : srv->services)
        for (const auto& e : s.events)
            srv->inst_map[{s.service, e.event}] = s.instance;

    if (config_path && *config_path) {
        srv->config_path = config_path;
    } else {
        char path[256];
        std::snprintf(path, sizeof(path), "/tmp/arhud_server_sp_%d.json", (int)GETPID());
        std::string cfg = gen_sp_config(unicast, srv->services);
        std::ofstream f(path);
        if (!f) { delete srv; return nullptr; }
        f << cfg;
        srv->config_path = path;
    }

    if (SPInit(&srv->spi, (char*)"", (char*)srv->config_path.c_str()) != 0) {
        delete srv;
        return nullptr;
    }
    srv->spi_initialized = true;
    return srv;
}

void arhud_server_destroy(arhud_server_t* srv) {
    if (!srv) return;
    arhud_server_stop(srv);
    if (srv->spi_initialized) SPRelease(&srv->spi);
    delete srv;
}

int arhud_server_add_service(arhud_server_t* srv, uint16_t service, uint16_t instance,
                             uint16_t port, uint16_t major, uint16_t minor) {
    if (!srv) return -1;
    std::lock_guard<std::mutex> lk(srv->mtx);
    ServiceDef d;
    d.service = service; d.instance = instance; d.port = port;
    d.major = major; d.minor = minor;
    srv->services.push_back(d);
    return 0;
}

int arhud_server_add_event(arhud_server_t* srv, uint16_t service, uint16_t instance,
                           uint16_t event, uint16_t group) {
    if (!srv) return -1;
    std::lock_guard<std::mutex> lk(srv->mtx);
    for (auto& s : srv->services) {
        if (s.service == service && s.instance == instance) {
            s.events.push_back({event, group, ""});
            srv->inst_map[{service, event}] = instance;
            return 0;
        }
    }
    return -1;
}

int arhud_server_start(arhud_server_t* srv) {
    if (!srv || !srv->spi_initialized) return -1;
    if (srv->started.load()) return 0;

    // 注册 23 个事件回调（与示例 C++ 服务端一致；数据由 SPServerSendNotify 主动发送）
    for (const auto& s : srv->services) {
        for (const auto& e : s.events) {
            SPServerNotifyCallbackFuncRegist(&srv->spi, s.service, s.instance,
                                             e.event, e.group, sp_notify_cb, nullptr);
        }
    }
    if (SPStart(&srv->spi) != 0) return -1;
    srv->started = true;
    return 0;
}

void arhud_server_stop(arhud_server_t* srv) {
    if (!srv) return;
    arhud_server_replay_stop(srv);
    if (srv->started.exchange(false)) {
        SPStop(&srv->spi);
    }
}

int arhud_server_notify(arhud_server_t* srv, uint16_t service, uint16_t event,
                        const uint8_t* data, uint32_t len) {
    if (!srv || !srv->spi_initialized || !srv->started.load() || !data || len == 0) return -1;
    uint16_t inst = srv->instance_of(service, event);
    return SPServerSendNotify(&srv->spi, service, inst, event,
                              const_cast<uint8_t*>(data), len);
}

int arhud_server_replay_start(arhud_server_t* srv, const char* pcap_path,
                              int loop, uint32_t interval_ms) {
    if (!srv || !pcap_path || !srv->started.load()) return -1;
    if (srv->replay_running.load()) return -1;

    std::vector<arhud::PcapMessage> msgs;
    if (!arhud::parse_pcap(pcap_path, msgs) || msgs.empty()) return -1;

    srv->replay_running = true;
    srv->replay_sent = 0;
    srv->replay_thread = std::thread([srv, msgs = std::move(msgs), loop, interval_ms]() {
        while (srv->replay_running.load()) {
            for (const auto& m : msgs) {
                if (!srv->replay_running.load()) break;
                arhud_server_notify(srv, m.service, m.event, m.payload.data(),
                                    (uint32_t)m.payload.size());
                srv->replay_sent++;
                if (interval_ms)
                    std::this_thread::sleep_for(std::chrono::milliseconds(interval_ms));
            }
            if (!loop) break;
        }
        srv->replay_running = false;
    });
    return 0;
}

void arhud_server_replay_stop(arhud_server_t* srv) {
    if (!srv) return;
    srv->replay_running = false;
    if (srv->replay_thread.joinable()) srv->replay_thread.join();
}

uint64_t arhud_server_replay_sent(arhud_server_t* srv) {
    return srv ? srv->replay_sent.load() : 0;
}

void arhud_server_set_subscribe_cb(arhud_server_t* srv, arhud_subscribe_cb cb, void* ctx) {
    (void)srv; (void)cb; (void)ctx;
    /* SP 分支 C 接口未提供订阅回调，保持占位 */
}

uint32_t arhud_crc32(const uint8_t* data, uint32_t len) {
    return (uint32_t)crc32(0, data, len);
}

uint32_t arhud_pack_u8(uint8_t* out, uint8_t v) { out[0] = v; return 1; }
uint32_t arhud_pack_u16(uint8_t* out, uint16_t v) { out[0] = v >> 8; out[1] = v & 0xff; return 2; }
uint32_t arhud_pack_u32(uint8_t* out, uint32_t v) {
    out[0] = v >> 24; out[1] = (v >> 16) & 0xff; out[2] = (v >> 8) & 0xff; out[3] = v & 0xff;
    return 4;
}
uint32_t arhud_pack_u64(uint8_t* out, uint64_t v) {
    for (int i = 7; i >= 0; --i) out[7 - i] = (uint8_t)(v >> (i * 8));
    return 8;
}
uint32_t arhud_pack_f32(uint8_t* out, float v) { uint32_t u; std::memcpy(&u, &v, 4); return arhud_pack_u32(out, u); }
uint32_t arhud_pack_f64(uint8_t* out, double v) { uint64_t u; std::memcpy(&u, &v, 8); return arhud_pack_u64(out, u); }

}  // extern "C"
