# docker/can-sim —— CAN（VCI）验证环境：无需 ZLG 硬件

本目录提供 **ZLG Linux 驱动的 VCI 接口桩库**，用于在没有 CAN 硬件的情况下验证
"驱动探测 → 接口形态判定 → VCI 适配 → 打开/初始化/收发/关闭"整条链路。

```
can-sim/
├── vci_stub.c         VCI 接口桩库（真实 ABI：结构体/调用约定与官方头文件一致）
├── loopback_demo.py   业务层回环演示（用项目自身的 can_core.device 跑在桩库上）
└── run_check.sh       一键：编译桩库 → 跑适配层单测 → 跑业务层回环
```

## 1. 用法

```bash
./docker/can-sim/run_check.sh          # 两步都跑（推荐）
./docker/can-sim/run_check.sh unit     # 只跑适配层单测
./docker/can-sim/run_check.sh demo     # 只跑业务层回环
OUT=/tmp/xx ./docker/can-sim/run_check.sh    # 指定桩库输出目录（默认 /tmp/hud-can-sim）
```

依赖：`gcc`、`pytest`（Ubuntu：`sudo apt install -y gcc python3-pytest`）。

## 2. 桩库做了什么

`vci_stub.c` 导出官方头文件声明的**全部 VCI 函数**（`VCI_OpenDevice` / `VCI_InitCAN` /
`VCI_Transmit(FD)` / `VCI_Receive(FD)` / `VCI_TransmitData` / `VCI_SetReference` …），行为：

| 行为 | 说明 |
|------|------|
| 打开/初始化/启动/关闭 | 一律成功（返回 1） |
| **发送即回环** | 发出去的帧进入该通道接收队列，并置上"发送帧"标志（bit13） |
| 接收 | 从队列取出；`VCI_GetReceiveNum` 返回队列长度 |
| 初始化参数 | 记录最后一次 `ZCAN_INIT`，供测试校验波特率时序换算 |
| 引用（配置） | 记录 `(通道, 引用码, 值)`；设备名（12/13）会真正存取 |
| 合并接收 | `VCI_TransmitData`/`VCI_ReceiveData` 走独立的 92 字节 `ZCANDataObj` 队列 |
| 自省接口 | `vci_stub_*` 系列（真实驱动没有，仅供测试断言） |

**为什么它能发现问题**：桩库按官方头文件的**真实结构体布局**读写内存。若 Python 侧
ctypes 布局有偏差（字段顺序、位域位置、联合体长度），回环回来的字段就会错乱，测试立刻失败。

## 3. 两层验证

| 层 | 用什么 | 覆盖什么 | 跑法 |
|----|--------|----------|------|
| 逻辑层 | Python 假 VCI 库（`tests/test_can_vci_adapter.py::FakeVciLib`） | 句柄映射、端口号保留、报文标志位、合并接收枚举归一、属性键映射、时序换算规则 | 始终运行 |
| ABI 层 | `vci_stub.c` 编译出的 `.so` | 结构体布局、指针参数、`byref` 传参、真实 `dlopen` 路径 | `HUD_VCI_STUB_SO=<so>` |
| 业务层 | `loopback_demo.py` | 项目自身的 `Initialize_Canfd_Device` / `Send_Can(FD)` / 接收线程 / `Close_Canfd_Device` | `HUD_ZLG_LIB=<so>` |

`run_check.sh` 会把三层都跑一遍。业务层回环的实测输出（aarch64 容器）：

```
适配后端: VciCanDriver
设备句柄=0x5A000000 通道=['0x5b000000', '0x5b000001'] 接收线程=2
[通过] CANFD 回环：{'can_id': '0x123', 'data_list': [17, 34, 51, 68], 'dlc': 4, ...}
[通过] 扩展帧回环：{'can_id': '0x18ff50e5', 'data_list': [170, 187], ...}
[通过] CAN 回环：{'can_id': '0xa1', 'data_list': [1, 2], ...}
[通过] 设备已正常关闭
```

## 4. 验证不了什么（必须现场确认）

- **真实波特率/时序是否被硬件接受**：适配层按
  `baud = clk / (brp * (1 + tseg1 + tseg2))` 换算，默认 `clk = 40 MHz`、
  采样点仲裁段 80% / 数据段 75%（依据官方样例反推，单测断言能重现样例数值）。
  现场若对不上，用 `HUD_VCI_CLK` / `HUD_VCI_SAMPLE_POINT` / `HUD_VCI_SAMPLE_POINT_DATA` 覆盖。
- **设备固件差异**：不同卡型对个别引用码（如 `SETREF_*`）的支持情况；
  适配层对不支持的引用码只告警一次，不影响其余流程。
- **USB 权限/udev 规则**：桩库不碰 USB，实机需按 ZLG 手册装 udev 规则。

## 5. 与 `docker/windows-sim/` 的关系

| 目录 | 目标 | 手段 |
|------|------|------|
| `docker/windows-sim/` | 验证**整个上位机**在 Windows（Wine + Windows CPython 3.13）下可用 | Windows 版 CAN 桩 `zlgcan.dll` + 19 项功能套件 |
| `docker/can-sim/`（本目录） | 验证 **Linux 上 VCI 驱动形态**可用 | VCI 桩库 + 适配层单测 + 业务层回环 |
