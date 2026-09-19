# -*- coding: utf-8 -*-
"""can_data_tools —— CAN 数据与测试用例的解析、检索、生成（非界面逻辑）

可用测试用例矩阵做信号级编解码；不依赖任何 gui 包。

依赖约束：上层（gui_handlers / can_gui / main）可依赖本包；
          本包不反向依赖界面层（保持可测试、可复用）。
说明：本文件只声明包边界与职责，不在导入时引入重依赖（无副作用）。
"""

# 新增模块（Di 用例链路；旧链路 gui_handlers/can_testcase_parser.py 保持不变）
#   case_format        用例格式开关（legacy / di / auto）
#   di_case_parser     Di 用例 JSON 解析与分类
#   di_case_runner     Di 用例执行（CAN / SOME/IP / 画面校验，依赖可注入）
#   can_bit_writer     按位域写 CAN 数据（extract_bits_from_data 的逆运算）
#   label_verify       标贴（标签）校验：参考图 dHash 比对
#   someip_field_map   Di 的 SOME/IP 字段键 → 回放库结构体映射
from . import (  # noqa: F401
    can_bit_writer, case_format, di_case_parser, di_case_runner,
    label_verify, someip_field_map,
)

__all__ = ["case_format", "di_case_parser", "di_case_runner",
           "can_bit_writer", "label_verify", "someip_field_map"]
