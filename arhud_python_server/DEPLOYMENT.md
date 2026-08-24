# C++ 服务端库 部署指南（SP 分支协议栈）

> 部署拓扑：**本机跑 Python + C++ 服务端库，经车载以太盒子（透明网桥）连开发板**；
> 板子上是既有 SOME/IP 中间件（托管 RM）+ 已烧录客户端，**零改动**。
> 服务端与板端 C++ 服务端使用同一协议栈（SP 分支 libsomeip.so），行为与原始部署一致。

---

## 1. 部署拓扑

```
本机 / PC (部署机)                               开发板 (零改动)
┌────────────────────────────┐   车载以太盒子     ┌──────────────────────────┐
│ Python 业务脚本             │   (透明网桥)      │ 既有 SOME/IP 中间件       │
│  └─ ctypes ─► C++ 服务端库 │◄──SD多播+UDP────►│   (托管 arhud01 RM)      │
│     (libarhud_server.so)   │                   │ 客户端 (配置已烧录)       │
│      + SP 库 + 配置 + pcap  │                   └──────────────────────────┘
└────────────────────────────┘
```

---

## 2. 部署包结构

部署机上的目录（示例 `/opt/arhud-server/`）：

```
/opt/arhud-server/
├── libarhud_server.so          # C++ 服务端库（SP 版，随架构编译）
├── libs/                       # SP 分支库（与客户端同版本/相近版本）
│   ├── libsomeip.so
│   ├── libsomeip-cfg.so
│   ├── libsomeip-sd.so
│   └── libsomeip-e2e.so
├── arhud_py.py                 # Python ctypes 封装
├── server.py                   # 业务脚本（回放/结构化发送，按需编写）
├── data/
│   └── out.pcap                # 回放数据源（可随时替换）
└── vsomeip_arhud01.json        # （可选）SP 分支配置，缺省由库自动生成
```

**部署机系统依赖（极少）**：
- Python 3（ctypes 为标准库，无第三方依赖）
- `libz`（Ubuntu：`sudo apt install -y zlib1g`，一般已装）
- gcc 运行时（`libstdc++` 等，一般已装）
- **不需要** boost、vsomeip、vsomeip_py —— SP 分支库已静态包含 boost，服务端库只依赖 libz

---

## 3. 打包步骤

```bash
# 1) 编译服务端库（用与客户端一致的架构和 SP 库）
cd arhud_python_server
# aarch64 板端配套：
make libarhud_server.so SP_LIBS=../to_longjie_demo_20250625/libs/lib_bst_t517
# x86_64 PC：
make libarhud_server.so SP_LIBS=../to_longjie_demo_20250625/libs/lib_x86
# 注：Makefile 里 SP_LIBS 也可用 ARCH=x86_64 自动选择

# 2) 组装部署包
mkdir -p /opt/arhud-server/{libs,data}
cp arhud_python_server/libarhud_server.so arhud_python_server/arhud_py.py  /opt/arhud-server/
cp to_longjie_demo_20250625/libs/lib_<架构>/*.so           /opt/arhud-server/libs/
cp <你的pcap>                                              /opt/arhud-server/data/out.pcap
```

---

## 4. 运行

### 4.1 前台 / 后台

```bash
export LD_LIBRARY_PATH=/opt/arhud-server/libs          # ★ SP 栈按插件加载 cfg/sd 模块，必须指向 libs/
cd /opt/arhud-server

# ① 指定 pcap 回放
python3 demo_replay.py data/out.pcap 192.168.1.10      # (pcap路径, 本机IP)

# ② 结构化赋值发送（业务脚本可任意组合）
python3 demo_struct.py 192.168.1.10
```

### 4.2 systemd 服务（示例 `/etc/systemd/system/arhud-server.service`）

```ini
[Unit]
Description=AR-HUD SOME/IP Python Server (C++ lib)
After=network-online.target

[Service]
WorkingDirectory=/opt/arhud-server
Environment=LD_LIBRARY_PATH=/opt/arhud-server/libs
ExecStart=/usr/bin/python3 /opt/arhud-server/server.py 192.168.1.10
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4.3 业务脚本要点（server.py）

```python
from arhud_py import ArHudServer
srv = ArHudServer(unicast="192.168.1.10")   # 或自动探测
srv.start()
srv.replay("data/out.pcap", loop=True, interval_ms=10)   # pcap 回放
# 或按需发送结构化数据：
srv.notify_fields("RTK", counter=n, longitude=..., latitude=..., ...)
```

---

## 5. 与板端联调检查清单

| 检查项 | 方法 |
|--------|------|
| 盒子为透明桥接，PC 与板子同网段 | `ping <板子IP>` |
| SD 多播 224.0.2.4:30490 跨盒子 | 两端抓包/多播收发测试 |
| UDP 放行 | 30490、51400-51409、52001-52012 |
| 板子中间件托管 RM | 板端 `ls /tmp/arhud01-0` |
| 板子中间件不 offer 服务 | 若 offer 会遮蔽远程服务端（见 FIXED_CONFIG_SOLUTION.md 5.9） |
| 客户端订阅稳定后再回放 | 先启动服务端，等 15~25s 再回放（51KB TP 大消息需要订阅就绪） |

---

## 6. 客户端 SOME/IP 库版本变更时怎么办（重点）

### 6.1 一句话结论

> **一般情况：只需替换部署包 `libs/` 里的 SP 库文件，无需重新编译**（服务端库动态链接
> libsomeip.so，且 SP 的 C 接口 `SPInit/SPStart/SPServerSendNotify` 跨版本稳定）。
> **仅当新版本改了 C 接口签名或配置文件格式时，才需要更新头文件并重新编译 C++ 库**。

### 6.2 为什么大多数情况不用重新编译

```
libarhud_server.so
   └─ DT_NEEDED: libsomeip.so          ← 动态链接，运行时装新库即可
        └─ 调用: SPInit / SPStart / SPServerSendNotify / ...   ← C 接口(extern "C")，版本间稳定
```

- **协议层**：SOME/IP（SD、消息格式）是标准化协议，vsomeip 3.x 内部兼容；
- **C 接口层**：`someip_com.h` 的接口（`SPInit`/`SPStart`/`SPServerSendNotify` 等）是 C ABI，
  私有分支版本迭代中保持稳定；
- **Python 层**：ctypes 绑定的是上述 C 接口，接口不变则 Python 封装零改动；
- **数据层**：pcap 解析、结构体序列化（arhud_pcap/arhud_types）与协议栈版本无关。

### 6.3 标准变更流程（推荐）

```bash
# 1) 从客户端/板端拿到新版 SP 库（libsomeip*.so），替换部署包 libs/
cp <新版libsomeip*.so> /opt/arhud-server/libs/

# 2) 回归验证（推荐跑自动化测试，或直接在板端实测）
cd <仓库> && bash docker/integration_test_cpplib.sh     # 双容器全链路

# 3) 结果判断
#    ✅ 正常 → 完成（无需重新编译）
#    ❌ 报 "undefined symbol" / 接口不匹配 → 需要更新 someip_com.h 并重新编译：
#        cd arhud_python_server
#        cp <新版头文件> include/vsomeip/someip_com.h
#        make clean && make libarhud_server.so SP_LIBS=<新SP库目录>
#    ❌ 配置解析异常（如 SP 栈日志报配置错误）→ 检查/调整配置文件生成（gen_sp_config），重新编译
```

### 6.4 版本配套建议

| 组件 | 版本策略 |
|------|----------|
| 板端客户端二进制 + SP 库 | 板端整体烧录（不变） |
| 板端中间件 SP 库 | 与客户端配套（同机 UDS 协议版本敏感，必须一致） |
| **服务端 SP 库** | **建议与客户端同版本/相近版本**（跨机走标准 SOME/IP，比同机宽松；但一致最稳妥） |
| 服务端 C++ 库 | 由 SP 库版本决定是否重编（见 6.3） |
| Python 封装 | C 接口不变则无需改动 |

### 6.5 例外情况（必须重新编译）

1. **C 接口签名变化**：新版 `someip_com.h` 中 `SPInit/SPStart/SPServerSendNotify` 等参数变了；
2. **配置文件格式变化**：新版 SP 栈解析器不接受旧配置 → 需更新 `gen_sp_config`；
3. **需要新能力**：如新增订阅回调接口、新的 SP 功能 API。

> 判断方法：替换 SP 库后直接运行，`dmesg`/日志出现 `undefined symbol`、`cannot open shared
> object`、或配置解析错误，即属于上述情况。
