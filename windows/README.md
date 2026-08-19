# ArHud SOME/IP —— Windows 部署指南（vsomeip_py）

> 对应问题：`windows_problem.txt`（DEREGISTERED 循环 / Routing info not found / 本机IP 错误）
> 完整分析见根目录 **`SOLUTION_WINDOWS.md`**。

## 一、Windows 上 vsomeip 的关键差异（必须先知道）

1. **本地路由不走 UDS**：Windows 没有 Unix Domain Socket，应用↔路由管理器的本地通道是
   **127.0.0.1 上的 TCP**（`justinlhudson/vsomeip` 分支的 `local_tcp_*_endpoint_impl`）。
   所以没有 `/tmp/vsomeip-*` 残留问题，也不需要清理 UDS 文件。
2. **必须用 Windows 分支**：标准 COVESA/vsomeip 不支持 Windows。vsomeip_py 官方 README
   明确：Windows 请使用 [justinlhudson/vsomeip](https://github.com/justinlhudson/vsomeip) 分支
   （已包含 Windows 补丁与 `*_std` API）。**用错库 = 完全连不上。**
3. **多网卡 IP 选择**：vsomeip 的 `unicast` 必须是对端可达的真实网卡地址。
   Windows 上 `socket.gethostbyname(socket.gethostname())` 常返回 127.0.0.1 或 VMware 地址
   —— 本仓库 `get_local_ip.py` 用"UDP connect 外部地址"法规避，并支持 `ARHUD_UNICAST` 显式指定。

## 二、安装 / 构建

```powershell
# 1) 准备构建工具（Visual Studio 2019/2022 C++ 桌面开发 + CMake）
#    https://visualstudio.microsoft.com/ 勾选 "使用 C++ 的桌面开发"

# 2) 编译安装 justinlhudson/vsomeip（Windows 分支）
git clone https://github.com/justinlhudson/vsomeip.git
cd vsomeip
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
cmake --install build --config Release   # 默认装到 C:\Program Files\vsomeip

# 3) 编译安装 vsomeip_py（需在能链接上述 vsomeip 的环境下）
git clone https://github.com/COVESA/vsomeip_py.git
cd vsomeip_py
# 按 vsomeip_py 的 Windows 说明（package.bat）或手动：
#   - include/lib 指向 vsomeip 安装目录
#   - python setup.py bdist_wheel 然后 pip install 生成的 wheel
pip install .

# 4) 其余依赖
pip install scapy
```

> 如果你已经能 `import vsomeip_py` 并成功运行过（报告里已安装于 Python313 site-packages），
> 第 2、3 步可跳过 —— 但要确认它链接的是 **justinlhudson 分支**，否则请重装。

## 三、运行（先服务端后客户端）

```powershell
cd windows

# 0) 可选：先自诊断（打印网卡/推荐IP，并校验 routing 配置）
py diagnose_windows.py

# 1) 终端 A：服务端（多网卡环境显式指定以太网 IP）
$env:ARHUD_UNICAST = "10.13.90.164"
py vsomeip_server_windows.py
#    预期日志：
#    [Server] 启动服务...
#    [Server] 已通知 Service=0xa, Event=0x8001, Counter=1 ...

# 2) 终端 B：客户端
$env:ARHUD_UNICAST = "10.13.90.164"
py vsomeip_client_windows.py
#    预期日志：
#    [Client] 收到 Service=0xa Event=0x8001 ...
#    不再出现 DEREGISTERED / Routing info ... not found
```

> **两次运行之间**：如遇异常退出，先 `taskkill /F /IM python.exe` 清理残留进程；
> 脚本已用 `force=True` 自动清理 vsomeip 锁文件。

## 四、环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `ARHUD_UNICAST` | 自动探测 | 本机主 IP（Windows 多网卡必设，如 10.13.90.164） |
| `ARHUD_SD` | `true` | 服务发现（事件组订阅要求开启，不要关） |
| `ARHUD_SERVICE_IDS` | `0x000A,0x000B,0x000C` | 服务 ID 列表 |
| `ARHUD_INSTANCE_IDS` | `0x000A,0x000B,0x000C` | 实例 ID 列表 |
| `ARHUD_EVENT_ID` | `0x8001` | 事件 ID |
| `ARHUD_EVENT_GROUP` | `0x1101` | 事件组（客户端/服务端必须一致） |
| `ARHUD_PORT_BASE` | `51400` | 服务 UDP 端口基址 |
| `ARHUD_INTERVAL` / `ARHUD_SEND_COUNT` | `0.2` / `0` | 发送节奏 |
| `ARHUD_ROUTING_HOST` | `arhud_server` | **客户端**：路由管理器宿主 = 服务端第一个应用名 |
| `ARHUD_EXIT_ALL` / `ARHUD_EXIT_AFTER` | - | 客户端收齐/收 N 条后退出 |

## 五、防火墙

Windows 防火墙默认拦截 UDP 入站。放行方式（管理员 PowerShell）：

```powershell
New-NetFirewallRule -DisplayName "vsomeip-arhud" -Direction Inbound -Protocol UDP `
  -LocalPort 51400-51402,30490 -Action Allow
# 若启用服务发现还需放行多播: 组 224.0.2.4
```

## 六、故障排查顺序

1. `py diagnose_windows.py` —— 看 **routing 配置检查**是否 FAIL（这是 DEREGISTERED 循环的头号原因）；
2. `py udp_loopback_check.py` —— 确认 UDP 通路/防火墙；
3. 确认客户端日志出现 `Application/Client xxxx is registered.` 与 `ON_AVAILABLE`（可用性）；
4. 确认服务端日志出现 `Instantiating routing manager [Host].`（只有第一个服务应用是宿主）。
