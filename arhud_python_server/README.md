# C++ 服务端库（libarhud_server.so，SP 分支协议栈）+ Python 调用

> **📄 相关文档**
> - [`DEPLOYMENT.md`](DEPLOYMENT.md) —— 部署包结构、systemd、客户端 SP 库版本变更流程
> - [`WINDOWS.md`](WINDOWS.md) —— ★ Windows 部署方案（原生/ WSL2 / Docker 三方案 + 修改清单）

用 **C++ 编写 SOME/IP 服务端库**，**Python 通过 ctypes 调用**：
Python 负责业务编排（指定 pcap 回放、对数据结构赋值组包），C++ 库负责通信内核。

**协议栈 = SP 分支（libsomeip.so，与板端示例 C++ 服务端 hud_pcap_huifang_server 完全一致）**，
接口即示例服务端所用：`SPInit → SPServerNotifyCallbackFuncRegist → SPStart → SPServerSendNotify`。
优势：与板端中间件/客户端同一协议栈，无标准 vsomeip 与 SP 分支的兼容性问题；
51KB 大消息由 SP 栈自动 SOME/IP-TP 分片（无需显式配置）。

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
