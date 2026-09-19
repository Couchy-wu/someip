# Windows 环境验证容器（docker/windows-sim）

在 **Linux 容器里构造一个真实的 Windows 运行时**，用于验证 HudAutoTest 在 Windows
（Python 3.13）下的各项功能是否正常 —— 不需要 Windows 机器、不需要 HUD/CAN 硬件、
不需要显示器。

**实测结果：17 项验证全部通过**（详见 [`../../docs/WINDOWS_VERIFICATION.md`](../../docs/WINDOWS_VERIFICATION.md)）。

---

## 1. 快速开始

```bash
cd docker/windows-sim

./build.sh          # 构建镜像（首次约 10~20 分钟）
./run_verify.sh     # 运行 17 项功能验证，产出 verify_report.md / .json
```

其他用法：

```bash
./run_verify.sh check                 # 项目环境自检（Windows 语义）
./run_verify.sh selftest              # hudcore 回归自测
./run_verify.sh gui                   # 启动 main.py，验证窗口能否创建
./run_verify.sh py -m pip list        # 用 Windows Python 执行任意命令
./run_verify.sh script tools/check_imports.py
./run_verify.sh shell                 # 进入容器交互排查
```

网络受限时用国内源构建：

```bash
PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/ \
APT_MIRROR=http://mirrors.aliyun.com/ubuntu ./build.sh
```

---

## 2. 实现原理

Docker 不能运行 Windows 内核，因此用下列组件拼出一个 Windows 运行时：

| 组件 | 作用 | 提供的 Windows 语义 |
|------|------|--------------------|
| **Wine 6.0.3**（Ubuntu jammy `wine64`） | Windows API 兼容层 | PE 加载器、`LoadLibrary`/`WinDLL`、注册表、盘符路径、`;` 分隔 PATH |
| **Windows CPython 3.13.15**（python-build-standalone 官方 Windows x86_64 构建） | 真正的 Windows 解释器 | `sys.platform == "win32"`、`platform.system() == "Windows"`、`ctypes.WinDLL`、`.exe` 后缀 |
| **win_amd64 wheel**（numpy/pandas/opencv/pillow…） | Windows 二进制依赖 | 与现场 Windows 机器相同的扩展 ABI |
| **原生 UCRT**（conda-forge `ucrt`） | 微软 UCRT + `api-ms-win-crt-*` 转发器 | 让 MSVC 构建的扩展（numpy 等）可运行 |
| **Xvfb** | 虚拟 X 显示 | Tk 窗口可创建、布局、渲染 |
| **CAN 驱动桩库** | MinGW 编译的 `zlgcan.dll`，或回退用 `python313.dll` | 验证「探测 → `WinDLL` 加载 → 调用导出」链路 |

> 一句话：**解释器、依赖 wheel、路径与 API 语义都是 Windows 的**，只是内核是 Linux。
> 这足以覆盖"代码在 Windows 上能否真正跑起来"这一层问题；硬件与真机特有行为见 §6。

---

## 3. 目录结构

```
docker/windows-sim/
├── Dockerfile           # 镜像定义（多阶段：base → winebase → winepy → pysim）
├── install_python.sh    # 在 Wine 中准备 Windows CPython（默认免安装器方案 + 安装器回退）
├── entrypoint.sh        # 容器入口：verify / check / selftest / gui / py / script / shell
├── verify_windows.py    # 17 项功能验证套件（输出 md + json）
├── check_deps.py        # 构建期依赖自检（在 Windows Python 中真实导入）
├── stub_zlgcan.c        # CAN 驱动桩库源码（WITH_MINGW=1 时交叉编译）
├── build.sh             # 构建镜像
├── run_verify.sh        # 挂载项目并运行容器
├── verify_report.md/json# 最近一次验证的结果（随仓库提交，作为证据）
└── README.md            # 本文档
```

---

## 4. 关键实现决策（为什么这么做）

| 决策 | 原因 |
|------|------|
| 用 **python-build-standalone** 而不是 python.org 安装器 | 官方 `.exe` 是 WiX Burn 引导包，在 Wine 下静默安装失败且 `/layout` 不产 MSI（补 `vcrun2022` 亦无效）；独立构建解压即用、自带 tkinter 与 pip |
| **不在 Wine 里跑 pip**，改用容器内 Linux pip 交叉安装 | Wine 6 下 OpenSSL 无法创建 SSL 上下文（`[SSL] unknown error (_ssl.c:3138)`），pip 任何网络操作都失败；Linux pip 用 `--platform win_amd64` 直接解包 Windows wheel，效果等价 |
| 装入**原生 UCRT** | Wine 6 内置 UCRT 缺 `fetestexcept`，导入 numpy 会直接崩溃 |
| **自起 Xvfb**，不用 `xvfb-run -a` | 实测该环境下 `xvfb-run -a` 会挂起（自动选号 + 残留锁） |
| 所有 wine 调用带 `timeout`，代码一律**写成 .py 文件**执行 | `wine python.exe -c "..."` 在该环境会挂起 |
| 强制 `--platform linux/amd64` | 宿主为 Apple Silicon 时，本地 `ubuntu:22.04` 标签可能是 arm64；Wine 需要 amd64 容器 |

---

## 5. 验证项清单（17 项）

| # | 验证项 | # | 验证项 |
|---|--------|---|--------|
| 1 | Windows 运行时环境 | 10 | 驱动缺失时的报错友好性 |
| 2 | hudcore 平台探测 | 11 | 外部程序探测 |
| 3 | 路径层 + 中文路径读写 | 12 | 图标相似度（dHash） |
| 4 | 界面字体与中文渲染字体 | 13 | GIF 合成（含中文路径） |
| 5 | Tk 窗口创建 | 14 | OpenCV 链路 |
| 6 | Theme + TextRedirector | 15 | CAN 信号 → 数据字节 |
| 7 | `main.py` 导入链 | 16 | 信号矩阵 XLSX → CSV |
| 8 | 全部界面/工具模块导入（37 个） | 17 | 项目自检脚本（check_imports / selftest） |
| 9 | CAN 驱动探测与加载 | | |

每项都有**独立线程 + 超时保护**：单项卡死只判该项失败并继续，不会拖死整套测试。

---

## 6. 能力边界

**可以验证**：代码在 Windows 解释器 + Windows wheel 下的导入与运行、平台分支正确性、
中文路径与字体、Tk 界面创建与样式、CAN 驱动加载链路（桩库）、无硬件依赖的业务功能。

**不能验证（需真实 Windows 机器 + 硬件）**：ZLG 驱动内核态行为与真实 CAN 收发、
`os.startfile` 拉起外部程序的界面行为、高 DPI/多显示器渲染、GPU 推理路径、
打包产物在干净机器上的落地效果。

真机复跑同一套件（脚本跨平台）：

```bat
python docker\windows-sim\verify_windows.py --expect win
```

---

## 7. 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| 构建时 `python.exe` 未生成 | Wine 下安装方式不兼容 | 默认走独立构建（免安装器）；仍失败则 `./build.sh --no-cache` 重建 |
| `import numpy` 报 `unimplemented function ... fetestexcept` | 缺原生 UCRT | 镜像已内置，确认 `/opt/ucrt_overrides.env` 存在且被 entrypoint 加载 |
| `wine: Bad EXE format` / `Exec format error` | 镜像架构不符 | 构建与运行都必须带 `--platform linux/amd64`（脚本已内置） |
| 构建卡在 apt 或 pip | 网络到 archive.ubuntu.com / PyPI 慢 | 用国内源：`APT_MIRROR=... PIP_INDEX=... ./build.sh` |
| Tk 相关项失败 | 虚拟显示未起来 | 检查 `/tmp/xvfb.log`；`DISPLAY_NUM` 冲突时换号重试 |
| 容器内 pip 安装报 SSL 错误 | Wine 下 OpenSSL 不可用 | 在构建阶段用 `--build-arg` 追加包，或用容器内 Linux pip 交叉安装 |

---

## 8. 相关文档

- [`docs/WINDOWS_VERIFICATION.md`](../../docs/WINDOWS_VERIFICATION.md) —— 完整验证报告（含发现的缺陷与修复）
- [`docs/PYTHON_COMPATIBILITY.md`](../../docs/PYTHON_COMPATIBILITY.md) —— Python 3.10~3.13 兼容性矩阵
- [`docs/PLATFORM_GUIDE.md`](../../docs/PLATFORM_GUIDE.md) —— 平台化改造说明
