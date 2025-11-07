import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import mylog
import json
import time
import re
from typing import List, Dict, Any, Tuple, Optional
from CanDataProcessing.find_can_from_csv import create_can_data_by_signal
import logging

class TestCaseProcessor:
    """
    测试用例处理器：解析 JSON 测试用例文件 → 过滤 → 抽取 → 输出结构化信息
    使用 mylog 模块记录日志，替代 print 输出
    """

    # ---------- 默认配置（可在实例化时覆盖） ----------
    # 需要保留的关键字（严格匹配大小写）
    DEFAULT_TARGET_FUNCS = {"采集", "输出", "发送", "等待", "启用", "禁用"}
    # 前缀匹配关键字（支持前缀如 “测试台CAN”、“台架CAN” 等）
    DEFAULT_PREFIXES = ["测试台CAN", "台架CAN", "CAN"]
    # --------------------------------------------------

    def __init__(
        self,
        json_file_path: str,
        target_funcs: Optional[set] = None,
        prefix_patterns: Optional[List[str]] = None,
        logger_name: str = "processor",  # 日志标识名，用于区分不同 logger 实例
    ):
        """
        初始化处理器
        :param json_file_path: JSON 测试用例文件路径
        :param target_funcs: 要提取的目标函数集合，默认为 DEFAULT_TARGET_FUNCS
        :param prefix_patterns: 函数调用前缀列表，用于正则匹配（如 "测试台CAN"）
        :param logger_name: 日志 logger 的唯一名称，用于 mylog 管理
        """
        self.json_file_path = json_file_path
        self.target_funcs = target_funcs or self.DEFAULT_TARGET_FUNCS
        self.prefix_patterns = prefix_patterns or self.DEFAULT_PREFIXES
        self.logger_name = logger_name
        self.total_cases = 0          # 总用例数
        self.processed_count = 0      # 已处理用例数



        # 初始化日志器，确保日志目录和配置已就绪
        mylog.setup_logger(
            logger_name=self.logger_name,
            log_dir="./logs/testcase",      # 日志保存路径
            log_prefix="testcase",          # 日志前缀名称
            level=logging.INFO,
            clear_old = True,
            use_timestamp=False
        )

    # ----------------------------------------------------------------------
    # 入口 & 文件读取
    # ----------------------------------------------------------------------
    def process(self) -> None:
        """遍历所有用例，逐条处理（已移除 CAN 设备初始化/关闭）"""
        data = self._load_json_data()
        if not data:
            return

        self.total_cases = len(data)

        # === 已移除 CAN 初始化 ===

        # 开始处理每个用例
        for idx, case in enumerate(data):
            self._process_single_case(case, idx + 1)

        # === 已移除 CAN 关闭 ===

    def _load_json_data(self) -> Optional[List[Dict[str, Any]]]:
        """
        从指定路径加载 JSON 数据
        :return: 解析后的用例列表，失败返回 None
        """
        try:
            with open(self.json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    mylog.error(self.logger_name, "错误：JSON 顶层结构应为用例列表（list）")
                    return None
                return data
        except FileNotFoundError:
            mylog.error(self.logger_name, f"错误：文件未找到 → {self.json_file_path}")
        except json.JSONDecodeError as e:
            mylog.error(self.logger_name, f"错误：JSON 解析失败 → {e}")
        except Exception as e:
            mylog.error(self.logger_name, f"未预期错误 → {e}")
        return None

    # ----------------------------------------------------------------------
    # 单条用例处理
    # ----------------------------------------------------------------------
    def _process_single_case(self, case: Dict[str, Any], case_index: int) -> None:
        """
        完整处理单条测试用例：
        - 校验行数（必须为 4 行）
        - 提取四类关键行（测试用例 / 状态 / 动作 / 响应）
        - 环境过滤（仅处理含“台架”的用例）
        - 打印结构并抽取脚本
        """
        rows = case.get("rows", [])
        if len(rows) != 4:
            mylog.warning(self.logger_name, f"[用例 {case_index}] 行数异常（应为 4 行），跳过...")
            return

        # 按 *类型 查找四类行
        test_case_row = self._find_row_by_type(rows, "*类型", "测试用例")
        status_row    = self._find_row_by_type(rows, "*类型", "状态")
        action_row    = self._find_row_by_type(rows, "*类型", "动作")
        response_row  = self._find_row_by_type(rows, "*类型", "响应")

        # 检查必要行是否缺失
        missing = [(name, row) for name, row in
                   [("测试用例", test_case_row), ("状态", status_row),
                    ("动作", action_row), ("响应", response_row)]
                   if row is None]
        if missing:
            for name, _ in missing:
                mylog.warning(self.logger_name, f"[用例 {case_index}] 缺少 【{name}】 行，跳过...")
            return

        # 提取基本信息
        case_id   = test_case_row.get("*用例编号", "未知")
        level1    = test_case_row.get("*一级功能", "未知")
        level2    = test_case_row.get("二级功能", "未知")
        test_env  = test_case_row.get("*测试环境", "")

        mylog.info(self.logger_name, f"=== 开始处理 用例 {case_id} ===")
        mylog.info(self.logger_name, f"功能：{level1} - {level2}")

        # 环境过滤：仅处理包含 “台架” 的用例
        if "台架" not in test_env:
            mylog.info(self.logger_name, f"测试环境：{test_env} （不含台架），跳过该用例")
            mylog.info(self.logger_name, "")  # 添加空行分隔（日志中用于可读性）
            return

        mylog.info(self.logger_name, f"测试环境：{test_env} （含台架），继续处理")

        # 输出结构信息并抽取脚本
        self._print_case_structure(status_row, action_row, response_row)
        self._extract_and_print_scripts(status_row, action_row, response_row)

        # 增加已处理用例计数
        self.processed_count += 1

        # 添加延时
        # time.sleep(0.5)

    # ----------------------------------------------------------------------
    # 辅助工具
    # ----------------------------------------------------------------------
    @staticmethod
    def _find_row_by_type(rows: List[Dict[str, Any]], key: str, value: str) -> Optional[Dict[str, Any]]:
        """
        在 rows 中查找指定字段等于给定值的第一条记录
        :param rows: 行数据列表
        :param key: 要匹配的字段名，如 "*类型"
        :param value: 匹配的目标值，如 "测试用例"
        :return: 匹配的字典或 None
        """
        return next((r for r in rows if r.get(key) == value), None)

    def _print_case_structure(self, status_row: Dict[str, Any],
                              action_row: Dict[str, Any],
                              response_row: Dict[str, Any]) -> None:
        """
        使用日志输出 “状态‑动作‑响应” 的描述信息
        """
        mylog.info(self.logger_name, "  └─ 状态   : " + status_row.get("描述", "无"))
        mylog.info(self.logger_name, "  └─ 动作   : " + action_row.get("描述", "无"))
        mylog.info(self.logger_name, "  └─ 响应   : " + response_row.get("描述", "无"))

    # ----------------------------------------------------------------------
    # 脚本抽取核心
    # ----------------------------------------------------------------------
    def _extract_and_print_scripts(self,
                                   status_row: Dict[str, Any],
                                   action_row: Dict[str, Any],
                                   response_row: Dict[str, Any]) -> None:
        """
        从三行（状态/动作/响应）的“测试脚本”字段中提取目标函数调用
        使用正则匹配，按行顺序输出解析结果，并对“采集”和“输出”生成 CAN 数据
        """
        rows = [("状态", status_row), ("动作", action_row), ("响应", response_row)]
        aggregated: List[Tuple[str, List[Tuple[str, str]]]] = []

        for row_type, row in rows:
            script_raw = row.get("测试脚本", "")
            calls = self._extract_target_calls(script_raw, self.target_funcs, self.prefix_patterns)
            if calls:
                aggregated.append((row_type, calls))

        if not aggregated:
            mylog.info(self.logger_name, "  └─ 脚本抽取结果：未发现目标函数（采集/输出/发送/等待）")
            return

        mylog.info(self.logger_name, "  └─ 脚本解析结果：")
        for row_type, calls in aggregated:
            mylog.info(self.logger_name, f"      {row_type}:")
            for func, args in calls:
                mylog.info(self.logger_name, f"          {func}({args})")

                # 仅对 "输出" 和 "采集" 生成 CAN 数据（如果未来需要保留生成日志，可保留此块）
                if func in {"输出", "采集"}:
                    self._generate_can_data_from_call(func, args)

            mylog.info(self.logger_name, "")  # 添加空行分隔（日志中用于可读性）

    @staticmethod
    def _extract_target_calls(
        script: str,
        target_funcs: set,
        prefix_patterns: List[str],
    ) -> List[Tuple[str, str]]:
        """
        正则提取目标函数调用，返回 [(函数名, 参数), ...]
        :param script: 原始脚本字符串
        :param target_funcs: 目标函数集合（严格大小写匹配）
        :param prefix_patterns: 可选前缀列表，如 ["测试台CAN", "台架CAN"]
        :return: 匹配到的函数调用列表
        """
        if not script or not isinstance(script, str):
            return []

        # 构建前缀正则
        prefix_regex = ""
        if prefix_patterns:
            escaped = [re.escape(p) for p in prefix_patterns]
            prefix_regex = f"(?:{'|'.join(escaped)})?"  # 非捕获组，可选

        # 函数名正则（严格匹配）
        func_regex = "|".join(map(re.escape, target_funcs))

        # 完整匹配模式：前缀?函数名(参数)
        pattern = re.compile(
            rf"{prefix_regex}({func_regex})\s*\(\s*(?P<args>[^)]*?)\s*\)",
        )

        calls: List[Tuple[str, str]] = []
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            match = pattern.search(stmt)
            if match:
                func = match.group(1)
                args = match.group("args").strip()
                calls.append((func, args))
        return calls

    def _generate_can_data_from_call(self, func: str, arg: str) -> None:
        """
        解析“输出”或“采集”函数的参数，生成对应的 CAN 数据帧，并打印合并的报文信息。
        支持格式：报文ID.信号名,值  例如：4C1.HUD_Mode_Settings_S,2
        """
        match = re.search(r'([0-9A-F]+)\.([a-zA-Z0-9_]+)\s*,\s*(\d+)', arg)
        if not match:
            mylog.warning(self.logger_name, f"      警告：无法解析参数 → {arg}")
            return
    
        message_id, signal_name_en, enum_value_str = match.groups()
        enum_value = int(enum_value_str)
    
        try:
            result = create_can_data_by_signal(message_id, signal_name_en, enum_value)
            if result["success"]:
                # 根据 func 类型区分输出或采集
                prefix = "输出" if func == "输出" else "采集"
                mylog.info(self.logger_name, 
                          f"          → {prefix}CAN报文 ID: {result['message_id_str']} | "
                          f"发送类型: {result['message_type']} | "
                          f"周期时间: {result['cycle_time']} ms | "
                          f"生成CAN数据: {result['can_data_str']}")
            else:
                mylog.warning(self.logger_name, f"          → 信号解析失败: {result['message_id_str']}.{result['signal_name_en']}")
        except Exception as e:
            mylog.error(self.logger_name, f"          → 生成CAN数据失败: {e}")



# ----------------------------------------------------------------------
# 使用示例（直接运行本文件即可）
# ----------------------------------------------------------------------
if __name__ == "__main__":
    
    processor = TestCaseProcessor("TestcaseCollection/001_data.json")
    processor.process()
