import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import re
import time
import can_control


ENABLE_AUTO_OPEN_CLOSE_CAN = True  # 是否每次解析前后自动开关CAN设备


class LogParser:
    def __init__(self, log_path):
        """
        初始化日志解析器
        :param log_path: 日志文件路径
        """
        self.log_path = log_path
        self.log_content = ""
        self.test_cases = []  # 存储解析出的测试用例块

    def load_log(self):
        """加载日志文件内容"""
        if not os.path.exists(self.log_path):
            raise FileNotFoundError(f"日志文件未找到: {self.log_path}")

        with open(self.log_path, 'r', encoding='utf-8') as file:
            self.log_content = file.read()
            print("文件加载成功！")

    def split_test_cases(self):
        """根据日志中的用例分隔符拆分测试用例"""
        print("\n开始处理用例")
        # 使用正则匹配每个用例的开始标志
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
            print("未检测到任何测试用例，请先调用 split_test_cases() 方法。")
            return
    
        # 如果开关打开，在解析前打开 CAN 设备
        if ENABLE_AUTO_OPEN_CLOSE_CAN:
            device_handle, channel_handles, receive_threads = can_control.Initialize_Canfd_Device(
                device_type=can_control.ZCAN_USBCANFD_200U,
                merge_receive=0
            )
            print("CAN设备已开启")
            # 将设备句柄存入实例，供后续使用
            self.can_device = (device_handle, channel_handles, receive_threads)
        else:
            self.can_device = None  # 不启用时设为 None
    
        try:
            for case in self.test_cases:
                print(f"\n正在处理用例: {case['id']}")
                if self.has_script_result(case['content']):
                    print("存在脚本解析结果, 开始执行测试")
                    self.analyze_script_parts(case['content'])
                else:
                    print("不存在脚本解析结果，开始进行下一项")
                    continue
        finally:
            # 如果开关打开，在解析结束后关闭 CAN 设备
            if ENABLE_AUTO_OPEN_CLOSE_CAN and hasattr(self, 'can_device') and self.can_device:
                device_handle, channel_handles, receive_threads = self.can_device
                can_control.Close_Canfd_Device(device_handle, channel_handles, receive_threads)
                print("CAN设备已关闭")



    def analyze_script_parts(self, content):
        """解析脚本中的状态、动作、响应部分（按顺序调用三个独立函数）"""
        self._analyze_state(content)
        self._analyze_action(content)
        self._analyze_response(content)


    def _analyze_state(self, content):
        """只处理“状态”块内的行"""
        print("执行“状态”")
        state_block = self._extract_block(content, "状态")
        if state_block:
            self._process_block_lines(state_block)


    def _analyze_action(self, content):
        """只处理“动作”块内的行"""
        print("执行“动作”")
        action_block = self._extract_block(content, "动作")
        if action_block:
            self._process_block_lines(action_block)


    def _analyze_response(self, content):
        """只处理“响应”块内的行，并视为执行阶段完成"""
        print("执行“响应”")
        response_block = self._extract_block(content, "响应")
        if response_block:
            self._process_block_lines(response_block)


    def _extract_block(self, content, block_name):
        """
        提取“状态”、“动作”、“响应”块中的具体内容（缩进部分）
        """
        pattern = rf'{block_name}[:：]\s*\n((?:[ \t]+.+?(?:\n|$))+)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if not match:
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
            # 匹配 输出(...) 或 采集(...)
            (r'^输出\(([^)]+)\)', lambda match: print("SndOK")),
            (r'^采集\(([^)]+)\)', lambda match: print("RcvOK")),
            (r'^等待\((\d+)\)', lambda match: self._delay_ms(int(match.group(1))))
        ]

        for line in lines:
            line = line.strip()
            if not line or line.startswith('→') or line.startswith('-'):
                # 跳过空行、说明行（→）或列表符号（─）
                continue

            for pattern, action in rules:
                match = re.match(pattern, line)  # 使用 match 而非 search，确保从行首匹配
                if match:
                    action(match)
                    break



    def run(self):
        """一键运行日志解析全流程"""
        print(f"正在加载文件: {self.log_path}")
        self.load_log()
        self.split_test_cases()
        self.parse_all_cases()

    def _delay_ms(self, milliseconds):
        """延迟指定毫秒数"""
        seconds = milliseconds / 1000.0
        print(f"Wait {milliseconds} ms")
        time.sleep(seconds)
    



# 使用示例（可直接运行）
if __name__ == "__main__":
    # 设置日志文件路径
    log_file_path = "TestcaseCollection/004_data.log"  # 请替换为你的实际日志路径

    # 创建解析器实例
    parser = LogParser(log_file_path)

    # 运行解析
    parser.run()