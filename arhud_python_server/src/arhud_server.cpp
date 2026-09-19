/*
 * arhud_server.cpp —— AR-HUD SOME/IP 服务端库（vsomeip 3.4.10，C 接口）
 * 一个 application "arhud01" 提供 11 个服务 / 23 个事件：
 *   - 内置服务注册表（端口/instance/major 与板端客户端一致）
 *   - 自动生成 vsomeip 配置（services 端口 + someip-tp 大消息分片 + SD 224.0.2.4）
 *   - notify 发送 / pcap 回放（TP 重组）/ 订阅回调
 */
#include "arhud_server.h"
#include "arhud_types.h"
#include "arhud_pcap.h"
#include "arhud_services.h"

#include <vsomeip/vsomeip.hpp>
#include <vsomeip/vsomeip_sec.h>
#include <zlib.h>

#ifdef _WIN32
#include <process.h>
#include <windows.h>
#include <cstring>
#define GETPID _getpid
static void cfg_path(char* buf, size_t n, const char* name) {
    DWORD len = GetTempPathA((DWORD)n, buf);
    if (!len || len >= n) { strcpy(buf, ".\\"); }
    strncat(buf, name, n - strlen(buf) - 1);
}
#else
#include <unistd.h>
#define GETPID getpid
static void cfg_path(char* buf, size_t n, const char* name) {
    snprintf(buf, n, "/tmp/%s", name);
}
#endif

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace {

struct EventDef { uint16_t event; uint16_t group; };
/* 服务/事件表来自 arhud_services.h（两代用 ARHUD_SERVICE_PROFILE 选择） */
typedef arhud::EventRow EventDef;
typedef arhud::ServiceRow ServiceDef;

std::string to_hex(uint16_t v) {
    char b[8];
    std::snprintf(b, sizeof(b), "0x%04X", v);
    return b;
}

/* 生成 vsomeip 配置文件（services 端口 + someip-tp + SD） */
std::string gen_config(const std::string& unicast,
                       const std::vector<ServiceDef>& svcs,
                       const std::string& profile) {
    const arhud::ProfileMeta meta = arhud::meta_for(profile);
    std::ostringstream o;
    o << "{\n";
    o << "  \"unicast\": \"" << unicast << "\",\n";
    o << "  \"netmask\": \"255.255.255.0\",\n";
    o << "  \"network\": \"arhud01\",\n";
    o << "  \"logging\": { \"level\": \"info\", \"console\": \"true\", "
         "\"file\": { \"enable\": \"false\", \"path\": \"/tmp/arhud_server.log\" }, \"dlt\": \"false\" },\n";
    o << "  \"applications\": [ { \"name\": \"arhud01\", \"id\": \"" << meta.app_id
      << "\", \"max_dispatchers\": \"" << meta.max_dispatchers
      << "\", \"threads\": \"" << meta.threads << "\" } ],\n";
    o << "  \"services\": [\n";
    for (size_t i = 0; i < svcs.size(); ++i) {
        const ServiceDef& s = svcs[i];
        o << "    { \"service\": \"" << to_hex(s.service)
          << "\", \"instance\": \"" << to_hex(s.instance)
          << "\", \"unreliable\": \"" << s.port
          << "\", \"major\": \"" << s.major << "\", \"minor\": \"" << s.minor << "\"";
        if (!s.tp_events.empty()) {
            o << ", \"someip-tp\": { \"service-to-client\": [";
            std::string tmp = s.tp_events;
            size_t pos = 0;
            bool first = true;
            while (pos < tmp.size()) {
                size_t comma = tmp.find(',', pos);
                std::string tok = tmp.substr(pos, comma == std::string::npos ? tmp.size() - pos : comma - pos);
                if (!first) o << ", ";
                o << "\"" << tok << "\"";
                first = false;
                if (comma == std::string::npos) break;
                pos = comma + 1;
            }
            o << "] }";
        }
        o << " }";
        if (i + 1 < svcs.size()) o << ",";
        o << "\n";
    }
    o << "  ],\n";
    o << "  \"routing\": \"arhud01\",\n";
    o << "  \"service-discovery\": { \"enable\": \"true\", \"multicast\": \"224.0.2.4\", "
         "\"port\": \"30490\", \"protocol\": \"udp\", "
         "\"initial_delay_min\": \"10\", \"initial_delay_max\": \"100\", "
         "\"repetitions_base_delay\": \"200\", \"repetitions_max\": \"3\", "
         "\"ttl\": \"3\", \"cyclic_offer_delay\": \"1000\", \"request_response_delay\": \"0\" }\n";
    o << "}\n";
    return o.str();
}

}  // namespace

struct arhud_server {
    std::shared_ptr<vsomeip::application> app;
    std::string config_path;
    std::string profile;                  // 服务表代（old / bplus）
    std::vector<ServiceDef> services;
    std::map<std::pair<uint16_t, uint16_t>, uint16_t> inst_map;  // (svc,event)->instance
    std::atomic<bool> started{false};
    std::thread io_thread;
    std::atomic<bool> io_running{false};

    std::thread replay_thread;
    std::atomic<bool> replay_running{false};
    std::atomic<uint64_t> replay_sent{0};       // 真正发送成功
    std::atomic<uint64_t> replay_attempted{0};  // 尝试次数（含失败）

    arhud_subscribe_cb sub_cb = nullptr;
    void* sub_ctx = nullptr;
    std::mutex mtx;

    uint16_t instance_of(uint16_t svc, uint16_t event) const {
        auto it = inst_map.find({svc, event});
        return it != inst_map.end() ? it->second : svc;
    }
};

/* ---------------- C 接口实现 ---------------- */

extern "C" {

arhud_server_t* arhud_server_create(const char* unicast, const char* config_path) {
    if (!unicast || !*unicast) return nullptr;
    auto* srv = new arhud_server();
    srv->profile = arhud::profile_from_env();
    srv->services = arhud::services_for(srv->profile);
    for (const auto& s : srv->services)
        for (const auto& e : s.events)
            srv->inst_map[{s.service, e.event}] = s.instance;

    if (config_path && *config_path) {
        srv->config_path = config_path;
    } else {
        char path[256];
        char name[64];
        std::snprintf(name, sizeof(name), "arhud_server_%d.json", (int)GETPID());
        cfg_path(path, sizeof(path), name);
        std::string cfg = gen_config(unicast, srv->services, srv->profile);
        std::ofstream f(path);
        if (!f) { delete srv; return nullptr; }
        f << cfg;
        srv->config_path = path;
    }

    srv->app = vsomeip::runtime::get()->create_application("arhud01", srv->config_path);
    if (!srv->app->init()) { delete srv; return nullptr; }
    return srv;
}

void arhud_server_destroy(arhud_server_t* srv) {
    if (!srv) return;
    arhud_server_stop(srv);
    delete srv;
}

int arhud_server_add_service(arhud_server_t* srv, uint16_t service, uint16_t instance,
                             uint16_t port, uint16_t major, uint16_t minor) {
    if (!srv) return -1;
    std::lock_guard<std::mutex> lk(srv->mtx);
    /* 幂等：同 (service, instance) 已存在时只更新端口/版本，不再追加
     * （否则内置表 + 调用方逐条注册会重复登记，协议栈侧出现重复 offer/回调） */
    for (auto& s : srv->services) {
        if (s.service == service && s.instance == instance) {
            s.port = port; s.major = major; s.minor = minor;
            return 0;
        }
    }
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
            s.events.push_back({event, group});
            srv->inst_map[{service, event}] = instance;
            return 0;
        }
    }
    return -1;
}

int arhud_server_start(arhud_server_t* srv) {
    if (!srv || !srv->app) return -1;
    if (srv->started.load()) return 0;

    // 订阅回调（可选）
    if (srv->sub_cb) {
        for (const auto& s : srv->services) {
            for (const auto& e : s.events) {
                srv->app->register_subscription_handler(
                    s.service, s.instance, e.group,
                    [srv, s, e](vsomeip::client_t /*client*/,
                                const vsomeip_sec_client_t* /*sec*/,
                                const std::string& /*token*/,
                                bool subscribed) -> bool {
                        if (srv->sub_cb)
                            srv->sub_cb(srv->sub_ctx, s.service, s.instance,
                                        e.group, e.event, subscribed ? 1 : 0);
                        return true;
                    });
            }
        }
    }

    // offer 服务（major=1）与事件
    for (const auto& s : srv->services) {
        srv->app->offer_service(s.service, s.instance, s.major, s.minor);
        std::set<vsomeip::eventgroup_t> groups;
        std::set<vsomeip::event_t> evs;
        for (const auto& e : s.events) {
            groups.insert(e.group);
            evs.insert(e.event);
            srv->app->offer_event(s.service, s.instance, e.event, {e.group},
                                  vsomeip::event_type_e::ET_EVENT,
                                  std::chrono::milliseconds::zero(), false, true,
                                  nullptr, vsomeip::reliability_type_e::RT_UNRELIABLE);
        }
    }

    // start() 放后台线程
    srv->io_running = true;
    srv->io_thread = std::thread([srv]() {
        srv->app->start();
        srv->io_running = false;
    });

    srv->started = true;
    return 0;
}

void arhud_server_stop(arhud_server_t* srv) {
    if (!srv) return;
    arhud_server_replay_stop(srv);
    if (srv->started.exchange(false)) {
        srv->app->stop();
        if (srv->io_thread.joinable()) srv->io_thread.join();
    }
}

int arhud_server_notify(arhud_server_t* srv, uint16_t service, uint16_t event,
                        const uint8_t* data, uint32_t len) {
    if (!srv || !srv->app || !srv->started.load() || !data || len == 0) return -1;
    uint16_t inst = srv->instance_of(service, event);
    auto payload = vsomeip::runtime::get()->create_payload();
    payload->set_data(data, len);
    srv->app->notify(service, inst, event, payload, true);
    return 0;
}

int arhud_server_replay_start(arhud_server_t* srv, const char* pcap_path,
                              int loop, uint32_t interval_ms) {
    if (!srv || !pcap_path || !srv->started.load()) return -1;
    if (srv->replay_running.load()) return -1;

    std::vector<arhud::PcapMessage> msgs;
    if (!arhud::parse_pcap(pcap_path, msgs) || msgs.empty()) return -1;

    srv->replay_running = true;
    srv->replay_sent = 0;
    srv->replay_attempted = 0;
    srv->replay_thread = std::thread([srv, msgs = std::move(msgs), loop, interval_ms]() {
        while (srv->replay_running.load()) {
            for (const auto& m : msgs) {
                if (!srv->replay_running.load()) break;
                const int rc = arhud_server_notify(srv, m.service, m.event, m.payload.data(),
                                                  (uint32_t)m.payload.size());
                srv->replay_attempted++;
                if (rc == 0) srv->replay_sent++;   // 未注册事件不计入成功
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

uint64_t arhud_server_replay_attempted(arhud_server_t* srv) {
    return srv ? srv->replay_attempted.load() : 0;
}

const char* arhud_server_profile(arhud_server_t* srv) {
    return srv ? srv->profile.c_str() : "";
}

int arhud_server_service_count(arhud_server_t* srv) {
    return srv ? (int)srv->services.size() : 0;
}

int arhud_server_event_count(arhud_server_t* srv) {
    if (!srv) return 0;
    int n = 0;
    for (const auto& s : srv->services) n += (int)s.events.size();
    return n;
}

void arhud_server_set_subscribe_cb(arhud_server_t* srv, arhud_subscribe_cb cb, void* ctx) {
    if (!srv) return;
    srv->sub_cb = cb;
    srv->sub_ctx = ctx;
}

uint32_t arhud_crc32(const uint8_t* data, uint32_t len) {
    return (uint32_t)crc32(0, data, len);
}

uint32_t arhud_pack_u8(uint8_t* out, uint8_t v) {
    out[0] = v;
    return 1;
}
uint32_t arhud_pack_u16(uint8_t* out, uint16_t v) {
    out[0] = v >> 8; out[1] = v & 0xff;
    return 2;
}
uint32_t arhud_pack_u32(uint8_t* out, uint32_t v) {
    out[0] = v >> 24; out[1] = (v >> 16) & 0xff; out[2] = (v >> 8) & 0xff; out[3] = v & 0xff;
    return 4;
}
uint32_t arhud_pack_u64(uint8_t* out, uint64_t v) {
    for (int i = 7; i >= 0; --i) out[7 - i] = (uint8_t)(v >> (i * 8));
    return 8;
}
uint32_t arhud_pack_f32(uint8_t* out, float v) {
    uint32_t u;
    std::memcpy(&u, &v, 4);
    return arhud_pack_u32(out, u);
}
uint32_t arhud_pack_f64(uint8_t* out, double v) {
    uint64_t u;
    std::memcpy(&u, &v, 8);
    return arhud_pack_u64(out, u);
}

}  // extern "C"
