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
            for i, case in enumerate(self.test_cases):
                case_id = case['id']
                mylog.info(LOGGER_NAME, "=============================================")
                mylog.info(LOGGER_NAME, f"正在处理用例: {case_id}")

                # 仅当存在脚本解析结果时才进行重复执行
                if self.has_script_result(case['content']):
                    mylog.info(LOGGER_NAME, f"存在脚本解析结果，开始执行测试（共重复 {self.case_repeat_count} 次）")

                    for round_idx in range(1, self.case_repeat_count + 1):
                        mylog.info(LOGGER_NAME, f"第 {round_idx} 次检测开始...")

                        self.analyze_script_parts(case['content'])

                        # 每次执行后等待并清理（最后一次也清理）
                        if round_idx < self.case_repeat_count:
                            delay_time = 3
                            mylog.info(LOGGER_NAME, f"第 {round_idx} 次检测完成，等待{delay_time}秒后开始下一次...")
                            time.sleep(delay_time)

                            # 清理操作：只要 CAN 设备已打开，就执行，不再依赖 ENABLE_AUTO_OPEN_CLOSE_CAN
                            if self.can_device and device_handle is not None and channel_handles is not None:
                                self._clear_can_channel(chn=0)
                        else:
                            # 最后一次执行后仍进行清理
                            mylog.info(LOGGER_NAME, f"第 {round_idx} 次检测完成，正在清理...")
                            if self.can_device and device_handle is not None and channel_handles is not None:
                                self._clear_can_channel(chn=0)
                else:
                    mylog.info(LOGGER_NAME, "不存在脚本解析结果，跳过该用例")
                    continue

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
        """处理块内每一行指令，支持上下文感知"""
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

            # === 采集CAN信号（新增）===
            collect_match = re.match(r'^采集\(([^)]+)\)', line)
            if collect_match:
                result = self._handle_collect_can_with_context(lines, i)
                i += 1
                continue

            # === 等待 ===
            wait_match = re.match(r'^等待\((\d+)\)', line)
            if wait_match:
                self._delay_ms(int(wait_match.group(1)))
                i += 1
                continue

            mylog.info(LOGGER_NAME, f"未识别的指令: {line}")
            i += 1


    def _handle_output_can_with_context(self, lines, current_index):
        """
        处理 '输出(...)' 指令：
        - 提取 enum_value（仅用于日志或后续扩展，当前不参与逻辑）
        - 从下一行提取 CAN 参数，尤其是 '分配index: X' 作为发送通道编号
        """
        mylog.debug(LOGGER_NAME, f"当前 CAN 设备状态: {self.can_device is not None}")
        current_line = lines[current_index].strip()

        # === 1. 提取 enum_value（仅用于日志提示，当前不使用）===
        enum_match = re.match(r'^输出\([^,]+,\s*(\d+)\)', current_line)
        if not enum_match:
            mylog.error(LOGGER_NAME, "输出指令格式错误，未匹配到枚举值")
            return
        try:
            enum_value = int(enum_match.group(1))
        except ValueError:
            mylog.error(LOGGER_NAME, f"无效的枚举值: {enum_match.group(1)}")
            return

        # === 2. 获取下一行 CAN 报文描述 ===
        if current_index + 1 >= len(lines):
            mylog.error(LOGGER_NAME, "缺少CAN报文参数：未找到下一行")
            return
        next_line = lines[current_index + 1].strip()

        if not next_line.startswith("→") or "输出CAN报文" not in next_line:
            mylog.error(LOGGER_NAME, "下一行未包含CAN报文参数（应以 → 开头）")
            return

        # === 3. 提取分配index（这才是真正的发送通道编号）===
        index_match = re.search(r'分配index:\s*(\d+)', next_line)
        if not index_match:
            mylog.error(LOGGER_NAME, "未找到 '分配index' 字段，请检查日志格式")
            return
        try:
            index = int(index_match.group(1))  # 真正的 index
        except ValueError:
            mylog.error(LOGGER_NAME, f"无效的分配index: {index_match.group(1)}")
            return

        # === 4. 提取 CAN ID ===
        id_match = re.search(r'ID:\s*0x([0-9A-Fa-f]+)', next_line)
        if not id_match:
            mylog.error(LOGGER_NAME, "未解析到CAN ID")
            return
        try:
            can_id = int(id_match.group(1), 16)
        except:
            mylog.error(LOGGER_NAME, "CAN ID 格式错误")
            return

        # === 5. 提取发送类型 ===
        type_match = re.search(r'发送类型:\s*(\w+)', next_line)
        if not type_match:
            mylog.error(LOGGER_NAME, "未解析到发送类型")
            return
        signal_type = type_match.group(1).upper()
        valid_types = {"EVENT", "CYCLE", "CE"}
        if signal_type not in valid_types:
            mylog.error(LOGGER_NAME, f"不支持的发送类型: {signal_type}")
            return

        # === 6. 提取 CAN 数据 ===
        data_match = re.search(r'生成CAN数据:\s*(\[.*?\])', next_line)
        if not data_match:
            mylog.error(LOGGER_NAME, "未解析到CAN数据")
            return
        try:
            data_str = data_match.group(1)
            data = [int(x.strip(), 16) for x in data_str[1:-1].split(',') if x.strip()]
            if len(data) < 1 or len(data) > 64:
                mylog.error(LOGGER_NAME, f"CAN数据长度非法: {len(data)} 字节")
                return
        except Exception as e:
            mylog.error(LOGGER_NAME, f"解析CAN数据失败: {e}")
            return

        # === 7. 处理 cycle_ms ===
        cycle_ms = None
        if signal_type == "CYCLE":
            cycle_match = re.search(r'周期时间:\s*(\d+)', next_line)
            if not cycle_match:
                mylog.error(LOGGER_NAME, "Cycle类型需提供周期时间")
                return
            try:
                cycle_ms = int(cycle_match.group(1))
                if cycle_ms <= 0:
                    raise ValueError
            except:
                mylog.error(LOGGER_NAME, "周期时间必须为正整数")
                return

        elif signal_type == "EVENT":
            event_cycle_match = re.search(r'事件间隔:\s*(\d+)', next_line)
            try:
                cycle_ms = int(event_cycle_match.group(1)) if event_cycle_match else 100
            except:
                cycle_ms = 100

        elif signal_type == "CE":
            event_match = re.search(r'事件间隔:\s*(\d+)', next_line)
            cycle_match = re.search(r'周期:\s*(\d+)', next_line)
            if not event_match or not cycle_match:
                mylog.error(LOGGER_NAME, "CE类型必须提供事件间隔和周期")
                return
            try:
                event_ms = int(event_match.group(1))
                cycle_period_ms = int(cycle_match.group(1))
                if event_ms <= 0 or cycle_period_ms <= 0:
                    raise ValueError
                cycle_ms = f"{event_ms}/{cycle_period_ms}"
            except:
                mylog.error(LOGGER_NAME, "CE类型的事件间隔或周期格式错误")
                return

        # === 8. 获取 CAN 设备句柄 ===
        if not hasattr(self, 'can_device') or self.can_device is None:
            mylog.error(LOGGER_NAME, "CAN设备未初始化，无法发送信号")
            return
        device_handle, channel_handles, receive_threads = self.can_device
        chn = 0
        chn_handle = channel_handles[chn]

        # === 9. 发送信号   ===
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

        # === 10. 日志输出 ===
        if result is not None:
            mylog.info(LOGGER_NAME, f"SndOK → 已发送 CAN ID: 0x{can_id:X} (index={index}) [信号枚举值={enum_value}]")
        else:
            mylog.error(LOGGER_NAME, f"发送失败: CAN ID: 0x{can_id:X} (index={index})")

    def _handle_collect_can_with_context(self, lines, current_index):
        """
        处理 '采集(...)' 指令：
        - 从下一行提取 '→ 采集CAN报文...' 中的 ID 和 数据
        - 调用 wait_for_check_signal_received 阻塞等待接收
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
            can_id = int(id_match.group(1), 16)
        except ValueError:
            mylog.error(LOGGER_NAME, f"无效的CAN ID: {id_match.group(1)}")
            return False

        # 提取期望数据
        data_match = re.search(r'生成CAN数据:\s*(\[.*?\])', next_line)
        if not data_match:
            mylog.error(LOGGER_NAME, "未解析到期望CAN数据")
            return False
        try:
            data_str = data_match.group(1)
            expected_data = [int(x.strip(), 16) for x in data_str[1:-1].split(',') if x.strip()]
            if len(expected_data) < 1 or len(expected_data) > 64:
                mylog.error(LOGGER_NAME, f"期望数据长度非法: {len(expected_data)} 字节")
                return False
        except Exception as e:
            mylog.error(LOGGER_NAME, f"解析期望数据失败: {e}")
            return False

        # 固定通道为 0（可根据实际扩展）
        channel = 0

        # 获取 CAN 设备句柄
        if not hasattr(self, 'can_device') or self.can_device is None:
            mylog.error(LOGGER_NAME, "CAN设备未初始化，无法接收信号")
            return False

        # 调用接收等待函数
        mylog.info(LOGGER_NAME, f"RcvWait → 等待 CAN ID: 0x{can_id:X} 数据: {expected_data}")
        received = can_control.wait_for_check_signal_received(
            signal_id=can_id,
            expected_data_list=expected_data,
            channel=channel,
            timeout=3.0,
            check_interval=0.1
        )

        if received:
            mylog.info(LOGGER_NAME, f"RcvOK → 已接收到 CAN ID: 0x{can_id:X}")
            return True
        else:
            mylog.error(LOGGER_NAME, f"RcvFail → 未收到预期信号: ID: 0x{can_id:X} 数据: {expected_data}")
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
