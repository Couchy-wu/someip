import time
import sys
import os
import re

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import mylog

from can_testcase_processor import TestCaseProcessor
import mylog
import can_control


class CanTestCaseExecutor(TestCaseProcessor):
    """
    子类：在父类解析测试脚本的基础上,进行脚本运行
    """

    def _extract_and_print_scripts(self, status_row, action_row, response_row):
        # 先调用父类的解析逻辑（完成脚本抽取与CAN数据生成等）
        super()._extract_and_print_scripts(status_row, action_row, response_row)

        # 判断是否包含有效脚本内容（即是否有脚本被解析出来）
        has_status = self._has_calls(status_row)
        has_action = self._has_calls(action_row)
        has_response = self._has_calls(response_row)

        # 执行对应延时
        if has_status:
            mylog.info(self.logger_name, "  └─ 状态执行完毕，延迟 1 秒...")
            time.sleep(1)

        if has_action:
            mylog.info(self.logger_name, "  └─ 动作执行完毕，延迟 1 秒...")
            time.sleep(1)

        if has_response:
            mylog.info(self.logger_name, "  └─ 响应检查完毕，延迟 1 秒...")
            time.sleep(1)

    def _has_calls(self, row: dict) -> bool:
        """
        检查该行的测试脚本中是否能提取出目标函数调用
        """
        script_raw = row.get("测试脚本", "")
        calls = self._extract_target_calls(script_raw, self.target_funcs, self.prefix_patterns)
        return len(calls) > 0




if __name__ == "__main__":
    processor = CanTestCaseExecutor("TestcaseCollection/003_data.json")
    processor.process()
