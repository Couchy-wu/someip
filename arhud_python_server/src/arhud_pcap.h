/*
 * arhud_pcap.h —— pcap 解析 + SOME/IP-TP 分片重组（C++）
 * 与 longjie_py/pcap_replay_tp.py 逻辑一致：
 *   Ethernet(14) / VLAN 0x8100(18) / IPv4 / UDP → SOME/IP 头(16)
 *   message_type 0x02 = Notification；0x22 = TP 分片（4字节TP头：bit0=More, bits1-31=字节偏移）
 *   按 (service, method, session) 重组；跳过 SD(0xFFFF/0x8100)
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
    std::vector<uint8_t> payload;  // SOME/IP 载荷（不含 16 字节头）
};

/* 解析 pcap，返回所有通知消息（TP 已重组）。成功返回 true；msg 填充结果。 */
bool parse_pcap(const std::string& path, std::vector<PcapMessage>& msgs);

}  // namespace arhud

#endif /* ARHUD_PCAP_H */
