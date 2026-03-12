# -*- coding: utf-8 -*-
import pandas as pd
from typing import List, Tuple, Optional

# 模块功能：根据 CAN ID、 信号名称 和 枚举值 生成信号数据
# 比如：create_can_data_by_signal('12D', 'BCMPower_Gear_12D_S', 3)
# →  [0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00]

# 全局缓存 _CSV_CACHE，在模块导入时读取一次 CSV
try:
    _CSV_CACHE = pd.read_csv('CanDataProcessing/outputMatrix.csv')
except Exception as exc:                     # 若文件不存在或读取出错，保持为 None
    _CSV_CACHE = None
    print(f"加载 CSV 失败: {exc}")

# 根据CAN ID 和 信号名称 从csv中找到更多信号信息
def get_signal_info_by_id_and_name(message_id, signal_name_en, csv_file='CanDataProcessing/outputMatrix.csv'):
    """
    根据报文ID和信号名称(英文)提取信号信息。
    如果找到多个信号：
      - 若所有字段完全相同 → 视为重复，取第一条
      - 若字段存在差异 → 报错并返回 None
    """
    # 读取CSV文件
    try:
        df =  _CSV_CACHE if _CSV_CACHE is not None else pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"错误：找不到文件: {csv_file}")
        return None

    # 标准化输入的 message_id（支持 '12D', '0x12d' 等）
    message_id_clean = message_id.strip().upper().replace('0X', '')
    if not all(c in '0123456789ABCDEF' for c in message_id_clean) or len(message_id_clean) == 0:
        print(f"错误：报文ID必须是十六进制数字（0-9, A-F），但收到: {message_id}")
        return None
    message_id_normalized = '0x' + message_id_clean.zfill(3)

    # 检查必要列
    expected_cols = ['报文ID', '信号名称(英文)', '子ID']
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        print(f"错误：CSV文件缺少必要列: {', '.join(missing_cols)}")
        return None

    # 标准化 CSV 中的报文ID列
    df['报文ID_normalized'] = df['报文ID'].astype(str).str.strip().str.upper()
    df['报文ID_normalized'] = df['报文ID_normalized'].apply(
        lambda x: '0x' + ''.join(c for c in x.replace('0X', '').replace('0x', '') if c in '0123456789ABCDEF').zfill(3)
        if any(c in '0123456789ABCDEF' for c in x.replace('0X', '').replace('0x', ''))
        else x
    )

    # 第一步：按报文ID筛选
    df_filtered = df[df['报文ID_normalized'] == message_id_normalized]
    if df_filtered.empty:
        print(f"未找到报文ID为 {message_id_normalized} 的数据。")
        return None

    # 第二步：按信号名称筛选
    final_match = df_filtered[df_filtered['信号名称(英文)'] == signal_name_en]
    if final_match.empty:
        print(f"在报文ID {message_id_normalized} 中未找到信号名称为 '{signal_name_en}' 的信号。")
        return None

    # 检查是否有多条记录
    if len(final_match) > 1:
        # 提取用于比较的字段（除可能的索引或无关列外）
        compare_cols = [col for col in df.columns if col != '报文ID_normalized']
        data_subset = final_match[compare_cols].drop_duplicates()

        if len(data_subset) == 1:
            # print(f"在报文ID {message_id_normalized} 中找到 {len(final_match)} 个完全相同的 '{signal_name_en}' 信号，自动取第一条。")
            record = final_match.iloc[0]  # 取第一条
        else:
            print(f"错误：在报文ID {message_id_normalized} 中找到多个名为 '{signal_name_en}' 的信号（共 {len(final_match)} 个），且数据不一致，请检查数据唯一性。")
            print("差异记录的子ID和关键字段：")
            for _, row in final_match.iterrows():
                print(f"  - 子ID: {row['子ID']}, 报文长度: {row['报文长度']}, 位: {row['位']}, 信号长度: {row['信号长度']}")
            return None
    else:
        record = final_match.iloc[0]

    # 构建返回字典（使用原始字段）
    result_can = {
        '报文名称': record['报文名称'],
        '报文类型': record['报文类型'],
        '报文ID': record['报文ID'],
        '报文发送类型': record['报文发送类型'],
        '报文周期时间': record['报文周期时间'],
        '子ID': record['子ID'],
        '报文长度': record['报文长度'],
        '位': record['位'],
        '信号长度': record['信号长度'],
        '信号名称(英文)': record['信号名称(英文)'],
        '信号名称(中文)': record['信号名称(中文)']
    }

    return result_can


def _parse_bit_range(bit_range: str, frame_length: int = 8) -> Tuple[int, int, int, int]:
    """支持 '7.2' → 自动转为 '7.2-7.2'"""
    if '-' not in bit_range:
        # 单个位置，自动扩展为范围
        try:
            row_col = bit_range.strip()
            row, col = map(int, row_col.split('.'))
            bit_range = f"{row}.{col}-{row}.{col}"
        except Exception:
            raise ValueError(f"无效的位地址格式: {bit_range}")
    # 继续原有逻辑...
    try:
        start, end = bit_range.split("-")
        start_row, start_col = map(int, start.split("."))
        end_row, end_col = map(int, end.split("."))
    except Exception as exc:
        raise ValueError(f'位范围格式错误: {bit_range}') from exc
    
    # 计算最大列号（基于帧长度）
    max_col = frame_length * 8 - 1
    
    # 验证行号范围（字节序号）
    if not (1 <= start_row <= frame_length and 1 <= end_row <= frame_length):
        raise ValueError(f"行号必须在 1~{frame_length} 之间")
    
    # 验证列号范围
    if not (0 <= start_col <= max_col and 0 <= end_col <= max_col):
        raise ValueError(f"列号必须在 0~{max_col} 之间")
    
    # 验证结束位置是否在起始位置的右下方
    if (end_row, end_col) < (start_row, start_col):
        raise ValueError("结束位置必须在起始位置的右下方")
    
    return start_row, start_col, end_row, end_col


def _calc_signal_length(start_row: int, start_col: int, end_row: int, end_col: int) -> int:
    """计算信号所占的总位数。"""
    if start_row == end_row:
        return end_col - start_col + 1
    first_row_remaining = 8 - start_col
    full_rows_between = max(end_row - start_row - 1, 0)
    middle = full_rows_between * 8
    last_row = end_col + 1
    return first_row_remaining + middle + last_row


# -------------------------- CAN 数据生成 --------------------------
def generate_can_data(bit_range: str,
                     enum_value: int,
                     sub_id: Optional[str] = None,
                     frame_length: int = 8) -> List[int]:
    """
    根据位范围和枚举值生成 frame_length 字节的 CAN 数据（返回整数列表）。
    与原实现的区别：  
      • 当信号跨越多个字节且 **起始列为 0、结束列为 7**（即字节对齐）时，采用 **大端‑字节顺序**（MSB‑first），
        这样可以得到你期望的 `[0xC1, 0x00, 0x32, 0x00, 0x31, 0x00, 0x30, 0x00]`。  
      • 其它情况仍使用 **LSB→MSB（小端）** 的位写法，保持对单字节或非字节对齐信号的兼容性。  
    参数同原实现。
    """
    # 解析位范围（已兼容单点写法）
    start_row, start_col, end_row, end_col = _parse_bit_range(bit_range, frame_length)

    # 计算信号的位宽
    signal_len = _calc_signal_length(start_row, start_col, end_row, end_col)

    # 合法性检查（保持原行为）
    if enum_value < 0:
        raise ValueError("enum_value 不能为负数")
    if enum_value >= (1 << signal_len):
        raise ValueError(
            f"enum_value={enum_value} 超出位宽 {signal_len} 能表示的范围"
        )

    # 初始化帧（全部 0）
    data_bytes = [0] * frame_length

    # -----------------------------------------------------------------
    # 对于 **字节对齐的多字节信号**（start_col == 0 且 signal_len%8==0）
    #       使用大端‑字节顺序（高位字节先写），而每个字节内部仍保持 LSB 在第 0 位。
    # -----------------------------------------------------------------
    if start_col == 0 and signal_len % 8 == 0:
        # 需要写入的完整字节数
        num_bytes = signal_len // 8
        # 起始字节的 0‑based 索引
        start_byte_idx = start_row - 1
        for i in range(num_bytes):
            # 最高字节先取 → 大端顺序
            shift = (num_bytes - 1 - i) * 8
            byte_val = (enum_value >> shift) & 0xFF
            if start_byte_idx + i < frame_length:
                data_bytes[start_byte_idx + i] = byte_val
    else:
        # -----------------------------------------------------------------
        # ★ DEL: 原来的位‑写循环（已迁移到 else 分支）
        # -----------------------------------------------------------------
        # 采用 LSB → MSB（小端）顺序写位，兼容单字节信号或非字节对齐的跨字节信号
        bits = [(enum_value >> i) & 1 for i in range(signal_len)]

        bit_index = 0
        current_byte_idx = start_row - 1          # 行号 → 0‑based
        current_bit_pos = start_col                # 列号即位偏移（0‑LSB）

        while bit_index < signal_len:
            bit_val = bits[bit_index]
            if 0 <= current_byte_idx < frame_length:
                if bit_val:
                    data_bytes[current_byte_idx] |= (1 << current_bit_pos)
                else:
                    data_bytes[current_byte_idx] &= ~(1 << current_bit_pos)

            # 向右移动一位
            current_bit_pos += 1
            if current_bit_pos >= 8:
                current_bit_pos = 0
                current_byte_idx += 1
                if current_byte_idx >= frame_length:
                    break
            bit_index += 1

    # ★ NEW: 子 ID 替换（保持原行为，只是把注释写得更清晰）
    if sub_id is not None and isinstance(sub_id, str):
        try:
            sub_id_decimal = int(sub_id.strip(), 16)
            data_bytes[0] = sub_id_decimal
        except ValueError:
            print(f"警告：无法解析子ID为十六进制数: {sub_id}，跳过替换。")

    return data_bytes


# -------------------------- 格式化 --------------------------
def format_can_data(data: List[int]) -> str:
    """把整数列表格式化为 `[0x00, 0x0C, …]` 形式的字符串。"""
    return "[" + ", ".join(f"0x{byte:02X}" for byte in data) + "]"


# -------------------------- 主入口 --------------------------
def create_can_data_by_signal(message_id: str, signal_name_en: str,
                              enum_value: int,
                              csv_file: str = 'CanDataProcessing/outputMatrix.csv') -> dict:
    """
    根据报文ID、信号英文名和枚举值生成对应的 CAN 数据。
    返回的字典中既有整数列表，也有十六进制字符串，供调试或直接输出使用。
    """
    # ① 查表得到信号元信息
    signal_info = get_signal_info_by_id_and_name(message_id, signal_name_en, csv_file)
    if signal_info is None:
        return {"success": False, "error": "信号信息未找到"}

    # 使用信号信息中的报文长度作为帧长度
    frame_length = int(signal_info['报文长度'])
    bit_range = signal_info['位']

    # 提取子ID
    sub_id_raw = signal_info.get('子ID')
    sub_id_hex = None
    if pd.notna(sub_id_raw):
        sub_id_str = str(sub_id_raw).strip()
        if sub_id_str.upper() != 'NO':
            clean = sub_id_str.upper()
            if '0X' in clean:
                hex_part = '0x' + clean.split('0X')[1].split()[0]
            elif all(c in '0123456789ABCDEF' for c in clean):
                hex_part = '0x' + clean
            else:
                hex_part = None
            if hex_part:
                try:
                    int(hex_part, 16)               # 验证合法性
                    sub_id_hex = hex_part
                except ValueError:
                    print(f"警告：子ID '{sub_id_raw}' 不是有效的十六进制数，跳过。")

    # ④ 生成 CAN 帧
    data = generate_can_data(bit_range, enum_value,
                             sub_id=sub_id_hex, frame_length=frame_length)

    # ⑤ 结果格式化
    data_str = format_can_data(data)

    # ⑥ 组装返回值
    return {
        "success": True,
        "can_data": data,                         # List[int]
        "can_data_str": data_str,                 # "[0x00, 0x0C, …]"
        "message_id": int(signal_info['报文ID'].strip(), 16),
        "message_id_str": signal_info['报文ID'],
        "message_type": signal_info['报文发送类型'],
        "cycle_time": signal_info['报文周期时间'],
        "signal_name_en": signal_name_en,
        "enum_value": enum_value,
        "bit": bit_range,
        "sub_id_raw": signal_info['子ID'],
        "sub_id_hex": sub_id_hex
    }


# -------------------------- 示例 --------------------------
if __name__ == "__main__":
    # 下面的示例均使用默认的 CSV 路径。如需自定义请在调用时传入 `csv_file` 参数
    data1 = create_can_data_by_signal('38b', 'Smart_Projection_Configuration_Judgment_S', 1)
    data2 = create_can_data_by_signal('12D', 'BCMPower_Gear_12D_S', 3)
    data3 = create_can_data_by_signal('43F', 'Media_LengthC1_S', 24)
    data4 = create_can_data_by_signal('43F', 'Media_Call_Num_S', 53876908634880)
    data5 = create_can_data_by_signal('43F', 'Media_Call_Num_43F_0xC2_S', 9007422596513846)
    data6 = create_can_data_by_signal('43F', 'Media_Call_Num_43F_0xC3_S', 60473676412928)
    data7 = create_can_data_by_signal('43F', 'Media_Call_Num_43F_0xC4_S', 16044279830937600)

    # 打印示例（可自行注释掉）
    print("data2_str:", data2["can_data_str"])
    print("data3_str:", data3["can_data_str"])
    print("data4_str:", data4["can_data_str"])
    print("data5_str:", data5["can_data_str"])
    print("data6_str:", data6["can_data_str"])
    print("data7_str:", data7["can_data_str"])