// 端序（字节序）检查与网络序（大端）编解码 —— C++ 参考实现
// ============================================================
// 1) 识别本机大小端：C++20 用 std::endian；C++14 用运行时探测（本项目编译 C++14）
// 2) 网络传输必须用大端（SOME/IP 与 ArHud 结构均为网络字节序）：
//    - 不要 memcpy 原生结构体当载荷！小端主机的原生 struct 是小端字节
//    - 用 htonl/htons（POSIX/Winsock）或逐字节显式移位，保证发出的字节与
//      Python 端(struct '>')、C++ 对端完全一致
// 编译: g++ -std=c++14 -I/usr/local/include endian_check.cpp -o endian_check
#include <cstdint>
#include <cstring>
#include <iostream>

#if defined(_WIN32)
#include <winsock2.h>   // htonl/htons
#else
#include <arpa/inet.h>  // htonl/htons
#endif

// ---------- 1) 机器端序识别 ----------
static bool is_little_endian() {
    const uint16_t v = 0x0102;
    uint8_t b[2];
    std::memcpy(b, &v, sizeof(v));
    return b[0] == 0x02;   // 低字节在前 = 小端
}

static const char* host_endian() {
    return is_little_endian() ? "little" : "big";
}

// ---------- 2) 网络字节序（大端）编解码 ----------
// 主机序 -> 大端（网络序）；大端 -> 主机序。htonl/ntohl 是平台自带的标准做法
static uint32_t to_network(uint32_t host_value) {
    return htonl(host_value);
}
static uint32_t from_network(uint32_t network_value) {
    return ntohl(network_value);
}

// 不依赖 htonl 的显式大端写入（跨平台、自解释；推荐用于协议序列化）
static void write_u32_be(uint8_t* dst, uint32_t value) {
    dst[0] = static_cast<uint8_t>((value >> 24) & 0xFF);
    dst[1] = static_cast<uint8_t>((value >> 16) & 0xFF);
    dst[2] = static_cast<uint8_t>((value >> 8) & 0xFF);
    dst[3] = static_cast<uint8_t>(value & 0xFF);
}
static uint32_t read_u32_be(const uint8_t* src) {
    return (static_cast<uint32_t>(src[0]) << 24)
         | (static_cast<uint32_t>(src[1]) << 16)
         | (static_cast<uint32_t>(src[2]) << 8)
         | static_cast<uint32_t>(src[3]);
}

int main() {
    std::cout << "本机端序: " << host_endian() << std::endl;

    // 大端编码固定字节（任意端序主机输出一致）
    uint8_t buf[4];
    write_u32_be(buf, 0x01020304u);
    bool ok = (buf[0] == 0x01 && buf[1] == 0x02 && buf[2] == 0x03 && buf[3] == 0x04);
    std::cout << "0x01020304 大端字节: "
              << std::hex << (int)buf[0] << " " << (int)buf[1] << " "
              << (int)buf[2] << " " << (int)buf[3] << std::dec << std::endl;

    // 往返（htonl / 显式移位 两条路径）
    uint32_t v = 0xDEADBEEFu;
    uint32_t net = to_network(v);
    uint32_t back = from_network(net);
    uint32_t via_be = read_u32_be(buf);
    ok = ok && (back == v) && (via_be == 0x01020304u);

    // 警告：memcpy 原生结构体会随主机端序变化！
    struct Native { uint16_t a; uint32_t b; } native = {0x0102, 0x01020304};
    std::cout << "警告: 原生 struct memcpy 字节(小端主机=小端字节): ";
    const uint8_t* raw = reinterpret_cast<const uint8_t*>(&native);
    std::cout << std::hex << (int)raw[0] << " " << (int)raw[1] << std::dec
              << " ... (载荷不应直接 memcpy!)" << std::endl;

    std::cout << (ok ? "端序自测通过 ✓ (大端字节与主机端序无关)" : "端序自测失败 ✘") << std::endl;
    return ok ? 0 : 1;
}
