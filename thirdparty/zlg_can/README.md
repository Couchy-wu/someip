# thirdparty/zlg_can —— ZLG CAN 驱动库（按平台/架构放置）

```
thirdparty/zlg_can/
├── README.md            本文档
├── windows/             Windows 驱动 zlgcan.dll 的放置位置（**当前由仓库根 zlgcan.dll 提供**）
├── linux-aarch64/       Linux aarch64 驱动（libusbcanfd.so / libusbcan.so / libzuds.so / libusb-1.0.so）
├── linux-x86_64/        Linux x86_64 驱动（同上，另有 libusbcanfd800u.so / libusbcan-4e/8e.so）
├── include/             ZLG 官方头文件（usbcanfd / usbcanfd-800u / usbcan-4e / usbcan-8e / usbcan）
└── bitrate.cfg.yaml     位速率配置（Rust 驱动与部分工具使用）
```

> 二进制（`*.so` / `*.dll`）已被 `.gitignore` 忽略：**运行时库不随仓库分发**。
> 本目录下的文件由 `tools/fetch_thirdparty_libs.py` 联网获取（见 §2）。

---

## 1. 程序到哪里找驱动库

`hudcore/can/backend.py` 的探测顺序（先命中先用）：

| 顺序 | 位置 | 说明 |
|------|------|------|
| 1 | `HUD_ZLG_LIB` | 完整文件路径（现场临时替换） |
| 2 | `HUD_ZLG_LIB_DIR` | 目录 |
| 3 | **`thirdparty/zlg_can/<平台>-<架构>/`** | **首选**（如 `linux-x86_64`、`windows-x86_64`） |
| 4 | `thirdparty/zlg_can/<平台>/` | 不分架构时 |
| 5 | `thirdparty/zlg_can/` | 扁平放置 |
| 6 | `drivers/<平台>/`、`drivers/` | 旧位置，兼容既有部署 |
| 7 | 项目根、`libs/`、`LD_LIBRARY_PATH` / `PATH` 中的目录、系统目录 | 兜底 |

候选文件名：`libzlgcan.so` → `libusbcanfd.so` → `libusbcan.so` → `libcanfd.so`
（Windows 为 `zlgcan.dll` 等）。

探测时还会**识别接口类型**并在自检里显示（`hudcore.can.library_api_kind`）：

- `zcan`：导出 `ZCAN_OpenDevice` 等 → 走 ZCAN 直连后端
- `vci`：导出 `VCI_OpenDevice` 等 → 走 **VCI 适配层**（见 §3），功能同样可用
- `error`：库定位到了但**加载失败**（多为缺依赖，如 `libusb-1.0.so.0`）→ 设 `LD_LIBRARY_PATH` 指向该目录
- `unknown`：既无 ZCAN 也无 VCI 导出

自检命令：

```bash
python -c "from hudcore.can import describe_library_status as d; print(d())"
```

---

## 2. 获取方式

### Windows（已有，无需下载）

仓库根目录的 `zlgcan.dll` 是 ZCAN 接口的 Windows 驱动（随仓库分发）；
`thirdparty/zlg/` 内还有 ZLG SDK 的配套 DLL（`kerneldlls` 系列）。
如需换版本，把新的 `zlgcan.dll` 放到 `thirdparty/zlg_can/windows-x86_64/` 或设置 `HUD_ZLG_LIB`。

### Linux（联网获取）

ZLG 的 Linux 驱动没有公开的官方直链；本项目从一个公开镜像仓库获取：

```bash
python tools/fetch_thirdparty_libs.py zlg                 # 默认本机架构
python tools/fetch_thirdparty_libs.py zlg --arch x86_64   # 指定架构
```

来源：<https://github.com/jesses2025smith/rust-can/tree/zlg-lib>（该分支的 `library/linux/<架构>/`）。
脚本会把 `*.so` 放到 `thirdparty/zlg_can/<平台>-<架构>/`，头文件放 `include/`，并做一次加载校验。

运行前需要把该目录加入库搜索路径（库之间有相互依赖）：

```bash
export LD_LIBRARY_PATH=$PWD/thirdparty/zlg_can/linux-x86_64:$LD_LIBRARY_PATH
python main.py
```

系统依赖（Ubuntu）：

```bash
sudo apt install -y libusb-1.0-0 libusb-1.0-0-dev
# 设备权限（按 ZLG 手册提供的 udev 规则，或用 root 运行）
```

---

## 3. Linux 库是 **VCI 接口**：已由内置适配层支持

实测（`readelf --dyn-syms`）：

| 平台 | 库 | 导出 ZCAN_* | 导出 VCI_* |
|------|----|-------------|-----------|
| linux aarch64 | `libusbcanfd.so` | 0 | 30 |
| linux x86_64 | `libusbcanfd.so` | 0 | 31 |
| linux x86_64 | `libusbcanfd800u.so` | 18（**无 `ZCAN_SetValue`**） | 36 |
| linux x86_64 | `libusbcan-4e.so` / `-8e.so` | 12（**无 `ZCAN_SetValue`**） | 0 |
| windows x86_64 | `zlgcan.dll` | ✅（项目驱动按此编写） | — |

结论与应对：

- **Windows**：`ZCAN_*` 直连，行为不变；
- **Linux**：公开驱动是 `VCI_*` 形态（没有句柄、用"设备类型/序号/通道号"三元组定位），
  项目已内置 **VCI 适配层**，业务代码（`can_core/receive.py`、`transmit.py`、界面、用例执行器）
  **无需改动**：

  | 模块 | 职责 |
  |------|------|
  | `can_core/vci_driver.py` | VCI 结构体与函数原型（布局对齐 `include/usbcanfd/zcan.h`）+ `as_int()` 等工具 |
  | `can_core/vci_adapter.py` | `VciCanDriver`：把 ZCAN 调用面翻译成 VCI 调用；波特率→`ZCAN_INIT` 时序；属性键映射 |
  | `can_core/driver_factory.py` | 按库**实际导出的符号**选择后端（ZCAN 直连 / VCI 适配） |

  注意 `libusbcanfd800u.so` 虽然导出 `ZCAN_*`，但**没有业务层配波特率用的 `ZCAN_SetValue`**，
  因此仍走 VCI 适配层（否则会"能打开设备、波特率配不上"）。

- 同目录依赖按 **SONAME** 互相引用，而 SDK 里的文件名常常不是 SONAME
  （目录里是 `libusb-1.0.so`，而 `libusbcanfd.so` 的 NEEDED 写的是 `libusb-1.0.so.0`）。
  `hudcore.can.backend.preload_sibling_libraries()` 会在 dlopen 前用绝对路径 +
  `RTLD_GLOBAL` 预加载同目录依赖，因此**不需要手工造软链或设 `LD_LIBRARY_PATH`**；
  否则探测会静默回退到不支持 CANFD 的 `libusbcan.so`（表现为"能连上却发不出 CANFD"）。

### 3.1 没有硬件时怎么验证

```bash
./docker/can-sim/run_check.sh          # 编译 VCI 桩库 + 单测 + 业务层收发回环
```

桩库 `docker/can-sim/vci_stub.c` 按真实 ABI 实现全部 VCI 接口（发送即回环），
可验证"驱动探测 → 接口形态判定 → 适配 → 打开/初始化/收发/关闭"整条链路；
**不能**验证真实波特率与时序是否被硬件接受（需现场设备，见 §3.2）。

### 3.2 需要现场确认的两点

1. **CAN 控制器时钟**：适配层按 `baud = clk / (brp * (1 + tseg1 + tseg2))` 换算时序，
   默认 `clk = 40 MHz`（由官方样例 `include/usbcanfd-800u/test.cpp` 的两组时序值反推，
   单测会断言能重现样例）。若现场波特率对不上，用 `HUD_VCI_CLK=<Hz>` 覆盖；
2. **采样点**：默认仲裁段 80%、数据段 75%（同官方样例），可用
   `HUD_VCI_SAMPLE_POINT` / `HUD_VCI_SAMPLE_POINT_DATA`（可写 `80` 或 `0.8`）覆盖。

排障：`python -c "from can_core import describe_driver_status as d; print(d())"`
会打印命中库、接口形态与所用后端。

---

## 4. 目录里的文件从哪来（可追溯）

| 文件 | 来源 |
|------|------|
| `linux-aarch64/*.so`、`linux-x86_64/*.so` | `tools/fetch_thirdparty_libs.py zlg`（镜像仓库 `rust-can#zlg-lib`） |
| `include/**` | 同上（ZLG 官方头文件：`zlgcan.h`、`controlcan.h`、`config.h` 等） |
| `bitrate.cfg.yaml` | 同上 |
| `windows/`（空） | 由仓库根 `zlgcan.dll` + `thirdparty/zlg/` 提供；如需升级可放到这里 |
