# C++ 服务端库（libarhud_server.so，SP 分支协议栈）+ Python 调用

> **📄 相关文档**
> - [`PCAP_REPLAY.md`](PCAP_REPLAY.md) —— ★ pcap 回放与发布指南（`lipeng20260228/old` 那批抓包、节奏/选表/验证）
> - [`CODE_GUIDE.md`](CODE_GUIDE.md) —— 代码详解（架构/逐模块/数据流/二次开发/排障）
> - [`DEPLOYMENT.md`](DEPLOYMENT.md) —— 部署包结构、systemd、客户端 SP 库版本变更流程
> - [`WINDOWS.md`](WINDOWS.md) —— Windows 部署方案（原生/ WSL2 / Docker 三方案）

用 **C++ 编写 SOME/IP 服务端库**，**Python 通过 ctypes 调用**：
Python 负责业务编排（指定 pcap 回放、对数据结构赋值组包），C++ 库负责通信内核。

**协议栈 = SP 分支（libsomeip.so，与板端示例 C++ 服务端 hud_pcap_huifang_server 完全一致）**，
接口即示例服务端所用：`SPInit → SPServerNotifyCallbackFuncRegist → SPStart → SPServerSendNotify`。
优势：与板端中间件/客户端同一协议栈，无标准 vsomeip 与 SP 分支的兼容性问题；
51KB 大消息由 SP 栈自动 SOME/IP-TP 分片（无需显式配置）。

## 服务表代（profile）与 2026-02 更新

服务/事件表**只有一处定义**：`src/arhud_services.h`（SP 版与标准 vsomeip 版共用），两代用
环境变量 `ARHUD_SERVICE_PROFILE` 选择：

| profile | 规模 | 来源（与参考实现逐条对齐） |
|---------|------|---------------------------|
| `old`（默认） | 11 服务 / 23 事件 | `lipeng20260228/old/someip_arhud01_pcap_server.json` |
| `old-capture` | 11 服务 / 33 事件 | `old` + 抓包实测的 10 个事件（完整回放/发布 `old/` 下 pcap 用，见 `PCAP_REPLAY.md`） |
| `bplus` | 6 服务 / 38 事件 | `lipeng20260228/BPlus/someip_arhud01_pcap_server_B+.json`（0x001A/0x001B/0x001C/0x001D/0x8000/0x010A） |

### 2026-10 更新：pcap 回放/发布能力（重点支持 `lipeng20260228/old` 抓包）

1. **流式解析**：`arhud::PcapStream` 边扫边重组边吐消息，不再把整个 pcap 读进内存
   （`old/output3.pcap` 260 MB：旧实现峰值 300 MB+，现在只与"在途分片"有关）；
2. **TP 重组加固**：分片按偏移**去重**（抓包重复投递不会再被拼两次）、允许乱序、
   缺口/截断的消息**整条丢弃**并计入 `tp_dropped`（`BPlus/out.pcap` 有 36 片重复，
   旧实现会拼坏 18 条，现在 14 667/14 667 全对）；
3. **回放引擎独立**（`src/arhud_replay.*`，SP 版与标准版共用）：支持**多文件/目录**、
   `timing=capture`（按抓包时间戳，对齐参考实现）/`interval`（固定间隔）、倍速、限轮、起播延迟；
4. **逐事件统计报告**：`arhud_server_replay_report()` 输出 JSON（attempted/sent/unregistered），
   `unregistered` 单独计数，用来判断服务表选得对不对；
5. **新增 `old-capture` 服务表**：`old` + 抓包实测但参考配置未登记的 10 个事件
   （`0x0007:8003/8004`、`0x0017:8002`、`0x8202:8001/8006~800B`）；`old` 保持与参考配置逐条一致；
6. **Python 层**：`replay_dir()`、`for_pcaps()`（按 pcap 自动选表）、`replay_report()`、
   `pcap_events()`/`profile_events()`；`demo_replay.py` 支持目录、节奏、倍速、体检与报告落盘；
7. **工具**：`tools/analyze_pcap.py`（纯 Python 体检/对照实现）、`tools/pcap_selftest.cpp`、
   `tools/replay_selftest.cpp`、`tools/dryrun_server.cpp`（不联网演练）、两个一键自测脚本。

### 2026-02 更新（服务表两代 + 库升级）

1. **库更新**：`libs/arm64` 换成参考实现 `libs.zip` 的 `lib_bst_t517`（2025-12-15），
   新增 `libs/x86_64`（`lib_x86`，2025-12-23；库文件不入 git，见 `libs/README.md`）；
2. **两代服务表**：新增 `bplus` profile（表来自参考配置，脚本生成，可追溯）；
   实测可注册 6 服务/38 事件并完整回放 B+ 的 pcap（14667/14667）；
3. **配置生成对齐参考实现**：`gen_sp_config()` 现在带
   `max-payload-size-unreliable: 3000000`（大帧 TP 必需）、`max_dispatchers`/`threads`、
   按 profile 取 `applications[0].id`（old `0x1001` / bplus `0x1443`）、
   补齐 `dds_log_enable`/`dmesg_log_enable` 日志键；
4. **注册表幂等**：`arhud_server_add_service/add_event` 对同 (service,instance[,event])
   只更新不重复追加。此前"内置表 + 调用方逐条注册"会把表变成 22 服务/46 事件
   （协议栈侧重复 offer/回调），现在库自报计数与实际一致；
5. **回放计数拆开**：`arhud_server_replay_sent()` 只统计**真正发送成功**（notify 返回 0），
   新增 `arhud_server_replay_attempted()` 统计尝试次数。二者差值即"事件未注册（profile 选错）"
   导致的跳过量 —— 原来把失败也算成功，容易误判；
6. **新增诊断接口**：`arhud_server_profile()/service_count()/event_count()`；
7. **rpath 改为 `$ORIGIN`**：库与同目录 `libsomeip*.so` 一起拷到任何位置都能加载，
   **不再需要 `LD_LIBRARY_PATH`**；Makefile 的默认 `SP_LIBS` 路径也修正为 `../libs/<arch>`。

## 架构

```
Python (业务层)                    C++ 库 (通信内核)                      客户端
┌──────────────────────┐          ┌────────────────────────┐   SD多播    ┌──────────────┐
│ demo_struct.py       │ ctypes   │ libarhud_server.so     │  事件UDP    │ 板子客户端    │
│  结构体赋值→序列化    │─────────►│  · 1 应用 offer 11 服务  │◄──────────►│ (SP 中间件RM) │
│ demo_replay.py       │          │  · notify 发送          │            └──────────────┘
│  指定 pcap 回放       │          │  · pcap 回放(TP重组)    │
└──────────────────────┘          └────────────────────────┘
```

## 文件说明

```
arhud_python_server/
├── src/
│   ├── arhud_server.h / .cpp   # C 接口 + 标准 vsomeip 内核（备用）
│   ├── arhud_server_sp.cpp     # C 接口 + SP 分支内核（主）
│   ├── arhud_pcap.h / .cpp     # ★ 流式 pcap 解析 + SOME/IP-TP 重组（去重/乱序/缺口）
│   ├── arhud_replay.h / .cpp   # ★ 回放引擎（多文件、capture/interval 节奏、倍速、限轮、报告）
│   ├── arhud_services.h        # ★ 服务表唯一来源（old / old-capture / bplus）
│   ├── arhud_types.h / .cpp    # 9 种数据结构 + 大端序列化 + CRC32
│   └── Makefile                # make → libarhud_server.so
├── python/
│   ├── arhud_py.py             # Python ctypes 封装（replay_dir / for_pcaps / replay_report …）
│   ├── demo_struct.py          # 示例①：结构化赋值 → 组包 → 发送
│   └── demo_replay.py          # 示例②：文件或目录回放/发布（节奏/倍速/体检/报告）
├── tools/
│   ├── analyze_pcap.py         # 纯 Python pcap 体检（C++ 解析器的独立对照实现）
│   ├── pcap_selftest.cpp       # C++ 解析器自测（无需协议栈）
│   ├── replay_selftest.cpp     # 回放引擎自测（假发送器）
│   ├── dryrun_server.cpp       # "演练版"库：不联网跑通 Python 全链路
│   ├── local_selftest.sh       # 本机一键自测
│   └── container_replay_test.sh# 容器内用真实 SP 协议栈编译并回放
├── config/                     # SP 分支配置模板（old，app id 0x1001）
├── PCAP_REPLAY.md              # ★ pcap 回放与发布指南
└── README.md
```

## 编译

```bash
# 依赖：SP 分支库（libsomeip.so 等，zip 内 libs/lib_bst_t517 或 lib_x86）+ zlib
cd arhud_python_server
make libarhud_server.so SP_LIBS=../libs/arm64    # aarch64（或 ../libs/x86_64）
# 运行（SP 栈按插件加载 cfg/sd 模块，需要 LD_LIBRARY_PATH 指向 SP 库目录）
LD_LIBRARY_PATH=libs/arm64 python3 python/demo_replay.py <pcap或目录> <本机IP>
```

> 标准 vsomeip 3.4.10 版保留为备用：`make libarhud_server_std.so`（链接 libvsomeip3）。
> 没有协议栈时可以先跑"演练版"（不联网）：
> `g++ -std=c++14 -O2 -shared -fPIC -I src src/arhud_pcap.cpp src/arhud_replay.cpp src/arhud_types.cpp tools/dryrun_server.cpp -o /tmp/dryrun/libarhud_server.so -lz`
> → `ARHUD_LIB_PATH=/tmp/dryrun/libarhud_server.so python3 python/demo_replay.py <pcap或目录> --once`。

## Python 使用

```python
from arhud_py import ArHudServer

srv = ArHudServer(unicast="192.168.1.10")   # 自动探测 IP
srv.start()

# ① 结构化赋值 → C++ 库序列化（大端 + CRC32 自动补）→ 发送
srv.notify_fields("RTK", counter=1, rtk_status=1,
                  longitude=116.397, latitude=39.908, ...)
srv.notify_fields("IMU", counter=1, angular_velocity_x=0.01, ...)
srv.notify_fields("VehiclePosition", counter=1, Longitude=116.397, ...,
                  lanes=[1,2,3], segs=[10,20], loc_offset=0)

# ② 原始字节发送
srv.notify_raw(0x000A, 0x8001, b"...")

# ③ pcap 回放/发布（后台线程，流式解析 + TP 重组）
srv.replay("out.pcap", timing="capture")                    # 按抓包原始节奏
srv.replay_dir("/path/to/pcap_dir", loop=True, speed=1.0)   # 目录：out.pcap 优先 + 其余
print(srv.replay_status(), srv.replay_report())             # 进度 / 逐事件报告

# ④ 按 pcap 自动选表并创建（省去手工挑 profile）
srv2 = ArHudServer.for_pcaps("/path/to/pcap_dir", unicast="192.168.1.10")
srv2.start(); srv2.replay_dir("/path/to/pcap_dir")

srv.stop()
```

> 回放 `/Users/wunengfa/Desktop/someip/lipeng20260228/old` 下的三个 pcap（48 404 条、24 个事件）
> 完整流程见 [`PCAP_REPLAY.md`](PCAP_REPLAY.md)。

支持的结构化类型（与板端 `ArHudSomeipDataType.h` 布局一致，字节级验证通过）：
`RTK` `IMU` `ChangeLane` `PilotStatus` `PilotAlarm` `Broadcast` `HudMappath`
`HudNavmap` `VehiclePosition`（动态数组用 `lanes=` / `segs=` 传入）。

## 环境变量

| 变量 | 作用 | 取值 |
|------|------|------|
| `ARHUD_SERVICE_PROFILE` | 选择服务表 | `old`（默认）/ `old-capture`（+抓包实测 10 事件）/ `bplus` |
| `HUD_SOMEIP_TABLE` | 上位机（HudAutoTest）侧的服务表开关 | `old` / `bplus`，会同步写入 `ARHUD_SERVICE_PROFILE` |
| `ARHUD_LIB_PATH` | 覆盖 Python 加载的库路径（演练版/多架构并存时用） | 绝对路径 |
| `ARHUD_DRYRUN_VERBOSE` | 演练版库逐条打印 notify | `1` / `0` |

> 两者不一致时以 `HUD_SOMEIP_TABLE` 为准（上位机会记录告警），避免"上位机认为注册了 38 个事件、
> 库只注册 23 个"的错配。

## C 接口速览

```c
arhud_server_t* arhud_server_create(const char* unicast, const char* config_path);
int  arhud_server_start(arhud_server_t*);
int  arhud_server_notify(arhud_server_t*, uint16_t service, uint16_t event,
                         const uint8_t* data, uint32_t len);

/* pcap 回放/发布：老接口（单文件 + 固定间隔） */
int  arhud_server_replay_start(arhud_server_t*, const char* pcap_path, int loop, uint32_t interval_ms);
/* 新接口：多文件/目录 + 按抓包时间戳 + 倍速 + 限轮 + 起播延迟 */
void arhud_replay_opts_default(arhud_replay_opts*);
int  arhud_server_replay_start_ex(arhud_server_t*, const char* const* paths, int n_paths,
                                  const arhud_replay_opts*);
void        arhud_server_replay_stop(arhud_server_t*);
uint64_t    arhud_server_replay_parsed(arhud_server_t*);
uint64_t    arhud_server_replay_sent(arhud_server_t*);
uint64_t    arhud_server_replay_unregistered(arhud_server_t*);
int         arhud_server_replay_report(arhud_server_t*, char* buf, uint32_t buflen);  /* JSON */

/* pcap 体检 / 服务表导出（无需服务端句柄） */
int         arhud_pcap_events(const char* const* paths, int n_paths, char* buf, uint32_t buflen);
int         arhud_profile_events(const char* profile, char* buf, uint32_t buflen);
const char* arhud_pcap_error(void);

void arhud_server_destroy(arhud_server_t*);
uint32_t arhud_crc32(const uint8_t*, uint32_t);
```

## 实测结果（真实客户端，固定配置，双容器）

| 指标 | 结果 |
|------|------|
| 结构化数据（RTK/IMU/Broadcast 等） | 客户端反序列化字段**全部正确**（longitude=116.397 等） |
| pcap 回放 | 413 条全部解析（TP 重组与 Python 版一致），客户端持续接收 |
| 51KB 大消息 0x000C:8003 | **74+ 条**（SP 栈自动分片，0 丢弃） |
| 客户端总接收 | 940+ 条（14 个事件，SP 版） |
| 结构化数据 | 客户端反序列化字段全部正确（RTK/IMU/Broadcast 等） |

**2026-10 追加实测（`lipeng20260228/old` 那批抓包，真实 SP 协议栈，容器 aarch64）**：

| 指标 | 结果 |
|------|------|
| `old/out.pcap`（5 368 条）profile=`old` | 5 368 条经发送接口；其中 **187 条 `unregistered`**（10 个事件参考配置未登记） |
| `old/out.pcap` profile=`old-capture` | 5 368 条，`unregistered=0` |
| `old/` 整个目录（3 文件 48 404 条） | **48 404 条全部发布成功**，0 失败、0 表外；`tp_dropped=2`（两处文件尾截断） |
| C++ 解析器 vs 纯 Python 独立实现 | 逐文件条数**完全一致**（5368 / 37668 / 5368，B+ 14667） |
| `BPlus/out.pcap`（36 片重复分片） | 去重后 **14 667/14 667** 正确重组（旧实现会拼坏 18 条） |
| 260 MB `output3.pcap` | 流式解析，按抓包节奏约 339 s；50 倍速 8.8 s 跑完 3 个文件 |

复现：`tools/local_selftest.sh <pcap目录>`、`tools/container_replay_test.sh <pcap目录>`（见 [`PCAP_REPLAY.md`](PCAP_REPLAY.md) §6）。

## 已知限制

1. **0x000E:8001**（SP 包装器以组 0 订阅）无法经 SD 远程投递——与 Python 服务端方案相同的已知限制；
2. `HudRoad` 类型（复杂字符串/数组）暂未实现 C++ 序列化，可用 `notify_raw` 发送
   Python 侧 `hud_data_types.py` 生成的数据；
3. 回放间隔 `interval_ms` 过小会加大 TP 大消息的丢包概率（建议 ≥10ms，且等待客户端订阅稳定后再回放）；
4. SP 分支 C 接口未提供订阅回调（`arhud_server_set_subscribe_cb` 为占位）；
5. `0x000E:8001`（客户端 SP 包装器以组 0 订阅）在跨机 SD 路径下无法投递（组 0 为协议保留值，
   测试中间件与 SP 服务端均拒绝；若板端真实中间件对组 0 宽松处理则可通，原始抓包中有该事件数据）；
6. **pcap 只支持经典 pcap 格式**（这批抓包都是）；pcapng 需先 `editcap -F pcap` 转换；
7. **TCP 只计数、不解析**：参考实现会把 TCP 载荷当 SOME/IP 试解析，实测 `output3.pcap` 的
   116 996 个 TCP 报文无一通过版本校验，等价但更安全；
8. **TP 缺口消息整条丢弃**（宁缺勿错），条数记在回放报告的 `tp_dropped`；
9. 参考二进制 `old/x86_server_ArHud_huifang_pcap_B` 在 Apple Silicon 的 qemu 模拟容器里
   会卡在 `SPStart`，无法做逐包对比；改用"源码逐条对齐 + 两套独立解析器交叉验证"（见 `PCAP_REPLAY.md` §7）。
