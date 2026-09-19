# thirdparty/arhud_someip —— SOME/IP 服务端运行时库（按平台放置）

HudAutoTest 的「SOME/IP 回放」功能通过 `ctypes` 调用这里的 C++ 库
（源码：someip 工程的 `arhud_python_server/src`，协议栈为 vsomeip SP 分支）。

```
thirdparty/arhud_someip/
├── linux-aarch64/  libarhud_server.so + libsomeip*.so（按架构分开，避免 ELF class 不匹配）
├── linux-x86_64/   同上
└── windows/        **按要求留空**（暂无 libarhud_server.dll，需 MSVC 编译，见下）
```

> 本目录下的 `*.so` / `*.dll` / `*.dylib` 已在 `.gitignore` 中忽略：
> **运行时库不随仓库分发**，由部署方按平台放入。

---

## 1. 程序到哪里找库

`hudcore/someip/backend.py` 按下列顺序探测（先命中先用）：

| 顺序 | 位置 | 说明 |
|------|------|------|
| 1 | `HUD_SOMEIP_LIB` / `ARHUD_LIB_PATH` | 完整文件路径（现场临时替换最方便） |
| 2 | `HUD_SOMEIP_LIB_DIR` / `ARHUD_LIB_DIR` | 所在目录 |
| 3 | **`thirdparty/arhud_someip/<平台>/`** | **首选**（本目录） |
| 4 | `thirdparty/arhud_someip/` | 不分平台时的扁平放置 |
| 5 | `drivers/someip/<平台>/` | 旧位置，兼容既有部署 |
| 6 | 项目根目录、系统库路径 | 兜底 |

库文件名候选：`libarhud_server.so|dll`、`arhud_server.so|dll`。

---

## 2. Linux 部署（已验证）

```bash
# 1) 编译（源码在 someip 工程的 arhud_python_server/src）
cd <someip>/arhud_python_server/src
make libarhud_server.so ARCH=aarch64 SP_LIBS=<SP库目录>      # x86_64 用 ARCH=x86_64

# 2) 放到首选位置（libsomeip*.so 必须与 libarhud_server.so 同目录）
mkdir -p <HudAutoTest>/thirdparty/arhud_someip/linux-aarch64     # 按架构选子目录
cp libarhud_server.so libsomeip*.so <HudAutoTest>/thirdparty/arhud_someip/linux-aarch64/

# 3) 运行（同目录 libsomeip*.so 会被自动预加载，无需 LD_LIBRARY_PATH）
cd <HudAutoTest>
python main.py
```

编译期依赖 `zlib1g-dev`；运行期按 SP 库要求（如 `libusb`）。

服务表有两代（见 `docs/SOMEIP_REPLAY.md` §3.5 与 `someip_core.models`）：
`old`（11 服务/23 事件）与 `bplus`（6 服务/38 事件），**两代都由本库注册**，
库侧开关是环境变量 `ARHUD_SERVICE_PROFILE`（上位机在打开服务端时会按当前服务表代自动同步）。

实测（Ubuntu aarch64 容器）：库加载 → 创建 vsomeip 应用 → 注册 11 服务/23 事件 →
`out.pcap` 回放发送 413 条（与本地解析一致）。详见 `docs/SOMEIP_REPLAY.md`。

---

## 2.5 库版本与来源（2026-02 对齐参考实现）

| 平台 | 文件 | 来源 | 版本日期 |
|------|------|------|----------|
| linux-aarch64 | `libsomeip*.so` | 参考实现 `lipeng20260228/libs.zip → libs/lib_bst_t517` | 2025-12-15 |
| linux-x86_64 | `libsomeip*.so` | 参考实现 `lipeng20260228/libs.zip → libs/lib_x86` | 2025-12-23 |
| 两平台 | `libarhud_server.so` | 本项目 `arhud_python_server/src`（2026-02 重建：两代服务表 profile、配置对齐、回放计数修正、rpath `$ORIGIN`） | 与本仓库同步 |

更新方式：解压参考实现的 `libs.zip`，把 `lib_bst_t517/*` 覆盖到 `linux-aarch64/`、
`lib_x86/*` 覆盖到 `linux-x86_64/`（文件名与 SONAME 都是 `libsomeip*.so`，可直接替换），
然后跑 `python -m scripts.someip_replay_check` 复验（实测：11 服务/23 事件、RTK 194 字节、
自带样例 pcap 90/90）。

---

## 3. Windows（按要求留空，尚无 DLL）

1. 用 **MSVC** 编译 `arhud_python_server` 为 `libarhud_server.dll`（链接 Windows 版 vsomeip）；
2. 放到 `thirdparty/arhud_someip/windows/`（或设 `HUD_SOMEIP_LIB`）；
3. **当前状态：`windows/` 目录按要求留空**（只有 `.gitkeep`），暂无 Windows 版 vsomeip/服务端库；
   在此之前，Windows 上打开「SOME/IP 回放」窗口会显示
   **“SOME/IP 库不可用（动作已置灰）”** 并在日志给出上述提示 —— 窗口不崩、其它功能不受影响；
4. 临时替代：在 Ubuntu 上运行该功能，或用 WSL/容器承载 SOME/IP 回放。

---

## 4. 为什么放在 thirdparty 而不是 drivers

项目对"三方内容"的收纳规则（见 `thirdparty/README.md`）：

- 第三方提供的**源码/框架/模型/SDK 资源** → `thirdparty/<名称>/`
- 第三方提供的**运行时库/可执行文件（按平台区分）** → `thirdparty/<组件>/<平台>/`（本目录）
- `drivers/<平台>/`、`bin/<平台>/` 为**历史部署目录**，仍被探测链兼容，便于老部署平滑过渡

`drivers/someip/README.md` 保留为指向本目录的说明。
