# HudAutoTest

HUD（抬头显示）自动化测试上位机：**测试用例管理 · CAN 总线通信 · 图像/视频处理 · OCR 识别**。

支持 **Windows** 与 **Ubuntu 22.04 LTS**（平台化改造后，同一套代码两端运行）。

---

## 快速开始

```bash
# Ubuntu 22.04
sudo apt install -y python3-tk fonts-noto-cjk ffmpeg libreoffice-calc \
                    libgl1 libglib2.0-0 libusb-1.0-0
pip install -r requirements-linux.txt
./run.sh                 # 启动（含环境前置检查）
./run.sh --check         # 仅环境自检

# Windows
pip install -r requirements-windows.txt
run.bat                  # 或 python main.py
```

**环境自检**（推荐首次运行前执行，会输出问题与修复命令）：

```bash
python tools/check_env.py        # 依赖 / 字体 / CAN 驱动 / 外部程序
python tools/selftest.py         # 平台抽象层回归自测
```

---

## 目录结构

```
HudAutoTest/
├── main.py                  # GUI 主入口（MainWindow 类）
├── hudcore/                 # ★ 核心公共层（平台抽象/通用能力）
│   ├── platform/            #   OS 探测、路径、外部程序、字体
│   ├── can/                 #   CAN 驱动库探测与加载（DLL / .so）
│   └── ui/                  #   主题样式、stdout→Text 重定向
├── can_control.py           # ZLG CAN 通信（设备初始化/收发线程/信号解析）
├── zlgcan.py                # ZLG 驱动 Python 绑定（加载层已跨平台）
├── GuiFunction/             # 各功能 GUI 处理器（用例管理/图像/视频/矩阵转换…）
├── OtherGui/                # CAN 信号自动收发 GUI
├── CanDataProcessing/       # CAN 数据与用例解析
├── ImageTest/ CameraUtils/  # 图像测试与相机工具
├── Simple_Tools/            # 小工具（GIF/改名/图片转视频/ROI）
├── Auto label/              # 标注辅助
├── drivers/{windows,linux}/ # CAN 驱动库（按平台）
├── bin/{windows,linux}/     # 外部可执行（ffmpeg 等，按平台）
├── tools/                   # check_env.py / selftest.py
├── docs/                    # 平台化与部署文档
├── requirements*.txt        # 跨平台基线 + 平台增量依赖
└── run.sh / run.bat         # 平台启动脚本
```

---

## 文档

| 文档 | 内容 |
|------|------|
| [`docs/PLATFORM_GUIDE.md`](docs/PLATFORM_GUIDE.md) | **平台化改造说明**：新增 hudcore 层、改造点清单、扩展指南、验证方式 |
| [`docs/UBUNTU_SETUP.md`](docs/UBUNTU_SETUP.md) | **Ubuntu 22.04 部署**：系统依赖、ZLG Linux 驱动、字体、常见问题 |
| [`CLAUDE.md`](CLAUDE.md) | 项目架构与开发约定（供 AI/新成员快速上手） |

---

## 主要功能

| 模块 | 说明 |
|------|------|
| 测试用例管理 | 上传/删除/查看用例，解析日志查看（上位机主界面） |
| CAN 测试 | ZLG USBCANFD 设备收发、周期发送、信号级解析与断言（`can_control.py` + `OtherGui/test_can_gui.py`） |
| 图像/视频 | 打开图片、视频抽帧（ffmpeg）、图片序列播放、ROI 提取 |
| 图标测试 | YOLO + OCR 的图像识别与相似度校验（`ImageTest/`） |
| 工具集 | 信号矩阵转 CSV、CAN 数据生成器（binhex）、GIF/改名/转视频 |

---

## 平台兼容性

| 能力 | Windows | Ubuntu 22.04 |
|------|---------|--------------|
| GUI（tkinter） | ✅ | ✅（需 `python3-tk`） |
| 中文字体 | 微软雅黑（自动） | Noto Sans CJK（自动探测） |
| CAN 驱动 | `drivers/windows/zlgcan.dll` | `drivers/linux/libzlgcan.so`（ZLG Linux 驱动） |
| ffmpeg | `bin/windows/ffmpeg.exe` | 系统 `ffmpeg`（apt） |
| 打开 xlsx / 日志 | WPS/Excel · notepad | LibreOffice · gedit/xdg-open |
| YOLO / OCR | CUDA | CUDA 或 CPU（torch 按平台安装） |

平台差异全部由 `hudcore` 统一处理，业务代码无需区分系统。

---

## 环境变量（可选）

| 变量 | 用途 |
|------|------|
| `HUD_ZLG_LIB` | CAN 驱动库完整路径（覆盖自动探测） |
| `HUD_ZLG_LIB_DIR` | CAN 驱动库所在目录 |
| `HUD_FFMPEG` | ffmpeg 可执行文件完整路径 |
| `PYTHON_BIN` | 启动脚本使用的 Python 解释器（`run.sh`） |
