# Di 测试用例（CAN + SOME/IP + 标贴校验）

> 用例来源：`TestcaseCollection/Di_testcases/TC-*.json`（497 个，随仓库分发）。
> **旧格式解析链路（`gui_handlers/can_testcase_parser.py`）完全不动**，两套格式由
> `can_data_tools.case_format` 的**选择开关**区分。

---

## 1. 用例格式（已按 497 个样例逐字段核对）

```json
{
  "scenario_id": "TC-ACC-ACTIVE-HIGHSPEED",
  "description": "……（人读的判据说明，常引用 HUD 源码位置）",
  "input_combination": {
    "can": [
      {"signal_id": "0x23A", "sub_id": "", "bit_range": "1.0-1.7",
       "value": 240, "desc": "ACC_Cruise_Speed_Value_23A_S: …"}
    ],
    "someip": [
      {"key": "hnmap_s.navigation_map", "value": 1},                      // ① 字段型
      {"service_id": "0x010A", "instance_id": "0x01", "online": 1,        // ② 链路型
       "desc": "navigation ETH channel online"}
    ],
    "mem": [
      {"field": "dataValue.arEnginData.arNavData_s.navigating_status",    // ③ 内部状态量
       "value": 2, "desc": "navigation actively guiding"}
    ]
  },
  "expected_output": {
    "primary_label": "ACC",        // 期望显示的标贴；为空表示"应不显示"
    "negative_label": "",          // 不应显示的标贴（负向）
    "location_constraint": "540,259",
    "min_confidence": 0.9
  },
  "wait_ms": 100
}
```

### 1.1 实测分布（497 个用例）

| 项 | 数量 | 说明 |
|----|------|------|
| `can` 条目 | 1771（每例 0~11 条） | 其中 **415 条没有 `bit_range`**（只写"该报文在线/门控有效"） |
| `someip` 字段型 | 73 | 6 种键：`hrinfo_s.navigating_status`(38)、`hnmap_s.navigation_map`(11)、`hrinfo_s.distance_2_intersection`(9)、`hrinfo_s.next_road_name`(8)、`PlanningLinePointCount`(6)、`hrinfo_s.eta_info_remain_time`(1) |
| `someip` 链路型 | 92 | 只涉及 `0x010A:0x01`（on 65 / off 5）与 `0x000C:0x000C`（on 17 / off 5） |
| `mem` 条目 | 482（约一半用例） | HUD **内部**状态量，外部无法注入 |
| 期望显示标贴 | 312 | `primary_label` 非空 |
| 期望隐藏 | 185 | `primary_label` 为空（负向用例） |
| 标签种类 | 149（含负向去 `NO_` 前缀） | |
| `location_constraint` | `x,y` 379 / 线段 7 / 折线 1 / 空 100 | 空＝不约束位置 |
| `min_confidence` | 0.9 (464) / 0.85 (28) / 0.0 (5) | |
| `wait_ms` | 100 (468) / 120 (27) / 150 / 500 | |

### 1.2 两个必须注意的约定

1. **字节号是 0 起**（与项目既有 `can_core.bit_utils` 的 1 起**不同**）：
   `"0.0"` → `data[0]`，`"1.0-1.7"` → `data[1]`，最大到 `"46.0-46.7"` → `data[46]`
   （即 64 字节 CANFD 帧）。判定依据：样例里 `"0.0"`（139 次，多为 ONLINE/门控信号）与
   `"1.0-1.7"` 同时出现，且最大字节号 46 —— 只有"0 起 + CANFD"能自洽。
   → 实现见 `can_data_tools/can_bit_writer.py`（`base=0` 为 Di，`base=1` 兼容旧链路，两者可换算）。
2. **`sub_id`** 是台架/诊断用的子标识（`0x0E` / `0x01` / `0xC1` / `0xFF`），
   编码不依赖它；有 1 个样例把位域误写进 `sub_id`，解析器会自动纠正。

---

## 2. 选择开关（旧链路保持不变）

| 开关值 | 用例形态 | 解析实现 | 默认 |
|--------|----------|----------|------|
| `legacy` | 平台导出的中文键 JSON（`*用例编号`/`rows`/`测试脚本`） | `gui_handlers/can_testcase_parser.py`（**未修改**） | ✅ |
| `di` | 本文档的 Di JSON | `can_data_tools/di_case_parser.py` + `di_case_runner.py` | |
| `auto` | 按文件内容识别 | `case_format.detect_format_file()` | |

三种设置方式（优先级从高到低）：

```python
from can_data_tools import case_format
case_format.set_format("di")        # 1) 进程内（GUI 开关用它）
```
```bash
export HUD_TESTCASE_FORMAT=di       # 2) 环境变量
python main.py                      #    3) 不设置 → 默认 legacy
```

GUI：主界面 **[Di 测试用例]** 按钮 → 顶部单选开关（旧格式 / Di 格式 / 自动识别）。
命令行：`python -m scripts.run_di_cases --format di`。

---

## 3. 怎么跑

```bash
# ① 体检用例集（默认，不碰设备）：解析 + 分类 + 合成帧，输出支持度与不可下发项
python -m scripts.run_di_cases
python -m scripts.run_di_cases --summary-only --report logs/di_run.json

# ② 只跑可全自动的用例 / 指定场景 / 限条数
python -m scripts.run_di_cases --auto-only
python -m scripts.run_di_cases --only TC-ACC --limit 20

# ③ 真执行（需连接 CAN 设备；脚本自行初始化与关闭）
python -m scripts.run_di_cases --execute --chan 0 --msg-type canfd

# ④ 带 SOME/IP（链路型=服务注册；字段型=结构化发送；会打开 vsomeip 服务端）
python -m scripts.run_di_cases --execute --someip

# ⑤ 标贴校验：用离线画面或相机
python -m scripts.run_di_cases --execute --frame output_ocr/hud.png --only TC-ACC
python -m scripts.run_di_cases --execute --camera --camera-index 0
```

每次运行都会打印小结并（可选）导出 JSON 报告：逐条含**下发内容、不可下发项、画面校验结论**。

---

## 4. 三类输入的支持程度（诚实说明）

| 输入 | 支持 | 做法 / 现状 |
|------|------|-------------|
| `can`（有位域） | ✅ 完整 | 按 `bit_range`+`value` 合成整帧（同报文多信号合并），经 `can_core.device` 下发（CAN/CANFD 可选） |
| `can`（**无位域**，415 条） | ⚠️ 需补配置 | 只写"门控有效"无法定位到具体位 → 记为**不可编码**；若已从 CAN 矩阵确认，写进 `data/DI_Config/gate_frame.json`（按报文给默认位）即可套用 |
| `someip` 链路型 | ✅ 完整（old 代） | `0x010A`/`0x000C` 都在 old 代服务表内：`online=1` 注册该服务、`online=0` 不注册（`ReplayController.register(selected_services=…)`）。**已按服务表代校验**：切到 `bplus` 代时，`0x000C` 会被明确报成"不在当前服务表中"，`0x010A` 会报"该代暂不可注册"（见 `someip_field_map.service_generation()`） |
| `someip` 字段型 | ⚠️ 部分（两代通用） | `hnmap_s.*` → `HudNavmap`（可结构化发送，如 `navigation_map` → `Navigation_map`，`0x010A:0x8003` 两代都有）；`hrinfo_s.*` 与 `PlanningLinePointCount` 属 **Opaque 原始载荷**，库未提供结构体布局 → 不可下发（原因写在 `FieldTarget.reason` 里，并带 `table`/`registrable` 两个字段说明依据哪一代、该代能否注册） |
| `mem` | ❌ 需台架 | HUD 内部状态量，外部接口没有对应通道；执行器如实记为"需台架注入" |
| `expected_output` 标贴 | ⚠️ 受参考图限制 | 见下节 |

执行结论取值：`pass`（下发完成且画面校验通过）、`fail`（画面校验不通过）、
`inputs-ok`（下发完成但画面无法校验）、`skipped`（无任何可下发输入）、
`error`（执行出错）、`dry-run`（仅体检）。

---

## 5. 标贴（标签）校验

- 参考图与位置来自 `data/UI_Config/ui_config_SQ.json`（23 项，图片在 `Resources/ImageUI/SQ/`），
  比对用 `image_testing.image_similarity` 的 dHash（阈值 = `min_confidence × 100`，
  如 0.9 → 90%，dHash 64 位）。
- Di 标签（英文）→ 参考图的映射在 `data/DI_Config/label_map.json`（当前 33 条），
  例如 `ACC`/`ICC`/`SPEEDLIMIT`/`BSD_L`/`BSD_BOTH`/`GEAR_R`/`km/h`/`BORDER`…
- **当前覆盖：149 个标签中 25 个可校验**，其余 124 个仓库内暂无参考图
  （多为 `TRAFFICLIGHT`、`NEXT_ROAD_*`、`AR_*`、数值类如 `60`/`80`/`120`）。
  这些一律记为 `no_reference` → 用例结论为 `inputs-ok`（**不会**被当成通过）。
- 补充参考图后，只要在 `label_map.json` 里加一行映射即可参与校验。

---

## 6. 目录与模块

```
TestcaseCollection/Di_testcases/     497 个 Di 用例（随仓库分发）
data/DI_Config/label_map.json        标签 → 参考图映射
data/DI_Config/gate_frame.json       门控默认位（默认空）
can_data_tools/case_format.py        选择开关（legacy / di / auto）
can_data_tools/di_case_parser.py     解析 + 分类（纯函数，无副作用）
can_data_tools/can_bit_writer.py     位域写入（base=0/1）
can_data_tools/someip_field_map.py   字段型键 → 回放库结构体
can_data_tools/di_case_runner.py     执行器（依赖全部可注入）
can_data_tools/label_verify.py       标贴校验
scripts/run_di_cases.py              命令行入口（--someip-table old|bplus、--show-someip）
scripts/someip_replay_check.py       SOME/IP 回放一键自检（库→配置→服务表→注册→发送→回放）
gui_handlers/di_case_window.py       GUI 窗口（含格式开关）
docker/…                             （无）
tests/test_di_cases.py               33 项单测（解析/位写入/执行/校验/开关）
```

---

## 7. 已验证 / 未验证

**已验证（离线，可重复）**
- 497 个用例全部解析成功；统计与本文档 1.1 节一致（单测断言）。
- 位写入与项目既有 `extract_bits_from_data()` **读写互逆**（base=1）；Di 的 base=0
  与 base=1 可按 `n+1` 换算（单测断言）。
- 执行器用假发送器跑通：合成的整帧字节正确（如 0x23A 字节 1 = 240）、
  SOME/IP 链路与字段调用正确、mem/无位域项如实列入"不可下发"。
- 标贴校验用合成画面跑通：命中、负向命中（判 fail）、无参考图（`unverifiable`）、
  无画面（`error`）。
- 格式开关：默认 `legacy`、环境变量覆盖、非法值回退、按内容识别（单测断言）。
- SOME/IP 服务表代际：old/bplus 两代规模、切换开关、随仓库配置与代码表**逐条一致**、
  Di 用例在 bplus 代下对 `0x000C` 的缺失判定（`tests/test_someip_tables.py` 17 项）。

**未验证（需现场）**
- 真实 CAN 总线上的字段/字节序是否被 HUD 按预期解析（取决于 Di 用例作者的编码假设）。
- 相机画面与参考图坐标系是否一致（参考背景 725×247；画面尺寸不一致时会提示）。
- SOME/IP 字段型中 `hrinfo_s.*` / `PlanningLinePointCount` 的真实载荷布局（需 HUD 侧结构体定义）。
