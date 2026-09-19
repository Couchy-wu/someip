# thirdparty —— 第三方内容统一收纳目录

本目录用于集中管理**随仓库分发的第三方内容**（源码框架、工具、模型），
按子目录分别管理，避免它们散落在项目根目录、也避免与自研代码混在一起。

```
thirdparty/
├── ultralytics/     YOLO 框架源码（原 yolo_framework/ultralytics-8.3.217）
├── paddleocr/       PaddleOCR 源码（原 PaddleOCR-main）
├── zlg/             ZLG CAN SDK 资源（原 kerneldlls：DLL 与 XML 描述文件）
├── ffmpeg/          随项目分发的 ffmpeg 构建（原 vendor/ffmpeg）
├── models/          第三方预训练权重（原 models/，如 yolov8s.pt）
├── arhud_someip/    SOME/IP 服务端**运行时库**（按"平台-架构"放置，库文件不进仓库）
└── zlg_can/         ZLG CAN 驱动库（Windows 已有；Linux 用 tools/fetch_thirdparty_libs.py 联网获取）
```

---

## 1. 各子目录说明

| 子目录 | 内容 | 被谁使用 | 更新方式 |
|--------|------|----------|----------|
| `ultralytics/` | Ultralytics YOLO 框架源码（8.3.217） | `scripts/ocr_icon_test.py`（加入 `sys.path` 后 `from ultralytics import YOLO`）、`scripts/yolo_train.py`（权重与数据集定位） | 用新版本替换整个目录（保持目录名 `ultralytics/`） |
| `paddleocr/` | PaddleOCR 源码与模型目录（`model/`） | `scripts/ocr_icon_test.py`（`PADDLE_MODEL_HOME` 指向此处） | 替换目录；模型文件放 `paddleocr/model/` |
| `zlg/` | ZLG CAN SDK 附属资源（`*.dll`、设备描述 `*.xml`） | 现场排查与驱动配套（`hudcore.can` 只探测驱动库本身） | 随 ZLG SDK 版本替换 |
| `ffmpeg/` | ffmpeg 构建（含 `bin/`、`presets/`、`doc/`） | `hudcore.platform.executables.get_ffmpeg()` 探测链（`bin/<平台>` → `thirdparty/ffmpeg/bin` → PATH） | 替换 `bin/` 下的可执行文件即可 |
| `models/` | 第三方预训练权重（`*.pt` 等） | `hudcore.platform.paths.models_dir`、YOLO 相关脚本 | 直接放入新权重文件 |
| `arhud_someip/<平台>-<架构>/` | SOME/IP 服务端运行时库（`libarhud_server.so` + `libsomeip*.so`；Windows 为 `.dll`，暂缺） | `hudcore/someip`（ctypes 加载）、`someip_core` | 见 [`arhud_someip/README.md`](arhud_someip/README.md) |
| `zlg_can/<平台>-<架构>/` | ZLG CAN 驱动库（Linux 为 `libusbcanfd.so` 等，**VCI 接口**；Windows 为仓库根的 `zlgcan.dll`，**ZCAN 接口**） | `hudcore.can`（ctypes 加载）、`can_core` | `python tools/fetch_thirdparty_libs.py zlg`；见 [`zlg_can/README.md`](zlg_can/README.md) |

以上目录（除 `ultralytics/` 在本地为未跟踪内容外）都随仓库分发，路径已统一由
`hudcore.platform.paths` 提供：

```python
from hudcore.platform.paths import paths
paths.thirdparty_dir                  # <项目根>/thirdparty
paths.thirdparty("ffmpeg")            # <项目根>/thirdparty/ffmpeg
paths.thirdparty("ultralytics", "yolo_framework/ultralytics-8.3.217")   # 新位置优先，兼容旧位置
paths.models_dir                      # <项目根>/thirdparty/models
```

`paths.thirdparty(...)` 的第二、三个参数是**旧位置回退**：若旧目录仍在（未完成迁移的
工作副本），会继续使用旧位置，保证过渡期不中断。

---

## 2. 与 `drivers/`、`bin/` 的边界

| 目录 | 定位 | 是否随仓库分发 | 说明 |
|------|------|----------------|------|
| `thirdparty/` | **第三方源码/框架/模型/SDK 资源** | 是 | 本目录，按子目录管理 |
| `drivers/<平台>/` | **历史部署目录**（CAN 驱动 `libzlgcan.so`/`zlgcan.dll` 等；SOME/IP 库已迁至 `thirdparty/arhud_someip/`） | 否（`.gitignore` 忽略） | 现场替换/部署用；仍被探测链兼容，便于老部署平滑过渡 |
| `bin/<平台>/` | **外部可执行文件**（如 `ffmpeg.exe`） | 否（现场放入） | 同上，属部署契约；探测顺序见 `hudcore.platform.executables` |
| `Resources/` | 界面素材（图标、底图） | 是 | 属自研界面资源，不是第三方库 |
| `data/` | 业务数据与运行期状态 | 是 | 与代码分离，见 `docs/STRUCTURE.md` |

判断规则：

- **第三方提供的"代码/框架/模型/SDK 附带资源"** → 放 `thirdparty/<名称>/`
- **第三方运行时库（按平台区分）** → 放 `thirdparty/<组件>/<平台>/`（如 `thirdparty/arhud_someip/linux/`）
- **历史部署目录** → `drivers/<平台>/`、`bin/<平台>/`（仍被探测链兼容）
- **自己写的界面素材/业务数据** → `Resources/`、`data/`

---

## 3. 新增第三方内容时的做法

0. 运行时库优先用 `python tools/fetch_thirdparty_libs.py <名称>` 获取（可复现、可追溯来源）；
1. 在 `thirdparty/` 下新建子目录，目录名用小写英文（如 `thirdparty/onnxruntime/`）；
2. 在上表补一行说明"内容 / 被谁使用 / 更新方式"；
3. 代码中**不要**写死路径，统一用 `paths.thirdparty("<名称>")`（必要时给出旧位置回退）；
4. 若内容很大（>100MB）或含平台二进制，考虑只保留"获取脚本 + 说明"，把实际文件放到
   部署目录或忽略清单中，避免仓库膨胀；
5. 跑一遍自检：`python tools/check_imports.py && python tools/check_static.py && python -m pytest tests -q`。

---

## 4. 迁移记录

| 原位置 | 现位置 |
|--------|--------|
| `yolo_framework/ultralytics-8.3.217/` | `thirdparty/ultralytics/` |
| `PaddleOCR-main/` | `thirdparty/paddleocr/` |
| `kerneldlls/` | `thirdparty/zlg/` |
| `vendor/ffmpeg/` | `thirdparty/ffmpeg/`（`vendor/` 目录已移除） |
| `models/` | `thirdparty/models/` |

同步更新的位置：`hudcore/platform/paths.py`（新增 `thirdparty_dir` / `thirdparty()`）、
`hudcore/platform/executables.py`（ffmpeg 探测链）、`scripts/ocr_icon_test.py`、
`scripts/yolo_train.py`、`tools/check_imports.py`、`tools/check_static.py`、
`tools/rename_modules.py`（台账）、`tests/test_architecture_rules.py`、以及相关文档。
