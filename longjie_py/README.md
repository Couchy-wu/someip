# to_longjie 真实客户端 ⇄ Python 服务端

> **📄 详细方案与问题定位全记录见 [`FIXED_CONFIG_SOLUTION.md`](FIXED_CONFIG_SOLUTION.md)**
> （含固定配置客户端的 RM 宿主架构 + 6 个关键问题的完整定位过程）

让板子上编译好的 **真实 C++ 客户端**（`hud_huifang_client`，比亚迪 AR-HUD，SP 协议栈/SomeipCom）
正确订阅并收到 **Python 服务端**（vsomeip_py + 标准 vsomeip 3.4.10）发送的数据。

> 实测：客户端经 SD 多播发现服务 → 逐事件订阅（major=1）→ 收到服务端数据。
> 双机（双容器）自动化测试 **PASS**：11 个服务全部订阅接受，pcap 全部事件 + 生成事件共
> **17~19/23 个事件收到数据**（取决于 fill_missing 开关），0x000C:8003 的 51KB 大消息经
> SOME/IP-TP 分片正常送达。

---

## 一、文件说明

```
longjie_py/
├── hud_server_longjie.py                 # ★ Python 服务端（主程序）
├── pcap_replay_tp.py                     # pcap 解析 + SOME/IP-TP 分片重组
├── someip_arhud01_client_crosshost.json  # ★ 修正后的客户端配置模板（跨机部署用）
└── README.md                             # 本文档

docker/integration_test_longjie.sh        # ★ 双容器自动化测试（A=服务端/B=客户端）

to_longjie_demo_20250625/                 # 板子工程（源码 + 编译产物 + pcap）
├── build/hud_huifang_client              # 真实客户端二进制 (aarch64)
├── build/hud_huifang_client_x86          # 真实客户端二进制 (x86_64)
├── build/out.pcap                        # 抓包（服务端回放的数据源）
├── build/someip_arhud01.json             # 客户端配置（需按本文修正）
├── build/someip_arhud01_pcap_server.json # 原 C++ 服务端配置（对照参考）
├── libs/lib_bst_t517/                    # aarch64 SP 库（客户端依赖）
├── libs/lib_x86/                         # x86 SP 库
├── hud_huifang_client.cpp                # 客户端源码
├── hud_pcap_huifang_server.cpp           # 原 C++ 服务端源码（回放 pcap）
├── ArHudSomeipDataType.h                 # 23 种数据类型定义
└── ArHudSomeipDataConversion.cpp/.h      # SP 序列化/反序列化实现
```

---

## 二、通信原理（与 C++ 服务端行为对齐）

```
┌───────────────── 服务端（PC / 本机，Python） ─────────────────┐
│ 11 个 vsomeip_py 应用 (arhud01, arhud01_1 ... arhud01_10)     │
│   · arhud01 = 路由管理器宿主（网络名 arhud01）                 │
│   · 每个应用 offer 1 个服务：23 个事件，major=1                │
│   · SD 多播 224.0.2.4:30490 宣告服务                          │
│   · 收到 SUBSCRIBE → ACK → notify 发送事件                    │
│   · 载荷来源：out.pcap 回放（TP 重组）+ 缺失事件生成            │
└──────────────────────────┬────────────────────────────────────┘
                           │ UDP (SD: 多播 224.0.2.4:30490 / 数据: 单播)
┌──────────────────────────┴────────────────────────────────────┐
│ 客户端（板子 / 另一台机器，真实 C++ 二进制 + SP 库）            │
│   · 应用 arhud02，routing=arhud02（自托管 RM，网络模式）        │
│   · request_service(11 服务, major=1) → SD FindService         │
│   · 逐事件 subscribe(svc, inst, group, major=1, event)         │
│   · 收到通知 → SPDeserialization → 打印字段 + 计数              │
└────────────────────────────────────────────────────────────────┘
```

### 与 C++ 服务端（`hud_pcap_huifang_server`）对齐的关键点

| # | 项 | C++ 服务端 | Python 服务端 | 说明 |
|---|----|-----------|---------------|------|
| 1 | offer 版本 | major=1 | `version=(1,0)` + 配置 `"major":"1"` | 客户端按 major=1 请求/订阅，不匹配会被 NACK |
| 2 | 端口 | 51400-51409, 0x010A→52001 | 同左（services_map） | 0x010A 特殊：instance=0x0001 |
| 3 | 0x000E 事件组 | 0x1101/0x1102/0x1103 | 同左 | 三个事件分属三个组 |
| 4 | SD | 224.0.2.4:30490 | 同左 | `enable`（不是 `enabled`） |
| 5 | 大消息 | SP 分支自动 TP 分片 | **必须显式 `someip-tp`** | 标准 vsomeip 超 1400B 不自动分片，会丢弃 |
| 6 | 载荷 | 回放 out.pcap（含 TP 重组） | 同左 + 可选生成缺失事件 | CRC32 语义与 pcap 实测一致 |

---

## 三、实测踩坑记录（重要！）

### 3.1 客户端 UDS 协议与标准 vsomeip 3.4.10 不兼容
- SP 分支客户端（libsomeip.so）与标准 3.4.10 的**同机 UDS 通道协议不兼容**：
  即使 UDS socket 路径一致（`/tmp/arhud01-*`），Proxy 连接后 `request client timeout`，
  无法注册。
- SP 分支也不允许同机出现第二个 RM（`other routing manager present`）。
- **结论：跨机部署必须双 RM + 网络模式**（客户端 `routing` 改为自身应用名）。

### 3.2 客户端配置必须做的两处修改（`someip_arhud01.json`）
1. **`routing` → 客户端自身应用名**（`arhud02`）：跨机时本机没有 arhud01 的 RM，
   必须自托管 RM 走网络 SD。板端同机场景（C++ 服务端在板子上）保持 `arhud01` 不变。
2. **0x000E 必须拆分**：SP 包装器 `clientSubscribeCallbackFuncRegist` 实际按**配置**订阅，
   且只读顶层 `event_group`（per-event 的 `event_groups` 字符串解析为 0x0000 → 被 NACK）。
   把 0x000E 拆成 3 条记录，分别带 `event_group: 0x1101/0x1102/0x1103`。

> 修正后的完整模板见 `someip_arhud01_client_crosshost.json`（需把 `unicast` 改为板子实际 IP）。

### 3.3 服务端 three 要点
- offer 必须 major=1（`vSOMEIP(..., version=(1,0))` 且先 `offer()` 再 `offer(events)`）。
- `network` 必须设为 `arhud01`（vsomeip_py 模板缺省是 `"vsomeip"`，导致 UDS 路径不一致；
  跨机无影响但保持与板端一致）。
- 大载荷事件（0x000C:8002/8003、0x010A:8001/8003）必须配 `someip-tp`，
  否则标准 vsomeip 直接丢弃（`Dropping to big message`）。

### 3.4 数据/载荷
- pcap 解析含 **SOME/IP-TP 重组**（按 service/method/session，偏移为字节单位）。
- 生成载荷自动补 `Checksum = CRC32(payload[4:])`（与 pcap 实测一致）。
- pcap 中没有的事件（0x000B、0x010A、0x000D:8004、0x000E:8002/8003、0x002B、0x8202、
  0x0018）：
  - `ARHUD_FILL_MISSING=1`（默认）：已定义类型（RTK/IMU/Broadcast/HudRoad/Mappath/Navmap）
    自动生成并发送，客户端反序列化字段**实测全部正确**；
  - 其余 6 个复杂类型（OverseasHudRoad、newPlanningLine、drivingArea、NavHDLink2、
    sdTraffic、hpaMap）需要真实载荷（放 pcap 里即可自动回放），或按
    `ArHudSomeipDataType.h` 补序列化器。

---

## 三.5 客户端配置固定（已烧录在板子，无法修改）时的部署 ★

**结论：可以，客户端配置一行都不用改。** 前提是板子上有一个 SP 分支进程托管 RM——
实际部署中它就是**板子既有的 SOME/IP 中间件**（客户端 `routing=arhud01` 必须连本机
UDS 的 RM，这个 RM 只能由 SP 分支进程托管，标准 vsomeip 3.4.10 不行）。
**Python 服务端跑在本机（替代 C++ 服务端），经车载以太盒子（透明网桥）连板子，
板子零改动。**

```
PC(192.168.x.x)                         板子(192.168.195.11)
┌──────────────────────┐                ┌──────────────────────────────┐
│ Python 服务端         │                │ ① RM 宿主（SP 分支，不提供服务）│
│ (vsomeip_py 3.4.10)  │                │    = C++服务端二进制 + 空services│
│  · offer 23事件 major1│   SD 多播      │    配置 + 静默pcap（只含SD包）  │
│  · 0x000E 额外组0x0000│◄──────────────►│ ② 原版客户端（配置完全不动）    │
│  · 事件 → 板子RM      │   事件UDP      │    routing=arhud01 → UDS→①    │
└──────────────────────┘                └──────────────────────────────┘
```

**关键点（全部实测）**：
1. **RM 宿主必须用 SP 分支进程**：标准 vsomeip 3.4.10 的 UDS 协议与 SP 分支不兼容，
   Python 服务端无法托管这个 RM（客户端 register timeout）。
2. RM 宿主 = 板上的 `hud_pcap_huifang_server` 二进制 + **空 `services` 配置**
   （`longjie_py/someip_arhud01_rm_host.json`，改 unicast）+ **静默 pcap**
   （`longjie_py/rm_host_silent.pcap`，只含 SD 包：解析器跳过不发送，时间戳提供喘息）。
   空 services 避免本地 offer 遮蔽远程 Python 服务端；静默 pcap 避免空循环饿死 RM 线程。
3. **启动顺序敏感**：Python 服务端 → RM 宿主 → 等 8s → 客户端（客户端注册握手机敏，
   顺序不当会 register timeout 循环；多试几次或拉长间隔即可）。
4. Python 服务端为 0x000E 额外 offer 了 eventgroup 0x0000（固定配置下 SP 包装器用
   组 0 订阅 0x000E 事件）。
5. **实测结果**：16/17 个 pcap 事件 + 生成事件全部收到（每事件 200+ 条，0 注册超时）。
   **已知限制：0x000E:8001（组 0x0000 订阅）无法经 SD 远程投递**——SP 包装器把
   per-event `event_groups` 解析为组 0，而 SOME/IP-SD 协议中组 0 无法承载事件；
   该事件在板端同机（UDS 直连，原始部署）场景不受影响。
6. 自动化测试：`bash docker/integration_test_longjie_fixedcfg.sh`（PASS）。

**如果板子上没有任何 SP 分支进程（只有客户端）**：客户端本身就无法工作（缺本地 RM），
这与 Python/其他服务端无关，是客户端二进制的硬性要求——必须先跑起 RM 宿主。

---

## 四、部署指南

### 4.1 跨机部署（推荐：PC 跑 Python 服务端，板子跑客户端）

**服务端（PC，Linux x86_64，Python 3.10 + vsomeip_py）**
```bash
# 安装依赖（见仓库 docker/Dockerfile）
python3 hud_server_longjie.py          # 自动探测 IP；或 ARHUD_UNICAST=<PC IP>
```

**客户端（板子，aarch64）**
```bash
# 1. 把修正后的配置放客户端同目录
cp longjie_py/someip_arhud01_client_crosshost.json 板子上:someip_arhud01.json
#    并把其中 "unicast" 改为板子实际 IP（如 192.168.195.11）
# 2. 运行客户端（与 libs/ 同目录）
LD_LIBRARY_PATH=$PWD/libs ./hud_huifang_client
```

**网络要求**：两端互通；多播 224.0.2.4:30490 可达（同网段/路由器放行）；UDP 放行。

### 4.2 自动化测试（双容器）

```bash
bash docker/integration_test_longjie.sh
# 环境变量：IMAGE(镜像) FILL(1/0) DURATION(秒)
```

### 4.3 服务端环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `ARHUD_UNICAST` | 自动探测 | 本机 IP |
| `ARHUD_PCAP` | 自动探测 | pcap 路径（默认 `../to_longjie_demo_20250625/build/out.pcap`） |
| `ARHUD_FILL_MISSING` | `1` | 1=缺失事件生成数据；0=仅回放 pcap |
| `ARHUD_SD` | `true` | 服务发现开关 |
| `ARHUD_MAX_DELAY` | `0.5` | 每轮发送间隔秒 |
| `ARHUD_SEND_COUNT` | `0` | 0=无限 |

---

## 五、已知限制

1. **同机部署（服务端+客户端同一台 Linux）不可用**：SP 分支与标准 3.4.10 的 UDS
   协议不兼容，且 SP 分支禁止同机双 RM。如需同机，服务端也必须用 SP 分支库
   （vsomeip_py 与其 ABI 不兼容，暂不可行）。
2. **6 个复杂类型无生成器**（见 3.4）：其数据需来自 pcap；若你的 pcap 含这些事件，
   服务端自动回放，客户端即可收到（23/23）。
3. 客户端收到的服务端数据按 pcap 内容为准；`fill_missing` 只补已定义类型。

---

## 六、验证日志示例（客户端 SIGINT 汇总）

```
Total_count:                                                              57
0. (0x000A, 0x000A, 0x8001, 0x1101): VehiclePositionInfoNotify:           3
1. (0x000B, 0x000B, 0x8001, 0x1101): RTKInfoNotify:                       3
...
13.(0x000C, 0x000C, 0x8003, 0x1101): NewLanelineDataNotify                3   ← 51KB TP 大消息
17.(0x0017, 0x0017, 0x8003, 0x1101): NewParkingRealTimeDataNotify         3
```

服务端日志：
```
REMOTE SUBSCRIBE(0000): [000c.000c.1101] from 172.20.0.3:52003 unreliable was accepted
SUBSCRIBE ACK(1445): [000c.000c.1101.ffff]
```
