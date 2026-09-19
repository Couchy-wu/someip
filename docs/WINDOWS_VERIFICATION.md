# Windows 环境功能验证报告

> 目的：在**没有 Windows 机器**的情况下，验证 HudAutoTest 在 Windows（Python 3.13）下各项功能是否正常。
> 方法：在 Docker 容器内用 **Wine + Windows 版 CPython 3.13** 构造真实 Windows 运行时，逐项功能验证。
> 结论：**18 项验证全部通过（18 PASS / 0 FAIL / 0 SKIP）**，并在此过程中发现并修复了多类真实缺陷。

---

## 1. 验证环境

| 项目 | 值 |
|------|-----|
| 宿主 | macOS (Apple Silicon)，Docker Desktop 29.2.1 |
| 容器基础镜像 | ubuntu:22.04（`linux/amd64`，Apple Silicon 经 Rosetta 加速） |
| Windows 运行时 | **Wine 6.0.3**（Ubuntu jammy 的 wine64） |
| Windows Python | **CPython 3.13.15**（python-build-standalone 官方 Windows x86_64 构建，`MSC v.1944 64 bit (AMD64)`） |
| 依赖 | win_amd64 wheel（numpy 2.x / pandas / opencv / pillow / pandas / openpyxl 等） |
| 图形环境 | Xvfb 虚拟显示（`1280x800x24`），使 Tk 界面可真实创建 |
| 项目代码 | 通过 `-v` 挂载到容器 `/work`（Windows 侧为 `Z:\work`），**不复制、不改动** |

Windows 语义确凿性证据（验证套件第 1 项输出）：

```
platform.system()=Windows, sys.platform=win32, Python=3.13.15,
arch=AMD64, 64bit=True, exe=python.exe
platform=Windows-2008ServerR2-6.1.7601-SP1   ← Wine 报告的 Windows 版本
```

---

## 2. 验证结果（17/17 通过）

运行命令：

```bash
cd docker/windows-sim
./build.sh        # 构建镜像（首次较慢）
./run_verify.sh   # 运行验证套件，产出 verify_report.md / .json
```

| # | 验证项 | 结果 | 关键证据 |
|---|--------|------|----------|
| 1 | Windows 运行时环境 | ✅ PASS | `sys.platform=win32`、`platform.system()=Windows`、Python 3.13.15、AMD64 |
| 2 | hudcore 平台探测 | ✅ PASS | `exe_suffix='.exe'`、`lib_suffix='.dll'`、`pathsep=';'`、版本策略 `ok` |
| 3 | 路径层 + 中文路径读写 | ✅ PASS | 项目根解析为 `Z:\work`；中文文件名写入/读取成功 |
| 4 | 界面字体与中文渲染字体 | ✅ PASS | 自动选中 **微软雅黑**；PIL 中文字体可加载 |
| 5 | Tk 窗口创建 | ✅ PASS | Tk 8.6 创建/销毁成功，几何 `320x120+0+0` |
| 6 | Theme 样式 + TextRedirector | ✅ PASS | 8 个样式工厂可用；`print` 内容被重定向进 Tk Text |
| 7 | `main.py` 导入链 | ✅ PASS | `MainWindow` / `TextRedirector` 可用（未启动主循环） |
| 8 | 全部界面与工具模块导入 | ✅ PASS | **37/37 个模块全部导入成功** |
| 9 | CAN 驱动探测与加载 | ✅ PASS | 命中 `Z:\work\drivers\windows\zlgcan.dll`，经 `ctypes.WinDLL` 加载并**成功调用导出函数**（`Py_GetVersion()` 返回 3.13.15） |
| 10 | 驱动缺失时的报错友好性 | ✅ PASS | `HUD_ZLG_LIB` 指向不存在路径 → 给出中文修复提示，不崩溃 |
| 11 | 外部程序探测 | ✅ PASS | ffmpeg 命中（`vendor/ffmpeg` 探测链生效）；解释器命中；Office/编辑器缺失时返回 None 不抛异常 |
| 12 | 图标相似度（dHash） | ✅ PASS | 相同图→True、不同图→False，哈希差 32 bit |
| 13 | GIF 合成（含中文路径） | ✅ PASS | `中文输出目录/结果.gif` 生成成功，5 帧 |
| 14 | OpenCV 链路 | ✅ PASS | cv2 5.0.0 中文路径读写正常；`ImageEnhancer` 可导入 |
| 15 | CAN 信号 → 数据字节 | ✅ PASS | 59497 行信号矩阵中取值：枚举 0→`[0x00,…]`、枚举 1→`[0x01,…]`，值随枚举变化 |
| 16 | 信号矩阵 XLSX → CSV | ✅ PASS | openpyxl 读写链路正常，`XlsmToCsvConverter` 可导入 |
| 17 | 项目自带自检脚本 | ✅ PASS | `tools/check_imports.py` rc=0；`tools/check_static.py` rc=0；`tools/selftest.py` rc=0 |
| 18 | 单元测试（pytest） | ✅ PASS | `tests/` 全部用例通过（含架构规则守卫） |

产物（已随仓库提交）：

- [`docker/windows-sim/verify_report.md`](../docker/windows-sim/verify_report.md) —— 本次运行生成的表格报告
- [`docker/windows-sim/verify_report.json`](../docker/windows-sim/verify_report.json) —— 机器可读结果（含完整环境信息）

---

## 3. 验证过程中发现并修复的真实缺陷

> 这些缺陷**在 Windows 真机上同样会复现**（不是在容器里才出现的问题）。
> 它们正是"只做静态检查、不跑功能"时最容易漏掉的一类问题。

### 3.1 导入即阻塞：三个小工具模块在模块级启动 GUI

`misc_tools/gif_creator.py`、`misc_tools/images_to_video.py`、`misc_tools/image_batch_rename.py`
把 `root = tk.Tk()` 与 `root.mainloop()` 写在**模块级**：

```python
# 修复前（节选）
root = tk.Tk()
root.title("图片转GIF工具")
...
root.mainloop()          # ← import 本模块会永久阻塞在这里
```

后果：任何 `import` 这些模块的操作都会永久卡死（自动化测试、被其他模块复用、打包工具分析依赖时都会中招）。

修复：GUI 构造移入 `main()`，并用 `if __name__ == "__main__": main()` 守卫。
证据：修复后 `import misc_tools.gif_creator` 由 **TIMEOUT(>20s)** 变为 **0s 成功**。

### 3.2 导入即退出进程：三个标注工具的 `parse_args()` 在模块级执行

`auto_labeling/draw_boxes.py`、`draw_boxes_v2.py`、`draw_labels.py` 在模块级调用
`args = parser.parse_args()`：

```
$ python -c "import auto_labeling.draw_labels"        # 修复前，带任意外部参数时
prog: error: unrecognized arguments: --expect linux   ← SystemExit(2)，进程直接退出
```

后果：这些模块无法作为库被导入（主程序/测试框架一旦带自己的命令行参数就会崩），
且因为 `SystemExit` 不是 `Exception`，异常还会被静默吞掉。

修复：参数解析改为惰性 —— 模块级只保留与 argparse `default` 一致的默认值，
新增 `configure(argv=None)`，由 `__main__` 守卫调用；导入无副作用。
证据：三个模块均可带外部参数导入成功；`configure(["--data_root","/tmp/xyz","--subset","train"])` 正常生效。

### 3.3 同级模块"扁平导入"导致部分模块不可用

`image_testing/icon_manager.py`、`image_testing/verify_icons.py`、`auto_labeling/draw_boxes*.py`
使用 `from image_similarity import ...` 这类**同目录绝对导入**，只有在"该目录被加入
`sys.path`"时才成立（项目里另一些文件用 `sys.path.append(current_dir)` 兜着，这两个没有）：

```
ModuleNotFoundError: No module named 'image_similarity'
```

修复：改为"包内导入优先 + 脚本模式回退"：

```python
try:                       # 作为包导入
    from .image_similarity import get_image_hash
except ImportError:        # 直接运行本文件（脚本模式）
    from image_similarity import get_image_hash
```

### 3.4 导入期弹窗：`find_sub_id.py` 在导入失败时直接弹 messagebox

```python
# 修复前
except ImportError as e:
    messagebox.showerror("导入错误", ...)   # ← 无人值守环境直接卡在模态对话框
    raise e
```

修复：导入失败只记录状态并打印警告，真正调用功能时再明确报错。

### 3.5 依赖清单缺失（干净环境无法启动 / 功能静默不可用）

审计"代码里 import 了、清单里没有"的第三方包，发现并补齐：

| 包 | 影响 | 处理 |
|----|------|------|
| `pyperclip` | `gui_handlers.can_data_generator` 模块级导入 → **主界面导入失败** | 加入 `requirements.txt`，并做可选降级（缺库时点"复制"给提示而非崩溃） |
| `watchdog` | `camera_tools.perspective_calibration` 模块级导入 → 导入失败 | 加入清单 + 可选降级（无 watchdog 时监视功能禁用） |
| `ffmpeg-python` | `gui_handlers.video_extract_ffmpeg` 模块级导入 → 导入失败 | 加入清单 + 可选降级（缺库时给出 `pip install ffmpeg-python` 提示） |
| `tqdm` | `auto_labeling.draw_*` 需要 | 已在清单，容器验证时确认 |
| `natsort` | `misc_tools.images_to_video` 需要 | 加入 `requirements.txt` |

另外修复了一个**隐蔽的包名遮蔽**：项目根的 `ffmpeg/` 目录（vendored ffmpeg 构建）
会被 Python 当作命名空间包，遮蔽 PyPI 的 `ffmpeg-python`（`import ffmpeg` 拿到的是目录，
`ffmpeg.input()` 必然 AttributeError）。已迁移到 `vendor/ffmpeg/` 并纳入外部程序探测路径。

### 3.6 顺带修复的测试稳健性问题

- `tools/selftest.py` 的 TextRedirector 用例：`TextRedirector` 通过 `root.after()` 轮询写入，
  单次 `root.update()` 不一定覆盖一个轮询周期，在负载较高时会偶发失败 → 改为循环驱动事件循环直到内容出现。
- 验证套件 `verify_windows.py`：为**每一项**验证加了独立线程 + 超时（默认 120s，容器内 180s），
  单项卡死只会判该项 FAIL 并继续，避免整套测试被一个 GUI 调用拖死；
  同时捕获 `BaseException`，避免 `SystemExit` 让用例"无返回值"。
- 新增 `tools/check_imports.py`：项目内部导入静态校验（支持命名空间包），
  重构/改名后兜底；当前 **59 个文件全部可解析**。

---

## 4. 容器方案的实现要点（踩坑记录）

这一节对后续维护容器的人最有价值 —— 每一坑都是实测踩出来的。

| 现象 | 根因 | 解法 |
|------|------|------|
| `ubuntu:22.04` 拉到的其实是 arm64，apt 走 `ports.ubuntu.com` 且 i386 索引 404 | Docker 本地已存在 arm64 同名标签 | 显式 `docker pull --platform linux/amd64 ubuntu:22.04`，构建/运行都带 `--platform linux/amd64` |
| Wine 11（WineHQ）下 `wineboot` 直接 abort：`anon_mmap_fixed: Assertion ... failed` | 该断言在 Apple Silicon + Rosetta 的 16K 页环境下必现 | 改用 Ubuntu jammy 的 **Wine 6.0.3**（内存布局兼容） |
| `wine python.exe -c "..."` 挂起 | 该环境下的控制台/标准输出处理问题 | 一律**写成 .py 文件再执行**，并全部加 `timeout` |
| `xvfb-run -a` 挂起 | 自动选号 + 残留锁 | **自起 Xvfb** 并固定 `DISPLAY=:99`（`ensure_display()`） |
| python.org 安装器（`python-3.13.x-amd64.exe`）静默安装失败、`/layout` 不产 MSI | WiX Burn 引导包依赖 Wine 未完整实现的 UCRT/COM 细节（补 `vcrun2022` 亦无效） | 改用 **python-build-standalone** 的 Windows 构建（解压即用，自带 tkinter/pip） |
| Wine 内 pip 全部失败：`ssl.SSLError: [SSL] unknown error (_ssl.c:3138)` | Wine 6 下 OpenSSL 无法创建 SSL 上下文；pip 26 还会先建 truststore 上下文 | **不在 Wine 里跑 pip**：用容器自带 Linux pip 以 `--platform win_amd64 --only-binary=:all: --target <Wine site-packages>` 交叉安装 Windows wheel |
| `import numpy` 崩溃：`unimplemented function api-ms-win-crt-runtime-l1-1-0.dll.fetestexcept` | Wine 6 内置 UCRT 缺函数 | 装入**原生 UCRT**（conda-forge `ucrt` 包：`ucrtbase.dll` + 全套 `api-ms-win-crt-*.dll`）+ `WINEDLLOVERRIDES` 优先原生 |
| Dockerfile 里 heredoc 报 `unknown instruction` | 传统 builder 不支持 RUN 内 heredoc | 自检脚本独立成 `check_deps.py` 用 `COPY` 引入 |
| `PIP_INDEX: parameter not set` | 多阶段构建 ARG 不跨 stage 继承 | 每个 stage 重新声明 ARG |

---

## 5. 能力边界：容器验证能覆盖什么，不能覆盖什么

**已验证（本报告结论的有效范围）**

- 代码在 **Windows 解释器 + Windows wheel** 下能否正常导入与运行（37/37 模块）；
- 平台分支正确性：`platform.system()`、`ctypes.WinDLL`、盘符路径、`.`/`;` 分隔符、`.exe` 后缀；
- 中文路径、中文文件名、字体回退（微软雅黑）在 Windows 语义下的行为；
- Tk 界面创建、主题样式、日志重定向链路；
- CAN 驱动「探测 → `WinDLL` 加载 → 调用导出」整条链路（用桩库替代真实驱动）；
- 无硬件依赖的业务功能：图像相似度、GIF、CV 链路、CAN 信号编解码、XLSX 转换。

**未覆盖（需真实 Windows 机器 + 硬件）**

- ZLG 驱动的内核态行为与真实 CAN 收发（需真设备）；
- `os.startfile` 真正拉起 WPS/Excel 等外部程序的界面行为；
- 高 DPI 缩放、多显示器、真实字体的像素级渲染差异；
- GPU（CUDA）推理路径与 torch/paddle 的 GPU 性能；
- PyInstaller 等打包产物在干净机器上的落地效果；
- Wine 报告的 Windows 版本为 `2008ServerR2`（不代表真机版本），仅影响版本判断类分支。

> 需要在真机覆盖上述内容时，可直接复用同一套件（脚本本身跨平台）：
> ```bat
> python docker\windows-sim\verify_windows.py --expect win
> ```

---

## 6. 复现步骤

```bash
# 1) 构建镜像（首次约 10~20 分钟，取决于网络；可指定国内镜像源）
cd docker/windows-sim
PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/ ./build.sh

# 2) 运行验证（挂载项目目录，产出报告）
./run_verify.sh                 # 17 项功能验证
./run_verify.sh check           # 项目环境自检（Windows 语义）
./run_verify.sh selftest        # hudcore 回归自测
./run_verify.sh gui             # 启动 main.py 验证窗口能否创建
./run_verify.sh py -m pip list  # 用 Windows Python 执行任意命令
```

Linux/Python 3.13 下的同一套件（用于横向对比）：

```bash
docker run --rm -v "$PWD:/work" -w /work python:3.13-slim bash -lc '
  apt-get update -qq && apt-get install -y -qq xvfb tk8.6 libgl1 libglib2.0-0 fonts-wqy-microhei
  pip install -q numpy pandas openpyxl pillow opencv-python-headless pyyaml requests psutil \
        pyperclip watchdog ffmpeg-python tqdm natsort
  xvfb-run -a python docker/windows-sim/verify_windows.py --expect linux'
# 实测结果：16 通过 / 0 失败 / 1 跳过（跳过项为"Linux 下无 CAN 驱动桩库"，属预期）
```

---

## 7. 相关文档

- [`docker/windows-sim/README.md`](../docker/windows-sim/README.md) —— 容器构建与使用说明
- [`docs/PYTHON_COMPATIBILITY.md`](PYTHON_COMPATIBILITY.md) —— Python 3.10~3.13 依赖矩阵
- [`docs/PLATFORM_GUIDE.md`](PLATFORM_GUIDE.md) —— 平台化改造与扩展指南
- [`docs/UBUNTU_SETUP.md`](UBUNTU_SETUP.md) —— Ubuntu 22.04 部署
