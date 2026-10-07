/*
 * dryrun_server.cpp —— "演练版" libarhud_server（不联网，纯本地验证用）
 * ==============================================================================
 * 目的：在没有 SOME/IP 协议栈的机器上（macOS/Windows/未部署的 Linux），
 *       也能完整跑通 **Python 层 + pcap 解析 + TP 重组 + 回放引擎 + 统计报告**，
 *       用来做"回放前演练"和回归自测：
 *         · 解析/重组/pacing/计数/报告 全部走真实代码路径（arhud_pcap + arhud_replay）；
 *         · SPServerSendNotify 换成"本地计数 + 可选打印"，不发一个字节到网络。
 *
 * 用法：
 *   # macOS
 *   g++ -std=c++14 -O2 -shared -fPIC -I src src/arhud_pcap.cpp src/arhud_replay.cpp \
 *       src/arhud_types.cpp tools/dryrun_server.cpp -o python/libarhud_server.so -lz
 *   ARHUD_DRYRUN_VERBOSE=1 python3 python/demo_replay.py <pcap或目录>
 *
 * 注意：这不是部署用的库；真机发布数据请编译 src/arhud_server_sp.cpp（见 Makefile）。
 */
#include "arhud_server.h"
#include "arhud_pcap.h"
#include "arhud_replay.h"
#include "arhud_services.h"
#include "arhud_types.h"

#include <zlib.h>

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <mutex>
#include <string>
#include <vector>

namespace {

bool verbose() {
    const char* v = std::getenv("ARHUD_DRYRUN_VERBOSE");
    return v && *v && *v != '0';
}

}  // namespace

struct arhud_server {
    std::string unicast;
    std::string profile;
    std::vector<arhud::ServiceRow> services;
    bool started = false;
    arhud::ReplayEngine replay;
    std::atomic<uint64_t> notify_ok{0};
    std::atomic<uint64_t> notify_fail{0};
    std::map<std::pair<uint16_t, uint16_t>, uint16_t> inst_map;
    std::mutex mtx;

    bool has_event(uint16_t svc, uint16_t ev) const { return arhud::has_event(services, svc, ev); }
    uint16_t instance_of(uint16_t svc, uint16_t ev) const {
        auto it = inst_map.find({svc, ev});
        return it != inst_map.end() ? it->second : svc;
    }
};

extern "C" {

arhud_server_t* arhud_server_create(const char* unicast, const char* config_path) {
    (void)config_path;
    if (!unicast || !*unicast) return nullptr;
    arhud_server* s = new arhud_server();
    s->unicast = unicast;
    s->profile = arhud::profile_from_env();
    s->services = arhud::services_for(s->profile);
    for (const auto& sv : s->services)
        for (const auto& e : sv.events) s->inst_map[{sv.service, e.event}] = sv.instance;
    if (verbose())
        std::printf("[dryrun] create unicast=%s profile=%s services=%zu events=%zu\n",
                    unicast, s->profile.c_str(), s->services.size(),
                    arhud::event_count(s->services));
    return s;
}

void arhud_server_destroy(arhud_server_t* s) {
    if (!s) return;
    arhud_server_stop(s);
    delete s;
}

int arhud_server_add_service(arhud_server_t* s, uint16_t service, uint16_t instance,
                             uint16_t port, uint16_t major, uint16_t minor) {
    if (!s) return -1;
    for (auto& sv : s->services) {
        if (sv.service == service && sv.instance == instance) {
            sv.port = port; sv.major = major; sv.minor = minor;
            return 0;
        }
    }
    arhud::ServiceRow r;
    r.service = service; r.instance = instance; r.port = port;
    r.major = major; r.minor = minor; r.tp_events = "";
    s->services.push_back(r);
    return 0;
}

int arhud_server_add_event(arhud_server_t* s, uint16_t service, uint16_t instance,
                           uint16_t event, uint16_t group) {
    if (!s) return -1;
    for (auto& sv : s->services) {
        if (sv.service == service && sv.instance == instance) {
            for (const auto& e : sv.events)
                if (e.event == event) { s->inst_map[{service, event}] = instance; return 0; }
            sv.events.push_back({event, group, ""});
            s->inst_map[{service, event}] = instance;
            return 0;
        }
    }
    return -1;
}

int arhud_server_start(arhud_server_t* s) {
    if (!s) return -1;
    s->started = true;
    return 0;
}

void arhud_server_stop(arhud_server_t* s) {
    if (!s) return;
    s->replay.stop();
    s->started = false;
}

int arhud_server_notify(arhud_server_t* s, uint16_t service, uint16_t event,
                        const uint8_t* data, uint32_t len) {
    if (!s || !s->started || !data || len == 0) return -1;
    const bool reg = s->has_event(service, event);
    if (verbose())
        std::printf("[dryrun] notify %04X:%04X inst=%04X len=%u %s\n", service, event,
                    s->instance_of(service, event), len, reg ? "" : "(不在服务表)");
    if (reg) s->notify_ok++;
    else s->notify_fail++;
    return reg ? 0 : -1;   // 演练：表里没有就算发不出去（与协议栈侧行为一致）
}

int arhud_server_replay_start(arhud_server_t* s, const char* path, int loop, uint32_t interval_ms) {
    if (!path) return -1;
    const char* paths[1] = {path};
    arhud_replay_opts o;
    arhud_replay_opts_default(&o);
    o.loop = loop ? 1 : 0;
    o.interval_ms = interval_ms;
    return arhud_server_replay_start_ex(s, paths, 1, &o);
}

int arhud_server_replay_start_ex(arhud_server_t* s, const char* const* paths, int n_paths,
                                 const arhud_replay_opts* opts) {
    if (!s || !paths || n_paths <= 0 || !s->started) return -1;
    std::vector<std::string> ps;
    for (int i = 0; i < n_paths; ++i)
        if (paths[i] && *paths[i]) ps.push_back(paths[i]);
    if (ps.empty()) return -1;
    arhud::ReplayOptions e;
    if (opts) {
        e.loop = opts->loop != 0;
        e.timing = (opts->timing == arhud::kTimingCapture) ? arhud::kTimingCapture
                                                           : arhud::kTimingInterval;
        e.interval_ms = opts->interval_ms;
        e.speed = opts->speed;
        e.max_loops = opts->max_loops;
        e.start_delay_ms = opts->start_delay_ms;
        e.log_every = opts->log_every;
    }
    arhud::ReplayEngine::Sender sender = [s](uint16_t svc, uint16_t ev,
                                             const uint8_t* d, uint32_t n) -> int {
        return arhud_server_notify(s, svc, ev, d, n) == 0 ? arhud::kSendOk : arhud::kSendErr;
    };
    arhud::ReplayEngine::Registered reg = [s](uint16_t svc, uint16_t ev) {
        return s->has_event(svc, ev);
    };
    std::string err;
    if (!s->replay.start(ps, e, sender, reg, &err)) {
        arhud_set_last_error(err.c_str());
        return -1;
    }
    return 0;
}

void arhud_server_replay_stop(arhud_server_t* s) { if (s) s->replay.stop(); }
uint64_t arhud_server_replay_sent(arhud_server_t* s) { return s ? s->replay.snapshot().sent : 0; }
uint64_t arhud_server_replay_attempted(arhud_server_t* s) { return s ? s->replay.snapshot().parsed : 0; }
uint64_t arhud_server_replay_parsed(arhud_server_t* s) { return s ? s->replay.snapshot().parsed : 0; }
uint64_t arhud_server_replay_unregistered(arhud_server_t* s) { return s ? s->replay.snapshot().unregistered : 0; }
int arhud_server_replay_running(arhud_server_t* s) { return s && s->replay.running() ? 1 : 0; }

int arhud_server_replay_report(arhud_server_t* s, char* buf, uint32_t buflen) {
    if (!s || !buf || !buflen) return -1;
    const std::string js = s->replay.report_json();
    if (js.size() + 1 > buflen) return -1;
    std::memcpy(buf, js.data(), js.size());
    buf[js.size()] = '\0';
    return (int)js.size();
}

const char* arhud_server_profile(arhud_server_t* s) { return s ? s->profile.c_str() : ""; }
int arhud_server_service_count(arhud_server_t* s) { return s ? (int)s->services.size() : 0; }
int arhud_server_event_count(arhud_server_t* s) {
    return s ? (int)arhud::event_count(s->services) : 0;
}
void arhud_server_set_subscribe_cb(arhud_server_t* s, arhud_subscribe_cb cb, void* ctx) {
    (void)s; (void)cb; (void)ctx;
}

uint32_t arhud_crc32(const uint8_t* d, uint32_t n) { return (uint32_t)crc32(0, d, n); }
uint32_t arhud_pack_u8(uint8_t* o, uint8_t v) { o[0] = v; return 1; }
uint32_t arhud_pack_u16(uint8_t* o, uint16_t v) { o[0] = (uint8_t)(v >> 8); o[1] = (uint8_t)v; return 2; }
uint32_t arhud_pack_u32(uint8_t* o, uint32_t v) {
    o[0] = (uint8_t)(v >> 24); o[1] = (uint8_t)(v >> 16); o[2] = (uint8_t)(v >> 8); o[3] = (uint8_t)v;
    return 4;
}
uint32_t arhud_pack_u64(uint8_t* o, uint64_t v) {
    for (int i = 7; i >= 0; --i) o[7 - i] = (uint8_t)(v >> (i * 8));
    return 8;
}
uint32_t arhud_pack_f32(uint8_t* o, float v) { uint32_t u; std::memcpy(&u, &v, 4); return arhud_pack_u32(o, u); }
uint32_t arhud_pack_f64(uint8_t* o, double v) { uint64_t u; std::memcpy(&u, &v, 8); return arhud_pack_u64(o, u); }

}  // extern "C"
