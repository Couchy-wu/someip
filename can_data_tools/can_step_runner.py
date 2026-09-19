# -*- coding: utf-8 -*-
"""
can_data_tools.can_step_runner —— 日志中 CAN 步骤的执行（Mixin）
================================================================
职责：把用例日志里描述的输出 CAN / 采集 CAN 步骤真正送到总线上，
      并做超时等待、条件收集、结果回传等处理。

拆分背景：这两个方法（合计约 270 行）原先混在 case_log_parser 里，
          但它们的关注点是"执行"而非"解析"，单独成模块后：
            · case_log_parser.py   纯解析（文本 → 步骤流）
            · can_step_runner.py   步骤执行（步骤 → CAN 收发）
            · testcase_runner.py   编排（设备开关/暂停恢复/主循环 + 组合）

依赖约束：可依赖 can_core（设备操作）与 hudcore（日志）；不依赖界面层。
"""
import logging
import time

from can_core import device
from hudcore import logging_setup

LOGGER_NAME = "parser"


class CanStepRunnerMixin:
    """执行日志中描述的 CAN 收发步骤（由 LogParser 组合使用）。"""



    def _handle_output_can_with_context(self, lines, current_index):
        """
        处理 `输出(...)` 指令：
        - 解析枚举值（仅用于日志）
        - 读取紧随其后的 “→ 输出CAN报文 …” 行
        - 提取 ID、发送类型、数据、分配 index 以及周期/间隔参数
        - 调用 `device.Send_Can_Signal`
        - 修正：不再以 'result is not None' 作为成功唯一标准，避免周期信号被误判为失败
        """
        # 当前 CAN 设备是否已初始化（仅日志）
        # logging_setup.debug(LOGGER_NAME, f"当前 CAN 设备状态: {self.can_device is not None}")

        # 1. 解析枚举值（日志用）
        current_line = lines[current_index].strip()
        enum_match = re.match(r'^输出\([^,]+,\s*(\d+)\)', current_line)
        if not enum_match:
            logging_setup.error(LOGGER_NAME, "输出指令格式错误，未匹配到枚举值")
            return
        try:
            enum_value = int(enum_match.group(1))
        except ValueError:
            logging_setup.error(LOGGER_NAME, f"无效的枚举值: {enum_match.group(1)}")
            return

        # 2. 读取下一行的 CAN 报文描述
        if current_index + 1 >= len(lines):
            logging_setup.error(LOGGER_NAME, "缺少CAN报文参数：未找到下一行")
            return
        next_line = lines[current_index + 1].strip()
        if not next_line.startswith("→") or "输出CAN报文" not in next_line:
            logging_setup.error(LOGGER_NAME, "下一行未包含CAN报文参数（应以 → 开头）")
            return

        # 3. 提取分配 index（实际发送通道编号）
        index_match = re.search(r'分配index:\s*(\d+)', next_line)
        if not index_match:
            logging_setup.error(LOGGER_NAME, "未找到 '分配index' 字段，请检查日志格式")
            return
        try:
            index = int(index_match.group(1))
        except ValueError:
            logging_setup.error(LOGGER_NAME, f"无效的分配index: {index_match.group(1)}")
            return

        # 4. 提取 CAN ID
        id_match = re.search(r'ID:\s*0x([0-9A-Fa-f]+)', next_line)
        if not id_match:
            logging_setup.error(LOGGER_NAME, "未解析到CAN ID")
            return
        can_id = int(id_match.group(1), 16)

        # 5. 提取发送类型
        type_match = re.search(r'发送类型:\s*(\w+)', next_line)
        if not type_match:
            logging_setup.error(LOGGER_NAME, "未解析到发送类型")
            return
        signal_type = type_match.group(1).upper()
        valid_types = {"EVENT", "CYCLE", "CE"}
        if signal_type not in valid_types:
            logging_setup.error(LOGGER_NAME, f"不支持的发送类型: {signal_type}")
            return

        # 6. 提取 CAN 数据
        data_match = re.search(r'生成CAN数据:\s*(\[[^\]]*\])', next_line)
        if not data_match:
            logging_setup.error(LOGGER_NAME, "未解析到CAN数据")
            return
        try:
            data_str = data_match.group(1)
            data = [int(x.strip(), 16) for x in data_str[1:-1].split(',') if x.strip()]
            if not (1 <= len(data) <= 64):
                logging_setup.error(LOGGER_NAME, f"CAN数据长度非法: {len(data)} 字节")
                return
        except Exception as e:
            logging_setup.error(LOGGER_NAME, f"解析CAN数据失败: {e}")
            return

        # 7. 解析周期/间隔参数，生成 `cycle_ms` 供 Send_Can_Signal 使用
        cycle_ms = None
        if signal_type == "CYCLE":
            period_match = re.search(r'周期(?:时间)?:\s*(\d+)', next_line)
            if not period_match:
                logging_setup.error(LOGGER_NAME, "Cycle 类型需提供周期时间")
                return
            try:
                cycle_ms = int(period_match.group(1))
                if cycle_ms <= 0:
                    raise ValueError
            except Exception:
                logging_setup.error(LOGGER_NAME, "周期时间必须为正整数")
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
                    logging_setup.error(LOGGER_NAME, "CE 类型的周期时间格式错误，缺少 '/' 分隔符")
                    return
                ev_str, per_str = pair_str.split('/', 1)
                try:
                    event_ms = int(ev_str)
                    cycle_period_ms = int(per_str)
                except Exception:
                    logging_setup.error(LOGGER_NAME, "CE 类型的事件间隔或周期不是整数")
                    return
            else:
                ev_match = re.search(r'事件间隔:\s*(\d+)', next_line)
                per_match = re.search(r'周期:\s*(\d+)', next_line)
                if not ev_match or not per_match:
                    logging_setup.error(LOGGER_NAME, "CE 类型必须提供事件间隔和周期（或使用‘周期时间: a/b’）")
                    return
                try:
                    event_ms = int(ev_match.group(1))
                    cycle_period_ms = int(per_match.group(1))
                except Exception:
                    logging_setup.error(LOGGER_NAME, "CE 类型的事件间隔或周期不是整数")
                    return

            if event_ms <= 0 or cycle_period_ms <= 0:
                logging_setup.error(LOGGER_NAME, "CE 类型的事件间隔和周期必须均为正整数")
                return
            cycle_ms = f"{event_ms}/{cycle_period_ms}"

        # 获取 CAN 设备句柄
        if not hasattr(self, 'can_device') or self.can_device is None:
            logging_setup.error(LOGGER_NAME, "CAN设备未初始化，无法发送信号")
            return
        device_handle, channel_handles, _ = self.can_device
        chn = 0
        chn_handle = channel_handles[chn]

        # 调用发送函数
        try:
            result = device.Send_Can_Signal(
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
                logging_setup.debug(
                    LOGGER_NAME,
                    f"SndOK → 已启动发送 CAN ID: 0x{can_id:X} (index={index}) [信号枚举值={enum_value}]"
                )
            else:
                logging_setup.error(
                    LOGGER_NAME,
                    f"发送任务提交失败: CAN ID: 0x{can_id:X} (index={index})"
                )

            # 可选：调试用
            # logging_setup.debug(LOGGER_NAME, f"Send_Can_Signal 返回值: {result}")

        except Exception as e:
            logging_setup.error(
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
            logging_setup.error(LOGGER_NAME, "缺少采集参数：未找到下一行")
            return False
        next_line = lines[current_index + 1].strip()

        if not next_line.startswith("→") or "采集CAN报文" not in next_line:
            logging_setup.error(LOGGER_NAME, "下一行未包含采集CAN报文参数（应以 → 开头）")
            return False

        # 提取 CAN ID
        id_match = re.search(r'ID:\s*0x([0-9A-Fa-f]+)', next_line)
        if not id_match:
            logging_setup.error(LOGGER_NAME, "未解析到CAN ID")
            return False
        try:
            signal_id = int(id_match.group(1), 16)  # 仍需 int 用于传入（支持 int 或 str）
        except ValueError:
            logging_setup.error(LOGGER_NAME, f"无效的CAN ID: {id_match.group(1)}")
            return False

        # 提取 子ID 原始字符串
        sub_id_match = re.search(r'子ID:\s*([^|]+)', next_line)
        if not sub_id_match:
            logging_setup.error(LOGGER_NAME, "未解析到子ID")
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
                logging_setup.error(LOGGER_NAME, f"无法将子ID转为十六进制: {sub_id_raw}")
                return False

        # 提取 位域
        bit_match = re.search(r'位:\s*([^|]+)', next_line)
        if not bit_match:
            logging_setup.error(LOGGER_NAME, "未解析到位域")
            return False
        bit_position = bit_match.group(1).strip()

        # 提取 枚举值
        enum_match = re.search(r'枚举值:(\d+)', next_line)
        if not enum_match:
            logging_setup.error(LOGGER_NAME, "未解析到期望枚举值")
            return False
        try:
            expected_enum_value = int(enum_match.group(1))
        except ValueError:
            logging_setup.error(LOGGER_NAME, f"无效的枚举值: {enum_match.group(1)}")
            return False

        # 固定通道为 0（可根据实际扩展）
        channel = 0

        # 获取 CAN 设备句柄
        if not hasattr(self, 'can_device') or self.can_device is None:
            logging_setup.error(LOGGER_NAME, "CAN设备未初始化，无法接收信号")
            return False

        # 调用信号等待函数（sub_id 为字符串："No" 或 "0x..."）
        logging_setup.debug(LOGGER_NAME, f"RcvWait → 等待 CAN ID: 0x{signal_id:X}, 子ID={sub_id_raw}, 位={bit_position}, 期望枚举值={expected_enum_value}")
        received = device.wait_for_check_signal_by_bit_enum(
            signal_id=signal_id,
            sub_id=sub_id,  # 传入标准化字符串："No" 或 "0x..."
            bit_position=bit_position,
            expected_enum_value=expected_enum_value,
            channel=channel,
            timeout=2.0,
            check_interval=0.1
        )

        if received:
            logging_setup.debug(LOGGER_NAME, f"RcvOK → 已接收到满足条件的 CAN ID: 0x{signal_id:X}, 子ID={sub_id_raw}, 位={bit_position}, 值={expected_enum_value}")
            return True
        else:
            logging_setup.error(LOGGER_NAME, f"RcvFail → 未收到预期信号: ID=0x{signal_id:X}, 子ID={sub_id_raw}, 位={bit_position}, 期望枚举值={expected_enum_value}")
            return False
