# Python 版本兼容性说明（3.10 ~ 3.13）

本文说明 HudAutoTest 在各 Python 版本上的支持情况、依赖 wheel 可用性核查结果，
以及升级到 Python 3.13 的具体步骤与排障方法。

---

## 1. 结论速览

| 项目 | 结论 |
|------|------|
| 支持区间 | **Python 3.10 ~ 3.13**（3.14 未验证，不保证） |
| 3.13 能否用 | **可以直接用**：全部依赖都有 cp313 / abi3 wheel，不需要降级 Python |
| 代码改动 | **无需改动**：项目未使用任何 3.12/3.13 移除的模块或 API |
| 唯一版本门槛 | `paddlepaddle >= 3.2.1`（首个提供 cp313 wheel 的版本） |
| 安装方式 | 3.13 用 `pip install -r requirements-py313.txt`；其余用平台清单 |
| 自检方式 | `python tools/check_env.py` → 「Python 3.13 兼容性」小节 |

---

## 2. 已核查的依赖 wheel 可用性（针对当前固定版本）

核查方法：查询 PyPI 各项目该版本的发布文件（是否含 `cp313` / `abi3` wheel）。

| 依赖 | 固定版本 | cp313 wheel | 说明 |
|------|---------|-------------|------|
| **paddlepaddle** | 3.2.1 | ✅ 有 | win_amd64 / manylinux1_x86_64 / manylinux2014_aarch64 / macosx_11_0_arm64 |
| paddleocr / paddlex | 3.3.0 / 3.2.0 | ✅ 纯 Python | 依赖上面的 paddlepaddle |
| **torch / torchvision** | 2.9.0 / 0.24.0 | ✅ 有 | cp313 覆盖 win_amd64、manylinux_2_28_x86_64/aarch64、macOS arm64 |
| numpy | 2.2.6 | ✅ 有 | 55 个 wheel，含 cp313 全平台 |
| pandas | 2.3.3 | ✅ 有 | 同上 |
| scipy | 1.16.2 | ✅ 有 | |
| scikit-image | 0.25.2 | ✅ 有 | |
| matplotlib | 3.10.7 | ✅ 有 | |
| opencv-python | 4.12.0.88 | ✅ abi3 | `cp37-abi3` wheel 向前兼容 3.13（含 win_amd64、manylinux x86_64/aarch64） |
| tokenizers | 0.22.1 | ✅ abi3 | `cp39-abi3`，覆盖 3.13 |
| pydantic-core | 2.41.4 | ✅ 有 | |
| lxml / pillow / shapely / pycryptodome | 6.0.2 / 12.0.0 / 2.1.2 / 3.23.0 | ✅ 有 | |
| ultralytics / easyocr | 8.3.217 / 1.7.2 | ✅ 纯 Python | 运行时依赖 torch |

> 也就是说：**当前 `requirements.txt` 里固定的版本本身就满足 3.13**，
> `requirements-py313.txt` 只是在基线之上追加"可用性下限"，防止解析器回退到
> 没有 cp313 wheel 的旧版本（最典型的就是 `paddlepaddle < 3.2.1`）。

### 3.13 上容易出现问题的依赖

| 依赖 | 3.13 最低可用版本 | 低于该版本的后果 |
|------|------------------|------------------|
| paddlepaddle | 3.2.1 | 无 wheel，pip 尝试源码编译，几乎必然失败（需完整 C++ 工具链） |
| torch | 2.6.0 | 无 cp313 wheel |
| numpy | 2.1.0 | 无 cp313 wheel |
| opencv-python | 4.10.0 | 无可用 abi3 wheel（老版本仅 cp3x 专用 wheel） |
| tokenizers | 0.21.0 | 无可用 abi3 wheel |

---

## 3. 代码层面的兼容性核查

对全部自有代码（排除第三方目录）做了静态扫描，结果：

| 检查项 | 结果 |
|--------|------|
| `distutils` / `imp` / `parser` / `symbol`（3.12 移除） | 0 处 |
| PEP 594 移除模块（`cgi`、`crypt`、`telnetlib`、`pipes`、`imghdr`、`sndhdr`、`audioop`、`chunk`、`uu`、`xdrlib`、`nis`、`spwd`、`sunau`、`mailcap`、`msilib`、`ossaudiodev`、`asynchat`、`asyncore`、`smtpd`、`lib2to3`） | 0 处 |
| `datetime.utcnow()` / `locale.getdefaultlocale()` / `importlib.find_loader()` / `typing.ByteString` | 0 处 |
| f-string 表达式内反斜杠（3.12 起才允许，3.10/3.11 会语法错误） | 0 处（验证套件中曾有一处，已修正） |
| 类型标注 `X \| Y` | 全部文件已 `from __future__ import annotations`，3.10 亦可用 |
| `list[str]` / `dict[str, X]` 运行期下标 | Python 3.9+ 支持，OK |

新增的版本策略集中在 `hudcore/platform/system.py`：

```python
PYTHON_MIN = (3, 10)              # 低于此版本直接报错并给出升级建议
PYTHON_MAX_TESTED = (3, 13)       # 高于此版本按"尽力支持"给出警告
python_status() -> ("ok" | "warn" | "error", 说明文字)   # 供自检/启动日志复用
```

---

## 4. 升级到 Python 3.13 的步骤

### Windows

```bat
:: 1) 安装 Python 3.13（python.org 官方安装器，勾选 tcl/tk 与 Add to PATH）
::    https://www.python.org/downloads/windows/  （选择 Windows installer (64-bit)）
:: 2) 建虚拟环境并安装依赖
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements-py313.txt
:: 3) 自检
python tools\check_env.py
python tools\selftest.py
python tools\check_imports.py
:: 4) 启动
run.bat
```

PyTorch 按需单独装（GPU 版示例）：

```bat
pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0 ^
    --index-url https://download.pytorch.org/whl/cu126
```

### Ubuntu 22.04

系统自带 3.10；需要用 3.13 时推荐 deadsnakes PPA 或官方源码包：

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-tk
python3.13 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements-py313.txt
python tools/check_env.py
```

> 注意：`python3.13-tk` 提供 tkinter；缺它时所有 GUI 功能不可用（自检会明确报出）。

---

## 5. 自检输出示例

```
=== 平台 ===
[OK]  OS=Windows Python=3.13.7 arch=AMD64
[OK]  Python 3.13.7  (C:\Python313\python.exe)
[OK]  Python 版本受支持（3.10 ~ 3.13）
      注: Python 3.13 需要 paddlepaddle>=3.2.1（首个提供 cp313 wheel 的版本）…
=== Python 3.13 兼容性 ===
[OK]  paddlepaddle 3.2.1（满足 3.13 要求 >= 3.2.1）
[OK]  torch 2.9.0（满足 3.13 要求 >= 2.6.0）
[OK]  numpy 2.2.6（满足 3.13 要求 >= 2.1.0）
[OK]  opencv-python 4.12.0（满足 3.13 要求 >= 4.10.0）
[OK]  tokenizers 0.22.1（满足 3.13 要求 >= 0.21.0）
```

---

## 6. 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| `paddlepaddle` 安装时开始编译源码并报 C++ 错误 | 版本 < 3.2.1，3.13 无 wheel | `pip install -U "paddlepaddle>=3.2.1"` |
| `ModuleNotFoundError: No module named '_tkinter'` | 安装 Python 时未勾选 tcl/tk（Windows）或未装 `python3.13-tk`（Ubuntu） | 重装并勾选 tcl/tk / `apt install python3.13-tk` |
| `ImportError: libtk8.6.so: cannot open shared object file` | Linux 上缺 Tk 运行库 | `sudo apt install -y tk8.6`（或 `python3-tk`） |
| `pip` 解析出 numpy 1.x / torch 2.4 等旧版本 | 未使用 py313 清单，解析器选了无 3.13 wheel 的版本 | 用 `requirements-py313.txt` |
| OCR/YOLO 功能不可用 | 未装 torch / paddlepaddle（可选依赖） | 按 §4 安装；其余功能不受影响 |
| 想在无 Windows 机器上验证 | — | 用 `docker/windows-sim/` 在容器内构造 Windows 运行时验证 |

---

## 7. 相关文档

- [`docs/WINDOWS_VERIFICATION.md`](WINDOWS_VERIFICATION.md) —— Windows 环境实测验证结果
- [`docs/PLATFORM_GUIDE.md`](PLATFORM_GUIDE.md) —— 平台化改造与扩展指南
- [`docs/UBUNTU_SETUP.md`](UBUNTU_SETUP.md) —— Ubuntu 22.04 部署细节
- [`requirements-py313.txt`](../requirements-py313.txt) —— Python 3.13 依赖清单
