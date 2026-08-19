# ArHud SOME/IP 完整示例（vsomeip_py，不绕开 vsomeip 库）

一套**可直接运行**的完整示例，覆盖你要求的三件事：

```
pcap 文件 ──解码──▶ SOME/IP 事件 ──反序列化──▶ NewLaneLineDataNotify 数据对象
                                                        │ 序列化(to_bytes)
服务端 (server.py, vsomeip) ──app.notify()──▶ 事件 0x8003
                                                        │ 订阅(on_event)
客户端 (client.py, vsomeip) ◀──收到载荷── 反序列化(from_bytes)──▶ 打印结构体
```

## 文件说明

| 文件 | 作用 |
|---|---|
| `arhud_data_types.py` | 数据结构 + 序列化/反序列化（对应 C++ `stNewLanelineDataNotify`，大端布局，可独立自测） |
| `pcap_decoder.py` | pcap → SOME/IP 头解析 → 事件载荷 → 反序列化（含 `--dump` 排查模式） |
| `server.py` | **标准 vsomeip 服务端**：解码 pcap → 反序列化 → 重新序列化 → `app.notify()` 发送事件 |
| `client.py` | vsomeip 客户端：订阅事件 0x8003 → 反序列化 → 打印 |
| `server_multi.py` | **20 服务版服务端**：提供 `ARHUD_SERVICES`(默认 20) 个服务，每个服务一个事件，周期 notify |
| `client_multi.py` | **20 服务版客户端**：订阅全部 20 个服务，收齐后打印每服务的事件 |

> 你项目里已经写好的客户端（C++ 或其它 vsomeip 实现）**不需要任何改动**：本示例服务端是标准 vsomeip 服务，发送的事件载荷就是 C++ 结构体的序列化字节。

## 运行步骤

```bash
# 1) 依赖（vsomeip_py 与 scapy）
pip install scapy
# 并确保本机构建安装了 COVESA vsomeip C++ 库 + vsomeip_py（见 SOLUTION.md）

# 2) 终端 A：先启动服务端（参数为 pcap 路径；缺省读当前目录 out.pcap，
#    没有 pcap 时自动用内置示例数据，保证链路可跑通）
python3 server.py /path/to/out.pcap
#    预期日志：服务端就绪 -> 持续打印 [send] #N event=0x8003 payload=XXB ...

# 3) 终端 B：再启动客户端
python3 client.py
#    预期日志：收到事件 -> 打印 HEX + 解析出的 NewLaneLineDataNotify 结构体
```

> 每次重启前先清理残留：`pkill -9 -f "server.py|client.py"` 与 `rm -f /tmp/vsomeip-*`（原因见 SOLUTION.md：包装器退出不干净会留下 socket/锁文件，导致 register timeout 循环）。

## 关键对齐点（对接你现有客户端时逐一核对）

| 参数 | 值 | 说明 |
|---|---|---|
| **构造函数第 2 参数** | **`SERVICE_ID (0x000C)`** | **vsomeip_py 的 `vSOMEIP(name, id, instance)` 中 `id` 是【服务 ID】（offer/request/on_event 都用它），不是客户端 ID！** 这是最容易踩的坑（原始报告和我们第一版都传成了客户端 ID，导致服务端 offer 了 0x1201、客户端请求 0x1003，两端永远对不上） |
| **客户端 ID** | `applications[].id`（server=`0x1201`, client=`0x1003`） | 由配置文件 `"applications"` 段的 `"id"` 决定，与构造函数第 2 参数无关，两端可以不同 |
| Service ID | `0x000C` | 两端必须一致 |
| Instance ID | `0x000C` | 两端必须一致 |
| Event ID | `0x8003` | NewLaneLineDataNotify |
| **Event Group** | `0x01` | **必须等于你客户端 subscribe 的事件组**（若你的客户端用默认 0xFFFF，把 server.py 的 `EVENT_GROUP` 改成一致） |
| **Routing Host** | `"arhud_server"` | **多进程场景最关键的一项**：客户端必须显式 `"routing": "arhud_server"`，否则客户端会自建路由管理器、与服务端各自为政，收不到事件。你已写好的 C++ 客户端配置里同样要有 `"routing": "arhud_server"`（或改用 vsomeipd 守护进程） |
| 端口 | `51402` (UDP) | 服务端 `services.unreliable` 与客户端 `clients.unreliable` 一致 |
| 载荷格式 | `NewLaneLineDataNotify.to_bytes()` | 即 C++ `stNewLanelineDataNotify` 内存布局（大端）。**若你的 C++ 结构与示例不同（字段顺序/类型/数量），改 `arhud_data_types.py` 一处即可** |
| 服务发现 | 默认开启 | **事件组订阅要求 SD 开启**（vsomeip 限制，`SOME/IP eventgroups require SD to be enabled!`）；两端一致地开启即可 |

## 兼容性提示

- vsomeip_py 的 `offer_event`/`request_event` 固定使用 `ET_FIELD`（C++ 扩展里硬编码）。如果你的 C++ 客户端按 `is_field=false` 订阅，事件仍会推送（订阅基于事件组）；若出现订阅不生效，优先核对事件组与端口，必要时在你的 C++ 服务端侧保证事件类型一致。
- 本示例客户端、服务端均在 127.0.0.1 上运行；部署到真机/多机时，把 `configuration["unicast"]` 改为各自主机 IP（并保证两端可路由）。

## 排查工具

```bash
# 查看 pcap 里到底是不是标准 SOME/IP 报文（前 N 个 UDP 载荷的 HEX + 头解析）
python3 pcap_decoder.py out.pcap --dump 5

# 单独验证序列化/反序列化往返一致
python3 arhud_data_types.py
```

## Docker 完整测试（推荐，目标环境 Ubuntu 22.04 + Python 3.10）

`../docker/` 提供了完整容器化测试：容器内编译安装 **vsomeip 3.4.10 + vsomeip_py**，
然后用**两个独立进程**跑 `server.py` / `client.py`，走真实 UDS 路由管理器注册与事件收发。

```bash
bash docker/run_tests.sh
# 依次执行：
#   1. 构建镜像（首次约 5-15 分钟，编译 vsomeip）
#   2. test_pipeline.py 解码管线回归测试
#   3. 集成测试：server.py(notify) ─▶ client.py(subscribe+反序列化)，断言收到事件
```

容器内测试细节：

- **SD 保持开启**（vsomeip 事件组订阅要求 SD）；同一容器内两个进程通过多播回环完成发现；
- 可用环境变量控制行为：`ARHUD_SD`(true/false)、`ARHUD_SEND_COUNT`(服务端发送条数)、
  `ARHUD_INTERVAL`(发送间隔秒)、`ARHUD_EXIT_AFTER`(客户端收到 N 条后退出)；
- 手动进容器调试：`docker run --rm -it -v $PWD:/app:ro arhud-vsomeip-test bash`，
  然后 `cd /tmp && cp -r /app/* . && python3 server.py & sleep 2 && python3 client.py`。

## 20 服务版（server_multi.py + client_multi.py）

```
服务端(一个进程)                         客户端(一个进程)
├─ arhud_svc_0  offer 服务 0x0100 ──▶  ├─ arhud_cli_0  订阅 0x0100 事件
├─ arhud_svc_1  offer 服务 0x0101 ──▶  ├─ arhud_cli_1  订阅 0x0101 事件
│  ...                                   │  ...
└─ arhud_svc_19 offer 服务 0x0113 ──▶  └─ arhud_cli_19 订阅 0x0113 事件
```

运行（先服务端后客户端）：

```bash
python3 server_multi.py          # 终端 A：默认 20 个服务，事件 0x8003
python3 client_multi.py          # 终端 B：订阅全部 20 个服务
# 环境变量: ARHUD_SERVICES=个数  ARHUD_SD=true/false  ARHUD_INTERVAL=秒  ARHUD_SEND_COUNT=条数
# 客户端:   ARHUD_EXIT_ALL=1(收齐退出)  ARHUD_EXIT_AFTER=N(收N条退出)
```

每个服务的数据用 `timestamp` 字段携带服务序号(0..19)，客户端可据此验证数据来源。

### 一个应用能否订阅 20 个服务？

- **vsomeip（C++ 层面）：可以，而且是标准用法。** 一个 application 对每个服务分别
  `request_service` + `request_event` + `subscribe` 即可（见 `../docker/min_cli_multi.cpp`，
  单应用订阅 20 个服务，已实测收齐）。两个注意点：
  1. 消息处理器要按 `(service, instance, method)` 各注册一次（可共用同一回调），
     vsomeip 不会把通知分发给 `ANY_SERVICE/ANY_INSTANCE` 注册的处理器；
  2. `subscribe` 的 major 版本必须与服务端 offer 的 major 一致（`DEFAULT_MAJOR=0`），
     否则 pending 订阅永远不会被冲刷发出。
- **vsomeip_py 高层包装：不可以（一个 `vSOMEIP` 对象 = 一个服务）。** 原因：
  1. `vSOMEIP(name, id, instance)` 的 `id` 即服务 ID，`on_event/register/offer` 都用它；
  2. vsomeip 运行时对同名 `create_application` 会**自动改名**（`name_0/name_1/...`），
     无法让多个实体共享一个应用。
  所以 Python 侧用 20 个 `vSOMEIP` 对象（20 个应用）——但仍是**一个进程、一个逻辑客户端**，
  对外行为与单应用等价。若必须单应用，请用 C++ 客户端（min_cli_multi.cpp）或扩展包装器。

### 服务端一个应用能否提供 20 个服务？（与客户端的回答镜像）

- **vsomeip（C++ 层面）：可以，而且是标准用法。** 一个 application 对每个服务分别
  `offer_service` + `offer_event`（见 `../docker/min_svc_multi.cpp`，单应用提供 20 个服务，
  已实测：C++ 单应用客户端与 Python 20 应用客户端都能收齐全部 20 个服务的事件）。
- **vsomeip_py 高层包装：不可以（一个 `vSOMEIP` 对象 = 一个服务）。** 与客户端同理：
  构造函数第 2 参数即服务 ID、同名 `create_application` 会被运行时改名。
  所以 Python 侧用 20 个 `vSOMEIP` 对象（20 个应用）——仍是**一个进程、一个逻辑服务端**。

#### 1 个应用 vs 20 个应用的区别

| 维度 | 1 个应用 offer 20 服务（C++） | 20 个应用各 offer 1 服务（vsomeip_py） |
|---|---|---|
| vsomeip 支持 | ✅ 标准用法 | ✅ 同样支持 |
| 客户端 ID 消耗 | 1 个（`applications[].id`） | 20 个（0x1200..0x1213） |
| 与 RM 的注册握手 | 1 次（1 个本地端点） | 20 次（20 个本地端点） |
| io / 分发线程 | 2~3 个 | 20×(2~3) ≈ 40~60 个线程 |
| 内存 | 1 份 application_impl + 路由代理 | 20 份 |
| handler 注册 | 每个 (service,instance,event) 注册一次（可共用回调） | 每个应用各注册自己的 |
| notify | `app->notify(svc_i, inst, event, payload)` 显式带服务 | 每个 `app.notify` 只发自己的服务 |
| **线上行为** | **完全一致**：事件按 (service, instance, event) 路由，客户端无感知 | 同左 |
| 适用场景 | 客户端 ID / 线程 / 内存紧张的嵌入式或大规模部署 | Python 开发/验证（当前仓库方式） |

> 结论：两种方式对**客户端完全透明**（同一个客户端既能消费"1 应用 20 服务"也能消费"20 应用 20 服务"，
> 上面的 a/b 两个组合均已实测）。区别只在服务端自身的资源开销：
> 需要单应用时用 C++（`min_svc_multi.cpp` 为参考实现）；Python 侧受包装层限制用 20 应用即可。
