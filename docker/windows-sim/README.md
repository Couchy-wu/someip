# Windows 环境验证容器（docker/windows-sim）

在 **Linux 容器里构造一个真实的 Windows 运行时**，用于验证 HudAutoTest 在 Windows
下的各项功能是否正常 —— 不依赖真实 Windows 机器、不依赖 HUD/CAN 硬件、不需要显示器。

---

## 1. 为什么可以"在 Docker 里验证 Windows"

Docker 不能运行 Windows 内核，所以本方案用两个组件拼出一个 Windows 运行时：

| 组件 | 作用 | 提供的 Windows 语义 |
|------|------|--------------------|
| **Wine**（WineHQ stable） | Windows API 兼容层（PE 加载器 + Win32 API 实现） | `LoadLibrary`、`WinDLL`、注册表、盘符路径、`;` 分隔的 PATH |
| **Windows 版 CPython 3.13**（python.org 官方 win_amd64 构建） | 真正的 Windows 解释器 | `sys.platform == "win32"`、`platform.system() == "Windows"`、`os.startfile`、`ctypes.WinDLL` |
| **Xvfb** | 虚拟 X 显示 | Tk 窗口可以创建、布局、渲染（无物理显示器） |
| **MinGW-w64 交叉编译的 `zlgcan.dll`** | CAN 驱动桩库 | 验证「驱动探测 → `WinDLL` 加载 → 按约定调用」整条链路 |
| **Windows wheel**（pip 安装） | numpy / pandas / opencv / pillow … | 与现场 Windows 机器相同的二进制依赖 |

> 一句话：**解释器、依赖 wheel、路径与 API 语义都是 Windows 的**，只是内核是 Linux。
> 这足以覆盖「代码是否真的能在 Windows 上跑起来」这一层问题；
> 无法覆盖的是依赖真实硬件/驱动内核态行为的场景（见 §6 能力边界）。

---

## 2. 快速开始

```bash
cd docker/windows-sim

./build.sh              # 构建镜像（首次约 10~20 分钟，视网络而定）
./run_verify.sh         # 运行完整功能验证套件（17 项）
```

其他用法：

```bash
./run_verify.sh check                 # 项目环境自检（tools/check_env.py，Windows 语义下）
./run_verify.sh selftest              # hudcore 回归自测
./run_verify.sh gui                   # 启动 main.py，验证 GUI 能起来
./run_verify.sh py -m pip list        # 用 Windows Python 执行任意命令
./run_verify.sh script tools/check_imports.py
./run_verify.sh shell                 # 进入容器交互排查
```

产物（写回宿主项目目录）：

- `verify_report.md` —— 人类可读的验证报告（Markdown 表格）
- `verify_report.json` —— 机器可读结果（含环境信息）

---

## 3. 验证项清单

| # | 验证项 | 说明 |
|---|--------|------|
| 1 | Windows 运行时环境 | `platform.system()`、`sys.platform`、Python 版本、64 位、解释器路径 |
| 2 | hudcore 平台探测 | `IS_WINDOWS`、`exe_suffix=".exe"`、`lib_suffix=".dll"`、`pathsep=";"`、版本策略 |
| 3 | 路径层 + 中文路径读写 | `paths.*` 全部为绝对路径；中文文件名写入/读取（Windows 默认代码页最易出问题处） |
| 4 | 字体层 | UI 字体名解析、可用字体枚举、PIL 中文字体加载 |
| 5 | Tk 窗口创建 | 真实创建 Tk 窗口 + 中文标签 + 布局刷新（Xvfb） |
| 6 | Theme + TextRedirector | 控件样式工厂可用；`print` 重定向进 Tk Text（线程安全日志链路） |
| 7 | `main.py` 导入链 | 主入口可导入、`MainWindow` 存在（不启动主循环） |
| 8 | 全部界面/工具模块导入 | 37 个模块全量导入，捕获 Windows 特有 ImportError |
| 9 | CAN 驱动探测与加载 | 找到 `drivers/windows/zlgcan.dll` → `WinDLL` 加载 → 实际调用导出函数取返回值 |
| 10 | 驱动缺失时的报错友好性 | `HUD_ZLG_LIB` 指向不存在路径：应给出修复提示而非崩溃 |
| 11 | 外部程序探测 | ffmpeg / Office / 编辑器 / 终端探测不抛异常 |
| 12 | 图标相似度（dHash） | 相同图判「一致」、不同图判「不一致」，并校验汉明距离 |
| 13 | GIF 合成 | 5 张图合成 GIF（含中文目录/文件名），校验帧数与体积 |
| 14 | OpenCV 链路 | `cv2` 中文路径读写 + `ImageEnhancer` 可用 |
| 15 | CAN 信号 → 数据字节 | 用项目自带 `can_data_tools/outputMatrix.csv`，不同枚举值生成不同数据 |
| 16 | 信号矩阵 XLSX → CSV | `openpyxl` 读写链路 |
| 17 | 项目自检脚本 | `tools/check_imports.py`、`tools/selftest.py` 在 Windows 下退出码为 0 |

---

## 4. 目录结构

```
docker/windows-sim/
├── Dockerfile           # 镜像定义（Ubuntu 22.04 amd64 + WineHQ + Windows CPython 3.13）
├── install_python.sh    # 在 Wine 中安装 Windows CPython（静默安装 + MSI 解包双路径回退）
├── entrypoint.sh        # 容器入口：verify / check / selftest / gui / py / script / shell
├── verify_windows.py    # 验证套件本体（在 Windows Python 中运行，输出 md + json）
├── stub_zlgcan.c        # CAN 驱动桩库源码（MinGW 交叉编译成 zlgcan.dll，仅用于验证）
├── build.sh             # 构建镜像
├── run_verify.sh        # 挂载项目并运行容器
└── README.md            # 本文档
```

---

## 5. 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| 构建时 `python.exe` 未生成 | Wine 下静默安装偶发失败 | `install_python.sh` 会自动走 `/layout` + `msiexec /a` 回退；仍失败则 `./build.sh --no-cache` 重建 |
| `Cannot open display` | Xvfb 未生效 | 容器内命令统一由 `xvfb-run -a` 包装（见 `entrypoint.sh`） |
| `wine: Bad EXE format` | 镜像架构不符 | 构建/运行都必须带 `--platform linux/amd64`（`build.sh`/`run_verify.sh` 已内置） |
| Tk 相关项 SKIP/FAIL | Windows Python 缺 tcl/tk | 用 `Include_tcltk=1` 重装（`install_python.sh` 已带该参数） |
| pip 安装慢/超时 | 容器直连 PyPI | 构建时用国内源：`PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple ./build.sh` |
| 第 9 项 SKIP | `drivers/windows/zlgcan.dll` 不存在 | 桩库由镜像自带，`entrypoint.sh` 会自动拷入；确认项目目录可写 |

---

## 6. 能力边界（哪些能验证、哪些不能）

**可以验证**

- 代码在 Windows 解释器 + Windows wheel 下能否正常导入与运行；
- 平台分支是否正确（`platform.system()`、`WinDLL`、盘符路径、`.`/`;` 分隔符）；
- 中文路径、中文文件名、字体回退在 Windows 语义下的行为；
- Tk 界面能否创建、样式与日志重定向链路是否正常；
- CAN 驱动「探测 → 加载 → 调用」链路（用桩库替代真实驱动）；
- 无硬件依赖的业务功能（图像相似度、GIF、CV 链路、CAN 信号编解码）。

**不能验证（需真实 Windows 机器 + 硬件）**

- ZLG 驱动的内核态/设备枚举行为与真实 CAN 收发（需要真设备）；
- `os.startfile` 真正拉起 WPS/Excel/gedit 等外部程序的界面行为；
- 高 DPI 缩放、多显示器、真实字体的像素级渲染差异；
- GPU（CUDA）推理性能与 torch/paddle 的 GPU 路径；
- Windows 安装包/打包（PyInstaller 等）在干净机器上的落地效果。

如需覆盖最后一类问题，请在真实 Windows 机器上跑同一套件：
`python docker\windows-sim\verify_windows.py --expect win`（脚本本身跨平台，可直接复用）。
