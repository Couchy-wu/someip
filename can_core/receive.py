# -*- coding: utf-8 -*-
"""can_core.receive —— 设备/通道建立与接收

从 device.py 拆出，聚焦"接入设备并把报文收回来"：
  · 设备信息读写、名称设置
  · 接收线程、报文缓存与信号等待（含按位枚举等待）
  · 设备/通道初始化与关闭、USBCANFD 启动

共享状态（线程开关、接收缓存、锁、驱动实例）统一放在 can_core.can_state，
避免各模块各持一份全局变量导致状态不一致。
"""
import logging
import threading
import time
from ctypes import addressof, byref, c_char_p, memset, sizeof
from typing import List, Optional, Union

from hudcore import logging_setup

from .driver import (
    INVALID_DEVICE_HANDLE, ZCAN, ZCANFD_AUTO_TRANSMIT_OBJ, ZCAN_AUTO_TRANSMIT_OBJ,
    ZCAN_CHANNEL_INIT_CONFIG, ZCAN_DT_ZCAN_CAN_CANFD_DATA, ZCAN_STATUS_OK,
    ZCAN_TYPE_CAN, ZCAN_TYPE_CANFD, ZCAN_TYPE_MERGE, ZCAN_TransmitFD_Data,
    ZCAN_Transmit_Data, ZCAN_USBCANFD_200U,
)
from .can_state import state
from .bit_utils import calculate_bit_length, extract_bits_from_data


def Read_Device_Info(device_handle):
    " 读取设备信息 "
    info = state.zcanlib.GetDeviceInf(device_handle)
    # print("设备信息: \n%s" % info)
    can_number = info.can_num
    return can_number


def Set_Device_Name(device_handle):
    """设置自定义序列号（用于区分同型号的 CAN 卡）。

    注意：与原实现保持一致 —— 实际操作的是 state.handle（由 Initialize_Canfd_Device
    打开设备时写入的全局句柄），入参 device_handle 在原实现中同样未被使用。
    """

    ret = state.zcanlib.ZCAN_SetValue(state.handle, "0/set_cn", "A001".encode("utf-8")) 
    if ret == ZCAN_STATUS_OK:
        t = state.zcanlib.ZCAN_GetValue(state.handle, "0/get_cn/1")
        print("自定义序列号为："+ c_char_p(t).value.decode("utf-8"))
    return


def receive_thread(device_handle,chn_handle):
    " 接收线程 "
    # 方便打印对齐 --无实际作用
    CANType_width = len("CANFD加速    ")
    id_width = len(hex(0x1FFFFFFF))

    while state.thread_flag:      # 使用全局变量device_handle控制是否继续运行，可用于退出线程
        time.sleep(0.005)
        # 接收 CAN 帧
        # 查询当前有多少 CAN 帧未读取
        rcv_num = state.zcanlib.GetReceiveNum(chn_handle, ZCAN_TYPE_CAN)  # CAN
        if rcv_num:
            if rcv_num > 100 :      # 限制依次最多读取100帧，避免缓冲区溢出或处理延迟
                rcv_msg, rcv_num = state.zcanlib.Receive(chn_handle, 100,100)
            else :
                rcv_msg, rcv_num = state.zcanlib.Receive(chn_handle, rcv_num, 100)
            with state.print_lock:
                # 解析并打印 CAN 帧
                for msg in rcv_msg[:rcv_num]:
                    can_type = "CAN   "
                    frame = msg.frame
                    direction = "TX" if frame._pad & 0x20 else "RX"
                    frame_type = "扩展帧" if frame.can_id & (1 << 31) else "标准帧"
                    frame_format = "远程帧" if frame.can_id & (1 << 30) else "数据帧"
                    can_id = hex(frame.can_id & 0x1FFFFFFF)
                    # 数据字段处理
                    if frame.can_id & (1 << 30):
                        data = ""
                        dlc = 0
                    else:
                        dlc = frame.can_dlc
                        data = " ".join([f"{num:02X}" for num in frame.data[:dlc]])
                    # 在 CAN 帧接收部分，找到原始 data 的字节列表
                    raw_data = list(frame.data[:dlc])  # 转为 [0x01, 0x00, 0x00, 0x00] 形式
                    # 存储消息（包含原始列表）
                    with state.received_messages_lock:
                        state.received_messages.append({
                            'can_id': can_id,           # str: '0x12d'
                            'data_list': raw_data,      # list: [1, 0, 0, 0]
                            'dlc': dlc,
                            'timestamp': msg.timestamp,
                            'type': 'CAN',
                            'channel': chn_handle & 0xFF   # 提取通道号，如 CAN0 -> 0
                        })
                    # 打印输出
                    logging_setup.info("candata", f"[{msg.timestamp}] CAN{chn_handle & 0xFF} {can_type:<{CANType_width}}\t{direction} ID: {can_id:<{id_width}}\t{frame_type} {frame_format}"
                          f" DLC: {dlc}\tDATA(hex): {data}")

        # 接收 CANDU 帧
        rcv_canfd_num = state.zcanlib.GetReceiveNum(chn_handle, ZCAN_TYPE_CANFD)  # CANFD
        if rcv_canfd_num:
            if rcv_num > 100 :
                rcv_canfd_msgs, rcv_canfd_num = state.zcanlib.ReceiveFD(chn_handle, 100,100)
            else :
                rcv_canfd_msgs, rcv_canfd_num = state.zcanlib.ReceiveFD(chn_handle, rcv_canfd_num,100)
            with state.print_lock:
                for msg in rcv_canfd_msgs[:rcv_canfd_num]:
                    frame = msg.frame
                    brs = "加速" if frame.flags & 0x1 else "   "
                    can_type = "CANFD" + brs
                    direction = "TX" if frame.flags & 0x20 else "RX"
                    frame_type = "扩展帧" if frame.can_id & (1 << 31) else "标准帧"
                    frame_format = "远程帧" if frame.can_id & (1 << 30) else "数据帧"     # CANFD没有远程帧
                    can_id = hex(frame.can_id & 0x1FFFFFFF)
                    data = " ".join([f"{num:02X}" for num in frame.data[:frame.len]])
                    raw_data = list(frame.data[:frame.len])
                    with state.received_messages_lock:
                        state.received_messages.append({
                            'can_id': can_id,
                            'data_list': raw_data,
                            'dlc': frame.len,
                            'timestamp': msg.timestamp,
                            'type': 'CANFD',
                            'channel': chn_handle & 0xFF
                        })
                    logging_setup.info("candata", f"[{msg.timestamp}] CAN{chn_handle & 0xFF} {can_type:<{CANType_width}}\t{direction} ID: {can_id:<{id_width}}\t{frame_type} {frame_format}"
                          f" DLC: {frame.len}\tDATA(hex): {data}")

        # 接收 合并模式 帧
        rcv_merge_num = state.zcanlib.GetReceiveNum(device_handle, ZCAN_TYPE_MERGE)  # CANFD
        if rcv_merge_num:
            if rcv_num > 100 :
                rcv_merger_msgs, rcv_merge_num = state.zcanlib.ReceiveData(device_handle, 100,100)
            else :
                rcv_merger_msgs, rcv_merge_num = state.zcanlib.ReceiveData(device_handle, rcv_merge_num, 100)
            with state.print_lock:
                for msg in rcv_merger_msgs[:rcv_merge_num]:
                    if msg.dataType == ZCAN_DT_ZCAN_CAN_CANFD_DATA:
                        flag = msg.zcanfddata.flag
                        frame = msg.zcanfddata.frame
                        type = "CANFD" if flag.frameType else "CAN"
                        brs = "加速" if  (frame.flags & 0x1) else "   "
                        can_type = type + brs
                        direction = "TX" if msg.zcanfddata.flag.txEchoed else "RX"
                        frame_type = "扩展帧" if frame.can_id & (1 << 31) else "标准帧"
                        frame_format = "远程帧" if frame.can_id & (1 << 30) else "数据帧"
                        can_id = frame.can_id & 0x1FFFFFFF
                        data = " ".join([f"{num:02X}" for num in frame.data[:frame.len]])
                        raw_data = list(frame.data[:frame.len])
                        with state.received_messages_lock:
                            state.received_messages.append({
                                'can_id': hex(can_id),
                                'data_list': raw_data,
                                'dlc': frame.len,
                                'timestamp': msg.zcanfddata.timestamp,
                                'type': type,
                                'channel': msg.chnl
                            })
                        logging_setup.info("candata", f"[{msg.zcanfddata.timestamp}] CAN{msg.chnl} {can_type:<{CANType_width}}\t{direction} ID: {hex(can_id):<{id_width}}\t{frame_type} {frame_format}"
                        f" DLC: {frame.len}\tDATA(hex): {data}")


def check_signal_received(signal_id, expected_data_list, channel):
    """
    检查是否接收到指定 ID 和 data 的信号（data 为字节列表）

    :param signal_id: int 或 str，例如 0x123 或 "0x123"
    :param expected_data_list: list，例如 [0x01, 0x00, 0x00, 0x00]
    :param channel: int, 可选，指定通道号（如 0 表示 CAN0）
    :return: 返回bool，是否找到完全匹配的消息
    """
    def format_hex_bytes(data):
        """将字节列表格式化为 0x01, 0x02 形式的列表字符串"""
        return "[" + ", ".join(f"0x{x:02X}" for x in data) + "]"

    # 标准化 signal_id 为小写 hex 字符串
    if isinstance(signal_id, int):
        signal_id_str = hex(signal_id).lower()
    else:
        signal_id_str = str(signal_id).strip().lower()

    # 确保 expected_data_list 是 list 或 tuple
    if not isinstance(expected_data_list, (list, tuple)):
        raise ValueError("expected_data_list must be a list or tuple of bytes, e.g. [0x01, 0x00]")

    # 转为整数 list（避免传入 str 等类型）
    expected_data_list = [int(x) for x in expected_data_list]

    hex_expected_data = format_hex_bytes(expected_data_list)
    logging_setup.debug("candata", f"正在检查通道: {channel} 是否接收到信号: ID=0x{signal_id:X}, 数据={hex_expected_data}")

    with state.received_messages_lock:
        for msg in state.received_messages:
            # 先匹配 ID
            if msg['can_id'].lower() != signal_id_str:
                continue

            # 匹配 data
            if msg['data_list'] != expected_data_list:
                continue

            # 如果指定了 channel，还需匹配通道
            if channel is not None:
                if msg.get('channel') != channel:
                    continue

            # 完全匹配
            logging_setup.info("candata", f"成功检测到信号 0x{signal_id:X} 接收！")
            return True

    # 没找到匹配的消息 → 不打印任何日志
    return False


def wait_for_check_signal_received(
    signal_id: Union[int, str],
    expected_data_list: List[int],
    channel: int,
    timeout: float = 2.0,
    check_interval: float = 0.1
) -> bool:
    """
    等待指定信号（ID + 数据 + 通道）在超时时间内被接收到

    :param signal_id: CAN ID，如 0x123 或 "0x123"
    :param expected_data_list: 期望的数据字节列表，如 [0x01, 0x00]
    :param channel: 指定通道号（如 0 表示 CAN0）
    :param timeout: 检查时间，单位：秒
    :param check_interval: 每次检查间隔，单位：秒，默认 0.1 秒
    :return: bool，是否在超时前成功接收到匹配信号
    """
    start_time = time.time()
    end_time = start_time + timeout
    def format_hex_bytes(data):
        """将字节列表格式化为 0x01, 0x02 形式的列表字符串"""
        return "[" + ", ".join(f"0x{x:02X}" for x in data) + "]"
        
    expected_data_list = [int(x) for x in expected_data_list]
    hex_expected_data = format_hex_bytes(expected_data_list)
    # 日志：开始等待
    logging_setup.info("candata", f"开始等待信号: ID=0x{int(signal_id, 16) if isinstance(signal_id, str) else signal_id:X}, "
                          f"数据={hex_expected_data}, 通道={channel}, 等待时长: {timeout} s")

    while time.time() < end_time:
        # 调用原有的检查函数
        if check_signal_received(signal_id, expected_data_list, channel):
            return True  # 找到了，立即返回 True

        # 小间隔休眠，避免过度占用 CPU
        time.sleep(check_interval)

    # 超时仍未收到
    logging_setup.warning("candata", f"等待超时！未收到信号: ID=0x{signal_id:X}, 数据={hex_expected_data}, 通道={channel}")
    return False


def wait_for_check_signal_by_bit_enum(
    signal_id: Union[int, str],
    sub_id: str,
    bit_position: str,
    expected_enum_value: int,
    channel: int,
    timeout: float = 2.0,
    check_interval: float = 0.1
) -> bool:
    """
    等待并检查 CAN 信号，仅匹配调用开始后接收到的新消息
    时间基准：使用设备硬件时间戳 msg['timestamp']（如 87006154300），单位：微秒
    """
    # 解析 CAN ID
    if isinstance(signal_id, str):
        try:
            can_id_int = int(signal_id, 16)
        except ValueError:
            logging_setup.error("can", f"无效 CAN ID: {signal_id}")
            return False
    else:
        can_id_int = int(signal_id)

    can_id_hex_str = f"0x{can_id_int:X}"

    # 处理 sub_id
    check_sub_id = sub_id != "No"
    expect_sub_id_val = 0
    if check_sub_id:
        try:
            if sub_id.lower().startswith("0x"):
                expect_sub_id_val = int(sub_id, 16)
            else:
                expect_sub_id_val = int(sub_id)
        except ValueError:
            logging_setup.error("can", f"无效的 sub_id 格式: {sub_id}，应为 'No' 或 '0x...' 形式")
            return False

    # 计算位长度（日志用）
    signal_length = calculate_bit_length(bit_position)

    # --- 关键：获取当前最新的设备时间戳作为“起始点” ---
    start_device_ts = 0
    with state.received_messages_lock:
        if state.received_messages:
            # 取最新一条消息的时间戳作为当前设备时间参考
            start_device_ts = max(msg.get('timestamp', 0) for msg in state.received_messages)
        else:
            start_device_ts = 0  # 没有历史消息，接受所有

    logging_setup.info("candata", f"开始等待信号: ID={can_id_hex_str}, 子ID={sub_id}, "
                          f"位域={bit_position}({signal_length}bits), "
                          f"期望值={expected_enum_value}, 通道={channel}, 超时={timeout}s, "
                          f"起始设备时间戳={start_device_ts}")

    end_time = time.time() + timeout

    while time.time() < end_time:
        matched = False
        current_messages = []
        with state.received_messages_lock:
            # 获取所有消息（后续过滤时间）
            current_messages = list(state.received_messages)

        for msg in current_messages:
            ts = msg.get('timestamp', 0)
            if ts <= start_device_ts:
                continue  # 跳过调用前已存在的消息

            # CAN ID 匹配
            try:
                msg_id = int(msg['can_id'], 16)
            except (ValueError, TypeError):
                continue
            if msg_id != can_id_int:
                continue

            # 通道匹配
            if msg.get('channel') != channel:
                continue

            data_list = msg.get('data_list', [])
            if not isinstance(data_list, list) or len(data_list) == 0:
                continue

            # 子ID匹配
            if check_sub_id:
                if len(data_list) <= 0:
                    continue
                if data_list[0] != expect_sub_id_val:
                    continue

            # 提取目标位值
            actual_value = extract_bits_from_data(data_list, bit_position)
            if actual_value == -1:
                continue
            if actual_value != expected_enum_value:
                continue

            # ✅ 成功匹配：新消息且满足条件
            hex_data = " ".join(f"{b:02X}" for b in data_list)
            sub_id_log = "子ID=No" if sub_id == "No" else f"子ID=0x{expect_sub_id_val:x}"

            logging_setup.info("candata", f"✅ 条件满足! ID={can_id_hex_str}, 数据=[{hex_data}], "
                                  f"{sub_id_log}, {bit_position}={actual_value}, "
                                  f"消息时间戳={ts}, 相对延迟={(ts - start_device_ts) / 1000.0:.3f}ms")
            
            return True

        time.sleep(check_interval)

    # ❌ 超时
    logging_setup.warning("candata", f"❌ 等待超时! ID={can_id_hex_str}, 子ID={sub_id}, "
                             f"位={bit_position}, 期望值={expected_enum_value}")
    return False


def USBCANFD_Start(zcanlib, device_handle, chn):
    "启动通道"
    # 设置波特率（仲裁段 & 数据段）
    # ZCAN_SetValue ：设置设备属性
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/canfd_abit_baud_rate", "500000".encode("utf-8"))
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/canfd_dbit_baud_rate", "2000000".encode("utf-8"))
    if ret != ZCAN_STATUS_OK:
        logging_setup.error("candata", "Set CH%d baud failed!" % chn)
        return None

    # 自定义波特率    当产品波特率对采样点有要求，或者需要设置非常规波特率时使用   ---默认不管
    # ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/baud_rate_custom", "500Kbps(80%),2.0Mbps(80%),(80,07C00002,01C00002)".encode("utf-8"))
    # if ret != ZCAN_STATUS_OK:
    #     print("Set CH%d baud failed!" % chn)
    #     return None

    # 打开终端电阻
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/initenal_resistance", "1".encode("utf-8"))
    if ret != ZCAN_STATUS_OK:
        logging_setup.warning("candata", "Open CH%d resistance failed!" % chn)
        return None

    # 初始化通道
    chn_init_cfg = ZCAN_CHANNEL_INIT_CONFIG()
    chn_init_cfg.can_type = ZCAN_TYPE_CANFD  # USBCANFD 必须选择CANFD
    chn_init_cfg.config.canfd.mode = 0  # 0-正常模式 1-只听模式
    chn_handle = zcanlib.InitCAN(device_handle, chn, chn_init_cfg)
    if chn_handle is None:
        logging_setup.error("candata", "initCAN failed!" % chn)
        return None


    # 设置发送回显    USBCANFD系列老卡（无LIN口，设备白色标签值版本为V1.02即以下,包括V1.02）需要以下操作，否则由CAN报文结构体_pad结构体bit5标识，见Transmit_Test 发送示例
    # 禁用回显，避免收到自己发的消息（除非需要监控）
    ret = zcanlib.ZCAN_SetValue(device_handle,str(chn)+"/set_device_tx_echo","0".encode("utf-8"))   #发送回显设置，0-禁用，1-开启
    if ret != ZCAN_STATUS_OK:
        logging_setup.warning("candata", "Set CH%d  set_device_tx_echo failed!" %(chn))
        return None

    # 使能/关闭合并接收(startCAN 之前)    0-关闭 1-使能
    ret = zcanlib.ZCAN_SetValue(device_handle, str(0) + "/set_device_recv_merge", repr(state.enable_merge_receive))
    if ret != ZCAN_STATUS_OK:
        logging_setup.error("candata", "Open CH%d recv merge failed!" % chn)
        return None

    # 启动通道
    ret = zcanlib.StartCAN(chn_handle)
    if ret != ZCAN_STATUS_OK:
        logging_setup.error("candata", "startCAN failed!" % chn)
        return None

    return chn_handle


def Initialize_Canfd_Device(device_type=ZCAN_USBCANFD_200U, merge_receive=0):
    """初始化CAN FD设备
    
    Args:
        device_type:    设备类型,如ZCAN_USBCANFD_200U,(默认ZCAN_USBCANFD_200U)
        merge_receive:  是否启用合并接收,0-关闭,1-开启,(默认0)
        
    Returns:
        成功返回: (设备句柄，通道句柄列表, 接收线程列表)
        失败返回: (None, None, None)
    """
    
    print("开始运行can设备")

    # 打开设备
    state.handle = state.zcanlib.OpenDevice(device_type, 0, 0)
    if state.handle == INVALID_DEVICE_HANDLE:
        logging_setup.error("candata", "打开设备失败！")
        return None, None, None
    logging_setup.info("candata", "打开设备成功，设备句柄为: %d." % state.handle)
    
    # 获取设备信息
    can_number = Read_Device_Info(state.handle)

    # 设置自定义序列号--通常用于多卡同时使用时对卡进行区分
    # Set_Device_Name(handle)
    
    # 启动通道
    chn_handles = []
    threads = []
    
    # 遍历can_number个通道，依次调用USBCANFD_Start()函数初始化每个通道
    for i in range(can_number):  
        chn_handle = USBCANFD_Start(state.zcanlib, state.handle, i)
        if chn_handle is None:
            logging_setup.error("candata", "启动通道%d失败!" % i)
            return None, None, None
        chn_handles.append(chn_handle)  # 将通道句柄添加到列表中
        logging_setup.info("candata", f"打开通道{i}成功, 通道句柄为: %d." % chn_handle)
    
    # 接收线程创建策略
    if merge_receive == 1:   #   若开启合并接收，所有通道都由一个接收线程处理
        thread = threading.Thread(target=receive_thread, args=(state.handle, chn_handles[0]))    # 开启独立接收线程
        threads.append(thread)
        thread.start()
    else:                           #   若没有开启合并接收，所有通道的数据需要各自开一个线程接收
        for i in range(len(chn_handles)):
            thread = threading.Thread(target=receive_thread, args=(state.handle, chn_handles[i]))  # 开启独立接收线程
            threads.append(thread)
            thread.start()
    
    return state.handle, chn_handles, threads


def Close_Canfd_Device(handle, chn_handles, threads):
    """关闭CAN FD设备
    
    Args:
        handle:         设备句柄
        chn_handles:    通道句柄列表
        threads:        接收线程列表
    """
    
    print("结束运行can设备")

    # 停止接收线程
    state.thread_flag = False
    
    # 关闭接收线程
    if state.enable_merge_receive == 1:
        threads[0].join()
    else:
        for i in range(len(chn_handles)):
            threads[i].join()

    # 关闭通道
    for i in range(len(chn_handles)):
        ret = state.zcanlib.ResetCAN(chn_handles[i])
        if ret == 1:
            logging_setup.info("candata", f"关闭通道{i}成功")
        else:
            logging_setup.error("candata", f"关闭通道{i}失败")

    # 关闭设备
    ret = state.zcanlib.CloseDevice(handle)
    if ret == 1:
        logging_setup.info("candata", "关闭设备成功")
    else:
        logging_setup.error("candata", "关闭设备失败")

