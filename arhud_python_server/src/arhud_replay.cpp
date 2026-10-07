/*
 * arhud_replay.cpp —— pcap 回放引擎实现（见 arhud_replay.h）
 */
#include "arhud_replay.h"
#include "arhud_server.h"   /* arhud_replay_opts 等 C 接口类型 */
#include "arhud_pcap.h"
#include "arhud_services.h"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <set>

namespace arhud {

namespace {

/* 最近一次 pcap 相关调用的错误信息（arhud_pcap_error() 返回给调用方） */
std::string& last_error() {
    static std::string e;
    return e;
}

}  // namespace

}  // namespace arhud

/* 这些 C 接口与具体协议栈无关（SP 版/标准版共用 arhud_replay.o），故放在这里只定义一次 */
extern "C" {

void arhud_replay_opts_default(arhud_replay_opts* o) {
    if (!o) return;
    o->loop = 1;
    o->timing = 0;
    o->interval_ms = 10;
    o->speed = 1.0;
    o->max_loops = 0;
    o->start_delay_ms = 0;
    o->log_every = 0;
}

void arhud_set_last_error(const char* msg) { arhud::last_error() = msg ? msg : ""; }
const char* arhud_pcap_error(void) { return arhud::last_error().c_str(); }

/* 回放前体检：扫一组 pcap，返回出现过的 (service,event)（JSON） */
int arhud_pcap_events(const char* const* paths, int n_paths, char* buf, uint32_t buflen) {
    if (!paths || n_paths <= 0 || !buf || buflen == 0) return -1;
    arhud::last_error().clear();
    std::vector<std::pair<uint16_t, uint16_t> > events;
    std::vector<std::string> ps;
    for (int i = 0; i < n_paths; ++i)
        if (paths[i] && *paths[i]) ps.push_back(paths[i]);
    if (!arhud::ReplayEngine::scan_events(ps, events, &arhud::last_error())) return -1;

    std::string js = "{\"events\":[";
    char b[128];
    for (size_t i = 0; i < events.size(); ++i) {
        std::snprintf(b, sizeof(b), "%s{\"service\":%u,\"event\":%u}",
                      i ? "," : "", events[i].first, events[i].second);
        js += b;
    }
    std::snprintf(b, sizeof(b), "],\"count\":%u}", (unsigned)events.size());
    js += b;
    if (js.size() + 1 > buflen) return -1;
    std::memcpy(buf, js.data(), js.size());
    buf[js.size()] = '\0';
    return (int)js.size();
}

/* 服务表导出（Python 侧核对"pcap 里的事件表里有没有"） */
int arhud_profile_events(const char* profile, char* buf, uint32_t buflen) {
    if (!buf || buflen == 0) return -1;
    const std::string name = (profile && *profile) ? std::string(profile) : arhud::profile_from_env();
    const std::string js = arhud::services_json(arhud::services_for(name));
    if (js.size() + 1 > buflen) return -1;
    std::memcpy(buf, js.data(), js.size());
    buf[js.size()] = '\0';
    return (int)js.size();
}

const char* arhud_profile_name(void) {
    static std::string name = arhud::profile_from_env();
    return name.c_str();
}

}  // extern "C"

namespace arhud {

namespace {

using Clock = std::chrono::steady_clock;

/* 可被打断的休眠：分片睡，停止时最多等 slice 毫秒 */
void sleep_interruptible(Clock::time_point until, const std::atomic<bool>& running,
                         uint32_t slice_ms = 20) {
    while (running.load()) {
        const auto now = Clock::now();
        if (now >= until) return;
        auto left = std::chrono::duration_cast<std::chrono::milliseconds>(until - now).count();
        if (left <= 0) return;
        if (left > (long long)slice_ms) left = slice_ms;
        std::this_thread::sleep_for(std::chrono::milliseconds(left));
    }
}

}  // namespace

ReplayEngine::~ReplayEngine() { stop(); }

bool ReplayEngine::start(const std::vector<std::string>& paths, const ReplayOptions& opts,
                         Sender sender, Registered registered, std::string* err) {
    if (running_.load()) {
        if (err) *err = "回放已在运行";
        return false;
    }
    if (paths.empty()) {
        if (err) *err = "没有指定 pcap 文件";
        return false;
    }
    /* 先试打开每个文件：早失败、错误信息清楚（而不是在后台线程里悄悄失败） */
    for (const std::string& p : paths) {
        PcapStream s;
        std::string e;
        if (!s.open(p, &e)) {
            if (err) *err = e;
            return false;
        }
    }
    {
        std::lock_guard<std::mutex> lk(mtx_);
        snap_ = ReplaySnapshot();
        snap_.files = paths.size();
        elapsed_s_ = 0.0;
    }
    running_ = true;
    th_ = std::thread(&ReplayEngine::thread_main, this, paths, opts, sender, registered);
    return true;
}

void ReplayEngine::stop() {
    running_ = false;
    if (th_.joinable()) th_.join();
}

void ReplayEngine::thread_main(std::vector<std::string> paths, ReplayOptions opts,
                               Sender sender, Registered registered) {
    const auto t_start = Clock::now();
    if (opts.start_delay_ms && running_.load())
        sleep_interruptible(t_start + std::chrono::milliseconds(opts.start_delay_ms), running_);
    const double speed = opts.speed > 0.0 ? opts.speed : 1.0;

    uint32_t loop_no = 0;
    while (running_.load()) {
        for (size_t fi = 0; fi < paths.size() && running_.load(); ++fi) {
            PcapStream s;
            std::string err;
            if (!s.open(paths[fi], &err)) continue;   // start() 已校验过，这里只是保险
            PcapMessage m;
            bool first = true;
            uint64_t base_ts = 0;
            const auto file_start = Clock::now();
            int rc;
            while (running_.load() && (rc = s.next(m)) == 1) {
                if (opts.timing == kTimingCapture) {
                    if (first) { base_ts = m.ts_us; }
                    const double target_s = (double)(m.ts_us > base_ts ? m.ts_us - base_ts : 0) / (1e6 * speed);
                    sleep_interruptible(file_start + std::chrono::microseconds((long long)(target_s * 1e6)),
                                        running_);
                    if (!running_.load()) break;
                }
                first = false;
                const int send_rc = sender ? sender(m.service, m.event, m.payload.data(),
                                                    (uint32_t)m.payload.size())
                                           : kSendErr;
                const bool reg = registered ? registered(m.service, m.event) : true;
                {
                    std::lock_guard<std::mutex> lk(mtx_);
                    snap_.parsed++;
                    ReplayEventStat& st = snap_.per_event[{m.service, m.event}];
                    st.attempted++;
                    if (send_rc == kSendOk) { snap_.sent++; st.sent++; }
                    else snap_.failed++;
                    if (!reg) { snap_.unregistered++; st.unregistered++; }
                }
                if (opts.log_every > 0) {
                    uint64_t n;
                    { std::lock_guard<std::mutex> lk(mtx_); n = snap_.parsed; }
                    if (n % (uint64_t)opts.log_every == 0)
                        std::printf("[replay] #%llu %04X:%04X len=%zu\n",
                                    (unsigned long long)n, m.service, m.event, m.payload.size());
                }
                if (opts.timing == kTimingInterval && opts.interval_ms && running_.load())
                    sleep_interruptible(Clock::now() + std::chrono::milliseconds(opts.interval_ms),
                                        running_);
            }
            /* 汇总本文件的解析丢包统计 */
            {
                const PcapStats& st = s.stats();
                std::lock_guard<std::mutex> lk(mtx_);
                snap_.tp_dropped += st.tp_dropped;
                snap_.tp_duplicates += st.tp_duplicates;
                snap_.packets += st.packets;
            }
            if (!running_.load()) break;
        }
        loop_no++;
        {
            std::lock_guard<std::mutex> lk(mtx_);
            snap_.loops = loop_no;
        }
        if (!opts.loop) break;
        if (opts.max_loops && loop_no >= opts.max_loops) break;
    }

    {
        std::lock_guard<std::mutex> lk(mtx_);
        elapsed_s_ = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - t_start).count() / 1000.0;
        snap_.elapsed_s = elapsed_s_;
    }
    running_ = false;
}

ReplaySnapshot ReplayEngine::snapshot() const {
    std::lock_guard<std::mutex> lk(mtx_);
    ReplaySnapshot s = snap_;
    s.running = running_.load();
    return s;
}

std::string ReplayEngine::report_json() const {
    ReplaySnapshot s = snapshot();
    char b[512];
    std::string o;
    std::snprintf(b, sizeof(b),
                  "{\"files\":%llu,\"loops\":%llu,\"parsed\":%llu,\"sent\":%llu,\"failed\":%llu,"
                  "\"unregistered\":%llu,\"tp_dropped\":%llu,\"tp_duplicates\":%llu,"
                  "\"packets\":%llu,\"elapsed_s\":%.3f,\"running\":%s,\"events\":[",
                  (unsigned long long)s.files, (unsigned long long)s.loops,
                  (unsigned long long)s.parsed, (unsigned long long)s.sent,
                  (unsigned long long)s.failed, (unsigned long long)s.unregistered,
                  (unsigned long long)s.tp_dropped, (unsigned long long)s.tp_duplicates,
                  (unsigned long long)s.packets, s.elapsed_s, s.running ? "true" : "false");
    o += b;
    bool first = true;
    for (const auto& kv : s.per_event) {
        std::snprintf(b, sizeof(b),
                      "%s{\"service\":%u,\"event\":%u,\"attempted\":%llu,\"sent\":%llu,\"unregistered\":%llu}",
                      first ? "" : ",", kv.first.first, kv.first.second,
                      (unsigned long long)kv.second.attempted, (unsigned long long)kv.second.sent,
                      (unsigned long long)kv.second.unregistered);
        first = false;
        o += b;
    }
    o += "]}";
    return o;
}

bool ReplayEngine::scan_events(const std::vector<std::string>& paths,
                               std::vector<std::pair<uint16_t, uint16_t> >& events,
                               std::string* err) {
    std::set<std::pair<uint16_t, uint16_t> > seen;
    for (const std::string& p : paths) {
        PcapStream s;
        std::string e;
        if (!s.open(p, &e)) {
            if (err) *err = e;
            return false;
        }
        PcapMessage m;
        int rc;
        while ((rc = s.next(m)) == 1) seen.insert(std::make_pair(m.service, m.event));
        if (rc != 0) {
            if (err) *err = "读取 pcap 出错: " + p;
            return false;
        }
    }
    events.assign(seen.begin(), seen.end());
    return true;
}

}  // namespace arhud
