#include "arhud_pcap.h"

#ifdef _WIN32
#include <winsock2.h>
#else
#include <arpa/inet.h>
#endif
#include <cstdio>
#include <cstring>
#include <map>
#include <fstream>
#include <algorithm>

namespace arhud {

namespace {

struct TpKey {
    uint16_t service, method, session;
    bool operator<(const TpKey& o) const {
        if (service != o.service) return service < o.service;
        if (method != o.method) return method < o.method;
        return session < o.session;
    }
};

struct TpPart {
    uint32_t offset;
    bool more;
    std::vector<uint8_t> data;
};

}  // namespace

bool parse_pcap(const std::string& path, std::vector<PcapMessage>& msgs) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;

    char hdr[24];
    f.read(hdr, 24);
    if (f.gcount() != 24) return false;

    bool be = (static_cast<unsigned char>(hdr[0]) == 0xa1);  // 0xa1b2c3d4 大端
    auto rd16 = [&](const char* p) -> uint16_t {
        return be ? ntohs(*reinterpret_cast<const uint16_t*>(p))
                  : (static_cast<uint16_t>(static_cast<unsigned char>(p[0])) |
                     (static_cast<uint16_t>(static_cast<unsigned char>(p[1])) << 8));
    };
    auto rd32 = [&](const char* p) -> uint32_t {
        if (be) return ntohl(*reinterpret_cast<const uint32_t*>(p));
        return static_cast<uint32_t>(static_cast<unsigned char>(p[0])) |
               (static_cast<uint32_t>(static_cast<unsigned char>(p[1])) << 8) |
               (static_cast<uint32_t>(static_cast<unsigned char>(p[2])) << 16) |
               (static_cast<uint32_t>(static_cast<unsigned char>(p[3])) << 24);
    };

    std::vector<PcapMessage> plain;
    std::map<TpKey, std::vector<TpPart>> tp_parts;

    while (f) {
        char rh[16];
        f.read(rh, 16);
        if (f.gcount() != 16) break;
        uint32_t incl_len = rd32(rh + 8);
        std::vector<uint8_t> pkt(incl_len);
        f.read(reinterpret_cast<char*>(pkt.data()), incl_len);
        if (f.gcount() != static_cast<std::streamsize>(incl_len)) break;

        // Ethernet + VLAN（EtherType 是网络字节序，恒为大端）
        size_t off = 14;
        if (pkt.size() >= 14) {
            uint16_t et = ntohs(*reinterpret_cast<const uint16_t*>(pkt.data() + 12));
            if (et == 0x8100) off = 18;
            else if (et == 0x88a8) off = 22;
        }
        if (pkt.size() < off + 20) continue;
        if ((pkt[off] >> 4) != 4) continue;        // IPv4
        if (pkt[off + 9] != 17) continue;          // UDP
        size_t ihl = (pkt[off] & 0x0f) * 4;
        size_t pay_off = off + ihl + 8;            // after UDP header
        if (pkt.size() < pay_off + 16) continue;

        const uint8_t* h = pkt.data() + pay_off;
        uint16_t svc = ntohs(*reinterpret_cast<const uint16_t*>(h));
        uint16_t meth = ntohs(*reinterpret_cast<const uint16_t*>(h + 2));
        uint32_t len = ntohl(*reinterpret_cast<const uint32_t*>(h + 4));
        uint16_t sess = ntohs(*reinterpret_cast<const uint16_t*>(h + 10));
        uint8_t mtype = h[14];
        if (svc == 0xffff && meth == 0x8100) continue;  // SD
        if (h[12] != 0x01) continue;                    // SOME/IP 版本

        if (mtype == 0x02) {  // Notification
            uint32_t plen = len >= 8 ? len - 8 : 0;
            if (pkt.size() < pay_off + 16 + plen) continue;
            PcapMessage m;
            m.service = svc;
            m.event = meth;
            m.payload.assign(pkt.begin() + pay_off + 16, pkt.begin() + pay_off + 16 + plen);
            plain.push_back(std::move(m));
        } else if (mtype == 0x22) {  // SOME/IP-TP segment
            if (pkt.size() < pay_off + 20) continue;
            uint32_t tpoff_raw = ntohl(*reinterpret_cast<const uint32_t*>(h + 16));
            TpPart part;
            part.more = (tpoff_raw & 0x1) != 0;
            part.offset = tpoff_raw & 0xFFFFFFFE;  // 字节偏移
            part.data.assign(pkt.begin() + pay_off + 20, pkt.end());
            tp_parts[{svc, meth, sess}].push_back(std::move(part));
        }
    }

    // TP 重组
    for (auto& kv : tp_parts) {
        auto& parts = kv.second;
        std::sort(parts.begin(), parts.end(),
                  [](const TpPart& a, const TpPart& b) { return a.offset < b.offset; });
        PcapMessage m;
        m.service = kv.first.service;
        m.event = kv.first.method;
        for (auto& p : parts)
            m.payload.insert(m.payload.end(), p.data.begin(), p.data.end());
        if (!m.payload.empty())
            plain.push_back(std::move(m));
    }

    msgs.swap(plain);
    return true;
}

}  // namespace arhud
