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
#include "arhud_replay.h"
#include "arhud_services.h"
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

namespace {

/* 服务/事件表来自 arhud_services.h（与参考实现逐条对齐，两代用 ARHUD_SERVICE_PROFILE 选择） */
typedef arhud::EventRow EventDef;
typedef arhud::ServiceRow ServiceDef;

std::string to_hex(uint16_t v) {
    char b[8];
    std::snprintf(b, sizeof(b), "0x%04X", v);
    return b;
}

/* 生成 SP 分支配置（与板端 someip_arhud01_pcap_server.json 同格式） */
std::string gen_sp_config(const std::string& unicast,
                          const std::vector<ServiceDef>& svcs,
                          const std::string& profile) {
    const arhud::ProfileMeta meta = arhud::meta_for(profile);
    std::ostringstream o;
    o << "{\n";
    o << "  \"unicast\": \"" << unicast << "\",\n";
    o << "  \"netmask\": \"255.255.255.0\",\n";
    o << "  \"network\": \"arhud01\",\n";
    /* 日志键与参考实现一致（dds/dmesg 开关也要给全，缺键在部分版本会被判为配置错误） */
    o << "  \"logging\": { \"level\": \"info\", \"console\": \"true\", "
         "\"file\": { \"enable\": \"false\", \"path\": \"" << meta.log_path << "\" }, "
         "\"dlt\": \"false\", \"dds_log_enable\": \"false\", \"dmesg_log_enable\": \"false\" },\n";
    o << "  \"applications\": [ { \"name\": \"arhud01\", \"id\": \"" << meta.app_id
      << "\", \"max_dispatchers\": \"" << meta.max_dispatchers
      << "\", \"threads\": \"" << meta.threads << "\" } ],\n";
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
        if (s.tp_events && *s.tp_events) {
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
    /* 参考实现里显式给了最大载荷（车道线等大帧可达 ~51KB，缺省值偏小会导致 TP 失败） */
    o << "  \"max-payload-size-unreliable\": \"3000000\",\n";
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
    std::string profile;                  // 服务表代（old / old-capture / bplus）
    std::vector<ServiceDef> services;
    std::map<std::pair<uint16_t, uint16_t>, uint16_t> inst_map;
    std::atomic<bool> started{false};

    arhud::ReplayEngine replay;           // pcap 回放引擎（流式 + 两种节奏 + 逐事件统计）

    std::mutex mtx;

    uint16_t instance_of(uint16_t svc, uint16_t event) const {
        auto it = inst_map.find({svc, event});
        return it != inst_map.end() ? it->second : svc;
    }

    bool has_event(uint16_t svc, uint16_t event) const {
        return arhud::has_event(services, svc, event);
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
        std::snprintf(name, sizeof(name), "arhud_server_sp_%d.json", (int)GETPID());
        cfg_path(path, sizeof(path), name);
        std::string cfg = gen_sp_config(unicast, srv->services, srv->profile);
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
    d.tp_events = "";             // 必须显式置空：gen_sp_config 会解引用它
    srv->services.push_back(d);
    return 0;
}

int arhud_server_add_event(arhud_server_t* srv, uint16_t service, uint16_t instance,
                           uint16_t event, uint16_t group) {
    if (!srv) return -1;
    std::lock_guard<std::mutex> lk(srv->mtx);
    for (auto& s : srv->services) {
        if (s.service == service && s.instance == instance) {
            for (const auto& e : s.events) {           /* 幂等：已登记的事件不重复追加 */
                if (e.event == event) { srv->inst_map[{service, event}] = instance; return 0; }
            }
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

/* 把 C 选项翻译成引擎选项 */
static arhud::ReplayOptions to_engine_opts(const arhud_replay_opts* o) {
    arhud::ReplayOptions e;
    if (!o) return e;
    e.loop = o->loop != 0;
    e.timing = (o->timing == arhud::kTimingCapture) ? arhud::kTimingCapture : arhud::kTimingInterval;
    e.interval_ms = o->interval_ms;
    e.speed = o->speed;
    e.max_loops = o->max_loops;
    e.start_delay_ms = o->start_delay_ms;
    e.log_every = o->log_every;
    return e;
}

int arhud_server_replay_start_ex(arhud_server_t* srv, const char* const* paths, int n_paths,
                                 const arhud_replay_opts* opts) {
    if (!srv || !paths || n_paths <= 0 || !srv->started.load()) return -1;
    std::vector<std::string> ps;
    for (int i = 0; i < n_paths; ++i)
        if (paths[i] && *paths[i]) ps.push_back(paths[i]);
    if (ps.empty()) return -1;

    arhud::ReplayOptions e = to_engine_opts(opts);
    /* 发送动作：走 notify（内部按服务表映射 instance）；未注册事件也照发（与参考实现一致） */
    arhud::ReplayEngine::Sender sender = [srv](uint16_t svc, uint16_t ev,
                                                const uint8_t* data, uint32_t len) -> int {
        return arhud_server_notify(srv, svc, ev, data, len) == 0 ? arhud::kSendOk : arhud::kSendErr;
    };
    arhud::ReplayEngine::Registered reg = [srv](uint16_t svc, uint16_t ev) {
        return srv->has_event(svc, ev);
    };
    std::string err;
    if (!srv->replay.start(ps, e, sender, reg, &err)) {
        arhud_set_last_error(err.c_str());
        return -1;
    }
    return 0;
}

int arhud_server_replay_start(arhud_server_t* srv, const char* pcap_path,
                              int loop, uint32_t interval_ms) {
    if (!pcap_path) return -1;
    const char* paths[1] = {pcap_path};
    arhud_replay_opts o;
    arhud_replay_opts_default(&o);
    o.loop = loop ? 1 : 0;
    o.timing = arhud::kTimingInterval;
    o.interval_ms = interval_ms;
    return arhud_server_replay_start_ex(srv, paths, 1, &o);
}

void arhud_server_replay_stop(arhud_server_t* srv) {
    if (!srv) return;
    srv->replay.stop();
}

uint64_t arhud_server_replay_sent(arhud_server_t* srv) {
    return srv ? srv->replay.snapshot().sent : 0;
}

uint64_t arhud_server_replay_attempted(arhud_server_t* srv) {
    return srv ? srv->replay.snapshot().parsed : 0;
}

uint64_t arhud_server_replay_parsed(arhud_server_t* srv) {
    return srv ? srv->replay.snapshot().parsed : 0;
}

uint64_t arhud_server_replay_unregistered(arhud_server_t* srv) {
    return srv ? srv->replay.snapshot().unregistered : 0;
}

int arhud_server_replay_running(arhud_server_t* srv) {
    return srv && srv->replay.running() ? 1 : 0;
}

int arhud_server_replay_report(arhud_server_t* srv, char* buf, uint32_t buflen) {
    if (!srv || !buf || buflen == 0) return -1;
    const std::string js = srv->replay.report_json();
    if (js.size() + 1 > buflen) return -1;
    std::memcpy(buf, js.data(), js.size());
    buf[js.size()] = '\0';
    return (int)js.size();
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

/* 注：arhud_replay_opts_default / arhud_pcap_events / arhud_pcap_error /
 * arhud_profile_events / arhud_profile_name 与协议栈无关，定义在 arhud_replay.cpp，
 * SP 版与标准 vsomeip 版共用同一份实现（同一份 arhud_replay.o）。 */

}  // extern "C"
