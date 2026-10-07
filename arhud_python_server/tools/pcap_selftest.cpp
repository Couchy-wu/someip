/*
 * pcap_selftest.cpp —— arhud_pcap 的独立自测/体检工具（不链接 SOME/IP 协议栈）
 * ---------------------------------------------------------------------------
 * 用途：
 *   1. 在没有协议栈（macOS/Windows/任意 Linux）上验证 pcap 解析 + TP 重组是否正确；
 *   2. 回放前先看清 pcap 有什么：逐事件条数、载荷长度范围、时间跨度、丢弃/重复分片；
 *   3. 与 tools/analyze_pcap.py（纯 Python 实现）交叉比对，互为对照。
 *
 * 编译（macOS/Linux 均可）：
 *   g++ -std=c++14 -O2 -I src src/arhud_pcap.cpp tools/pcap_selftest.cpp -o /tmp/pcap_selftest
 * 用法：
 *   /tmp/pcap_selftest a.pcap b.pcap ...
 *   /tmp/pcap_selftest --head 20 a.pcap        # 额外打印前 20 条（svc:evt len ts）
 *   /tmp/pcap_selftest --json out.json a.pcap
 */
#include "arhud_pcap.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace {

struct Row {
    uint64_t notifications = 0;
    uint64_t tp = 0;
    uint32_t min_len = 0, max_len = 0;
};

void add_len(Row& r, uint32_t n) {
    if (r.min_len == 0 || n < r.min_len) r.min_len = n;
    if (n > r.max_len) r.max_len = n;
}

int run_one(const std::string& path, int head, std::vector<std::string>* json_rows) {
    arhud::PcapStream s;
    std::string err;
    if (!s.open(path, &err)) {
        std::fprintf(stderr, "[FAIL] %s: %s\n", path.c_str(), err.c_str());
        return 2;
    }
    std::map<std::pair<uint16_t, uint16_t>, Row> rows;
    uint64_t total = 0, first_ts = 0, last_ts = 0;
    int shown = 0;
    std::printf("== %s\n", path.c_str());
    std::printf("   linktype=%d %s时间戳  %.1f MB\n", s.linktype(),
                s.nanosecond_ts() ? "纳秒" : "微秒", s.stats().bytes / 1048576.0);
    arhud::PcapMessage m;
    int rc;
    while ((rc = s.next(m)) == 1) {
        Row& r = rows[{m.service, m.event}];
        if (m.fragments > 1) r.tp++; else r.notifications++;
        add_len(r, (uint32_t)m.payload.size());
        if (total == 0) first_ts = m.ts_us;
        last_ts = m.ts_us;
        total++;
        if (head > 0 && shown < head) {
            std::printf("   #%llu %04X:%04X len=%zu frags=%u ts=%.6f\n",
                        (unsigned long long)m.packet_index, m.service, m.event,
                        m.payload.size(), m.fragments, m.ts_us / 1e6);
            shown++;
        }
    }
    const arhud::PcapStats& st = s.stats();
    std::printf("   包=%llu  SOME/IP=%llu  SD=%llu  通知=%llu  TP分片=%llu  TP消息=%llu\n",
                (unsigned long long)st.packets, (unsigned long long)st.udp_someip,
                (unsigned long long)st.sd, (unsigned long long)st.notifications,
                (unsigned long long)st.tp_fragments, (unsigned long long)st.tp_messages);
    std::printf("   丢弃: TP重复分片=%llu  TP不完整=%llu  长度钳制=%llu  跳过=%llu  TCP=%llu%s\n",
                (unsigned long long)st.tp_duplicates, (unsigned long long)st.tp_dropped,
                (unsigned long long)st.clamped, (unsigned long long)st.skipped,
                (unsigned long long)st.tcp, st.truncated_file ? "  [文件尾部截断]" : "");
    if (total)
        std::printf("   消息=%llu  时间跨度=%.3f 秒\n", (unsigned long long)total,
                    (last_ts - first_ts) / 1e6);
    std::printf("   %-14s %8s %8s   %s\n", "事件", "通知", "TP", "载荷长度");
    for (auto& kv : rows) {
        std::printf("   %04X:%-7X %8llu %8llu   %u..%u\n", kv.first.first, kv.first.second,
                    (unsigned long long)kv.second.notifications, (unsigned long long)kv.second.tp,
                    kv.second.min_len, kv.second.max_len);
        if (json_rows) {
            char b[256];
            std::snprintf(b, sizeof(b),
                          "{\"file\":\"%s\",\"service\":%u,\"event\":%u,\"notifications\":%llu,"
                          "\"tp\":%llu,\"min_len\":%u,\"max_len\":%u}",
                          path.c_str(), kv.first.first, kv.first.second,
                          (unsigned long long)kv.second.notifications,
                          (unsigned long long)kv.second.tp, kv.second.min_len, kv.second.max_len);
            json_rows->push_back(b);
        }
    }
    if (json_rows) {
        char b[512];
        std::snprintf(b, sizeof(b),
                      "{\"file\":\"%s\",\"packets\":%llu,\"messages\":%llu,\"notifications\":%llu,"
                      "\"tp_fragments\":%llu,\"tp_messages\":%llu,\"tp_duplicates\":%llu,"
                      "\"tp_dropped\":%llu,\"duration_s\":%.3f}",
                      path.c_str(), (unsigned long long)st.packets, (unsigned long long)total,
                      (unsigned long long)st.notifications, (unsigned long long)st.tp_fragments,
                      (unsigned long long)st.tp_messages, (unsigned long long)st.tp_duplicates,
                      (unsigned long long)st.tp_dropped, total ? (last_ts - first_ts) / 1e6 : 0.0);
        json_rows->push_back(b);
    }
    return rc == 0 ? 0 : 3;
}

}  // namespace

int main(int argc, char** argv) {
    int head = 0;
    std::string json_out;
    std::vector<std::string> paths;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--head" && i + 1 < argc) { head = std::atoi(argv[++i]); }
        else if (a == "--json" && i + 1 < argc) { json_out = argv[++i]; }
        else paths.push_back(a);
    }
    if (paths.empty()) {
        std::fprintf(stderr, "用法: pcap_selftest [--head N] [--json out.json] <pcap> [pcap...]\n");
        return 1;
    }
    std::vector<std::string> json_rows;
    int worst = 0;
    for (const auto& p : paths) {
        int rc = run_one(p, head, json_out.empty() ? nullptr : &json_rows);
        if (rc > worst) worst = rc;
        std::printf("\n");
    }
    if (!json_out.empty()) {
        FILE* f = std::fopen(json_out.c_str(), "w");
        if (!f) { std::fprintf(stderr, "无法写 %s\n", json_out.c_str()); return 4; }
        std::fprintf(f, "[\n");
        for (size_t i = 0; i < json_rows.size(); ++i)
            std::fprintf(f, "  %s%s\n", json_rows[i].c_str(), i + 1 < json_rows.size() ? "," : "");
        std::fprintf(f, "]\n");
        std::fclose(f);
        std::printf("JSON 报告已写入 %s\n", json_out.c_str());
    }
    return worst;
}
