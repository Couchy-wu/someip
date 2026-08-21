#include <mutex>
#include <chrono>
#include <numeric>
#include <thread>
#include <libgen.h>

#include <pcap.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <netinet/ip.h>
#include <netinet/tcp.h>
#include <netinet/udp.h>
#include <net/ethernet.h>

#include "vsomeip/someip_com.h"
#include "../ArHudSomeipDataType.h"
#include "../CppCommon.h"
#include "../ArHudSomeipDataConversion.h"

#define MAX_PACKET_SIZE 65536*2
#define MAX_EVENT_CNT 23	//支持的最大事件个数
uint32_t g_Cnt[MAX_EVENT_CNT] = { 0 };
#define LOOP_HUIFANG 1 		//是否循环回放
#define VLAN_TAG_PRESENT 0x8100

#pragma pack(1)
struct SomeIpHeader {
    uint16_t service_id;
    uint16_t method_id;
    uint32_t length;
    uint16_t client_id;
    uint16_t session_id;
    uint8_t someip_version;
    uint8_t interface_version;
    uint8_t message_type;
    uint8_t return_code;
    //uint32_t payload_length;
};

struct PacketInfo {
    uint16_t service_id;
    uint16_t method_id;
    uint32_t length;
    uint16_t client_id;
    uint16_t session_id;
    uint8_t someip_version;
    uint8_t interface_version;
    uint8_t message_type;
    uint8_t return_code;
    uint32_t payload_length;
    uint32_t tp_offset;
    bool more_segments;
    uint32_t num;
    u_char payload[MAX_PACKET_SIZE];
    struct pcap_pkthdr *hdr;
    // uint32_t data_len;
    u_char *data;
};
#pragma pack()

bool parse_someip_packet(const u_char *dpacket, struct PacketInfo *packet_info) {
    struct ip *ip_header;
    struct udphdr *udp_header;
    struct tcphdr *tcp_header;
    const u_char *transport_header;
    const u_char *payload_start;
    int transport_header_length;
    const u_char *packet = NULL;

    struct ether_header *eth_header = (struct ether_header *)dpacket;

    if (ntohs(eth_header->ether_type) == VLAN_TAG_PRESENT)
    {
        packet = dpacket + 18;
    }
    else
    {
        packet = dpacket + 14;
    }

    ip_header = (struct ip *)(packet); // 以太网头14字节

    // 检查是否为IPv4数据包
    if (ip_header->ip_v != 4) {
        return false;
    }

    u_short dest_port = 0;
    // 确定传输层协议
    if (ip_header->ip_p == IPPROTO_UDP) {
        udp_header = (struct udphdr *)(ip_header + 1);
        transport_header = (u_char *)udp_header;
        transport_header_length = 8; // UDP头部固定长度
    } else if (ip_header->ip_p == IPPROTO_TCP) {
        tcp_header = (struct tcphdr *)(ip_header + 1);
        transport_header = (u_char *)tcp_header;
        transport_header_length = (tcp_header->th_off) << 2; // TCP头部长度
        dest_port = tcp_header->th_dport;
        dest_port = ntohs(dest_port);
    } else {
        return false;// 仅处理UDP和TCP
    }

    // 计算Payload起始位置
    int ip_header_length = ip_header->ip_hl << 2;
    payload_start = packet + ip_header_length + transport_header_length;

    // 检查Payload长度是否足够
    int payload_length = 0;
    if (ip_header->ip_p == IPPROTO_UDP) {
        payload_length = ntohs(udp_header->uh_ulen) - transport_header_length;
    } else if (ip_header->ip_p == IPPROTO_TCP) {
        payload_length = ntohs(ip_header->ip_len) - (ip_header_length + transport_header_length);
    }

    if (payload_length < sizeof(struct SomeIpHeader) || dest_port == 22) {
        return false; // Payload过短，无法解析SOME/IP头部
    }

    // 解析SOME/IP头部
    struct SomeIpHeader *someip_header = (struct SomeIpHeader *)payload_start;
    packet_info->service_id = ntohs(someip_header->service_id);
    packet_info->method_id = ntohs(someip_header->method_id);
    packet_info->length = ntohl(someip_header->length);
    packet_info->client_id = ntohs(someip_header->client_id);
    packet_info->session_id = ntohs(someip_header->session_id);
    packet_info->someip_version = someip_header->someip_version;
    packet_info->interface_version = someip_header->interface_version;
    packet_info->message_type = someip_header->message_type;
    packet_info->return_code = someip_header->return_code;
    //packet_info->payload_length = packet_info->length - 8;
    if (packet_info->message_type == 0x22) //SOME/IP-TP segment
    {
        uint8_t *pTP = (uint8_t*)(payload_start + 16);
        uint32_t TPoffset = 0u;
        memcpy(&TPoffset, pTP, 4);
        //TPoffset = TPoffset&0x11111100;
        TPoffset = ntohl(TPoffset);
        packet_info->more_segments = TPoffset&0x1;
        TPoffset &= 0xFFFFFFFE;
        packet_info->tp_offset = TPoffset;        
    }

    // 检查是否为SOME/IP-SD数据包
    if (packet_info->service_id == 0xFFFF && packet_info->method_id == 0x8100) {
        return false; // 跳过服务发现数据包
    }

    if (packet_info->someip_version != 0x01)
    {
        return false;
    }

    // 复制Payload数据
    int total_payload_size = packet_info->payload_length;
    if (total_payload_size > MAX_PACKET_SIZE) {
        total_payload_size = MAX_PACKET_SIZE;
    }

    memset(packet_info->payload, 0, MAX_PACKET_SIZE);
    if (packet_info->message_type == 0x02)
    {
        packet_info->payload_length = packet_info->length - 8;
        memcpy(packet_info->payload, payload_start + sizeof(struct SomeIpHeader), packet_info->payload_length);
    }
    else if (packet_info->message_type == 0x022)
    {
        packet_info->payload_length = packet_info->length - 12;
        memcpy(packet_info->payload, payload_start + sizeof(struct SomeIpHeader)+4, packet_info->payload_length);
    }
    
    return true;
}

uint32_t g_sum_tmp = 0, g_sum = 0, g_SendCount = 0;
bool g_bIsEnd = true;
std::mutex gMtx;
int32_t DefaultServerSubScribeCallback(uint16_t snServiceId, uint16_t snInstanceId, uint16_t snMethodId, uint8_t** pcNotifyData, uint32_t* pcNotifyDataLen, void* pParam)//pcNotifyData指向需要分发的数据,这里是g_VehiclePositionInfoNotify
{
	// 打印时间戳
	std::lock_guard<std::mutex> its_lock(gMtx);
	int idx = -1;
	bool bSend = false;
	g_bIsEnd = false;

		 if (snServiceId == 0x000A && snInstanceId == 0x000A && snMethodId == 0x8001) { bSend = true;   idx = 0;  g_Cnt[idx]++;}
	else if (snServiceId == 0x000B && snInstanceId == 0x000B && snMethodId == 0x8001) { bSend = true;   idx = 1;  g_Cnt[idx]++;}
	else if (snServiceId == 0x000B && snInstanceId == 0x000B && snMethodId == 0x8002) { bSend = true;   idx = 2;  g_Cnt[idx]++;}
	else if (snServiceId == 0x000C && snInstanceId == 0x000C && snMethodId == 0x8001) { bSend = true;   idx = 3;  g_Cnt[idx]++;}
	else if (snServiceId == 0x000C && snInstanceId == 0x000C && snMethodId == 0x8002) { bSend = true;   idx = 4;  g_Cnt[idx]++;}
	else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8001) { bSend = true;   idx = 5;  g_Cnt[idx]++;}
	else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8002) { bSend = true;   idx = 6;  g_Cnt[idx]++;}
	else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8003) { bSend = true;   idx = 7;  g_Cnt[idx]++;}
	else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8004) { bSend = true;   idx = 8;  g_Cnt[idx]++;}
	else if (snServiceId == 0x010A && snInstanceId == 0x0001 && snMethodId == 0x8001) { bSend = true;   idx = 9;  g_Cnt[idx]++;}
	else if (snServiceId == 0x010A && snInstanceId == 0x0001 && snMethodId == 0x8002) { bSend = true;   idx = 10; g_Cnt[idx]++;}
	else if (snServiceId == 0x010A && snInstanceId == 0x0001 && snMethodId == 0x8003) { bSend = true;   idx = 11; g_Cnt[idx]++;}
	else if (snServiceId == 0x010A && snInstanceId == 0x0001 && snMethodId == 0x8004) { bSend = true;   idx = 12; g_Cnt[idx]++;}
	else if (snServiceId == 0x000C && snInstanceId == 0x000C && snMethodId == 0x8003) { bSend = true;   idx = 13; g_Cnt[idx]++;}
	else if (snServiceId == 0x000D && snInstanceId == 0x000D && snMethodId == 0x8005) { bSend = true;   idx = 14; g_Cnt[idx]++;}
	else if (snServiceId == 0x000E && snInstanceId == 0x000E && snMethodId == 0x8001) { bSend = true;   idx = 15; g_Cnt[idx]++;}
	else if (snServiceId == 0x0007 && snInstanceId == 0x0007 && snMethodId == 0x8001) { bSend = true;   idx = 16; g_Cnt[idx]++;}
	else if (snServiceId == 0x0017 && snInstanceId == 0x0017 && snMethodId == 0x8003) { bSend = true;   idx = 17; g_Cnt[idx]++;}
	else if (snServiceId == 0x002B && snInstanceId == 0x002B && snMethodId == 0x8001) { bSend = false;  idx = 18; g_Cnt[idx]++;}
	else if (snServiceId == 0x8202 && snInstanceId == 0x8202 && snMethodId == 0x8002) { bSend = false;  idx = 19; g_Cnt[idx]++;}
	else if (snServiceId == 0x000E && snInstanceId == 0x000E && snMethodId == 0x8002) { bSend = true;   idx = 20; g_Cnt[idx]++;}
	else if (snServiceId == 0x000E && snInstanceId == 0x000E && snMethodId == 0x8003) { bSend = true;   idx = 21; g_Cnt[idx]++;}
	else if (snServiceId == 0x0018 && snInstanceId == 0x0018 && snMethodId == 0x8001) { bSend = false;  idx = 22; g_Cnt[idx]++;}
	else if (pcNotifyDataLen != nullptr)
	{ 
		printf("\r\nunknow event\r\n"); 
		*pcNotifyDataLen = 0x00;
		return 0;
	}
}



#include <csignal>

// SIGINT 信号处理函数
void signalHandler(int signal) {
    
    g_SendCount = std::accumulate(g_Cnt, g_Cnt + MAX_EVENT_CNT, 0);
    // 在这里添加您希望在程序关闭之前执行的操作代码
			printf("\r\n\
       event_type                      recv_count\r\n\
Total_count:                                                              %u\r\n\
0. (0x000A, 0x000A, 0x8001, 0x1101): VehiclePositionInfoNotify:           %u\r\n\
1. (0x000B, 0x000B, 0x8001, 0x1101): RTKInfoNotify:                       %u\r\n\
2. (0x000B, 0x000B, 0x8002, 0x1101): IMUInfoNotify:                       %u\r\n\
3. (0x000C, 0x000C, 0x8001, 0x1101): ObstacleInfoNotify:                  %u\r\n\
4. (0x000C, 0x000C, 0x8002, 0x1101): LaneLineDataNotify:                  %u\r\n\
5. (0x000D, 0x000D, 0x8001, 0x1101): ChangeLaneDataNotify:                %u\r\n\
6. (0x000D, 0x000D, 0x8002, 0x1101): PilotStatusNofity:                   %u\r\n\
7. (0x000D, 0x000D, 0x8003, 0x1101): PilotAlarmAndNoticeInfoNotify:       %u\r\n\
8. (0x000D, 0x000D, 0x8004, 0x1101): BroadcastInfoNotify:                 %u\r\n\
9. (0x010A, 0x0001, 0x8001, 0x1101): PlanningLineInfoNotify:              %u\r\n\
10.(0x010A, 0x0001, 0x8002, 0x1101): HudRoadInfo_EG:                      %u\r\n\
11.(0x010A, 0x0001, 0x8003, 0x1101): HudMappathInfoNotify:                %u\r\n\
12.(0x010A, 0x0001, 0x8004, 0x1101): HudNavigationmapNotify:              %u\r\n\
\
13.(0x000C, 0x000C, 0x8003, 0x1101): NewLanelineDataNotify                %u\r\n\
14.(0x000D, 0x000D, 0x8005, 0x1101): NewBroadcastInfoNotify               %u\r\n\
15.(0x000E, 0x000E, 0x8001, 0x1101): PlanningLineInfoNotify               %u\r\n\
16.(0x0007, 0x0007, 0x8001, 0x1101): NavigationStatus_LinkInfoNotify      %u\r\n\
17.(0x0017, 0x0017, 0x8003, 0x1101): NewParkingRealTimeDataNotify         %u\r\n\
18.(0x002B, 0x002B, 0x8001, 0x1101): NavigationHDLink2Info                %u\r\n\
19.(0x8202, 0x8202, 0x8002, 0x1101): sdTraffiIncident                     %u\r\n\
20.(0x000E, 0x000E, 0x8002, 0x1102): newPlanningLineInfo                  %u\r\n\
21.(0x000E, 0x000E, 0x8003, 0x1103): drivingAreaIdentification            %u\r\n\
22.(0x0018, 0x0018, 0x8001, 0x1101): hpaMapDataNotify                     %u\r\n",
g_SendCount, g_Cnt[0], g_Cnt[1], g_Cnt[2], g_Cnt[3], g_Cnt[4], g_Cnt[5],g_Cnt[6], g_Cnt[7], g_Cnt[8], g_Cnt[9], g_Cnt[10], 
g_Cnt[11], g_Cnt[12], g_Cnt[13],g_Cnt[14], g_Cnt[15], g_Cnt[16], g_Cnt[17], g_Cnt[18], g_Cnt[19], g_Cnt[20], g_Cnt[21], g_Cnt[22]);

    // 退出程序
    exit(signal);
}

struct timespec program_start;
std::chrono::system_clock::time_point g_when;
int main(int argc, char *argv[]) {

    // 注册 SIGINT 信号处理函数
    signal(SIGINT, signalHandler);

    SPInstance spi;
    SPInit(&spi, "", "./someip_arhud01_pcap_server.json");

	//为通知绑定回调处理函数
	SPServerNotifyCallbackFuncRegist(&spi, 0x000A, 0x000A, 0x8001, 0x1101, DefaultServerSubScribeCallback, NULL);    //0.VehiclePositionInfoNotify
	SPServerNotifyCallbackFuncRegist(&spi, 0x000B, 0x000B, 0x8001, 0x1101, DefaultServerSubScribeCallback, NULL);    //1.RTKInfoNotify
	SPServerNotifyCallbackFuncRegist(&spi, 0x000B, 0x000B, 0x8002, 0x1101, DefaultServerSubScribeCallback, NULL);    //2.IMUInfoNotify
	SPServerNotifyCallbackFuncRegist(&spi, 0x000C, 0x000C, 0x8001, 0x1101, DefaultServerSubScribeCallback, NULL);    //3.ObstacleInfoNotify
	SPServerNotifyCallbackFuncRegist(&spi, 0x000C, 0x000C, 0x8002, 0x1101, DefaultServerSubScribeCallback, NULL);    //4.LaneLineDataNotify
	SPServerNotifyCallbackFuncRegist(&spi, 0x000D, 0x000D, 0x8001, 0x1101, DefaultServerSubScribeCallback, NULL);    //5.ChangeLaneDataNotify
	SPServerNotifyCallbackFuncRegist(&spi, 0x000D, 0x000D, 0x8002, 0x1101, DefaultServerSubScribeCallback, NULL);    //6.PilotStatusNofity
	SPServerNotifyCallbackFuncRegist(&spi, 0x000D, 0x000D, 0x8003, 0x1101, DefaultServerSubScribeCallback, NULL);    //7.PilotAlarmAndNoticeInfoNotify
	SPServerNotifyCallbackFuncRegist(&spi, 0x000D, 0x000D, 0x8004, 0x1101, DefaultServerSubScribeCallback, NULL);    //8.BroadcastInfoNotify
	SPServerNotifyCallbackFuncRegist(&spi, 0x010A, 0x0001, 0x8001, 0x1101, DefaultServerSubScribeCallback, NULL);    //9.HudRoadInfo_EG
	SPServerNotifyCallbackFuncRegist(&spi, 0x010A, 0x0001, 0x8002, 0x1101, DefaultServerSubScribeCallback, NULL);    //10.HudMappathInfo_EG
	SPServerNotifyCallbackFuncRegist(&spi, 0x010A, 0x0001, 0x8003, 0x1101, DefaultServerSubScribeCallback, NULL);    //11.HudNavigationmap
	SPServerNotifyCallbackFuncRegist(&spi, 0x010A, 0x0001, 0x8004, 0x1101, DefaultServerSubScribeCallback, NULL);    //12.overseasHudRoadInfoNotify

	//SR
    SPServerNotifyCallbackFuncRegist(&spi, 0x000C, 0x000C, 0x8003, 0x1101, DefaultServerSubScribeCallback, NULL);    //13.NewLanelineDataNotify
    SPServerNotifyCallbackFuncRegist(&spi, 0x000D, 0x000D, 0x8005, 0x1101, DefaultServerSubScribeCallback, NULL);    //14.NewBroadcastInfoNotify
    SPServerNotifyCallbackFuncRegist(&spi, 0x000E, 0x000E, 0x8001, 0x1101, DefaultServerSubScribeCallback, NULL);    //15.PlanningLineInfoNotify
    SPServerNotifyCallbackFuncRegist(&spi, 0x0007, 0x0007, 0x8001, 0x1101, DefaultServerSubScribeCallback, NULL);    //16.NavigationStatus_LinkInfoNotifyfy
    SPServerNotifyCallbackFuncRegist(&spi, 0x0017, 0x0017, 0x8003, 0x1101, DefaultServerSubScribeCallback, NULL);    //17.NewParkingRealTimeDataNotify
    SPServerNotifyCallbackFuncRegist(&spi, 0x002B, 0x002B, 0x8001, 0x1101, DefaultServerSubScribeCallback, NULL);    //18.NavigationHDLink2Info
    SPServerNotifyCallbackFuncRegist(&spi, 0x8202, 0x8202, 0x8002, 0x1101, DefaultServerSubScribeCallback, NULL);    //19.sdTraffiIncident
    SPServerNotifyCallbackFuncRegist(&spi, 0x000E, 0x000E, 0x8002, 0x1102, DefaultServerSubScribeCallback, NULL);    //20.newPlanningLineInfo
    SPServerNotifyCallbackFuncRegist(&spi, 0x000E, 0x000E, 0x8003, 0x1103, DefaultServerSubScribeCallback, NULL);    //21.drivingAreaIdentification
	SPServerNotifyCallbackFuncRegist(&spi, 0x0018, 0x0018, 0x8001, 0x1101, DefaultServerSubScribeCallback, NULL);    //22.drivingAreaIdentification
    SPStart(&spi);


    char path[256] = { 0 }, pcapFile[256] = {0};
    readlink("/proc/self/exe", path, sizeof(path));
	dirname(path);
    sprintf(pcapFile, "%s/out.pcap", path);

#if LOOP_HUIFANG
while(1){
#endif

    pcap_t *cap_handle = pcap_open_offline(pcapFile, NULL);
    if (cap_handle == NULL) {
        fprintf(stderr, "无法打开文件 %s\n", pcap_file);
        return 1;
    }

    std::vector<struct PacketInfo> TPSegments;
    struct PacketInfo current_packet, next_packet;
    struct PacketInfo previous_packet;
    struct timeval first_time, current_time, previous_time;
    std::chrono::_V2::system_clock::time_point program_start;

    struct timeval ts;	/* time stamp */
    bool first_packet = true;
    program_start = std::chrono::high_resolution_clock::now();

    while (true) {
        //memset(&current_packet, 0, sizeof(struct PacketInfo));
        int res = pcap_next_ex(cap_handle, &(current_packet.hdr), (const u_char**)&(current_packet.data));
        if (res != 1) {
            pcap_close(cap_handle);
            // 文件末尾
            //return 0;
            g_sum = g_sum_tmp;
            g_sum_tmp = 0;
            break;
        }
        current_packet.num++;
        g_sum_tmp++;

        // 解析SOME/IP数据包
        // 如果是SOME/IP-SD数据包或非SOME/IP数据包，跳过
        if (!parse_someip_packet(current_packet.data, &current_packet))
        {
            continue;
        }

        //TODO:SOME/IP TP packet
        if (current_packet.message_type == 0x22 && current_packet.tp_offset == 0 && current_packet.more_segments)
        {
            TPSegments.push_back(current_packet);
            continue;
        }
        else if (current_packet.message_type == 0x22 && current_packet.tp_offset != 0 && current_packet.more_segments)
        {
            bool bbreak = false;
            for (uint32_t i = 0; i < TPSegments.size(); ++i)
            {
                if (TPSegments[i].service_id == current_packet.service_id && TPSegments[i].method_id == current_packet.method_id &&
                    TPSegments[i].session_id == current_packet.session_id)
                {
                    memcpy((char*)(TPSegments[i].payload + TPSegments[i].payload_length), (char*)(current_packet.payload), (current_packet.payload_length));
                    TPSegments[i].payload_length += current_packet.payload_length;
                    bbreak = true;
                    break;
                }
            }
            if (bbreak) continue;
        }
        else if (current_packet.message_type == 0x22 && !current_packet.more_segments)
        {
            for (uint32_t i = 0; i < TPSegments.size(); ++i)
            {
                if (TPSegments[i].service_id == current_packet.service_id && TPSegments[i].method_id == current_packet.method_id &&
                    TPSegments[i].session_id == current_packet.session_id)
                {
                    memcpy((char*)(TPSegments[i].payload + TPSegments[i].payload_length), (char*)(current_packet.payload), (current_packet.payload_length));
                    TPSegments[i].payload_length += current_packet.payload_length;

                    memcpy(current_packet.payload, TPSegments[i].payload, TPSegments[i].payload_length);
                    current_packet.payload_length = TPSegments[i].payload_length;
                    TPSegments.erase(TPSegments.begin() + i);
                }
            }
        }

        // 如果是第一个数据包，直接发送
        if (first_packet) {
            first_packet = false;
            first_time = current_packet.hdr->ts;
            previous_time = current_packet.hdr->ts;
            // 发送数据包
            if (current_packet.service_id == 0x010a)
            {
                SPServerSendNotify(&spi, current_packet.service_id, 0x0001, current_packet.method_id, current_packet.payload, current_packet.payload_length);
                //DefaultServerSubScribeCallback(current_packet.service_id, 0x0001, current_packet.method_id, nullptr, nullptr, nullptr);
            }
            else
            {
                SPServerSendNotify(&spi, current_packet.service_id, current_packet.service_id, current_packet.method_id, current_packet.payload, current_packet.payload_length);
                //DefaultServerSubScribeCallback(current_packet.service_id, current_packet.service_id, current_packet.method_id, nullptr, nullptr, nullptr);
            }
            g_SendCount++;

            // 获取当前时间
            auto current_time = std::chrono::high_resolution_clock::now();
            // 计算时间差（以微秒为单位）
            auto time_diff = std::chrono::duration_cast<std::chrono::microseconds>(current_time - program_start);
            // 将时间差分解为秒、毫秒和微秒
            unsigned long long total_micro = time_diff.count();
            unsigned long long seconds = total_micro / 1000000;
            printf("%ld.%06ld ", seconds, total_micro%1000000);

            printf("发-->:send_count:%u No.%u serviceID:%04X instanceID:%04X eventID:%04X data_len:%u\r\n",
                g_SendCount, current_packet.num, current_packet.service_id, current_packet.service_id, current_packet.method_id, current_packet.payload_length);
            continue;
        }

        // 计算当前数据包与前一个数据包的时间差
        struct timeval diff;
        timersub(&current_packet.hdr->ts, &previous_time, &diff);

        if (diff.tv_sec > 0)
        {
            sleep(diff.tv_sec);
        }
        if (diff.tv_usec > 0)
        {
            std::this_thread::sleep_for(std::chrono::microseconds(diff.tv_usec));
        }

        // 发送当前数据包
        if (current_packet.service_id == 0x010a)
        {
            SPServerSendNotify(&spi, current_packet.service_id, 0x0001, current_packet.method_id, current_packet.payload, current_packet.payload_length);
            DefaultServerSubScribeCallback(current_packet.service_id, 0x0001, current_packet.method_id, nullptr, nullptr, nullptr);
        }
        else
        {
            SPServerSendNotify(&spi, current_packet.service_id, current_packet.service_id, current_packet.method_id, current_packet.payload, current_packet.payload_length);
            DefaultServerSubScribeCallback(current_packet.service_id, current_packet.service_id, current_packet.method_id, nullptr, nullptr, nullptr);
        }
        g_SendCount++;

        // 更新前一个数据包的时间戳
        previous_time = current_packet.hdr->ts;

        // // 获取当前时间
        // auto current_time = std::chrono::high_resolution_clock::now();
        // // 计算时间差（以微秒为单位）
        // auto time_diff = std::chrono::duration_cast<std::chrono::microseconds>(current_time - program_start);
        // // 将时间差分解为秒、毫秒和微秒
        // unsigned long long total_micro = time_diff.count();
        // unsigned long long seconds = total_micro / 1000000;
        // printf("%ld.%06ld ", seconds, total_micro%1000000);

        //if (current_packet.num % 300 == 0)
        {
            //printf("%ld.%06ld ", seconds, total_micro%1000000);
            printf("发-->:total_count:%u send_count:%u No.%u serviceID:%04X instanceID:%04X eventID:%04X data_len:%u\r\n",
                g_sum, g_SendCount, current_packet.num, current_packet.service_id, current_packet.service_id, current_packet.method_id, current_packet.payload_length);
        }
    }

#if LOOP_HUIFANG
}
#endif

    return 0;
}






