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
6. **根目录只放入口**（`main.py` 与独立脚本）—— 共享库模块必须进包，避免"根目录杂货间"；
7. 每个包都有 `__init__.py` 声明职责与依赖约束；新模块放入对应包，不要新增根级模块；
8. **不要**用 `sys.path.append`/`import *` 绕过包结构 —— 用标准包导入（子模块用 `python -m 包.模块` 运行）；
9. 不要让 import 产生副作用（不要在模块级建 GUI、解析命令行、写日志文件、读大文件）。

### 自检与自测

```bash
python tools/check_env.py       # 环境自检（依赖/版本/字体/驱动/外部程序）
python tools/selftest.py        # hudcore 回归自测（跨平台可跑）
python tools/check_imports.py   # 项目内部导入静态校验（重构改名后兜底）
./run.sh --check                # Linux 一键自检
```

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
| `train_freeze.py` / `image_test.py` | `yolo_train.py` / `ocr_icon_test.py` | 训练 / OCR 测试 |

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

产物：`verify_report.md` / `verify_report.json`（17 项功能验证）。
容器内**不能**验证真实 CAN 硬件、外部程序界面与 GPU 路径（见该目录 README §6）。

### 文档

- `docs/PLATFORM_GUIDE.md` — 平台化改造说明与扩展指南
- `docs/UBUNTU_SETUP.md` — Ubuntu 22.04 部署（含 ZLG Linux 驱动安装）
- `docs/PYTHON_COMPATIBILITY.md` — Python 3.10 ~ 3.13 兼容性矩阵与升级步骤
- `docs/WINDOWS_VERIFICATION.md` — Windows 环境验证方法与实测结果
- `docker/windows-sim/README.md` — Windows 验证容器使用说明
