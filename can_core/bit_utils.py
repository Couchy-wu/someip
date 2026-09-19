# -*- coding: utf-8 -*-
"""can_core.bit_utils —— CAN 数据的位/字节工具（纯函数，无设备依赖）

从 device.py 拆出：位区间解析与按位取值、位长度计算。
不含 IO 与全局状态，可被算法、测试与工具脚本直接复用。
"""
import re
from typing import List, Tuple

from hudcore import logging_setup


def extract_bits_from_data(data_list: List[int], bit_range: str) -> int:
    """
    从 CAN 数据中提取指定范围的位（支持跨字节）
    注意：位表示法中，"1.0-1.7" 对应 data[0]，"2.0-2.7" 对应 data[1]，以此类推
    """
    try:
        bit_range = bit_range.strip()
        if '-' in bit_range:
            start_part, end_part = bit_range.split('-')
        else:
            start_part = end_part = bit_range

        # 解析 byte.bit，注意：1.0 表示第1字节bit0 → data[0]
        start_byte_idx, start_bit = map(int, start_part.split('.'))
        end_byte_idx, end_bit = map(int, end_part.split('.'))

        # 转换为 data 索引：第 n 字节 → data[n-1]
        start_data_index = start_byte_idx - 1
        end_data_index = end_byte_idx - 1

        # 检查数据长度
        max_data_index = max(start_data_index, end_data_index)
        if max_data_index >= len(data_list):
            logging_setup.warning("bit_parse", f"数据长度不足，无法访问 data[{max_data_index}]")
            return -1

        value = 0
        current_pos = 0

        byte_idx = start_data_index
        bit_idx = start_bit

        while byte_idx <= end_data_index:
            if byte_idx == end_data_index and bit_idx > end_bit:
                break
            if byte_idx == start_data_index and bit_idx < start_bit:
                bit_idx += 1
                continue

            if data_list[byte_idx] & (1 << bit_idx):
                value |= (1 << current_pos)

            current_pos += 1
            bit_idx += 1
            if bit_idx > 7:
                byte_idx += 1
                bit_idx = 0
                if byte_idx > end_data_index:
                    break

        return value

    except Exception as e:
        logging_setup.error("bit_parse", f"解析位范围失败: {bit_range}, 错误: {e}")
        return -1


def calculate_bit_length(bit_range: str) -> int:
    """计算位范围长度"""
    try:
        bit_range = bit_range.strip()
        if '-' in bit_range:
            start_part, end_part = bit_range.split('-')
        else:
            start_part = end_part = bit_range

        start_byte, start_bit = map(int, start_part.split('.'))
        end_byte, end_bit = map(int, end_part.split('.'))

        if start_byte == end_byte:
            length = end_bit - start_bit + 1
        else:
            start_remaining = 8 - start_bit
            middle_full = 8 * (end_byte - start_byte - 1) if end_byte - start_byte > 1 else 0
            end_prefix = end_bit + 1
            length = start_remaining + middle_full + end_prefix

        return max(1, length) if length <= 32 else 32

    except Exception as e:
        logging_setup.error("bit_parse", f"计算位长度失败: {bit_range}, 错误: {e}")
        return -1

