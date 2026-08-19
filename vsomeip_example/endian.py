#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端序（字节序）工具：机器大/小端识别 + 网络字节序（大端）编解码
================================================================
为什么需要关注字节序？
  - SOME/IP 报文头（Message ID / Length / Request ID / 版本 / 类型 / 返回码）按 AUTOSAR
    规范使用【网络字节序 = 大端】；
  - ArHud 数据结构（NewLaneLineDataNotify 等）序列化同样采用大端（与 C++ 端约定一致）。

自动适配（关键）：
  Python 的 struct 用显式前缀 '>'（大端）/ '<'（小端）时，转换由 struct 内部完成，
  【与主机端序完全无关】——同样的代码在小端(x86/ARM)和大端(s390x)主机上产生完全相同的字节。
  因此本项目所有序列化/反序列化都写死 '>'，不需要任何"判断主机端序再分支"的逻辑。
  本模块的 detect_endian() 仅用于诊断/自测（例如确认代码运行在什么端序的主机上）。

用法：
    from endian import detect_endian, is_big_endian, pack_u32, unpack_u32, self_test
    self_test()          # 任意主机上验证：大端字节与主机端序无关
"""

import struct
import sys


# ---------- 机器端序识别 ----------

def detect_endian() -> str:
    """返回本机端序：'little' 或 'big'（Python 标准做法，跨平台）"""
    return sys.byteorder


def is_big_endian() -> bool:
    return sys.byteorder == "big"


def is_little_endian() -> bool:
    return sys.byteorder == "little"


def manual_detect_endian() -> str:
    """不依赖 sys.byteorder 的识别方法（演示用）：
    整数 0x0102 写入 2 字节，看第一个字节是高字节(0x01)还是低字节(0x02)"""
    raw = (0x0102).to_bytes(2, "little")   # 显式按小端写出，看它怎么存
    return "little" if raw == b"\x02\x01" else "big"


# ---------- 网络字节序（大端）编解码 ----------
# 显式 '>' 前缀：无论主机端序如何，都按大端编解码（自动适配）

def pack_u16(v: int) -> bytes:
    return struct.pack(">H", v & 0xFFFF)


def pack_u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


def pack_u64(v: int) -> bytes:
    return struct.pack(">Q", v & 0xFFFFFFFFFFFFFFFF)


def unpack_u16(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def unpack_u32(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def unpack_u64(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from(">Q", data, offset)[0]


def swap_bytes(data: bytes) -> bytes:
    """整块字节反转（小端 ↔ 大端 原始字节互换），仅作参考"""
    return data[::-1]


# ---------- 自测：验证大端字节与主机端序无关 ----------

def self_test() -> str:
    """在任何端序的主机上，大端编码的固定字节必须完全一致"""
    # 整数
    assert pack_u16(0x0102) == b"\x01\x02", "u16 大端错误"
    assert pack_u32(0x01020304) == b"\x01\x02\x03\x04", "u32 大端错误"
    assert pack_u64(0x0102030405060708) == bytes(range(1, 9)), "u64 大端错误"
    # 浮点（IEEE754 大端表示）
    assert pack_u32(0x3F800000) == b"\x3F\x80\x00\x00", "1.0 的位模式"
    assert struct.pack(">f", 1.0) == b"\x3F\x80\x00\x00", ">f 1.0 大端错误"
    assert struct.pack(">f", 0.5) == b"\x3F\x00\x00\x00", ">f 0.5 大端错误"
    # 往返
    for v in (0x0000, 0x7FFF, 0x8000, 0xFFFF, 0xDEADBEEF):
        assert unpack_u32(pack_u32(v)) == v, f"u32 往返失败: {v:#x}"
    msg = (f"机器端序: {detect_endian()} ({manual_detect_endian()}), "
           f"大端(网络序)编解码自测通过 ✓ 字节与主机端序无关")
    return msg


if __name__ == "__main__":
    print(self_test())
    print("示例: 0x01020304 大端字节 =", pack_u32(0x01020304).hex().upper())
