import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import re
import time
import can_control
import mylog
import logging

# 注意！仅调试该文件时打开开关，其他情况请务必关掉该开关，避免重复初始化或意外关闭can设备
# 其实现在逻辑已经解决了重复初始化，但是没解决意外关闭can设别，后续再修改
ENABLE_AUTO_OPEN_CLOSE_CAN = False  # 是否自动开关CAN设备

# 全局 logger 名称
LOGGER_NAME = "parser"

# 每个测试用例重复执行的次数
CASE_REPEAT_COUNT = 1 

class LogParser:
    def __init__(self, log_path, device_handle=None, channel_handles=None, receive_threads=None, case_repeat_count=None):
        """
        初始化日志解析器
        :param log_path: 日志文件路径
        :param device_handle: 外部传入的设备句柄（可选）
        :param channel_handles: 外部传入的通道句柄列表（可选）
        :param case_repeat_count: 外部指定的重复次数（可选），优先级高于全局 CASE_REPEAT_COUNT
        """
        self.log_path = log_path
        self.log_content = ""
        self.test_cases = []
        self.can_device = (device_handle, channel_handles, receive_threads)

        # 使用传入值或默认值
        self.case_repeat_count = case_repeat_count if case_repeat_count is not None else CASE_REPEAT_COUNT

        mylog.setup_logger(
            logger_name=LOGGER_NAME,
            log_dir="./logs",
            log_prefix="parser",
            level=logging.INFO,
            clear_old=True,           # 自动清理旧日志
            use_timestamp=True,       # 文件名带时间戳
            show_prefix=True          # 显示日志前缀（时间+级别）
        )

    def load_log(self):
        """加载日志文件内容"""
        if not os.path.exists(self.log_path):
            error_msg = f"日志文件未找到: {self.log_path}"
            mylog.error(LOGGER_NAME, error_msg)
            raise FileNotFoundError(error_msg)

        with open(self.log_path, 'r', encoding='utf-8') as file:
            self.log_content = file.read()
        mylog.info(LOGGER_NAME, "文件加载成功！")

    def split_test_cases(self):
        """根据日志中的用例分隔符拆分测试用例"""
        mylog.info(LOGGER_NAME, "开始处理用例")
        case_pattern = r"=== 开始处理 用例 ([A-Z0-9_]+) ==="
        matches = list(re.finditer(case_pattern, self.log_content))

        self.test_cases = []
        for i in range(len(matches)):
            start_idx = matches[i].start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(self.log_content)
            case_block = self.log_content[start_idx:end_idx].strip()
            case_id = matches[i].group(1)
            self.test_cases.append({
                'id': case_id,
                'content': case_block
            })
        mylog.info(LOGGER_NAME, f"共拆分出 {len(self.test_cases)} 个测试用例。")

    def has_script_result(self, case_content):
        """
        判断用例日志中是否包含“脚本解析结果”
        :param case_content: 用例日志文本
        :return: bool
        """
        return "脚本解析结果：" in case_content

    def parse_all_cases(self):
        """依次解析所有测试用例，并重复执行指定次数"""
        mylog.debug(LOGGER_NAME, f"使用外部CAN设备资源: device={self.can_device[0]}, chn_handles={self.can_device[1]}, threads={self.can_device[2]}")
        if not self.test_cases:
            mylog.info(LOGGER_NAME, "未检测到任何测试用例，请先调用 split_test_cases() 方法。")
            return

        # ========== 启动 CAN 设备 ==========
        if ENABLE_AUTO_OPEN_CLOSE_CAN:
            # 如果外部已传入设备，则跳过自动初始化
            if self.can_device and self.can_device[0] is not None:
                mylog.info(LOGGER_NAME, "检测到外部传入的CAN设备，跳过自动初始化")
            else:
                try:
                    device_handle, channel_handles, receive_threads = can_control.Initialize_Canfd_Device(
                        device_type=can_control.ZCAN_USBCANFD_200U,
                        merge_receive=0
                    )
                    self.can_device = (device_handle, channel_handles, receive_threads)
                    mylog.info(LOGGER_NAME, "CAN设备已开启")
                except Exception as e:
                    mylog.error(LOGGER_NAME, f"CAN设备开启失败: {e}")
                    return

        device_handle = None
        channel_handles = None
        if self.can_device:
            device_handle, channel_handles, _ = self.can_device
        try:
            total_cases = len(self.test_cases)
            for i, case in enumerate(self.test_cases):
                case_id = case['id']
                mylog.info(LOGGER_NAME, "=============================================")
                mylog.info(LOGGER_NAME, f"开始处理用例: {case_id}")
                print(f"▶ 开始处理用例: {case_id}")
    
                executed = False  # 标记该用例是否执行了至少一次
    
                if self.has_script_result(case['content']):
                    mylog.info(LOGGER_NAME, f"存在脚本解析结果，开始执行测试（共重复 {self.case_repeat_count} 次）")
                    print(f"开始执行测试（共重复 {self.case_repeat_count} 次）")

                    for round_idx in range(1, self.case_repeat_count + 1):
                        mylog.info(LOGGER_NAME, f"第 {round_idx} 次检测开始...")
                        print(f"第 {round_idx} 次检测开始...")
                        self.analyze_script_parts(case['content'])
                        executed = True
    
                        # 每轮重复后等待并清理（最后一次重复内也清理，但不在此处加用例间延迟）
                        if round_idx < self.case_repeat_count:
                            delay_time = 5
                            mylog.info(LOGGER_NAME, f"第 {round_idx} 次检测完成，等待{delay_time}秒后开始下一次...")
                            print(f"第 {round_idx} 次检测完成，等待{delay_time}秒后开始下一次...")
                            time.sleep(delay_time)
                            self._clear_can_channel(chn=0)
    
                    # 所有重复执行完后，进行最后一次清理
                    mylog.info(LOGGER_NAME, f"第 {self.case_repeat_count} 次检测完成，正在清理...")
                    if self.can_device and device_handle is not None and channel_handles is not None:
                        self._clear_can_channel(chn=0)
                else:
                    mylog.info(LOGGER_NAME, "不存在脚本解析结果，跳过该用例")
                    print("不存在脚本解析结果，跳过该用例")
                    continue
                
                # 如果不是最后一个用例，并且当前用例已执行，则等待 x 秒再进入下一个用例
                if executed and (i < total_cases - 1):
                    inter_case_delay = 5  # 可以定义为配置项或参数
                    mylog.info(LOGGER_NAME, f"用例 {case_id} 已完成，等待{inter_case_delay}秒后开始下一个用例...")
                    print(f"用例 {case_id} 已完成，等待{inter_case_delay}秒后开始下一个用例...")
                    time.sleep(inter_case_delay)
    
        finally:
            # ========== 关闭 CAN 设备 ==========
            if ENABLE_AUTO_OPEN_CLOSE_CAN and hasattr(self, 'can_device') and self.can_device:
                device_handle, channel_handles, receive_threads = self.can_device
                try:
                    can_control.Close_Canfd_Device(device_handle, channel_handles, receive_threads)
                    mylog.info(LOGGER_NAME, "CAN设备已关闭")
                except Exception as e:
                    mylog.error(LOGGER_NAME, f"CAN设备关闭失败: {e}")


    def _clear_can_channel(self, chn=0):
        """
        清理指定 CAN 通道的定时发送列表
        :param chn: 通道编号
        """
        if not self.can_device:
            return
        device_handle, channel_handles, _ = self.can_device
        if device_handle is None or chn >= len(channel_handles):
            mylog.warning(LOGGER_NAME, f"无效的设备或通道编号: {chn}")
            return
        try:
            if can_control.Clear_Auto_Can_Send(device_handle, chn):
                mylog.info(LOGGER_NAME, f"已清除通道 {chn} 的定时发送列表")
            else:
                mylog.warning(LOGGER_NAME, f"清除通道 {chn} 定时发送列表失败")
        except Exception as e:
            mylog.error(LOGGER_NAME, f"清理定时发送列表时发生异常: {e}")

    def analyze_script_parts(self, content):
        """解析状态、动作、响应"""
        self._analyze_state(content)
        self._analyze_action(content)
        self._analyze_response(content)

    def _analyze_state(self, content):
        mylog.info(LOGGER_NAME, "执行“状态”")
        block = self._extract_block(content, "状态")
        if block:
            self._process_block_lines(block)

    def _analyze_action(self, content):
        mylog.info(LOGGER_NAME, "执行“动作”")
        block = self._extract_block(content, "动作")
        if block:
            self._process_block_lines(block)

    def _analyze_response(self, content):
        mylog.info(LOGGER_NAME, "执行“响应”")
        block = self._extract_block(content, "响应")
        if block:
            self._process_block_lines(block)

    def _extract_block(self, content, block_name):
        """提取指定块内容"""
        pattern = rf'{block_name}[:：]\s*\n((?:[ \t]+.+?(?:\n|$))+)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if not match:
            mylog.info(LOGGER_NAME, f"未找到 {block_name} 块")
            return []

        block_text = match.group(1)
        lines = [line.strip() for line in block_text.split('\n')]
        return [line for line in lines if line]

    def _process_block_lines(self, lines):
        """处理块内每一行指令，支持上下文感知，并新增禁用index自动调用功能"""
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('-') or line.startswith('→'):
                i += 1
                continue

            # === 输出CAN信号 ===
            output_match = re.match(r'^输出\(([^,]+),\s*(\d+)\)', line)
            if output_match:
                self._handle_output_can_with_context(lines, i)
                i += 1
                continue

            # === 采集CAN信号 ===
            collect_match = re.match(r'^采集\(([^)]+)\)', line)
            if collect_match:
                self._handle_collect_can_with_context(lines, i)
                i += 1
                continue

            # === 等待 ===
            wait_match = re.match(r'^等待\((\d+)\)', line)
            if wait_match:
                self._delay_ms(int(wait_match.group(1)))
                i += 1
                continue

            # === 新增：检测“测试台CANID禁用”并调用禁用函数 ===
            disable_match = re.match(r'^测试台CANID禁用[0-9A-F]+，禁用对应index:(.+)$', line)
            if disable_match:
                indices_str = disable_match.group(1).strip()
                indices = [int(x.strip()) for x in indices_str.split(',') if x.strip().isdigit()]

                # 获取设备句柄（复用已有资源）
                device_handle = self.can_device[0] if self.can_device else None
                if device_handle is not None:
                    for idx in indices:
                        can_control.Remove_Auto_Send_By_Index(
                            device_handle=device_handle,
                            chn=0,              # 固定通道0
                            msg_type="canfd",    # 固定类型canfd
                            index=idx
                        )
                        mylog.info(LOGGER_NAME, f"Disable → 禁用定时发送 index: {idx}")
                        time.sleep(0.2)  # 每次禁用后延迟 200ms，确保设备处理完成
                i += 1
                continue

            mylog.info(LOGGER_NAME, f"未识别的指令: {line}")
            i += 1


    def _handle_output_can_with_context(self, lines, current_index):
        """
        处理 `输出(...)` 指令：
        - 解析枚举值（仅用于日志）
        - 读取紧随其后的 “→ 输出CAN报文 …” 行
        - 提取 ID、发送类型、数据、分配 index 以及周期/间隔参数
        - 调用 `can_control.Send_Can_Signal`
        - 修正：不再以 'result is not None' 作为成功唯一标准，避免周期信号被误判为失败
        """
        # 当前 CAN 设备是否已初始化（仅日志）
        mylog.debug(LOGGER_NAME, f"当前 CAN 设备状态: {self.can_device is not None}")

        # 1. 解析枚举值（日志用）
        current_line = lines[current_index].strip()
        enum_match = re.match(r'^输出\([^,]+,\s*(\d+)\)', current_line)
        if not enum_match:
            mylog.error(LOGGER_NAME, "输出指令格式错误，未匹配到枚举值")
            return
        try:
            enum_value = int(enum_match.group(1))
        except ValueError:
            mylog.error(LOGGER_NAME, f"无效的枚举值: {enum_match.group(1)}")
            return

        # 2. 读取下一行的 CAN 报文描述
        if current_index + 1 >= len(lines):
            mylog.error(LOGGER_NAME, "缺少CAN报文参数：未找到下一行")
            return
        next_line = lines[current_index + 1].strip()
        if not next_line.startswith("→") or "输出CAN报文" not in next_line:
            mylog.error(LOGGER_NAME, "下一行未包含CAN报文参数（应以 → 开头）")
            return

        # 3. 提取分配 index（实际发送通道编号）
        index_match = re.search(r'分配index:\s*(\d+)', next_line)
        if not index_match:
            mylog.error(LOGGER_NAME, "未找到 '分配index' 字段，请检查日志格式")
            return
        try:
            index = int(index_match.group(1))
        except ValueError:
            mylog.error(LOGGER_NAME, f"无效的分配index: {index_match.group(1)}")
            return

        # 4. 提取 CAN ID
        id_match = re.search(r'ID:\s*0x([0-9A-Fa-f]+)', next_line)
        if not id_match:
            mylog.error(LOGGER_NAME, "未解析到CAN ID")
            return
        can_id = int(id_match.group(1), 16)

        # 5. 提取发送类型
        type_match = re.search(r'发送类型:\s*(\w+)', next_line)
        if not type_match:
            mylog.error(LOGGER_NAME, "未解析到发送类型")
            return
        signal_type = type_match.group(1).upper()
        valid_types = {"EVENT", "CYCLE", "CE"}
        if signal_type not in valid_types:
            mylog.error(LOGGER_NAME, f"不支持的发送类型: {signal_type}")
            return

        # 6. 提取 CAN 数据
        data_match = re.search(r'生成CAN数据:\s*(\[[^\]]*\])', next_line)
        if not data_match:
            mylog.error(LOGGER_NAME, "未解析到CAN数据")
            return
        try:
            data_str = data_match.group(1)
            data = [int(x.strip(), 16) for x in data_str[1:-1].split(',') if x.strip()]
            if not (1 <= len(data) <= 64):
                mylog.error(LOGGER_NAME, f"CAN数据长度非法: {len(data)} 字节")
                return
        except Exception as e:
            mylog.error(LOGGER_NAME, f"解析CAN数据失败: {e}")
            return

        # 7. 解析周期/间隔参数，生成 `cycle_ms` 供 Send_Can_Signal 使用
        cycle_ms = None
        if signal_type == "CYCLE":
            period_match = re.search(r'周期(?:时间)?:\s*(\d+)', next_line)
            if not period_match:
                mylog.error(LOGGER_NAME, "Cycle 类型需提供周期时间")
                return
            try:
                cycle_ms = int(period_match.group(1))
                if cycle_ms <= 0:
                    raise ValueError
            except Exception:
                mylog.error(LOGGER_NAME, "周期时间必须为正整数")
                return

        elif signal_type == "EVENT":
            ev_match = re.search(r'事件间隔:\s*(\d+)', next_line)
            try:
                cycle_ms = int(ev_match.group(1)) if ev_match else 100
                if cycle_ms <= 0:
                    raise ValueError
            except Exception:
                cycle_ms = 100   # 使用默认值

        elif signal_type == "CE":
            ce_match = re.search(r'周期时间:\s*([\d\s/]+)ms?', next_line, re.IGNORECASE)
            if ce_match:
                pair_str = ce_match.group(1).replace(' ', '')
                if '/' not in pair_str:
                    mylog.error(LOGGER_NAME, "CE 类型的周期时间格式错误，缺少 '/' 分隔符")
                    return
                ev_str, per_str = pair_str.split('/', 1)
                try:
                    event_ms = int(ev_str)
                    cycle_period_ms = int(per_str)
                except Exception:
                    mylog.error(LOGGER_NAME, "CE 类型的事件间隔或周期不是整数")
                    return
            else:
                ev_match = re.search(r'事件间隔:\s*(\d+)', next_line)
                per_match = re.search(r'周期:\s*(\d+)', next_line)
                if not ev_match or not per_match:
                    mylog.error(LOGGER_NAME, "CE 类型必须提供事件间隔和周期（或使用‘周期时间: a/b’）")
                    return
                try:
                    event_ms = int(ev_match.group(1))
                    cycle_period_ms = int(per_match.group(1))
                except Exception:
                    mylog.error(LOGGER_NAME, "CE 类型的事件间隔或周期不是整数")
                    return

            if event_ms <= 0 or cycle_period_ms <= 0:
                mylog.error(LOGGER_NAME, "CE 类型的事件间隔和周期必须均为正整数")
                return
            cycle_ms = f"{event_ms}/{cycle_period_ms}"

        # 获取 CAN 设备句柄
        if not hasattr(self, 'can_device') or self.can_device is None:
            mylog.error(LOGGER_NAME, "CAN设备未初始化，无法发送信号")
            return
        device_handle, channel_handles, _ = self.can_device
        chn = 0
        chn_handle = channel_handles[chn]

        # 调用发送函数
        try:
            result = can_control.Send_Can_Signal(
                device_handle=device_handle,
                chn_handle=chn_handle,
                chn=chn,
                stdorext=0,
                id=can_id,
                data=data,
                msg_type="canfd",
                signal_type=signal_type,
                cycle_ms=cycle_ms,
                index=index
            )

            # 成功判断逻辑
            if result is not False:  # 只要不是明确返回 False，都认为提交成功
                mylog.info(
                    LOGGER_NAME,
                    f"SndOK → 已启动发送 CAN ID: 0x{can_id:X} (index={index}) [信号枚举值={enum_value}]"
                )
            else:
                mylog.error(
                    LOGGER_NAME,
                    f"发送任务提交失败: CAN ID: 0x{can_id:X} (index={index})"
                )

            # 可选：调试用
            # mylog.debug(LOGGER_NAME, f"Send_Can_Signal 返回值: {result}")

        except Exception as e:
            mylog.error(
                LOGGER_NAME,
                f"调用 Send_Can_Signal 时发生异常: CAN ID: 0x{can_id:X} (index={index}) 错误: {e}"
            )


    def _handle_collect_can_with_context(self, lines, current_index):
        """
        处理 '采集(...)' 指令：
        - 从下一行提取 '→ 采集CAN报文...' 中的 ID、子ID、位、枚举值
        - 子ID 以字符串形式保留，统一为 "No" 或 "0x..." 格式（小写），传给 wait_for_check_signal_by_bit_enum
        - 不再进行 int 转换，保持 str 模式
        """
        current_line = lines[current_index].strip()

        # 获取下一行
        if current_index + 1 >= len(lines):
            mylog.error(LOGGER_NAME, "缺少采集参数：未找到下一行")
            return False
        next_line = lines[current_index + 1].strip()

        if not next_line.startswith("→") or "采集CAN报文" not in next_line:
            mylog.error(LOGGER_NAME, "下一行未包含采集CAN报文参数（应以 → 开头）")
            return False

        # 提取 CAN ID
        id_match = re.search(r'ID:\s*0x([0-9A-Fa-f]+)', next_line)
        if not id_match:
            mylog.error(LOGGER_NAME, "未解析到CAN ID")
            return False
        try:
            signal_id = int(id_match.group(1), 16)  # 仍需 int 用于传入（支持 int 或 str）
        except ValueError:
            mylog.error(LOGGER_NAME, f"无效的CAN ID: {id_match.group(1)}")
            return False

        # 提取 子ID 原始字符串
        sub_id_match = re.search(r'子ID:\s*([^|]+)', next_line)
        if not sub_id_match:
            mylog.error(LOGGER_NAME, "未解析到子ID")
            return False
        sub_id_raw = sub_id_match.group(1).strip()

        # 统一格式化为函数期望的字符串格式："No" 或 "0x..."
        if sub_id_raw.upper() == "NO":
            sub_id = "No"
        else:
            # 尝试解析为十六进制，并转为标准 "0x.." 小写格式
            try:
                if sub_id_raw.lower().startswith("0x"):
                    hex_val = int(sub_id_raw, 16)
                else:
                    hex_val = int(sub_id_raw, 16)  # 支持无前缀
                sub_id = f"0x{hex_val:x}"  # 输出小写，如 0xa → 0xa（不补0）
            except ValueError:
                mylog.error(LOGGER_NAME, f"无法将子ID转为十六进制: {sub_id_raw}")
                return False

        # 提取 位域
        bit_match = re.search(r'位:\s*([^|]+)', next_line)
        if not bit_match:
            mylog.error(LOGGER_NAME, "未解析到位域")
            return False
        bit_position = bit_match.group(1).strip()

        # 提取 枚举值
        enum_match = re.search(r'枚举值:(\d+)', next_line)
        if not enum_match:
            mylog.error(LOGGER_NAME, "未解析到期望枚举值")
            return False
        try:
            expected_enum_value = int(enum_match.group(1))
        except ValueError:
            mylog.error(LOGGER_NAME, f"无效的枚举值: {enum_match.group(1)}")
            return False

        # 固定通道为 0（可根据实际扩展）
        channel = 0

        # 获取 CAN 设备句柄
        if not hasattr(self, 'can_device') or self.can_device is None:
            mylog.error(LOGGER_NAME, "CAN设备未初始化，无法接收信号")
            return False

        # 调用信号等待函数（sub_id 为字符串："No" 或 "0x..."）
        mylog.info(LOGGER_NAME, f"RcvWait → 等待 CAN ID: 0x{signal_id:X}, 子ID={sub_id_raw}, 位={bit_position}, 期望枚举值={expected_enum_value}")
        received = can_control.wait_for_check_signal_by_bit_enum(
            signal_id=signal_id,
            sub_id=sub_id,  # 传入标准化字符串："No" 或 "0x..."
            bit_position=bit_position,
            expected_enum_value=expected_enum_value,
            channel=channel,
            timeout=2.0,
            check_interval=0.1
        )

        if received:
            mylog.info(LOGGER_NAME, f"RcvOK → 已接收到满足条件的 CAN ID: 0x{signal_id:X}, 子ID={sub_id_raw}, 位={bit_position}, 值={expected_enum_value}")
            return True
        else:
            mylog.error(LOGGER_NAME, f"RcvFail → 未收到预期信号: ID=0x{signal_id:X}, 子ID={sub_id_raw}, 位={bit_position}, 期望枚举值={expected_enum_value}")
            return False

    def _delay_ms(self, milliseconds):
        """延迟指定毫秒数"""
        seconds = milliseconds / 1000.0
        mylog.info(LOGGER_NAME, f"Wait {milliseconds} ms")
        time.sleep(seconds)

    def run(self):
        """一键运行全流程"""
        mylog.info(LOGGER_NAME, f"开始解析日志文件: {self.log_path}")
        try:
            self.load_log()
            self.split_test_cases()
            self.parse_all_cases()
            mylog.info(LOGGER_NAME, "日志解析执行完成。")
        except Exception as e:
            mylog.error(LOGGER_NAME, f"解析过程中发生未预期异常: {e}")
            raise


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 确保 mylog.py 存在于当前路径或可导入路径
    import mylog  # 显式导入（可选，已在上方导入）

    # 设置日志文件路径
    log_file_path = "TestcaseCollection/001_data.log"  # ← 修改为你的实际路径

    # 创建解析器并运行
    parser = LogParser(log_file_path)
    parser.run()
