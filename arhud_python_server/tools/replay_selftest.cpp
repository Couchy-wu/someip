/*
 * replay_selftest.cpp —— 回放引擎自测（不链接 SOME/IP 协议栈，macOS/Linux 均可跑）
 * ---------------------------------------------------------------------------
 * 用"假发送器"跑一遍真实 pcap，验证：
 *   · 流式解析 + TP 重组条数（与 pcap_selftest / analyze_pcap.py 对齐）
 *   · 两种节奏（按抓包时间戳 / 固定间隔）
 *   · 循环轮数、限速倍速、停止响应
 *   · 逐事件统计与 report_json 输出
 *   · C 接口 arhud_pcap_events / arhud_profile_events 是否可用
 *
 * 编译：
 *   g++ -std=c++14 -O2 -I src src/arhud_pcap.cpp src/arhud_replay.cpp \
 *       tools/replay_selftest.cpp -o /tmp/replay_selftest
 * 用法：
 *   /tmp/replay_selftest <pcap...> [--timing capture|interval] [--speed 20] \
 *                        [--interval-ms 0] [--loops 1] [--profile old|old-capture]
 */
#include "arhud_pcap.h"
#include "arhud_replay.h"
#include "arhud_services.h"
#include "arhud_server.h"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <set>
#include <string>
#include <thread>
#include <vector>

int main(int argc, char** argv) {
    std::vector<std::string> paths;
    std::string timing = "capture";
    double speed = 20.0;
    uint32_t interval_ms = 0;
    uint32_t loops = 1;
    std::string profile = "old-capture";
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--timing" && i + 1 < argc) timing = argv[++i];
        else if (a == "--speed" && i + 1 < argc) speed = std::atof(argv[++i]);
        else if (a == "--interval-ms" && i + 1 < argc) interval_ms = (uint32_t)std::atoi(argv[++i]);
        else if (a == "--loops" && i + 1 < argc) loops = (uint32_t)std::atoi(argv[++i]);
        else if (a == "--profile" && i + 1 < argc) profile = argv[++i];
        else paths.push_back(a);
    }
    if (paths.empty()) {
        std::fprintf(stderr, "用法: replay_selftest <pcap...> [--timing capture|interval] "
                             "[--speed N] [--interval-ms N] [--loops N] [--profile X]\n");
        return 1;
    }
    setenv("ARHUD_SERVICE_PROFILE", profile.c_str(), 1);

    /* ---- C 接口：回放前体检 + 服务表导出 ---- */
    std::vector<const char*> cps;
    for (auto& p : paths) cps.push_back(p.c_str());
    std::vector<char> buf(1 << 20);
    int n = arhud_pcap_events(cps.data(), (int)cps.size(), buf.data(), (uint32_t)buf.size());
    if (n < 0) {
        std::fprintf(stderr, "[FAIL] arhud_pcap_events: %s\n", arhud_pcap_error());
        return 2;
    }
    std::printf("== pcap 体检(JSON, %d 字节): %s\n", n, buf.data());

    const std::vector<arhud::ServiceRow>& svcs = arhud::services_for(profile);
    std::printf("== 服务表 profile=%s：%zu 服务 / %zu 事件\n", profile.c_str(), svcs.size(),
                arhud::event_count(svcs));
    n = arhud_profile_events(profile.c_str(), buf.data(), (uint32_t)buf.size());
    if (n < 0) {
        std::fprintf(stderr, "[FAIL] arhud_profile_events\n");
        return 2;
    }
    std::printf("== 服务表(JSON, %d 字节) 前 200 字符: %.200s...\n", n, buf.data());

    /* ---- 覆盖率：pcap 里的事件 vs 服务表 ---- */
    int rc = arhud_pcap_events(cps.data(), (int)cps.size(), buf.data(), (uint32_t)buf.size());
    if (rc < 0) return 2;
    std::map<std::pair<uint16_t, uint16_t>, bool> in_table;
    {
        /* 直接问服务表（避免解析 JSON） */
        std::vector<std::pair<uint16_t, uint16_t> > evs;
        std::string err;
        if (!arhud::ReplayEngine::scan_events(paths, evs, &err)) {
            std::fprintf(stderr, "[FAIL] scan_events: %s\n", err.c_str());
            return 2;
        }
        std::printf("== 覆盖率：\n");
        size_t miss = 0;
        for (auto& e : evs) {
            const bool ok = arhud::has_event(svcs, e.first, e.second);
            if (!ok) miss++;
            std::printf("   %04X:%04X  %s\n", e.first, e.second, ok ? "在表里" : "!! 不在表里");
        }
        std::printf("   合计 %zu 个事件，其中不在表里 %zu 个\n", evs.size(), miss);
    }

    /* ---- 跑回放引擎（假发送器） ---- */
    arhud::ReplayOptions opts;
    opts.loop = loops > 1;
    opts.max_loops = loops;
    opts.timing = (timing == "capture") ? arhud::kTimingCapture : arhud::kTimingInterval;
    opts.interval_ms = interval_ms;
    opts.speed = speed;
    opts.start_delay_ms = 0;

    arhud::ReplayEngine eng;
    std::map<std::pair<uint16_t, uint16_t>, int> seen;
    uint64_t sent = 0, empty = 0;
    auto t0 = std::chrono::steady_clock::now();
    bool ok = eng.start(paths, opts,
                        [&](uint16_t svc, uint16_t ev, const uint8_t* data, uint32_t len) -> int {
                            seen[{svc, ev}]++;
                            sent++;
                            if (!data || len == 0) empty++;
                            return arhud::kSendOk;
                        },
                        [&](uint16_t svc, uint16_t ev) { return arhud::has_event(svcs, svc, ev); });
    if (!ok) {
        std::fprintf(stderr, "[FAIL] 引擎启动失败: %s\n", arhud_pcap_error());
        return 3;
    }
    while (eng.running()) std::this_thread::sleep_for(std::chrono::milliseconds(50));
    eng.stop();
    const double wall = std::chrono::duration_cast<std::chrono::milliseconds>(
                            std::chrono::steady_clock::now() - t0).count() / 1000.0;

    arhud::ReplaySnapshot s = eng.snapshot();
    std::printf("== 回放结果：timing=%s speed=%.1f loops=%llu 墙钟=%.2fs\n", timing.c_str(), speed,
                (unsigned long long)s.loops, wall);
    std::printf("   parsed=%llu sent=%llu failed=%llu unregistered=%llu tp_dropped=%llu "
                "tp_duplicates=%llu packets=%llu\n",
                (unsigned long long)s.parsed, (unsigned long long)s.sent,
                (unsigned long long)s.failed, (unsigned long long)s.unregistered,
                (unsigned long long)s.tp_dropped, (unsigned long long)s.tp_duplicates,
                (unsigned long long)s.packets);
    std::printf("   假发送器实收=%llu 空载荷=%llu\n", (unsigned long long)sent, (unsigned long long)empty);
    std::string report = eng.report_json();
    std::printf("== report_json(%zu 字节) 前 300 字符:\n%.300s...\n", report.size(), report.c_str());

    int bad = 0;
    if (s.parsed != sent) { std::fprintf(stderr, "[FAIL] parsed(%llu) != 发送(%llu)\n",
                                         (unsigned long long)s.parsed, (unsigned long long)sent); bad++; }
    if (s.sent != s.parsed - s.failed) { std::fprintf(stderr, "[FAIL] sent 统计不一致\n"); bad++; }
    if (empty) { std::fprintf(stderr, "[FAIL] 有 %llu 条空载荷\n", (unsigned long long)empty); bad++; }
    if (opts.max_loops && s.loops != opts.max_loops) {
        std::fprintf(stderr, "[FAIL] 轮数 %llu != %u\n", (unsigned long long)s.loops, opts.max_loops); bad++;
    }
    std::printf("%s\n", bad ? "== 自测失败" : "== 自测通过");
    return bad ? 4 : 0;
}
