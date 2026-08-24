# Windows 部署解决方案

> 场景：**部署机是 Windows PC**（很多台架/HIL 环境），需要跑 Python + C++ 服务端库，
> 经车载以太盒子连开发板。本文给出方案对比、修改清单与构建步骤。

---

## 1. 根本限制（先说结论）

**SP 分支协议栈（libsomeip.so）只有 Linux 版**（zip 内 lib_bst_t517/lib_x86 均为 Linux ELF），
**Windows 上无法使用**。因此：

| 能力 | Linux | Windows |
|------|-------|---------|
| SP 分支库（与板端 C++ 服务端同栈） | ✅ | ❌ 无 Windows 版 |
| 标准 vsomeip 跨机提供数据 | ✅ | ✅（justinlhudson/vsomeip Windows fork） |
| pcap 回放 / TP 重组 / 结构化序列化 | ✅ | ✅（纯数据层，平台无关） |
| Python ctypes 封装 | ✅ | ✅（ctypes 跨平台） |

> 关键事实：**标准 vsomeip 服务端与板端 SP 客户端跨机互通已实测**（Python 服务端即标准
> vsomeip，16 事件收到、51KB TP 大消息正常）。所以 Windows 上改用标准 vsomeip fork，
> **跨机部署不受影响**；仅同机 UDS 直连不可用（跨机场景本就不需要）。

---

## 2. 三个可选方案

| 方案 | 改动量 | 适用场景 | 说明 |
|------|--------|----------|------|
| **A. Windows 原生**（标准 vsomeip fork） | 中 | 必须用 Windows 本机运行 | 编译 `libarhud_server_std.dll`，链接 justinlhudson/vsomeip |
| **B. WSL2** | 小 | Windows 上可装 WSL2 | 现有 `.so` 零改动，WSL2 内跑 Linux 服务端，与 Windows 共享网卡 |
| **C. Docker Desktop** | 小 | Windows 上可装 Docker | Linux 容器跑现有 `.so`，`--network host` 或桥接，Windows 只做管理 |

**推荐**：能装 WSL2/Docker 就选 B/C（零代码改动）；**必须原生 Windows** 用方案 A。

---

## 3. 方案 A：Windows 原生部署（详细修改清单）

### 3.1 依赖获取

| 依赖 | Windows 版来源 |
|------|---------------|
| vsomeip Windows fork | `https://github.com/justinlhudson/vsomeip`（CMake 构建，支持 MSVC/MinGW） |
| boost | vsomeip fork 依赖 boost（vcpkg：`vcpkg install boost`，或预编译） |
| zlib | vcpkg：`vcpkg install zlib`；或 zlib 官方 Windows 预编译 dll |
| Python 3 | python.org 安装包（ctypes 为标准库） |

### 3.2 代码修改（已完成条件编译）

| 文件 | Linux 依赖 | Windows 修改（已加 `#ifdef _WIN32`） |
|------|-----------|-------------------------------------|
| `src/arhud_pcap.cpp` | `<arpa/inet.h>` | → `<winsock2.h>`（ntohs/ntohl 相同） |
| `src/arhud_server.cpp`（标准版） | `<unistd.h>` + `getpid()`、`/tmp/` | → `<process.h>` `_getpid()`、`GetTempPathA()` |
| `src/arhud_server_sp.cpp` | SP 分支库 | **Windows 不用 SP 版**，改用标准版 |
| `src/arhud_types.cpp` | zlib | zlib Windows 版（vcpkg） |

> Windows 用 **标准版 `arhud_server.cpp`**（内部 vsomeip 标准 API），编译产物
> `libarhud_server_std.dll`（或改名 `libarhud_server.dll` 供 Python 加载）。

### 3.3 构建（CMake，支持 MSVC / MinGW-w64）

```bash
# 准备（MinGW-w64 示例；MSVC 用对应生成器）
git clone https://github.com/justinlhudson/vsomeip.git
cd vsomeip && cmake -B build -DCMAKE_INSTALL_PREFIX=install && cmake --build build && cmake --install build
# zlib（vcpkg）
vcpkg install zlib

# 构建服务端库
cd arhud_python_server
cmake -B build-win -DVSOMEIP_DIR=<vsomeip install/lib/cmake> \
      -DZLIB_ROOT=<zlib路径> -G "MinGW Makefiles"
cmake --build build-win --config Release
# 产物：build-win/libarhud_server_std.dll
```

CMakeLists 已提供（见本目录 `CMakeLists.txt`），自动按平台选择标准版源码并链接 vsomeip/zlib。

### 3.4 Python 侧修改

| 项 | Linux | Windows |
|----|-------|---------|
| 库文件 | `libarhud_server.so` | `libarhud_server.dll`（编译时把标准版改名为此） |
| 加载 | `ctypes.CDLL` | `ctypes.CDLL` 同样可用（cdecl 接口）✓ |
| DLL 搜索路径 | `LD_LIBRARY_PATH` | ① 把 dll 与 vsomeip dll 放同一目录；② Python 启动前 `os.add_dll_directory(r"C:\path\to\dlls")`；③ 或加入 `PATH` |
| 配置路径 | `/tmp/xxx.json` | `GetTempPathA()`（代码已处理） |
| 多播 | 直接 | **Windows 防火墙需放行多播 + UDP**（见 3.5） |

Python 代码已兼容：`arhud_py.py` 用 `ARHUD_LIB_PATH` 环境变量可指定 dll 路径；
库名差异在部署时通过 `ARHUD_LIB_PATH` 或改名解决（也可在 `arhud_py.py` 里按
`sys.platform == "win32"` 自动选 `.dll`）。

### 3.5 Windows 防火墙（关键，经常踩坑）

```powershell
# 管理员 PowerShell
New-NetFirewallRule -DisplayName "ARHUD SOME/IP UDP" -Direction Inbound -Protocol UDP `
  -LocalPort 30490,51400-51409,52001-52012 -Action Allow
# 多播（vsomeip SD 用 224.0.2.4:30490）
New-NetFirewallRule -DisplayName "ARHUD SD multicast" -Direction Inbound -Protocol UDP `
  -LocalPort 30490 -RemoteAddress 224.0.2.4 -Action Allow
```

### 3.6 配置差异

- Windows fork 的**本地通道是 TCP 127.0.0.1**（不是 Linux UDS），但**跨机部署用不到
  本地通道**（SD 多播 + UDP 数据），配置由库自动生成，无需改动；
- 网卡选择：多网卡机器用 `ARHUD_UNICAST` 指定连盒子那块的 IP。

---

## 4. 验证步骤（Windows）

```bash
# 1) 纯本地自检（无需板子）：先起一个 vsomeip 客户端/服务端确认栈可用
#    参考仓库 windows/ 目录（vsomeip_server_windows.py 等）
# 2) 跨机联调（推荐复用 Docker 双容器测试验证协议链路，再切 Windows 实机）
bash docker/integration_test_cpplib.sh     # Linux 容器验证服务端库逻辑
# 3) Windows 实机：启动服务端库 + 板子联调
set ARHUD_LIB_PATH=C:\arhud-server\libarhud_server.dll
python demo_replay.py data\out.pcap 192.168.1.10
```

---

## 5. 已知限制（Windows 方案 A）

1. 协议栈是标准 vsomeip fork，不是 SP 分支：**同机 UDS 直连板端中间件不可用**（跨机不受影响）；
2. `0x000E:8001`（客户端组 0 订阅）跨机 SD 无法投递（与 Linux 标准版相同限制）；
3. 订阅回调（`arhud_server_set_subscribe_cb`）依赖 vsomeip fork 的 API，需按 fork 头文件确认；
4. 建议先用 Linux 容器（方案 B/C）验证业务逻辑，Windows 原生（方案 A）作为最终部署形态。
