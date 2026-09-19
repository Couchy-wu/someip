# C++ 服务端库（libarhud_server.so，SP 分支协议栈）+ Python 调用

> **📄 相关文档**
> - [`CODE_GUIDE.md`](CODE_GUIDE.md) —— ★ 代码详解（架构/逐模块/数据流/二次开发/排障）
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
| `bplus` | 6 服务 / 38 事件 | `lipeng20260228/BPlus/someip_arhud01_pcap_server_B+.json`（0x001A/0x001B/0x001C/0x001D/0x8000/0x010A） |

本次更新内容：

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
├── arhud_server.h / .cpp   # C 接口 + vsomeip 内核（offer/notify/回放/订阅回调）
├── arhud_pcap.h / .cpp     # pcap 解析 + SOME/IP-TP 分片重组（字节偏移）
├── arhud_types.h / .cpp    # 9 种数据结构 + 大端序列化 + CRC32
├── Makefile                # make → libarhud_server.so
├── arhud_py.py             # Python ctypes 封装（ArHudServer 类）
├── demo_struct.py          # 示例①：结构化赋值 → 组包 → 发送
├── demo_replay.py          # 示例②：指定 pcap 文件回放
└── README.md
docker/integration_test_cpplib.sh  # 自动化测试（PASS）
```

## 编译

```bash
# 依赖：SP 分支库（libsomeip.so 等，zip 内 libs/lib_bst_t517 或 lib_x86）+ zlib
cd arhud_python_server
make libarhud_server.so SP_LIBS=../to_longjie_demo_20250625/libs/lib_bst_t517   # aarch64
make libarhud_server.so SP_LIBS=../to_longjie_demo_20250625/libs/lib_x86       # x86_64
# 运行（Python demo 需要 LD_LIBRARY_PATH 指向 SP 库，SP 栈按插件加载 cfg/sd 模块）
LD_LIBRARY_PATH=<SP库目录> python3 demo_replay.py out.pcap <本机IP>
```

> 标准 vsomeip 3.4.10 版保留为备用：`make libarhud_server_std.so`（链接 libvsomeip3）。

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

# ③ 指定 pcap 回放（后台线程，自动 TP 重组）
srv.replay("out.pcap", loop=True, interval_ms=10)
print("已回放:", srv.replay_sent())

srv.stop()
```

支持的结构化类型（与板端 `ArHudSomeipDataType.h` 布局一致，字节级验证通过）：
`RTK` `IMU` `ChangeLane` `PilotStatus` `PilotAlarm` `Broadcast` `HudMappath`
`HudNavmap` `VehiclePosition`（动态数组用 `lanes=` / `segs=` 传入）。

## 环境变量

| 变量 | 作用 | 取值 |
|------|------|------|
| `ARHUD_SERVICE_PROFILE` | 选择服务表代 | `old`（默认）/ `bplus` |
| `HUD_SOMEIP_TABLE` | 上位机（HudAutoTest）侧的服务表开关 | `old` / `bplus`，会同步写入 `ARHUD_SERVICE_PROFILE` |

> 两者不一致时以 `HUD_SOMEIP_TABLE` 为准（上位机会记录告警），避免"上位机认为注册了 38 个事件、
> 库只注册 23 个"的错配。

## C 接口速览

```c
arhud_server_t* arhud_server_create(const char* unicast, const char* config_path);
int  arhud_server_start(arhud_server_t*);
int  arhud_server_notify(arhud_server_t*, uint16_t service, uint16_t event,
                         const uint8_t* data, uint32_t len);
int  arhud_server_replay_start(arhud_server_t*, const char* pcap_path, int loop, uint32_t interval_ms);
uint64_t arhud_server_replay_sent(arhud_server_t*);
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

## 已知限制

1. **0x000E:8001**（SP 包装器以组 0 订阅）无法经 SD 远程投递——与 Python 服务端方案相同的已知限制；
2. `HudRoad` 类型（复杂字符串/数组）暂未实现 C++ 序列化，可用 `notify_raw` 发送
   Python 侧 `hud_data_types.py` 生成的数据；
3. 回放间隔 `interval_ms` 过小会加大 TP 大消息的丢包概率（建议 ≥10ms，且等待客户端订阅稳定后再回放）；
4. SP 分支 C 接口未提供订阅回调（`arhud_server_set_subscribe_cb` 为占位）；
5. `0x000E:8001`（客户端 SP 包装器以组 0 订阅）在跨机 SD 路径下无法投递（组 0 为协议保留值，
   测试中间件与 SP 服务端均拒绝；若板端真实中间件对组 0 宽松处理则可通，原始抓包中有该事件数据）。
