'''
    支持的设备有 USBCANFD-100U mini   USBCANFD-100U/200U/400U/800U
'''

from zlgcan import *
import threading
import time
import os
import xml.etree.ElementTree as ET
from collections import deque
import mylog
import logging
from typing import Union, Optional, List

# 创建第一个日志：前缀为 "candata"
LOG_PATH = "./logs/can"
mylog.setup_logger(logger_name="candata", log_dir=LOG_PATH, log_prefix="candata", level=logging.INFO, clear_old=True)

# 全局变量
thread_flag = True              # 控制接收线程是否继续运行
print_lock = threading.Lock()   # 线程锁，只是为了打印不冲突
enable_merge_receive = 0        # 合并接收标识，（默认不使能）
transmit_type = 2               # 0-正常发送，2-自发自收

# 初始化ZCAN库
zcanlib = ZCAN()                # 全局初始化，供所有函数使用

# 全局缓存接收到的消息（用于后续检查）
received_messages = deque(maxlen=1000)  # 最多保存1000条消息
received_messages_lock = threading.Lock()


# # 定义设备类型映射表
# DEVICE_TYPE_MAP = {
#     "ZCAN_USBCANFD_100U": 42,
#     "ZCAN_USBCANFD_200U": 41,
#     "ZCAN_USBCANFD_400U": 76,
#     "ZCAN_USBCANFD_800U": 59,
#     "ZCAN_USBCANFD_MINI": 43,
# }

#读取设备信息
def Read_Device_Info(device_handle):
    " 读取设备信息 "
    info = zcanlib.GetDeviceInf(device_handle)
    # print("设备信息: \n%s" % info)
    can_number = info.can_num
    return can_number

# 设置自定义序列号  ---用于区分分同型号的CAN卡
def Set_Device_Name(device_handle):
    " 设置自定义序列号  ---用于区分分同型号的CAN卡 "
    ret = zcanlib.ZCAN_SetValue(handle, "0/set_cn", "A001".encode("utf-8")) 
    if ret == ZCAN_STATUS_OK:
        t = zcanlib.ZCAN_GetValue(handle, "0/get_cn/1")
        print("自定义序列号为："+ c_char_p(t).value.decode("utf-8"))
    return

# 接收线程
def receive_thread(device_handle,chn_handle):
    " 接收线程 "
    # 方便打印对齐 --无实际作用
    CANType_width = len("CANFD加速    ")
    id_width = len(hex(0x1FFFFFFF))

    while thread_flag:      # 使用全局变量device_handle控制是否继续运行，可用于退出线程
        time.sleep(0.005)
        # 接收 CAN 帧
        # 查询当前有多少 CAN 帧未读取
        rcv_num = zcanlib.GetReceiveNum(chn_handle, ZCAN_TYPE_CAN)  # CAN
        if rcv_num:
            if rcv_num > 100 :      # 限制依次最多读取100帧，避免缓冲区溢出或处理延迟
                rcv_msg, rcv_num = zcanlib.Receive(chn_handle, 100,100)
            else :
                rcv_msg, rcv_num = zcanlib.Receive(chn_handle, rcv_num, 100)
            with print_lock:
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
                    with received_messages_lock:
                        received_messages.append({
                            'can_id': can_id,           # str: '0x12d'
                            'data_list': raw_data,      # list: [1, 0, 0, 0]
                            'dlc': dlc,
                            'timestamp': msg.timestamp,
                            'type': 'CAN',
                            'channel': chn_handle & 0xFF   # 提取通道号，如 CAN0 -> 0
                        })
                    # 打印输出
                    mylog.info("candata", f"[{msg.timestamp}] CAN{chn_handle & 0xFF} {can_type:<{CANType_width}}\t{direction} ID: {can_id:<{id_width}}\t{frame_type} {frame_format}"
                          f" DLC: {dlc}\tDATA(hex): {data}")

        # 接收 CANDU 帧
        rcv_canfd_num = zcanlib.GetReceiveNum(chn_handle, ZCAN_TYPE_CANFD)  # CANFD
        if rcv_canfd_num:
            if rcv_num > 100 :
                rcv_canfd_msgs, rcv_canfd_num = zcanlib.ReceiveFD(chn_handle, 100,100)
            else :
                rcv_canfd_msgs, rcv_canfd_num = zcanlib.ReceiveFD(chn_handle, rcv_canfd_num,100)
            with print_lock:
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
                    with received_messages_lock:
                        received_messages.append({
                            'can_id': can_id,
                            'data_list': raw_data,
                            'dlc': frame.len,
                            'timestamp': msg.timestamp,
                            'type': 'CANFD',
                            'channel': chn_handle & 0xFF
                        })
                    mylog.info("candata", f"[{msg.timestamp}] CAN{chn_handle & 0xFF} {can_type:<{CANType_width}}\t{direction} ID: {can_id:<{id_width}}\t{frame_type} {frame_format}"
                          f" DLC: {frame.len}\tDATA(hex): {data}")

        # 接收 合并模式 帧
        rcv_merge_num = zcanlib.GetReceiveNum(device_handle, ZCAN_TYPE_MERGE)  # CANFD
        if rcv_merge_num:
            if rcv_num > 100 :
                rcv_merger_msgs, rcv_merge_num = zcanlib.ReceiveData(device_handle, 100,100)
            else :
                rcv_merger_msgs, rcv_merge_num = zcanlib.ReceiveData(device_handle, rcv_merge_num, 100)
            with print_lock:
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
                        with received_messages_lock:
                            received_messages.append({
                                'can_id': hex(can_id),
                                'data_list': raw_data,
                                'dlc': frame.len,
                                'timestamp': msg.zcanfddata.timestamp,
                                'type': type,
                                'channel': msg.chnl
                            })
                        mylog.info("candata", f"[{msg.zcanfddata.timestamp}] CAN{msg.chnl} {can_type:<{CANType_width}}\t{direction} ID: {hex(can_id):<{id_width}}\t{frame_type} {frame_format}"
                        f" DLC: {frame.len}\tDATA(hex): {data}")

# 检查是否接收到指定 ID 和 data 的信号
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
    mylog.debug("candata", f"正在检查通道: {channel} 是否接收到信号: ID=0x{signal_id:X}, 数据={hex_expected_data}")

    with received_messages_lock:
        for msg in received_messages:
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
            mylog.info("candata", f"成功检测到信号 0x{signal_id:X} 接收！")
            return True

    # 没找到匹配的消息 → 不打印任何日志
    return False

# 检查是否接收到指定 ID 和 data 的信号——支持超时等待
def wait_for_check_signal_received(
    signal_id: Union[int, str],
    expected_data_list: List[int],
    channel: int,
    timeout: float = 3.0,
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
    mylog.info("candata", f"开始等待信号: ID=0x{int(signal_id, 16) if isinstance(signal_id, str) else signal_id:X}, "
                          f"数据={hex_expected_data}, 通道={channel}，等待时长: {timeout}s")

    while time.time() < end_time:
        # 调用原有的检查函数
        if check_signal_received(signal_id, expected_data_list, channel):
            return True  # 找到了，立即返回 True

        # 小间隔休眠，避免过度占用 CPU
        time.sleep(check_interval)

    # 超时仍未收到
    mylog.warning("candata", f"等待超时！未收到信号: ID=0x{signal_id:X}, 数据={hex_expected_data}, 通道={channel}")
    return False

# 启动通道
def USBCANFD_Start(zcanlib, device_handle, chn):
    "启动通道"
    # 设置波特率（仲裁段 & 数据段）
    # ZCAN_SetValue ：设置设备属性
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/canfd_abit_baud_rate", "500000".encode("utf-8"))
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/canfd_dbit_baud_rate", "2000000".encode("utf-8"))
    if ret != ZCAN_STATUS_OK:
        mylog.error("candata", "Set CH%d baud failed!" % chn)
        return None

    # 自定义波特率    当产品波特率对采样点有要求，或者需要设置非常规波特率时使用   ---默认不管
    # ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/baud_rate_custom", "500Kbps(80%),2.0Mbps(80%),(80,07C00002,01C00002)".encode("utf-8"))
    # if ret != ZCAN_STATUS_OK:
    #     print("Set CH%d baud failed!" % chn)
    #     return None

    # 打开终端电阻
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/initenal_resistance", "1".encode("utf-8"))
    if ret != ZCAN_STATUS_OK:
        mylog.warning("candata", "Open CH%d resistance failed!" % chn)
        return None

    # 初始化通道
    chn_init_cfg = ZCAN_CHANNEL_INIT_CONFIG()
    chn_init_cfg.can_type = ZCAN_TYPE_CANFD  # USBCANFD 必须选择CANFD
    chn_init_cfg.config.canfd.mode = 0  # 0-正常模式 1-只听模式
    chn_handle = zcanlib.InitCAN(device_handle, chn, chn_init_cfg)
    if chn_handle is None:
        mylog.error("candata", "initCAN failed!" % chn)
        return None


    # 设置发送回显    USBCANFD系列老卡（无LIN口，设备白色标签值版本为V1.02即以下,包括V1.02）需要以下操作，否则由CAN报文结构体_pad结构体bit5标识，见Transmit_Test 发送示例
    # 禁用回显，避免收到自己发的消息（除非需要监控）
    ret = zcanlib.ZCAN_SetValue(device_handle,str(chn)+"/set_device_tx_echo","0".encode("utf-8"))   #发送回显设置，0-禁用，1-开启
    if ret != ZCAN_STATUS_OK:
        mylog.warning("candata", "Set CH%d  set_device_tx_echo failed!" %(chn))
        return None

    # 使能/关闭合并接收(startCAN 之前)    0-关闭 1-使能
    ret = zcanlib.ZCAN_SetValue(device_handle, str(0) + "/set_device_recv_merge", repr(enable_merge_receive))
    if ret != ZCAN_STATUS_OK:
        mylog.error("candata", "Open CH%d recv merge failed!" % chn)
        return None

    # 启动通道
    ret = zcanlib.StartCAN(chn_handle)
    if ret != ZCAN_STATUS_OK:
        mylog.error("candata", "startCAN failed!" % chn)
        return None

    return chn_handle

# 发送 CAN 报文
def Send_Can(chn_handle, stdorext, id, data, round):
    """发送 CAN 报文
    
    Args:
        chn_handle:     CAN 通道的句柄，表示已打开的 CAN 通道，用于标识发送数据的通道。
        stdorext:       布尔值（0 或 1），表示使用标准帧=0,还是扩展=1
        id:             CAN ID。
        data:           要发送的数据，应为一个可迭代对象（如列表或字节数组），包含最多 8 个字节。
        round:          设置can信号发送帧数

    Returns:
        返回实际发送成功的 CAN 报文
    """
    global transmit_type
    transmit_num = round     # 设置can信号发送帧数
    length = len(data)       # 自动计算数据长度

    # 确保数据长度不超过8字节（CAN帧限制）
    if length > 8:
        with print_lock:
            mylog.warning("candata", "警告：CAN数据长度为 %d，超过最大限制8字节，跳过发送。" % length)
        return None  
    
    # 创建ZCAN_Transmit_Data数组
    msgs = (ZCAN_Transmit_Data * transmit_num)()
    for i in range(transmit_num):
        msgs[i].transmit_type = transmit_type   # 0-正常发送，1-单次发发送，2-自发自收，3-单次自发自收
        msgs[i].frame.eff     = stdorext        # 0-标准帧，1-扩展帧，根据输入变量stdorext值决定
        msgs[i].frame.rtr     = 0               # 0-数据帧，1-远程帧
        msgs[i].frame.can_id  = id              # CAN ID
        msgs[i].frame.can_dlc = length          # 数据长度，实际发送的数据字节数（0~8）
        msgs[i].frame._pad |= 0x20              # 发送回显
        msgs[i].frame._res0 = 10                # res0，res1共同表示队列发送间隔(可以理解为一个short 2Byte分开传入)
        msgs[i].frame._res1 = 0         
        # 填充数据
        for j in range(length):
            msgs[i].frame.data[j] = data[j]

    ret = zcanlib.Transmit(chn_handle, msgs, transmit_num)
    # with print_lock: mylog.info("candata", "成功发送 %d 条CAN报文" % ret)
    return ret 

# 发送 CANFD 报文
def Send_Canfd(chn_handle, stdorext, id, data, round):
    """发送 CANFD 报文
    
    Args:
        chn_handle:     CAN 通道的句柄，表示已打开的 CAN 通道，用于标识发送数据的通道。
        stdorext:       布尔值（0 或 1），表示使用标准帧=0,还是扩展=1
        id:             CAN ID。
        data:           要发送的数据，应为一个可迭代对象（如列表或字节数组），包含最多 8 个字节。
        round:          设置can信号发送帧数

    Returns:
        返回实际发送成功的 CANFD 报文
    """
    global transmit_type 
    transmit_canfd_num = round
    length = len(data)     

    # 确保数据长度不超过64字节（CANFD帧限制）
    if length > 64:
        with print_lock:
            mylog.warning("candata", "警告：CAN数据长度为 %d，超过最大限制8字节，跳过发送。" % length)
        return None 
    
    # 创建ZCAN_Transmit_Data数组
    canfd_msgs = (ZCAN_TransmitFD_Data * transmit_canfd_num)()
    for i in range(transmit_canfd_num):
        canfd_msgs[i].transmit_type = transmit_type     # 0-正常发送，2-自发自收
        canfd_msgs[i].frame.eff     = stdorext          # 0-标准帧，1-扩展帧，根据输入变量stdorext值决定
        canfd_msgs[i].frame.rtr     = 0                 # 0-数据帧，1-远程帧
        canfd_msgs[i].frame.can_id = id                 # ID
        canfd_msgs[i].frame.len = length                # 长度
        canfd_msgs[i].frame.flags |= 0x20               # 发送回显
        canfd_msgs[i].frame.flags |= 0x0                # BRS 加速标志位：0不加速，1加速
        canfd_msgs[i].frame._res0 = 10
        for j in range(length):
            canfd_msgs[i].frame.data[j] = data[j]
    ret = zcanlib.TransmitFD(chn_handle, canfd_msgs, transmit_canfd_num)
    # with print_lock: mylog.info("candata", "成功发送 %d 条CANFD报文" % ret)
    return ret

# 清除已有的定时发送设置
def Clear_Auto_Can_Send(device_handle, chn):
    """清除指定通道的定时发送列表"""
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/clear_auto_send", "0".encode("utf-8"))
    if ret != ZCAN_STATUS_OK:
        mylog.warning("candata", "Clear CH%d USBCANFD AutoSend failed!" % chn)
        return False
    return True

# 使能所有定时发送报文
def Enable_Auto_Can_Send(device_handle, chn):
    """使能指定通道的所有定时发送任务"""
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/apply_auto_send", "0".encode("utf-8"))
    if ret != ZCAN_STATUS_OK:
        mylog.error("candata", "Apply CH%d USBCANFD AutoSend failed!" % chn)
        return False
    return True

# 定时发送 CAN 设置 
def Auto_Send_Can(device_handle, chn, stdorext, id, data, signal_cycle, index=0):
    """定时发送 CAN 报文
    # 每通道最多100条   老卡无法在使能队列发送 的情况下，启动定时发送！！
    
    Args:
        device_handle:  设备句柄
        chn:            通道号（如0, 1），表示操作的是设备上的第几个 CAN 通道
        stdorext:       标准帧=0,扩展帧=1
        id:             CAN ID。
        data:           要发送的数据，应为一个可迭代对象（如列表或字节数组），包含最多 8 个字节。
        signal_cycle:   发送周期，单位为 毫秒（ms），表示每隔多少毫秒发送一次 CAN 帧
        index:          定时发送序列号(默认0)

    Returns:
        函数成功执行后不返回任何值（即 return 隐式为 None），但会通过 ZCAN_SetValue 实际下发配置到硬件
    """
    # 构造定时发送对象和发送参数
    global transmit_type
    auto_can = ZCAN_AUTO_TRANSMIT_OBJ()
    length = len(data)          # 自动计算数据长度
    # 确保数据长度不超过8字节（CAN帧限制）
    if length > 8:
        with print_lock:
            mylog.warning("candata", "警告：CAN数据长度为 %d，超过最大限制8字节，跳过发送。" % length)
        return None
    memset(addressof(auto_can), 0, sizeof(auto_can))
    auto_can.index = index                          # 定时发送序列号 用于标记这条报文
    auto_can.enable = 1                             # 使能该条报文发送 0-关闭 1-使能
    auto_can.interval = signal_cycle                # 定时周期，单位ms
    # auto_can.obj 同 ZCAN_Transmit_Data结构体
    auto_can.obj.transmit_type = transmit_type      # 0-正常发送，1-单次发发送，2-自发自收，3-单次自发自收
    auto_can.obj.frame.can_id  = id                 # CAN ID
    auto_can.obj.frame.can_dlc = length             # 数据长度
    auto_can.obj.frame.eff     = stdorext           # 0-标准帧，1-扩展帧，根据输入变量stdorext值决定
    auto_can.obj.frame._pad |= 0x20                 # 发送回显
    # 填充数据
    for j in range(length):
        auto_can.obj.frame.data[j] = data[j]

    # 将发送任务配置写入到导通的定时发送列表中
    ret = zcanlib.ZCAN_SetValue(device_handle,str(chn)+"/auto_send",byref(auto_can))
    if ret != ZCAN_STATUS_OK:
        mylog.error("candata", "设置定时发送 CAN%d 失败!" % chn)
        return None

# 定时发送 CANFD 设置 
def Auto_Send_Canfd(device_handle, chn, stdorext, id, data, signal_cycle, index=0):
    """定时发送 CANFD 报文
    # 每通道最多100条   老卡无法在使能队列发送 的情况下，启动定时发送！！
    
    Args:
        device_handle:  设备句柄
        chn:            通道号（如0, 1），表示操作的是设备上的第几个 CAN 通道
        stdorext:       标准帧=0,扩展帧=1
        id:             CANFD ID。
        data:           要发送的数据，应为一个可迭代对象（如列表或字节数组)
        signal_cycle:   发送周期，单位为 毫秒（ms），表示每隔多少毫秒发送一次 CANFD 帧
        index:          定时发送序列号(默认0)

    Returns:
        函数成功执行后不返回任何值（即 return 隐式为 None），但会通过 ZCAN_SetValue 实际下发配置到硬件
    """
    # 构造定时发送对象和发送参数
    global transmit_type
    auto_canfd = ZCANFD_AUTO_TRANSMIT_OBJ()
    length = len(data)          
    # 确保数据长度不超过8字节（CANFD帧限制）
    if length > 64:
        with print_lock:
            mylog.warning("candata", "警告：CAN数据长度为 %d，超过最大限制64字节，跳过发送。" % length)
        return None

    memset(addressof(auto_canfd), 0, sizeof(auto_canfd))
    auto_canfd.index = index                           # 定时发送序列号 用于标记这条报文
    auto_canfd.enable = 1                              # 使能该条报文发送 0-关闭 1-使能
    auto_canfd.interval = signal_cycle                 # 定时周期，单位ms
    auto_canfd.obj.transmit_type = transmit_type       # 0-正常发送，1-单次发发送，2-自发自收，3-单次自发自收
    auto_canfd.obj.frame.can_id  = id                  # CANFD ID
    auto_canfd.obj.frame.len     = length              # 数据长度
    auto_canfd.obj.frame.eff     = stdorext            # 0-标准帧，1-扩展帧，根据输入变量stdorext值决定
    auto_canfd.obj.frame.flags |= 0x20                 # 发送回显
    # 填充数据
    for j in range(length):
        auto_canfd.obj.frame.data[j] = data[j]

    # 将发送任务配置写入到导通的定时发送列表中
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/auto_send_canfd", byref(auto_canfd))
    if ret != ZCAN_STATUS_OK:
        mylog.error("candata", "设置定时发送 CANFD%d 失败!" % chn)
        return None

# 关闭发送任务 即关闭定时发送
def Clear_Send_Task(device_handle,chn):
    "关闭发送任务 即关闭定时发送"
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/clear_auto_send", "0".encode("utf-8"))
    if ret != ZCAN_STATUS_OK:
        mylog.error("candata", "Clear CH%d AutoSend failed!" % (chn))
        exit(0)

# CAN设备初始化函数
def Initialize_Canfd_Device(device_type=ZCAN_USBCANFD_200U, merge_receive=0):
    """初始化CAN FD设备
    
    Args:
        device_type:    设备类型,如ZCAN_USBCANFD_200U,(默认ZCAN_USBCANFD_200U)
        merge_receive:  是否启用合并接收,0-关闭,1-开启,(默认0)
        
    Returns:
        成功返回: (设备句柄，通道句柄列表, 接收线程列表)
        失败返回: (None, None, None)
    """
    global handle, thread_flag
    
    print("开始运行can设备")

    # 打开设备
    handle = zcanlib.OpenDevice(device_type, 0, 0)
    if handle == INVALID_DEVICE_HANDLE:
        mylog.error("candata", "打开设备失败！")
        return None, None, None
    mylog.info("candata", "打开设备成功，设备句柄为: %d." % handle)
    
    # 获取设备信息
    can_number = Read_Device_Info(handle)

    # 设置自定义序列号--通常用于多卡同时使用时对卡进行区分
    # Set_Device_Name(handle)
    
    # 启动通道
    chn_handles = []
    threads = []
    
    # 遍历can_number个通道，依次调用USBCANFD_Start()函数初始化每个通道
    for i in range(can_number):  
        chn_handle = USBCANFD_Start(zcanlib, handle, i)
        if chn_handle is None:
            mylog.error("candata", "启动通道%d失败！" % i)
            return None, None, None
        chn_handles.append(chn_handle)  # 将通道句柄添加到列表中
        mylog.info("candata", f"打开通道{i}成功，通道句柄为: %d." % chn_handle)
    
    # 接收线程创建策略
    if merge_receive == 1:   #   若开启合并接收，所有通道都由一个接收线程处理
        thread = threading.Thread(target=receive_thread, args=(handle, chn_handles[0]))    # 开启独立接收线程
        threads.append(thread)
        thread.start()
    else:                           #   若没有开启合并接收，所有通道的数据需要各自开一个线程接收
        for i in range(len(chn_handles)):
            thread = threading.Thread(target=receive_thread, args=(handle, chn_handles[i]))  # 开启独立接收线程
            threads.append(thread)
            thread.start()
    
    return handle, chn_handles, threads

# 关闭CAN设备函数
def Close_Canfd_Device(handle, chn_handles, threads):
    """关闭CAN FD设备
    
    Args:
        handle:         设备句柄
        chn_handles:    通道句柄列表
        threads:        接收线程列表
    """
    global thread_flag
    
    print("结束运行can设备")

    # 停止接收线程
    thread_flag = False
    
    # 关闭接收线程
    if enable_merge_receive == 1:
        threads[0].join()
    else:
        for i in range(len(chn_handles)):
            threads[i].join()

    # 关闭通道
    for i in range(len(chn_handles)):
        ret = zcanlib.ResetCAN(chn_handles[i])
        if ret == 1:
            mylog.info("candata", f"关闭通道{i}成功")
        else:
            mylog.error("candata", f"关闭通道{i}失败")

    # 关闭设备
    ret = zcanlib.CloseDevice(handle)
    if ret == 1:
        mylog.info("candata", "关闭设备成功")
    else:
        mylog.error("candata", "关闭设备失败")

# 发送 CAN 或 CANFD 报文的通用接口————适用于事件型信号
def Send_Can_Or_Canfd(chn_handle, stdorext, id, msg_type, data, signal_cycle=None, send_count=1):
    """发送 CAN 或 CANFD 报文的通用接口————适用于事件型信号

    Args:
        chn_handle:     CAN 通道句柄
        stdorext:       帧格式类型，0-标准帧，1-扩展帧
        id:             CAN 报文 ID
        msg_type:       报文类型，'can' 表示 CAN 报文，'canfd' 表示 CANFD 报文（不区分大小写）
        data:           要发送的数据，支持列表、字节串等可迭代对象
        signal_cycle:   信号周期(单位ms)，为 None 表示非周期发送
        send_count:     发送次数，默认发1次

    Returns:
        实际成功发送的报文数量，出错时返回 None
    """
    mylog.debug("candata", f"开始以 {signal_cycle} ms频率连续发送 {send_count} 帧0x{id:X}")

    # 验证 msg_type
    if msg_type not in ['can', 'canfd']:
        with print_lock:
            mylog.error("candata", "错误：不支持的报文类型 '%s'，请使用 'can' 或 'canfd'" % msg_type)
        return None

    success_count = 0

    try:
        for i in range(send_count):
            if msg_type == 'can':
                result = Send_Can(chn_handle, stdorext, id, data, 1)    # 这里的1代表极短时间连发次数！直接写1就好
            elif msg_type == 'canfd':
                result = Send_Canfd(chn_handle, stdorext, id, data, 1)
            else:
                # 理论不会走到这里
                continue

            if result is not None and result > 0:
                success_count += result

            # 如果是周期发送，在每次发送后 sleep (除了最后一次)
            if signal_cycle is not None and i < send_count - 1:
                time.sleep(signal_cycle / 1000.0)  # 转为秒

        return success_count

    except Exception as e:
        with print_lock:
            mylog.error("candata", "发送报文时发生异常: %s" % str(e))
        return None      

# 定时发送 CAN 或 CANFD 报文的通用接口————适用于周期型信号
def Auto_Send_Can_Or_Canfd(device_handle, chn, stdorext, id, msg_type, data, signal_cycle, index=0, send_count=-1):
    """
    定时发送 CAN 或 CANFD 报文的通用接口————适用于周期型信号
    
    Args:
        device_handle:  设备句柄
        chn:            端口号，0或1
        stdorext:       帧格式：标准帧=0, 扩展帧=1
        id:             CAN/CANFD 报文 ID
        msg_type:       报文类型，'can' 表示 CAN，'canfd' 表示 CANFD
        data:           要发送的数据，可迭代对象（如列表或字节数组）
        signal_cycle:   发送周期，单位为毫秒（ms）
        index:          定时发送序列号，默认为0
        send_count:     发送的帧数，负数表示无限发送

    Returns:
        无返回值。调用对应的发送函数完成配置下发。
    """

    # 先尝试移除同 index 的旧任务
    Remove_Auto_Send_By_Index(device_handle, chn, msg_type, index)

    if msg_type == "can":
        Auto_Send_Can(device_handle, chn, stdorext, id, data, signal_cycle, index)
    elif msg_type == "canfd":
        Auto_Send_Canfd(device_handle, chn, stdorext, id, data, signal_cycle, index)
    else:
        with print_lock:
            mylog.error("candata", "错误：不支持的 type 类型 '%s'，请使用 'can' 或 'canfd'" % msg_type)
        return

    if send_count < 0:
        return
    elif send_count ==0:
        raise ValueError("send_count 不能为 0")
    else:
        # 计算总延迟时间（单位：秒），并增加余量确保最后一帧已发出
        total_delay = (signal_cycle / 1000.0) * (send_count - 1) + (signal_cycle / 1000.0 * 0.15)
        # 启动后台线程延时关闭
        def shutdown():
            time.sleep(total_delay) 
            Remove_Auto_Send_By_Index(device_handle, chn, msg_type, index)
            with print_lock:
                mylog.info("candata", f"已停止发送 {msg_type.upper()} 信号：通道 0, ID=0x{id:X}, index={index}")
        threading.Thread(target=shutdown, daemon=True).start()

# 关闭指定 index 的定时发送
def Remove_Auto_Send_By_Index(device_handle, chn, msg_type, index):
    """
    禁用指定通道、指定类型、指定 index 的定时发送条目
    备注：只能禁用index，没法彻底删除，设备固件限制

    Args:
        device_handle: 设备句柄
        chn:           通道号 (0, 1, ...)
        msg_type:      "can" 或 "canfd"
        index:         定时发送序列号（之前设置时用的 index）
    Returns:
        bool: 成功返回 True，失败返回 False
    """

    if msg_type == "can":
        # 构造一个仅禁用指定 index 的 CAN 定时发送对象
        auto_can = ZCAN_AUTO_TRANSMIT_OBJ()
        memset(addressof(auto_can), 0, sizeof(auto_can))
        auto_can.index = index
        auto_can.enable = 0  # 关闭该条目

        ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/auto_send", byref(auto_can))
        if ret != ZCAN_STATUS_OK:
            mylog.error("candata", "禁用定时发送 CAN[%d][%d] 失败!" % (chn, index))
            return False
        return True

    elif msg_type == "canfd":
        # 构造一个仅禁用指定 index 的 CANFD 定时发送对象
        auto_canfd = ZCANFD_AUTO_TRANSMIT_OBJ()
        memset(addressof(auto_canfd), 0, sizeof(auto_canfd))
        auto_canfd.index = index
        auto_canfd.enable = 0  # 关闭该条目

        ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/auto_send_canfd", byref(auto_canfd))
        if ret != ZCAN_STATUS_OK:
            mylog.error("candata", "禁用定时发送 CANFD[%d][%d] 失败!" % (chn, index))
            return False
        return True

    else:
        mylog.error("candata", "不支持的消息类型: %s" % msg_type)
        return False

# 接口实现：以a频率连发b帧，然后以c频率持续发送————适用于事件周期型信号
def Send_Can_With_Dynamic_Interval(device_handle, chn_handle, chn, stdorext, id, data,msg_type, event_cycle_ms=100, event_count=3, cycle_ms=1000, index=0):
    """
    以event_cycle_ms频率连发manu_number帧，然后以automatic_cycle_ms频率持续发送————适用于事件周期型信号

    :param device_handle:   设备句柄
    :param chn_handle:      通道句柄
    :param chn:             通道号
    :param stdorext:        帧格式：标准帧=0, 扩展帧=1
    :param id:              CAN帧ID
    :param data:            发送的数据
    :param msg_type:        报文类型，'can' 表示 CAN，'canfd' 表示 CANFD
    :param event_cycle_ms:  每帧之间的手动发送间隔（单位：ms）
    :param event_count:     手动发送的帧数
    :param cycle_ms:        定时发送的周期（单位：ms）
    :param index:           定时发送任务索引
    """
    # 导入将要定时持续发送的信息
    Auto_Send_Can_Or_Canfd(device_handle, chn, stdorext, id, msg_type, data, cycle_ms, index, send_count=-1)
    # 打印开始日志
    mylog.info("candata", f"开始以 {event_cycle_ms}ms 频率连续发送 {event_count}帧 0x{id:X}")
    # 手动连发帧
    event_cycle_s = event_cycle_ms/1000 # 单位转换成秒
    for i in range(event_count):
        Send_Can_Or_Canfd(chn_handle, stdorext, id, msg_type, data, None, 1)
        time.sleep(event_cycle_s)     # 缺点：时间间隔会略大于预设值，延迟比预设要平均多1ms
    a = 1-event_cycle_s
    if a > 0:
        time.sleep(a)
    mylog.info("candata", f"连续发送{event_count}帧已完成, 现在开始以 {cycle_ms} ms频率持续发送 0x{id:X}")
    Enable_Auto_Can_Send(device_handle, chn)

# 通用信号发送接口，根据信号类型自动选择发送方式
def Send_Can_Signal(
    device_handle,
    chn_handle,
    chn,
    stdorext: int,
    id: int,
    data,
    msg_type: str,
    signal_type: str,
    cycle_ms: Optional[Union[int, str]] = None,
    index: int = 0
):
    """
    通用CAN信号发送接口，支持事件、周期、事件周期三种信号类型

    :param device_handle:       设备句柄
    :param chn_handle:          通道句柄
    :param chn:                 通道号
    :param stdorext:            帧格式：标准帧=0, 扩展帧=1
    :param id:                  CAN帧ID
    :param data:                发送的数据
    :param msg_type:            报文类型，'can' 或 'canfd'
    :param signal_type:         信号类型: 'Event'(事件), 'Cycle'(周期), 'CE'(事件周期)
    :param cycle_ms:            - EVENT: 事件帧间隔（ms）
                                - CYCLE: 周期发送周期（ms）
                                - CE:    "事件间隔/周期" 字符串
    :param index:               定时任务索引（默认0）
    """
    msg_type = msg_type.lower()
    signal_type = signal_type.strip().upper()
    valid_signal_types = {"EVENT", "CYCLE", "CE"}

    if msg_type not in ['can', 'canfd']:
        mylog.error("candata", f"不支持的报文类型: {msg_type}")
        return None

    if signal_type not in valid_signal_types:
        mylog.error("candata", f"不支持的信号类型: {signal_type}，仅支持 Event, Cycle, CE")
        return None

    # === 解析 cycle_ms 参数 ===
    event_cycle_ms_val = None
    cycle_period_ms = None

    if signal_type == "CE":
        if isinstance(cycle_ms, str):
            try:
                event_cycle_ms_val, cycle_period_ms = map(int, cycle_ms.split('/'))
            except Exception:
                mylog.error("candata", "CE信号的cycle_ms格式错误，应为 '事件间隔/周期' 如 '100/1000'")
                return None
        else:
            mylog.error("candata", "CE信号必须提供 '事件间隔/周期' 形式的字符串，如 '100/1000'")
            return None

    elif signal_type == "CYCLE":
        try:
            cycle_period_ms = int(cycle_ms) if cycle_ms is not None else None
            if cycle_period_ms is None or cycle_period_ms <= 0:
                raise ValueError
        except Exception:
            mylog.error("candata", "Cycle信号的cycle_ms必须为正整数或可转换为正整数的值")
            return None

    elif signal_type == "EVENT":
        try:
            event_cycle_ms_val = int(cycle_ms) if cycle_ms is not None else 100
            if event_cycle_ms_val <= 0:
                event_cycle_ms_val = 100
        except Exception:
            event_cycle_ms_val = 100

    # === 执行发送逻辑 ===
    if signal_type == "EVENT":
        mylog.info("candata", f"事件信号: 以 {event_cycle_ms_val} ms 间隔连发3帧 0x{id:X}, 已为信号分配 index={index}")
        Send_Can_Or_Canfd(
            chn_handle=chn_handle,
            stdorext=stdorext,
            id=id,
            msg_type=msg_type,
            data=data,
            signal_cycle=event_cycle_ms_val,
            send_count=3
        )

    elif signal_type == "CYCLE":
        mylog.info("candata", f"周期信号: 以 {cycle_period_ms} ms 周期持续发送 0x{id:X}, 已为信号分配 index={index}")
        Auto_Send_Can_Or_Canfd(
            device_handle=device_handle,
            chn=chn,
            stdorext=stdorext,
            id=id,
            msg_type=msg_type,
            data=data,
            signal_cycle=cycle_period_ms,
            index=index,
            send_count=-1
        )
        Enable_Auto_Can_Send(device_handle, chn)

    elif signal_type == "CE":
        mylog.info("candata", f"事件周期信号: 先以 {event_cycle_ms_val} ms 间隔连发3帧，再以 {cycle_period_ms} ms 周期持续发送 0x{id:X}, 已为信号分配 index={index}")
        return Send_Can_With_Dynamic_Interval(
            device_handle=device_handle,
            chn_handle=chn_handle,
            chn=chn,
            stdorext=stdorext,
            id=id,
            data=data,
            msg_type=msg_type,
            event_cycle_ms=event_cycle_ms_val,
            event_count=3,
            cycle_ms=cycle_period_ms,
            index=index
        )

    return True


if __name__ == "__main__":

    # 初始化CAN FD设备
    device_handle, channel_handles, receive_threads = Initialize_Canfd_Device(
        device_type = ZCAN_USBCANFD_200U,
        merge_receive = 0
    )

    print("正在运行can设备")

    data1 = [0x01, 0x00, 0x00, 0x00]
    data2 = [0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
    data3 = [0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

    # 发送事件信号：每50ms发一次，连发3帧
    Send_Can_Signal(device_handle, channel_handles[0], 0, 0, 0x100, data1, 'can', 'Event', cycle_ms=50, index = 0)

    # 发送周期信号：每200ms周期发送
    # Send_Can_Signal(device_handle, channel_handles[0], 0, 0, 0x200, data2, 'canfd', 'Cycle', cycle_ms=200, index = 1)

    # 发送事件周期信号：先每100ms发3帧，然后每1000ms持续发送
    # Send_Can_Signal(device_handle, channel_handles[0], 0, 0, 0x300, data3, 'canfd', 'CE', cycle_ms="100/1000", index = 2)


    # 检查是否收到 ID 为 0x12d，数据为 [0x01, 0x00, 0x00, 0x00] 的帧
    time.sleep(2)
    wait_for_check_signal_received(0x300, data3, 0)

    # 回车退出
    input()

    Close_Canfd_Device(device_handle, channel_handles, receive_threads)
