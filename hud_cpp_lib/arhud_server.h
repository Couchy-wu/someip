/*
 * arhud_server.h —— AR-HUD SOME/IP 服务端 C 接口（Python ctypes 可调用）
 * =========================================================================
 * C++ 服务端库（内部 vsomeip 3.4.10）：一个应用提供 11 个服务 / 23 个事件，
 * 供 Python 通过 ctypes 调用：发送数据、指定 pcap 回放、结构化赋值组包。
 *
 * 用法（Python）：
 *   srv = arhud_server_create("192.168.1.10", NULL)   # NULL=自动生成配置
 *   arhud_server_start(srv)
 *   arhud_server_notify(srv, 0x000A, 0x8001, data, len)
 *   arhud_server_replay_start(srv, "out.pcap", 1, 10)
 *   arhud_server_destroy(srv)
 *
 * 编译：make  （见 Makefile，链接 libvsomeip3）
 */
#ifndef ARHUD_SERVER_H
#define ARHUD_SERVER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 不透明句柄 */
typedef struct arhud_server arhud_server_t;

/*
 * 创建服务端。unicast=本机IP；config_path=NULL 时自动生成内置配置（11 服务/23 事件）。
 * 返回 NULL 表示失败。
 */
arhud_server_t* arhud_server_create(const char* unicast, const char* config_path);

/* 销毁（停止并释放） */
void arhud_server_destroy(arhud_server_t* srv);

/*
 * 动态添加服务/事件（覆盖内置注册表；create 后、start 前调用）。
 * 返回 0 成功，-1 失败。
 */
int arhud_server_add_service(arhud_server_t* srv, uint16_t service, uint16_t instance,
                             uint16_t port, uint16_t major, uint16_t minor);
int arhud_server_add_event(arhud_server_t* srv, uint16_t service, uint16_t instance,
                           uint16_t event, uint16_t group);

/* 启动：offer 所有服务/事件 + app->start()（内部后台线程）。返回 0 成功。 */
int arhud_server_start(arhud_server_t* srv);
void arhud_server_stop(arhud_server_t* srv);

/*
 * 发送一个事件（原始字节载荷）。service=服务ID，event=事件ID。
 * 返回 0 成功，-1 失败（未启动/未知服务事件）。
 */
int arhud_server_notify(arhud_server_t* srv, uint16_t service, uint16_t event,
                        const uint8_t* data, uint32_t len);

/*
 * pcap 回放（后台线程，自动做 SOME/IP-TP 分片重组）。
 * pcap_path: pcap 文件；loop: 1=循环；interval_ms: 每条之间的间隔毫秒。
 * 返回 0 成功（已解析 pcap），-1 失败。
 */
int arhud_server_replay_start(arhud_server_t* srv, const char* pcap_path,
                              int loop, uint32_t interval_ms);
void arhud_server_replay_stop(arhud_server_t* srv);
/* 已回放条数（供 Python 轮询） */
uint64_t arhud_server_replay_sent(arhud_server_t* srv);

/* 订阅状态回调（可选）：subscribed=1 订阅，0 退订 */
typedef void (*arhud_subscribe_cb)(void* ctx, uint16_t service, uint16_t instance,
                                   uint16_t eventgroup, uint16_t event, int subscribed);
void arhud_server_set_subscribe_cb(arhud_server_t* srv, arhud_subscribe_cb cb, void* ctx);

/* ---- 序列化工具 ---- */

/* 标准 CRC32（与客户端 Checksum 语义一致：CRC32(payload[4:]) 写入前 4 字节） */
uint32_t arhud_crc32(const uint8_t* data, uint32_t len);

/* 大端打包帮助：把值按大端写入 out 并返回写入字节数 */
uint32_t arhud_pack_u8(uint8_t* out, uint8_t v);
uint32_t arhud_pack_u16(uint8_t* out, uint16_t v);
uint32_t arhud_pack_u32(uint8_t* out, uint32_t v);
uint32_t arhud_pack_u64(uint8_t* out, uint64_t v);
uint32_t arhud_pack_f32(uint8_t* out, float v);
uint32_t arhud_pack_f64(uint8_t* out, double v);

#ifdef __cplusplus
}
#endif

#endif /* ARHUD_SERVER_H */
