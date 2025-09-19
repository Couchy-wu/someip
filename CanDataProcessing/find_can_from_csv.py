import pandas as pd
from typing import List, Tuple

# 模块功能：根据 CAN ID、 信号名称 和 枚举值 生成信号数据
# 比如：create_can_data_by_signal('12D', 'BCMPower_Gear_12D_S', 3)
# →  [0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00]

# 根据CAN ID 和 信号名称 从csv中找到更多信号信息
def get_signal_info_by_id_and_name(message_id, signal_name_en, csv_file='TestcaseCollection/outputMatrix.csv'):
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
    print("找到信号")
    # print("找到信号：")
    # for key, value in result_can.items():
    #     print(f"  {key}: {value}")

    return result_can

def _parse_bit_range(bit_range: str) -> Tuple[int, int, int, int]:
    """解析 "row_start.col_start-row_end.col_end" → 四个整数坐标。"""
    try:
        start, end = bit_range.split("-")
        rs, cs = map(int, start.split("."))
        re, ce = map(int, end.split("."))
    except Exception as exc:
        raise ValueError(f'位范围格式错误') from exc

    if not (1 <= rs <= 8 and 1 <= re <= 8):
        raise ValueError("行号必须在 1~8 之间")
    if not (0 <= cs <= 7 and 0 <= ce <= 7):
        raise ValueError("列号必须在 0~7 之间")
    if (re, ce) < (rs, cs):
        raise ValueError("结束位置必须在起始位置的右下方")
    return rs, cs, re, ce

def _calc_signal_length(rs: int, cs: int, re: int, ce: int) -> int:
    """计算信号所占的总位数。"""
    length = 0
    r, c = rs, cs
    while (r, c) <= (re, ce):
        length += 1
        if c < 7:
            c += 1
        else:
            r += 1
            c = 0
    return length

# 根据信号 位 和 枚举值 生成数据（十进制整数）（普通帧）
def generate_can_data(bit_range: str, enum_value: int) -> List[int]:
    """
    根据位范围和枚举值生成 8 字节 CAN 数据（返回整数列表）。
    """
    rs, cs, re, ce = _parse_bit_range(bit_range)
    signal_len = _calc_signal_length(rs, cs, re, ce)

    if enum_value < 0:
        raise ValueError("enum_value 不能为负数")
    if enum_value >= (1 << signal_len):
        raise ValueError(
            f"enum_value={enum_value} 超出位宽 {signal_len} 能表示的范围"
        )

    # LSB → MSB 的位序列
    bits = [int(b) for b in reversed(bin(enum_value)[2:].zfill(signal_len))]

    # 8×8 位矩阵，初始化为 0
    rows = [[0] * 8 for _ in range(8)]

    # 按行优先顺序写入位
    r, c = rs, cs
    i = 0
    while (r, c) <= (re, ce) and i < signal_len:
        rows[r - 1][c] = bits[i]
        i += 1
        if c < 7:
            c += 1
        else:
            r += 1
            c = 0

    # 转换为字节值（整数列表）
    data_bytes = []
    for row in rows:
        value = sum(bit << idx for idx, bit in enumerate(row))
        data_bytes.append(value)

    return data_bytes

# 将整数列表格式化为 [0x00, 0x60, ...] 形式的字符串
def format_can_data(data: List[int]) -> str:
    """
    将整数列表格式化为 [0x00, 0x60, ...] 形式的字符串。
    """
    return "[" + ", ".join(f"0x{byte:02X}" for byte in data) + "]"

# 根据 CAN ID、 信号名称 和 枚举值 生成信号数据
def create_can_data_by_signal(message_id: str, signal_name_en: str, enum_value: int, csv_file: str = 'TestcaseCollection/outputMatrix.csv') -> List[int]:
    """
    根据报文ID和信号英文名获取位定义，并生成对应的CAN数据。

    参数:
        message_id (str): 报文ID，如 '12D'
        signal_name_en (str): 信号英文名，如 'BCMPower_Gear_12D_S'
        enum_value (int): 枚举值，用于生成数据
        csv_file (str): CSV文件路径，默认为 'outputMatrix.csv'

    返回:
        List[int]: 生成的CAN数据字节列表
    """
    # 获取信号信息
    signal_info = get_signal_info_by_id_and_name(message_id, signal_name_en, csv_file)
    
    # 提取“位”字段
    bit_range = signal_info['位']
    
    # 调用生成函数
    data = generate_can_data(bit_range, enum_value)      # 举例输出：[0, 0, 0, 0, 12, 0, 0, 0]
    data = format_can_data(data)                         # 举例输出：[0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00]

    return data


# 示例调用
if __name__ == "__main__":
    data = create_can_data_by_signal('12D', 'BCMPower_Gear_12D_S', 3)
    print(data)  
