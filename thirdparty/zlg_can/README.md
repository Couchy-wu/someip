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

- `zcan`：导出 `ZCAN_OpenDevice` 等 → **本项目驱动可用**
- `vci`：导出 `VCI_OpenDevice` 等 → 与本项目驱动不匹配（见 §3）
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

## 3. 重要：Linux 库是 **VCI 接口**，与本项目驱动不匹配

实测（`nm -D --defined-only`）：

| 平台 | 库 | 导出 ZCAN_* | 导出 VCI_* |
|------|----|-------------|-----------|
| linux aarch64 | `libusbcanfd.so` | 0 | 30 |
| linux x86_64 | `libusbcanfd.so` | 0 | 31 |
| windows x86_64 | `zlgcan.dll` | ✅（项目驱动按此编写） | — |

也就是说：

- **Windows**：驱动走 `ZCAN_*`（`hudcore.can` + `can_core/driver.py`）✅ 现状可用；
- **Linux**：公开可下载的是 `VCI_*` 接口，`can_core/driver.py` 直接调用 `ZCAN_*` 会失败
  （表现为 `Exception on OpenDevice!` 之类），因此本目录的 Linux 库目前**只完成"获取与放置"**，
  还缺一层适配。

让 Linux CAN 真正可用的三条路（按推荐度）：

1. **补充 VCI 适配层**（推荐）：新增 `can_core/vci_*.py`，把项目用到的最小操作
   （打开设备 / 初始化通道 / 启动 / 发送 CAN 与 CANFD / 接收 / 关闭）映射到 `VCI_*`；
   硬件自动发送、合并接收等在 VCI 侧不可用，用软件定时器与软件合并替代。
   工作量约 300~500 行，且有设备后即可验证。
2. **取得 ZCAN 接口的 Linux 库**：向 ZLG 索取提供 `libzlgcan.so`（ZCAN 统一接口）的 Linux SDK，
   放到本目录即可直接被现有驱动使用（`hudcore.can` 首选名即 `libzlgcan.so`）。
3. **纯 VCI 场景走 python-can**：`pip install zlgcan python-can` 后使用 python-can 的 zlg 后端
   （Rust 实现，自带 Linux 支持），但这与本项目现有 CAN 界面/用例执行器是两套通道。

---

## 4. 目录里的文件从哪来（可追溯）

| 文件 | 来源 |
|------|------|
| `linux-aarch64/*.so`、`linux-x86_64/*.so` | `tools/fetch_thirdparty_libs.py zlg`（镜像仓库 `rust-can#zlg-lib`） |
| `include/**` | 同上（ZLG 官方头文件：`zlgcan.h`、`controlcan.h`、`config.h` 等） |
| `bitrate.cfg.yaml` | 同上 |
| `windows/`（空） | 由仓库根 `zlgcan.dll` + `thirdparty/zlg/` 提供；如需升级可放到这里 |
