# AR-HUD 23 服务 SOME/IP —— 解决方案（依据 new_describe.md）

> 对应文档：`new_describe.md`（to_longjie_demo_20250625，C++ 服务端/客户端 + Python 复现指南）
> 交付：`hud/` 目录（Python 实现，vsomeip_py）+ 集成测试（已实测通过）

## 一、问题概述

文档描述了 AR-HUD 的 SOME/IP 通信系统：**11 个服务、23 个事件**（VehiclePosition /
RTK / IMU / Obstacle / LaneLine / ChangeLane / Pilot* / Broadcast / Hud* 等），
C++ 服务端从 PCAP 回放，客户端订阅 23 个事件。需要 Python 化实现，并修正原始配置的端口错误。

## 二、关键修正（附录A）

| Service | Instance | 服务端端口 | 原配置(错误) | 修正 |
|---|---|---|---|---|
| 0x000A | 0x000A | 51400 | 52001 | **51400** |
| 0x000B | 0x000B | 51401 | 52002 | **51401** |
| 0x000C | 0x000C | 51402 | 52003 | **51402** |
| 0x000D | 0x000D | 51403 | 52005 | **51403** |
| **0x010A** | **0x0001** | **52001** | 52011 | **52001（正确，且 Instance 特殊）** |
| 0x000E | 0x000E | 51404 | 52006 | **51404** |
| 0x0007 | 0x0007 | 51405 | 52007 | **51405** |
| 0x0017 | 0x0017 | 51406 | 52008 | **51406** |
| 0x002B | 0x002B | 51407 | 52009 | **51407** |
| 0x8202 | 0x8202 | 51408 | 52010 | **51408** |
| 0x0018 | 0x0018 | 51409 | 52012 | **51409** |

- 0x010A 特殊：**Instance = 0x0001**（不是 0x010A）、端口 52001、事件 0x8001/0x8003 配置了 SOME/IP-TP；
- 其余服务 Instance = Service ID；
- **0x000E 三事件的事件组不同**：0x8001→0x1101、0x8002→0x1102、0x8003→0x1103。

## 三、文档矛盾点与实现决策

| 矛盾 | 文档 A | 文档 B | 本实现 |
|---|---|---|---|
| 字节序 | 4.3/九.1：**大端** | 附录B 4.2/4.3：**小端** | **大端**（SOME/IP 标准 + 主文档）；`ENDIAN='>'` 一处可切换 |
| 字符串格式 | 5.12：长度=3+BOM+内容 | 附录B 4.1：长度+4（含终止符） | **5.12**（`serialize_string`，无终止符） |
| 动态数组长度字段 | 5.2：字节数（÷4=元素数） | 附录B 4.2：小端元素个数 | **5.2**（字节数，大端） |
| 各类型"总大小" | 与字段不符（RTK 136≠194、IMU 70≠72、ChangeLane 56≠76、PilotAlarm 40≠42、Broadcast 11≠10、HudMappath 11≠12） | — | **以字段序列为准**（文档给出的偏移量已验证一致，如 VehiclePosition hd_lane_type@110 / target_cruise_speed@178） |
| SOME/IP-TP | 0x010A 事件 0x8001/0x8003 走分片 | — | 载荷默认 < TP 阈值；如需大帧，客户端需实现 0x22 分片重组（见 TODO） |

> ⚠️ 若你手头有真实 PCAP，先跑 `pcap_decoder.py --dump` 核对载荷字节序/字符串格式，
> 再决定是否把 `hud_data_types.py` 顶部 `ENDIAN`/字符串/数组长度常量切换。

## 四、架构（hud/）

```
hud/
├── hud_data_types.py    # 23 事件注册表 + 12 种已定义类型序列化/反序列化 + 样例数据
│                        #   （类型 12..22 仅有概要 → Opaque：帧正确、载荷 hex 展示）
├── hud_server.py        # 11 个服务应用（第一个名 arhud01=路由宿主，ID 0x1443），
│                        #   按修正表端口/实例 offer 23 个事件，周期 notify 样例数据
└── hud_client.py        # 11 个客户端应用，订阅 23 事件（含 0x000E 三个事件组），
                         #   已定义类型反序列化摘要打印，Opaque hex 展示
```

- 路由宿主：服务端第一个应用 **arhud01**（客户端 `routing="arhud01"`）——与文档 3.3 一致；
- vsomeip_py 限制：一个 `vSOMEIP` 对象 = 一个服务 ID → 服务端/客户端各 11 个应用（一个进程）；
- 大端序列化 + 字节序自测（配合 `vsomeip_example/endian.py`）。

## 五、运行与测试

```bash
# 本地（需 vsomeip_py）
cd hud
python3 hud_server.py    # 终端 A
python3 hud_client.py    # 终端 B（收齐 23 事件或 Ctrl+C）

# Docker 完整测试（集成在 run_tests.sh / CI）
bash docker/run_tests.sh     # 含 [9/9] AR-HUD 23 服务集成测试
```

集成测试断言：
1. 12 种已定义类型序列化/反序列化**往返一致**（字节级）；
2. 客户端**收齐 23/23 事件**（按 service+event 去重）；
3. 已定义类型全部解析正确（`解析失败=0`），字符串（HudRoad/HudNavmap/HudMappath）与
   动态数组（Obstacle/LaneLine）内容正确。

## 六、测试结果（已实测）

```
[9/9] AR-HUD 23 服务集成测试 ...  PASS: 23/23 事件收齐，已定义类型解析正确 ✔
收到事件总数: 37+   去重事件数: 23   解析失败数: 0
```
