# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HudAutoTest is a GUI-based automated testing application for HUD (Head-Up Display) systems. It provides test case management, CAN bus communication, image/video processing, and OCR capabilities for testing automotive HUD displays.

## Running the Application

```bash
python main.py
```

## Key Dependencies

- **GUI**: Tkinter (built-in)
- **OCR**: PaddleOCR, EasyOCR
- **Computer Vision**: OpenCV, Ultralytics (YOLO)
- **CAN Communication**: ZLG CAN driver（Windows `zlgcan.dll` 走 ZCAN 直连；Linux `libusbcanfd.so`
  是 VCI 形态，由 `can_core/vci_adapter.py` 适配，见下文"驱动接口形态与 VCI 适配层"）
- **数据目录**: `data/`（信号矩阵、设备配置、平台分辨率、标定结果；见 `hudcore.platform.paths.data_dir`）
- **第三方内容**: `thirdparty/<名称>/`（ultralytics / paddleocr / zlg / ffmpeg / models）；
  **运行时库**按 `thirdparty/<组件>/<平台>-<架构>/` 放置（arhud_someip、zlg_can），
  库文件不入库；定位用 `paths.thirdparty("名称")`，说明见 `thirdparty/README.md`
- **库获取**: `python tools/fetch_thirdparty_libs.py zlg`（ZLG Linux 驱动）；
  SOME/IP 库需就地编译（脚本会打印步骤）
- **Data Processing**: Pandas, NumPy, openpyxl

## Architecture

### Main Application
- [main.py](main.py) - Tkinter GUI main window with multiple functionality buttons

### Core Modules
- `can_core/device.py` - ZLG CAN 设备与通道操作（原 `can_control.py`）
- `can_core/driver.py` - ZLG CAN 驱动 **ZCAN 接口** Python 绑定（原 `zlgcan_driver.py`）
- `can_core/driver_factory.py` - 按驱动库**实际导出的符号**选择后端（ZCAN 直连 / VCI 适配）
- `can_core/vci_driver.py` / `can_core/vci_adapter.py` - Linux VCI 接口绑定与适配层（详见下文）
- `hudcore/logging_setup.py` - 统一日志初始化（原根目录 `log_setup.py`）

### gui_handlers/
GUI components and handlers:
- `testcase_menu.py`, `testcase_upload.py`, `testcase_delete.py` - Test case file management
- `testcase_open_table.py`, `testcase_view_log.py` - Test case viewing
- `image_open.py`, `video_extract_frames.py`, `image_sequence_player.py` - Image/video processing
- `can_testcase_parser.py` - CAN test case parsing
- `signal_matrix_to_csv.py` - Signal matrix to CSV conversion
- `can_data_generator.py` - CAN data generator

### can_gui/
- [can_send_receive_gui.py](can_gui/can_send_receive_gui.py) - CAN signal automated send/receive GUI

### can_data_tools/
- CAN data processing utilities, device configuration (can_device_config.xml)

### image_testing/
- Icon testing and validation using YOLO/OCR

### misc_tools/
- `gif_creator.py` - GIF creation
- `image_batch_rename.py` - Batch image renaming
- `images_to_video.py` - Image sequence to video
- `video_roi_crop.py` - Video ROI extraction

## CAN Communication

The project uses ZLG CAN devices (USBCANFD series). See `can_core/device.py` for:
- Device initialization and handling
- Send/receive threads
- Message filtering
- Support for both standard and extended CAN frames

### 驱动接口形态与 VCI 适配层（Linux 必读）

ZLG 在不同平台给出**两套形态**的库，业务层只按 Windows 的 **ZCAN** 形态编写：

| 平台 | 库 | 形态 | 后端 |
|------|----|------|------|
| Windows | `zlgcan.dll` | ZCAN（有句柄，属性用 `ZCAN_SetValue(handle,"0/xxx",...)`） | `driver.ZCAN` 直连 |
| Linux | `libusbcanfd.so` | VCI（**无句柄**，用"设备类型/序号/通道号"三元组；配置走 `ZCAN_INIT` + `VCI_SetReference`） | `vci_adapter.VciCanDriver` |

- 选路由 `can_core/driver_factory.open_can_driver()` 完成，`can_state.zcanlib` 已改为调用它，
  因此**业务代码/界面/用例执行器不需要任何平台分支**；
- VCI 适配层负责：句柄 ↔ 三元组、波特率 → `ZCAN_INIT` 时序（`calc_canfd_timing`）、
  属性键 → `VCI_SetReference`、报文标志位（扩展帧/远程帧/BRS/回显/队列发送）双向翻译；
- **Python 3.13 注意**：`int(ctypes.c_uint(41))` 会抛 `ValueError`（3.10~3.12 正常），
  取 ctypes 常量一律用 `can_core.vci_driver.as_int()`；
- 同目录依赖按 SONAME 互相引用而文件名常与 SONAME 不一致（`libusb-1.0.so` vs
  `libusb-1.0.so.0`），`hudcore.can.backend.preload_sibling_libraries()` 会在 dlopen 前预加载，
  因此不需要手工软链或 `LD_LIBRARY_PATH`；
- 无硬件验证：`./docker/can-sim/run_check.sh`（VCI 桩库 + 适配层单测 + 业务层收发回环）；
- 现场可能需要微调：`HUD_VCI_CLK`（默认 40 MHz）、`HUD_VCI_SAMPLE_POINT`（默认 80%）/
  `HUD_VCI_SAMPLE_POINT_DATA`（默认 75%）。

## Key Patterns

- Thread-safe logging via `TextRedirector` class in main.py
- Queue-based cross-thread UI updates
- Global CAN message cache (`received_messages` deque, in `can_core/device.py`)

---

## 平台化架构（v2 新增）

项目支持 **Windows + Ubuntu 22.04**，平台差异全部收敛到 `hudcore/` 层，业务代码不区分系统。

### hudcore 结构

- `hudcore/platform/system.py` — OS 探测（`IS_WINDOWS` / `IS_LINUX` / `IS_UBUNTU`、后缀、pathsep）
- `hudcore/platform/paths.py` — 统一路径（`paths.project_root/logs_dir/drivers_dir/bin_dir/testcase_dir`）
- `hudcore/platform/executables.py` — 外部程序探测（ffmpeg / Office / 编辑器 / 终端）+ 打开文件
- `hudcore/platform/fonts.py` — Tk 字体回退链 + PIL 中文字体文件探测（`load_pil_font`）
- `hudcore/can/backend.py` — CAN 驱动库探测与加载（Windows `WinDLL` / Linux `CDLL`）
- `hudcore/ui/theme.py` — 配色与控件样式工厂（字体走跨平台回退）
- `hudcore/ui/text_redirector.py` — print→Tk Text 线程安全重定向（tkinter 软依赖）

### 开发约定

1. **不要**再写 `platform.system() == "Windows"` 分支 —— 用 `hudcore.platform.system` 的常量或探测函数；
2. **不要**硬编码外部程序路径 —— 用 `find_executable()` / `get_ffmpeg()` / `get_office_app()`；
3. **不要**硬编码字体名/字体文件 —— 用 `Theme` / `get_ui_font_name()` / `load_pil_font()`；
4. **不要**写死 `./zlgcan.dll` —— 用 `hudcore.can.load_zlg_library()`（自动按平台探测）；
5. 新增平台相关能力 → 加到 `hudcore/` 并保持"探测 + 回退 + 明确报错提示"的风格；
6. **根目录只放 `main.py`**；共享库模块必须进包，面向使用者的独立脚本放 `scripts/`，
   业务数据与运行期状态放 `data/`（`paths.data_dir`）；
7. 每个包都有 `__init__.py` 声明职责与依赖约束；新模块放入对应包，不要新增根级模块；
8. **不要**用 `sys.path.append`/`import *` 绕过包结构 —— 用标准包导入（子模块用 `python -m 包.模块` 运行）；
9. 不要让 import 产生副作用（不要在模块级建 GUI、解析命令行、写日志文件、读大文件）；
10. 移动/拆分模块后**必须**跑 `python tools/check_static.py` —— 容器验证覆盖不到
    硬件与界面路径，`undefined name` 这类问题只能靠静态检查拦住。

### 自检与自测

```bash
python tools/check_env.py       # 环境自检（依赖/版本/字体/驱动/外部程序）
python tools/selftest.py        # hudcore 回归自测（跨平台可跑）
python tools/check_imports.py   # 项目内部导入静态校验（重构改名后兜底）
python tools/check_static.py     # 静态检查（pyflakes：undefined name 等，需 pip install pyflakes）
python -m pytest tests -q        # 单元测试 + 架构规则守卫（需 pip install pytest）
./run.sh --check                # Linux 一键自检
```

验证报告：`docker/windows-sim/verify_windows.py` 跑完后由 `tools/verify_report.py` 生成
Markdown + JSON（自动判断运行环境标签、记录逐项耗时、列出失败/跳过原因，并与**上一次报告**做
回归对比：新增失败 / 已修复 / 持续失败）。改报告格式请同步 `tests/test_verify_report.py`。

### Di 测试用例（can_data_tools/di_case_*，与旧链路并存）

- **两套格式用开关区分**（`can_data_tools/case_format.py`，默认 `legacy`）：
  旧格式走 `gui_handlers/can_testcase_parser.py`（**未改动**）；Di 格式走
  `can_data_tools/di_case_parser.py` + `di_case_runner.py`；
  开关优先级：`case_format.set_format()`（GUI）→ `HUD_TESTCASE_FORMAT` → 默认 legacy；
- 用例在 `TestcaseCollection/Di_testcases/`（497 个，**只读基线**），格式与实测分布见
  `docs/DI_TESTCASES.md`；
- 三个易踩的点：
  1. Di 的 `bit_range` 是 **0 起字节号**（`"0.0"`→`data[0]`，最大 `"46.0-46.7"`→64 字节 CANFD），
     与项目既有 `can_core.bit_utils` 的 1 起不同 → 一律用 `can_data_tools/can_bit_writer.py`
     并显式传 `base`（`DI_BASE=0` / `LEGACY_BASE=1`）；
  2. 415 条 CAN 条目没有位域（只写"门控有效"）→ 记为不可编码，可用
     `data/DI_Config/gate_frame.json` 补默认位，**不要猜**；
  3. `mem` 字段（482 条）是 HUD 内部状态量，外部无法注入 → 执行器如实列为"需台架注入"；
- 标贴校验：标签→参考图映射在 `data/DI_Config/label_map.json`，参考图/位置来自
  `data/UI_Config/*.json` + `Resources/ImageUI/`，比对用 `image_testing` 的 dHash；
  没有参考图的标签记为 `no_reference`（不算通过）；
- 入口：`python -m scripts.run_di_cases`（体检/执行/报告）、GUI 主界面 **[Di 测试用例]** 按钮；
- 单测：`tests/test_di_cases.py`（解析/位写入/执行/校验/开关）。

### SOME/IP 回放（someip_core / someip_gui）

- **两代服务表**（`someip_core.models`，开关 `HUD_SOMEIP_TABLE` / `set_table()` / 界面下拉）：
  `old`（11 服务/23 事件，**默认**）与 `bplus`（6 服务/38 事件）；
  **两代都由服务端库注册**：`ReplayController.open()` 会把当前代写入 `ARHUD_SERVICE_PROFILE`
  （库在 create() 时读它），两边不一致时以服务表代为准并告警 —— 不要手工只改一侧；
- 回放计数语义：`replay_sent` 只统计**真正成功**，`arhud_server_replay_attempted()` 统计尝试次数，
  差值 = 未注册事件数（profile 选错的第一指标）；
- **随仓库分发的 vsomeip 配置**：`data/someip/config/*.json`（来自参考实现 lipeng20260228），
  `ReplayConfig.config_path` 留空时用当前代的配置（`someip_core.config.shipped_config_path()`）；
- 库版本已对齐参考实现 `libs.zip`（aarch64 2025-12-15 / x86_64 2025-12-23）；
  `thirdparty/arhud_someip/windows/` **按要求留空**；
- 一键自检：`python -m scripts.someip_replay_check`（自带样例 pcap，clone 后即可跑）；
- 单测 `tests/test_someip_tables.py` 会逐条比对"配置 ↔ 代码表"，防止三者漂移；
- 业务：`someip_core/`（models 定义表 / api ctypes 绑定 / pcap_info 解析 / config / replay 控制器），
  **不依赖界面**；库探测在 `hudcore/someip/backend.py`（环境变量 → `drivers/someip/<平台>/` → 系统路径）
- 界面：`someip_gui/`（独立窗口；左侧配置、右侧回放/发送/日志；字段表由 ctypes 结构体自动生成）
- 约定：库**惰性加载**（不在 import 时 dlopen）；Windows DLL 暂缺时窗口照常打开、动作置灰并给提示
- 文档：`docs/SOMEIP_REPLAY.md`（含实测结果与排障）

### 单元测试与架构规则守卫

`tests/` 下的 pytest 用例除了核心行为（位工具/CAN 状态与编码/日志解析/平台路径），
还包含 **架构规则守卫**：包必须有 `__init__.py`、禁止 `import *`、禁止业务代码
`sys.path` 注入、禁止模块级副作用（建 GUI/跑 mainloop/解析命令行）、根目录只放入口。
改动结构后这些用例会直接失败，防止已确立的约定被破坏。

### 命名约定与重构工具

目录/文件命名统一使用"见名知意"的英文；映射关系与自动改名能力都保留在
`tools/rename_modules.py`（支持 `--dry-run` / `--apply`，内部对驱动库文件名与
第三方目录做了保护，不会误改 `zlgcan.dll` / `libzlgcan.so` 等）。

| 旧名 | 新名 | 含义 |
|------|------|------|
| `GuiFunction/` | `gui_handlers/` | 主界面各功能事件处理器 |
| `OtherGui/` | `can_gui/` | CAN 收发 GUI |
| `CanDataProcessing/` | `can_data_tools/` | CAN 数据解析与检索 |
| `ImageTest/` | `image_testing/` | 图标测试 |
| `CameraUtils/` | `camera_tools/` | 相机与图像工具 |
| `Simple_Tools/` | `misc_tools/` | 杂项小工具 |
| `Auto label/` | `auto_labeling/` | 自动标注 |
| `zlgcan.py` / `mylog.py` | `can_core/driver.py` / `hudcore/logging_setup.py` | 驱动绑定 / 日志 |
| `can_control.py` | `can_core/device.py` | CAN 设备与通道操作 |
| `image_preprocessing.py` | `auto_labeling/preprocessing.py` | 图像预处理（就近下沉） |
| 根目录 `log_setup.py` | `hudcore/logging_setup.py` | 横切基础设施归入 hudcore |
| `train_freeze.py` / `image_test.py` | `scripts/yolo_train.py` / `scripts/ocr_icon_test.py` | 训练 / OCR 测试 |
| 根目录数据文件（信号矩阵/设备配置/分辨率…） | `data/`（`paths.data_dir`） | 业务数据与代码分离 |

> 日志按"模块级函数"使用（如 `logging_setup.info(...)`、`logging_setup.setup_logger(...)`，
> 模块为 `hudcore/logging_setup.py`），改名时必须同步更新全部调用点。

### Python 版本

- 支持 **3.10 ~ 3.13**；版本策略集中在 `hudcore/platform/system.py`
  （`PYTHON_MIN` / `PYTHON_MAX_TESTED` / `python_status()`）；
- 3.13 依赖清单：`requirements-py313.txt`（含 `paddlepaddle>=3.2.1` 等下限）；
- **不要**在 f-string 表达式内使用反斜杠（3.10/3.11 会直接语法错误）；
- 详细矩阵与排障见 `docs/PYTHON_COMPATIBILITY.md`。

### Windows 环境验证（无 Windows 机器时）

`docker/windows-sim/` 用 Wine + Windows 版 CPython 在容器内构造 Windows 运行时：

```bash
cd docker/windows-sim && ./build.sh && ./run_verify.sh
```

产物：`verify_report.md` / `verify_report.json`（19 项功能验证，含单元测试）。
容器内**不能**验证真实 CAN 硬件、外部程序界面与 GPU 路径（见该目录 README §6）。

### CAN VCI 适配层验证（Linux，无需硬件）

```bash
./docker/can-sim/run_check.sh     # 编译 VCI 桩库 + 适配层单测 + 业务层收发回环
```

桩库 `docker/can-sim/vci_stub.c` 按真实 ABI 实现全部 VCI 接口（发送即回环），
覆盖"探测 → 形态判定 → 适配 → 打开/初始化/收发/关闭"；验证不到的项见该目录 README §4。

### 文档

- `docs/SOMEIP_REPLAY.md` — SOME/IP 回放（界面布局、库部署、实测与排障）
- `docs/STRUCTURE.md` — 项目结构说明（分层、依赖方向、设计约定、量化对比）
- `docs/PLATFORM_GUIDE.md` — 平台化改造说明与扩展指南
- `docs/UBUNTU_SETUP.md` — Ubuntu 22.04 部署（含 ZLG Linux 驱动安装）
- `docs/DI_TESTCASES.md` — Di 测试用例（格式规范、格式开关、三类输入支持度、标贴校验覆盖）
- `docs/PYTHON_COMPATIBILITY.md` — Python 3.10 ~ 3.13 兼容性矩阵与升级步骤
- `docs/WINDOWS_VERIFICATION.md` — Windows 环境验证方法与实测结果
- `docker/windows-sim/README.md` — Windows 验证容器使用说明
