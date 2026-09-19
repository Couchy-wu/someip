# -*- coding: utf-8 -*-
"""
can_data_tools.case_log_parser —— 用例日志解析（Mixin）
=====================================================
职责：把测试用例日志解析成可执行的步骤流（状态/动作/响应块），
      以及从日志中切分用例、读取用例 JSON 配置。

设计说明（为什么用 Mixin）：
  原 `testcase_runner.LogParser` 是 884 行的过程式大类，解析与执行职责混杂。
  现按关注点拆成两个 Mixin：
    · 本模块                       CaseLogParserMixin —— 日志解析（文本 → 步骤流）
    · can_step_runner.CanStepRunnerMixin  —— 执行日志中的 CAN 收发步骤
    · testcase_runner.TestcaseRunnerMixin —— 执行编排（设备开关、延时、暂停/恢复、状态机）
  由 `testcase_runner.LogParser(...)` 组合三者，
  对外接口与行为不变（既有 `from can_data_tools.testcase_runner import LogParser` 无需改动）。

依赖约束：可依赖 can_core（设备操作）与 hudcore（日志）；不依赖任何界面层。
"""
import json
import logging
import os
import re
import time

from can_core import device
from hudcore import logging_setup

# 全局 logger 名称
LOGGER_NAME = "parser"

# 是否自动开关 CAN 设备：本模块被导入时为 False（与拆分前一致）；
# 直接运行 testcase_runner.py 时，那里会把它置为 True。
ENABLE_AUTO_OPEN_CLOSE_CAN = False


class CaseLogParserMixin:
    """日志解析能力（由 LogParser 组合使用）。"""



    def load_log(self):
        """加载日志文件内容"""
        if not os.path.exists(self.log_path):
            error_msg = f"日志文件未找到: {self.log_path}"
            logging_setup.error(LOGGER_NAME, error_msg)
            raise FileNotFoundError(error_msg)

        with open(self.log_path, 'r', encoding='utf-8') as file:
            self.log_content = file.read()
        logging_setup.info(LOGGER_NAME, "文件加载成功！")

    def split_test_cases(self):
        """根据日志中的用例分隔符拆分测试用例"""
        logging_setup.info(LOGGER_NAME, "开始处理用例")
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
        logging_setup.info(LOGGER_NAME, f"共拆分出 {len(self.test_cases)} 个测试用例。")

    def has_script_result(self, case_content):
        """
        判断用例日志中是否包含“脚本解析结果”
        :param case_content: 用例日志文本
        :return: bool
        """
        return "脚本解析结果：" in case_content

    def parse_all_cases(self):
        """依次解析所有测试用例"""

        # logging_setup.debug(LOGGER_NAME, f"使用外部CAN设备资源: device={self.can_device[0]}, chn_handles={self.can_device[1]}, threads={self.can_device[2]}")

        if not self.test_cases:
            logging_setup.warning(LOGGER_NAME, "未检测到任何测试用例，请先调用 split_test_cases() 方法。")
            return

        # ========== 启动 CAN 设备 ==========
        if ENABLE_AUTO_OPEN_CLOSE_CAN:
            if self.can_device and self.can_device[0] is not None:
                logging_setup.info(LOGGER_NAME, "检测到外部传入的CAN设备，跳过自动初始化")
            else:
                try:
                    device_handle, channel_handles, receive_threads = device.Initialize_Canfd_Device(
                        device_type=device.ZCAN_USBCANFD_200U,
                        merge_receive=0
                    )
                    self.can_device = (device_handle, channel_handles, receive_threads)
                    logging_setup.info(LOGGER_NAME, "CAN设备已开启")
                except Exception as e:
                    logging_setup.error(LOGGER_NAME, f"CAN设备开启失败: {e}")
                    return

        # 提取 CAN 设备句柄
        device_handle = None
        channel_handles = None
        if self.can_device:
            device_handle, channel_handles, _ = self.can_device

        # 遍历并处理每个测试用例    
        try:
            total_cases = len(self.test_cases)

            # ---------- 外层循环：执行 total_test_rounds 轮完整测试 ----------
            for round_idx in range(1, self.total_test_rounds + 1):
                logging_setup.info(LOGGER_NAME, f"============开始第 {round_idx} 轮完整测试============")
                print(f"============开始第 {round_idx} 轮完整测试============", flush=True)

                if getattr(self, '_stop_event', False):
                    logging_setup.info(LOGGER_NAME, "收到中断信号，停止本轮测试。")
                    break

                for i, case in enumerate(self.test_cases):
                    if getattr(self, '_stop_event', False):
                        logging_setup.info(LOGGER_NAME, "收到中断信号，停止执行测试用例。")
                        break

                    case_id = case['id']

                    logging_setup.info(LOGGER_NAME, "=============================================")

                    # 读取对应的 JSON 配置（可能为空）
                    cfg = self._load_case_config(case_id)
                    # 清理/重新保存当前用例的缓存
                    self.current_case_config = cfg if cfg else {}
                    if cfg:
                        logging_setup.info(LOGGER_NAME,
                                   f"已加载 JSON 配置: 用例 '{case_id}' 对应的图标信息 ({len(cfg)} 条)")
                    else:
                        logging_setup.info(LOGGER_NAME,
                                   f"未找到用例 '{case_id}' 的 JSON 配置，继续按原逻辑执行用例。")

                    # 进入“未启用”前先设状态
                    if not self.has_script_result(case['content']):
                        self._set_state("等待")
                        logging_setup.info(LOGGER_NAME, "不存在脚本解析结果，跳过该用例")
                        print("不存在脚本解析结果，跳过该用例", flush=True)
                        continue

                    logging_setup.info(LOGGER_NAME, f"开始处理用例: {case_id}")
                    print(f"✅ 开始处理用例: {case_id}", flush=True)

                    executed = False
                    if self.has_script_result(case['content']):
                        logging_setup.info(LOGGER_NAME, f"存在脚本解析结果，开始执行测试（每个用例重复 {self.case_repeat_count} 次）")
                        print(f"存在脚本解析结果，开始执行测试（每个用例重复 {self.case_repeat_count} 次）", flush=True)

                        for rep in range(1, self.case_repeat_count + 1):
                            if getattr(self, '_stop_event', False):
                                logging_setup.info(LOGGER_NAME, f"第 {rep} 次检测前收到中断，停止执行。")
                                break

                            logging_setup.info(LOGGER_NAME, f"第 {rep} 次检测开始...")
                            print(f"第 {rep} 次检测开始...", flush=True)
                            try:
                                self.analyze_script_parts(case['content'])
                            except Exception as e:
                                logging_setup.error(LOGGER_NAME, f"第 {rep} 次检测执行异常: {e}")
                                print(f"第 {rep} 次检测执行异常: {e}", flush=True)
                            executed = True

                            # 每次重复后等待并清理（最后一次不等待）
                            if rep < self.case_repeat_count:
                                logging_setup.info(LOGGER_NAME,
                                           f"第 {rep} 次检测完成，等待{self.delay_between_repeats}秒后开始下一次...")
                                print(f"第 {rep} 次检测完成，等待{self.delay_between_repeats}秒后开始下一次...", flush=True)
                                if not self._safe_wait(self.delay_between_repeats):
                                    break
                                self._clear_can_channel(chn=0)
                                if getattr(self, '_stop_event', False):
                                    break

                        # 补全最后一次检测完成的日志
                        logging_setup.info(LOGGER_NAME, f"第 {self.case_repeat_count} 次检测完成，正在清理...")
                        print(f"第 {self.case_repeat_count} 次检测完成，正在清理...", flush=True)
                        self._clear_can_channel(chn=0)

                    else:
                        logging_setup.info(LOGGER_NAME, "不存在脚本解析结果，跳过该用例")
                        print("不存在脚本解析结果，跳过该用例", flush=True)
                        continue

                    # 用例间延迟
                    if self.test_cases:
                        self._set_state("等待")
                        logging_setup.info(LOGGER_NAME,
                                   f"用例 {case_id} 已完成，等待{self.delay_between_cases}秒后开始下一个用例...")
                        print(f"用例 {case_id} 已完成，等待{self.delay_between_cases}秒后开始下一个用例...", flush=True)
                        if not self._safe_wait(self.delay_between_cases):
                            break

                # 本轮完成，若非最后一轮则等待
                if round_idx < self.total_test_rounds:
                    self._set_state("等待")
                    logging_setup.info(LOGGER_NAME,
                               f"第 {round_idx} 轮测试完成，等待{self.delay_between_rounds}秒后开始下一轮...")
                    print(f"第 {round_idx} 轮测试完成，等待{self.delay_between_rounds}秒后开始下一轮...", flush=True)
                    if not self._safe_wait(self.delay_between_rounds):
                        break

        finally:
            # ========== 关闭 CAN 设备 ==========
            if ENABLE_AUTO_OPEN_CLOSE_CAN and hasattr(self, 'can_device') and self.can_device:
                device_handle, channel_handles, receive_threads = self.can_device
                try:
                    if device_handle is not None and channel_handles is not None and receive_threads is not None:
                        device.Close_Canfd_Device(device_handle, channel_handles, receive_threads)
                        logging_setup.info(LOGGER_NAME, "测试结束, 已自动关闭CAN设备")
                except Exception as e:
                    logging_setup.error(LOGGER_NAME, f"测试结束, 但自动关闭CAN设备失败: {e}")
            self.can_device = (None, None, None)

    def analyze_script_parts(self, content):
        """解析状态、动作、响应"""
        self._analyze_state(content)
        self._analyze_action(content)
        self._analyze_response(content)

    def _analyze_state(self, content):
        self._set_state("执行状态")
        logging_setup.debug(LOGGER_NAME, "执行“状态”")
        block = self._extract_block(content, "状态")
        if block:
            self._process_block_lines(block)

    def _analyze_action(self, content): 
        self._set_state("执行动作")
        logging_setup.debug(LOGGER_NAME, "执行“动作”")
        block = self._extract_block(content, "动作")
        if block:
            self._process_block_lines(block)

    def _analyze_response(self, content):
        self._set_state("执行响应")
        logging_setup.debug(LOGGER_NAME, "执行“响应”")
        block = self._extract_block(content, "响应")
        if block:
            self._process_block_lines(block)
        # 响应模块全部解析并触发完成后，延迟 2 秒（视为“触发响应中”）
        # print(LOGGER_NAME, "响应处理完成，进入 2 秒延时（触发响应中）")
        self._safe_wait(2)

    def _extract_block(self, content, block_name):
        """提取指定块内容"""
        pattern = rf'{block_name}[:：]\s*\n((?:[ \t]+.+?(?:\n|$))+)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if not match:
            logging_setup.debug(LOGGER_NAME, f"未找到 {block_name} 块")
            return []

        block_text = match.group(1)
        lines = [line.strip() for line in block_text.split('\n')]
        return [line for line in lines if line]

    def _process_block_lines(self, lines):
        """处理块内每一行指令，支持上下文感知，并支持暂停"""
        i = 0
        while i < len(lines):
            # 检查是否被中断
            if getattr(self, '_stop_event', False):
                logging_setup.info(LOGGER_NAME, "收到中断信号，停止处理指令。")
                break

            # 检查是否暂停：如果未 set（即已 clear），则阻塞等待
            while not self._pause_event.is_set():
                # logging_setup.debug(LOGGER_NAME, "处理流程已暂停，等待恢复...")
                time.sleep(0.1)  # 避免忙等待
                if getattr(self, '_stop_event', False):
                    logging_setup.info(LOGGER_NAME, "暂停期间收到中断信号，停止处理。")
                    break
            else:
                # 只有在未中断且未暂停时才继续处理下一行
                pass

            line = lines[i].strip()
            if not line or line.startswith('-') or line.startswith('→'):
                i += 1
                continue

            # 检测 “立刻截图” 指令（等价于键盘 a 键）
            if "立刻截图" in line:
                logging_setup.info(LOGGER_NAME, "检测到 ‘立刻截图’ 指令，触发截图回调。")
                if callable(getattr(self, "screenshot_callback", None)):
                    try:
                        # 交给外部回调执行实际保存，回调自行决定线程/GUI 处理
                        self.screenshot_callback()
                    except Exception as e:
                        logging_setup.error(LOGGER_NAME, f"截图回调异常: {e}")
                else:
                    logging_setup.warning(LOGGER_NAME, "未设置 screenshot_callback，已忽略 ‘立刻截图’。")
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

            # === 测试台CANID禁用 ===
            # 兼容 “测试台CANID禁用(32B.主ID禁用)” 这种括号形式
            disable_paren_match = re.match(r'^测试台CANID禁用\(([^)]+)\)', line)
            if disable_paren_match:
                can_id_desc = disable_paren_match.group(1).strip()
                # 这里仅记录日志，实际禁用逻辑视项目需求自行实现
                logging_setup.debug(LOGGER_NAME, f"Disable → 禁用 CAN ID 描述: {can_id_desc}")
                i += 1
                continue
            # 原有的 “禁用对应 index” 形式
            disable_match = re.match(
                r'^测试台CANID禁用[0-9A-F]+[，,]?\s*禁用对应index\s*:\s*(.+)$',
                line
            )
            if disable_match:
                indices_str = disable_match.group(1).strip()
                indices = [int(x.strip()) for x in re.split(r'[,\s]+', indices_str) if x.strip().isdigit()]
                device_handle = self.can_device[0] if self.can_device else None
                if device_handle is not None:
                    for idx in indices:
                        device.Remove_Auto_Send_By_Index(
                            device_handle=device_handle,
                            chn=0,              # 固定通道0
                            msg_type="canfd",    # 固定类型canfd
                            index=idx
                        )
                        logging_setup.debug(LOGGER_NAME, f"Disable → 禁用定时发送 index: {idx}")
                        time.sleep(0.2)  # 每次禁用后延迟 200ms，确保设备处理完成
                i += 1
                continue

            logging_setup.warning(LOGGER_NAME, f"未识别的指令: {line}")
            i += 1

    # 读取 ImageData.json 配置的辅助函数
    def _load_case_config(self, case_id: str) -> dict:
        """
        读取与当前日志同目录、同前缀的 *_ImageData.json*，
        并返回键为 ``case_id`` 的子字典。

        - 若找不到 JSON 文件 → 返回空 dict 并记录 warning；
        - 若 JSON 中不存在 ``case_id`` → 返回空 dict 并记录 info；
        - 只在成功得到非空字典时才在后续流程中使用。

        Returns
        -------
        dict
            对应用例的配置信息（可能为空）。
        """
        # 1️⃣ 计算 JSON 文件完整路径
        log_dir   = os.path.dirname(self.log_path)                         # 日志所在目录
        log_stem  = os.path.splitext(os.path.basename(self.log_path))[0]   # 如 xx_data
        json_name = log_stem.replace("_data", "_ImageData") + ".json"      # xx_ImageData.json
        json_path = os.path.join(log_dir, json_name)

        # 2️⃣ 文件不存在 → 直接返回空 dict
        if not os.path.isfile(json_path):
            logging_setup.warning(LOGGER_NAME,
                         f"对应的 JSON 配置文件未找到: {json_path}")
            return {}

        # 3️⃣ 读取 JSON 并返回对应键的子字典
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                full_cfg = json.load(f)
            case_cfg = full_cfg.get(case_id, {})
            if not case_cfg:
                logging_setup.info(LOGGER_NAME,
                           f"JSON 中未找到键 '{case_id}'，返回空配置")
            return case_cfg
        except Exception as e:
            logging_setup.error(LOGGER_NAME,
                        f"读取 JSON 配置文件出错 ({json_path}): {e}")
            return {}
