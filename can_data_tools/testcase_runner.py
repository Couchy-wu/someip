import os
import re
import time
from can_core import device
from hudcore import logging_setup
import logging
import threading
import json

# 模块功能：基于日志文件驱动的 CAN 总线自动化测试用例执行器

# 是否自动开关CAN设备：根据执行方式智能判断
if __name__ == "__main__":
    ENABLE_AUTO_OPEN_CLOSE_CAN = True
    # 解析逻辑已移至 case_log_parser，直接运行本文件时同步打开其设备开关
    import can_data_tools.case_log_parser as _case_log_parser
    _case_log_parser.ENABLE_AUTO_OPEN_CLOSE_CAN = True
else:
    ENABLE_AUTO_OPEN_CLOSE_CAN = False

# 全局 logger 名称
LOGGER_NAME = "parser"

# 每个测试用例重复执行的次数（单轮内）
CASE_REPEAT_COUNT = 1 

# 总共执行多少轮完整测试
TOTAL_TEST_ROUNDS = 1  

# 解析与 CAN 步骤执行能力来自同包的 Mixin（见各模块说明）
from can_data_tools.can_step_runner import CanStepRunnerMixin      # noqa: E402
from can_data_tools.case_log_parser import CaseLogParserMixin      # noqa: E402


class TestcaseRunnerMixin:
    """用例执行编排：设备开关、延时、暂停/恢复、状态机、主循环。"""

    def __init__(self, log_path, device_handle=None, channel_handles=None, receive_threads=None, case_repeat_count=None, total_test_rounds=None):
        """
        初始化日志解析器
        :param log_path: 日志文件路径
        :param device_handle: 外部传入的设备句柄（可选）
        :param channel_handles: 外部传入的通道句柄列表（可选）
        :param case_repeat_count: 外部指定的重复次数（可选），优先级高于全局 CASE_REPEAT_COUNT
        :param total_test_rounds: 总共执行多少轮完整测试（可选）,优先级高级全局 TOTAL_TEST_ROUNDS
        """
        self.log_path = log_path
        self.log_content = ""
        self.test_cases = []
        self.can_device = (device_handle, channel_handles, receive_threads)

        self._stop_event = False    # 测试停止标识位
        self._pause_event = threading.Event()  # 初始为 Set（运行状态）
        self._pause_event.set()  # 默认不暂停，允许执行

        # 使用传入值或默认值
        self.case_repeat_count = case_repeat_count if case_repeat_count is not None else CASE_REPEAT_COUNT
        self.total_test_rounds = total_test_rounds if total_test_rounds is not None else TOTAL_TEST_ROUNDS

        # 当前工况记录，初始为“等待”
        self.current_state = "等待"      # 可取值：执行状态 / 执行动作 / 执行响应 / 等待        

        #  统一的延迟参数
        self.delay_between_repeats = 1          # 每次重复检测结束后的等待（秒）
        self.delay_between_cases   = 1          # 用例间的等待（秒）
        self.delay_between_rounds = 1          # 轮次之间的等待（秒）
        self.delay_after_disable  = 0.2        # 禁用 index 后的短暂等待（秒）  
        # 备注：响应模块触发完成后有2秒的延迟，该阶段视为“执行等待”      

        logging_setup.setup_logger(
            logger_name=LOGGER_NAME,
            log_dir="./logs",
            log_prefix="parser",
            level=logging.DEBUG,
            clear_old=True,           # 自动清理旧日志
            use_timestamp=True,       # 文件名带时间戳
            show_prefix=True          # 显示日志前缀（时间+级别）
        )
        # 用于在解析到“立刻截图”时回调 GUI 保存图像
        self.screenshot_callback = None  # 赋值后应为 callable，或保持 None


    def _clear_can_channel(self, chn=0):
        """
        清理指定 CAN 通道的定时发送列表
        :param chn: 通道编号
        """
        if not self.can_device:
            return
        device_handle, channel_handles, _ = self.can_device
        if device_handle is None or chn >= len(channel_handles):
            logging_setup.warning(LOGGER_NAME, f"无效的设备或通道编号: {chn}")
            return
        try:
            if device.Clear_Auto_Can_Send(device_handle, chn):
                logging_setup.info(LOGGER_NAME, f"已清除通道 {chn} 的定时发送列表")
            else:
                logging_setup.warning(LOGGER_NAME, f"清除通道 {chn} 定时发送列表失败")
        except Exception as e:
            logging_setup.error(LOGGER_NAME, f"清理定时发送列表时发生异常: {e}")

    def get_current_state(self): 
        """
        返回当前正处于的工况名称。
        """
        return self.current_state

    def _delay_ms(self, milliseconds):
        """延迟指定毫秒数，支持暂停和停止"""
        seconds = milliseconds / 1000.0
        logging_setup.debug(LOGGER_NAME, f"Wait {milliseconds} ms")
        self._safe_wait(seconds)

    def run(self):
        """一键运行全流程"""
        logging_setup.info(LOGGER_NAME, f"开始解析日志文件: {self.log_path}")
        try:
            self.load_log()
            self.split_test_cases()
            self.parse_all_cases()
            logging_setup.info(LOGGER_NAME, "日志解析执行完成。")
        except Exception as e:
            logging_setup.error(LOGGER_NAME, f"解析过程中发生未预期异常: {e}")
            raise


    def close_test(self):
        """
        中断并关闭正在进行的测试
        调用后会尝试关闭 CAN 设备及所有相关资源
        """
        logging_setup.info(LOGGER_NAME, "收到关闭测试请求，正在停止测试...")
        print("正在关闭测试...")

        # 清理内部标志，防止重复执行
        self._stop_event = True  # 假设我们用这个标志控制循环

        # 获取设备资源
        device_handle, channel_handles, receive_threads = self.can_device

        if device_handle is not None and channel_handles is not None and receive_threads is not None:
            try:
                device.Close_Canfd_Device(device_handle, channel_handles, receive_threads)
                logging_setup.info(LOGGER_NAME, "CAN设备已成功关闭")
            except Exception as e:
                logging_setup.error(LOGGER_NAME, f"关闭CAN设备时发生异常: {e}")
        else:
            logging_setup.warning(LOGGER_NAME, "未检测到有效的CAN设备资源，跳过关闭流程")

        # 可选：重置设备句柄
        self.can_device = (None, None, None)
        print("测试已关闭。")

    def _safe_wait(self, seconds):
        """
        安全等待：支持在等待期间响应暂停和停止信号
        :param seconds: 等待秒数（可为小数）
        """
        total_waited = 0.0
        step = 0.1  # 每次 sleep 0.1 秒，提高响应速度
        while total_waited < seconds:
            if getattr(self, '_stop_event', False):
                logging_setup.info(LOGGER_NAME, "等待期间收到停止信号，终止等待。")
                return False
            if not self._pause_event.is_set():
                # 暂停中，不增加等待时间，持续等待恢复
                time.sleep(0.1)
                continue
            # 正常等待
            time.sleep(step)
            total_waited += step
        return True


    def pause_test(self):
        """暂停测试流程，等待恢复"""
        if getattr(self, '_pause_event', None) is None:
            logging_setup.warning(LOGGER_NAME, "暂停功能未初始化，请检查 _pause_event 是否在 __init__ 中创建。")
            return
        self.current_state = "等待"
        self._pause_event.clear()  # 进入暂停状态
        logging_setup.info(LOGGER_NAME, "测试流程已暂停。调用 resume_test() 可恢复。")
        print("测试已暂停。")


    def resume_test(self):
        """恢复已暂停的测试流程"""
        if getattr(self, '_pause_event', None) is None:
            logging_setup.warning(LOGGER_NAME, "恢复功能未初始化。")
            return
        self.current_state = "等待"
        self._pause_event.set()  # 恢复运行
        logging_setup.info(LOGGER_NAME, "测试流程已恢复。")
        print("测试已恢复。")

    # 为外部（GUI）提供状态变化回调
    def set_state_callback(self, callback):
        """
        注册一个回调函数，当 ``current_state`` 发生改变时自动调用。
        callback 必须接受一个 ``str`` 参数（新的状态）。
        """
        self._state_callback = callback

    # 统一的状态更新入口，负责保存状态并触发回调
    def _set_state(self, new_state):
        """
        统一修改 ``self.current_state`` 并在有回调时通知 UI。
        """
        self.current_state = new_state
        # 若 GUI 已注册回调则立即调用（在同一线程里）
        if hasattr(self, "_state_callback") and self._state_callback:
            try:
                self._state_callback(new_state)
            except Exception as e:
                # 回调异常不应影响主流程，记录即可
                logging_setup.error(LOGGER_NAME,
                            f"状态回调异常: {e}")


class LogParser(CaseLogParserMixin, CanStepRunnerMixin, TestcaseRunnerMixin):
    """测试用例日志解析 + 执行器（三块能力组合，对外接口与拆分前一致）。

    解析     → case_log_parser.CaseLogParserMixin
    CAN 步骤 → can_step_runner.CanStepRunnerMixin
    执行编排 → 本模块 TestcaseRunnerMixin
    """


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # -------------------------------------------------
    # 1. 创建 LogParser 实例
    # -------------------------------------------------
    log_file_path = "TestcaseCollection/J12312_data.log"   # ← 请改为实际路径
    parser = LogParser(log_file_path)                         # 实例化

    # -------------------------------------------------
    # 2. 启动一个守护线程：每 100 ms 打印一次当前工况状态
    # -------------------------------------------------
    def _state_printer(p: LogParser):
        """在后台循环打印 parser 的 current_state，间隔 100 ms。"""
        while not getattr(p, "_stop_event", False):
            # 通过公开的 getter 获取状态，避免直接访问内部属性
            print(f"[状态监控] 当前工况状态: {p.get_current_state()}", flush=True)
            time.sleep(0.1)

    state_thread = threading.Thread(
        target=_state_printer,
        args=(parser,),
        daemon=True,          # 主程序退出时自动结束
        name="StatePrinter"
    )
    state_thread.start()

    # -------------------------------------------------
    # 3. 启动测试主流程（保持原有的后台运行方式）
    # -------------------------------------------------
    threading.Thread(target=parser.run, daemon=True, name="ParserRun").start()

    # # -------------------------------------------------
    # # 4. 交互式控制
    # # -------------------------------------------------

    # 回车 → 关闭测试并退出
    input()
    parser.close_test()
