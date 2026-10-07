/*
 * arhud_replay.h —— pcap 回放引擎（协议栈无关）
 * ==============================================================================
 * 把"读 pcap → 按节奏发布"这件事从服务端实现里独立出来，SP 版（arhud_server_sp.cpp）
 * 和标准 vsomeip 版（arhud_server.cpp）共用同一份回放语义：
 *
 *   · 多文件 / 目录：Python 侧展开目录后传进来，文件顺序即回放顺序；
 *   · 两种节奏（与参考实现 to_longjie_demo_20250625/hud_pcap_huifang_server.cpp 对齐）：
 *       kTimingCapture  —— 按 pcap 里记录的包间隔回放（参考实现的做法；speed 可加速）
 *       kTimingInterval —— 固定间隔 interval_ms（老接口行为，给"慢速喂给板端"用）
 *   · 流式读取：不把整个 pcap 读进内存，260MB 的 output3.pcap 峰值内存只有 MB 级；
 *   · 循环：每轮重新打开文件流式读（不做内存缓存），所以大文件循环回放也不会涨内存；
 *   · 统计：总数 + 逐 (service,event) 的 发布/失败 计数，供回放后核对"数据有没有发全"。
 */
#ifndef ARHUD_REPLAY_H
#define ARHUD_REPLAY_H

#include <atomic>
#include <cstdint>
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace arhud {

enum ReplayTiming {
    kTimingInterval = 0,  // 固定间隔（interval_ms）
    kTimingCapture  = 1,  // 按抓包时间戳（参考实现）
};

enum ReplaySendResult {
    kSendOk  = 0,   // 发送成功
    kSendErr = -1,  // 发送失败
};

struct ReplayOptions {
    bool loop = true;             // 是否循环
    int  timing = kTimingInterval;
    uint32_t interval_ms = 10;    // timing=kTimingInterval 时每条之间的间隔
    double speed = 1.0;           // timing=kTimingCapture 时的时间倍速（2.0 = 两倍速）
    uint32_t max_loops = 0;       // 0 = 不限轮数
    uint32_t start_delay_ms = 0;  // 起播前等待（等客户端订阅稳定）
    int log_every = 0;            // >0：每 N 条打印一行（调试用）
};

struct ReplayEventStat {
    uint64_t attempted = 0;
    uint64_t sent = 0;
    uint64_t unregistered = 0;   // 服务表里没有该事件（仍尝试发送，与参考实现一致）
};

struct ReplaySnapshot {
    uint64_t files = 0;
    uint64_t loops = 0;
    uint64_t parsed = 0;          // 从 pcap 读到的消息条数
    uint64_t sent = 0;            // 发送成功（发送接口返回 0）
    uint64_t failed = 0;          // 发送失败
    uint64_t unregistered = 0;    // 不在服务表里的条数
    uint64_t tp_dropped = 0;      // pcap 里 TP 残缺被丢弃的消息
    uint64_t tp_duplicates = 0;   // 被去重丢掉的重复分片
    uint64_t packets = 0;         // 读过的 pcap 记录数
    double elapsed_s = 0.0;
    bool running = false;
    std::map<std::pair<uint16_t, uint16_t>, ReplayEventStat> per_event;
};

class ReplayEngine {
public:
    /* 发送一条消息：返回 kSendOk(0) 表示成功，其它为失败 */
    using Sender = std::function<int(uint16_t service, uint16_t event,
                                     const uint8_t* data, uint32_t len)>;
    /* 可选：判断 (service,event) 是否在服务表里（用于统计"发不出去"的条数） */
    using Registered = std::function<bool(uint16_t service, uint16_t event)>;

    ReplayEngine() = default;
    ~ReplayEngine();
    ReplayEngine(const ReplayEngine&) = delete;
    ReplayEngine& operator=(const ReplayEngine&) = delete;

    /* 启动回放线程。paths 为空 / 打不开任一文件 时返回 false 并写 err。 */
    bool start(const std::vector<std::string>& paths, const ReplayOptions& opts,
               Sender sender, Registered registered = nullptr, std::string* err = nullptr);
    void stop();
    bool running() const { return running_.load(); }

    ReplaySnapshot snapshot() const;
    /* 回放报告（JSON）：总数 + 逐事件 + 文件/节奏参数，便于贴日志/落盘 */
    std::string report_json() const;

    /* 静态工具：扫一组 pcap，返回出现过的 (service,event) 与统计（不发送） */
    static bool scan_events(const std::vector<std::string>& paths,
                            std::vector<std::pair<uint16_t, uint16_t> >& events,
                            std::string* err = nullptr);

private:
    void thread_main(std::vector<std::string> paths, ReplayOptions opts,
                     Sender sender, Registered registered);

    std::thread th_;
    std::atomic<bool> running_{false};
    mutable std::mutex mtx_;
    ReplaySnapshot snap_;
    double elapsed_s_ = 0.0;
};

}  // namespace arhud

#endif /* ARHUD_REPLAY_H */
