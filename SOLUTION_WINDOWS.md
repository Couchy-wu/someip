# ArHud SOME/IP Windows 版 —— 问题分析与完整解决方案

> 对应问题：`windows_problem.txt`
> 结论先行：报告里"vSomeIP 在 Windows 上的路由机制存在已知限制（平台限制）"**不成立**。
> 你引用的 [issue #289](https://github.com/COVESA/vsomeip/issues/289)（"configured as routing but other
> routing manager present"）是**路由配置错误**，[#615](https://github.com/COVESA/vsomeip/issues/615)
> （`/tmp/vsomeip.lck` 残留）是**锁文件清理**问题——两者都与平台无关，Linux 上同样会发生。
> **DEREGISTERED 循环的真正根因是配置错误（与 Ubuntu 上"注册超时"同源）+ Windows 特有环境问题**，
> 全部可修，见下文。

---

## 1. 现象解读（对照日志）

| 现象 | 真实含义 |
|---|---|
| `[error] Routing info for remote service could not be found! (1003): [000a.000a.0001]` | 客户端请求了服务 0x000A，但它的路由代理(RM proxy)拿不到该服务的路由信息——因为**它连的路由管理器宿主根本不存在/未正确建立**。报的是"remote service"，因为连不上本地 RM，vsomeip 把它当远程服务走 SD 查找，SD 也没结果 |
| `routing_manager_client::on_disconnect: Client 0x1003 ... DEREGISTERED`（循环） | 客户端代理反复尝试连接路由管理器、失败、被置为 DEREGISTERED。**等价于 Ubuntu 上的 "register timeout! Trying again..." 循环**，同一根因：没有一个健康的 RM 宿主在应答 |
| 服务端正常运行、持续通知 | 服务端进程活着，但它也（可能）没成为 RM 宿主，或即使成为了宿主，客户端也没连上它 |
| 客户端打印 `本机IP: 127.0.0.1` | 代码用 `socket.gethostbyname(hostname)` 取 IP，Windows 多网卡下返回了回环/VMware 地址 → unicast 错误 |

## 2. 根因分析

### 根因 1（首要）：路由管理器宿主配置错误 —— `"routing": "arhud01"` 指向不存在的应用

你在 `vsomeip.json` 里配置了：

```json
"applications": [ {"name": "arhud_client", "id": 4099} ],
"routing": "arhud01",
"network": "arhud01"
```

vsomeip 判定"谁是路由管理器宿主"的逻辑（`application_impl::init`）：

```cpp
std::string its_routing_host = configuration_->get_routing_host_name();
if (its_routing_host != "") {
    is_routing_manager_host_ = (its_routing_host == name_);   // routing 值 == 本应用名才当宿主
}
```

- `routing` 的值必须是**某个真实应用名**（[issue #396](https://github.com/COVESA/vsomeip/issues/396) 的语义）。
- 你的应用叫 `arhud_client`/`arhud_server`，**没有任何应用叫 `arhud01`** → 每个应用都判定
  `name != "arhud01"` → **没有任何进程成为 RM 宿主** → 所有应用都变成"代理"，连向一个没人监听的
  本地路由端点 → 客户端反复 DEREGISTERED。这与 Ubuntu 上"客户端连不上 /tmp/vsomeip-0"是**同一个根因**。

**修复**：`"routing"` 必须指向服务端第一个应用名。用本仓库代码时（模板自动配置）：

```python
# 服务端：第一个含 services 的应用自动成为宿主（arhud_server）
# 客户端：显式声明
configuration["routing"] = "arhud_server"   # = 服务端第一个应用名，不是 "arhud01"
```

### 根因 2：vSOMEIP 构造函数第 2 参数是"服务 ID"不是"客户端 ID"（与 Ubuntu 相同）

```python
app = vSOMEIP("arhud_client", 0x1003, 0x000A)   # ✗ 0x1003 被当服务 ID → 订阅服务 0x1003（不存在）
app = vSOMEIP("arhud_client", 0x000A, 0x000A)   # ✓ 服务 ID；客户端 ID 放配置 applications[].id
```

### 根因 3：`app.request()` 不是"请求服务订阅"

```python
app.register()   # ✓ request_service —— 请求服务订阅
app.request(id)  # ✗ 发送一个 SOME/IP 请求报文，不是订阅
```

### 根因 4：Windows 多网卡下 unicast 选择错误（已识别，方向正确）

`socket.gethostbyname(socket.gethostname())` 在多网卡（以太网 10.13.90.164 + VMware
192.168.137.1/126.1 + 回环）下不可靠。你改用"连接 8.8.8.8 取源地址"思路正确。
本仓库 `get_local_ip.py` 提供更稳的版本（UDP connect 不发包 + 多级回退 + `ARHUD_UNICAST` 显式覆盖）。

### 根因 5（Windows 特有，环境要求）：必须用 Windows 分支的 vsomeip

- vsomeip 官方不支持 Windows；vsomeip_py 官方 README 指定 Windows 使用
  [justinlhudson/vsomeip](https://github.com/justinlhudson/vsomeip) 分支。
- 该分支把本地路由实现为 **127.0.0.1 上的 TCP**（`local_tcp_server_endpoint_impl`，
  端口由 vsomeip 动态分配并自协商），替代 Linux 的 Unix Domain Socket。
- **用错库（官方 vsomeip 或其它 fork）→ 本地路由端点对不上 → 必然 DEREGISTERED**。
- 好消息：既然是 TCP 本地路由，**没有 /tmp/vsomeip-* 残留问题**，两端配置一致即可，
  不需要像 Linux 那样清 UDS 套接字。

### 根因 6：事件组订阅要求开启服务发现（与 Ubuntu 相同）

vsomeip 限制：`SOME/IP eventgroups require SD to be enabled!`。保持
`"service-discovery": {"enable": "true"}`（不要写错键名 `enabled`）。

---

## 3. 解决方案（对应代码见 `windows/` 目录）

| 步骤 | 内容 |
|---|---|
| 1. 确认库 | 确保 vsomeip_py 链接的是 **justinlhudson/vsomeip** 分支（Windows）；否则重装（见 `windows/README.md` 第二节） |
| 2. 配置 | `routing` = 服务端第一个应用名（如 `arhud_server`）；`unicast` = 以太网 IP；`service-discovery.enable=true`；`network` 两端一致 |
| 3. 代码 | 构造函数第 2 参数 = 服务 ID；`app.register()`；`app.on_event(EVENT_ID, cb, group=G)` 与服务端 `offer(events=[EVENT_ID], group=G)` 的 G 一致；`force=True` |
| 4. 运行顺序 | 先服务端（确认日志 `Instantiating routing manager [Host].`），后客户端（确认 `is registered` + `ON_AVAILABLE`） |
| 5. 防火墙 | 放行 UDP 51400-51402、30490（管理员 PowerShell 命令见 `windows/README.md` 第五节） |

## 4. 交付代码（`windows/`）

| 文件 | 作用 |
|---|---|
| `vsomeip_server_windows.py` | 修正服务端：3 个服务(0xA/0xB/0xC)，事件 0x8001，`routing` 自动指向第一个应用 |
| `vsomeip_client_windows.py` | 修正客户端：订阅 3 个服务，`routing=arhud_server`、构造函数服务 ID、`register()` |
| `get_local_ip.py` | 健壮的本机 IP 获取（ARHUD_UNICAST 覆盖 → UDP connect 8.8.8.8 → 网卡过滤 → 回环兜底） |
| `diagnose_windows.py` | 自诊断：网卡/IP + **routing 配置一致性校验**（抓根因 1）+ 构造函数参数提醒 + UDP 通路 |
| `udp_loopback_check.py` | 纯 UDP 回环检查（隔离网络/防火墙问题，不依赖 vsomeip） |
| `vsomeip_windows.json` | 参考配置（routing=arhud_server，键名正确） |
| `README.md` | Windows 构建/安装/运行/防火墙/排查步骤 |

## 5. 验证（可在 Linux/容器中先行验证代码逻辑）

`windows/` 的 Python 代码与 `vsomeip_example/` 已验证的结构一致（模板配置、routing 语义、
构造函数服务 ID、register()、SD 开启），可先在 Linux/Docker 中跑通再上 Windows。
`diagnose_windows.py` / `udp_loopback_check.py` / `get_local_ip.py` 为纯 Python，跨平台可测。

## 6. 参考资料

- [COVESA/vsomeip #396](https://github.com/COVESA/vsomeip/issues/396)：`routing` 键语义（"routing":"app-name" 必须匹配真实应用名）
- [COVESA/vsomeip #537](https://github.com/COVESA/vsomeip/issues/537)：注册超时/Operation canceled 同类现象（配置问题）
- [COVESA/vsomeip #289](https://github.com/COVESA/vsomeip/issues/289)：路由宿主配置错误（"configured as routing but other routing manager present"）
- [COVESA/vsomeip #615](https://github.com/COVESA/vsomeip/issues/615)：锁文件残留（`force=True` 清理）
- [justinlhudson/vsomeip](https://github.com/justinlhudson/vsomeip)：Windows 支持分支（本地路由 = TCP loopback）
- [COVESA/vsomeip_py](https://github.com/COVESA/vsomeip_py)：Python 绑定（Windows 需上述分支）
