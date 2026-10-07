# 代码详解：arhud_python_server —— 以 C++ 为通信库的 SOME/IP 服务端

> 面向**开发者**：本文把整个项目从架构到每一行关键逻辑讲清楚，让新接手的人能快速上手、
> 能扩展、能排障。配套文档：`README.md`（快速开始）、`DEPLOYMENT.md`（部署）、
> `WINDOWS.md`（Windows）、`FIXED_CONFIG_SOLUTION.md`（仓库根，架构背景）。

---

## 目录

1. [项目定位](#1-项目定位)
2. [通信原理（30 秒版）](#2-通信原理30-秒版)
3. [代码结构总览](#3-代码结构总览)
4. [逐模块详解](#4-逐模块详解)
   - 4.1 C 接口层 `arhud_server.h`
   - 4.2 SP 分支服务端内核 `arhud_server_sp.cpp`
   - 4.3 配置自动生成
   - 4.4 pcap 解析与 TP 重组 `arhud_pcap.cpp`
   - 4.5 数据结构序列化 `arhud_types.cpp`
   - 4.6 Python ctypes 封装 `arhud_py.py`
   - 4.7 示例 `demo_struct.py` / `demo_replay.py`
5. [数据流全景](#5-数据流全景)
6. [二次开发指南](#6-二次开发指南)
7. [构建与验证](#7-构建与验证)
8. [常见问题与坑](#8-常见问题与坑)

---

## 1. 项目定位

**一句话**：把 SOME/IP 服务端封装成 **C++ 共享库（通信内核）**，Python 通过 ctypes 调用
做业务编排（指定 pcap 回放、对数据结构赋值组包），让**板端已烧录的客户端**订阅并收到数据。

**三个关键设计决策**：

| 决策 | 原因 |
|------|------|
| C++ 做通信内核 | SOME/IP/vsomeip 是 C++ 生态；协议栈（SP 分支）是 C++ 库 |
| 导出 **C 接口**（extern "C"） | Python ctypes / 其他语言可直接调用；C ABI 跨版本稳定 |
| 用 **SP 分支协议栈**（与板端 C++ 服务端一致） | 避免标准 vsomeip 与 SP 分支的兼容性问题；行为与原始部署完全一致 |

**与板端 C++ 服务端（`hud_pcap_huifang_server`）的关系**：
本项目的 C++ 库就是它的"库化"版本——用同一协议栈（`libsomeip.so`）、同一 C 接口
（`SPInit/SPStart/SPServerSendNotify`），但把"读 pcap 回放"和"数据生成"交还给 Python 编排。

---

## 2. 通信原理（30 秒版）

SOME/IP 的订阅-通知模型（本项目用到的最小集）：

```
服务端(本 C++ 库)                       客户端(板端已烧录)
  offer_service(0x000A, major=1)  ──SD多播──►  订阅 0x000A/0x8001(组0x1101)
  offer_event(0x8001, 组0x1101)              ◄──SubscribeEventGroup──
  SUBSCRIBE ACK ──────────────────────────────►
  notify(0x000A, 0x8001, 载荷) ──UDP事件───►  回调收到载荷
```

- **服务/实例/事件/事件组**：服务（0x000A 等）下有实例；事件（0x8001 等）归入事件组
  （0x1101 等）；客户端订阅"事件组"即收到组内所有事件。
- **major 版本**：客户端按 major=1 订阅，服务端必须 offer major=1，否则 NACK。
- **SD（Service Discovery）**：多播 `224.0.2.4:30490`，负责 offer/find/subscribe/ack。
- **someip-tp**：大载荷（>1400B）自动分片为多个 SOME/IP-TP 段，接收端重组。
- **Checksum**：本工程载荷首 4 字节 = CRC32(载荷[4:])（与板端约定一致）。

---

## 3. 代码结构总览

```
arhud_python_server/
├── src/                          # ★ C++ 通信库源码
│   ├── arhud_server.h            #   C 接口（ctypes 绑定的边界）
│   ├── arhud_server_sp.cpp       #   ★ SP 分支服务端内核（主）
│   ├── arhud_server.cpp          #   标准 vsomeip 版内核（备用）
│   ├── arhud_pcap.h/.cpp         #   ★ 流式 pcap 解析 + SOME/IP-TP 重组（去重/乱序/缺口）
│   ├── arhud_replay.h/.cpp       #   ★ 回放引擎（多文件、capture/interval、倍速、限轮、统计）
│   ├── arhud_services.h          #   ★ 服务表唯一来源（old / old-capture / bplus）
│   ├── arhud_types.h/.cpp        #   数据结构 + 大端序列化 + CRC32
│   ├── Makefile                  #   Linux 构建（SP 库链接）
│   └── include/vsomeip/someip_com.h  # SP 分支 C 接口声明
├── CMakeLists.txt                # 跨平台构建（Windows/Linux、SP/标准）
├── python/                       # ★ Python 业务层
│   ├── arhud_py.py               #   ctypes 封装（ArHudServer 类）
│   ├── demo_struct.py            #   示例：结构化赋值 → 发送
│   └── demo_replay.py            #   示例：文件/目录回放（节奏/倍速/体检/报告）
├── tools/                        # ★ 自测与体检工具
│   ├── analyze_pcap.py           #   纯 Python 体检（解析器的独立对照实现）
│   ├── pcap_selftest.cpp         #   C++ 解析器自测（无需协议栈）
│   ├── replay_selftest.cpp       #   回放引擎自测（假发送器）
│   ├── dryrun_server.cpp         #   演练版库（不联网跑通 Python 全链路）
│   ├── local_selftest.sh         #   本机一键自测
│   └── container_replay_test.sh  #   容器内用真实 SP 协议栈编译并回放
├── libs/                         # SP 分支库依赖
│   ├── arm64/                    #   aarch64（lib_bst_t517）
│   └── x86_64/                   #   x86_64（build_package.sh 从 zip 提取）
├── config/                       # SP 分支配置模板
├── build_package.sh              # 一键组装自包含部署包
├── PCAP_REPLAY.md                # ★ pcap 回放与发布指南
└── *.md                          # 文档
```

**分层关系**：

```
┌───────────── Python 业务层（python/）─────────────┐
│  组装载荷、选 pcap、启动/停止、业务逻辑            │
└──────────────────────┬────────────────────────────┘
                       │ ctypes（C ABI）
┌───────────── C++ 通信库（src/，编译为 .so/.dll）──┐
│  arhud_server_sp: 生命周期 + 事件注册 + 发送       │
│  arhud_pcap:     pcap → 消息列表（TP 重组）        │
│  arhud_types:    结构体 → 字节（大端 + CRC32）     │
└──────────────────────┬────────────────────────────┘
                       │ 链接 libsomeip.so（SP 分支）
┌───────────── SOME/IP 协议栈 + 网络 ───────────────┐
│  SD 多播 224.0.2.4:30490 / UDP 事件 51400-52001   │
└────────────────────────────────────────────────────┘
```

---

## 4. 逐模块详解

### 4.0 服务表 `src/arhud_services.h`（唯一来源）

三代服务表与 profile 参数（应用 id、线程数、日志路径）都在这里：

| profile | 规模 | 说明 |
|---------|------|------|
| `old`（默认） | 11 服务 / 23 事件 | 与 `old/someip_arhud01_pcap_server.json` 逐条一致 |
| `old-capture` | 11 服务 / 33 事件 | `old` + 抓包实测的 10 个事件（完整回放 `old/` 下 pcap 用） |
| `bplus` | 6 服务 / 38 事件 | 与 `BPlus/someip_arhud01_pcap_server_B+.json` 一致 |

SP 版与标准版都通过 `arhud::services_for(profile)` 取表，`arhud::profile_from_env()` 读
`ARHUD_SERVICE_PROFILE`（默认 old，详见 `PCAP_REPLAY.md` §3）。表里还提供两个小工具：
`has_event()`（覆盖判断）与 `services_json()`（导出给 Python 核对）。
**改服务表只改这一处**，避免两版各改一半。

### 4.1 C 接口层 `src/arhud_server.h`

**为什么是 C 接口**：ctypes 只能绑定 C ABI；C 接口在版本迭代中稳定，Python 封装不用跟着改。

**核心 API**：

```c
typedef struct arhud_server arhud_server_t;   // 不透明句柄

arhud_server_t* arhud_server_create(const char* unicast, const char* config_path);
int  arhud_server_start(arhud_server_t* srv);
int  arhud_server_notify(arhud_server_t* srv, uint16_t service, uint16_t event,
                         const uint8_t* data, uint32_t len);        // 发一个事件
int  arhud_server_replay_start(arhud_server_t* srv, const char* pcap_path,
                               int loop, uint32_t interval_ms);      // 回放 pcap（单文件+固定间隔）
// 多文件/目录 + 按抓包时间戳 + 倍速 + 限轮 + 起播延迟（推荐）：
void arhud_replay_opts_default(arhud_replay_opts* o);
int  arhud_server_replay_start_ex(arhud_server_t* srv, const char* const* paths,
                                  int n_paths, const arhud_replay_opts* o);
uint64_t arhud_server_replay_parsed(arhud_server_t* srv);            // 读到的条数
uint64_t arhud_server_replay_sent(arhud_server_t* srv);              // 发布成功条数
uint64_t arhud_server_replay_unregistered(arhud_server_t* srv);      // 服务表外的事件条数
int  arhud_server_replay_report(arhud_server_t* srv, char* buf, uint32_t buflen);  // JSON 报告
// pcap 体检 / 服务表导出（不需要句柄）：
int  arhud_pcap_events(const char* const* paths, int n, char* buf, uint32_t len);
int  arhud_profile_events(const char* profile, char* buf, uint32_t len);
const char* arhud_pcap_error(void);
void arhud_server_stop(arhud_server_t* srv);
void arhud_server_destroy(arhud_server_t* srv);
// 动态注册（默认内置服务表，一般不需要）：
int  arhud_server_add_service(...);  int  arhud_server_add_event(...);
// 序列化工具：
uint32_t arhud_crc32(const uint8_t*, uint32_t);
uint32_t arhud_pack_u8/u16/u32/u64/f32/f64(uint8_t* out, ...);       // 大端写入
```

**用法骨架**（Python 侧最终都会走到这里）：

```c
arhud_server_t* srv = arhud_server_create("192.168.1.10", NULL);  // NULL=自动生成配置
arhud_server_start(srv);                                          // offer 23/33 事件 + SPStart
arhud_server_notify(srv, 0x000A, 0x8001, payload, len);           // 发送
arhud_server_replay_start(srv, "out.pcap", 1, 10);                // 回放（老接口）
arhud_replay_opts o; arhud_replay_opts_default(&o);
o.timing = 1; o.speed = 1.0;                                      // 按抓包节奏
arhud_server_replay_start_ex(srv, paths, n, &o);                  // 多文件/目录回放
arhud_server_destroy(srv);
```

### 4.2 SP 分支服务端内核 `src/arhud_server_sp.cpp`（主）

**生命周期**：`create → start → notify/replay → stop → destroy`

**① create：初始化 SP 栈 + 自动生成配置**

```cpp
SPInstance spi;
SPInit(&spi, "", cfg_path);          // SP 栈初始化（读取 SP 分支格式配置）
```

`SPInit` 需要配置文件。`config_path=NULL` 时由 `gen_sp_config()` 自动生成
（写临时文件，Linux `/tmp/`、Windows `GetTempPathA()`）。配置内容 = **SP 分支格式**
（与板端 `someip_arhud01_pcap_server.json` 同款）：11 个服务、端口、major=1、事件组、
someip-tp（0x000C/0x010A 大消息）。

**② start：注册事件 + 启动**

```cpp
for (service : services)
    for (event : service.events)
        SPServerNotifyCallbackFuncRegist(&spi, svc, inst, event, group, sp_notify_cb, NULL);
SPStart(&spi);          // SP 栈自动 offer 配置里的所有服务
```

- 注册回调是占位（数据由 `SPServerSendNotify` 主动发送，回调 `*len=0` 表示不周期发送）；
- `SPStart` 内部会按配置 offer 服务并启动 SD（多播宣告）。

**③ notify：发送一个事件**

```cpp
int arhud_server_notify(...) {
    uint16_t inst = instance_of(service, event);   // 0x010A → 0x0001，其余 = service
    return SPServerSendNotify(&spi, service, inst, event, data, len);
}
```

**关键映射**：`instance_of` 表——0x010A 服务的实例是 0x0001（不是 0x010A），其他服务
实例 = 服务 ID。这张表在 create 时从注册表构建。

**④ replay：pcap 回放（后台线程，交给 `arhud::ReplayEngine`）**

```cpp
arhud::ReplayOptions opt;                     // loop / timing / interval_ms / speed / max_loops / start_delay_ms
srv->replay.start(paths, opt,
    [srv](svc, ev, data, len) { return arhud_server_notify(srv, svc, ev, data, len); },
    [srv](svc, ev) { return srv->has_event(svc, ev); });   // 用于统计"表外事件"
```

引擎（`src/arhud_replay.cpp`）负责：流式读 pcap → 按节奏发布 → 逐事件统计。
**服务端实现里不再有回放线程代码**，SP 版与标准版共用同一份（详见 §4.4.1）。

**内置服务注册表**（`arhud_services.h` 的 `services_old()`）：11 服务 / 23 事件，与板端客户端配置一一对应：

| 服务 | 实例 | 端口 | 事件（组） |
|------|------|------|-----------|
| 0x000A | 0x000A | 51400 | 8001(1101) |
| 0x000B | 0x000B | 51401 | 8001(1101), 8002(1101) |
| 0x000C | 0x000C | 51402 | 8001/8002/8003(1101) + **someip-tp** |
| 0x000D | 0x000D | 51403 | 8001-8005(1101) |
| 0x000E | 0x000E | 51404 | 8001(1101), 8002(1102), 8003(1103) |
| 0x010A | **0x0001** | 52001 | 8001-8004(1101) + **someip-tp** |
| 0x0007/0x0017/0x002B/0x8202/0x0018 | =服务 | 51405-51409 | 各 1-2 个事件 |

### 4.3 配置自动生成 `gen_sp_config`

生成的 vsomeip 配置与参考实现对齐：`applications[0].id` 按 profile（old `0x1001` / bplus `0x1443`）、
`max_dispatchers`/`threads`、`max-payload-size-unreliable: 3000000`（大帧 TP 必需）、
日志键含 `dds_log_enable`/`dmesg_log_enable`。

### 4.2.1 注册与回放语义（2026-02 修正，2026-10 补充）

- `add_service/add_event` **幂等**：同 (service,instance) / (service,event) 只更新不追加，
  否则"内置表 + 调用方逐条注册"会膨胀成 22 服务/46 事件；
- `arhud_server_replay_parsed()` = 从 pcap 读到的条数；`..._sent()` = 发送接口返回 0 的条数；
  `..._unregistered()` = 不在服务表里的事件条数（**仍然会尝试发送**，与参考实现一致）。
  `parsed - sent` = 发送失败数；`unregistered > 0` 说明 profile 选小了（比如用 `old` 回放
  `old/out.pcap` 会有 187 条），换 `old-capture` 即可 —— 这是排查错配的第一指标；
- 真正的"数据发全了没有"看 `arhud_server_replay_report()`：逐 `(service,event)` 的
  attempted/sent/unregistered。


生成 SP 分支格式 JSON（与板端配置同结构），要点：
- `services[].unreliable`：服务端口；
- `services[].events[]`：每个事件的 name/event/is_field/is_reliable/notify-period；
- `services[].eventgroups[]`：事件 → 组映射（0x000E 三事件分三组）；
- `services[].someip-tp.service-to-client`：大消息分片（0x000C:8002/8003、0x010A:8001/8003）；
- `service-discovery`：`224.0.2.4:30490`。

> 若想用板端原配置，可把 `config/someip_arhud01_pcap_server.json`（unicast 改为本机 IP）
> 传给 `arhud_server_create(unicast, config_path)`。

### 4.4 pcap 解析与 TP 重组 `src/arhud_pcap.cpp`（2026-10 重写为流式）

**输入**：pcap 文件（Ethernet/VLAN/IPv4/UDP + SOME/IP）。
**输出**：`PcapStream::next()` 每次吐一条 `PcapMessage{service, event, ts_us, packet_index, fragments, payload}`。

```cpp
arhud::PcapStream s;
std::string err;
if (!s.open(path, &err)) { /* err 里有原因（pcapng / linktype / 打不开） */ }
arhud::PcapMessage m;
while (s.next(m) == 1) { /* 用 m 发布 */ }
const arhud::PcapStats& st = s.stats();   // 包数/通知/TP 分片/重复/丢弃/钳制…
```

解析流程：

```
Ethernet(14) ─ VLAN(0x8100/0x88A8/0x9100，每级 +4) ─ IPv4(20+opts) ─ UDP(8) ─ SOME/IP 头(16)
  SOME/IP 头: service(2) method(2) length(4) client(2) session(2) ver(1) iver(1) type(1) rc(1)
  type==0x02 → Notification：payload = length-8 字节（超过实收长度则钳制并计数）
  type==0x22 → TP 分片：TP头(4)= bit0 MoreSegments, bits1-31 字节偏移
     按 (service, method, session) 分组 → 按偏移缓存 → 连续段搬进缓冲 → More=0 时发布
  service==0xFFFF（SD）/ version!=1 → 跳过
```

**为什么重写**（与旧版的差异，都是被真实抓包打出来的）：

| 旧版 | 现在 |
|------|------|
| 整个文件的消息/分片全读进内存（260 MB 抓包峰值 300 MB+） | 流式：边扫边重组边吐，内存与"在途分片"成正比 |
| 分片按偏移排序后**无条件拼接** | 同偏移**去重**；重复尾巴（上一条已完成消息的分片签名匹配）也识别为重复 |
| 乱序到达会顺序错乱 | 按偏移缓存，缺口补齐后自然拼接；`More=0` 且仍有缺口 → **整条丢弃**（`tp_dropped++`），绝不发半截 |
| 没有时间戳 | 每条带 `ts_us`，供 `timing=capture` 按抓包节奏回放 |

**易错点（已踩过）**：
1. **字节序**：EtherType、IP、UDP、SOME/IP 头**恒为大端**（网络字节序），与 pcap 记录头
   （文件字节序）无关；pcap 文件头 magic 决定**记录头**字节序（`0xa1b2c3d4` 大端 / `0xd4c3b2a1` 小端，
   `0xa1b23c4d`/`0x4d3cb2a1` 是纳秒版本，纳秒要除以 1000 转成微秒）；
2. **TP 偏移单位是字节**（不是 SOME/IP 标准的 8 字节块）；
3. VLAN 标签会让 Ethernet 头变长（0x8100→18），漏掉则整包错位；
4. `length` 字段可能大于实收字节（抓包 snaplen 截断），**必须钳到实际长度**，否则越界读取。

### 4.4.1 回放引擎 `src/arhud_replay.h/.cpp`

协议栈无关，SP 版与标准版共用（`arhud_server_sp.cpp` / `arhud_server.cpp` 只提供
`Sender`（怎么发）与 `Registered`（在不在服务表里）两个回调）。

```cpp
struct ReplayOptions { bool loop; int timing; uint32_t interval_ms; double speed;
                       uint32_t max_loops, start_delay_ms; int log_every; };
enum  ReplayTiming { kTimingInterval = 0, kTimingCapture = 1 };
bool ReplayEngine::start(paths, opts, sender, registered, &err);
ReplaySnapshot ReplayEngine::snapshot();      // parsed/sent/failed/unregistered/逐事件
std::string    ReplayEngine::report_json();   // 报告（C 接口 arhud_server_replay_report）
static bool    ReplayEngine::scan_events(paths, events, &err);  // 回放前体检
```

节奏实现：
- `kTimingInterval`：每条之后 `sleep(interval_ms)`；
- `kTimingCapture`：以**每个文件的首条消息**为 0 点，`sleep` 到 `(ts - base_ts)/speed`。
  与参考实现 `hud_pcap_huifang_server.cpp` 的"按相邻包时间差 sleep"等价，但不受单次
  `sleep()` 粒度与文件间空档影响；休眠是**分片可中断**的（20 ms 一片），`stop()` 能立刻返回。
- 循环：每轮重新 `open()` 文件（不缓存消息），所以 260 MB 抓包循环回放内存也不涨。

统计口径（诊断三件套）：
`parsed`（读到的消息数）＝`sent`（发送接口返回 0）＋`failed`；
`unregistered`（服务表里没有该事件，默认仍会尝试发送，与参考实现一致）。

### 4.5 数据结构序列化 `src/arhud_types.cpp`

**职责**：C 结构体（`#pragma pack(1)`，与板端 `ArHudSomeipDataType.h` 布局一致）→ 大端字节流。

**已实现 9 种类型**：`RTK / IMU / ChangeLane / PilotStatus / PilotAlarm / Broadcast /
HudMappath / HudNavmap / VehiclePosition`。

**序列化约定**（与板端客户端 SPDeserialization 对齐，已字节级验证）：
- 所有多字节字段**大端**（`put_u16/u32/f32/f64`）；
- 载荷前 4 字节 = `Checksum`（占位 0），序列化完成后
  `Checksum = CRC32(payload[4:])`（`finalize_crc`）；
- 字符串格式：`长度(4, 含BOM) + UTF-8 BOM(3) + 内容`；
- 动态数组：`长度字段(字节数) + 元素`（如 VehiclePosition 的 `target_lane_id`）。

```cpp
int arhud_serialize_rtk(const arhud_rtk_t* s, uint8_t* out, uint32_t* out_len) {
    uint8_t* p = out;
    put_u32(p, 0); put_u16(p, s->Counter);          // Checksum 占位 + Counter
    put_u32(p, s->rtk_status);
    put_f64(p, s->longitude); ...                    // 依字段顺序
    *out_len = p - out;
    finalize_crc(out, *out_len);                     // 补 CRC32
    return 0;
}
```

### 4.6 Python ctypes 封装 `src/../python/arhud_py.py`

**职责**：把 C 接口包成 Python 类，让业务代码不用碰 ctypes 细节。

**三层结构**：
1. **ctypes 结构体**（`class RTK(ctypes.Structure)` 等）——与 C 结构体内存布局逐字段对应
   （`_pack_ = 1`）；
2. **C 函数绑定**（`_lib.arhud_server_create.restype = ...`）——声明参数/返回类型；
3. **ArHudServer 类**——高层 API：

```python
class ArHudServer:
    def __init__(self, unicast=None, config_path=None, profile=None)   # profile: old/old-capture/bplus
    # 类方法（不需要实例）
    @classmethod best_profile_for_pcaps(paths)  # → (profile, missing)
    @classmethod for_pcaps(paths, unicast=None) # 按 pcap 自动选表并创建
    @staticmethod pcap_events(paths)            # 扫 pcap → [(svc, ev), ...]
    @staticmethod profile_events(profile=None)  # 某表定义的全部 (svc, ev)
    # 实例
    def start(self) / stop(self) / close(self)
    def notify_raw(self, service, event, data: bytes)          # 原始字节发送
    def notify_fields(self, kind, counter=1, **fields)         # ★ 结构化赋值
    def replay(self, pcap_path, loop=True, interval_ms=10, timing="interval", speed=1.0,
               max_loops=0, start_delay_ms=0, log_every=0)     # 文件或目录
    def replay_dir(self, directory, pattern="*.pcap", loop=True, **kw)
    def replay_status(self) / replay_report(self) / replay_stop(self)
    def replay_running(self) / replay_sent(self)
```

模块级辅助：`pcap_events()` / `profile_events()` / `profile_name()` / `find_pcaps()`（目录 → 文件列表，`out.pcap` 优先）。

**`notify_fields` 做了什么**（结构化赋值 → 组包 → 发送的完整链路）：

```python
def notify_fields(self, kind, counter=1, **fields):
    st = RTK()                            # 1. 构造结构体
    for k, v in fields.items(): setattr(st, k, v)   # 2. 按字段赋值
    out = (c_uint8 * 4096)(); out_len = c_uint32(4096)
    ser(byref(st), out, byref(out_len))   # 3. 调 C++ 序列化（大端+CRC32）
    self.notify_raw(service, event, bytes(out[:out_len.value]))  # 4. 发送
```

**平台适配**：`_default_lib_name()` 按 `sys.platform` 选 `.so` / `.dll`；`ARHUD_LIB_PATH`
环境变量可覆盖库路径。

### 4.7 示例 `demo_struct.py` / `demo_replay.py`

**demo_struct.py**（结构化赋值发送）：每 1 秒一轮，对 RTK/IMU/Broadcast/PilotStatus/
PilotAlarm/ChangeLane/HudMappath/HudNavmap/VehiclePosition 赋值并发送，演示
`notify_fields` 的完整用法——这是"按功能需求对数据结构赋值"的标准模板。

**demo_replay.py**（pcap 回放/发布）：

```bash
python3 python/demo_replay.py <pcap文件|目录> [本机IP] \
    [--profile auto|old|old-capture|bplus] [--timing capture|interval] [--speed N] \
    [--interval-ms N] [--once|--loops N] [--delay S] [--analyze] [--list] [--report-json F]
```

`--analyze` 先打印"pcap 里的事件 vs 服务表"的覆盖情况；`--profile auto` 会自动挑一个能
全覆盖的最小表；跑完打印逐事件发布报告，可落盘 JSON。这是"目录回放 + 发布"的标准模板。

---

## 5. 数据流全景

```
① Python: srv.start()
     → C++: SPInit(生成配置) → SPServerNotifyCallbackFuncRegist(23/33事件) → SPStart
     → SP栈: 绑定端口 51400-51409/52001, 加入多播 224.0.2.4:30490, offer 11 服务(major=1)

② 客户端(板端)经中间件 SD 订阅
     → 中间件发送 SubscribeEventGroup(224.0.2.4)
     → SP栈: SUBSCRIBE ACK → 记录订阅者(中间件的 unicast:port)

③ Python: srv.notify_fields("RTK", longitude=..., ...)
     → ctypes → C++: arhud_serialize_rtk(结构体) → 大端字节 + CRC32
     → SPServerSendNotify(0x000B, 0x000B, 0x8001, payload, len)
     → SP栈: UDP 事件 → 中间件 → UDS → 客户端回调(SPDeserialization 显示字段)

④ Python: srv.replay("out.pcap", timing="capture")  /  srv.replay_dir(目录)
     → C++: ReplayEngine → PcapStream 流式解析 + TP 重组
            → 按抓包时间戳 sleep → SPServerSendNotify → 逐事件统计
     → Python: srv.replay_status() / srv.replay_report() 看"发全了没有"
```

---

## 6. 二次开发指南

### 6.1 新增一个数据结构类型（如 HudRoad）

1. **C 结构体**（`arhud_types.h`）：按 `ArHudSomeipDataType.h` 定义字段（`#pragma pack(1)`）；
2. **序列化函数**（`arhud_types.cpp`）：按字段顺序 `put_xxx` 写入，结尾 `finalize_crc`；
3. **Python 结构体**（`arhud_py.py`）：`class HudRoad(ctypes.Structure)` 逐字段对应；
4. **注册**：加入 `_SERIALIZERS` 和 `KIND_SERVICE_EVENT`（类型 → 服务/事件）；
5. 业务代码即可 `srv.notify_fields("HudRoad", ...)`。

### 6.2 新增一个服务/事件

1. `src/arhud_services.h` 的表里加一行（服务/实例/端口/事件/组）——**表只有这一处**，
   SP 版与标准版、`gen_sp_config()`、Python 侧的 `profile_events()` 都会跟着走；
2. 端口/事件组与板端客户端配置一致（否则订阅不匹配）；
3. 大消息事件（>1400B）在 `tp_events` 里登记（如 `"0x8003"`）；
4. 只想"多回放一批抓包里的事件"而不动正式表：仿照 `services_old_capture()` 加一个扩展
   profile（`old-capture` 就是这么来的：`old` + 抓包实测的 10 个事件）。

### 6.3 修改端口 / 事件组 / major

改 `arhud_services.h` 即可——配置文件由 `gen_sp_config()` 自动跟随。

### 6.4 业务逻辑（server.py 模式）

不要改 C++ 库；在 Python 里组合：

```python
from arhud_py import ArHudServer
srv = ArHudServer(unicast="192.168.1.10")
srv.start()
# 业务：条件触发结构化发送 / 回放不同 pcap / 按订阅状态切换数据源
if condition:
    srv.notify_fields("RTK", counter=n, longitude=..., ...)
else:
    srv.replay("data/backup.pcap", timing="interval", interval_ms=50)

# 或者：把一批抓包整个目录回放出去，先自动选表、再核对发全了没有
srv2 = ArHudServer.for_pcaps("/path/to/pcap_dir", unicast="192.168.1.10")
srv2.start()
srv2.replay_dir("/path/to/pcap_dir", timing="capture")
print(srv2.replay_report())
```

---

## 7. 构建与验证

```bash
# Linux（aarch64，默认内置 libs/arm64）
cd arhud_python_server/src && make libarhud_server.so
# x86_64：make libarhud_server.so SP_LIBS=../libs/x86_64
# 跨平台：cmake -B build-win -DBUILD_SP=ON -DSP_LIBS_DIR=...（Windows 见 WINDOWS.md）

# 验证（任选）
bash docker/integration_test_cpplib.sh                     # 双容器全链路（服务端库 + 真实客户端）
tools/local_selftest.sh <pcap目录>                          # 本机：解析/重组/引擎/Python 全链路
tools/container_replay_test.sh <pcap目录>                   # 容器：真实 SP 协议栈编译 + 回放
```

**验证指标**：客户端 `收<--` 行数增长、SIGINT 汇总表各事件计数、服务端 `Dropping to big
message` = 0；回放侧看 `replay_report()` 的 `parsed == sent + failed`、`unregistered == 0`、
`tp_dropped`（抓包缺口）。

---

## 8. 常见问题与坑

| 现象 | 原因 | 处理 |
|------|------|------|
| `Configuration module could not be loaded` | SP 栈按插件加载 `libsomeip-cfg.so`，找不到 | 运行时 `LD_LIBRARY_PATH=<SP库目录>`（部署必做） |
| 客户端收不到任何事件 | 订阅未建立就回放 / 中间件未起 | 先 `srv.start()` 等 15~25s 再 `replay`；确认中间件托管 RM |
| 大消息收不到，服务端 `Dropping to big message` | 事件 >1400B 未配 someip-tp | `tp_events` 登记（SP 栈自动分片，标准版需显式配置） |
| 订阅 NACK | major 不匹配 | 服务端 offer major=1（内置默认） |
| 0x000E:8001 收不到 | 客户端 SP 包装器以组 0 订阅，跨机 SD 无法投递 | 已知限制（真实中间件宽松时可通） |
| 回放报告里 `unregistered` 不为 0 | 服务表没覆盖抓包里的事件（如用 `old` 回放 `old/out.pcap` 有 187 条） | 换 `--profile old-capture` 或 `--profile auto`（见 `PCAP_REPLAY.md` §3） |
| 回放报告里 `tp_dropped` > 0 | 抓包有丢片/文件被截断 | 那条消息整条不发（宁缺勿错）；确认抓包完整性 |
| `这是 pcapng 格式…` | 只支持经典 pcap | `editcap -F pcap in.pcapng out.pcap` 或 `tcpdump -r … -w …` |
| 大抓包（260MB）回放很慢 | `timing=capture` 会按原始时长放 | 演练用 `--speed 10~50`；正式联调再回到 `--speed 1` |
| Windows 加载 dll 失败 | DLL 搜索路径 | `os.add_dll_directory` / 同目录 / PATH |
| 客户端 SP 库版本变更 | — | 替换 `libs/` 库文件即可（动态链接）；C 接口/配置格式变才需重编（DEPLOYMENT.md §6） |

---

*配套：`PCAP_REPLAY.md`（pcap 回放与发布）、`DEPLOYMENT.md`（部署）、`WINDOWS.md`（Windows）、
`FIXED_CONFIG_SOLUTION.md`（架构背景与排障记录）。*
