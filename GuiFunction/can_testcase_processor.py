import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import mylog
import json
import time
import re
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from CanDataProcessing.find_can_from_csv import create_can_data_by_signal
import logging
import tkinter as tk
from tkinter import messagebox
import unicodedata


def _remove_hidden_control_chars(text: str) -> str:
    """
    删除可能出现在 JSON 字符串中的隐藏 Unicode 控制字符（如 U+202C、U+200B~U+200F、以及
    其它类别为 “Format” (Cf) 的字符），返回清理后的字符串。
    """
    # 过滤掉所有 “格式控制字符” 或者常见的不可见字符范围
    cleaned = ''.join(
        ch for ch in text
        if not (
            unicodedata.category(ch) == 'Cf'               # 通用的格式控制字符
            or 0x200B <= ord(ch) <= 0x200F                 # 零宽空格等
            or 0xFEFF == ord(ch)                           # 字节顺序标记 (BOM)
        )
    )
    return cleaned


class TestCaseProcessor:
    """
    测试用例处理器：解析 JSON 测试用例文件 → 过滤 → 抽取 → 输出结构化信息
    使用 mylog 模块记录日志，替代 print 输出
    """

    # ---------- 默认配置（可在实例化时覆盖） ----------
    # 需要保留的关键字（严格匹配大小写）
    DEFAULT_TARGET_FUNCS = {"采集", "输出", "发送", "等待", "启用", "测试台CANID禁用"}
    # 前缀匹配关键字（支持前缀如 “测试台CAN”、“台架CAN” 等）
    DEFAULT_PREFIXES = ["测试台CAN", "台架CAN", "CAN","测试台CANID"]
    # --------------------------------------------------

    def __init__(
        self,
        json_file_path: str,
        target_funcs: Optional[set] = None,
        prefix_patterns: Optional[List[str]] = None,
        logger_name: str = "processor",  # 日志标识名，用于区分不同 logger 实例
        use_main_thread_dialog: bool = True   #  是否强制在主线程弹框（默认 True，安全）
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
        self._use_main_thread_dialog = use_main_thread_dialog
        self._has_internal_error: bool = False   # 用来记录在 _generate_can_data_from_call 中捕获的异常

        # 同一 CAN ID 的累计帧缓存 + CAN ID → index 映射
        self._frame_cache: Dict[str, List[int]] = {}
        self._subid_written: set = set()
        self._canid_to_index: Dict[str, int] = {}
        self._signal_frame_cache: Dict[str, List[int]] = {}   # 信号唯一键 → 单信号帧

        # 初始化日志器，确保日志目录和配置已就绪
        mylog.setup_logger(
            logger_name=self.logger_name,
            log_dir="./logs/testcase",      # 日志保存路径
            log_prefix="testcase",          # 日志前缀名称
            level=logging.INFO,
            clear_old = True,
            use_timestamp=False,
            show_prefix=False
        )

    # ----------------------------------------------------------------------
    # 入口 & 文件读取
    # ----------------------------------------------------------------------
    def process(self) -> None:
        """遍历所有用例，逐条处理，出错时不中断，最后打印失败用例"""
        data = self._load_json_data()
        if not data:
            return

        self.total_cases = len(data)
        self.failed_cases = []  # 用于记录出错的用例

        for idx, case in enumerate(data):
            case_index = idx + 1
            try:
                self._process_single_case(case, case_index)
            except Exception as e:
                case_id = "未知"
                # 尽量提取用例编号
                try:
                    rows = case.get("rows", [])
                    test_case_row = self._find_row_by_type(rows, "*类型", "测试用例")
                    case_id = test_case_row.get("*用例编号", "未知")
                except:
                    pass  # 如果也出错，就保留“未知”

                self.failed_cases.append({
                    "index": case_index,
                    "case_id": case_id,
                    "error": str(e)
                })
                # 可选：在日志中记录完整 traceback
                mylog.error(self.logger_name, f"[用例 {case_id}] 解析时发生异常: {e}")

        # 将内部生成信息的异常也计入 failed_cases（方便后面统一判断）
        if self._has_internal_error:
            # 这里不关联具体的 case_id，直接标记为“内部错误”
            self.failed_cases.append({
                "index": "N/A",
                "case_id": "内部错误",
                "error": "在生成 CAN 数据时出现异常"
            })

        # === 所有用例处理完成后，打印汇总错误 ===
        if self.failed_cases:
            print("\n" + "="*10)
            print("❌ 以下测试用例解析失败：")
            print("="*10)
            for fail in self.failed_cases:
                print(f"❌ 用例 {fail['case_id']} (索引: {fail['index']}) → 错误: {fail['error']}")
            print(f"\n共 {len(self.failed_cases)} 个用例解析失败。")
        print("\n✅ 所有用例解析完成")

        # 内部辅助函数：弹框入口
        def _show_dialog():
            """实际弹窗的实现，放在内部函数方便主线程调度"""
            title = "解析完成"
            if self.failed_cases:
                msg = "已解析完成（解析过程中发现异常）"
            else:
                msg = "已解析完成（解析过程中未发现异常）"
            # 使用默认根窗口（已经在主程序里创建），不再自己 new Tk()
            messagebox.showinfo(title, msg)

        # 根据是否要求在主线程弹框决定调用方式
        if self._use_main_thread_dialog:
            root = tk._default_root   # 这是 Tkinter 自动缓存的唯一根窗口
            if root is None:
                # 仍然找不到根窗口时，退回直接弹框（不推荐但防止崩溃）
                _show_dialog()
            else:
                # 通过 after 把弹框任务放到根窗口的事件循环里执行
                root.after(0, _show_dialog)
        else:
            tmp_root = tk.Tk()
            _show_dialog()
            tmp_root.destroy()

    def _load_json_data(self) -> Optional[List[Dict[str, Any]]]:
        """
        从指定路径加载 JSON 数据，并在返回前删除隐藏的 Unicode 控制字符。
        """
        try:
            with open(self.json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                mylog.error(self.logger_name, "错误：JSON 顶层结构应为用例列表（list）")
                return None

            # 递归遍历 data，把所有字符串中的隐藏控制字符全部去掉
            def _clean_obj(obj: Any) -> Any:
                if isinstance(obj, dict):
                    return {k: _clean_obj(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_clean_obj(item) for item in obj]
                if isinstance(obj, str):
                    return _remove_hidden_control_chars(obj)   # 清除隐藏字符
                return obj

            data = _clean_obj(data)
        
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

        # --- 重置本用例专用的状态 ---
        self.signal_to_index: Dict[str, int] = {}        # 缓存：信号唯一键 → index
        self.next_index = 1                              # 下一个可用 index（从1开始）

        # 清空累计帧、子ID、CAN‑ID→index 映射
        self._frame_cache.clear()
        self._subid_written.clear()
        self._canid_to_index.clear()
        self._signal_frame_cache.clear()

        try:
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

            print(f"✅ 解析到测试用例 {case_id}")
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

        finally:
            # **无论本用例是否提前返回或抛异常，统一在这里清理缓存**
            self._frame_cache.clear()
            self._subid_written.clear()
            self._canid_to_index.clear()
            self._signal_frame_cache.clear()
            self.signal_to_index.clear()

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
        mylog.info(self.logger_name, "  └─ 脚本解析结果：")

        for row_type, row in rows:
            script_raw = row.get("测试脚本", "")
            calls = self._extract_target_calls(script_raw, self.target_funcs, self.prefix_patterns)
            if not calls:
                continue

            mylog.info(self.logger_name, f"      {row_type}:")
            for func, args in calls:
                mylog.info(self.logger_name, f"          {func}({args})")

                if func in {"输出", "采集"}:
                    self._generate_can_data_from_call(func, args)

                elif func == "禁用":
                    # 立即处理：解析 CAN ID 并查找已分配的 index
                    match = re.match(r'([0-9A-F]+)\.[^,]*', args.strip())
                    if match:
                        can_id = match.group(1)
                        # 查找所有属于该 CAN ID 的已注册信号的 index
                        indices = []
                        for sig_key, idx in self.signal_to_index.items():
                            msg_id = sig_key.split('.')[0]
                            if msg_id == can_id:
                                indices.append(idx)
                        indices = sorted(set(indices))  # 去重排序
                        indices_str = ','.join(map(str, indices)) if indices else ""

                        log_msg = f"测试台CANID禁用{can_id}，禁用对应index:{indices_str}"
                        mylog.info(self.logger_name, f"          {log_msg}")
                        # print(log_msg)  # 同时输出到控制台
                    else:
                        mylog.warning(self.logger_name, "          警告：无法解析禁用参数格式")

            mylog.info(self.logger_name, "")  # 空行分隔

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

        # 先清理潜在的隐藏控制字符
        script = _remove_hidden_control_chars(script)

        # 统一标点
        script = (script
            .replace('（', '(')           # 中文左括号 → 英文
            .replace('）', ')')           # 中文右括号 → 英文
            .replace('，', ',')           # 中文逗号 → 英文
            .replace('；', ';')           # 中文分号 → 英文
            # .replace('　', ' ')           # 全角空格 → 半角
            .strip()
        )

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
        解析“输出”或“采集”函数参数，生成CAN报文信息。
        - 采集：输出信号属性（ID/子ID/位/枚举值），不生成CAN数据
        - 输出：同一信号覆盖旧值，不同信号按ID（含子ID）进行OR合并，输出完整CAN数据及index
        """
        match = re.search(r'([0-9A-F]+)\.([a-zA-Z0-9_]+)\s*,\s*(\d+)', arg)
        if not match:
            mylog.warning(self.logger_name, f"      警告：无法解析参数 → {arg}")
            return
        message_id, signal_name_en, enum_value_str = match.groups()
        enum_value = int(enum_value_str)
        try:
            # 获取信号对应的完整CAN帧（8字节）
            result = create_can_data_by_signal(message_id, signal_name_en, enum_value)
            if not result["success"]:
                mylog.warning(self.logger_name,
                              f"          → 信号解析失败: {message_id}.{signal_name_en}")
                return
            # 提取基础信息
            message_id_str = result["message_id_str"]
            message_type   = result["message_type"]
            cycle_time_raw = result["cycle_time"]
            # 智能处理周期时间：CE类型保留"100/1000"格式，其他提取首个数值
            if pd.isna(cycle_time_raw) or not str(cycle_time_raw).strip():
                cycle_time = "未知"
            else:
                cycle_str = str(cycle_time_raw).strip()
                if message_type == "CE" and '/' in cycle_str:
                    cycle_time = cycle_str  # 保留双周期格式
                else:
                    match_cycle = re.search(r'\d+', cycle_str)
                    cycle_time = match_cycle.group(0) if match_cycle else "未知"

            can_id_key = message_id_str.lower()
            # ---------- 子 ID 处理 ----------
            sub_id_hex = result.get("sub_id_hex")                    
            # 合并时使用的唯一键：若有子 ID，则把子 ID 加入键值，子 ID 不同视为不同 ID
            merge_key = can_id_key if not sub_id_hex else f"{can_id_key}_{sub_id_hex}"   

            # ---------- 处理 “输出” ----------
            if func == "输出":
                # 记录子ID（仅首次写入同一 merge_key）
                if merge_key not in self._subid_written and sub_id_hex:   
                    self._subid_written.add(merge_key)                    

                # 缓存当前信号帧（覆盖同信号），同时保存子 ID 供后续合并判断
                signal_key = f"{message_id_str}.{signal_name_en}"
                self._signal_frame_cache[signal_key] = (            
                    result["can_data"].copy(),
                    sub_id_hex
                )                                                      

                # 合并同一 ID（含子 ID）下所有信号（按位 OR）
                merged_frame = [0] * len(result["can_data"])
                for key, (frm, sid) in self._signal_frame_cache.items():
                    # 只合并 **同一报文 ID 且子 ID 相同** 的信号
                    if key.startswith(f"{message_id_str}.") and sid == sub_id_hex:  
                        merged_frame = [c | n for c, n in zip(merged_frame, frm)]

                # 将合并结果写入缓存（使用 merge_key）
                self._frame_cache[merge_key] = merged_frame             

                # 分配 index（12D 挡位信号固定为 0，其余首次出现递增）
                if message_id == "12D" and signal_name_en == "BCMPower_Gear_12D_S":
                    index = 0
                else:
                    if merge_key in self._canid_to_index:              
                        index = self._canid_to_index[merge_key]        
                    else:
                        index = self.next_index
                        self._canid_to_index[merge_key] = index          
                        self.next_index += 1

                # 建立信号到 index 的映射（用于禁用等功能）
                self.signal_to_index[signal_key] = index

                # 输出日志
                can_data_hex = [f"0x{b:02X}" for b in merged_frame]
                log_msg = (
                    f"          → 输出CAN报文 ID: {message_id_str} | "
                    f"发送类型: {message_type} | "
                    f"周期时间: {cycle_time} ms | "
                    f"生成CAN数据: [{', '.join(can_data_hex)}] | "
                    f"分配index: {index}"
                )
                mylog.info(self.logger_name, log_msg)
                return

            # ---------- 处理 “采集” ----------
            if func == "采集":
                # 解析子ID显示值
                sub_id_raw = result.get("sub_id_raw")
                if pd.isna(sub_id_raw) or str(sub_id_raw).strip().upper() == 'NO':
                    sub_id_display = "No"
                else:
                    match_sub = re.search(r'0x[0-9A-F]+', str(sub_id_raw), re.IGNORECASE)
                    sub_id_display = match_sub.group(0).upper() if match_sub else "Unknown"
                # 获取位范围
                bit_position = result.get("bit", "未知")
                if bit_position == "未知" or bit_position is None:
                    bit_position = "未知"
                # 输出采集信息
                log_msg = (
                    f"          → 采集CAN报文 ID: {message_id_str} | "
                    f"子ID:{sub_id_display} | "
                    f"位:{bit_position} | "
                    f"枚举值:{enum_value}"
                )
                mylog.info(self.logger_name, log_msg)
                return
        except Exception as e:
            self._has_internal_error = True
            mylog.error(self.logger_name, f"          → 生成信息时异常: {e}")




# ----------------------------------------------------------------------
# 使用示例（直接运行本文件即可）
# ----------------------------------------------------------------------
if __name__ == "__main__":
    
    processor = TestCaseProcessor("TestcaseCollection/004_data.json")
    processor.process()
