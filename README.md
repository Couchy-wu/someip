# ArHud SOME/IP (vsomeip) 示例与问题分析

![CI](https://github.com/Couchy-wu/someip/actions/workflows/ci.yml/badge.svg)

ArHud 车道线数据 SOME/IP 通信的完整示例：**PCAP 解码 → 序列化/反序列化 → vsomeip 服务端发送事件 → 客户端订阅**，以及最初"注册超时"问题的深入分析报告。

## 目录结构

```
├── SOLUTION.md                 # 问题分析报告（日志解读、根因、解决方案）
├── problem.txt                 # 原始问题描述
├── arhud_client_fixed.py       # 最小修正版客户端
├── arhud_server_fixed.py       # 最小修正版服务端
├── vsomeip_example/            # 完整可运行示例（推荐）
│   ├── arhud_data_types.py     #   数据结构序列化/反序列化（对应 C++ stNewLanelineDataNotify）
│   ├── pcap_decoder.py         #   pcap → SOME/IP 事件载荷 → 数据对象
│   ├── server.py               #   vsomeip 服务端：回放 pcap 事件
│   ├── client.py               #   vsomeip 客户端：订阅 + 反序列化
│   ├── test_pipeline.py        #   解码管线回归测试
│   └── README.md               #   运行与对接说明
└── docker/                     # Docker 完整测试（目标: Ubuntu 22.04 + Python 3.10）
    ├── Dockerfile              #   编译 vsomeip 3.4.10 + vsomeip_py
    ├── run_tests.sh            #   一键: 构建 + 解码管线测试 + 真实 vsomeip 收发集成测试
    ├── integration_test.sh     #   两进程 server↔client 收发断言
    ├── min_cli.cpp             #   最小 C++ 客户端（验证服务端兼容性）
    └── min_svc.cpp             #   最小 C++ 服务端（验证客户端兼容性）
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

## 测试状态

- `test_pipeline.py`：pcap 解码/序列化往返回归测试 ✅
- Docker 集成测试：客户端 `is registered` → `ON_AVAILABLE` → `SUBSCRIBE ACK` → 收到并反序列化事件 ✅
- C++ 客户端兼容性验证：`min_cli`（C++）连接 Python 服务端收到 `availability=true` ✅
- GitHub Actions CI：每次 push/PR 自动构建 Docker 镜像并跑以上全部测试（`.github/workflows/ci.yml`）
