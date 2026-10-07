# pcap 回放与发布指南（重点：`lipeng20260228/old` 那批抓包）

> 本文回答一件事：**怎么让本工程回放并把 `lipeng20260228/old/` 下的 pcap 数据发布到板端**，
> 以及这批数据里有什么、和参考实现（`to_longjie_demo_20250625/hud_pcap_huifang_server.cpp`，
> 也就是 `old/` 里那两个二进制对应的源码）有哪些对齐/差异。
>
> 配套：`README.md`（快速开始）、`CODE_GUIDE.md`（代码详解）、`DEPLOYMENT.md`（部署）。

---

## 1. 三条命令

```bash
cd arhud_python_server

# ① 回放前先体检（纯 Python，不需要库；看清 pcap 里有什么、服务表覆不覆盖得住）
python3 tools/analyze_pcap.py /Users/wunengfa/Desktop/someip/lipeng20260228/old

# ② 编译库（真机 aarch64 / x86_64）
cd src && make libarhud_server.so SP_LIBS=../libs/arm64 && cd ..   # 或 ../libs/x86_64

# ③ 回放 + 发布整个目录（out.pcap 优先，其余按名字排序；auto 自动选表）
LD_LIBRARY_PATH=libs/arm64 python3 python/demo_replay.py \
    /Users/wunengfa/Desktop/someip/lipeng20260228/old <本机IP> \
    --profile auto --timing capture --once
```

板端客户端要先起好、订阅稳定再回放（真机建议 `--delay 15~25`）。不带 `--once` 就是无限循环。

---

## 2. 这批抓包里到底有什么（实测）

| pcap | 大小 | 包数 | 时长 | 通知 | TP 重组 | **合计** | TP 缺口丢弃 |
|------|------|------|------|------|---------|---------|------------|
| `old/out.pcap` | 28.1 MB | 25 078 | 51.2 s | 3 902 | 1 466 | **5 368** | 1（文件尾半条） |
| `old/output3.pcap` | 260.0 MB | 265 550 | 338.9 s | 30 150 | 7 518 | **37 668** | 0 |
| `old/outputblanket.pcap` | 28.1 MB | 25 078 | 51.2 s | 3 902 | 1 466 | **5 368** | 1（文件尾半条） |
| 合计（3 个文件） | 316 MB | 315 706 | 441 s | | | **48 404** | 2 |

> `out.pcap` 与 `outputblanket.pcap` **内容完全相同**（md5 均为 `b418ad2663e0673fbb25debda82e8ad7`），
> 目录整体回放会重放两遍，不想重复就只传 `out.pcap`。

`output3.pcap` 里还有 116 996 个 TCP 报文（目的端口 35958，非 SOME/IP）与
2 369 个 SOME/IP-SD 报文，都会被正确跳过；`out.pcap` 尾部有一条第 9 分片缺失的 TP 消息
（抓包被截断），新解析器**整条丢弃**而不是发出半截数据。

**事件覆盖**：这三个文件一共出现 **24 个 (service,event)**，其中 **10 个不在参考配置 `old`（11 服务/23 事件）里**：

| 缺失事件 | 条数（out.pcap） | 说明 |
|----------|------------------|------|
| `0x0007:0x8003` / `0x0007:0x8004` | 36 / 58 | 服务 0x0007 已在表内，事件未登记 |
| `0x0017:0x8002` | 1 | 同上 |
| `0x8202:0x8001/8006/8007/8008/8009/800A/800B` | 2/1/37/8/36/1/7 | 同上 |

合计 **187 条**（占 out.pcap 的 3.5%）。不登记它们，回放时协议栈侧没有对应事件，
这 187 条就"发不出去"。

---

## 3. 服务表：`old` 保持与参考配置一致，新增可选 `old-capture`

| profile | 规模 | 来源 | 用途 |
|---------|------|------|------|
| `old`（默认） | 11 服务 / 23 事件 | 与 `old/someip_arhud01_pcap_server.json` **逐条一致** | 正式联调（与板端配置一致） |
| `old-capture` | 11 服务 / 33 事件 | `old` + 上表 10 个"抓包实测"事件 | **完整回放/发布**这批抓包 |
| `bplus` | 6 服务 / 38 事件 | `BPlus/someip_arhud01_pcap_server_B+.json` | 新一代接口 |
| `auto`（Python 侧） | 自动 | 按 pcap 内容挑"能全覆盖的最小表" | 不想手工选表时用 |

```bash
ARHUD_SERVICE_PROFILE=old-capture LD_LIBRARY_PATH=libs/arm64 python3 python/demo_replay.py <目录> <IP>
# 或
python3 python/demo_replay.py <目录> <IP> --profile auto
```

为什么要单独一个 profile、而不是直接往 `old` 里加 10 个事件：
`old` 的价值就是"和参考配置一字不差"，直接改会让这份对齐关系失效、也难以回溯；
扩展事件名参考配置里并没有（只知道事件 ID），故用 `ext_<svc>_<evt>` 记号，事件组按同服务既有事件取 `0x1101`。

Python 侧可以一键核对覆盖率：

```python
from arhud_py import ArHudServer
prof, missing = ArHudServer.best_profile_for_pcaps("/path/to/pcap_dir")   # → ('old-capture', set())
srv = ArHudServer.for_pcaps("/path/to/pcap_dir")                          # 自动选表并创建
```

---

## 4. 回放节奏：`capture`（对齐参考实现）与 `interval`

参考实现 `hud_pcap_huifang_server.cpp` 的做法是：用 libpcap 逐包读，
**按抓包记录里相邻包的时间差 sleep**（`timersub(current, previous)` + `sleep/sleep_for`），
读完一轮再从头开始（`LOOP_HUIFANG 1`），并且只读**可执行文件所在目录**的 `out.pcap`。

本工程把同样的语义做成 C 接口，并补上"批量/限速/限轮"：

| 选项 | 含义 |
|------|------|
| `--timing capture`（默认） | 按 pcap 时间戳回放：`out.pcap` 约 51 s、`output3.pcap` 约 339 s |
| `--speed N` | `capture` 模式倍速：`--speed 10` → 51 s 的抓包 5.1 s 放完（联调用） |
| `--timing interval --interval-ms 10` | 固定间隔（老行为；"慢速喂"给板端用） |
| `--once` / `--loops N` | 只跑一轮 / 跑 N 轮（默认无限循环） |
| `--delay S` | 起播前等待（等客户端订阅稳定，真机建议 15~25 s） |
| 目录 | `out.pcap` 优先，其余按名字排序；与参考实现"读目录下 out.pcap"的习惯兼容 |

`capture` 模式下**每个文件各自以首条消息为 0 点计时**，多文件串行回放不会把
文件之间的空档算进来。

---

## 5. 这次为了"能回放 260 MB 抓包"改了什么

| 问题（旧实现） | 现在 |
|----------------|------|
| `parse_pcap` 把**整个文件**的消息/分片先全读进内存（output3.pcap 峰值 300 MB+） | `arhud::PcapStream` **流式**解析：边扫边重组边吐消息，内存只与"在途分片"有关（MB 级）；循环回放每轮重新开流，不缓存消息 |
| TP 分片按偏移排序后**无条件拼接** | 按偏移**去重**后再拼：抓包被复制/重复投递时不会把同一段拼两次 |
| 缺口/半截消息会照发 | 缺口不补齐的消息**整条丢弃**并计入统计（`tp_dropped`） |
| 只支持单文件 + 固定间隔 | 多文件/目录、`capture` 时间戳节奏、倍速、限轮、起播延迟 |
| 只有总计数 | 逐 `(service,event)` 的 attempted/sent/unregistered 报告（JSON），回放后能直接核对"发全了没有" |
| 未登记事件与发送失败混在一起 | `unregistered` 单独统计（配合 `old-capture` 判断表选得对不对） |

`BPlus/out.pcap` 是"重复分片"的现成例子：36 片重复，旧实现会把 18 条消息拼坏；
新实现去重后 **14 667/14 667** 全部正确重组（与工程文档里记录的实测值一致）。

---

## 6. 验证（可复现）

```bash
# 本机（macOS/Linux，不需要协议栈）：解析/重组/回放引擎/Python 层全链路自测
tools/local_selftest.sh /Users/wunengfa/Desktop/someip/lipeng20260228/old

# 容器（用真实 SP 协议栈编译并回放；本机是 Apple Silicon 时默认 linux/arm64 + libs/arm64）
tools/container_replay_test.sh /Users/wunengfa/Desktop/someip/lipeng20260228/old
```

实测结果：

| 验证项 | 结果 |
|--------|------|
| C++ 解析器 vs 纯 Python 独立实现（`tools/analyze_pcap.py`）逐文件条数 | **完全一致**（5368 / 37668 / 5368 / B+ 14667） |
| 回放引擎（按抓包节奏） | 48 404 条 = 解析 48 404，`failed=0`，`tp_dropped=2`（两处文件尾截断） |
| 真实 SP 协议栈（容器 aarch64 + `libs/arm64`）跑 `old/out.pcap`，profile=`old` | 5 368 条经发送接口，其中 **187 条 `unregistered`**（正是那 10 个未登记事件） |
| 同上，profile=`old-capture` | 5 368 条，`unregistered=0` |
| 真实 SP 协议栈跑**整个目录** | 48 404 条全部发布，0 失败、0 表外；50 倍速 8.8 s 跑完 |
| 3 轮 interval 循环 | 16 104 = 5 368 × 3 |

---

## 7. 与参考实现的对齐说明

参考实现在仓库里能找到源码：`to_longjie_demo_20250625/hud_pcap_huifang_server.cpp`
（`old/x86_server_ArHud_huifang_pcap_B`、`old/server_ArHud_huifang_pcap_B` 即其编译产物）。
逐条对齐关系：

| 参考实现 | 本工程 |
|----------|--------|
| libpcap `pcap_open_offline(<exe目录>/out.pcap)` | 自研流式 pcap 解析（`arhud_pcap.cpp`），目录用法保留"out.pcap 优先" |
| Ethernet + VLAN 0x8100 → IPv4 → UDP → SOME/IP | 同；额外支持 0x88A8/0x9100 多级 VLAN 与 Linux SLL |
| `message_type==0x22` 按 `(service, method, session)` 重组，TP 偏移是**字节** | 同（并按偏移去重、允许乱序、缺口整条丢弃） |
| 跳过 SD（`0xFFFF:0x8100`）与 `someip_version != 1` | 同 |
| instance：`0x010A → 0x0001`，其余 = service | 同（`instance_of()`，由服务表构建） |
| 23 个事件表 | `arhud_services.h` 的 `old`（11 服务/23 事件） |
| 按抓包时间差 `sleep` 回放，读完循环 | `ReplayOptions.timing = kTimingCapture`（另可倍速/限轮） |
| 对未登记事件也调用 `SPServerSendNotify` | 同（照发，同时单独统计 `unregistered`） |
| TCP 也会当 SOME/IP 试解析（`dest_port != 22`） | **不解析 TCP，仅计数**（见下） |

> 关于 TCP：参考实现会拿 TCP 载荷当 SOME/IP 头试解析。实测 `output3.pcap` 的
> 116 996 个 TCP 报文（目的端口 35958）**没有一个能通过** `someip_version==1` 校验，
> 所以跳过 TCP 与参考实现的最终行为等价，且更安全（避免误判随机载荷）。

**为什么没有做"与参考二进制逐包对比"**：参考二进制是 x86-64，本机是 Apple Silicon，
只能跑 qemu 模拟；在容器里它始终卡在 `SPStart`（日志停在 `SOME/IP routing ready.`，
未打开 pcap），这与其运行手册要求的实车网络配置（`ifconfig ens37 …`、`ip route add 224.0.2.4 …`）
有关，也不排除模拟环境下的协议栈行为差异。同一容器里**本工程编译出的库**用同一份配置
可以正常 `SPStart` 并完整回放，因此改用"源码逐条对齐 + 两套独立解析器交叉验证"作为证据链。

---

## 8. 已知限制

1. **pcapng 不支持**：`PcapStream` 只认经典 pcap（本文这批都是经典 pcap）。拿到 pcapng 先
   `editcap -F pcap in.pcapng out.pcap` 或 `tcpdump -r in.pcapng -w out.pcap` 转换（报错信息里会提示）。
2. **TP 缺口丢弃是"整条丢"**：抓包丢片时该条消息不会发布（宁缺勿错）；条数记在报告的
   `tp_dropped` 里，可用于判断抓包质量。
3. **`0x000E:0x8001` 组 0 订阅的已知问题**仍存在（见 README「已知限制」）。
4. **大帧回放建议放慢**：`0x000C:0x8003`（最大 79 KB）、`0x010A:0x8003`（最大 49 KB）走 SOME/IP-TP
   分片，`--timing interval --interval-ms 10` 或 `--speed 1` 更稳；加速只建议用于演练。
5. **`old-capture` 的事件名是记号**（`ext_*`）：参考配置里没有这些事件的名字，只有事件 ID 参与发布，
   名字仅用于日志/统计展示。
6. `output3.pcap` 全程按抓包节奏回放需要约 339 秒；演练请用 `--speed`。

---

## 9. 相关文件

| 文件 | 作用 |
|------|------|
| `src/arhud_pcap.h/.cpp` | 流式 pcap 解析 + SOME/IP-TP 重组（去重/乱序/缺口） |
| `src/arhud_replay.h/.cpp` | 回放引擎（多文件、两种节奏、倍速、限轮、逐事件统计、JSON 报告） |
| `src/arhud_services.h` | 服务表（新增 `old-capture`）+ `services_json()` / `has_event()` |
| `src/arhud_server.h` | 新增 C 接口：`arhud_server_replay_start_ex` / `arhud_pcap_events` / `arhud_profile_events` 等 |
| `python/arhud_py.py` | `replay_dir()` / `for_pcaps()` / `replay_report()` / `pcap_events()` |
| `python/demo_replay.py` | 命令行：文件或目录、profile、节奏、倍速、轮数、体检、报告 |
| `tools/analyze_pcap.py` | 纯 Python 体检/对照实现 |
| `tools/pcap_selftest.cpp` | C++ 解析器自测（不需要协议栈） |
| `tools/replay_selftest.cpp` | 回放引擎自测（假发送器） |
| `tools/dryrun_server.cpp` | "演练版"库：不联网跑通 Python 全链路 |
| `tools/local_selftest.sh` / `tools/container_replay_test.sh` | 一键自测脚本 |
