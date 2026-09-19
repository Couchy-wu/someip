# Ubuntu 22.04 部署指南（UBUNTU_SETUP）

> 目标：在 **Ubuntu 22.04 LTS**（x86_64 或 aarch64）上运行 HudAutoTest，
> 包含 GUI、CAN 通信、图像/OCR 功能。Windows 侧使用方式不变。

---

## 1. 系统要求

| 项 | 要求 |
|----|------|
| 系统 | Ubuntu 22.04 LTS（20.04/24.04 亦可，命令基本一致） |
| Python | 3.10（系统自带）；**必须安装 tkinter** |
| 显示 | 桌面环境（GUI 必需）；远程用 X11 转发或 VNC |
| CAN 设备 | ZLG USBCANFD 系列（需 ZLG Linux 驱动） |
| GPU（可选） | NVIDIA + CUDA 12.x（YOLO/OCR 加速；无 GPU 用 CPU 版 torch） |

---

## 2. 系统依赖（apt）

```bash
sudo apt update
sudo apt install -y \
    python3 python3-pip python3-tk python3-dev python3-venv \
    build-essential cmake \
    libgl1 libglib2.0-0 \
    ffmpeg \
    fonts-noto-cjk \
    libreoffice-calc \
    libusb-1.0-0 libusb-1.0-0-dev
```

| 包 | 用途 |
|----|------|
| `python3-tk` | **GUI 必需**（tkinter） |
| `libgl1` / `libglib2.0-0` | OpenCV 运行时依赖（否则 `import cv2` 报错） |
| `ffmpeg` | 视频抽帧（Windows 用 `bin/windows/ffmpeg.exe`） |
| `fonts-noto-cjk` | 中文字体（否则界面/绘制中文显示方块） |
| `libreoffice-calc` | 查看测试用例 xlsx（替代 Windows 的 WPS/Excel） |
| `libusb-1.0-0-dev` | ZLG CAN Linux 驱动依赖 |

---

## 3. Python 依赖

```bash
cd <项目根>
python3 -m venv .venv
source .venv/bin/activate

# 基础依赖
pip install -U pip
pip install -r requirements-linux.txt

# PyTorch（按硬件二选一）
# GPU（CUDA 12.6）：
pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0 \
    --index-url https://download.pytorch.org/whl/cu126
# CPU（无独显 / 仅功能验证）：
pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0 \
    --index-url https://download.pytorch.org/whl/cpu
```

> 说明：原 `requirements.txt` 为 Windows `pip freeze` 产物（UTF-16、含 `+cu126` 后缀），
> 已转为 UTF-8 并拆分平台文件；**torch 必须按平台从官方源安装**。

---

## 4. ZLG CAN 驱动（Linux）

Windows 用 `zlgcan.dll`；Linux 需要 ZLG 官方的 **Linux 驱动/SDK**。

```bash
# 1) 从 ZLG 官网下载「USBCANFD 系列 Linux 驱动」，解压后通常包含：
#    libzlgcan.so（新版统一库）或 libusbcanfd.so（旧版）+ udev 规则

# 2) 放置驱动库（二选一）
mkdir -p <项目根>/drivers/linux
cp libzlgcan.so <项目根>/drivers/linux/          # 方式 A：项目内（推荐）
sudo cp libzlgcan.so /usr/local/lib/ && sudo ldconfig   # 方式 B：系统路径

# 或者用环境变量指定完整路径
export HUD_ZLG_LIB=/path/to/libzlgcan.so

# 3) 设备权限（避免必须 root）
sudo cp <SDK>/99-*.rules /etc/udev/rules.d/      # 若 SDK 提供 udev 规则
sudo udevadm control --reload && sudo udevadm trigger

# 4) 验证
python3 tools/check_env.py        # 查看「CAN 驱动库」段落
ldd <项目根>/drivers/linux/libzlgcan.so | grep "not found"   # 依赖是否齐全
```

**探测顺序**（`hudcore.can`，无需改代码）：
`HUD_ZLG_LIB` 环境变量 → `drivers/linux/` → `drivers/` → 项目根 → 系统库路径
（`/usr/local/lib`、`/usr/lib/x86_64-linux-gnu`、`/opt/zlgcan` 等）。

候选库名：`libzlgcan.so` → `libusbcanfd.so` → `libusbcan.so` → `libcanfd.so`。

---

## 5. 显示环境

| 场景 | 做法 |
|------|------|
| 本机桌面 | 直接运行 |
| SSH 远程 | `ssh -X user@host`（需服务端 `X11Forwarding yes`），或改用 VNC |
| 无桌面（服务器） | 装 `xvfb` 做无头测试：`xvfb-run -s "-screen 0 1920x1080x24" python main.py`（仅用于自动化，不便于人工操作） |

---

## 6. 运行

```bash
cd <项目根>
./run.sh                # 启动（含 Python/tkinter/字体前置检查）
./run.sh --check        # 仅环境自检

# 或手动
python3 tools/check_env.py     # 自检
python3 main.py                # 启动
```

启动后主界面日志区会打印平台信息（字体、外部程序、CAN 驱动探测结果），便于现场确认。

---

## 7. 目录约定（平台化后）

```
<项目根>/
├── drivers/linux/       # libzlgcan.so 等（Windows 对应 drivers/windows/zlgcan.dll）
├── bin/linux/           # ffmpeg 等（Windows 对应 bin/windows/ffmpeg.exe）
├── logs/                # 运行日志
├── output/ output_ocr/  # 处理产物
└── TestcaseCollection/  # 测试用例（xlsx + 解析日志）
```

> 兼容性：原放在项目根的 `zlgcan.dll`、`ffmpeg/` 目录**仍然可用**（探测链包含项目根）。

---

## 8. 功能差异对照（Windows → Ubuntu）

| 功能 | Windows | Ubuntu 22.04 | 备注 |
|------|---------|--------------|------|
| GUI（tkinter） | ✅ | ✅ 需 `python3-tk` | 字体自动切换（雅黑 → Noto Sans CJK） |
| CAN 收发 | `zlgcan.dll` | `libzlgcan.so` | 需 ZLG Linux 驱动 + udev 权限 |
| 打开 xlsx | WPS / Excel | LibreOffice Calc | 自动探测 |
| 查看日志 | notepad++/notepad | gedit/kate/xdg-open | 自动探测 |
| 视频抽帧 | `ffmpeg.exe` | `ffmpeg`（apt） | 自动探测 |
| 图像标注中文字体 | `C:\Windows\Fonts\msyh.ttc` | Noto Sans CJK | 自动探测字体文件 |
| YOLO / OCR | CUDA | CUDA 或 CPU | torch 需按平台安装 |

---

## 9. 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| `ModuleNotFoundError: tkinter` | 未装 GUI 包 | `sudo apt install -y python3-tk` |
| 界面中文显示方块 | 缺中文字体 | `sudo apt install -y fonts-noto-cjk` |
| `import cv2` 报 `libGL.so.1` | 缺 OpenCV 运行时依赖 | `sudo apt install -y libgl1 libglib2.0-0` |
| CAN 功能报"未找到驱动库" | 未放置 Linux 驱动 | 见第 4 节；或设 `HUD_ZLG_LIB` |
| 驱动库加载失败（`OSError`） | .so 依赖缺失 | `ldd libzlgcan.so` 查看缺什么；`sudo apt install -y libusb-1.0-0` |
| 打开设备失败（权限） | udev 规则未装 | 配置 SDK 提供的 udev 规则，或临时 `sudo` |
| 找不到 ffmpeg | 未安装 | `sudo apt install -y ffmpeg` |
| torch 安装报版本不存在 | 用了 Windows 的 `+cu126` 写法 | 按第 3 节用 `--index-url` 安装 |
| 远程无界面 | 无 X11 显示 | 用 `ssh -X` 或 VNC；服务器场景用 `xvfb-run` |

---

## 10. 交付前检查清单

```bash
python3 tools/check_env.py      # 应无"影响核心功能"的报错
python3 tools/selftest.py       # 平台层自测应全部通过（跳过项为环境缺失）
./run.sh                        # GUI 正常打开，日志区显示平台信息与驱动探测结果
```

- [ ] `tkinter` 可用、中文字体正常显示
- [ ] `drivers/linux/` 下有驱动库，`check_env` 显示"驱动库就绪"
- [ ] ffmpeg / LibreOffice / 文本编辑器探测命中（或接受回退）
- [ ] CAN 设备插上后能在「can测试」窗口正常收发

---

## 附：ZLG Linux 驱动库的获取（thirdparty/zlg_can）

ZLG 官方没有公开的 Linux 驱动直链，本项目用脚本从公开镜像获取（含头文件）：

```bash
python tools/fetch_thirdparty_libs.py zlg            # 默认本机架构
python tools/fetch_thirdparty_libs.py zlg --arch x86_64
```

库会被放到 `thirdparty/zlg_can/<平台>-<架构>/`（如 `linux-x86_64/`）。安装运行期依赖即可，
**不需要**设置 `LD_LIBRARY_PATH`（同目录依赖会被自动预加载，见下）：

```bash
sudo apt install -y libusb-1.0-0 libusb-1.0-0-dev
```

自检（显示命中库、**接口形态**与所用后端）：

```bash
python -c "from can_core import describe_driver_status as d; print(d())"
# 例：CAN 驱动：.../thirdparty/zlg_can/linux-x86_64/libusbcanfd.so
#       接口形态：vci
#       后端：VCI 适配层（业务代码无需改动；波特率由适配层换算成 ZCAN_INIT 时序）
```

> ✅ **接口差异已内置适配**：公开可下载的 Linux 库是 **VCI 接口**（`VCI_OpenDevice` 等，
> 没有句柄、用"设备类型/序号/通道号"三元组定位），而业务层按 Windows 版 `zlgcan.dll` 的
> **ZCAN 接口**编写。`can_core/driver_factory.py` 会按库实际导出的符号选择后端：
> ZCAN 直连（Windows / ZCAN 版 Linux 库）或 **VCI 适配层**
> （`can_core/vci_adapter.py`，波特率 → `ZCAN_INIT` 时序、句柄 → 三元组、属性键 → `VCI_SetReference`）。
> 业务代码、界面与用例执行器**无需区分平台**。
>
> 两个可能需要现场微调的量（见 [`../thirdparty/zlg_can/README.md`](../thirdparty/zlg_can/README.md) §3.2）：
> `HUD_VCI_CLK`（控制器时钟，默认 40 MHz）、`HUD_VCI_SAMPLE_POINT` /
> `HUD_VCI_SAMPLE_POINT_DATA`（采样点，默认 80% / 75%）。
>
> 无硬件时先自测：`./docker/can-sim/run_check.sh`（VCI 桩库 + 业务层收发回环）。
