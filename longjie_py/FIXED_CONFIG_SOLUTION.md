# to_longjie 固定配置客户端 ⇄ Python 服务端 完整方案与问题定位全记录

> 适用场景：**客户端程序与配置已经烧录在开发板上，无法修改**（`someip_arhud01.json` 中
> `routing=arhud01`、`0x000E` 事件组配置等全部保持原样），需要用 Python 服务端替换/补充
> 原有 C++ 服务端提供数据。
>
> 文档两部分：**一、最终方案（怎么做）**；**二、问题定位全记录（怎么想出来的）**。
> 第二部分完整还原了每一步的"现象 → 诊断方法 → 根因 → 解决"，供以后排查同类问题参考。

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [最终方案：RM 宿主架构](#2-最终方案rm-宿主架构)
3. [部署指南](#3-部署指南)
4. [实测结果](#4-实测结果)
5. [问题定位全记录（核心章节）](#5-问题定位全记录核心章节)
   - 5.1 拆解板子工程，理解客户端
   - 5.2 第一版方案：跨机自托管 RM（配置可改，19/23）
   - 5.3 用户提出硬约束：客户端配置不能改
   - 5.4 定位问题①：客户端必须有本地 RM（UDS）
   - 5.5 定位问题②：SP 分支与标准 vsomeip 的 UDS 协议不兼容
   - 5.6 定位问题③：SP 库与标准头文件 ABI 不兼容（编译 RM 宿主失败）
   - 5.7 转机：用 C++ 服务端二进制当 RM 宿主
   - 5.8 定位问题④：空 pcap 造成 RM 空循环饿死
   - 5.9 定位问题⑤：RM 宿主不能提供服务（遮蔽远程）
   - 5.10 定位问题⑥：0x000E 组 0x0000 订阅无法远程投递
6. [关键技术结论表](#6-关键技术结论表)
7. [排障速查表](#7-排障速查表)

---

## 1. 背景与目标

### 1.1 原始工程

从板子上拉取到 `to_longjie_demo_20250625.zip`，包含比亚迪 AR-HUD 的 SOME/IP 通信实现：

| 文件 | 说明 |
|------|------|
| `build/hud_huifang_client` / `_x86` | **客户端**二进制（aarch64 / x86_64），已烧录在板子上 |
| `build/hud_pcap_huifang_server` / `_x86` | **C++ 服务端**二进制：回放 out.pcap 发送事件 |
| `build/someip_arhud01.json` | 客户端配置（**已烧录，无法修改**） |
| `build/someip_arhud01_pcap_server.json` | C++ 服务端配置 |
| `libs/lib_bst_t517/`、`libs/lib_x86/` | SP 分支 vsomeip 库（`libsomeip.so` 等） |
| `build/out.pcap` | 真实抓包（1659 包，时长 3.6 秒，事件源 `192.168.195.3` → 客户端 `192.168.195.11`） |
| `hud_huifang_client.cpp` / `hud_pcap_huifang_server.cpp` | 客户端/服务端源码 |
| `ArHudSomeipDataType.h` | 23 种数据类型定义 |

**客户端本质**：`SomeipCom`（SP 协议栈封装类）内部持有标准 `vsomeip_v3::runtime` /
`application` —— **底层就是 vsomeip v3**，只是被比亚迪二次封装（加了 CRC32 Checksum、
自定义配置解析等）。它按 `clientSubscribeCallbackFuncRegist(svc, inst, event, group, cb, param)`
注册 23 个事件的回调，收到事件后 `SPDeserialization` 反序列化并打印字段 + 计数。

### 1.2 客户端配置的关键内容（已烧录，不能改）

```jsonc
{
  "unicast": "192.168.195.11",     // 板子 IP
  "network": "arhud01",
  "applications": [{ "name": "arhud02", "id": "0x1002" }],
  "clients": [
    // 11 个服务 / 23 个事件；major=1；客户端接收端口 52001-52012
    // 0x000E 用的是 per-event 的 "event_groups":"0x1101"（字符串形式）—— 这是个坑！
  ],
  "routing": "arhud01",            // ★ 指向一个"本机不存在"的应用名
  "service-discovery": { "enable": "true", "multicast": "224.0.2.4", "port": "30490", ... }
}
```

**三个无法绕开的硬点**：
1. `routing=arhud01`：客户端作为 **RM 代理（Proxy）**，必须连到本机 UDS 的 RM；
2. `0x000E` 三个事件：SP 包装器只读顶层 `event_group` 字段，per-event 的 `event_groups`
   字符串解析失败 → 实际以 **eventgroup 0x0000** 订阅；
3. 订阅版本 `major=1`。

### 1.3 目标

写一个 **Python 服务端**，让板子上这个"配置已烧录"的客户端能正确订阅并收到数据。
客户端配置**一行不改**。

---

## 2. 最终方案：RM 宿主架构

### 2.1 架构总览（实际部署拓扑）

**实际部署**：Python 服务端跑在**本机**（替代原 C++ 服务端），通过**车载以太盒子**
（透明网桥）连接开发板；板子上只有**既有 SOME/IP 中间件**（托管 RM）和**已烧录的客户端**，
什么都不用新增、不用改动。

```
本机 / PC (Python 服务端 = C++服务端替代者)        板子 (严格管控, 零改动)
┌──────────────────────────────────┐   车载以太盒子   ┌─────────────────────────────┐
│ Python 服务端                     │   (透明网桥)    │ ① 既有 SOME/IP 中间件         │
│ (vsomeip_py + 标准 3.4.10)       │◄──SD多播+UDP──►│    (SP 分支, 托管 arhud01 RM) │
│  · 11 应用 offer 23 事件          │                │ ② 原版客户端（配置烧录不动）   │
│  · major=1                       │                │    routing=arhud01           │
│  · 0x000E 额外 offer 组 0x0000    │                │    → UDS 连接 ① 的 RM        │
│  · 载荷: out.pcap 回放+生成        │                │                             │
└──────────────────────────────────┘                └─────────────────────────────┘
```

**与原始部署（C++ 服务端）的对应关系**：

| 原始部署 | Python 方案 | 位置 |
|----------|-------------|------|
| C++ 服务端 `hud_pcap_huifang_server`（回放 out.pcap 发数据） | **Python 服务端** `hud_server_longjie.py`（同样回放 out.pcap + 生成缺失事件） | 本机，经车载以太盒子连板子 |
| 板子 SOME/IP 中间件（托管 arhud01 的 RM） | **不变**（既有程序） | 板子 |
| 客户端 `hud_huifang_client`（配置烧录） | **不变** | 板子 |

数据流（客户端视角与原始部署完全一致）：
```
客户端订阅(组) --UDS--> 板子中间件RM --SD多播 Find/Subscribe--[车载以太盒子]--> 本机Python服务端
本机Python服务端 ACK + 事件 --UDP单播--[车载以太盒子]--> 板子中间件RM --UDS--> 客户端回调
```

### 2.2 三个关键组件

**① RM 宿主**（实际部署中 = 板子既有 SOME/IP 中间件）
- 作用：托管 `arhud01` 的 routing manager（UDS socket `/tmp/arhud01-0`），替本地客户端
  与远端做 SD 发现、订阅转发、事件回传。**实际部署中它已经存在**（板子中间件），无需新增。
- 前提确认：板子中间件**不应 offer 这 11 个服务**（它只托管 RM + 转发 SD）。
  若它 offer 了服务，本地 offer 会遮蔽远程 Python 服务端（见 5.9 问题⑤），需在中间件
  配置里关闭 offer。
- 自动化测试里用 `hud_pcap_huifang_server` 二进制（SP 分支）**模拟**板子中间件：
  - `longjie_py/someip_arhud01_rm_host.json`：**空 `services`** 配置 —— 不提供任何服务；
  - `longjie_py/rm_host_silent.pcap`：**静默 pcap**（60 个间隔 1 秒的 SD 包）——
    SD 包被解析器跳过、不发送，时间戳提供喘息，避免空循环饿死 RM 线程。

**② 原版客户端**：配置保持原样（仅确认 `unicast` 是板子 IP）。

**③ Python 服务端**（`longjie_py/hud_server_longjie.py`）：
- 11 应用 / 23 事件，offer 版本 `major=1`；
- 0x000E 三个事件在正常组（0x1101/0x1102/0x1103）之外，**额外 offer eventgroup 0x0000**
  （兼容固定配置客户端的组 0 订阅，虽然后续发现 SOME/IP-SD 组 0 无法承载事件，见 5.10）；
- 0x000C:8002/8003、0x010A:8001/8003 配置 `someip-tp`（超 1400B 分片）；
- 载荷：out.pcap 回放（含 SOME/IP-TP 重组）+ 缺失事件生成（自动补
  `Checksum = CRC32(payload[4:])`）。

### 2.3 为什么必须这样设计（一句话版）

> 客户端 `routing=arhud01` 决定了它**只能通过本机 UDS 工作**，而 UDS 的 RM 只能由
> **SP 分支进程**托管（标准 vsomeip 3.4.10 与 SP 分支的 UDS 协议不兼容）。所以板子上
> 必须保留一个 SP 分支的 RM 宿主；Python 服务端负责在**网络侧**提供数据。

---

## 3. 部署指南

### 3.1 实际部署：板子零改动，本机只跑 Python 服务端

**板子侧**：什么都不用做（中间件 + 客户端都是既有程序）。只需确认：
- 中间件在托管 `arhud01` 的 RM（`/tmp/arhud01-0` 存在）；
- 中间件**不 offer** 这 11 个服务（否则遮蔽远程 Python 服务端）。

**本机侧**（Python 服务端，替代 C++ 服务端）：
```bash
# 依赖：Python 3.10 + vsomeip_py（构建方法见 docker/Dockerfile）
python3 longjie_py/hud_server_longjie.py
# 环境变量（按需）：
#   ARHUD_UNICAST=<本机在车载以太盒子网络的 IP>   （默认自动探测）
#   ARHUD_PCAP=<out.pcap 路径>                    （默认自动探测仓库内 pcap）
#   ARHUD_FILL_MISSING=1                          （默认，缺失事件生成数据）
```

**车载以太盒子**（透明网桥）要求：
- PC 与板子同网段（板子固定 `192.168.195.11`，PC 配同网段 IP）；
- 多播 `224.0.2.4:30490` 跨盒子转发（透明网桥默认转发多播）；
- UDP 放行：30490、51400-51409、52001-52012。

### 3.2 PC 侧（Python 服务端）

```bash
# 依赖：Python 3.10 + vsomeip_py（构建方法见 docker/Dockerfile）
python3 longjie_py/hud_server_longjie.py        # ARHUD_UNICAST=<PC IP> 可选
```

### 3.3 网络要求

- PC 与板子同网段互通；UDP 放行；
- SD 多播 `224.0.2.4:30490` 可达（同网段/交换机放行 IGMP）。

### 3.4 自动化验证

```bash
# 双容器模拟：A=Python服务端，B=RM宿主+原版客户端（架构自适应 aarch64/x86_64）
bash docker/integration_test_longjie_fixedcfg.sh
```

---

## 4. 实测结果

| 指标 | 结果 |
|------|------|
| 客户端配置 | **零修改**（routing=arhud01、0x000E 原样） |
| 收到事件 | **16/17 个 pcap 事件 + 生成事件**（每事件 200+ 条；LaneLine 588 条） |
| 注册 | **0 次注册超时**（正确启动顺序下） |
| 服务订阅 | 11 个服务 REMOTE SUBSCRIBE 全部 accepted + ACK |
| RM 宿主发送 | **0 条**（静默 pcap 生效） |
| 大消息 TP | 0x000C:8003（51KB）正常分片送达 |
| 已知限制 | 0x000E:8001（组 0x0000 订阅）无法经 SD 远程投递 |

CI（GitHub Actions，amd64）run #19：17 步全部通过，含固定配置测试（x86 二进制路径）。

---

## 5. 问题定位全记录（核心章节）

> 这一章按时间顺序还原完整排查过程。每个问题都是独立的故事：
> **现象 → 用什么方法诊断 → 根因 → 怎么解决**。

### 5.1 拆解板子工程，理解客户端

**现象**：拿到 zip，不知道客户端到底是什么协议栈。

**诊断方法**：
- `file` 看二进制架构（aarch64 / x86_64 ELF）；
- `readelf -d` 看动态依赖 → 客户端只依赖 `libsomeip.so`（SP 分支库）；
- `strings` 看符号 → 出现 `SomeipNS::SomeipCom`、`vsomeip_v3::application_impl`、
  `SP_POLYNOMIAL 0x04C11DB7`（CRC32）；
- 读 `include/vsomeip/SomeipCom.hpp` → **发现 SomeipCom 内部就是标准 vsomeip v3 的
  runtime + application**！

**根因理解**：客户端 = vsomeip v3 + 比亚迪封装（SP 栈）。它和标准 vsomeip 协议兼容，
但封装层有几个自定义行为（配置解析、CRC32 校验、注册回调）。

**产出**：23 事件注册表、端口/实例映射表（0x010A 特殊 instance=0x0001、端口 52001）、
大端序列化规则、Checksum = CRC32(payload[4:])（用 zlib 与 pcap 实测比对确认）。

### 5.2 第一版方案：跨机自托管 RM（配置可改，19/23）

**现象**：想直接让 Python 服务端 + 板端客户端通信。

**诊断与迭代**（此处只列结论，细节见 5.4-5.10 同源）：
- 客户端配置 `major=1` → 服务端必须 `version=(1,0)` offer，否则订阅 NACK；
- 客户端 `routing=arhud01` 在本机没有 arhud01 → 客户端卡死（register timeout）→
  **把配置临时改为 `routing=arhud02`（自托管 RM）** 后走网络模式；
- 0x000C:8003 是 51KB 大消息 → 标准 vsomeip 必须显式 `someip-tp` 才分片（SP 分支自动）；
- 0x000E 订阅组=0x0000（SP 包装器只读顶层 event_group）→ 配置拆分 0x000E 为三条带
  `event_group` 的记录；
- 生成载荷补 CRC32 → 客户端反序列化字段**全部正确**（RTK/IMU/HudRoad 值都对）。

**结果**：客户端配置改动后，**19/23 事件**收到，自动化测试 PASS，CI 全绿。

### 5.3 用户提出硬约束：客户端配置不能改

**问题**：客户端程序（含配置）已烧录在板子，`routing=arhud01` 等全部固定。
这推翻了"改配置"路线，需要另寻他路。

**关键思考**：`routing=arhud01` 意味着客户端必须以 **RM 代理**方式工作 —— 它必须连到
本机 UDS 的 RM。那么问题变成：**谁能在板子上托管这个 RM？Python 服务端能吗？**

### 5.4 定位问题①：客户端必须有本地 RM（UDS）

**现象**：把客户端单独跑起来（`routing=arhud01`，本机无任何进程），日志：
```
Instantiating routing manager [Proxy].
Client [1002] is connecting to [0] at /tmp/arhud01-0
Client 0x1002 request client timeout! Trying again...
```
客户端永远卡在"请求客户端 ID / 注册"，**不发送任何 SD 数据**。

**诊断方法**：
- 读 vsomeip 源码 `application_impl.cpp` 的 RM 判定逻辑：
  ```
  routing host name == 自身名字 → 本应用当 RM 宿主
  否则 → 当 RM 代理（Proxy），连 /tmp/<network>-0 的 UDS socket
  ```
  代理连不上 RM 时**不会回退自托管**（只有 `routing` 为空或等于自身时才会自托管）；
- 抓包确认：客户端 0 SD 包（它根本没进入网络交互）。

**根因**：客户端配置 `routing=arhud01`，本机必须有一个名为 arhud01 的进程托管 RM，
否则客户端完全无法工作 —— 这与服务端是谁无关，是客户端自身的硬性要求。

**结论**：方案必须是"板子保留 RM 宿主 + Python 服务端网络侧提供数据"。

### 5.5 定位问题②：SP 分支与标准 vsomeip 的 UDS 协议不兼容

**现象**：让 Python 服务端（标准 vsomeip 3.4.10）在本机托管 RM
（应用名 `arhud01`、`network=arhud01`），UDS socket `/tmp/arhud01-0` 已创建；
客户端连接上了，但：
```
Client [1002] is connecting to [0] at /tmp/arhud01-0
Client 0x1002 request client timeout! Trying again...
```
（与 5.4 症状相同，但这次 RM 明明存在。）

**诊断方法**：
- 先检查 socket 路径是否一致：SP 分支日志 `Routing endpoint at /tmp/arhud01-0`；
  标准版日志 `Routing root @ /tmp/arhud01-0`。发现标准版默认网络名是 `"vsomeip"`
  → 路径是 `/tmp/vsomeip-0`！在 Python 配置里补上 `"network": "arhud01"` 后路径一致了；
- 路径一致后仍超时 → 怀疑 **UDS 内部协议（REGISTER 报文格式）不同**。
  两边的 `REGISTER/REGISTERED_ACK` 消息序列化格式在不同版本间有差异（3.4.10 引入
  "routing root" 机制），SP 分支基于更早版本 → 标准 stub 不认 SP 代理的 REGISTER。

**根因**：**SP 分支（板端 libsomeip.so）与标准 vsomeip 3.4.10 的 UDS 通道协议不兼容**。
Python 服务端（vsomeip_py 绑定标准 3.4.10）**无法**托管 SP 客户端的 RM。

**结论**：RM 宿主必须用 SP 分支进程；同机 UDS 直连方案排除，走"板子 RM 宿主 + 跨机"。

### 5.6 定位问题③：SP 库与标准头文件 ABI 不兼容（编译 RM 宿主失败）

**现象**：想写一个"最小 RM 宿主"（只托管 RM、不提供服务），用 SP 库编译：
```cpp
#include <vsomeip/vsomeip.hpp>
auto app = vsomeip_v3::runtime::get()->create_application("arhud01");
app->init(); app->start();
```
编译通过，但运行即崩溃：
```
creating app arhud01
app created, init...
terminate called after throwing an instance of 'std::length_error'
  what():  basic_string::_M_create
```

**诊断方法**：崩溃发生在 `init()` —— 用标准 3.4.10 头文件调 SP 库的 `init()`，
函数签名/结构体布局不一致（`std::string` 成员布局差异等）导致运行时 ABI 崩溃。
vsomeip_py 加载 SP 库时也出现同样的 `std::length_error`。

**根因**：**标准 vsomeip 3.4.10 头文件与 SP 分支库 ABI 不兼容**。没有 SP 分支自己的
头文件（zip 里只有封装层头文件），无法重新编译 SP 兼容的 RM 宿主。

**结论**：放弃自编 RM 宿主 → 改用**现成的 SP 分支二进制**当 RM 宿主。

### 5.7 转机：用 C++ 服务端二进制当 RM 宿主

**想法**：板子上已有的 `hud_pcap_huifang_server`（SP 分支编译）本身就是"arhud01 应用 +
RM 宿主"。它的行为和客户端天然兼容（原始部署就是这么工作的）。
**在自动化测试中我们用这个二进制模拟"板子既有 SOME/IP 中间件"的 RM 角色**——
实际部署里这个角色由板子中间件承担，无需任何新程序。

**首次尝试**：直接跑 C++ 服务端（原版全配置）+ 客户端，同机：
- 服务端 RM 日志出现 `REGISTERED_ACK(1002)` + 23 个 `REGISTER EVENT` —— **客户端注册成功**！
- 但客户端随后仍报 `register timeout`，且收不到事件。

**诊断**：注册成功后又超时 → 注册握手机敏（时序竞争）；服务端主线程在忙回放 pcap。

### 5.8 定位问题④：空 pcap 造成 RM 空循环饿死

**现象**：给 RM 宿主配了**空 pcap**（只有文件头）想让它"不发送任何数据"，结果：
- RM 日志循环出现 `Didn't receive a multicast SD message for 1100ms` +
  `Leaving/Joining the multicast group`；
- 客户端注册/订阅全部不稳定，事件时断时续。

**诊断方法**：
- 读 C++ 服务端源码 `hud_pcap_huifang_server.cpp`：
  ```cpp
  while(1) {                    // LOOP_HUIFANG = 1
      pcap_open_offline(pcapFile);
      while (pcap_next_ex(...) == 1) { ...按时间戳 sleep 后发送... }
      // 文件读完 → break → 外层 while(1) 立刻重新打开 → 空 pcap 立即 EOF
  }
  ```
  空 pcap → 立即 EOF → **外层死循环空转**，主线程满负荷，RM 的 io 线程被拖垮；
- 用 `top` 确认进程 CPU 占用，用 `cat /proc/net/igmp` 看多播 join 状态
  （IGMP 表里 224.0.2.4 反复增删 —— join/leave 循环的证据）。

**根因**：**RM 宿主需要一个"有喘息"的 pcap**。空 pcap 让回放循环变成忙等。

**解决**：构造**静默 pcap** —— 60 个间隔 1 秒的 SOME/IP-SD 包。解析器对 SD 包
（`service=0xFFFF`）直接 `continue`（**不发送**），但包间的时间戳让主线程
`sleep(diff)`，RM 每 60 秒才有一次循环，且循环内零发送。

**验证**：RM 宿主日志 `发-->` 行数 = **0**；客户端注册稳定、事件持续到达。

### 5.9 定位问题⑤：RM 宿主不能提供服务（遮蔽远程）

**现象**：RM 宿主用**原版全 services 配置**时，服务端日志出现：
```
routing_manager_impl::add_routing_info: rejecting routing info.
Remote: 172.20.0.2 is trying to offer [0007.0007.1.0] on port 51405
offered previously on this node: [0007.0007.1.0]
```

**根因**：RM 宿主本地 offer 了同样的服务 → 客户端的订阅走**本地路径**，数据来源是
RM 宿主应用（它不发数据）→ 客户端收不到 Python 服务端的数据。

**解决**：RM 宿主配置 **`services: []`**（空）→ 本地不 offer → 客户端的订阅由 RM
经 SD 转发给远程 Python 服务端 → 事件经网络回传。`someip_arhud01_rm_host.json` 即此配置。

### 5.10 定位问题⑥：0x000E 组 0x0000 订阅无法远程投递

**现象**：其余 16 个事件全部正常（每事件 200+ 条），唯独 **0x000E:8001 = 0**。
而它明明在 pcap 里有数据（37 条 943B 消息）。

**诊断方法**（逐层排除）：
1. **客户端侧**：日志显示 `SUBSCRIBE(1002): [000e.000e.0000:8001:1]` —— 组 **0x0000**
   （SP 包装器读不到 per-event `event_groups` 字符串，回退到 0）；
2. **服务端侧**：`SUBSCRIBE(0000): [000e.000e.0000:ffff:1] true 1 accepted` +
   `SUBSCRIBE ACK` —— 订阅被接受；服务端 `[send]` 日志显示 0x000E/8001 已发 769 条；
3. **网络侧**：在 RM 容器抓包 —— **端口 51404（0x000E）一个包都没到**，而 51402（0x000C）
   流量正常。说明服务端的 0x000E 事件"发送了"但**没出本机**；
4. **源码侧**：`offer_event` 把事件注册进组 0x0000（`register_event` 无组 0 校验），
   但 **SOME/IP-SD 协议中 eventgroup 0x0000 是保留值**，SD OfferService 条目无法把
   事件挂到组 0 → 订阅接受了，事件却无法路由。

**根因**：SP 包装器把 per-event `event_groups` 解析失败 → 用组 0 订阅；而
**SOME/IP-SD 的组 0 不承载事件**。板端同机（UDS 直连，原始部署）时组不参与 SD
校验，所以原始场景不受影响；跨机走 SD 时该事件无法投递。

**结论**：`0x000E:8001` 是固定配置方案的已知限制（1/23 事件），文档与测试均标注。
服务端保留组 0x0000 的 offer（无害，万一某些环境可用）。

### 5.11 启动顺序敏感（最终收尾）

**现象**：同样的部署，有时客户端正常收数据，有时一直 `register timeout`。

**诊断**：客户端注册握手（`REQUEST_CLIENT_ID → REGISTERED_ACK`）有约 1 秒超时，
RM 刚启动时 SD 加入多播组尚未稳定，客户端过早连接会触发超时重试循环。

**解决**：固定启动顺序：**Python 服务端 → RM 宿主 → 等 8 秒 → 客户端**。
测试脚本 `integration_test_longjie_fixedcfg.sh` 已固化该顺序；在板子上首次运行不稳时
重试或拉长间隔即可。

---

## 6. 关键技术结论表

| # | 结论 | 证据/出处 | 影响 |
|---|------|-----------|------|
| 1 | 客户端 = vsomeip v3 + SP 封装（SomeipCom） | SomeipCom.hpp、strings | 协议与标准兼容，可用 vsomeip_py 服务端 |
| 2 | 客户端 `routing=arhud01` 必须有本地 RM | application_impl.cpp 源码 | 板子必须保留 RM 宿主进程 |
| 3 | SP 分支与标准 3.4.10 UDS 协议不兼容 | 实测 register timeout | Python 服务端无法托管该 RM |
| 4 | 标准 3.4.10 头文件与 SP 库 ABI 不兼容 | std::length_error 崩溃 | 无法自编 SP 兼容 RM 宿主 |
| 5 | C++ 服务端二进制可当"空服务 RM 宿主" | REGISTERED_ACK 实测 | 板子上无需新程序 |
| 6 | RM 宿主必须空 services | add_routing_info 拒绝日志 | 避免遮蔽远程 Python 服务端 |
| 7 | RM 宿主必须用"有喘息"的 pcap | 空 pcap 忙等 | 静默 pcap（只含 SD 包） |
| 8 | offer 必须 major=1 | 订阅 NACK 实测 | 服务端 version=(1,0) |
| 9 | 超 1400B 必须显式 someip-tp | Dropping to big message | 0x000C/0x010A 大事件 |
| 10 | Checksum = CRC32(payload[4:]) | zlib 与 pcap 比对 | 生成载荷自动补 |
| 11 | 0x000E 组 0x0000 无法远程投递 | 抓包 51404 空 | 已知限制（1/23） |
| 12 | 启动顺序敏感 | 注册握手机敏 | 服务端→RM宿主→等8s→客户端 |

---

## 7. 排障速查表

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 客户端 `register timeout` 循环 | RM 未启动 / 顺序不对 / RM 是标准版 | 先启动 RM 宿主（SP 分支），等 8s 再启客户端 |
| 客户端 `request client timeout` | 本机没有 /tmp/arhud01-0 | 确认 RM 宿主在跑（`ls /tmp/arhud01-0`） |
| 服务端 `Dropping to big message` | 大事件没配 someip-tp | 0x000C:8002/8003、0x010A:8001/8003 配 TP |
| 订阅被 NACK / 服务不可用 | major 不匹配 | 服务端 `version=(1,0)` |
| RM 宿主 `Didn't receive multicast SD` | 空 pcap 忙等 / 多播不通 | 换静默 pcap；查网段多播放行 |
| 客户端收不到某个事件 | 事件不在 pcap / 组 0x0000 限制 | 看 pcap 是否有该事件；0x000E:8001 为已知限制 |
| 客户端收到数据但字段乱 | 生成载荷类型布局不符 | 该事件改用 pcap 数据（放 pcap 里自动回放） |
| 双机不互通 | 多播/防火墙 | 同网段；放行 UDP 30490、51400-51409、52001-52012 |

---

*文档配套代码：`longjie_py/`（服务端 + 配置模板 + 静默 pcap）、`docker/integration_test_longjie_fixedcfg.sh`（自动化测试）。*
