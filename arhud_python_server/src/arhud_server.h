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
 * pcap 回放（后台线程，流式解析 + SOME/IP-TP 自动重组）。
 * pcap_path: pcap 文件；loop: 1=循环；interval_ms: 每条之间的间隔毫秒。
 * 返回 0 成功（已解析 pcap），-1 失败。
 * 注：需要"按抓包原始节奏回放 / 多文件 / 限速倍速 / 限轮数"时用下面的 _ex 版本。
 */
int arhud_server_replay_start(arhud_server_t* srv, const char* pcap_path,
                              int loop, uint32_t interval_ms);

/*
 * 回放选项（_ex 接口）。字段含义见注释；先用 arhud_replay_opts_default() 取默认值再改。
 */
typedef struct arhud_replay_opts {
    int      loop;            /* 0/1，是否循环回放 */
    int      timing;          /* 0 = 固定间隔(interval_ms)；1 = 按 pcap 抓包时间戳 */
    uint32_t interval_ms;     /* timing=0 时每条之间的间隔毫秒 */
    double   speed;           /* timing=1 时的倍速：2.0 = 两倍速，<=0 视为 1.0 */
    uint32_t max_loops;       /* 最大轮数，0 = 不限 */
    uint32_t start_delay_ms;  /* 起播前等待毫秒（等客户端订阅稳定） */
    int      log_every;       /* >0 时每 N 条打印一行进度（调试用） */
} arhud_replay_opts;

void arhud_replay_opts_default(arhud_replay_opts* opts);

/*
 * 多文件/目录回放（目录由调用方展开成文件列表，按传入顺序回放）。
 * paths: 文件路径数组；n_paths: 个数；opts: NULL 时用默认（循环 + 10ms 固定间隔）。
 * 返回 0 成功，-1 失败（含打不开文件）。
 */
int arhud_server_replay_start_ex(arhud_server_t* srv, const char* const* paths, int n_paths,
                                 const arhud_replay_opts* opts);

void arhud_server_replay_stop(arhud_server_t* srv);
/* 回放计数：sent = 真正发送成功（notify 返回 0）；attempted = 已尝试发布的条数；
 * parsed = 从 pcap 读到的消息数（= attempted）；两者差值 = 发送失败的条数。
 * unregistered = 服务表里没有的事件（默认仍会尝试发布，与参考实现一致）。 */
uint64_t arhud_server_replay_sent(arhud_server_t* srv);
uint64_t arhud_server_replay_attempted(arhud_server_t* srv);
uint64_t arhud_server_replay_parsed(arhud_server_t* srv);
uint64_t arhud_server_replay_unregistered(arhud_server_t* srv);
int arhud_server_replay_running(arhud_server_t* srv);

/*
 * 回放报告（JSON）：总数 + 逐 (service,event) 的 attempted/sent/unregistered。
 * 写入 buf（含结尾 0），返回写入长度；buf 太小返回 -1。
 */
int arhud_server_replay_report(arhud_server_t* srv, char* buf, uint32_t buflen);

/*
 * 回放前体检：扫一组 pcap，返回出现过的 (service,event) 与条数（JSON 写入 buf）。
 * 不需要服务端句柄，也不发送任何数据。返回写入长度，-1 失败。
 */
int arhud_pcap_events(const char* const* paths, int n_paths, char* buf, uint32_t buflen);
/* 最近一次 pcap 相关调用的错误信息（静态缓冲，失败后调用） */
const char* arhud_pcap_error(void);
/* 内部：记录错误信息（由各服务端实现调用；定义在 arhud_replay.cpp） */
void arhud_set_last_error(const char* msg);

/*
 * 服务表导出：profile=NULL/空 时用环境变量 ARHUD_SERVICE_PROFILE（默认 old）。
 * 返回 JSON（写入 buf），-1 表示 buf 太小。
 */
int arhud_profile_events(const char* profile, char* buf, uint32_t buflen);
/* 当前环境变量归一化后的服务表代（old / old-capture / bplus） */
const char* arhud_profile_name(void);

/* 服务表代诊断：old（11 服务/23 事件）/ bplus（6 服务/38 事件），由 ARHUD_SERVICE_PROFILE 选择 */
const char* arhud_server_profile(arhud_server_t* srv);
int arhud_server_service_count(arhud_server_t* srv);
int arhud_server_event_count(arhud_server_t* srv);

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
