# 项目结构说明（改造后）

本文说明 HudAutoTest 当前的目录/文件/模块划分、各层职责与依赖方向，
以及"为什么这样划分"。它是 P0→P1→P2 三级结构整改的结果，
配套的**架构规则守卫**在 [`tests/test_architecture_rules.py`](../tests/test_architecture_rules.py)，
运行 `python -m pytest tests -q` 即可校验本文所述的约定是否被破坏。

---

## 1. 总览

```
HudAutoTest/
├── main.py                    唯一入口（GUI 主窗口）
├── hudcore/                   ★ 基础设施层（平台抽象 + 横切能力，零反向依赖）
│   ├── platform/              OS 探测、统一路径、外部程序探测、字体
│   ├── can/                   CAN 驱动库探测与加载（DLL / .so）
│   ├── logging_setup.py       统一日志初始化
│   └── ui/                    主题样式、按钮状态机、声明式布局、stdout→Text 重定向
├── can_core/                  ★ CAN 设备能力层
│   ├── driver.py              ZLG 驱动 Python 绑定（结构体/常量/库加载）
│   ├── can_state.py           共享状态单例（线程开关/接收缓存/锁/驱动实例/句柄）
│   ├── bit_utils.py           位与字节工具（纯函数）
│   ├── receive.py             设备与通道建立、接收线程、信号等待
│   ├── transmit.py            单帧/信号级/周期发送
│   └── device.py              公共门面（聚合导出，保持 device.XXX 调用方式）
├── 业务包（无界面依赖）
│   ├── can_data_tools/        用例日志解析、信号矩阵检索与生成
│   ├── image_testing/         图标测试（相似度、图标库、测试图生成）
│   ├── camera_tools/          相机预览、透视标定、图像增强、稳定性测试
│   ├── misc_tools/            小工具（GIF、批量改名、图片转视频、ROI）
│   └── auto_labeling/         自动标注（预处理 + template_matching 子包）
├── 界面包（依赖业务包与 hudcore）
│   ├── gui_handlers/          主界面各功能事件处理器
│   └── can_gui/               CAN 收发界面（布局与按钮状态 / 相机图像 / 测试流程 / 配置 四个 Mixin）
├── scripts/                   面向使用者的独立脚本（OCR 图标测试、YOLO 训练）
├── data/                      ★ 业务数据与运行期状态（与代码分离）
├── tests/                     ★ 单元测试 + 架构规则守卫
├── tools/                     自检与重构工具（见 §4）
├── docker/windows-sim/        Windows 环境验证工程（Wine + Windows CPython）
├── docs/                      文档
├── thirdparty/                ★ 第三方内容（ultralytics / paddleocr / zlg / ffmpeg / models）
├── drivers/  bin/             按平台分发的部署目录（现场替换，不进仓库）
└── Resources/                 界面素材
```

---

## 2. 分层与依赖方向

```
        main.py
           │
   ┌───────┴────────┐
   │  界面包         │   gui_handlers / can_gui
   └───────┬────────┘
           │  可依赖 ↓（禁止反向）
   ┌───────┴─────────────────────────────┐
   │ 业务包                               │   can_data_tools / image_testing /
   │                                     │   camera_tools / misc_tools / auto_labeling
   └───────┬─────────────────────────────┘
           │
   ┌───────┴────────┐
   │  can_core      │   CAN 设备能力（驱动绑定、共享状态、收发）
   └───────┬────────┘
           │
   ┌───────┴────────┐
   │  hudcore       │   平台抽象与横切能力（**不依赖任何上层**）
   └────────────────┘
```

规则（由架构守卫测试强制）：

1. **`hudcore` 不反向依赖任何上层** —— 它是可复用的基础设施，必须保持在最底层；
2. 业务包**不导入界面包**；界面包负责"事件 → 业务动作"的编排；
3. 跨模块共享的可变状态集中到 `can_core.can_state.state` 单例，
   禁止各模块各持一份全局变量（会造成"改了 A 模块、B 模块读旧值"的状态分裂）。

---

## 3. 关键设计约定

| 约定 | 原因 / 反例 |
|------|-------------|
| 根目录只放 `main.py`；独立脚本放 `scripts/` | 避免"根目录杂货间"：原 `can_control.py`/`zlgcan_driver.py`/`log_setup.py` 等被多个包反向引用的底层模块曾与入口并排放在根目录 |
| 每个包都有 `__init__.py` 并写明职责与依赖约束 | 命名空间包没有 API 边界，重构无保障；`can_core/__init__.py` 另外显式导出公共 API |
| 业务数据与运行期状态放 `data/`（`paths.data_dir`） | 原 `outputMatrix.csv`(6.1MB)、设备配置、标定结果散落在代码包里，且部分路径相对当前工作目录，换目录即失效 |
| 禁止 `import *` | 命名空间污染；曾因通配符导入掩盖了 `c_char_p`/`memset` 等名字缺失 |
| 禁止业务代码 `sys.path.append/insert` | 绕过包结构；拆模块后极易失效（同包模块请用相对导入，脚本用 `python -m 包.模块`） |
| 禁止导入副作用（模块级建 GUI、跑 mainloop、解析命令行、写日志文件、读大文件） | 这些都会让模块无法作为库使用：曾出现 `import` 即阻塞、带参数 `import` 直接退出进程、导入即弹窗等问题 |
| 拆模块后必须跑 `tools/check_static.py` | 容器验证覆盖不到硬件与界面路径，`undefined name` 只能在静态阶段拦住 |
| 大模块按关注点用 Mixin 组合拆分 | 保持对外类名/方法与行为不变，降低回归风险（如 `LogParser`、`CANFDGUI`、`IconManagerApp`） |

---

## 4. 工具与验证入口

| 命令 | 作用 |
|------|------|
| `python tools/check_imports.py` | 项目内部导入静态校验（支持命名空间包） |
| `python tools/check_static.py` | pyflakes 静态检查（undefined name / 重复定义 / 通配符导入） |
| `python -m pytest tests -q` | 单元测试 + 架构规则守卫 |
| `python tools/selftest.py` | hudcore 回归自测（跨平台） |
| `python tools/check_env.py` | 环境自检（依赖/版本/字体/驱动/外部程序） |
| `python tools/rename_modules.py --dry-run` | 查看/执行目录与文件改名映射（含历史台账） |
| `cd docker/windows-sim && ./run_verify.sh` | 容器内 Windows 环境 18 项功能验证 |

> 建议顺序：`check_imports` → `check_static` → `pytest` → `selftest` → 容器验证。

---

## 5. 改造前后对比（量化）

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 根目录 `.py` 文件 | 7（入口 + 4 个共享库模块 + 2 个脚本） | 1（仅 `main.py`） |
| 无 `__init__.py` 的包 | 10 | 0 |
| 业务代码 `sys.path` 注入 | 5 处 | 0 |
| `import *`（自研代码） | 4 处 | 0 |
| 模块级副作用（GUI/mainloop/parse_args） | 7 处 | 0 |
| 单文件最大行数 | 1641 | 679 |
| 业务数据文件位于代码包内 | 7 个（含 6.1MB 矩阵、5.3MB 图片） | 0（统一 `data/`） |
| 第三方内容位置 | 项目根散落 5 处（yolo_framework / PaddleOCR-main / kerneldlls / vendor / models） | 0（统一 `thirdparty/<名称>/`） |
| 自动化测试 | 仅 `tools/selftest.py` | 18 项容器验证 + 18 个 pytest 用例（含架构守卫） |

---

## 6. 仍需持续改进的点

1. ~~`can_gui/can_send_receive_gui.py` 的 `__init__` 仍是 367 行的界面构建方法~~
   **已解决（v2.1 界面优化）**：界面构建拆到 `can_gui/gui_layout.py`（`LayoutMixin`），
   主类缩到 70 行的"组装 + 起线程"；按钮可用性收敛为 `UiState` + `RULES` 规则表，
   并补了 headless 交互测试（`tests/test_ui_layout.py`、`tests/test_can_gui_layout.py`：
   零格子冲突 + 状态流转）。**控件摆放按用户要求保持改造前的原样**，只把原实现里
   三处互相盖住的控件挪到空闲格（`平台`/`曝光值` 两组）。
2. **`auto_labeling/draw_boxes.py` / `draw_boxes_v2.py` 仍是两套独立实现**（747 / 1387 行）——
   二者仅 `ensure_dir` 等少数函数逐字相同，其余逻辑不同，合并需先确认业务口径。
3. **`camera_tools/perspective_calibration.py`(806) / `image_enhancement.py`(632) /
   `gui_handlers/can_testcase_parser.py`(563)** 仍超过 500 行，可按同样方式继续拆分。
4. **界面逻辑的自动化测试** —— v2.1 已补齐"按钮状态机 + 布局零冲突 + 探测链路"三类
   （`tests/test_ui_state.py` / `test_ui_layout.py` / `test_can_gui_layout.py`，
   Tk 在 Xvfb 下驱动）；仍缺真实点击流程（含相机画面）的端到端用例。
5. **`tools/selftest.py` 与 `tests/` 存在功能重叠**，可考虑把前者收敛为后者的一部分。
