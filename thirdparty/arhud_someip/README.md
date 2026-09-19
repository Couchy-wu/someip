# thirdparty/arhud_someip —— SOME/IP 服务端运行时库（按平台放置）

HudAutoTest 的「SOME/IP 回放」功能通过 `ctypes` 调用这里的 C++ 库
（源码：someip 工程的 `arhud_python_server/src`，协议栈为 vsomeip SP 分支）。

```
thirdparty/arhud_someip/
├── linux/     libarhud_server.so + libsomeip.so / libsomeip-cfg.so / libsomeip-sd.so / libsomeip-e2e.so
└── windows/   libarhud_server.dll（**暂无产物**，需用 MSVC 编译，见下）
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
mkdir -p <HudAutoTest>/thirdparty/arhud_someip/linux
cp libarhud_server.so libsomeip*.so <HudAutoTest>/thirdparty/arhud_someip/linux/

# 3) 运行：SP 版 libsomeip 由插件方式加载，需要 LD_LIBRARY_PATH 指向该目录
cd <HudAutoTest>
LD_LIBRARY_PATH=$PWD/thirdparty/arhud_someip/linux python main.py
```

编译期依赖 `zlib1g-dev`；运行期按 SP 库要求（如 `libusb`）。

实测（Ubuntu aarch64 容器）：库加载 → 创建 vsomeip 应用 → 注册 11 服务/23 事件 →
`out.pcap` 回放发送 413 条（与本地解析一致）。详见 `docs/SOMEIP_REPLAY.md`。

---

## 3. Windows（当前留占位，尚无 DLL）

1. 用 **MSVC** 编译 `arhud_python_server` 为 `libarhud_server.dll`（链接 Windows 版 vsomeip）；
2. 放到 `thirdparty/arhud_someip/windows/`（或设 `HUD_SOMEIP_LIB`）；
3. 在此之前，Windows 上打开「SOME/IP 回放」窗口会显示
   **“SOME/IP 库不可用（动作已置灰）”** 并在日志给出上述提示 —— 窗口不崩、其它功能不受影响；
4. 临时替代：在 Ubuntu 上运行该功能，或用 WSL/容器承载 SOME/IP 回放。

---

## 4. 为什么放在 thirdparty 而不是 drivers

项目对"三方内容"的收纳规则（见 `thirdparty/README.md`）：

- 第三方提供的**源码/框架/模型/SDK 资源** → `thirdparty/<名称>/`
- 第三方提供的**运行时库/可执行文件（按平台区分）** → `thirdparty/<组件>/<平台>/`（本目录）
- `drivers/<平台>/`、`bin/<平台>/` 为**历史部署目录**，仍被探测链兼容，便于老部署平滑过渡

`drivers/someip/README.md` 保留为指向本目录的说明。
