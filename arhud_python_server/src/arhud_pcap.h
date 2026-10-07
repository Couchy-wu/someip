/*
 * arhud_pcap.h —— pcap 解析 + SOME/IP-TP 分片重组（C++，流式）
 * ==============================================================================
 * 链路：Ethernet(14) / VLAN 0x8100(18) / 0x88A8(22) / Linux SLL(16) → IPv4 → UDP
 *       → SOME/IP 头(16)
 *   message_type 0x02 = Notification  → payload = length-8 字节
 *   message_type 0x22 = SOME/IP-TP 分片（TP 头 4 字节：bit0=More Segments，
 *                        bits1-31 = **字节**偏移）→ 按 (service, method, session) 重组
 *   service 0xFFFF / method 0x8100 = SOME/IP-SD → 跳过
 *
 * 与参考实现（to_longjie_demo_20250625/hud_pcap_huifang_server.cpp，libpcap 版）相比，
 * 这里额外做了三件它没做的事（都是为了"能真实回放 260MB 大抓包"）：
 *   1. **流式**：边扫边重组边吐消息，不再把整个文件的消息/分片全塞进内存
 *      （output3.pcap 260MB：旧实现峰值 300MB+，流式后只保留在途分片）；
 *   2. **分片去重**：抓包被复制/多播重复投递时会出现重复分片，旧实现按偏移排序后
 *      无条件拼接，会把同一段数据拼两次 → 载荷错乱（BPlus/out.pcap 实测有 18 组）；
 *   3. **乱序/缺口判定**：允许分片乱序到达（按偏移缓存），缺口不补齐的消息整条丢弃，
 *      并计入统计，而不是发出半截数据。
 *
 * 另：每条消息带上抓包时间戳（ts_us），供"按原始节奏回放"使用。
 */
#ifndef ARHUD_PCAP_H
#define ARHUD_PCAP_H

#include <stdint.h>
#include <string>
#include <vector>

namespace arhud {

struct PcapMessage {
    uint16_t service;
    uint16_t event;
    uint64_t ts_us;        // 抓包时间戳（微秒，来自 pcap 记录头）
    uint64_t packet_index; // 完成该消息的包序号（1 起）
    uint32_t fragments;    // 分片数（Notification 恒为 1）
    std::vector<uint8_t> payload;  // SOME/IP 载荷（不含 16 字节头）
};

/* 解析统计（体检/排障用） */
struct PcapStats {
    uint64_t packets = 0;          // pcap 记录数
    uint64_t bytes = 0;            // pcap 文件字节数
    uint64_t udp_someip = 0;       // 通过链路/IP/版本校验的 SOME/IP 报文
    uint64_t notifications = 0;    // type=0x02
    uint64_t tp_fragments = 0;     // type=0x22 分片
    uint64_t tp_messages = 0;      // 重组完成的 TP 消息
    uint64_t tp_duplicates = 0;    // 被丢弃的重复分片
    uint64_t tp_dropped = 0;       // 因缺口/截断整条丢弃的 TP 消息
    uint64_t clamped = 0;          // length 字段比实收字节多，被钳到实际长度
    uint64_t snaplen_cut = 0;      // incl_len < orig_len（snaplen 截断）
    uint64_t sd = 0;               // SOME/IP-SD
    uint64_t skipped = 0;          // 非 UDP / 非 IPv4 / 非 SOME/IP / 版本不符
    uint64_t tcp = 0;              // TCP 报文（当前不重组，仅计数）
    bool truncated_file = false;   // 文件末尾有半条记录
};

/*
 * 流式 pcap 读取器：open() 之后反复 next()，每返回 1 就是一条可发送的消息
 * （TP 已重组）。返回 0 = 到文件尾，-1 = 出错。
 */
class PcapStream {
public:
    PcapStream() = default;
    ~PcapStream();
    PcapStream(const PcapStream&) = delete;
    PcapStream& operator=(const PcapStream&) = delete;

    bool open(const std::string& path, std::string* err = nullptr);
    void close();
    int next(PcapMessage& out);
    const PcapStats& stats() const { return stats_; }
    const std::string& error() const { return error_; }
    /* 文件头信息 */
    int linktype() const { return linktype_; }
    bool nanosecond_ts() const { return ns_ts_; }

private:
    void finalize();   // 文件尾结算（未拼完的 TP 计入丢弃）
    struct Impl;
    Impl* impl_ = nullptr;
    PcapStats stats_;
    std::string error_;
    int linktype_ = -1;
    bool ns_ts_ = false;
};

/* 兼容旧接口：一次性把整个 pcap 读成消息列表（小文件/测试用；大文件请用 PcapStream） */
bool parse_pcap(const std::string& path, std::vector<PcapMessage>& msgs);

/* 只扫事件（不保留载荷）：用于"回放前先看清这个 pcap 有什么" */
struct PcapEventCount {
    uint16_t service;
    uint16_t event;
    uint64_t notifications;   // type=0x02 条数
    uint64_t tp_messages;     // TP 重组条数
    uint32_t min_len;
    uint32_t max_len;
};
bool scan_pcap_events(const std::string& path, std::vector<PcapEventCount>& events,
                      PcapStats* stats = nullptr);

}  // namespace arhud

#endif /* ARHUD_PCAP_H */
