import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import re
import time
import can_control
import mylog
import logging

ENABLE_AUTO_OPEN_CLOSE_CAN = True  # 是否自动开关CAN设备

# 全局 logger 名称（统一使用一个日志文件）
LOGGER_NAME = "parser"


class LogParser:
    def __init__(self, log_path):
        """
        初始化日志解析器
        :param log_path: 日志文件路径
        """
        self.log_path = log_path
        self.log_content = ""
        self.test_cases = []

        # 初始化统一的日志器（延迟创建文件）
        mylog.setup_logger(
            logger_name=LOGGER_NAME,
            log_dir="./logs",
            log_prefix="parser",
            level=mylog.logging.INFO,
            clear_old=False,          # 设为 True 可自动清理旧日志
            use_timestamp=True,       # 文件名带时间戳
            show_prefix=True          # 显示时间与日志级别
        )

        # 定义日志函数快捷方式
        self.log = lambda msg: mylog.info(LOGGER_NAME, msg)
        self.error = lambda msg: mylog.error(LOGGER_NAME, msg)

    def load_log(self):
        """加载日志文件内容"""
        if not os.path.exists(self.log_path):
            error_msg = f"日志文件未找到: {self.log_path}"
            self.error(error_msg)
            raise FileNotFoundError(error_msg)

        with open(self.log_path, 'r', encoding='utf-8') as file:
            self.log_content = file.read()
        self.log("文件加载成功！")

    def split_test_cases(self):
        """根据日志中的用例分隔符拆分测试用例"""
        self.log("开始处理用例")
        case_pattern = r"=== 开始处理 用例 ([A-Z0-9_]+) ==="
        matches = list(re.finditer(case_pattern, self.log_content))

        # test_cases 用于存储提取的测试用例
        self.test_cases = []
        for i in range(len(matches)):
            start_idx = matches[i].start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(self.log_content)
            case_block = self.log_content[start_idx:end_idx].strip()
            case_id = matches[i].group(1)
            self.test_cases.append({
                'id': case_id,              # id: 每个测试用例的唯一标识符
                'content': case_block       # content：  每个测试用例的具体内容
            })
        self.log(f"共拆分出 {len(self.test_cases)} 个测试用例。")

    def has_script_result(self, case_content):
        """
        判断用例日志中是否包含“脚本解析结果”
        :param case_content: 用例日志文本
        :return: bool
        """
        return "脚本解析结果：" in case_content


    def parse_all_cases(self):
        """依次解析所有测试用例"""
        if not self.test_cases:
            self.log("未检测到任何测试用例，请先调用 split_test_cases() 方法。")
            return
    
        # 如果开关打开，在解析前打开 CAN 设备
        if ENABLE_AUTO_OPEN_CLOSE_CAN:
            try:
                device_handle, channel_handles, receive_threads = can_control.Initialize_Canfd_Device(
                    device_type=can_control.ZCAN_USBCANFD_200U,
                    merge_receive=0
                )
                self.log("CAN设备已开启")
                self.can_device = (device_handle, channel_handles, receive_threads)
            except Exception as e:
                self.error(f"CAN设备开启失败: {e}")
                return
        else:
            self.can_device = None  # 不启用时设为 None
    
        try:
            for case in self.test_cases:
                case_id = case['id']
                self.log(f"正在处理用例: {case_id}")
                if self.has_script_result(case['content']):
                    self.log("存在脚本解析结果，开始执行测试")
                    self.analyze_script_parts(case['content'])
                else:
                    self.log("不存在脚本解析结果，跳过该用例")
        finally:
            # 关闭 CAN 设备（如启用）
            if ENABLE_AUTO_OPEN_CLOSE_CAN and hasattr(self, 'can_device') and self.can_device:
                device_handle, channel_handles, receive_threads = self.can_device
                try:
                    can_control.Close_Canfd_Device(device_handle, channel_handles, receive_threads)
                    self.log("CAN设备已关闭")
                except Exception as e:
                    self.error(f"CAN设备关闭失败: {e}")

    def analyze_script_parts(self, content):
        """解析状态、动作、响应"""
        self._analyze_state(content)
        self._analyze_action(content)
        self._analyze_response(content)


    def _analyze_state(self, content):
        self.log("执行“状态”")
        block = self._extract_block(content, "状态")
        if block:
            self._process_block_lines(block)

    def _analyze_action(self, content):
        self.log("执行“动作”")
        block = self._extract_block(content, "动作")
        if block:
            self._process_block_lines(block)

    def _analyze_response(self, content):
        self.log("执行“响应”")
        block = self._extract_block(content, "响应")
        if block:
            self._process_block_lines(block)

    def _extract_block(self, content, block_name):
        """提取指定块内容"""
        pattern = rf'{block_name}[:：]\s*\n((?:[ \t]+.+?(?:\n|$))+)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if not match:
            self.log(f"未找到 {block_name} 块")
            return []

        block_text = match.group(1)
        lines = [line.strip() for line in block_text.split('\n')]
        return [line for line in lines if line]



    def _process_block_lines(self, lines):
        """
        逐行处理一个块中的内容，仅对原始脚本指令（输出(...)、采集(...)、等待(...)）执行动作
        忽略以 '→' 开头的说明性行
        """
        rules = [
            (r'^输出\(([^)]+)\)', lambda m: self.log("SndOK")),
            (r'^采集\(([^)]+)\)', lambda m: self.log("RcvOK")),
            (r'^等待\((\d+)\)', lambda m: self._delay_ms(int(m.group(1)))),
        ]

        for line in lines:
            line = line.strip()
            if not line or line.startswith('→') or line.startswith('-'):
                # 跳过空行、说明行（→）或列表符号（─）
                continue

            matched = False
            for pattern, action in rules:
                match = re.match(pattern, line)
                if match:
                    action(match)
                    matched = True
                    break
            if not matched:
                self.log(f"未识别的指令: {line}")

    def _delay_ms(self, milliseconds):
        """延迟指定毫秒数"""
        seconds = milliseconds / 1000.0
        self.log(f"Wait {milliseconds} ms")
        time.sleep(seconds)

    def run(self):
        """一键运行全流程"""
        self.log(f"开始解析日志文件: {self.log_path}")
        try:
            self.load_log()
            self.split_test_cases()
            self.parse_all_cases()
            self.log("日志解析执行完成。")
        except Exception as e:
            self.error(f"解析过程中发生未预期异常: {e}")
            raise


# ==================== 使用示例 ====================
if __name__ == "__main__":

    # 设置你的日志文件路径
    log_file_path = "TestcaseCollection/004_data.log"  # ← 修改为你的实际路径

    # 创建解析器并运行
    parser = LogParser(log_file_path)
    parser.run()
