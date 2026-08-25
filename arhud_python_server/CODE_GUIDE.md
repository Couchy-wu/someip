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
│   ├── arhud_pcap.h/.cpp         #   pcap 解析 + SOME/IP-TP 重组
│   ├── arhud_types.h/.cpp        #   数据结构 + 大端序列化 + CRC32
│   ├── Makefile                  #   Linux 构建（SP 库链接）
│   └── include/vsomeip/someip_com.h  # SP 分支 C 接口声明
├── CMakeLists.txt                # 跨平台构建（Windows/Linux、SP/标准）
├── python/                       # ★ Python 业务层
│   ├── arhud_py.py               #   ctypes 封装（ArHudServer 类）
│   ├── demo_struct.py            #   示例：结构化赋值 → 发送
│   └── demo_replay.py            #   示例：指定 pcap 回放
├── libs/                         # SP 分支库依赖
│   ├── arm64/                    #   aarch64（lib_bst_t517）
│   └── x86_64/                   #   x86_64（build_package.sh 从 zip 提取）
├── config/                       # SP 分支配置模板
├── build_package.sh              # 一键组装自包含部署包
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
                               int loop, uint32_t interval_ms);      // 回放 pcap
uint64_t arhud_server_replay_sent(arhud_server_t* srv);              // 已回放计数
void arhud_server_stop(arhud_server_t* srv);
void arhud_server_destroy(arhud_server_t* srv);
// 动态注册（默认内置 11 服务，一般不需要）：
int  arhud_server_add_service(...);  int  arhud_server_add_event(...);
// 序列化工具：
uint32_t arhud_crc32(const uint8_t*, uint32_t);
uint32_t arhud_pack_u8/u16/u32/u64/f32/f64(uint8_t* out, ...);       // 大端写入
```

**用法骨架**（Python 侧最终都会走到这里）：

```c
arhud_server_t* srv = arhud_server_create("192.168.1.10", NULL);  // NULL=自动生成配置
arhud_server_start(srv);                                          // offer 23 事件 + SPStart
arhud_server_notify(srv, 0x000A, 0x8001, payload, len);           // 发送
arhud_server_replay_start(srv, "out.pcap", 1, 10);                // 回放
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

**④ replay：pcap 回放（后台线程）**

```cpp
std::vector<arhud::PcapMessage> msgs;
arhud::parse_pcap(pcap_path, msgs);            // TP 重组后的事件列表
std::thread([msgs, loop, interval]() {
    while (running)
        for (m : msgs) arhud_server_notify(srv, m.service, m.event, m.payload...);
});                                              // 循环发送，interval 控制节奏
```

**内置服务注册表**（`default_services()`）：11 服务 / 23 事件，与板端客户端配置一一对应：

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

生成 SP 分支格式 JSON（与板端配置同结构），要点：
- `services[].unreliable`：服务端口；
- `services[].events[]`：每个事件的 name/event/is_field/is_reliable/notify-period；
- `services[].eventgroups[]`：事件 → 组映射（0x000E 三事件分三组）；
- `services[].someip-tp.service-to-client`：大消息分片（0x000C:8002/8003、0x010A:8001/8003）；
- `service-discovery`：`224.0.2.4:30490`。

> 若想用板端原配置，可把 `config/someip_arhud01_pcap_server.json`（unicast 改为本机 IP）
> 传给 `arhud_server_create(unicast, config_path)`。

### 4.4 pcap 解析与 TP 重组 `src/arhud_pcap.cpp`

**输入**：pcap 文件（Ethernet/VLAN/IPv4/UDP + SOME/IP）。
**输出**：`vector<PcapMessage>`，每个元素 = `{service, event, payload}`（TP 已重组）。

解析流程：

```
Ethernet(14) ─ VLAN(0x8100→18) ─ IPv4(20) ─ UDP(8) ─ SOME/IP 头(16)
  SOME/IP 头: service(2) method(2) length(4) client(2) session(2) ver(1) iver(1) type(1) rc(1)
  type==0x02 → Notification：payload = length-8 字节
  type==0x22 → TP 分片：TP头(4)= bit0 MoreSegments, bits1-31 字节偏移
    按 (service, method, session) 收集分片 → 按偏移拼接 → 完整消息
  service==0xFFFF（SD）→ 跳过
```

**易错点（已踩过）**：
1. **字节序**：EtherType、IP、UDP、SOME/IP 头**恒为大端**（网络字节序），与 pcap 记录头
   （文件字节序）无关——`ntohs/ntohl` 处理；
2. **TP 偏移单位是字节**（不是 SOME/IP 标准的 8 字节块）；
3. VLAN 标签 0x8100 会让 Ethernet 头变 18 字节，漏掉则整包错位。

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
    def start(self)                       # create + start
    def notify_raw(self, service, event, data: bytes)          # 原始字节发送
    def notify_fields(self, kind, counter=1, **fields)         # ★ 结构化赋值
    def replay(self, pcap_path, loop=True, interval_ms=10)     # pcap 回放
    def replay_sent(self)                                     # 已回放计数
    def stop(self) / close(self)
```

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

**demo_replay.py**（pcap 回放）：`srv.replay("out.pcap", loop=True, interval_ms=10)`，
每 2 秒打印一次回放计数——这是"指定 pcap 回放"的标准模板。

---

## 5. 数据流全景

```
① Python: srv.start()
     → C++: SPInit(生成配置) → SPServerNotifyCallbackFuncRegist(23事件) → SPStart
     → SP栈: 绑定端口 51400-51409/52001, 加入多播 224.0.2.4:30490, offer 11 服务(major=1)

② 客户端(板端)经中间件 SD 订阅
     → 中间件发送 SubscribeEventGroup(224.0.2.4)
     → SP栈: SUBSCRIBE ACK → 记录订阅者(中间件的 unicast:port)

③ Python: srv.notify_fields("RTK", longitude=..., ...)
     → ctypes → C++: arhud_serialize_rtk(结构体) → 大端字节 + CRC32
     → SPServerSendNotify(0x000B, 0x000B, 0x8001, payload, len)
     → SP栈: UDP 事件 → 中间件 → UDS → 客户端回调(SPDeserialization 显示字段)

④ Python: srv.replay("out.pcap")
     → C++: parse_pcap(TP重组) → 后台线程循环 SPServerSendNotify
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

1. `arhud_server_sp.cpp` 的 `default_services()` 注册表加一行（服务/实例/端口/事件/组）；
2. 端口/事件组与板端客户端配置一致（否则订阅不匹配）；
3. 大消息事件（>1400B）在 `tp_events` 里登记（如 `"0x8003"`）。

### 6.3 修改端口 / 事件组 / major

改 `default_services()` 即可——配置文件由 `gen_sp_config()` 自动跟随。

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
    srv.replay("data/backup.pcap", loop=True, interval_ms=50)
```

---

## 7. 构建与验证

```bash
# Linux（aarch64，默认内置 libs/arm64）
cd arhud_python_server/src && make libarhud_server.so
# x86_64：ARCH=x86_64（需先 build_package.sh 提取 x86 库）
# 跨平台：cmake -B build-win -DBUILD_SP=ON -DSP_LIBS_DIR=...（Windows 见 WINDOWS.md）

# 验证
bash docker/integration_test_cpplib.sh     # 双容器全链路（服务端库 + 真实客户端）
```

**验证指标**：客户端 `收<--` 行数增长、SIGINT 汇总表各事件计数、服务端 `Dropping to big
message` = 0、`已回放` 计数增长。

---

## 8. 常见问题与坑

| 现象 | 原因 | 处理 |
|------|------|------|
| `Configuration module could not be loaded` | SP 栈按插件加载 `libsomeip-cfg.so`，找不到 | 运行时 `LD_LIBRARY_PATH=<SP库目录>`（部署必做） |
| 客户端收不到任何事件 | 订阅未建立就回放 / 中间件未起 | 先 `srv.start()` 等 15~25s 再 `replay`；确认中间件托管 RM |
| 大消息收不到，服务端 `Dropping to big message` | 事件 >1400B 未配 someip-tp | 注册表 `tp_events` 登记（SP 栈自动分片，标准版需显式配置） |
| 订阅 NACK | major 不匹配 | 服务端 offer major=1（内置默认） |
| 0x000E:8001 收不到 | 客户端 SP 包装器以组 0 订阅，跨机 SD 无法投递 | 已知限制（真实中间件宽松时可通） |
| Windows 加载 dll 失败 | DLL 搜索路径 | `os.add_dll_directory` / 同目录 / PATH |
| 客户端 SP 库版本变更 | — | 替换 `libs/` 库文件即可（动态链接）；C 接口/配置格式变才需重编（DEPLOYMENT.md §6） |

---

*配套：`DEPLOYMENT.md`（部署）、`WINDOWS.md`（Windows）、`FIXED_CONFIG_SOLUTION.md`（架构背景与排障记录）。*
