/*
 * vci_stub.c —— ZLG **VCI 接口** 驱动桩库（仅用于验证，不含任何真实硬件逻辑）
 * ==========================================================================
 * 用途：在容器里编译成 libusbcanfd_stub.so，让 HudAutoTest 的
 *       `can_core.vci_adapter.VciCanDriver` 走**真实的 ctypes/dlopen 路径**：
 *       结构体布局、函数调用约定、字节序、指针参数全部按真实 ABI 传递，
 *       从而在没有 ZLG 硬件的环境里验证「VCI → ZCAN 调用面」的翻译是否正确。
 *
 * 结构体布局严格对齐随仓库分发的官方头文件
 *   thirdparty/zlg_can/include/usbcanfd/zcan.h（ZCAN_MSG_HDR / ZCAN_20_MSG /
 *   ZCAN_FD_MSG / ZCAN_INIT / ZCAN_DEV_INF / ZCAN_STAT / ZCANDataObj）
 * 若 Python 侧的 ctypes 布局与该头文件不一致，本桩库回环回来的字段就会错乱，
 * 测试会立刻失败 —— 这正是本桩库的价值。
 *
 * 编译（容器内，gcc）：
 *   gcc -shared -fPIC -O2 -o libusbcanfd_stub.so vci_stub.c
 *
 * 行为约定（桩）：
 *   · 打开/初始化/启动/关闭一律成功（返回 1）
 *   · 发送即回环：VCI_Transmit* 把帧塞进对应通道的接收队列（标记为"已发送帧"）
 *   · VCI_Receive* 从队列取出；VCI_GetReceiveNum 返回队列长度
 *   · VCI_SetReference 记录 (port, ref, value) 供测试断言；SETREF_SET_DEVICE_NAME(12)
 *     会把字符串记下来，供 GETREF_GET_DEVICE_NAME(13) 读回
 *   · VCI_InitCAN 记录最后一次 ZCAN_INIT，供测试校验波特率时序换算
 *   · vci_stub_* 系列导出仅用于测试自省（真实驱动不存在这些符号）
 */
#include <stdint.h>
#include <string.h>

#define EXPORT __attribute__((visibility("default")))

#define VCI_STATUS_OK 1
#define VCI_STATUS_ERR 0

#define MAX_PORTS 8
#define QUEUE_LEN 64
#define REF_LOG_LEN 64
#define NAME_LEN 64

/* ---- 与 zcan.h 对齐的结构体 ---- */
typedef struct {
    uint32_t ts;
    uint32_t id;
    uint32_t inf;      /* 位域：txm[0:4] fmt[4:8] sdf[8] sef[9] err[10] brs[11]
                          est[12] tx[13] echo[14] qsend_100us[15] qsend[16] */
    uint16_t pad;
    uint8_t chn;
    uint8_t len;
} ZCAN_MSG_HDR;

typedef struct { ZCAN_MSG_HDR hdr; uint8_t dat[8]; } ZCAN_20_MSG;
typedef struct { ZCAN_MSG_HDR hdr; uint8_t dat[64]; } ZCAN_FD_MSG;
typedef struct { ZCAN_MSG_HDR hdr; uint8_t dat[8]; } ZCAN_ERR_MSG;

/* `inf` 是位域（见 zcan.h）：bit13 = tx（发送帧），bit14 = echo（回显帧） */
#define ZCAN_INF_TX_BIT   13u
#define ZCAN_INF_ECHO_BIT 14u
#define SET_INF_BIT(hdr, bit) ((hdr).inf |= (1u << (bit)))

typedef struct { uint8_t tseg1, tseg2, sjw, smp; uint16_t brp; } ZCAN_TIMING_SEG;
typedef struct {
    uint32_t clk;
    uint32_t mode;
    ZCAN_TIMING_SEG aset;
    ZCAN_TIMING_SEG dset;
} ZCAN_INIT;

typedef struct {
    uint16_t hwv, fwv, drv, api, irq;
    uint8_t chn;
    uint8_t sn[20];
    uint8_t id[40];
    uint16_t pad[4];
} ZCAN_DEV_INF;

typedef struct {
    uint8_t IR, MOD, SR, ALC, ECC, EWL, RXE, TXE;
    uint32_t PAD;
} ZCAN_STAT;

typedef struct {
    uint8_t dataType;
    uint8_t chnl;
    uint16_t flag;
    uint8_t extraData[4];
    union { ZCAN_20_MSG can; ZCAN_FD_MSG fd; ZCAN_ERR_MSG err; uint8_t raw[92]; } data;
} ZCANDataObj;

/* ---- 桩内部状态 ---- */
static ZCAN_20_MSG g_can_q[MAX_PORTS][QUEUE_LEN];
static int g_can_n[MAX_PORTS];
static ZCAN_FD_MSG g_fd_q[MAX_PORTS][QUEUE_LEN];
static int g_fd_n[MAX_PORTS];
static ZCANDataObj g_merge_q[QUEUE_LEN];
static int g_merge_n;

static ZCAN_INIT g_last_init[MAX_PORTS];
static uint32_t g_init_seen[MAX_PORTS];

static struct { uint32_t port, code, value; } g_refs[REF_LOG_LEN];
static int g_ref_n;
static char g_dev_name[NAME_LEN];

static uint32_t g_ts = 1000;

EXPORT void vci_stub_reset(void)
{
    memset(g_can_n, 0, sizeof(g_can_n));
    memset(g_fd_n, 0, sizeof(g_fd_n));
    g_merge_n = 0;
    memset(g_init_seen, 0, sizeof(g_init_seen));
    memset(g_refs, 0, sizeof(g_refs));
    g_ref_n = 0;
    memset(g_dev_name, 0, sizeof(g_dev_name));
    g_ts = 1000;
}

/* ---------------- 自省接口（测试用） ---------------- */
EXPORT int vci_stub_ref_count(void) { return g_ref_n; }
EXPORT uint32_t vci_stub_ref_port(int i) { return (i >= 0 && i < g_ref_n) ? g_refs[i].port : 0xFFFFFFFFu; }
EXPORT uint32_t vci_stub_ref_code(int i) { return (i >= 0 && i < g_ref_n) ? g_refs[i].code : 0xFFFFFFFFu; }
EXPORT uint32_t vci_stub_ref_value(int i) { return (i >= 0 && i < g_ref_n) ? g_refs[i].value : 0xFFFFFFFFu; }
EXPORT int vci_stub_init_seen(uint32_t port) { return (port < MAX_PORTS) ? (int)g_init_seen[port] : 0; }
EXPORT int vci_stub_get_init(uint32_t port, void *out)
{
    if (port >= MAX_PORTS || out == NULL) return 0;
    memcpy(out, &g_last_init[port], sizeof(ZCAN_INIT));
    return 1;
}
EXPORT const char *vci_stub_name(void) { return g_dev_name; }
EXPORT uint32_t vci_stub_version(void) { return 0x00010000; }

/* ---------------- 设备与通道 ---------------- */
EXPORT uint32_t VCI_OpenDevice(uint32_t type, uint32_t card, uint32_t reserved)
{
    (void)type; (void)card; (void)reserved;
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_CloseDevice(uint32_t type, uint32_t card)
{
    (void)type; (void)card;
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_InitCAN(uint32_t type, uint32_t card, uint32_t port, ZCAN_INIT *init)
{
    (void)type; (void)card;
    if (port >= MAX_PORTS || init == NULL) return VCI_STATUS_ERR;
    g_last_init[port] = *init;
    g_init_seen[port] = 1;
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_StartCAN(uint32_t type, uint32_t card, uint32_t port)
{
    (void)type; (void)card; (void)port;
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_ResetCAN(uint32_t type, uint32_t card, uint32_t port)
{
    (void)type; (void)card; (void)port;
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_ClearBuffer(uint32_t type, uint32_t card, uint32_t port)
{
    (void)type; (void)card;
    if (port < MAX_PORTS) { g_can_n[port] = 0; g_fd_n[port] = 0; }
    g_merge_n = 0;
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_GetReceiveNum(uint32_t type, uint32_t card, uint32_t port)
{
    (void)type; (void)card;
    if (port >= MAX_PORTS) return 0;
    return (uint32_t)(g_can_n[port] + g_fd_n[port]);
}

EXPORT uint32_t VCI_ReadBoardInfo(uint32_t type, uint32_t card, ZCAN_DEV_INF *info)
{
    (void)type; (void)card;
    if (info == NULL) return VCI_STATUS_ERR;
    memset(info, 0, sizeof(*info));
    info->hwv = 0x0102;
    info->fwv = 0x0304;
    info->drv = 0x0506;
    info->api = 0x0708;
    info->irq = 0;
    info->chn = 2;
    memcpy(info->sn, "STUB-SN-0001", 12);
    memcpy(info->id, "USBCANFD-STUB", 13);
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_ReadErrInfo(uint32_t type, uint32_t card, uint32_t port, ZCAN_ERR_MSG *err)
{
    (void)type; (void)card; (void)port;
    if (err) memset(err, 0, sizeof(*err));
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_ReadCANStatus(uint32_t type, uint32_t card, uint32_t port, ZCAN_STAT *stat)
{
    (void)type; (void)card; (void)port;
    if (stat) memset(stat, 0, sizeof(*stat));
    return VCI_STATUS_OK;
}

/* ---------------- 引用（配置） ---------------- */
EXPORT uint32_t VCI_SetReference(uint32_t type, uint32_t card, uint32_t port,
                                 uint32_t ref, void *data)
{
    (void)type; (void)card;
    uint32_t value = 0;
    if (ref == 12 && data != NULL) {                 /* SETREF_SET_DEVICE_NAME */
        strncpy(g_dev_name, (const char *)data, NAME_LEN - 1);
        value = 0;
    } else if (data != NULL) {
        value = *(uint32_t *)data;                   /* 其余引用码传的是 uint32* */
    }
    if (g_ref_n < REF_LOG_LEN) {
        g_refs[g_ref_n].port = port;
        g_refs[g_ref_n].code = ref;
        g_refs[g_ref_n].value = value;
        g_ref_n++;
    }
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_GetReference(uint32_t type, uint32_t card, uint32_t port,
                                 uint32_t ref, void *data)
{
    (void)type; (void)card; (void)port;
    if (ref == 13 && data != NULL) {                 /* GETREF_GET_DEVICE_NAME */
        strncpy((char *)data, g_dev_name, NAME_LEN - 1);
        return VCI_STATUS_OK;
    }
    if (data != NULL) *(uint32_t *)data = 0;
    return VCI_STATUS_OK;
}

EXPORT uint32_t VCI_Debug(uint32_t level)
{
    (void)level;
    return VCI_STATUS_OK;
}

/* ---------------- 收发（回环） ---------------- */
EXPORT uint32_t VCI_Transmit(uint32_t type, uint32_t card, uint32_t port,
                             ZCAN_20_MSG *data, uint32_t count)
{
    (void)type; (void)card;
    if (port >= MAX_PORTS || data == NULL) return 0;
    uint32_t sent = 0;
    for (uint32_t i = 0; i < count && g_can_n[port] < QUEUE_LEN; i++) {
        ZCAN_20_MSG msg = data[i];
        msg.hdr.ts = g_ts++;
        SET_INF_BIT(msg.hdr, ZCAN_INF_TX_BIT);       /* 回环帧标记为发送帧 */
        msg.hdr.chn = (uint8_t)port;
        g_can_q[port][g_can_n[port]++] = msg;
        sent++;
    }
    return sent;
}

EXPORT uint32_t VCI_TransmitFD(uint32_t type, uint32_t card, uint32_t port,
                               ZCAN_FD_MSG *data, uint32_t count)
{
    (void)type; (void)card;
    if (port >= MAX_PORTS || data == NULL) return 0;
    uint32_t sent = 0;
    for (uint32_t i = 0; i < count && g_fd_n[port] < QUEUE_LEN; i++) {
        ZCAN_FD_MSG msg = data[i];
        msg.hdr.ts = g_ts++;
        SET_INF_BIT(msg.hdr, ZCAN_INF_TX_BIT);
        msg.hdr.chn = (uint8_t)port;
        g_fd_q[port][g_fd_n[port]++] = msg;
        sent++;
    }
    return sent;
}

EXPORT uint32_t VCI_Receive(uint32_t type, uint32_t card, uint32_t port,
                            ZCAN_20_MSG *data, uint32_t count, uint32_t time)
{
    (void)type; (void)card; (void)time;
    if (port >= MAX_PORTS || data == NULL) return 0;
    uint32_t got = 0;
    while (got < count && g_can_n[port] > 0) {
        data[got++] = g_can_q[port][0];
        for (int i = 1; i < g_can_n[port]; i++) g_can_q[port][i - 1] = g_can_q[port][i];
        g_can_n[port]--;
    }
    return got;
}

EXPORT uint32_t VCI_ReceiveFD(uint32_t type, uint32_t card, uint32_t port,
                              ZCAN_FD_MSG *data, uint32_t count, uint32_t time)
{
    (void)type; (void)card; (void)time;
    if (port >= MAX_PORTS || data == NULL) return 0;
    uint32_t got = 0;
    while (got < count && g_fd_n[port] > 0) {
        data[got++] = g_fd_q[port][0];
        for (int i = 1; i < g_fd_n[port]; i++) g_fd_q[port][i - 1] = g_fd_q[port][i];
        g_fd_n[port]--;
    }
    return got;
}

EXPORT uint32_t VCI_TransmitData(uint32_t type, uint32_t card, uint32_t port,
                                 ZCANDataObj *data, uint32_t count)
{
    (void)type; (void)card; (void)port;
    if (data == NULL) return 0;
    uint32_t sent = 0;
    for (uint32_t i = 0; i < count && g_merge_n < QUEUE_LEN; i++) {
        ZCANDataObj obj = data[i];
        obj.data.fd.hdr.ts = g_ts++;
        SET_INF_BIT(obj.data.fd.hdr, ZCAN_INF_TX_BIT);
        g_merge_q[g_merge_n++] = obj;
        sent++;
    }
    return sent;
}

EXPORT uint32_t VCI_ReceiveData(uint32_t type, uint32_t card, uint32_t port,
                                ZCANDataObj *data, uint32_t count, uint32_t time)
{
    (void)type; (void)card; (void)port; (void)time;
    if (data == NULL) return 0;
    uint32_t got = 0;
    while (got < count && g_merge_n > 0) {
        data[got++] = g_merge_q[0];
        for (int i = 1; i < g_merge_n; i++) g_merge_q[i - 1] = g_merge_q[i];
        g_merge_n--;
    }
    return got;
}
