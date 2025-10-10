'''
    支持的设备有 USBCANFD-100U mini   USBCANFD-100U/200U/400U/800U
'''

from zlgcan import *
import threading
import time


thread_flag = True
print_lock = threading.Lock()   # 线程锁，只是为了打印不冲突
enable_merge_receive = 0        # 合并接收标识


#读取设备信息
def Read_Device_Info(device_handle):
    # 获取设备信息
    info = zcanlib.GetDeviceInf(device_handle)
    print("设备信息: \n%s" % info)
    can_number = info.can_num
    return can_number

# 设置自定义序列号  ---用去区分同型号的CAN卡
def Set_Device_Name(device_handle):
    ret = zcanlib.ZCAN_SetValue(handle, "0/set_cn", "A001".encode("utf-8")) 
    if ret == ZCAN_STATUS_OK:
        t = zcanlib.ZCAN_GetValue(handle, "0/get_cn/1")
        print("自定义序列号为："+ c_char_p(t).value.decode("utf-8"))
    return

# 接收线程
def receive_thread(device_handle,chn_handle):

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
                    # 打印输出
                    print(f"[{msg.timestamp}] CAN{chn_handle & 0xFF} {can_type:<{CANType_width}}\t{direction} ID: {can_id:<{id_width}}\t{frame_type} {frame_format}"
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

                    print(f"[{msg.timestamp}] CAN{chn_handle & 0xFF} {can_type:<{CANType_width}}\t{direction} ID: {can_id:<{id_width}}\t{frame_type} {frame_format}"
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

                        print(f"[{msg.zcanfddata.timestamp}] CAN{msg.chnl} {can_type:<{CANType_width}}\t{direction} ID: {hex(can_id):<{id_width}}\t{frame_type} {frame_format}"
                        f" DLC: {frame.len}\tDATA(hex): {data}")
    print("=====")

# 启动通道
def USBCANFD_Start(zcanlib, device_handle, chn):

    # 设置波特率（仲裁段 & 数据段）
    # ZCAN_SetValue ：设置设备属性
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/canfd_abit_baud_rate", "500000".encode("utf-8"))
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/canfd_dbit_baud_rate", "2000000".encode("utf-8"))
    if ret != ZCAN_STATUS_OK:
        print("Set CH%d baud failed!" % chn)
        return None

    # 自定义波特率    当产品波特率对采样点有要求，或者需要设置非常规波特率时使用   ---默认不管
    # ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/baud_rate_custom", "500Kbps(80%),2.0Mbps(80%),(80,07C00002,01C00002)".encode("utf-8"))
    # if ret != ZCAN_STATUS_OK:
    #     print("Set CH%d baud failed!" % chn)
    #     return None

    # 打开终端电阻
    ret = zcanlib.ZCAN_SetValue(device_handle, str(chn) + "/initenal_resistance", "1".encode("utf-8"))
    if ret != ZCAN_STATUS_OK:
        print("Open CH%d resistance failed!" % chn)
        return None

    # 初始化通道
    chn_init_cfg = ZCAN_CHANNEL_INIT_CONFIG()
    chn_init_cfg.can_type = ZCAN_TYPE_CANFD  # USBCANFD 必须选择CANFD
    chn_init_cfg.config.canfd.mode = 0  # 0-正常模式 1-只听模式
    chn_handle = zcanlib.InitCAN(device_handle, chn, chn_init_cfg)
    if chn_handle is None:
        print("initCAN failed!" % chn)
        return None

    # 设置滤波
    # Set_Filter(device_handle, chn)

    # 设置发送回显    USBCANFD系列老卡（无LIN口，设备白色标签值版本为V1.02即以下,包括V1.02）需要以下操作，否则由CAN报文结构体_pad结构体bit5标识，见Transmit_Test 发送示例
    # 禁用回显，避免收到自己发的消息（除非需要监控）
    ret = zcanlib.ZCAN_SetValue(device_handle,str(chn)+"/set_device_tx_echo","0".encode("utf-8"))   #发送回显设置，0-禁用，1-开启
    if ret != ZCAN_STATUS_OK:
        print("Set CH%d  set_device_tx_echo failed!" %(chn))
        return None

    # 使能/关闭合并接收(startCAN 之前)    0-关闭 1-使能
    ret = zcanlib.ZCAN_SetValue(device_handle, str(0) + "/set_device_recv_merge", repr(enable_merge_receive))
    if ret != ZCAN_STATUS_OK:
        print("Open CH%d recv merge failed!" % chn)
        return None

    # 启动通道
    ret = zcanlib.StartCAN(chn_handle)
    if ret != ZCAN_STATUS_OK:
        print("startCAN failed!" % chn)
        return None

    return chn_handle

# 发送 CAN 报文
'''
    # chn_handle: CAN 通道的句柄，表示已打开的 CAN 通道，用于标识发送数据的通道。
    # stdorext: 布尔值（0 或 1），表示使用标准帧=还是扩展帧=，若为 True 或非零，则使用扩展帧。
    # id: CAN 帧的 ID（即消息标识符）。
    # data: 要发送的数据，应为一个可迭代对象（如列表或字节数组），包含最多 8 个字节。
    # length: 实际要发送的数据长度（字节数），通常为 0~8。
'''
def Transmit_Test_Can(chn_handle, stdorext, id, data, round):
    transmit_num = round     # 设置can信号发送帧数
    length = len(data)       # 自动计算数据长度

    # 确保数据长度不超过8字节（CAN帧限制）
    if length > 8:
        with print_lock:
            print("警告：CAN数据长度为 %d，超过最大限制8字节，跳过发送。" % length)
        return None  
    
    # 创建ZCAN_Transmit_Data数组
    msgs = (ZCAN_Transmit_Data * transmit_num)()
    for i in range(transmit_num):
        msgs[i].transmit_type = 2           # 0-正常发送，1-单次发发送，2-自发自收，3-单次自发自收
        msgs[i].frame.eff     = 0           # 0-标准帧，1-扩展帧，根据输入变量stdorext值决定
        if stdorext:
            msgs[i].frame.eff = 1 
        msgs[i].frame.rtr     = 0           # 0-数据帧，1-远程帧
        msgs[i].frame.can_id  = id          # CAN ID
        msgs[i].frame.can_dlc = length      # 数据长度，实际发送的数据字节数（0~8）
        msgs[i].frame._pad |= 0x20          # 发送回显
        msgs[i].frame._res0 = 10            # res0，res1共同表示队列发送间隔(可以理解为一个short 2Byte分开传入)
        msgs[i].frame._res1 = 0         
        # 填充数据
        for j in range(msgs[i].frame.can_dlc):
            msgs[i].frame.data[j] = data[j]

    ret = zcanlib.Transmit(chn_handle, msgs, transmit_num)
    with print_lock: print("成功发送 %d 条CAN报文" % ret)
    return ret 

# 发送 CANFD 报文
def Transmit_Test_Canfd(chn_handle, stdorext, id, data):
    transmit_canfd_num = round
    length = len(data)       # 自动计算数据长度
    canfd_msgs = (ZCAN_TransmitFD_Data * transmit_canfd_num)()
    for i in range(transmit_canfd_num):
        canfd_msgs[i].transmit_type = 2         # 0-正常发送，2-自发自收
        canfd_msgs[i].frame.eff     = 0         # 0-标准帧，1-扩展帧，根据输入变量stdorext值决定
        if stdorext:
            canfd_msgs[i].frame.eff = 1
        canfd_msgs[i].frame.rtr     = 0         # 0-数据帧，1-远程帧
        canfd_msgs[i].frame.can_id = id         # ID
        canfd_msgs[i].frame.len = length        # 长度
        canfd_msgs[i].frame.flags |= 0x20       # 发送回显
        canfd_msgs[i].frame.flags |= 0x0        # BRS 加速标志位：0不加速，1加速
        canfd_msgs[i].frame._res0 = 10
        for j in range(canfd_msgs[i].frame.len):
            canfd_msgs[i].frame.data[j] = data[j]
    ret = zcanlib.TransmitFD(chn_handle, canfd_msgs, transmit_canfd_num)
    with print_lock: print("成功发送 %d 条CANFD报文" % ret)



if __name__ == "__main__":
    zcanlib = ZCAN()

    # 打开设备
    handle = zcanlib.OpenDevice(ZCAN_USBCANFD_200U, 0, 0)
    if handle == INVALID_DEVICE_HANDLE:
        print("打开设备失败！")
        exit(0)
    print("打开设备成功，设备句柄为: %d." % handle)

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
            print("启动通道%d失败！" % i)
            exit(0)
        chn_handles.append(chn_handle)  # 将通道句柄添加到列表中
        print(f"打开通道{i}成功，通道句柄为: %d." % chn_handle)
    # 接收线程创建策略
    if enable_merge_receive == 1:   #   若开启合并接收，所有通道都由一个接收线程处理
        thread = threading.Thread(target=receive_thread, args=(handle,chn_handles[0]))    # 开启独立接收线程
        threads.append(thread)
        thread.start()
    else:                           #   若没有开启合并接收，所有通道的数据需要各自开一个线程接收
        for i in range(len(chn_handles)):
            thread = threading.Thread(target=receive_thread, args=(handle, chn_handles[i]))  # 开启独立接收线程
            threads.append(thread)
            thread.start()

    # 发送报文示例
    data = [0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00]
    Transmit_Test_Can(chn_handles[0], 0, 0x12D, data, 1)

    # 回车退出
    input()
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
            print(f"关闭通道{i}成功")

    # 关闭设备
    ret = zcanlib.CloseDevice(handle)
    if ret == 1:
        print("关闭设备成功")