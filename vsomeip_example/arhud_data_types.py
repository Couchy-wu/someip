#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArHud 数据类型定义：序列化 / 反序列化
=====================================
对应 C++ 结构体 stNewLanelineDataNotify（SOME/IP 事件 0x8003 的载荷格式）。

内存布局（大端，与 C++ #pragma pack(1) 一致）：

    NewLaneLineDataNotify:
        version       uint16   2 字节
        timestamp     uint32   4 字节
        lane_count    uint8    1 字节
        lanes[0..n-1]          LaneLineData  × lane_count

    LaneLineData:
        lane_type     uint8    1 字节   (见 LaneLineType)
        lane_id       uint8    1 字节
        quality       float32  4 字节
        confidence    float32  4 字节
        point_count   uint16   2 字节
        points[0..m-1]         LaneLinePoint × point_count

    LaneLinePoint:
        x float32  y float32  z float32   (各 4 字节)

自测：python3 arhud_data_types.py
"""

import struct
from dataclasses import dataclass, field
from typing import List


class LaneLineType:
    SOLID = 0
    DASHED = 1
    DOUBLE = 2
    CURB = 3
    COLORED = 4

    _NAMES = {0: "SOLID", 1: "DASHED", 2: "DOUBLE", 3: "CURB", 4: "COLORED"}

    @staticmethod
    def name(t: int) -> str:
        return LaneLineType._NAMES.get(t, f"UNKNOWN({t})")


@dataclass
class LaneLinePoint:
    """三维点（float32 × 3）"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    SIZE = 12  # 3 * 4 字节

    def to_bytes(self) -> bytes:
        return struct.pack(">fff", self.x, self.y, self.z)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> "LaneLinePoint":
        x, y, z = struct.unpack_from(">fff", data, offset)
        return cls(x, y, z)

    def __str__(self) -> str:
        return f"({self.x:.3f},{self.y:.3f},{self.z:.3f})"


@dataclass
class LaneLineData:
    """一条车道线"""
    lane_type: int = 0
    lane_id: int = 0
    quality: float = 0.0
    confidence: float = 0.0
    points: List[LaneLinePoint] = field(default_factory=list)

    HEADER_SIZE = 12  # BBffH

    def to_bytes(self) -> bytes:
        result = struct.pack(">BBffH", self.lane_type, self.lane_id,
                             self.quality, self.confidence, len(self.points))
        for p in self.points:
            result += p.to_bytes()
        return result

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> "LaneLineData":
        lane_type, lane_id, quality, confidence, point_count = \
            struct.unpack_from(">BBffH", data, offset)
        offset += cls.HEADER_SIZE
        points = [LaneLinePoint.from_bytes(data, offset + i * LaneLinePoint.SIZE)
                  for i in range(point_count)]
        return cls(lane_type, lane_id, quality, confidence, points)

    @property
    def size(self) -> int:
        return self.HEADER_SIZE + len(self.points) * LaneLinePoint.SIZE

    def __str__(self) -> str:
        pts = ", ".join(str(p) for p in self.points[:4])
        if len(self.points) > 4:
            pts += f" ... (共{len(self.points)}点)"
        return (f"Lane[{self.lane_id}] type={LaneLineType.name(self.lane_type)} "
                f"quality={self.quality:.3f} confidence={self.confidence:.3f} "
                f"points=[{pts}]")


@dataclass
class NewLaneLineDataNotify:
    """事件 0x8003 NewLaneLineDataNotify 的完整载荷"""
    version: int = 1
    timestamp: int = 0
    lane_count: int = 0
    lanes: List[LaneLineData] = field(default_factory=list)

    HEADER_SIZE = 7  # HIB

    def to_bytes(self) -> bytes:
        """序列化：数据对象 -> 字节（即 SOME/IP 事件载荷）"""
        result = struct.pack(">HIB", self.version, self.timestamp, len(self.lanes))
        for lane in self.lanes:
            result += lane.to_bytes()
        return result

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> "NewLaneLineDataNotify":
        """反序列化：字节（SOME/IP 事件载荷）-> 数据对象"""
        version, timestamp, lane_count = struct.unpack_from(">HIB", data, offset)
        offset += cls.HEADER_SIZE
        lanes = []
        for _ in range(lane_count):
            lane = LaneLineData.from_bytes(data, offset)
            offset += lane.size
            lanes.append(lane)
        return cls(version, timestamp, lane_count, lanes)

    @property
    def size(self) -> int:
        return self.HEADER_SIZE + sum(l.size for l in self.lanes)

    def __str__(self) -> str:
        lanes = "\n    ".join(str(l) for l in self.lanes)
        return (f"NewLaneLineDataNotify(version={self.version}, "
                f"timestamp=0x{self.timestamp:08X}, lane_count={len(self.lanes)})\n"
                f"    {lanes}")


def make_sample_notify() -> NewLaneLineDataNotify:
    """构造一份示例数据（没有 pcap 文件时用于演示完整链路）"""
    return NewLaneLineDataNotify(
        version=1,
        timestamp=0x11223344,
        lane_count=2,
        lanes=[
            LaneLineData(
                lane_type=LaneLineType.SOLID, lane_id=1,
                quality=0.95, confidence=0.98,
                points=[LaneLinePoint(0.0, 0.0, 0.0),
                        LaneLinePoint(1.0, 2.0, 0.0),
                        LaneLinePoint(2.0, 4.0, 0.0)],
            ),
            LaneLineData(
                lane_type=LaneLineType.DASHED, lane_id=2,
                quality=0.88, confidence=0.91,
                points=[LaneLinePoint(0.0, 3.5, 0.0),
                        LaneLinePoint(1.0, 5.5, 0.0)],
            ),
        ],
    )


if __name__ == "__main__":
    # 自测：序列化 -> 反序列化 往返一致性
    n = make_sample_notify()
    buf = n.to_bytes()
    print(f"序列化: {len(buf)} 字节")
    print("HEX: " + buf.hex().upper())
    print()
    n2 = NewLaneLineDataNotify.from_bytes(buf)
    print("反序列化结果:")
    print(n2)

    # 注意：float32 有精度损失，不能用浮点相等比较；应比较"再序列化后的字节"
    buf2 = n2.to_bytes()
    assert buf2 == buf, "round-trip 不一致!"
    print(f"\n[OK] 序列化/反序列化往返一致（{len(buf)} 字节，二次序列化字节完全相同）")
