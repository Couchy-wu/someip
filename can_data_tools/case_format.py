# -*- coding: utf-8 -*-
"""can_data_tools.case_format —— 测试用例「格式选择开关」

项目里现在有两套**互不影响**的用例格式与解析链路：

| 开关值   | 用例形态                                   | 解析实现                                       | 状态 |
|----------|--------------------------------------------|------------------------------------------------|------|
| `legacy` | 平台导出的中文键 JSON（`*用例编号`/`rows`/`测试脚本`…） | `gui_handlers/can_testcase_parser.py`（**保持原样**） | 默认 |
| `di`     | Di 用例 JSON（`scenario_id`/`input_combination`/`expected_output`） | `can_data_tools/di_case_parser.py` + `di_case_runner.py` | 新增 |

选择优先级：`set_format()`（GUI 开关/进程内） → 环境变量 `HUD_TESTCASE_FORMAT` → 默认 `legacy`。
**默认必须是 legacy**：老用户的用法与既有自动化不受影响，Di 链路要显式开启。

顺带提供 `detect_format_file()`：不确定某文件属于哪套格式时，按内容特征判断（GUI 里
"自动识别"选项与命令行 `--format auto` 都用它）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from hudcore import logging_setup

LOGGER_NAME = "di_case"

LEGACY = "legacy"
DI = "di"
AUTO = "auto"
ENV_VAR = "HUD_TESTCASE_FORMAT"

_FORMATS: dict[str, str] = {
    LEGACY: "旧格式（平台导出的中文键 JSON，走 gui_handlers/can_testcase_parser.py）",
    DI: "Di 格式（scenario_id/input_combination/expected_output，走 can_data_tools/di_case_*）",
    AUTO: "按文件内容自动识别",
}

# 进程内覆盖（GUI 开关用；None 表示跟随环境变量/默认值）
_active: str | None = None


def available_formats() -> dict[str, str]:
    """{开关值: 说明}（GUI 下拉/单选按钮直接用）。"""
    return dict(_FORMATS)


def normalize(name: str | None) -> str:
    """把任意写法归一到开关值（大小写不敏感，非法值回退默认）。"""
    text = str(name or "").strip().lower()
    if text in (DI, "di_case", "di_testcases"):
        return DI
    if text in (LEGACY, "old", "chinese", "legacy_json"):
        return LEGACY
    if text == AUTO:
        return AUTO
    return LEGACY


def default_format() -> str:
    """默认开关值（常量，便于文档与测试引用）。"""
    return LEGACY


def active_format() -> str:
    """当前生效的格式（进程内覆盖 → 环境变量 → 默认）。"""
    if _active is not None:
        return _active
    env = os.environ.get(ENV_VAR)
    if env:
        return normalize(env)
    return default_format()


def set_format(name: str | None) -> str:
    """设置进程内开关；传 None 恢复为"跟随环境变量/默认"。返回设置后的值。"""
    global _active
    _active = None if name is None else normalize(name)
    value = active_format()
    logging_setup.info(LOGGER_NAME, f"用例格式开关 → {value}（{_FORMATS.get(value, '')}）")
    return value


def is_di() -> bool:
    """当前是否走 Di 链路（业务代码用它做分支）。"""
    return active_format() == DI


def detect_format_file(path: Path | str) -> str:
    """按内容判断单个文件属于哪套格式；判不出来时返回 legacy（保守）。"""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging_setup.warning(LOGGER_NAME, f"无法判断用例格式：{p}（{exc}）")
        return LEGACY
    return detect_format_obj(data)


def detect_format_obj(data) -> str:
    """按已解析的 JSON 对象判断格式。"""
    if isinstance(data, dict):
        if "scenario_id" in data and "input_combination" in data:
            return DI
        if "cases" in data or "rows" in data:
            return LEGACY
        # 中文键特征（旧平台导出）
        for key in data:
            if str(key).startswith("*") or "用例" in str(key):
                return LEGACY
        case = data.get("test_case") or {}
        if isinstance(case, dict) and "rows" in case:
            return LEGACY
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return detect_format_obj(data[0])
    return LEGACY


def resolve_format(requested: str | None, path: Path | str | None = None) -> str:
    """把"请求的开关值"解析成具体格式（`auto` 时按文件判断）。"""
    value = normalize(requested) if requested else active_format()
    if value == AUTO:
        return detect_format_file(path) if path else LEGACY
    return value


def describe() -> str:
    """一句话描述当前开关状态（自检/日志用）。"""
    current = active_format()
    source = "进程内设置" if _active is not None else (
        f"环境变量 {ENV_VAR}" if os.environ.get(ENV_VAR) else "默认值")
    return f"用例格式 = {current}（来源：{source}）；可选：{', '.join(_FORMATS)}"


__all__ = ["LEGACY", "DI", "AUTO", "ENV_VAR", "available_formats", "active_format",
           "set_format", "is_di", "detect_format_file", "detect_format_obj",
           "resolve_format", "normalize", "default_format", "describe"]
