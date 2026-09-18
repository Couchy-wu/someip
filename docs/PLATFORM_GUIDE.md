# 平台化改造说明（PLATFORM_GUIDE）

> 本次改造目标：在**不破坏原有 Windows 使用方式**的前提下，让 HudAutoTest 可在
> **Ubuntu 22.04**（及主流 Linux）运行；同时把平台相关代码收敛到独立层，提升模块化与通用性。

---

## 1. 改造原则

| 原则 | 做法 |
|------|------|
| **零破坏** | 原有模块名、类名、函数签名、业务逻辑保持不变；只在平台相关处替换实现 |
| **单一职责** | 新增 `hudcore/` 只负责"平台差异 + 通用能力"，不掺业务逻辑 |
| **可探测可回退** | 驱动库、外部程序、字体全部走"探测链 + 回退"，缺失时给出**明确修复命令**而非崩溃 |
| **可自检** | 提供 `tools/check_env.py`（环境自检）与 `tools/selftest.py`（平台层回归自测） |

---

## 2. 新增结构

```
HudAutoTest/
├── hudcore/                     # ★ 新增：核心公共层（平台无关/跨平台适配）
│   ├── platform/
│   │   ├── system.py            #   OS 探测（IS_WINDOWS/IS_LINUX/IS_UBUNTU、后缀、pathsep）
│   │   ├── paths.py             #   项目路径统一（logs/output/drivers/bin/testcase…）
│   │   ├── executables.py       #   外部程序探测（ffmpeg / Office / 编辑器 / 终端）
│   │   └── fonts.py             #   界面字体回退链 + PIL 中文字体文件探测
│   ├── can/
│   │   └── backend.py           #   CAN 驱动库探测与加载（Windows DLL / Linux .so）
│   └── ui/
│       ├── theme.py             #   配色与控件样式（字体走跨平台回退链）
│       └── text_redirector.py   #   print→Tk Text 线程安全重定向（tkinter 软依赖）
├── drivers/
│   ├── windows/                 #   zlgcan.dll（原位置：项目根；新位置：这里）
│   └── linux/                   #   libzlgcan.so / libusbcanfd.so（ZLG Linux 驱动）
├── bin/
│   ├── windows/                 #   ffmpeg.exe 等（按平台存放）
│   └── linux/                   #   ffmpeg 等
├── tools/
│   ├── check_env.py             #   环境自检（依赖/字体/驱动/外部程序 → 修复命令）
│   └── selftest.py              #   hudcore 回归自测（跨平台可跑）
├── run.sh / run.bat             #   平台启动脚本（含前置检查）
├── requirements.txt             #   跨平台基线依赖（原 UTF-16 已转 UTF-8）
├── requirements-windows.txt     #   Windows 增量（CUDA torch 源说明）
└── requirements-linux.txt       #   Ubuntu 增量（apt 系统依赖 + torch 源）
```

---

## 3. 改造点清单

| # | 文件 | 改造前（Windows 假设） | 改造后 |
|---|------|------------------------|--------|
| 1 | `zlgcan_driver.py` | `windll.LoadLibrary("./zlgcan.dll")`；非 Windows 直接 `print("No support now!")` | `hudcore.can.load_zlg_library()`：Windows 用 `WinDLL`、Linux 用 `CDLL`；探测 `drivers/<平台>/` → 项目根 → 系统路径；支持 `HUD_ZLG_LIB` 环境变量；**hudcore 缺失时回退原行为** |
| 2 | `main.py` | 全局脚本 + 字体写死 `微软雅黑` | 重构为 `MainWindow` 类（UI 分块方法）；字体走 `Theme`；启动打印平台自检；`TextRedirector` 复用 `hudcore.ui` |
| 3 | `gui_handlers/video_extract_ffmpeg.py` | 默认路径 `ffmpeg/bin/ffmpeg.exe`，手选过滤 `.exe` | `_resolve_ffmpeg()`：hudcore 探测（`bin/<平台>` → PATH → 常见路径）→ 手选（按平台后缀）→ 回退系统 PATH |
| 4 | `gui_handlers/testcase_open_table.py` | 硬编码 `C:\Program Files (x86)\Kingsoft\WPS Office` + `shutil.which('excel')` | `hudcore.platform.executables.open_in_office_app()`：Windows WPS/Excel、Ubuntu LibreOffice、macOS `open`；失败给出安装命令 |
| 5 | `gui_handlers/testcase_view_log.py` | 三平台分支（notepad / xdg-open / open）散落 | `open_in_text_editor()` 统一探测（notepad++/gedit/kate/xdg-open） |
| 6 | `auto_labeling/draw_boxes_v2.py` | 硬编码 `C:\Windows\Fonts\msyh.ttc` | `hudcore.platform.fonts.load_pil_font()`（Windows 雅黑 / Ubuntu Noto CJK / macOS PingFang） |
| 7 | `can_gui/can_send_receive_gui.py` | `ImageFont.truetype("arial.ttf", 32)` | `load_pil_font(32)`（Linux 无 arial 时自动换字体） |
| 8 | `requirements.txt` | UTF-16 编码、含 `+cu126` 平台后缀、三个 opencv 冲突包 | 转 UTF-8；去掉平台后缀与冲突包；按平台拆分 3 个文件 |
| 9 | 目录 | `zlgcan.dll` / `ffmpeg/` 混在根目录 | 按平台归入 `drivers/<平台>/`、`bin/<平台>/`（原位置仍兼容） |

> 说明：原 `can_control.py`、`can_gui/can_send_receive_gui.py` 等业务逻辑**未改动**，
> 它们通过 `zlgcan_driver.py` 间接受益于跨平台驱动加载。

---

## 4. 使用 hudcore

### 4.1 平台判断与路径

```python
from hudcore.platform.system import IS_WINDOWS, IS_LINUX, IS_UBUNTU, exe_suffix, lib_suffix
from hudcore.platform.paths import paths

print(paths.project_root, paths.logs_dir, paths.drivers_dir, paths.bin_dir)
log_file = paths.logs_dir / "app.log"          # 不再用 "./logs/xxx"
```

### 4.2 外部程序与打开文件

```python
from hudcore.platform.executables import (
    get_ffmpeg, get_office_app, open_with_default_app, open_in_text_editor, open_in_office_app)

ff = get_ffmpeg()                 # Path | None（可用 HUD_FFMPEG 环境变量覆盖）
open_in_office_app("001.xlsx")    # Windows→WPS/Excel，Ubuntu→libreoffice
open_in_text_editor("001_data.log")
```

### 4.3 字体

```python
from hudcore.ui.theme import Theme
from hudcore.platform.fonts import get_ui_font_name, load_pil_font

Theme.font_name()                    # "微软雅黑" / "Noto Sans CJK SC" / "PingFang SC"
tk.Button(root, **Theme.primary_button())     # 一套样式跨平台
draw.text((0, 0), "中文", font=load_pil_font(32))   # PIL/OpenCV 绘制中文
```

### 4.4 CAN 驱动

```python
from hudcore.can import load_zlg_library, describe_library_status, is_library_available

if not is_library_available():
    print(describe_library_status())          # 打印探测过程与安装指引
dll = load_zlg_library()                       # 或 load_zlg_library("/path/libzlgcan.so")
```

---

## 5. 扩展指南

### 5.1 新增一类外部工具

在 `hudcore/platform/executables.py` 加一个 `get_xxx()`，复用 `find_executable(names, extra_dirs, env_var)`：

```python
def get_my_tool():
    return find_executable(["mytool", "my-tool"], env_var="HUD_MY_TOOL")
```

### 5.2 接入第二种 CAN 设备（如 PEAK / Kvaser）

在 `hudcore/can/` 增加 `peak_backend.py`，实现与 `backend.py` 相同的两个函数
（`find_library()` / `load_library()`），再在 `hudcore/can/__init__.py` 做选择：

```python
DEVICE = os.environ.get("HUD_CAN_BACKEND", "zlg")     # zlg | peak
```

### 5.3 新增平台（例如 ARM Linux 板）

只需扩充 `hudcore/platform/system.py` 的探测与 `backend.py` 的候选库名，
业务代码无需改动。

---

## 6. 验证

```bash
# 环境自检（依赖/字体/驱动/外部程序，输出问题+修复命令）
python tools/check_env.py
./run.sh --check          # Linux

# 平台层回归自测（跨平台，无硬件也能跑）
python tools/selftest.py
```

**当前实测结果**

| 平台 | selftest 结果 | 说明 |
|------|---------------|------|
| Ubuntu 22.04 (Python 3.10) | **9 通过 / 0 失败 / 2 跳过** | 跳过项为 tkinter 未安装（容器内无 GUI 包） |
| macOS (Python 3.9, 有 tkinter) | **10 通过 / 0 失败 / 1 跳过** | 跳过项为非 Linux 的伪造驱动库测试 |
| Windows | 逻辑一致（`WinDLL` 分支） | 需在有 ZLG 设备的环境复测 |

---

## 7. 后续可选优化（未在本次改动）

1. `can_control.py`（1148 行过程式）可封装为 `CanController` 类，消除全局 `received_messages`；
2. `can_gui/can_send_receive_gui.py`（1638 行）可拆分 UI/业务/数据三层；
3. `image_testing/`、`camera_tools/` 内部路径与配置可统一接入 `hudcore.platform.paths`；
4. 抽出统一配置中心（`hudcore/config.py`）替代散落的常量。
