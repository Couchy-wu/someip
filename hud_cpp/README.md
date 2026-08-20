# AR-HUD 23 服务 C++ 客户端（vsomeip C++ 库 + 自研大端编解码）

用 **C++ vsomeip 库**实现的标准客户端：**单个 application 订阅全部 23 个事件**（11 个服务），
载荷用一套自包含的 C++ **大端（网络序）编解码层**（对应 Python `hud/hud_data_types.py`，
字段顺序/字节序/字符串BOM格式/动态数组长度 完全一致）。

## 文件

| 文件 | 说明 |
|---|---|
| `hud_data_types.hpp/.cpp` | "sp" 序列化层等价物：23 事件注册表 + 12 种已定义类型 序列化/反序列化 + 自测 |
| `hud_client.cpp` | vsomeip C++ 客户端：request_service/request_event/subscribe ×23，一个回调分发解析 |
| `vsomeip_client.json` | 客户端配置（`routing: "arhud01"` = Python 服务端第一个应用） |
| `Makefile` | `make` 构建（依赖 vsomeip3） |

> 若你有项目自研的 **sp 库**：`hud_client.cpp` 的 `on_message` 里调用
> `hud::deserialize_by_kind(...)` 处即替换点——换成 sp 的解析接口即可，传输/订阅层不变。

## 构建

```bash
# Ubuntu/Docker 内（需 vsomeip 头文件与 libvsomeip3）
make            # 生成 ./hud_client
# 或手动:
# g++ -std=c++14 -I/usr/local/include hud_client.cpp hud_data_types.cpp \
#     -L/usr/local/lib -lvsomeip3 -o hud_client
```

## 运行（配合 Python 服务端）

```bash
# 终端 A：Python 服务端（vsomeip_py）
cd ../hud
python3 hud_server.py

# 终端 B：C++ 客户端
cd ../hud_cpp
cp vsomeip_client.json ./vsomeip.json
./hud_client
```

预期日志：
```
[hud_cpp] 大端编解码自测通过 ✓  订阅 23 个事件
[avail] svc=0x000A inst=0x000A available
[recv] #1 svc=0x000A event=0x8001 VehiclePositionInfoNotify  len=211 已收 1/23  Counter=1 Lon=116.397 Lat=39.908 lanes=3
[recv] #23 svc=0x010A event=0x8004 OverseasHudRoadInfoNotify  len=6  已收 23/23  HEX=...
[done] 全部 23 个事件均已收到，退出
```

环境变量：`HUD_EXIT_ALL=1`（收齐自动退出，测试用）；配置用 `VSOMEIP_CONFIGURATION` 或当前目录 `vsomeip.json`。

## 与 Python 客户端对比

| | C++ 客户端（本目录） | Python 客户端（hud/hud_client.py） |
|---|---|---|
| 应用数 | **1 个**（标准 vsomeip） | 11 个（vsomeip_py 包装层限制） |
| 订阅 | `request_service/request_event/subscribe(5参, 按事件)` ×23 | `on_event` ×23 |
| 序列化 | C++ 大端编解码（hud_data_types.cpp） | Python struct `>` |
| 依赖 | vsomeip C++ 库 | vsomeip_py |
| 与 Python 服务端兼容 | ✅ 已实测（23/23） | ✅ 已实测 |

## 双机注意

双机（跨主机）时：`unicast`=本机真实 IP、`routing` 指向本机 RM 宿主（vsomeipd 或自身应用名）、
SD 开启；**多事件同组必须用 5 参 `subscribe(..., event)` 按事件订阅**（4 参只按组在远程只投递组内
首个事件，vsomeip 3.4.10 实测行为）。仓库双机测试 `docker/integration_test_dual_host.sh` 已覆盖
C++ 客户端双机（23/23）。

## 测试

```bash
# 仓库集成测试（Python 服务端 ↔ C++ 客户端）
bash docker/run_tests.sh   # 含 [11/11] AR-HUD C++ 客户端测试
```
