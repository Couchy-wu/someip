# HudAutoTest

HUD（抬头显示）自动化测试上位机：**测试用例管理 · CAN 总线通信 · 图像/视频处理 · OCR 识别**。

支持 **Windows 10/11** 与 **Ubuntu 22.04 LTS**，Python **3.10 ~ 3.13**（同一套代码跨平台运行）。

---

## 快速开始

```bash
# Ubuntu 22.04
sudo apt install -y python3-tk fonts-noto-cjk ffmpeg libreoffice-calc \
                    libgl1 libglib2.0-0 libusb-1.0-0
pip install -r requirements-linux.txt
./run.sh                 # 启动（含环境前置检查）
./run.sh --check         # 仅环境自检

# Windows（Python 3.13 推荐用专用清单）
pip install -r requirements-windows.txt     # 3.10 ~ 3.12
pip install -r requirements-py313.txt       # 3.13（含可用性下限）
run.bat                  # 或 python main.py
```

**环境自检**（推荐首次运行前执行，会输出问题与修复命令）：

```bash
python tools/check_env.py        # 依赖 / Python 版本 / 字体 / CAN 驱动 / 外部程序
python tools/selftest.py         # 平台抽象层回归自测
python tools/check_imports.py    # 项目内部导入静态校验（改名/重构后兜底）
python tools/check_static.py     # 静态检查（pyflakes，拦截 undefined name 等）
```

### Windows 环境免真机验证（Docker）

没有 Windows 机器时，可在容器内用 Wine + Windows 版 CPython 构造 Windows 运行时，
直接跑 17 项功能验证：

```bash
cd docker/windows-sim
./build.sh          # 构建镜像（首次较慢）
./run_verify.sh     # 运行验证，产出 verify_report.md / .json
```

详见 [`docker/windows-sim/README.md`](docker/windows-sim/README.md) 与
[`docs/WINDOWS_VERIFICATION.md`](docs/WINDOWS_VERIFICATION.md)（含实测结果与能力边界）。

---

## 目录结构

```
HudAutoTest/
├── main.py                       # GUI 主入口（MainWindow 类）
├── hudcore/                      # ★ 核心公共层（平台抽象/通用能力）
│   ├── platform/                 #   OS 探测、路径、外部程序、字体
│   ├── can/                      #   CAN 驱动库探测与加载（DLL / .so）
│   ├── logging_setup.py          #   日志初始化（原根目录 log_setup.py）
│   └── ui/                       #   主题样式、stdout→Text 重定向
├── can_core/                     # ★ CAN 设备基础设施（驱动绑定 + 设备/通道收发）
│   ├── driver.py                 #   ZLG 驱动 Python 绑定（原 zlgcan_driver.py）
│   └── device.py                 #   设备打开/关闭、周期发送、接收线程、信号级收发
├── yolo_train.py                 # YOLO 微调/验证脚本（原 train_freeze.py）
├── ocr_icon_test.py              # OCR + YOLO 图标识别测试（原 image_test.py）
├── gui_handlers/                 # 各功能 GUI 处理器（用例管理/图像/视频/矩阵转换…）
├── can_gui/                      # CAN 信号自动收发 GUI
├── can_data_tools/               # CAN 数据与用例解析（信号矩阵 CSV 等）
├── image_testing/                # 图标测试（相似度/图标管理/测试图生成）
├── camera_tools/                 # 相机工具（预览/标定/增强/稳定性）
├── misc_tools/                   # 小工具（GIF/改名/图片转视频/ROI）
├── auto_labeling/                # 标注辅助（preprocessing + template_matching/）
├── drivers/{windows,linux}/      # CAN 驱动库（按平台）
├── bin/{windows,linux}/          # 外部可执行（ffmpeg 等，按平台）
├── vendor/ffmpeg/                # 随项目分发的 ffmpeg 构建
├── tools/                        # check_env.py / selftest.py / check_imports.py / rename_modules.py
├── docker/windows-sim/           # ★ 容器内 Windows 环境验证
├── docs/                         # 平台化 / 部署 / 兼容性 / 验证文档
├── requirements*.txt             # 基线 + 平台增量 + py313 清单
└── run.sh / run.bat              # 平台启动脚本
```

> 目录/文件命名规则与改名映射表见 [`tools/rename_modules.py`](tools/rename_modules.py)：
> 模糊命名（`GuiFunction`、`OtherGui`、`test8wending`…）已改为"见名知意"的英文命名，
> 脚本保留完整映射与引用替换能力，便于追溯与再次重构。

---

## 文档

| 文档 | 内容 |
|------|------|
| [`docs/PLATFORM_GUIDE.md`](docs/PLATFORM_GUIDE.md) | **平台化改造说明**：hudcore 层、改造点清单、扩展指南、验证方式 |
| [`docs/UBUNTU_SETUP.md`](docs/UBUNTU_SETUP.md) | **Ubuntu 22.04 部署**：系统依赖、ZLG Linux 驱动、字体、常见问题 |
| [`docs/PYTHON_COMPATIBILITY.md`](docs/PYTHON_COMPATIBILITY.md) | **Python 版本兼容性**：3.10 ~ 3.13 依赖矩阵、wheel 可用性、升级步骤 |
| [`docs/WINDOWS_VERIFICATION.md`](docs/WINDOWS_VERIFICATION.md) | **Windows 环境验证报告**：容器化验证方法、17 项结果、能力边界 |
| [`docker/windows-sim/README.md`](docker/windows-sim/README.md) | Windows 验证容器的构建与使用 |
| [`CLAUDE.md`](CLAUDE.md) | 项目架构与开发约定（供 AI/新成员快速上手） |

---

## 主要功能

| 模块 | 说明 |
|------|------|
| 测试用例管理 | 上传/删除/查看用例，解析日志查看（上位机主界面） |
| CAN 测试 | ZLG USBCANFD 设备收发、周期发送、信号级解析与断言（`can_core/device.py` + `can_gui/can_send_receive_gui.py`） |
| 图像/视频 | 打开图片、视频抽帧（ffmpeg）、图片序列播放、ROI 提取 |
| 图标测试 | YOLO + OCR 的图像识别与相似度校验（`image_testing/`） |
| 工具集 | 信号矩阵转 CSV、CAN 数据生成器（binhex）、GIF/改名/转视频 |

---

## 平台兼容性

| 能力 | Windows | Ubuntu 22.04 |
|------|---------|--------------|
| GUI（tkinter） | ✅ | ✅（需 `python3-tk`） |
| 中文字体 | 微软雅黑（自动） | Noto Sans CJK（自动探测） |
| CAN 驱动 | `drivers/windows/zlgcan.dll` | `drivers/linux/libzlgcan.so`（ZLG Linux 驱动） |
| ffmpeg | `bin/windows/ffmpeg.exe` / `vendor/ffmpeg/bin` | 系统 `ffmpeg`（apt） |
| 打开 xlsx / 日志 | WPS/Excel · notepad | LibreOffice · gedit/xdg-open |
| YOLO / OCR | CUDA | CUDA 或 CPU（torch 按平台安装） |
| Python | 3.10 ~ 3.13 | 3.10（系统自带）~ 3.13 |

平台差异全部由 `hudcore` 统一处理，业务代码无需区分系统。

### Python 3.13 要点

- 全部依赖（含 `paddlepaddle>=3.2.1`、`torch>=2.6`、`numpy>=2.1`、`opencv-python>=4.10`）
  在 3.13 上均有 cp313 / abi3 wheel，**无需降级 Python**；
- 安装用 `requirements-py313.txt`（含下限约束），自检会用
  `tools/check_env.py` 的「Python 3.13 兼容性」小节核对版本；
- 项目未使用任何 3.12/3.13 已移除的模块或 API（`distutils`、`imp`、`utcnow`…）。

---

## 环境变量（可选）

| 变量 | 用途 |
|------|------|
| `HUD_ZLG_LIB` | CAN 驱动库完整路径（覆盖自动探测） |
| `HUD_ZLG_LIB_DIR` | CAN 驱动库所在目录 |
| `HUD_FFMPEG` | ffmpeg 可执行文件完整路径 |
| `PYTHON_BIN` | 启动脚本使用的 Python 解释器（`run.sh`） |
