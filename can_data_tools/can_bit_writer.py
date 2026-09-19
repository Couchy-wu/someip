# -*- coding: utf-8 -*-
"""can_data_tools.can_bit_writer —— 按位域写 CAN/CANFD 数据（`extract_bits_from_data` 的逆运算）

Di 用例给出的是「报文 ID + 位域 + 值」，需要还原成数据再下发；项目原有的
`can_core.bit_utils.extract_bits_from_data()` 只做"读"，本模块补"写"。

⚠️ **字节号基准（重要）**：两套用例的约定不同，本模块用参数区分，不要混用：

| 来源 | 写法 | 基准 | 说明 |
|------|------|------|------|
| 项目 `can_core.bit_utils`（旧链路） | `"1.0-1.7"` → `data[0]` | `base=1` | 1 起，`1.0`~`64.7` |
| **Di 用例**（`TestcaseCollection/Di_testcases`） | `"0.0"` → `data[0]`；`"46.0-46.7"` → `data[46]` | `base=0` | 0 起，`0.0`~`63.7`（64 字节 CANFD） |

判定依据（对 497 个样例实测）：Di 用例里同时出现 `"0.0"`（139 次，多为 ONLINE/门控类信号）
与 `"1.0-1.7"`，且最大字节号 46 —— 只有"0 起 + CANFD 64 字节"能自洽；
而旧链路（平台导出的中文键用例）一直是 1 起（`bit_utils` 的实现即为其定义）。

位序（两套一致）：值按 **LSB 优先** 落位 —— 值的 bit0 放在起始位，向高位/下一字节推进。

自校验（单元测试断言）：
  · `base=1` 时与 `extract_bits_from_data()` 读写互逆；
  · `base=0` 时 Di 用例的全部位域都能写入并读回。
"""
from __future__ import annotations

from typing import Iterable, List, Sequence

from hudcore import logging_setup

LOGGER_NAME = "di_case"

DI_BASE = 0                 # Di 用例：字节号 0 起
LEGACY_BASE = 1             # 旧链路（bit_utils）：字节号 1 起
MAX_CANFD_BYTES = 64


class BitRangeError(ValueError):
    """位域写法非法（不是 `byte.bit` 或 `byte.bit-byte.bit`，或超出行长范围）。"""


def parse_bit_range(bit_range: str, base: int = DI_BASE) -> tuple[int, int, int, int]:
    """解析位域 → `(起始字节下标, 起始位, 结束字节下标, 结束位)`（下标即 `data[]` 索引）。

    :param base: 0 表示位域里的字节号即下标；1 表示字节号 1 起（会减 1）
    """
    if base not in (0, 1):
        raise BitRangeError(f"base 只能是 0 或 1，实际 {base}")
    text = str(bit_range or "").strip()
    if not text:
        raise BitRangeError("位域为空")
    if "-" in text:
        start_part, _, end_part = text.partition("-")
    else:
        start_part = end_part = text
    try:
        start_byte, start_bit = (int(x) for x in start_part.strip().split("."))
        end_byte, end_bit = (int(x) for x in end_part.strip().split("."))
    except ValueError as exc:
        raise BitRangeError(f"位域写法非法：{bit_range!r}") from exc

    if base == 1:
        start_byte -= 1
        end_byte -= 1
    for idx in (start_byte, end_byte):
        if not (0 <= idx < MAX_CANFD_BYTES):
            raise BitRangeError(
                f"位域超范围（base={base}，允许 0~{MAX_CANFD_BYTES - 1} 字节）：{bit_range!r}")
    if not (0 <= start_bit <= 7 and 0 <= end_bit <= 7):
        raise BitRangeError(f"位号超范围（0~7）：{bit_range!r}")
    if (end_byte, end_bit) < (start_byte, start_bit):
        raise BitRangeError(f"位域起止顺序颠倒：{bit_range!r}")
    return start_byte, start_bit, end_byte, end_bit


def bit_length(bit_range: str, base: int = DI_BASE) -> int:
    """位域包含的位数。"""
    sb, sbit, eb, ebit = parse_bit_range(bit_range, base)
    if sb == eb:
        return ebit - sbit + 1
    return (8 - sbit) + 8 * (eb - sb - 1) + (ebit + 1)


def set_bits_in_data(data: List[int], bit_range: str, value: int, base: int = DI_BASE) -> List[int]:
    """把 `value` 写入 `data`（就地修改并返回）。

    :raises BitRangeError: 位域非法
    :raises ValueError: 值为负 / 超出位域可表示范围 / 数据长度不足
    """
    sb, sbit, eb, ebit = parse_bit_range(bit_range, base)
    width = bit_length(bit_range, base)
    value = int(value)
    if value < 0:
        raise ValueError(f"值为负数，无法写入位域 {bit_range}：{value}")
    if width < 64 and value >= (1 << width):
        raise ValueError(f"值 {value} 超出位域 {bit_range} 的 {width} 位范围（<{1 << width}）")
    if len(data) <= eb:
        raise ValueError(f"数据长度不足：需要 {eb + 1} 字节，实际 {len(data)}")

    byte_idx, bit_idx, remaining = sb, sbit, value
    while True:
        if byte_idx > eb or (byte_idx == eb and bit_idx > ebit):
            break
        if remaining & 1:
            data[byte_idx] |= (1 << bit_idx)
        else:
            data[byte_idx] &= ~(1 << bit_idx) & 0xFF
        remaining >>= 1
        bit_idx += 1
        if bit_idx > 7:
            byte_idx += 1
            bit_idx = 0
    return data


def frame_length(signals: Iterable, minimum: int = 8, base: int = DI_BASE) -> int:
    """按信号推出的数据长度（不超过 64 字节，小于 `minimum` 时取 `minimum`）。"""
    need = minimum
    for sig in signals:
        if not getattr(sig, "bit_range", None):
            continue
        _sb, _s, eb, _e = parse_bit_range(sig.bit_range, base)
        need = max(need, eb + 1)
    return max(1, min(MAX_CANFD_BYTES, need))


def build_frame(signals: Iterable, length: int | None = None, base: int = DI_BASE,
                gate_defaults: dict | None = None) -> List[int]:
    """把一组 CAN 信号合成为一帧数据。

    :param signals: 同一报文 ID 下的信号（`di_case_parser.CanSignal`）
    :param length: 帧长度；None 时按信号所需长度（≥8）
    :param gate_defaults: 门控位默认值 `{位域: 值}`，用于样例只写了"门控信号有效"却没给位域的
                          报文（见 `data/DI_Config/gate_frame.json`）
    """
    items = list(signals)
    size = frame_length(items, base=base) if length is None \
        else max(1, min(MAX_CANFD_BYTES, int(length)))
    data = [0] * size
    for bit_range, value in (gate_defaults or {}).items():
        try:
            set_bits_in_data(data, bit_range, value, base=base)
        except (BitRangeError, ValueError) as exc:
            logging_setup.warning(LOGGER_NAME, f"门控默认位域跳过（{bit_range}={value}）：{exc}")
    for sig in items:
        if not getattr(sig, "bit_range", None):
            continue                                   # 无位域：仅表示"该报文在线/门控有效"
        set_bits_in_data(data, sig.bit_range, sig.value, base=base)
    return data


def group_by_can_id(signals: Sequence) -> dict[int, list]:
    """按 CAN ID 归组（同一报文的多个信号必须合成一帧下发）。"""
    grouped: dict[int, list] = {}
    for sig in signals:
        grouped.setdefault(sig.can_id, []).append(sig)
    return grouped


__all__ = ["parse_bit_range", "bit_length", "set_bits_in_data", "build_frame",
           "frame_length", "group_by_can_id", "BitRangeError",
           "DI_BASE", "LEGACY_BASE", "MAX_CANFD_BYTES"]
