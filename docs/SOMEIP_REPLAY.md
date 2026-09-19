# SOME/IP 回放功能（HudAutoTest 集成版）

把原 `someip` 工程（`arhud_python_server`）的 SOME/IP 服务端能力整合进 HUD 上位机：
在界面里**指定 pcap 回放**、**对数据结构赋值后组包发送**、**勾选要 offer 的服务/事件**。

- 业务层：`someip_core/`（不含界面，可在无显示器环境使用）
- 界面层：`someip_gui/`（独立窗口，从主界面「SOME/IP 回放」按钮进入）
- 平台层：`hudcore/someip/`（库探测与加载）
- 内核：C++ 库 `libarhud_server`（vsomeip SP 分支，负责 offer/SD/发送/TP 重组）

---

## 1. 界面布局（发送界面改造说明）

窗口按"**左侧配置、右侧动作与反馈**"分区，避免原来把配置、发送、日志混在一列的问题：

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│ [打开服务][启动服务][停止][关闭服务] │ [重新检测库][导出服务表]   状态: 库就绪｜…  [保存配置] │
├──────────────────────────────────┬────────────────────────────────────────────────┤
│ ① 网络与 SD 配置                  │ ③ pcap 回放控制                                 │
│   单播地址 [__________][自动探测]  │   pcap [________________][浏览…][解析摘要]       │
│   network  [arhud01]              │   循环 ☑   节流间隔(ms) [10]  [开始回放][停止回放]│
│   vsomeip 配置 [______][浏览…]     │   已发送 0 条       （库返回 0=成功，条数以计数为准）│
│   ☑ 打开服务时自动启动             │   ── pcap 摘要：总包/SD/通知/TP 分片 + 逐事件条数 ──│
│ ② 服务 / 事件（勾选 = 注册）        │ ④ 单条发送（结构化赋值 → C++ 序列化 → 发送）      │
│   [全选][全不选][仅结构化类型] 过滤[]│   类型 [RTK ▾] [载入示例值][清零字段]  [发送该事件] │
│  ┌──────────────────────────────┐ │   ┌────────────┬───────────┬──────────┐        │
│  │注册 服务   事件   名称  类型  TP│ │   │ 字段        │ 值        │ 类型     │        │
│  │ ☑  0x000A 0x8001 Vehicle… 否 │ │   │ Counter     │ 1         │ 整数     │        │
│  │ ☑  0x000B 0x8001 RTKInfo… 否 │ │   │ Checksum    │ 0(只读)   │ 整数     │        │
│  │ …（23 行，可滚动）             │ │   │ …（按结构体自动生成，RTK 27 个字段）      │        │
│  └──────────────────────────────┘ │   └────────────┴───────────┴──────────┘        │
│                                   │   目标：0x000B:0x8001（Checksum 由库自动 CRC32） │
│                                   │ ⑤ 操作与报文日志  [清空][导出日志][打开数据目录]  │
│                                   │   ┌──────────────────────────────────────────┐  │
│                                   │   │ [12:01:03] 已注册 11 个服务 / 23 个事件     │  │
│                                   │   │ [12:01:05] 开始回放 out.pcap … 413 条      │  │
│                                   │   └──────────────────────────────────────────┘  │
└──────────────────────────────────┴────────────────────────────────────────────────┘
```

要点：

| 区块 | 为什么这样放 |
|------|--------------|
| ① 网络与 SD 配置 | 注册/发送前必须先确定"用哪个 IP、哪份 vsomeip 配置"，属前置条件，置于左上 |
| ② 服务/事件勾选 | **勾选 = 注册**，与 C++ 库"create 后、start 前注册"的语义一一对应；支持全选/仅结构化类型 |
| ③ 回放控制 | pcap 选择、循环/节流、启停与计数集中一处；「解析摘要」先在本地解析，回放前即可确认内容 |
| ④ 单条发送 | 字段表**由 ctypes 结构体自动生成**，界面字段与协议字段不会脱节；Checksum 只读（库自动算 CRC32） |
| ⑤ 日志 | 所有动作与结果按时间戳记录，可导出，现场排障直接给日志 |

---

## 2. 快速使用

1. 主界面点击 **「SOME/IP 回放」**；
2. 顶部 **[打开服务]**（创建 vsomeip 应用并注册勾选的服务/事件）→ **[启动服务]**（offer + SD 应答）；
3. 回放：③ 选 pcap → **[解析摘要]** 确认内容 → 设置循环/节流 → **[开始回放]**；
4. 单发：④ 选类型 → **[载入示例值]** 或手动填 → **[发送该事件]**；
5. 结束时 **[关闭服务]** 或直接关窗（自动按"停回放 → 停服务 → 销毁实例 → 保存配置"清理）。

配置持久化在 `data/someip/replay_config.json`；服务/事件表可 **[导出服务表]** 到 `data/someip/services.json`。

---

## 3. 库的获取与部署

程序按下列顺序查找库（`hudcore/someip/backend.py`）：

1. 环境变量 `HUD_SOMEIP_LIB` / `ARHUD_LIB_PATH`（完整文件路径）
2. 环境变量 `HUD_SOMEIP_LIB_DIR` / `ARHUD_LIB_DIR`（目录）
3. **`thirdparty/arhud_someip/<平台>-<架构>/`（首选，如 `linux-x86_64`、`linux-aarch64`）**
4. `thirdparty/arhud_someip/<平台>/`
5. `thirdparty/arhud_someip/`（扁平放置）
6. `drivers/someip/<平台>/`（旧位置，兼容既有部署）
7. 项目根目录、系统库路径

### Linux（已验证）

```bash
# 1) 编译（源码在 someip 工程的 arhud_python_server/src）
cd arhud_python_server/src
make libarhud_server.so ARCH=aarch64 SP_LIBS=<SP库目录>      # x86_64 用 ARCH=x86_64

# 2) 部署：libarhud_server.so 与 libsomeip*.so 必须放在同一目录
#    目录按"平台-架构"区分（同名库在 aarch64/x86_64 上 ABI 不兼容，混放会 dlopen 报错）
mkdir -p data_test/HudAutoTest/thirdparty/arhud_someip/linux-x86_64     # 或 linux-aarch64
cp libarhud_server.so libsomeip*.so data_test/HudAutoTest/thirdparty/arhud_someip/linux-x86_64/

# 3) 运行（无需设置 LD_LIBRARY_PATH）
python main.py
```

**同目录依赖会自动预加载**：SP 版 libsomeip 在运行期按**文件名**插件式 dlopen
`libsomeip-cfg.so` / `libsomeip-sd.so` 等，仅靠 `libarhud_server.so` 的 NEEDED 记录
找不到同目录插件（典型症状：`Configuration module could not be loaded!`，
随后 `create()` 长时间阻塞）。`hudcore.someip.backend.preload_sibling_libraries()`
会在加载主库前，用**绝对路径 + RTLD_GLOBAL** 多轮预加载同目录的 `libsomeip*.so`
（多轮是必需的：cfg/sd/e2e 依赖 `libsomeip.so`，需等它先进入内存），
之后 vsomeip 按文件名的 dlopen 即可命中，因此**不必再导出 LD_LIBRARY_PATH**。
若仍报该错误，可临时 `export LD_LIBRARY_PATH=<库目录>` 兜底。

依赖：`zlib1g-dev`（编译期）、`libusb` 等（运行期按 SP 库要求）。

### Windows（**当前留占位，尚未提供 DLL**）

- 需要把 `arhud_python_server` 用 **MSVC** 编译为 `libarhud_server.dll`（并链接 Windows 版 vsomeip），
  放到 `thirdparty/arhud_someip/windows/`（旧位置 `drivers/someip/windows/` 仍兼容）；
- 在该 DLL 就绪前，Windows 上打开窗口会显示：

  > SOME/IP 库不可用（动作已置灰）

  日志区同时给出放置路径与编译提示；**窗口本身不会崩溃**，其余功能（CAN 测试、图像工具等）不受影响；
- 临时替代方案：在 Ubuntu 上运行本功能，或用 WSL/容器承载 SOME/IP 回放。

---

## 3.5 与参考实现的更新（lipeng20260228）

参考实现（`lipeng20260228/`，含 old / BPlus 两套程序与 `libs.zip`）给出了 HUD 团队实际在用的
服务端配置与 vsomeip 库。本项目据此做了三处对齐：

### ① 库更新（Linux 两架构）

| 位置 | 来源 | 版本日期 | 说明 |
|------|------|----------|------|
| `thirdparty/arhud_someip/linux-aarch64/libsomeip*.so` | `libs.zip → libs/lib_bst_t517` | 2025-12-15 | 与 `libarhud_server.so`（本项目 C++ 库）实测兼容 |
| `thirdparty/arhud_someip/linux-x86_64/libsomeip*.so` | `libs.zip → libs/lib_x86` | 2025-12-23 | 同上 |
| `thirdparty/arhud_someip/windows/` | — | — | **按要求留空**：暂无 Windows 版 vsomeip/服务端库，界面会显示"库不可用"而不是崩溃 |

库文件不入 git（`.gitignore` 忽略）；同目录依赖由 `hudcore.can`/`hudcore.someip` 的预加载机制处理，
无需设置 `LD_LIBRARY_PATH`。

### ② vsomeip 配置随仓库分发

参考实现的做法是"把配置放在可执行文件同目录直接运行"；本项目改为**随仓库分发 + 显式传给服务端**：

```
data/someip/config/someip_arhud01_pcap_server.json                 # old 代，unicast=auto（默认使用）
data/someip/config/someip_arhud01_pcap_server_static_unicast.json   # old 代，unicast=192.168.195.11（现场固定 IP）
data/someip/config/someip_arhud01_pcap_server_B+.json               # B+ 代（见下）
```

`ReplayConfig.config_path` 留空时，默认使用**当前服务表代**对应的配置（见
`someip_core.config.shipped_config_path()`）。

### ③ 两代服务表（新增 B+）

| 代 | 服务/事件 | 来源 | 回放库能否注册 |
|----|-----------|------|----------------|
| `old`（默认） | 11 / 23 | `someip_arhud01_pcap_server.json` | ✅ 已实测（11 服务/23 事件、RTK 194 字节、样例 pcap 90/90） |
| `bplus` | 6 / 38 | `someip_arhud01_pcap_server_B+.json` | ✅ 可（服务端库支持；需 profile 与 Python 侧一致，见下） |

- 开关：环境变量 `HUD_SOMEIP_TABLE=old|bplus`、`someip_core.set_table()`、或界面
  **SOME/IP 回放 → ① 网络与 SD 配置 → 服务表** 下拉框（切换即刷新事件树，并明确提示该代能否注册）；
- 单测 `tests/test_someip_tables.py` 会**逐条比对**两代配置与我们代码里的服务表，防止三者漂移；
- **profile 联动（重要）**：服务端库在 `create()` 时读 `ARHUD_SERVICE_PROFILE` 决定内置表，
  Python 侧按自己的服务表逐条 `add_service/add_event`。`ReplayController.open()` 会把当前
  服务表代写入该环境变量，保证两侧同代；两边不一致时以服务表代为准并记录告警。
- 实测（容器内，更新后的服务端库）：
  · old：注册 **11 服务/23 事件**，样例 pcap **413/413** 成功投递；
  · bplus：注册 **6 服务/38 事件**，B+ 的 pcap **14667/14667** 成功投递；
- **更正一处此前的误读**：早前记录"B+ pcap 14667 条只发出 6594 条"其实是两点造成的假象 ——
  ① 观察窗口 45s 小于 14667×5ms 的回放时长；② 当时库的 `replay_sent` 把**尝试次数**也算成功，
  而未注册的事件其实发送失败。服务端库已修正为 `sent`（真正成功）/`attempted`（尝试）两个计数，
  因此现在可以据此判断 profile 是否选对：**差值 = 未注册事件数**。

### ④ 一键自检

```bash
python -m scripts.someip_replay_check          # 库 → 配置 → 服务表 → 注册 → 单条发送 → pcap 回放
python -m scripts.someip_replay_check --table bplus    # 查看 B+ 代（预期提示不可注册）
```

自带小样例 `data/someip/sample/out_sample.pcap`（参考实现 `old/out.pcap` 的前 400 包，454 KB，
解析出 90 条可回放通知），因此**任何机器 clone 后都能立即自检**，不依赖现场 pcap。

## 4. 实测验证（容器内真实库）

在 Ubuntu（aarch64）容器中编译真实 `libarhud_server.so` 并跑通全链路：

| 步骤 | 结果 |
|------|------|
| 编译 | `make libarhud_server.so` → 83 KB，导出 11 个 `arhud_server_*` 符号 |
| 库探测 | 库放 `thirdparty/arhud_someip/linux-aarch64/`，**不设任何环境变量** → 自动命中并显示「SOME/IP 库就绪」 |
| 库版本 | 换成参考实现 `libs.zip` 的版本（aarch64 2025-12-15 / x86_64 2025-12-23）后复测通过 |
| 同目录依赖预加载 | 自动预加载 `libsomeip*.so` 4 个（多轮：`libsomeip.so` → cfg/sd/e2e）；按文件名 `dlopen("libsomeip-cfg.so")` 命中成功，**无需 `LD_LIBRARY_PATH`** |
| 创建/注册 | `open()` 成功；默认 `register()` → **11 服务 / 23 事件**（仅选 RTK 时 → 1 服务 / 2 事件） |
| 启动 | `start()` 成功，vsomeip 应用 `arhud01` 启动并 offer（SD 报文可见） |
| 结构化发送 | `send_struct("RTK", …)` → 0x000B:0x8001，**194 字节**（CRC32 由库补齐） |
| 原始发送 | `send_raw(0x000B, 0x8002, …)` 成功 |
| **pcap 回放** | `out.pcap`：本地解析 **1659 包 / 24 SD / 375 通知 / 1260 TP 分片 → 413 条**；C++ 库回放实际发送 **413 条**（两侧完全一致） |
| 关闭 | 停回放 → 停服务 → 销毁实例，无残留 |

界面侧（Xvfb）验证：事件表 23 行、字段表按结构体生成（RTK 27 / VehiclePosition 34 / PilotStatus 7 字段）、
勾选交互、库不可用时按钮置灰且提示只弹一次、关窗保存配置 —— 全部通过（见 `tests/test_someip_gui.py`）。

---

## 5. 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| 状态栏「库不可用（动作已置灰）」 | 未找到 `libarhud_server.so/.dll` | 按 §3 放到 `thirdparty/arhud_someip/<平台>/`；点 **[重新检测库]** 重试 |
| `库加载失败` 且提示缺 `libsomeip*.so` | SP 库未与 `libarhud_server.so` 同目录 | 把 `libsomeip*.so` 与其放同一目录（重跑 `tools/fetch_thirdparty_libs.py someip` 可看到放置路径） |
| 卡在 `Configuration module could not be loaded!` 且 `create()` 长时间无返回 | 同目录 `libsomeip-cfg.so` 未加载进来 | 正常情况已由 `preload_sibling_libraries()` 自动处理；仍出现时 `export LD_LIBRARY_PATH=<库目录>` 后重试 |
| 发送报 `rc=-1` | 事件未注册或服务未启动 | 先 **[打开服务]/[启动服务]**；确认该事件已在 ② 勾选 |
| 回放 `rc=-1` | pcap 无法解析 | 点 **[解析摘要]** 看本地解析结果（无通知的 pcap 无法回放） |
| 「已发送」停在 0 | 客户端未订阅（SD 未完成） | 确认板端/客户端在线、组播可达（224.0.2.4:30490）、端口未被占用 |
| 回放很快结束 | 节流间隔为 0 时按原始时序 | 需要更慢/更快可调 ③ 的「节流间隔(ms)」 |

---

## 6. 设计说明（与项目约定的关系）

- 业务与界面分离：`someip_core` 不依赖 tkinter，可被脚本/测试直接复用；
- 库加载集中在 `hudcore.someip`（与 `hudcore.can` 同一模式：环境变量 → 项目目录 → 系统路径 + 中文修复提示）；
- **惰性加载**：不在 import 时 dlopen（原工程 `arhud_python.py` 在 import 时加载，库缺失就直接导入失败）；
- 状态放在控制器对象里（`ReplayController`），不引入新的模块级全局变量；
- 勾选/字段等界面状态可持久化（`data/someip/replay_config.json`），数据与代码分离。
