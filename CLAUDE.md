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
- **CAN Communication**: ZLG CAN driver (zlgcan.py, zlgcan.dll)
- **Data Processing**: Pandas, NumPy, openpyxl

## Architecture

### Main Application
- [main.py](main.py) - Tkinter GUI main window with multiple functionality buttons

### Core Modules
- [can_control.py](can_control.py) - ZLG CAN bus communication module
- [zlgcan.py](zlgcan.py) - ZLG CAN driver Python bindings

### GuiFunction/
GUI components and handlers:
- `file_updater.py`, `file_handler.py`, `delete_handler.py` - Test case file management
- `view_case_handler.py`, `view_case_processor.py` - Test case viewing
- `image_handler.py`, `video_processor.py`, `image_player.py` - Image/video processing
- `can_testcase_processor.py` - CAN test case parsing
- `matrix_to_csv.py` - Signal matrix to CSV conversion
- `binhex_gui.py` - CAN data generator

### OtherGui/
- [test_can_gui.py](OtherGui/test_can_gui.py) - CAN signal automated send/receive GUI

### CanDataProcessing/
- CAN data processing utilities, device configuration (can_device_config.xml)

### ImageTest/
- Icon testing and validation using YOLO/OCR

### Simple_Tools/
- `create_gif.py` - GIF creation
- `image_re_name.py` - Batch image renaming
- `images_to_mp4.py` - Image sequence to video
- `video_roi.py` - Video ROI extraction

## CAN Communication

The project uses ZLG CAN devices (USBCANFD series). See [can_control.py](can_control.py) for:
- Device initialization and handling
- Send/receive threads
- Message filtering
- Support for both standard and extended CAN frames

## Key Patterns

- Thread-safe logging via `TextRedirector` class in main.py
- Queue-based cross-thread UI updates
- Global CAN message cache (`received_messages` deque)

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
5. 新增平台相关能力 → 加到 `hudcore/` 并保持"探测 + 回退 + 明确报错提示"的风格。

### 自检与自测

```bash
python tools/check_env.py     # 环境自检（依赖/字体/驱动/外部程序）
python tools/selftest.py      # hudcore 回归自测（跨平台可跑）
./run.sh --check              # Linux 一键自检
```

### 文档

- `docs/PLATFORM_GUIDE.md` — 平台化改造说明与扩展指南
- `docs/UBUNTU_SETUP.md` — Ubuntu 22.04 部署（含 ZLG Linux 驱动安装）
