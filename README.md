# ArHud SOME/IP (vsomeip) 示例与问题分析

![CI](https://github.com/Couchy-wu/someip/actions/workflows/ci.yml/badge.svg)

ArHud 车道线数据 SOME/IP 通信的完整示例：**PCAP 解码 → 序列化/反序列化 → vsomeip 服务端发送事件 → 客户端订阅**，以及最初"注册超时"问题的深入分析报告。

## 目录结构

```
├── SOLUTION.md                 # 问题分析报告（日志解读、根因、解决方案）
├── SOLUTION_WINDOWS.md         # Windows 版问题分析（DEREGISTERED 循环根因与修复）
├── SOLUTION_HUD.md             # AR-HUD 23 服务方案（new_describe.md 的 Python 化实现）
├── problem.txt                 # 原始问题描述
├── windows_problem.txt         # Windows 版问题描述
├── arhud_client_fixed.py       # 最小修正版客户端
├── arhud_server_fixed.py       # 最小修正版服务端
├── hud/                        # AR-HUD 23 服务/11 个服务（new_describe.md）
│   ├── hud_data_types.py       #   23 事件注册表 + 12 种类型序列化/反序列化
│   ├── hud_server.py           #   11 服务应用服务端（端口/实例按修正表）
│   └── hud_client.py           #   11 应用客户端订阅 23 事件（含 0x000E 三事件组）
├── windows/                    # Windows 部署（vsomeip_py）
│   ├── vsomeip_server_windows.py  #   修正服务端（3 服务，routing=arhud_server）
│   ├── vsomeip_client_windows.py  #   修正客户端（订阅 3 服务）
│   ├── get_local_ip.py            #   健壮的本机 IP 获取（多网卡）
│   ├── diagnose_windows.py        #   自诊断（routing 配置一致性校验）
│   ├── udp_loopback_check.py      #   纯 UDP 通路检查（防火墙隔离）
│   ├── vsomeip_windows.json       #   参考配置
│   └── README.md                  #   Windows 构建/安装/运行/防火墙
├── vsomeip_example/            # 完整可运行示例（推荐）
│   ├── arhud_data_types.py     #   数据结构序列化/反序列化（对应 C++ stNewLanelineDataNotify）
│   ├── pcap_decoder.py         #   pcap → SOME/IP 事件载荷 → 数据对象
│   ├── server.py               #   vsomeip 服务端：回放 pcap 事件
│   ├── client.py               #   vsomeip 客户端：订阅 + 反序列化
│   ├── server_multi.py         #   20 服务版服务端（ARHUD_SERVICES 可调）
│   ├── client_multi.py         #   20 服务版客户端（订阅全部服务）
│   ├── make_test_pcap.py       #   生成 SOME/IP 测试 pcap（可复现）
│   ├── endian.py               #   端序工具：大小端识别 + 网络序(大端)编解码自测
│   ├── test_pipeline.py        #   解码管线回归测试
│   └── README.md               #   运行与对接说明
├── testdata/                   # 现成测试 pcap（仓库内可直接下载使用）
│   ├── test_arhud_000c_8003.pcap    #   Ubuntu 程序：服务 0x000C/事件 0x8003，6 条通知+噪声
│   └── test_windows_000a_8001.pcap  #   Windows 程序：服务 0xA/0xB/0xC/事件 0x8001，9 条通知+噪声
└── docker/                     # Docker 完整测试（目标: Ubuntu 22.04 + Python 3.10）
    ├── Dockerfile              #   编译 vsomeip 3.4.10 + vsomeip_py
    ├── run_tests.sh            #   一键: 构建 + 6 项测试
    ├── integration_test.sh     #   单服务两进程收发断言
    ├── integration_test_multi.sh # 20 服务两进程收发断言
    ├── min_cli.cpp             #   最小 C++ 客户端（验证服务端兼容性）
    ├── min_svc.cpp             #   最小 C++ 服务端（验证客户端兼容性）
    ├── min_cli_multi.cpp       #   C++ 单应用订阅 20 服务（标准 vsomeip 用法）
    ├── cpp_client_test.sh      #   C++ 客户端 ↔ Python 服务端 验证
    ├── cpp_client_test_multi.sh #  C++ 单应用 ↔ 20 服务服务端 验证
    ├── cross_check_windows.sh  #   windows/ 修复代码跨平台校验
    ├── integration_test_pcap.sh #  pcap 全链路测试（Ubuntu+Windows 程序）
    └── integration_test_hud.sh  #  AR-HUD 23 服务集成测试
```

## 快速开始

```bash
# 1) 本地直接跑（需本机装好 vsomeip C++ 库 + vsomeip_py + scapy）
cd vsomeip_example
python3 server.py /path/to/out.pcap   # 终端 A：服务端（无 pcap 时用内置示例数据）
python3 client.py                     # 终端 B：客户端，订阅事件 0x8003

# 2) Docker 完整测试（Ubuntu 22.04 + Python 3.10，推荐）
bash docker/run_tests.sh
```

## 关键结论（详见 SOLUTION.md）

最初报告的"vsomeip-py 库 UDS bug、无法解决"**不成立**。真正根因有三层，已在 Docker 中实测修复：

1. **vsomeip_py 构造函数第 2 个参数 `id` 是"服务 ID"不是"客户端 ID"**——传错会导致服务端 offer 的服务 ID 与客户端请求的服务 ID 永远对不上；
2. 客户端配置必须显式声明 `"routing": "<服务端应用名>"`（否则每个进程自建路由管理器）；
3. 事件组订阅要求开启服务发现（vsomeip 限制）。

## pcap 测试数据

仓库 `testdata/` 提供两份现成 pcap（可下载直接用，也可用 `make_test_pcap.py` 重新生成）：

```bash
# 查看/校验 pcap 内容
python3 vsomeip_example/pcap_decoder.py testdata/test_arhud_000c_8003.pcap --dump 3
python3 vsomeip_example/pcap_decoder.py testdata/test_arhud_000c_8003.pcap

# Ubuntu 程序回放
python3 vsomeip_example/server.py testdata/test_arhud_000c_8003.pcap   # 终端 A
python3 vsomeip_example/client.py                                      # 终端 B

# Windows 程序回放（在 Windows 上）
set ARHUD_PCAP=test_windows_000a_8001.pcap && py vsomeip_server_windows.py
```

pcap 内容：SOME/IP NOTIFICATION 报文（UDP），载荷为 `NewLaneLineDataNotify` 序列化字节，
`timestamp` 字段 = 0x1000+包序号，用于断言"客户端收到的数据与 pcap 一致"；另含噪声报文
（其它服务/其它事件/垃圾 UDP）验证解码过滤。

## 字节序（大小端）

网络传输使用大端（SOME/IP 与 ArHud 结构均为网络字节序）。代码全部用 `struct '>'` 显式大端，
**自动适配任意主机端序**（小端 x86/ARM 与大端 s390x 输出字节完全一致，无需分支）。
识别与自测：`python3 vsomeip_example/endian.py`；C++ 参考实现见 `docker/endian_check.cpp`
（含"不要 memcpy 原生结构体当载荷"的警告）。

## 测试状态

- `test_pipeline.py`：pcap 解码/序列化往返回归测试 ✅
- Docker 集成测试：客户端 `is registered` → `ON_AVAILABLE` → `SUBSCRIBE ACK` → 收到并反序列化事件 ✅
- C++ 客户端兼容性验证：`min_cli`（C++）连接 Python 服务端收到 `availability=true` ✅
- GitHub Actions CI：每次 push/PR 自动构建 Docker 镜像并跑以上全部测试（`.github/workflows/ci.yml`）
