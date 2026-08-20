# SOME/IP 测试 —— 手动运行教程

本文档教你**手动**跑通本仓库的全部测试（不需要 `bash docker/run_tests.sh` 自动化脚本）。
分三种环境：**Docker（推荐）** / **本机 Linux** / **Windows**。

> 自动化一键测试见：`docker/run_tests.sh`（10 步，CI 同款）。

---

## 0. 获取代码

```bash
git clone https://github.com/Couchy-wu/someip.git
cd someip
```

关键目录：
- `vsomeip_example/`：单服务 / 20 服务 / pcap 工具
- `hud/`：AR-HUD 23 服务/11 个服务（`new_describe.md` 场景）
- `windows/`：Windows 版
- `testdata/`：现成测试 pcap

---

## 方式一（推荐）：Docker 手动两终端

### 1) 构建镜像（首次 5-15 分钟，之后秒级）

```bash
docker build -t arhud-vsomeip-test -f docker/Dockerfile .
```

### 2) 启动一个常驻容器（挂载代码）

```bash
docker run --name arhud-manual -d \
  -v "$PWD/vsomeip_example:/app:ro" \
  -v "$PWD/hud:/hud:ro" \
  -v "$PWD/windows:/win:ro" \
  -v "$PWD/testdata:/testdata:ro" \
  arhud-vsomeip-test sleep 3600
```

### 3) 进入容器，准备运行目录

```bash
docker exec -it arhud-manual bash          # 终端 A
```

容器内：
```bash
rm -rf /tmp/run && mkdir -p /tmp/run && cp -r /app/* /hud/* /tmp/run/
cd /tmp/run
```

### 4) 终端 A：启动服务端

```bash
# 例 1：AR-HUD 23 服务（推荐看这个）
ARHUD_SD=true ARHUD_INTERVAL=0.1 python3 hud_server.py

# 例 2：单服务（pcap 回放）
# ARHUD_SD=true python3 server.py /testdata/test_arhud_000c_8003.pcap

# 例 3：20 服务
# ARHUD_SD=true python3 server_multi.py
```

看到 `[send] #1 svc=0x000A event=0x8001 ...` 持续输出即正常。

### 5) 终端 B：另开一个终端进同一容器，启动客户端

```bash
docker exec -it arhud-manual bash          # 终端 B
cd /tmp/run
```

```bash
# 与终端 A 的服务端对应：
ARHUD_SD=true ARHUD_EXIT_ALL=1 python3 hud_client.py      # 收齐 23 个事件后自动退出
# 或
ARHUD_SD=true ARHUD_EXIT_AFTER=5 python3 client.py        # 单服务，收 5 条退出
# 或
ARHUD_SD=true ARHUD_EXIT_ALL=1 python3 client_multi.py    # 20 服务
```

### 6) 查看结果

```bash
# 服务端发送结果（在终端 A 或另开终端）
grep "\[send\]" /tmp/run/server.log | head -5

# 客户端接收结果
docker exec arhud-manual bash -c 'grep "\[recv\]" /tmp/run/client.log | head -10'
```

### 7) 收尾

```bash
docker rm -f arhud-manual
```

---

## 方式二：本机 Linux（已装好 vsomeip + vsomeip_py）

安装参考 `docker/Dockerfile`（Ubuntu 22.04 + vsomeip 3.4.10 + vsomeip_py + scapy）。

```bash
cd someip/hud

# 终端 A：服务端
python3 hud_server.py

# 终端 B：客户端（收齐 23 事件自动退出）
ARHUD_SD=true ARHUD_EXIT_ALL=1 python3 hud_client.py
```

pcap 回放（服务端从 `testdata/` 的现成 pcap 发数据）：

```bash
ARHUD_PCAP=../testdata/test_arhud_hud_23events.pcap python3 hud_server.py
```

多网卡/非本机部署时指定 IP：`export ARHUD_UNICAST=192.168.x.x`（两边一致）。

---

## 方式三：Windows（需先装好 justinlhudson 分支 vsomeip）

```powershell
cd someip\windows
set ARHUD_UNICAST=10.13.90.164        # 你的以太网 IP（多网卡必设）
py vsomeip_server_windows.py          # 终端 A
py vsomeip_client_windows.py          # 终端 B（收齐 3 服务自动退出）
```

Windows 自诊断：`py diagnose_windows.py`（打印网卡/IP + 校验 routing 配置），
防火墙放行 UDP 51400-51402、30490 的命令见 `windows/README.md`。

---

## 可手动跑的测试清单

| 场景 | 服务端命令 | 客户端命令 | 成功标志 |
|---|---|---|---|
| 单服务 | `python3 server.py` | `ARHUD_EXIT_AFTER=3 python3 client.py` | 客户端收到事件并打印结构体 |
| 单服务 pcap 回放 | `python3 server.py testdata/test_arhud_000c_8003.pcap` | 同上 | `解码出 6 条事件` + 收到 `timestamp=0x1000..` |
| 20 服务 | `python3 server_multi.py` | `ARHUD_EXIT_ALL=1 python3 client_multi.py` | `20 个服务均已收到事件` |
| HUD 23 服务 | `python3 hud_server.py` | `ARHUD_EXIT_ALL=1 python3 hud_client.py` | `已收 23/23`，解析失败 0 |
| HUD pcap 回放 | `ARHUD_PCAP=testdata/test_arhud_hud_23events.pcap python3 hud_server.py` | 同上 | 客户端 Counter 与 pcap 帧序一致 |
| 字节序自测 | — | `python3 vsomeip_example/endian.py` | `大端编解码自测通过 ✓` |
| pcap 内容查看 | — | `python3 vsomeip_example/pcap_decoder.py testdata/test_arhud_hud_23events.pcap --dump 3` | 打印 SOME/IP 头解析 |
| 序列化往返自测 | — | `python3 hud/hud_data_types.py`(无) / `python3 -c "..."` | 12 种类型往返一致 |
| UDP 通路检查(Windows) | — | `py windows/udp_loopback_check.py` | 全部端口可达 |

---

## 关键日志行（如何判断成功）

```
服务端:  Instantiating routing manager [Host].          ← 服务端成为路由管理器宿主
         create_routing_root: Routing root @ /tmp/vsomeip-0
客户端:  Application/Client 1003 (arhud_client) is registered.   ← 注册成功
         ON_AVAILABLE(1003): [000c.000c:0.0]            ← 服务可用
         SUBSCRIBE ACK(1201): [000c.000c.0001.ffff]     ← 订阅成功
         [recv] ... 已收 23/23                            ← 收齐全部事件
```

---

## 常见问题排查

| 现象 | 原因与解决 |
|---|---|
| 客户端反复 `DEREGISTERED` / `register timeout` | 路由宿主配置错误：客户端 `routing` 必须等于服务端第一个应用名；清理 `/tmp/vsomeip-*` 后先服务端后客户端 |
| `本机IP: 127.0.0.1`（Windows 多网卡） | 设 `ARHUD_UNICAST=<以太网IP>` |
| 客户端收不到数据但服务端在发 | ① 服务端发送预算太小提前退出（测试用 `SEND_COUNT=0` 持续发）；② 事件组不一致（`EVENT_GROUP`/`group` 参数两端一致）；③ Windows 防火墙拦 UDP |
| `SOME/IP eventgroups require SD to be enabled!` | 服务发现没开：`service-discovery.enable=true`（键名是 `enable` 不是 `enabled`） |
| 已定义类型显示"解析失败" | 载荷字节序/格式与文档不一致：核对 `hud_data_types.py` 顶部 `ENDIAN`/字符串/数组长度常量；用 `pcap_decoder.py --dump` 对照真实抓包 |
| 端口被占 | 按 `new_describe.md` 附录 A 修正表使用端口（51400-51409、52001） |

---

*配套：自动化一键测试 `bash docker/run_tests.sh`；问题根因分析见 `SOLUTION.md` / `SOLUTION_WINDOWS.md` / `SOLUTION_HUD.md`。*
