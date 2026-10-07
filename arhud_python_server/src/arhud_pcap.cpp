/*
 * arhud_pcap.cpp —— pcap 解析 + SOME/IP-TP 重组（实现，见 arhud_pcap.h 的说明）
 */
#include "arhud_pcap.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>

#if defined(_WIN32)
#include <winsock2.h>
#else
#include <arpa/inet.h>
#endif

namespace arhud {

namespace {

/* magic：把文件前 4 字节按大端读出来的值。
 *   0xa1b2c3d4 → 文件本身是大端；0xd4c3b2a1 → 文件是小端；
 *   0xa1b23c4d / 0x4d3cb2a1 为对应的纳秒时间戳版本；
 *   0x0a0d0d0a 为 pcapng（需要先转换）。 */
const uint32_t kPcapMagicBe   = 0xa1b2c3d4u;
const uint32_t kPcapMagicLe   = 0xd4c3b2a1u;
const uint32_t kPcapMagicNsBe = 0xa1b23c4du;
const uint32_t kPcapMagicNsLe = 0x4d3cb2a1u;
const uint32_t kPcapngMagic   = 0x0a0d0d0au;

const size_t kEtherHeader   = 14;
const size_t kSllHeader     = 16;
const size_t kSomeipHeader  = 16;
const size_t kTpHeader      = 4;
const uint32_t kMaxPayload  = 64u * 1024u * 1024u;  // 单条载荷上限（防损坏 length 拖垮内存）

inline uint16_t rd_be16(const uint8_t* p) { return (uint16_t)((p[0] << 8) | p[1]); }
inline uint32_t rd_be32(const uint8_t* p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}
inline uint32_t rd32(const uint8_t* p, bool be) {
    if (be) return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* TP 重组键：(service, method, session) —— 与参考实现一致 */
struct TpKey {
    uint16_t service, method, session;
    bool operator<(const TpKey& o) const {
        if (service != o.service) return service < o.service;
        if (method != o.method) return method < o.method;
        return session < o.session;
    }
};

/* 分片签名：用于识别"抓包重复投递"的同一分片 */
struct FragSig {
    uint32_t offset;
    uint32_t length;
    bool more;
};

struct TpGroup {
    uint32_t next = 0;                                  // 已连续收齐的字节数
    std::vector<uint8_t> buf;                           // 已连续部分
    std::map<uint32_t, std::vector<uint8_t>> pending;   // 乱序到达、等待缺口补齐
    std::vector<FragSig> sigs;                          // 本条消息已收分片签名
    std::map<uint32_t, bool> offsets;                   // 已收到的偏移（判重）
    bool finished = false;                              // 已见到 More=0 的分片
    uint32_t fragments = 0;
    uint64_t first_pkt = 0;
};

}  // namespace

struct PcapStream::Impl {
    std::ifstream f;
    bool be = false;
    bool ns = false;
    int linktype = -1;
    std::vector<uint8_t> pkt;                            // 复用的包缓冲
    std::map<TpKey, TpGroup> groups;
    std::map<TpKey, std::vector<FragSig>> last_completed;  // 上一条完成消息的分片签名
    bool eof = false;
    bool finalized = false;
};

PcapStream::~PcapStream() { close(); }

void PcapStream::close() {
    if (impl_) {
        finalize();
        delete impl_;
        impl_ = nullptr;
    }
}

/* 收尾：把文件尾仍未拼完的 TP 消息计入"丢弃"（半截数据绝不发布），只结算一次 */
void PcapStream::finalize() {
    if (!impl_ || impl_->finalized) return;
    impl_->finalized = true;
    for (auto& kv : impl_->groups)
        if (!kv.second.buf.empty() || !kv.second.pending.empty()) stats_.tp_dropped++;
    impl_->groups.clear();
}

bool PcapStream::open(const std::string& path, std::string* err) {
    close();
    impl_ = new Impl();
    stats_ = PcapStats();
    error_.clear();

    impl_->f.open(path.c_str(), std::ios::binary);
    if (!impl_->f) {
        error_ = "无法打开文件: " + path;
        if (err) *err = error_;
        delete impl_;
        impl_ = nullptr;
        return false;
    }
    uint8_t hdr[24];
    impl_->f.read(reinterpret_cast<char*>(hdr), 24);
    if (impl_->f.gcount() != 24) {
        error_ = "文件太小，不是 pcap: " + path;
        if (err) *err = error_;
        delete impl_;
        impl_ = nullptr;
        return false;
    }
    const uint32_t magic = rd_be32(hdr);
    if (magic == kPcapngMagic) {
        error_ = "这是 pcapng 格式（参考实现用 libpcap 能读）；请先转换："
                 "tcpdump -r in.pcapng -w out.pcap 或 editcap -F pcap in.pcapng out.pcap";
        if (err) *err = error_;
        delete impl_;
        impl_ = nullptr;
        return false;
    }
    if (magic == kPcapMagicBe)        { impl_->be = true;  impl_->ns = false; }
    else if (magic == kPcapMagicLe)   { impl_->be = false; impl_->ns = false; }
    else if (magic == kPcapMagicNsBe) { impl_->be = true;  impl_->ns = true; }
    else if (magic == kPcapMagicNsLe) { impl_->be = false; impl_->ns = true; }
    else {
        char b[64];
        std::snprintf(b, sizeof(b), "不支持的 pcap magic: %02X %02X %02X %02X",
                      hdr[0], hdr[1], hdr[2], hdr[3]);
        error_ = b;
        if (err) *err = error_;
        delete impl_;
        impl_ = nullptr;
        return false;
    }
    impl_->linktype = (int)rd32(hdr + 20, impl_->be);
    linktype_ = impl_->linktype;
    ns_ts_ = impl_->ns;
    if (impl_->linktype != 1 /*Ethernet*/ && impl_->linktype != 113 /*Linux SLL*/) {
        char b[128];
        std::snprintf(b, sizeof(b), "暂不支持的链路类型 linktype=%d（只支持 1=Ethernet / 113=Linux SLL）",
                      impl_->linktype);
        error_ = b;
        if (err) *err = error_;
        delete impl_;
        impl_ = nullptr;
        return false;
    }
    impl_->f.seekg(0, std::ios::end);
    stats_.bytes = (uint64_t)impl_->f.tellg();
    impl_->f.seekg(24, std::ios::beg);
    return true;
}

int PcapStream::next(PcapMessage& out) {
    if (!impl_) return -1;
    Impl& im = *impl_;

    for (;;) {
        if (im.eof) return 0;
        uint8_t rh[16];
        im.f.read(reinterpret_cast<char*>(rh), 16);
        if (im.f.gcount() != 16) {
            if (im.f.gcount() != 0) stats_.truncated_file = true;
            im.eof = true;
            finalize();
            return 0;
        }
        const uint32_t ts_sec  = rd32(rh + 0, im.be);
        const uint32_t ts_frac = rd32(rh + 4, im.be);
        const uint32_t incl    = rd32(rh + 8, im.be);
        const uint32_t orig    = rd32(rh + 12, im.be);
        stats_.packets++;

        if (incl > kMaxPayload) {           // 明显损坏的记录头
            stats_.skipped++;
            im.f.seekg(incl, std::ios::cur);
            continue;
        }
        im.pkt.resize(incl);
        if (incl) {
            im.f.read(reinterpret_cast<char*>(im.pkt.data()), incl);
            if (im.f.gcount() != (std::streamsize)incl) {
                stats_.truncated_file = true;
                im.eof = true;
                finalize();
                return 0;
            }
        }
        if (incl < orig) { stats_.snaplen_cut++; }  // 被 snaplen 截断
        const uint8_t* pkt = im.pkt.data();
        const size_t cap = im.pkt.size();

        /* ---- 链路层 ---- */
        size_t off = 0;
        if (im.linktype == 113) {           // Linux SLL：16 字节头，协议在 14:16
            if (cap < kSllHeader) { stats_.skipped++; continue; }
            const uint16_t proto = rd_be16(pkt + 14);
            if (proto != 0x0800) { stats_.skipped++; continue; }
            off = kSllHeader;
        } else {                            // Ethernet，可能带 VLAN 标签
            if (cap < kEtherHeader) { stats_.skipped++; continue; }
            uint16_t et = rd_be16(pkt + 12);
            off = kEtherHeader;
            while (et == 0x8100 || et == 0x88A8 || et == 0x9100) {
                if (cap < off + 4) break;
                et = rd_be16(pkt + off + 2);
                off += 4;
            }
            if (et != 0x0800) { stats_.skipped++; continue; }
        }

        /* ---- IPv4 ---- */
        if (cap < off + 20) { stats_.skipped++; continue; }
        if ((pkt[off] >> 4) != 4) { stats_.skipped++; continue; }
        const size_t ihl = (size_t)(pkt[off] & 0x0f) * 4;
        if (ihl < 20 || cap < off + ihl) { stats_.skipped++; continue; }
        const uint8_t proto = pkt[off + 9];
        const uint16_t ip_total = rd_be16(pkt + off + 2);
        if (proto == 6) { stats_.tcp++; continue; }              // TCP 不做流重组，仅计数
        if (proto != 17) { stats_.skipped++; continue; }         // 只处理 UDP
        size_t ip_end = off + (ip_total >= ihl ? ip_total : ihl);
        if (ip_end > cap) ip_end = cap;

        /* ---- UDP ---- */
        const size_t udp_off = off + ihl;
        if (cap < udp_off + 8) { stats_.skipped++; continue; }
        const uint16_t udp_len = rd_be16(pkt + udp_off + 4);
        size_t body_end = udp_off + (udp_len >= 8 ? udp_len : 8);
        if (body_end > ip_end) body_end = ip_end;
        if (body_end > cap) body_end = cap;
        const uint8_t* body = pkt + udp_off + 8;
        const size_t body_len = body_end > udp_off + 8 ? body_end - (udp_off + 8) : 0;
        if (body_len < kSomeipHeader) { stats_.skipped++; continue; }

        /* ---- SOME/IP ---- */
        const uint16_t svc  = rd_be16(body + 0);
        const uint16_t meth = rd_be16(body + 2);
        const uint32_t len  = rd_be32(body + 4);
        const uint16_t sess = rd_be16(body + 10);
        const uint8_t  ver  = body[12];
        const uint8_t  mtype = body[14];

        if (svc == 0xFFFF && meth == 0x8100) { stats_.sd++; continue; }
        if (ver != 0x01) { stats_.skipped++; continue; }
        stats_.udp_someip++;

        if (mtype == 0x02) {   // Notification
            size_t plen = len >= 8 ? (size_t)(len - 8) : 0;
            const size_t avail = body_len - kSomeipHeader;
            if (plen > avail) { plen = avail; stats_.clamped++; }
            if (plen > kMaxPayload) { plen = kMaxPayload; stats_.clamped++; }
            stats_.notifications++;
            out.service = svc;
            out.event = meth;
            out.ts_us = (uint64_t)ts_sec * 1000000ull + (im.ns ? ts_frac / 1000ull : ts_frac);
            out.packet_index = stats_.packets;
            out.fragments = 1;
            out.payload.assign(body + kSomeipHeader, body + kSomeipHeader + plen);
            return 1;
        }

        if (mtype == 0x22) {   // SOME/IP-TP 分片
            if (body_len < kSomeipHeader + kTpHeader) { stats_.skipped++; continue; }
            const uint32_t tp_raw = rd_be32(body + kSomeipHeader);
            const bool more = (tp_raw & 0x1u) != 0;
            const uint32_t toff = tp_raw & 0xFFFFFFFEu;
            const uint8_t* frag = body + kSomeipHeader + kTpHeader;
            const size_t frag_len = body_len - kSomeipHeader - kTpHeader;
            stats_.tp_fragments++;

            const TpKey key{svc, meth, sess};
            TpGroup& g = im.groups[key];

            /* 1) 完全重复的分片（同一偏移已收过）→ 丢弃，不参与拼接 */
            if (g.offsets.count(toff)) {
                stats_.tp_duplicates++;
                continue;
            }
            /* 2) 已完成的"上一条消息"的重复尾巴（抓包重复投递）→ 丢弃 */
            if (g.buf.empty() && g.pending.empty() && g.sigs.empty() && toff != 0) {
                auto lc = im.last_completed.find(key);
                if (lc != im.last_completed.end()) {
                    bool dup = false;
                    for (const FragSig& s : lc->second) {
                        if (s.offset == toff && s.length == frag_len && s.more == more) { dup = true; break; }
                    }
                    if (dup) { stats_.tp_duplicates++; continue; }
                }
            }
            /* 3) 同 key 的消息重新从 0 开始，而上一条没拼完 → 丢上一条（绝不发半截）。
             *    能走到这里的组一定是未完成/有缺口的：拼齐的组在上面就已经发布并 erase 了。 */
            if (toff == 0 && (!g.buf.empty() || !g.pending.empty())) {
                stats_.tp_dropped++;
                g = TpGroup();
            }

            g.offsets[toff] = true;
            g.pending[toff] = std::vector<uint8_t>(frag, frag + frag_len);
            g.sigs.push_back(FragSig{toff, (uint32_t)frag_len, more});
            g.fragments++;
            if (g.first_pkt == 0) g.first_pkt = stats_.packets;
            if (!more) g.finished = true;

            /* 连续段搬进 buf */
            while (!g.pending.empty()) {
                auto it = g.pending.begin();
                if (it->first != g.next) break;
                g.buf.insert(g.buf.end(), it->second.begin(), it->second.end());
                g.next += (uint32_t)it->second.size();
                g.pending.erase(it);
            }

            if (g.finished && g.pending.empty()) {   // 拼齐 → 发布
                stats_.tp_messages++;
                out.service = svc;
                out.event = meth;
                out.ts_us = (uint64_t)ts_sec * 1000000ull + (im.ns ? ts_frac / 1000ull : ts_frac);
                out.packet_index = g.first_pkt ? g.first_pkt : stats_.packets;
                out.fragments = g.fragments;
                out.payload.swap(g.buf);
                im.last_completed[key] = g.sigs;     // 记住签名，后面重复尾巴才认得出来
                im.groups.erase(key);
                return 1;
            }
            continue;
        }

        stats_.skipped++;
    }
}

/* ---------------- 兼容接口 ---------------- */

bool parse_pcap(const std::string& path, std::vector<PcapMessage>& msgs) {
    PcapStream s;
    std::string err;
    if (!s.open(path, &err)) return false;
    PcapMessage m;
    int rc;
    while ((rc = s.next(m)) == 1) msgs.push_back(std::move(m));
    return rc == 0 && !msgs.empty();
}

bool scan_pcap_events(const std::string& path, std::vector<PcapEventCount>& events, PcapStats* stats) {
    PcapStream s;
    std::string err;
    if (!s.open(path, &err)) return false;
    std::map<std::pair<uint16_t, uint16_t>, PcapEventCount> acc;
    PcapMessage m;
    int rc;
    while ((rc = s.next(m)) == 1) {
        PcapEventCount& c = acc[{m.service, m.event}];
        c.service = m.service;
        c.event = m.event;
        if (m.fragments > 1) c.tp_messages++;
        else c.notifications++;
        const uint32_t n = (uint32_t)m.payload.size();
        if (c.min_len == 0 || n < c.min_len) c.min_len = n;
        if (n > c.max_len) c.max_len = n;
    }
    events.clear();
    for (auto& kv : acc) events.push_back(kv.second);
    if (stats) *stats = s.stats();
    return rc == 0;
}

}  // namespace arhud
