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
- **CAN Communication**: ZLG CAN driver (`can_core/driver.py` + `can_core/device.py`, `zlgcan.dll`)
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
- `can_core/driver.py` - ZLG CAN 驱动 Python 绑定（原 `zlgcan_driver.py`）
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

### SOME/IP 回放（someip_core / someip_gui）

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

产物：`verify_report.md` / `verify_report.json`（18 项功能验证，含单元测试）。
容器内**不能**验证真实 CAN 硬件、外部程序界面与 GPU 路径（见该目录 README §6）。

### 文档

- `docs/SOMEIP_REPLAY.md` — SOME/IP 回放（界面布局、库部署、实测与排障）
- `docs/STRUCTURE.md` — 项目结构说明（分层、依赖方向、设计约定、量化对比）
- `docs/PLATFORM_GUIDE.md` — 平台化改造说明与扩展指南
- `docs/UBUNTU_SETUP.md` — Ubuntu 22.04 部署（含 ZLG Linux 驱动安装）
- `docs/PYTHON_COMPATIBILITY.md` — Python 3.10 ~ 3.13 兼容性矩阵与升级步骤
- `docs/WINDOWS_VERIFICATION.md` — Windows 环境验证方法与实测结果
- `docker/windows-sim/README.md` — Windows 验证容器使用说明
