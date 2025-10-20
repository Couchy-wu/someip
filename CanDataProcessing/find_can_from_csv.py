import pandas as pd
from typing import List, Tuple, Optional

# 模块功能：根据 CAN ID、 信号名称 和 枚举值 生成信号数据
# 比如：create_can_data_by_signal('12D', 'BCMPower_Gear_12D_S', 3)
# →  [0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00]

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
        df = pd.read_csv(csv_file)
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
            print(f"在报文ID {message_id_normalized} 中找到 {len(final_match)} 个完全相同的 '{signal_name_en}' 信号，自动取第一条。")
            record = final_match.iloc[0]  # 取第一条
        else:
            print(f"错误：在报文ID {message_id_normalized} 中找到多个名为 '{signal_name_en}' 的信号（共 {len(final_match)} 个），且数据不一致，请检查数据唯一性。")
            print("差异记录的子ID和关键字段：")
            for _, row in final_match.iterrows():
                print(f"  - 子ID: {row['子ID']}, 报文长度: {row['报文长度']}, 位: {row['位']}, 信号长度: {row['信号长度']}")
            return None
    else:
        # 唯一匹配
        record = final_match.iloc[0]

    # 构建结果字典（使用原始字段）
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

    # 打印结果
    sub_id = record['子ID']
    if pd.notna(sub_id) and str(sub_id).strip().upper() == 'NO':
        print(f"找到信号：0x{message_id_clean} {signal_name_en}")
    else:
       print(f"找到信号：0x{message_id_clean} {sub_id} {signal_name_en}")

    # print("找到信号：")
    # for key, value in result_can.items():
    #     print(f"  {key}: {value}")

    return result_can

def _parse_bit_range(bit_range: str, frame_length: int = 8) -> Tuple[int, int, int, int]:
    """解析 "row_start.col_start-row_end.col_end" → 四个整数坐标。
    
    参数:
        bit_range: 字符串形式的位范围，格式为 "row_start.col_start-row_end.col_end"
        frame_length: 帧长度（字节数，默认为8）
    """
    try:
        start, end = bit_range.split("-")
        start_row, start_col = map(int, start.split("."))
        end_row, end_col = map(int, end.split("."))
    except Exception as exc:
        raise ValueError(f'位范围格式错误') from exc
    
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
    length = 0
    r, c = start_row, start_col
    while (r, c) <= (end_row, end_col):
        length += 1
        if c < 7:
            c += 1
        else:
            r += 1
            c = 0
    return length

def generate_can_data(bit_range: str, enum_value: int, sub_id: Optional[str] = None, frame_length: int = 8) -> List[int]:
    """
    根据位范围和枚举值生成 frame_length 字节 CAN 数据（返回整数列表）。
    参数:
        bit_range (str): 位范围，如 "5.4-5.7"
        enum_value (int): 枚举值
        sub_id (str, optional): 子ID，如 "0x02"，若提供则替换第一个字节
        frame_length (int, optional): 帧长度（字节数，默认为8）
    
    返回:
        List[int]: CAN数据字节列表，长度为 frame_length
    """
    # 解析位范围，同时考虑帧长度
    start_row, start_col, end_row, end_col = _parse_bit_range(bit_range, frame_length)
    
    # 计算信号长度（位数）
    signal_len = _calc_signal_length(start_row, start_col, end_row, end_col)
    # 检查枚举值合法性
    if enum_value < 0:
        raise ValueError("enum_value 不能为负数")
    if enum_value >= (1 << signal_len):
        raise ValueError(
            f"enum_value={enum_value} 超出位宽 {signal_len} 能表示的范围"
        )

    # LSB → MSB 的位序列
    bits = [int(b) for b in reversed(bin(enum_value)[2:].zfill(signal_len))]
  
  # 创建帧长度×8 位矩阵，初始化为 0
    rows = [[0] * 8 for _ in range(frame_length)]
    
    # 按行优先顺序写入位
    i = 0
    while (start_row, start_col) <= (end_row, end_col) and i < len(bits):
        # 确保不超出帧范围
        if start_row <= frame_length and start_col < 8:
            rows[start_row-1][start_col] = bits[i]
            i += 1
        if start_col < 7:
            start_col += 1
        else:
            start_row += 1
            start_col = 0
        if start_row > frame_length:
            break
    
    # 转换为字节值（整数列表）
    data_bytes = []
    for row_index, row in enumerate(rows):
        if row_index < frame_length:  # 确保不超出帧长度
            value = sum(bit << idx for idx, bit in enumerate(row))
            data_bytes.append(value)

    # 如果 sub_id 存在且是十六进制字符串，替换第一个字节
    if sub_id is not None and isinstance(sub_id, str):
        try:
            # 提取十六进制数（支持 0x02, 0X02, 等）
            sub_id_clean = sub_id.strip().upper()
            if '0X' in sub_id_clean:
                sub_id_decimal = int(sub_id_clean.replace('0X', ''), 16)
            else:
                # 尝试直接作为十六进制解析
                sub_id_decimal = int(sub_id_clean, 16)
            # 替换第一个字节（如果帧长度至少为1）
            if frame_length > 0:
                data_bytes[0] = sub_id_decimal
        except ValueError:
            print(f"警告：无法解析子ID为十六进制数: {sub_id}，跳过替换。")

    return data_bytes

# 将整数列表格式化为 [0x00, 0x60, ...] 形式的字符串
def format_can_data(data: List[int]) -> str:
    """
    将整数列表格式化为 [0x00, 0x60, ...] 形式的字符串。
    """
    return "[" + ", ".join(f"0x{byte:02X}" for byte in data) + "]"

# 根据 CAN ID、信号名称和枚举值生成信号数据
def create_can_data_by_signal(message_id: str, signal_name_en: str, enum_value: int, csv_file: str = 'CanDataProcessing/outputMatrix.csv') -> str:
    """
    根据报文ID和信号英文名获取位定义，并生成对应的CAN数据。

    参数:
        message_id (str): 报文ID，如 '12D'
        signal_name_en (str): 信号英文名，如 'BCMPower_Gear_12D_S'
        enum_value (int): 枚举值，用于生成数据
        csv_file (str): CSV文件路径，默认为 'outputMatrix.csv'
    返回:
        str: 格式化后的CAN数据字符串，如 [0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00]
    """
    # 获取信号信息
    signal_info = get_signal_info_by_id_and_name(message_id, signal_name_en, csv_file)
    if signal_info is None:
        return "[]"

    # 使用信号信息中的报文长度作为帧长度
    frame_length = int(signal_info['报文长度'])
    bit_range = signal_info['位']

    # 提取子ID
    sub_id_raw = signal_info.get('子ID')
    sub_id_hex = None
    if pd.notna(sub_id_raw):
        sub_id_str = str(sub_id_raw).strip()
        if sub_id_str.upper() != 'NO':
            # 保留类似 0x02 的格式
            # 尝试规范化
            clean = sub_id_str.strip().upper()
            if '0X' in clean:
                hex_part = '0x' + clean.split('0X')[1].split()[0]  # 取第一部分
            elif all(c in '0123456789ABCDEF' for c in clean):
                hex_part = '0x' + clean
            else:
                hex_part = None
            if hex_part:
                try:
                    int(hex_part, 16)  # 验证是否合法
                    sub_id_hex = hex_part
                except ValueError:
                    print(f"警告：子ID '{sub_id_raw}' 不是有效的十六进制数，跳过。")

    # 调用生成函数，并传入 sub_id（可能为 None）和帧长度
    data = generate_can_data(bit_range, enum_value, sub_id=sub_id_hex, frame_length=frame_length)  # [0, 0, 0, 0, 12, 0, 0, 0]
    data = format_can_data(data)  # [0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00]
    return data


# 示例调用
if __name__ == "__main__":
    data1 = create_can_data_by_signal('1EF', 'RF_Window_Action_Request_S', 1)
    data2 = create_can_data_by_signal('12D', 'BCMPower_Gear_12D_S', 3)
    data3 = create_can_data_by_signal('496', 'Emitting_Function_S', 1)
    print(data1)
    print(data2)
    print(data3)
