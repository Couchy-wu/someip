#include "CppCommon.h"
#if _WIN32
#else
#include <unistd.h>
#include <dirent.h>
#include <libgen.h>
#include <ifaddrs.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#endif
#include <sstream>
#include <fstream>
#include <memory>
#include <mutex>
#include <map>
#include <cmath>
#include "SPIni.h"


JxIni::Ini<char> ini;
std::string gpath;

#define DYNAMIC_CNT 3
#define SP_POLYNOMIAL 0x04C11DB7
#define SP_INITIAL_REMAINDER 0xFFFFFFFF
#define SP_FINAL_XOR_VALUE 0xFFFFFFFF

unsigned int sp_reflect(unsigned int data, unsigned char nBits) {
    unsigned int reflection = 0x00000000;
    unsigned char bit;

    for (bit = 0; bit < nBits; ++bit) {
        if (data & 0x01) {
            reflection |= (1 << ((nBits - 1) - bit));
        }
        data = (data >> 1);
    }
    return reflection;
}

unsigned int sp_crc32(unsigned char *message, int nBytes) {
    unsigned int remainder = SP_INITIAL_REMAINDER;
    unsigned char data;
    int byte, bit;

    for (byte = 0; byte < nBytes; ++byte) {
        data = sp_reflect(message[byte], 8);
        remainder ^= (data << 24);
        for (bit = 8; bit > 0; --bit) {
            if (remainder & 0x80000000) {
                remainder = (remainder << 1) ^ SP_POLYNOMIAL;
            } else {
                remainder = (remainder << 1);
            }
        }
    }
    return sp_reflect(remainder, 32) ^ SP_FINAL_XOR_VALUE;
}


//编码表
static const char EncodeTable[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
//解码表
static const char DecodeTable[] =
{
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    62, // '+'
    0, 0, 0,
    63, // '/'
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61, // '0'-'9'
    0, 0, 0, 0, 0, 0, 0,
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
    13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, // 'A'-'Z'
    0, 0, 0, 0, 0, 0,
    26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38,
    39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, // 'a'-'z'
};

string Encode(const unsigned char* Data, int DataByte)
{
    //返回值
    string strEncode;
    unsigned char Tmp[4] = {0};
    int LineLength = 0;
    for(int i = 0; i < (int)(DataByte / 3); i++)
    {
        Tmp[1] = *Data++;
        Tmp[2] = *Data++;
        Tmp[3] = *Data++;
        strEncode += EncodeTable[Tmp[1] >> 2];
        strEncode += EncodeTable[((Tmp[1] << 4) | (Tmp[2] >> 4)) & 0x3F];
        strEncode += EncodeTable[((Tmp[2] << 2) | (Tmp[3] >> 6)) & 0x3F];
        strEncode += EncodeTable[Tmp[3] & 0x3F];

        if(LineLength += 4, LineLength == 76)
        {
            strEncode += "\r\n";
            LineLength = 0;
        }
    }
    //对剩余数据进行编码
    int Mod = DataByte % 3;
    if(Mod == 1)
    {
        Tmp[1] = *Data++;
        strEncode += EncodeTable[(Tmp[1] & 0xFC) >> 2];
        strEncode += EncodeTable[((Tmp[1] & 0x03) << 4)];
        strEncode += "==";
    }
    else if(Mod == 2)
    {
        Tmp[1] = *Data++;
        Tmp[2] = *Data++;
        strEncode += EncodeTable[(Tmp[1] & 0xFC) >> 2];
        strEncode += EncodeTable[((Tmp[1] & 0x03) << 4) | ((Tmp[2] & 0xF0) >> 4)];
        strEncode += EncodeTable[((Tmp[2] & 0x0F) << 2)];
        strEncode += "=";
    }

    return std::move(strEncode);
}

string Decode(const char* Data, int DataByte, int& OutByte)
{
    //返回值
    string strDecode;
    int nValue = 0;
    int i = 0;
    while (i < DataByte)
    {
        if (*Data != '\r' && *Data !='\n')
        {
            nValue = DecodeTable[(int)*Data++] << 18;
            nValue += DecodeTable[(int)*Data++] << 12;
            strDecode += (nValue & 0x00FF0000) >> 16;
            OutByte++;
            if (*Data != '=')
            {
                nValue += DecodeTable[(int)*Data++] << 6;
                strDecode += (nValue & 0x0000FF00) >> 8;
                OutByte++;
                if (*Data != '=')
                {
                    nValue += DecodeTable[(int)*Data++];
                    strDecode +=nValue & 0x000000FF;
                    OutByte++;
                }
            }
            i += 4;
        }
        else// 回车换行,跳过
        {
            Data++;
            i++;
        }
    }
    return std::move(strDecode);
}

#if _WIN32
#else
std::string get_local_ip_address(int ip_v)
{
    struct ifaddrs * ifAddrStruct=NULL;
    struct ifaddrs * ifa=NULL;
    void * tmpAddrPtr=NULL;
    std::string retStr, strV4, strV6;

    struct ipv6_mreq group;

    getifaddrs(&ifAddrStruct);

    for (ifa = ifAddrStruct; ifa != NULL; ifa = ifa->ifa_next)
    {
        if (!ifa->ifa_addr)
        {
            continue;
        }
        if (ifa->ifa_addr->sa_family == AF_INET) // check it is IP4
        {
            // is a valid IP4 Address
            tmpAddrPtr=&((struct sockaddr_in *)ifa->ifa_addr)->sin_addr;
            char addressBuffer[INET_ADDRSTRLEN + 1] = {0};
            inet_ntop(AF_INET, tmpAddrPtr, addressBuffer, INET_ADDRSTRLEN);
            strV4 = addressBuffer;
            printf("%s IP Address %s\n", ifa->ifa_name, addressBuffer);
        }
        else if (ifa->ifa_addr->sa_family == AF_INET6) // check it is IP6
        {
            // is a valid IP6 Address
            tmpAddrPtr=&((struct sockaddr_in6 *)ifa->ifa_addr)->sin6_addr;
            char addressBuffer[INET6_ADDRSTRLEN + 1] = {0};
            inet_ntop(AF_INET6, tmpAddrPtr, addressBuffer, INET6_ADDRSTRLEN);
            strV6 = addressBuffer;
            printf("%s IP Address %s\n", ifa->ifa_name, addressBuffer);
        }
        
    }
    if (ifAddrStruct!=NULL)
    {
        freeifaddrs(ifAddrStruct);
    }
    retStr = (ip_v == AF_INET)? strV4:strV6;

    return retStr;
}
#endif

void SPHexToStr(unsigned char* pOutStr, unsigned char* pInHex, int hexLen)
{
    unsigned char uchHex, uchTemp;
    bool bIsUpper = true;

    for (int i = 0; i < hexLen; ++i)
    {
        uchHex = pInHex[i];
        for (int j = 0; j < 2; ++j)
        {
            uchTemp = (uchHex & 0x0f);
            if (uchTemp < 10)
            {
                uchTemp += '0';
            }
            else
            {
                uchTemp += ((bIsUpper? 'A':'a') - 10);
            }
            pOutStr[2*i+1-j] = uchTemp;
            uchHex >>= 4;
        }
    }
}

unsigned char SPCharToInt(char ch)
{
	if (ch >= '0' && ch <= '9')
	{
		return (unsigned char)(ch - '0');
	}
	else if (ch >= 'a' && ch <= 'f')
	{
		return (unsigned char)(ch - 'a') + 10;
	}
	else if (ch >= 'A' && ch <= 'F')
	{
		return (unsigned char)(ch - 'A') + 10;
	}

	return 0u;
}

void SPStrToHex(unsigned char* pInStr, unsigned char* pOutHex, int strLen)
{
	unsigned char uchHex1, uchHex2, uchTemp1 = 0u, uchTemp2 = 0u;
	int k = 0;

	for (int i = 0; i < strLen; i += 2)
	{
		uchHex1 = (unsigned char)toupper(pInStr[i]);
		uchHex2 = (unsigned char)toupper(pInStr[i + 1]);
		uchTemp1 = SPCharToInt(uchHex1);
		uchTemp2 = SPCharToInt(uchHex2);
		pOutHex[k++] = (uchTemp1 << 4) | uchTemp2;
	}
}

void LoadIni()
{
#if _WIN32
#else
    char path[256] = {0};
    readlink("/proc/self/exe", path, sizeof(path));
    dirname(path);
    gpath = path;
    gpath += "/";
    std::ifstream fin(gpath + "/arhud_data.ini");
    if(fin.is_open())
    {
        ini.parse(fin);
    }
    fin.close();
    ini.interpolate();
#endif
}

// string split
void SPSplit(const std::string str, std::vector<std::string>& vecOut, const std::string delimiters)
{
	if (vecOut.size() > 0) {
		vecOut.clear();
		std::vector<std::string> tmp;
		vecOut.swap(tmp);
	}

	std::string::size_type pos1 = 0, pos2;
	pos2 = str.find(delimiters);
	pos1 = 0;
	while (std::string::npos != pos2)
	{
		vecOut.push_back(str.substr(pos1, pos2 - pos1));

		pos1 = pos2 + delimiters.size();
		pos2 = str.find(delimiters, pos1);
	}
	if (pos1 != str.length())
		vecOut.push_back(str.substr(pos1));
}



//-----------------------------------------------set data---------------------------------------
// VehiclePositionInfoNotify
uint32_t SetVehiclePositionInfoNotify(stVehiclePositionInfoNotify& stDy)
{
    int count = 0, len;
    std::string str;
    std::stringstream sstream;
    stDy.HdStatus = 2;
    std::vector<std::string> vecStr;
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "Checksum"                          ,stDy.Checksum                      ); //Checksum
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "Counter"                           ,stDy.Counter                       ); //Counter
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "Longitude"                         ,stDy.Longitude                     ); //Longitude
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "Latitude"                          ,stDy.Latitude                      ); //Latitude
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "altitude"                          ,stDy.altitude                      ); //altitude
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "Heading"                           ,stDy.Heading                       ); //Heading
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "hd_lane_left_angle"                ,stDy.hd_lane_left_angle            ); //hd_lane_left_angle
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "Hd_lane_right_angle"               ,stDy.Hd_lane_right_angle           ); //Hd_lane_right_angle
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "VehicleSpeed"                      ,stDy.VehicleSpeed                  ); //VehicleSpeed
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "acceleration"                      ,stDy.acceleration                  ); //acceleration
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "x_speed"                           ,stDy.x_speed                       ); //x_speed
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "y_speed"                           ,stDy.y_speed                       ); //y_speed
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "z_speed"                           ,stDy.z_speed                       ); //z_speed
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "timestamp"                         ,stDy.timestamp                     ); //timestamp
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "hd_link_id"                        ,stDy.hd_link_id                    ); //hd_link_id
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "hd_lane_id"                        ,stDy.hd_lane_id                    ); //hd_lane_id
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "hd_lane_type"                      ,stDy.hd_lane_type                  ); //hd_lane_type
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "on_lane_offset"                    ,stDy.on_lane_offset                ); //on_lane_offset
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "hd_lane_seq"                       ,stDy.hd_lane_seq                   ); //hd_lane_seq
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "hd_lane_num"                       ,stDy.hd_lane_num                   ); //hd_lane_num
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "hd_lane_left_lateral_offset"       ,stDy.hd_lane_left_lateral_offset   ); //hd_lane_left_lateral_offset
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "hd_lane_right_lateral_offset"      ,stDy.hd_lane_right_lateral_offset  ); //hd_lane_right_lateral_offset
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "roll"                              ,stDy.roll                          ); //roll
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "pitch"                             ,stDy.pitch                         ); //pitch
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "HdStatus"                          ,stDy.HdStatus                      ); //HdStatus
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "hdmap_version"                     ,stDy.hdmap_version                 ); //hdmap_version
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "fusion_status"                     ,stDy.fusion_status                 ); //fusion_status
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "pos_confidence"                    ,stDy.pos_confidence                ); //pos_confidence
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "position_type"                     ,stDy.position_type                 ); //position_type
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "break_light"                       ,stDy.break_light                   ); //break_light
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "indicator_light"                   ,stDy.indicator_light               ); //indicator_light
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "Lights"                            ,stDy.Lights                        ); //Lights
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "Weather"                           ,stDy.Weather                       ); //Weather
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "target_cruise_speed"               ,stDy.target_cruise_speed           ); //target_cruise_speed
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "FieldLength_target_lane"           ,stDy.FieldLength_target_lane       ); //FieldLength_target_lane
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "target_lane_id"                    ,str                                ); 
    count = stDy.FieldLength_target_lane /4;//sizeof(uint32_t)
    vecStr.clear();
    stDy.target_lane_id = new uint32_t[count];
    memset(stDy.target_lane_id, 0, sizeof(uint32_t)*count);
    SPSplit(str, vecStr, ",");
    for (int i = 0; i < count && i < vecStr.size(); ++i)
    {
        sstream<<vecStr[i];
        sstream>>stDy.target_lane_id[i];
        sstream.clear();
    }
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "FieldLength_target_lane_id_segment",stDy.FieldLength_target_lane_id_segment);
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "target_lane_id_segment"            ,str);
    count = stDy.FieldLength_target_lane_id_segment /4;//sizeof(uint32_t)
    vecStr.clear();
    stDy.target_lane_id_segment = new uint32_t[count];
    memset(stDy.target_lane_id_segment, 0, sizeof(uint32_t)*count);
    SPSplit(str, vecStr, ",");
    for (int i = 0; i < count && i < vecStr.size(); ++i)
    {
        sstream<<vecStr[i];
        sstream>>stDy.target_lane_id_segment[i];
        sstream.clear();
    }
    JxIni::get_value(ini.sections["VehiclePositionInfoNotify"], "localization_output_offset"        ,stDy.localization_output_offset);


    len = (sizeof(stVehiclePositionInfoNotify) - sizeof(uint32_t*)*2 +
     (stDy.FieldLength_target_lane/4)*sizeof(uint32_t) + (stDy.FieldLength_target_lane_id_segment/4)*sizeof(uint32_t));
    return len;
}

// RTKInfoNotify
uint32_t SetRTKInfoNotify(stRTKInfoNotify& stDy)
{
    JxIni::get_value(ini.sections["RTKInfoNotify"], "Checksum"      ,stDy.Checksum      ); //Checksum
    JxIni::get_value(ini.sections["RTKInfoNotify"], "Counter"       ,stDy.Counter       ); //Counter
    JxIni::get_value(ini.sections["RTKInfoNotify"], "rtk_status"        ,stDy.rtk_status        ); //rtk_status
    JxIni::get_value(ini.sections["RTKInfoNotify"], "utc_time_us"       ,stDy.utc_time_us       ); //utc_time_us
    JxIni::get_value(ini.sections["RTKInfoNotify"], "sys_time_us"   ,stDy.sys_time_us   ); //sys_time_us
    JxIni::get_value(ini.sections["RTKInfoNotify"], "longitude"        ,stDy.longitude        ); //longitude
    JxIni::get_value(ini.sections["RTKInfoNotify"], "latitude"         ,stDy.latitude         ); //latitude
    JxIni::get_value(ini.sections["RTKInfoNotify"], "altitude"         ,stDy.altitude         ); //altitude
    JxIni::get_value(ini.sections["RTKInfoNotify"], "longitude_acc"    ,stDy.longitude_acc    ); //longitude_acc
    JxIni::get_value(ini.sections["RTKInfoNotify"], "latitude_acc"     ,stDy.latitude_acc     ); //latitude_acc
    JxIni::get_value(ini.sections["RTKInfoNotify"], "altitude_acc"     ,stDy.altitude_acc     ); //altitude_acc
    JxIni::get_value(ini.sections["RTKInfoNotify"], "heading_move"      ,stDy.heading_move      ); //heading_move
    JxIni::get_value(ini.sections["RTKInfoNotify"], "heading_double_ant",stDy.heading_double_ant); //heading_double_ant
    JxIni::get_value(ini.sections["RTKInfoNotify"], "heading_move_acc"  ,stDy.heading_move_acc  ); //heading_move_acc
    JxIni::get_value(ini.sections["RTKInfoNotify"], "speed_2d"          ,stDy.speed_2d          ); //speed_2d
    JxIni::get_value(ini.sections["RTKInfoNotify"], "speed_acc"         ,stDy.speed_acc         ); //speed_acc
    JxIni::get_value(ini.sections["RTKInfoNotify"], "speed_n"           ,stDy.speed_n           ); //speed_n
    JxIni::get_value(ini.sections["RTKInfoNotify"], "speed_e"           ,stDy.speed_e           ); //speed_e
    JxIni::get_value(ini.sections["RTKInfoNotify"], "speed_u"           ,stDy.speed_u           ); //speed_u
    JxIni::get_value(ini.sections["RTKInfoNotify"], "g_dop"             ,stDy.g_dop             ); //g_dop
    JxIni::get_value(ini.sections["RTKInfoNotify"], "h_dop"             ,stDy.h_dop             ); //h_dop
    JxIni::get_value(ini.sections["RTKInfoNotify"], "v_dop"             ,stDy.v_dop             ); //v_dop
    JxIni::get_value(ini.sections["RTKInfoNotify"], "satellite_num"     ,stDy.satellite_num     ); //satellite_num
    JxIni::get_value(ini.sections["RTKInfoNotify"], "satellite_used"    ,stDy.satellite_used    ); //satellite_used
    JxIni::get_value(ini.sections["RTKInfoNotify"], "snr_max"           ,stDy.snr_max           ); //snr_max
    JxIni::get_value(ini.sections["RTKInfoNotify"], "snr_mix"           ,stDy.snr_mix           ); //snr_mix
    JxIni::get_value(ini.sections["RTKInfoNotify"], "snr_avr"           ,stDy.snr_avr           ); //snr_avr
    return (sizeof(stRTKInfoNotify));
}

 // IMUInfoNotify
uint32_t SetIMUInfoNotify(stIMUInfoNotify& stDy)
{
    JxIni::get_value(ini.sections["IMUInfoNotify"], "Checksum"                      ,stDy.Checksum                  ); //Checksum
    JxIni::get_value(ini.sections["IMUInfoNotify"], "Counter"                       ,stDy.Counter                   ); //Counter
    JxIni::get_value(ini.sections["IMUInfoNotify"], "angular_velocity_x"            ,stDy.angular_velocity_x        ); //angular_velocity_x
    JxIni::get_value(ini.sections["IMUInfoNotify"], "angular_velocity_y"            ,stDy.angular_velocity_y        ); //angular_velocity_y
    JxIni::get_value(ini.sections["IMUInfoNotify"], "angular_velocity_z"            ,stDy.angular_velocity_z        ); //angular_velocity_z  
    JxIni::get_value(ini.sections["IMUInfoNotify"], "acc_speed_x"                   ,stDy.acc_speed_x               ); //acc_speed_x
    JxIni::get_value(ini.sections["IMUInfoNotify"], "acc_speed_y"                   ,stDy.acc_speed_y               ); //acc_speed_y
    JxIni::get_value(ini.sections["IMUInfoNotify"], "acc_speed_z"                   ,stDy.acc_speed_z               ); //acc_speed_z
    JxIni::get_value(ini.sections["IMUInfoNotify"], "IMU_status"                    ,stDy.IMU_status                ); //IMU_status
    JxIni::get_value(ini.sections["IMUInfoNotify"], "IMU_current_temperature"       ,stDy.IMU_current_temperature   ); //IMU current temperature
    JxIni::get_value(ini.sections["IMUInfoNotify"], "sys_time_us"                   ,stDy.sys_time_us               ); //sys_time_us
    JxIni::get_value(ini.sections["IMUInfoNotify"], "is_calibrated"                 ,stDy.is_calibrated             ); //is_calibrated
    return (sizeof(stIMUInfoNotify));
}

// ObstacleInfoNotify
uint32_t SetObstacleInfoNotify(stObstacleInfoNotify& stDy)
{
    int count = 0, len;
    stDy.Checksum                                    = 1;   //Checksum
    stDy.Counter                                     = 2;   //Counter
    stDy.target_flag                                 = 3;   //target_flag
    stDy.FieldLength_Object_len                      = 194;   //FieldLength_Object
    if (stDy.FieldLength_Object_len > 0)
    {
        count = stDy.FieldLength_Object_len / 97;//sizeof(stObstacleInfoNotifyFLO);
        stDy.FieldLength_Object = new stObstacleInfoNotifyFLO[count];
        memset(stDy.FieldLength_Object, 0, sizeof(stObstacleInfoNotifyFLO)*count);
        for (int i = 0; i < count; ++i)
        {
            (stDy.FieldLength_Object+i)->ObstacleType              = 1;     //ObstacleType
            (stDy.FieldLength_Object+i)->confidence                = 2;     //confidence
            (stDy.FieldLength_Object+i)->Obstacle_Id_i             = 3;     //Obstacle Id_i
            (stDy.FieldLength_Object+i)->ObstacleDistance_X_i      = 4;     //ObstacleDistance_X_i
            (stDy.FieldLength_Object+i)->ObstacleDistance_Y_i      = 5;     //ObstacleDistance_Y_i
            (stDy.FieldLength_Object+i)->ObstacleDistance_Z_i      = 6;     //ObstacleDistance_Z_i
            (stDy.FieldLength_Object+i)->Bounding_box_length_i     = 7;     //Bounding_box_length_i
            (stDy.FieldLength_Object+i)->Bounding_box_width_i      = 8;     //Bounding_box_width_i
            (stDy.FieldLength_Object+i)->Bounding_box_height_i     = 9;     //Bounding_box_height_i
            (stDy.FieldLength_Object+i)->break_light               = 10;    //break_light
            (stDy.FieldLength_Object+i)->indicator_light           = 11;    //indicator_light
            (stDy.FieldLength_Object+i)->obj_speed                 = 12;    //obj_speed
            (stDy.FieldLength_Object+i)->ObstacleState             = 13;    //ObstacleState
            (stDy.FieldLength_Object+i)->obstacle_timestamp        = 14;    //obstacle_timestamp
            (stDy.FieldLength_Object+i)->obstacle_camera_timestamp = 15;    //obstacle_camera_timestamp
            (stDy.FieldLength_Object+i)->moving                    = 16;    //moving
            (stDy.FieldLength_Object+i)->obj_heading               = 17;    //obj_heading
            (stDy.FieldLength_Object+i)->Obj_direction             = 18;    //Obj_direction
            (stDy.FieldLength_Object+i)->ObstacleWarningBrakeState = 19;    //ObstacleWarningBrakeState
        }
    }
    return (sizeof(stObstacleInfoNotify) - sizeof(uint32_t*) + stDy.FieldLength_Object_len);
}

// LanelineDataNotify
uint32_t SetLanelineDataNotify(stLanelineDataNotify& stDy)
{
    int count = 0, len;
    stDy.Checksum                                            = 1;   //Checksum
    stDy.Counter                                             = 2;   //Counter
    stDy.FieldLength_Line_len                                = 132;   //FieldLength_Line
    if (stDy.FieldLength_Line_len > 0)
    {
        count = stDy.FieldLength_Line_len / 66;//sizeof(stLanelineDataNotifyFLL);
        stDy.FieldLength_Line = new stLanelineDataNotifyFLL[count];
        memset(stDy.FieldLength_Line, 0, sizeof(stLanelineDataNotifyFLL)*count);
        for (int i = 0; i < count; ++i)
        {
            (stDy.FieldLength_Line+i)->LineID                   = 1;     //LineID
            (stDy.FieldLength_Line+i)->LineType                 = 2;     //LineType
            (stDy.FieldLength_Line+i)->LineColor                = 3;     //LineColor
            (stDy.FieldLength_Line+i)->LineWidth                = 4;     //LineWidth
            (stDy.FieldLength_Line+i)->Line_confidence          = 5;     //Line_confidence
            (stDy.FieldLength_Line+i)->CurvatureEquation_c0     = 6;     //CurvatureEquation_c0
            (stDy.FieldLength_Line+i)->CurvatureEquation_c1     = 7;     //CurvatureEquation_c1
            (stDy.FieldLength_Line+i)->CurvatureEquation_c2     = 8;     //CurvatureEquation_c2
            (stDy.FieldLength_Line+i)->CurvatureEquation_c3     = 9;     //CurvatureEquation_c3
            (stDy.FieldLength_Line+i)->Line_Startpoint_x        = 10;    //Line_Startpoint_x
            (stDy.FieldLength_Line+i)->Line_Startpoint_y        = 11;    //Line_Startpoint_y
            (stDy.FieldLength_Line+i)->Line_Startpoint_z        = 12;    //Line_Startpoint_z
            (stDy.FieldLength_Line+i)->Line_Endpoint_x          = 13;    //Line_Endpoint_x
            (stDy.FieldLength_Line+i)->Line_Endpoint_y          = 14;    //Line_Endpoint_y
            (stDy.FieldLength_Line+i)->Line_Endpoint_z          = 15;    //Line_Endpoint_z
            (stDy.FieldLength_Line+i)->sys_time_us              = 16;    //sys_time_us
        }
    }

    stDy.FieldLength_RoadMarking_len                            = 114;   //FieldLength_RoadMarking_len
    if (stDy.FieldLength_RoadMarking_len > 0)
    {
        count = stDy.FieldLength_RoadMarking_len / 57;//sizeof(stLanelineDataNotifyFLRM);
        stDy.FieldLength_RoadMarking = new stLanelineDataNotifyFLRM[count];
        memset(stDy.FieldLength_RoadMarking, 0, sizeof(stLanelineDataNotifyFLRM)*count);
        for (int i = 0; i < count; ++i)
        {
            (stDy.FieldLength_RoadMarking+i)->RoadMarkingID_i                    = 1;     //RoadMarkingID_i
            (stDy.FieldLength_RoadMarking+i)->RoadMarkingType_i                  = 2;     //RoadMarkingType_i
            (stDy.FieldLength_RoadMarking+i)->RoadMarkingType_confidence_i       = 3;     //RoadMarkingType_confidence_i
            (stDy.FieldLength_RoadMarking+i)->RoadMarking_length_i               = 4;     //RoadMarking_length_i
            (stDy.FieldLength_RoadMarking+i)->RoadMarking_width_i                = 5;     //RoadMarking_width_i
            (stDy.FieldLength_RoadMarking+i)->RoadMarking_height_i               = 6;     //RoadMarking_height_i
            (stDy.FieldLength_RoadMarking+i)->RoadMarking_Distance_X_i           = 7;     //RoadMarking_Distance_X_i
            (stDy.FieldLength_RoadMarking+i)->RoadMarking_Distance_Y_i           = 8;     //RoadMarking_Distance_Y_i
            (stDy.FieldLength_RoadMarking+i)->RoadMarking_Distance_Z_i           = 9;     //RoadMarking_Distance_Z_i
            (stDy.FieldLength_RoadMarking+i)->RoadMarkingPosition_confidence     = 10;    //RoadMarkingPosition_confidence
        }
    }

    stDy.FieldLength_TLA_len                                    = 84;   //FieldLength_TLA_len
    if (stDy.FieldLength_TLA_len > 0)
    {
        count = stDy.FieldLength_TLA_len / 42;//sizeof(stLanelineDataNotifyFLTLA);
        stDy.FieldLength_TLA = new stLanelineDataNotifyFLTLA[count];
        memset(stDy.FieldLength_TLA, 0, sizeof(stLanelineDataNotifyFLTLA)*count);
        for (int i = 0; i < count; ++i)
        {
            (stDy.FieldLength_TLA+i)->TLAID_i                    = 1;     //TLAID_i
            (stDy.FieldLength_TLA+i)->TLA_Distance_X             = 2;     //TLA_Distance_X
            (stDy.FieldLength_TLA+i)->TLA_Distance_Y             = 3;     //TLA_Distance_Y
            (stDy.FieldLength_TLA+i)->TLA_Distance_Z             = 4;     //TLA_Distance_Z
            (stDy.FieldLength_TLA+i)->TLAPosition_confidence     = 5;     //TLAPosition_confidence
            (stDy.FieldLength_TLA+i)->LeftTLA_Color              = 6;     //LeftTLA_Color
            (stDy.FieldLength_TLA+i)->LeftTLA_Type               = 7;     //LeftTLA_Type
            (stDy.FieldLength_TLA+i)->StraightTLA_Color          = 8;     //StraightTLA_Color
            (stDy.FieldLength_TLA+i)->StraightTLA_Type           = 9;     //StraightTLA_Type
            (stDy.FieldLength_TLA+i)->RightTLA_Color             = 10;    //RightTLA_Color
            (stDy.FieldLength_TLA+i)->RightTLA_Type              = 10;    //RightTLA_Type
        }
    }
    return (sizeof(stLanelineDataNotify) - sizeof(uint32_t*)*3 + 
    stDy.FieldLength_Line_len + stDy.FieldLength_RoadMarking_len + stDy.FieldLength_TLA_len);
}

// ChangeLaneDataNotify
uint32_t SetChangeLaneDataNotify(stChangeLaneDataNotify& stDy)
{
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "Checksum"               ,stDy.Checksum              ); //Checksum
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "Counter"                ,stDy.Counter               ); //Counter
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "ChangeLaneState"        ,stDy.ChangeLaneState       ); //ChangeLaneState
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "ChangeLaneDirection"    ,stDy.ChangeLaneDirection   ); //ChangeLaneDirection
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "is_change_safety"       ,stDy.is_change_safety      ); //is_change_safety
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "ChangeLane_timestamp"   ,stDy.ChangeLane_timestamp  ); //ChangeLane_timestamp
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "change_ratio"           ,stDy.change_ratio          ); //change_ratio
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "change_termi"           ,stDy.change_termi          ); //change_termi
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "landing_center_X"       ,stDy.landing_center_X      ); //landing_center_X
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "landing_center_Y"       ,stDy.landing_center_Y      ); //landing_center_Y
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "landing_center_Z"       ,stDy.landing_center_Z      ); //landing_center_Z
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "landing_box_length"     ,stDy.landing_box_length    ); //landing_box_length
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "landing_box__width"     ,stDy.landing_box__width    ); //landing_box__width
    JxIni::get_value(ini.sections["ChangeLaneDataNotify"], "landing_box_height"     ,stDy.landing_box_height    ); //landing_box_height
    return (sizeof(stChangeLaneDataNotify));
}

// PilotStatusNotify
uint32_t SetPilotStatusNotify(stPilotStatusNotify& stDy)
{
    JxIni::get_value(ini.sections["PilotStatusNotify"], "Checksum"           ,stDy.Checksum                     ); //Checksum
    JxIni::get_value(ini.sections["PilotStatusNotify"], "Counter"            ,stDy.Counter                      ); //Counter
    JxIni::get_value(ini.sections["PilotStatusNotify"], "ACCStatus"          ,stDy.ACCStatus                    ); //ACCStatus
    JxIni::get_value(ini.sections["PilotStatusNotify"], "ICCStatus"          ,stDy.ICCStatus                    ); //ICCStatus
    JxIni::get_value(ini.sections["PilotStatusNotify"], "DNPStatus"          ,stDy.DNPStatus                    ); //DNPStatus
    JxIni::get_value(ini.sections["PilotStatusNotify"], "TakeoverStatus"     ,stDy.TakeoverStatus               ); //TakeoverStatus
    JxIni::get_value(ini.sections["PilotStatusNotify"], "driving_time"       ,stDy.driving_time                 ); //driving_time
    return (sizeof(stPilotStatusNotify));
}

// PilotAlarmAndNoticeInfoNotify
uint32_t SetPilotAlarmAndNoticeInfoNotify(stPilotAlarmAndNoticeInfoNotify& stDy)
{
    JxIni::get_value(ini.sections["PilotAlarmAndNoticeInfoNotify"], "Checksum"           ,stDy.Checksum         ); //Checksum
    JxIni::get_value(ini.sections["PilotAlarmAndNoticeInfoNotify"], "Counter"            ,stDy.Counter          ); //Counter
    JxIni::get_value(ini.sections["PilotAlarmAndNoticeInfoNotify"], "PilotAlarmReason"   ,stDy.PilotAlarmReason ); //PilotAlarmReason
    JxIni::get_value(ini.sections["PilotAlarmAndNoticeInfoNotify"], "alarm_distance"     ,stDy.alarm_distance   ); //alarm_distance
    JxIni::get_value(ini.sections["PilotAlarmAndNoticeInfoNotify"], "alarm_stage"        ,stDy.alarm_stage      ); //alarm_stage
    JxIni::get_value(ini.sections["PilotAlarmAndNoticeInfoNotify"], "alarm_timestamp"    ,stDy.alarm_timestamp  ); //alarm_timestamp
    JxIni::get_value(ini.sections["PilotAlarmAndNoticeInfoNotify"], "PilotNotice"        ,stDy.PilotNotice      ); //PilotNotice
    JxIni::get_value(ini.sections["PilotAlarmAndNoticeInfoNotify"], "notice_distance"    ,stDy.notice_distance  ); //notice_distance
    JxIni::get_value(ini.sections["PilotAlarmAndNoticeInfoNotify"], "notice_timestamp"   ,stDy.notice_timestamp ); //notice_timestamp
    return (sizeof(stPilotAlarmAndNoticeInfoNotify));
}

// BroadcastInfoNotify
uint32_t SetBroadcastInfoNotify(stBroadcastInfoNotify& stDy)
{
    JxIni::get_value(ini.sections["BroadcastInfoNotify"], "Checksum"          ,stDy.Checksum                    ); //Checksum
    JxIni::get_value(ini.sections["BroadcastInfoNotify"], "Counter"           ,stDy.Counter                     ); //Counter
    JxIni::get_value(ini.sections["BroadcastInfoNotify"], "driver_attention"  ,stDy.driver_attention            ); //driver_attention
    JxIni::get_value(ini.sections["BroadcastInfoNotify"], "large_vehicles"    ,stDy.large_vehicles              ); //large_vehicles
    JxIni::get_value(ini.sections["BroadcastInfoNotify"], "dangerous_vehicle" ,stDy.dangerous_vehicle           ); //dangerous_vehicle
    JxIni::get_value(ini.sections["BroadcastInfoNotify"], "pedestrians"       ,stDy.pedestrians                 ); //pedestrians
    return (sizeof(stBroadcastInfoNotify));
}

// // PlanningLineInfoNotify
// uint32_t SetPlanningLineInfoNotify(stPlanningLineInfoNotify& stDy)
// {
//     int count = 0, len;
//     stDy.Checksum                                  = 1;     //Checksum
//     stDy.Counter                                   = 2;     //Counter
//     stDy.PlanningLineStatus                        = 3;     //PlanningLineStatus
//     stDy.planning_timestamp                        = 4;     //planning_timestamp
//     stDy.FieldLength_PlanningLinePoints_len        = 56;    //FieldLength_PlanningLinePoints
//     if (stDy.FieldLength_PlanningLinePoints_len > 0)
//     {
//         count = stDy.FieldLength_PlanningLinePoints_len / 28;//sizeof(stPlanningLineInfoNotifyFPLP);
//         stDy.FieldLength_PlanningLinePoints = new stPlanningLineInfoNotifyFPLP[count];
//         memset(stDy.FieldLength_PlanningLinePoints, 0, sizeof(stPlanningLineInfoNotifyFPLP)*count);
//         for (int i = 0; i < count; ++i)
//         {
//             (stDy.FieldLength_PlanningLinePoints+i)->PlanningLinePointsID_i             = 1;     //target_lane_id
//             (stDy.FieldLength_PlanningLinePoints+i)->points_X                           = 2;     //points_X
//             (stDy.FieldLength_PlanningLinePoints+i)->points_Y                           = 3;     //points_Y
//             (stDy.FieldLength_PlanningLinePoints+i)->points_Z                           = 4;     //points_Z
//         }
//     }
//     return (sizeof(stPlanningLineInfoNotify) - sizeof(uint32_t*) + stDy.FieldLength_PlanningLinePoints_len);
// }

// HudRoadInfoNotify
uint32_t SetHudRoadInfoNotify(stHudRoadInfoNotify& stDy)
{
    int count = 0;
    std::string str;
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Checksum"                  ,stDy.Checksum                 ); //Checksum
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Counter"                   ,stDy.Counter                  ); //Counter
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "car_2_dest"                ,stDy.car_2_dest               ); //car_2_dest
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "time_of_car_2_dest"        ,stDy.time_of_car_2_dest       ); //time_of_car_2_dest
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Num_of_lanes"              ,stDy.Num_of_lanes             ); //Num_of_lanes
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Current_road_level"        ,stDy.Current_road_level       ); //Current_road_level
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Permissible_direction"     ,str                           ); //Permissible_direction

    std::mutex mt;
    std::unique_lock<std::mutex> itslock(mt);
    std::ifstream fin(gpath + str);
    if (fin.is_open())
    {
        fin.seekg(0, std::ios::end);
        stDy.Permissible_direction_len = fin.tellg();
        fin.seekg(0, std::ios::beg);
        count = stDy.Permissible_direction_len / 1;//sizeof(uint8_t);
        stDy.Permissible_direction = new uint8_t[count];
        memset(stDy.Permissible_direction, 0, sizeof(uint8_t)*count);
        fin.read((char*)stDy.Permissible_direction, stDy.Permissible_direction_len);
    }
    if (!fin.is_open() || stDy.Permissible_direction_len <= 0)
    {
       printf("%s %d:\r\n %sfile open failed, size=%u\r\n", __FILE__, __LINE__, str.c_str(), stDy.Permissible_direction_len);
    }
    fin.close();

    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Recommended_driving_directions_for_AJOTP"     ,str         ); //Recommended_driving_directions_for_AJOTP
    fin.open(gpath + str);
    if (fin.is_open())
    {
        fin.seekg(0, std::ios::end);
        stDy.Recommended_driving_directions_for_AJOTP_len = fin.tellg();
        fin.seekg(0, std::ios::beg);
        count = stDy.Recommended_driving_directions_for_AJOTP_len / 1;//sizeof(uint8_t);
        stDy.Recommended_driving_directions_for_AJOTP = new uint8_t[count];
        memset(stDy.Recommended_driving_directions_for_AJOTP, 0, sizeof(uint8_t)*count);
        fin.read((char*)stDy.Recommended_driving_directions_for_AJOTP, stDy.Recommended_driving_directions_for_AJOTP_len);
    }
    if (!fin.is_open() || stDy.Recommended_driving_directions_for_AJOTP_len <= 0)
    {
        printf("%s %d:\r\n %sfile open failed, size=%u\r\n", __FILE__, __LINE__, str.c_str(), stDy.Recommended_driving_directions_for_AJOTP_len);
    }
    fin.close();

    stDy.POI_information="11";
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "distance_2_intersection"       ,stDy.distance_2_intersection         ); //distance_2_intersection
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "next_road_name"                ,stDy.next_road_name                  ); //next_road_name
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Current_max_speed_limit"       ,stDy.Current_max_speed_limit         ); //Current_max_speed_limit
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Current_speed"                 ,stDy.Current_speed                   ); //Current_speed
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Distance_2_speed_limit_zone"   ,stDy.Distance_2_speed_limit_zone     ); //Distance_2_speed_limit_zone
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "length_of_speed_limit"         ,stDy.length_of_speed_limit           ); //length_of_speed_limit
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "speed_limit"                   ,stDy.speed_limit                     ); //speed_limit
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "navigating_status"             ,stDy.navigating_status               ); //navigating_status
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "camera_ahead_status"           ,stDy.camera_ahead_status             ); //camera_ahead_status
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "The_distance_2_camera"         ,stDy.The_distance_2_camera           ); //The_distance_2_camera
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "vehicle_coordinates_Longitude" ,stDy.vehicle_coordinates_Longitude   ); //vehicle_coordinates_Longitude
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "vehicle_coordinates_Latitude"  ,stDy.vehicle_coordinates_Latitude    ); //vehicle_coordinates_Latitude
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "vehicle_speed"                 ,stDy.vehicle_speed                   ); //vehicle_speed
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "vehicle_altitude"              ,stDy.vehicle_altitude                ); //vehicle_altitude
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Danger_signs"                  ,stDy.Danger_signs                    ); //Danger_signs
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "POI_information"               ,stDy.POI_information                 ); //POI_information
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "reach_the_destination"         ,stDy.reach_the_destination           ); //reach_the_destination
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "ETA_info_time"                 ,stDy.ETA_info_time                   ); //ETA_info_time
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "ETA_info_remain_time"          ,stDy.ETA_info_remain_time            ); //ETA_info_remain_time
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "RecommendedDrivingDirectionsId",stDy.RecommendedDrivingDirectionsId  ); //RecommendedDrivingDirectionsId
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "lanesPermissibleDirectionId"   ,stDy.lanesPermissibleDirectionId     ); //lanesPermissibleDirectionId
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "guideLine"                     ,stDy.guideLine                       ); //guideLine
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "guidePoint"                    ,stDy.guidePoint                      ); //guidePoint
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "vehicleHeading"                ,stDy.vehicleHeading                  ); //vehicleHeading
    JxIni::get_value(ini.sections["HudRoadInfoNotify"], "Navigating_ratio"              ,stDy.Navigating_ratio                ); //Navigating_ratio

    return (77 + stDy.Permissible_direction_len + stDy.Recommended_driving_directions_for_AJOTP_len +
    stDy.next_road_name.length() + stDy.POI_information.length() + stDy.reach_the_destination.length() +
    stDy.ETA_info_time.length() + stDy.ETA_info_remain_time.length() + stDy.lanesPermissibleDirectionId.length() + 
    stDy.guideLine.length() + stDy.guidePoint.length() + 8 * 8);
}

// HudMappathInfo_EG
uint32_t SetHudMappathInfo_EG(stHudMappathInfo_EG& stDy)
{
    JxIni::get_value(ini.sections["HudMappathInfo_EG"], "Checksum"          ,stDy.Checksum            ); //Checksum
    JxIni::get_value(ini.sections["HudMappathInfo_EG"], "Counter"           ,stDy.Counter             ); //Counter
    JxIni::get_value(ini.sections["HudMappathInfo_EG"], "is_on_the_path"    ,stDy.is_on_the_path      ); //is_on_the_path
    JxIni::get_value(ini.sections["HudMappathInfo_EG"], "road_angle"        ,stDy.road_angle          ); //road_angle
    JxIni::get_value(ini.sections["HudMappathInfo_EG"], "road_slope"        ,stDy.road_slope          ); //road_slope
    JxIni::get_value(ini.sections["HudMappathInfo_EG"], "all_EHP_v2_info"   ,stDy.all_EHP_v2_info     ); //all_EHP_v2_info
    return (12+stDy.all_EHP_v2_info.length() + 8);
}

// HudNavigationmap
uint32_t SetHudNavigationmap(stHudNavigationmap& stDy)
{
    int count = 0;
    std::string str;
    JxIni::get_value(ini.sections["HudNavigationmap"], "Navigation_map"     ,str         ); //Navigation_map
    std::mutex mt;
    std::unique_lock<std::mutex> itslock(mt);
    std::ifstream fin(gpath + str);
    if (fin.is_open())
    {
        fin.seekg(0, std::ios::end);
        stDy.Navigation_map_len = fin.tellg();
        fin.seekg(0, std::ios::beg);
        count = stDy.Navigation_map_len / 1;//sizeof(uint8_t);
        uint8_t* pdata = new uint8_t[count];
        memset(pdata, 0, sizeof(uint8_t)*count);
        fin.read((char*)pdata, stDy.Navigation_map_len);
        stDy.Navigation_map.assign((const char*)pdata, count);
    }
    if (!fin.is_open() || stDy.Navigation_map_len <= 0)
    {
        printf("%s %d:\r\n %sfile open failed, size=%u\r\n", __FILE__, __LINE__, str.c_str(), stDy.Navigation_map_len);
    }
    fin.close();
    return (sizeof(stHudNavigationmap)- sizeof(uint32_t*) + stDy.Navigation_map_len);
}




// VehiclePositionInfoNotify
uint32_t SetVehiclePositionInfoNotify2(stVehiclePositionInfoNotify& stDy)
{
    int count = 0, len;
    std::string str;
    std::stringstream sstream;
    stDy.HdStatus = 2;
    std::vector<std::string> vecStr;
    stDy.Checksum                      = 1  ; //Checksum
    stDy.Counter                       = 2  ; //Counter
    stDy.Longitude                     = 3  ; //Longitude
    stDy.Latitude                      = 4  ; //Latitude
    stDy.altitude                      = 5  ; //altitude
    stDy.Heading                       = 6  ; //Heading
    stDy.hd_lane_left_angle            = 7  ; //hd_lane_left_angle
    stDy.Hd_lane_right_angle           = 8  ; //Hd_lane_right_angle
    stDy.VehicleSpeed                  = 9  ; //VehicleSpeed
    stDy.acceleration                  = 10  ; //acceleration
    stDy.x_speed                       = 11  ; //x_speed
    stDy.y_speed                       = 12  ; //y_speed
    stDy.z_speed                       = 13  ; //z_speed
    stDy.timestamp                     = 14  ; //timestamp
    stDy.hd_link_id                    = 15  ; //hd_link_id
    stDy.hd_lane_id                    = 16  ; //hd_lane_id
    stDy.hd_lane_type                  = 17  ; //hd_lane_type
    stDy.on_lane_offset                = 18  ; //on_lane_offset
    stDy.hd_lane_seq                   = 19  ; //hd_lane_seq
    stDy.hd_lane_num                   = 20  ; //hd_lane_num
    stDy.hd_lane_left_lateral_offset   = 21  ; //hd_lane_left_lateral_offset
    stDy.hd_lane_right_lateral_offset  = 22  ; //hd_lane_right_lateral_offset
    stDy.roll                          = 23  ; //roll
    stDy.pitch                         = 24  ; //pitch
    stDy.HdStatus                      = 25  ; //HdStatus
    stDy.hdmap_version                 = 26  ; //hdmap_version
    stDy.fusion_status                 = 27  ; //fusion_status
    stDy.pos_confidence                = 28  ; //pos_confidence
    stDy.position_type                 = 29  ; //position_type
    stDy.break_light                   = 30  ; //break_light
    stDy.indicator_light               = 31  ; //indicator_light
    stDy.Lights                        = 32  ; //Lights
    stDy.Weather                       = 33  ; //Weather
    stDy.target_cruise_speed           = 34  ; //target_cruise_speed
    stDy.FieldLength_target_lane       = 12  ; //FieldLength_target_lane
    str                                = 36  ; 
    count = stDy.FieldLength_target_lane = DYNAMIC_CNT*sizeof(uint32_t);
    stDy.target_lane_id = new uint32_t[DYNAMIC_CNT];
    memset(stDy.target_lane_id, 0, sizeof(uint32_t)*DYNAMIC_CNT);
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        stDy.target_lane_id[i] = i;
    }
    stDy.FieldLength_target_lane_id_segment = DYNAMIC_CNT*sizeof(uint32_t);
    stDy.target_lane_id_segment = new uint32_t[DYNAMIC_CNT];
    memset(stDy.target_lane_id_segment, 0, sizeof(uint32_t)*DYNAMIC_CNT);
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        stDy.target_lane_id_segment[i] = i;
    }
    stDy.localization_output_offset = 37;

    len = (sizeof(stVehiclePositionInfoNotify) - sizeof(uint32_t*)*2 +
     (stDy.FieldLength_target_lane/4)*sizeof(uint32_t) + (stDy.FieldLength_target_lane_id_segment/4)*sizeof(uint32_t));
    return len;
}

// RTKInfoNotify
uint32_t SetRTKInfoNotify2(stRTKInfoNotify& stDy)
{
    stDy.Checksum           = 1 ; //Checksum
    stDy.Counter            = 2 ; //Counter
    stDy.rtk_status         = 3 ; //rtk_status
    stDy.utc_time_us        = 4 ; //utc_time_us
    stDy.sys_time_us        = 5 ; //sys_time_us
    stDy.longitude          = 6 ; //longitude
    stDy.latitude           = 7 ; //latitude
    stDy.altitude           = 8 ; //altitude
    stDy.longitude_acc      = 9 ; //longitude_acc
    stDy.latitude_acc       = 10 ; //latitude_acc
    stDy.altitude_acc       = 11 ; //altitude_acc
    stDy.heading_move       = 12 ; //heading_move
    stDy.heading_double_ant = 13 ; //heading_double_ant
    stDy.heading_move_acc   = 14 ; //heading_move_acc
    stDy.speed_2d           = 15 ; //speed_2d
    stDy.speed_acc          = 16 ; //speed_acc
    stDy.speed_n            = 17 ; //speed_n
    stDy.speed_e            = 18 ; //speed_e
    stDy.speed_u            = 19 ; //speed_u
    stDy.g_dop              = 20 ; //g_dop
    stDy.h_dop              = 21 ; //h_dop
    stDy.v_dop              = 22 ; //v_dop
    stDy.satellite_num      = 23 ; //satellite_num
    stDy.satellite_used     = 24 ; //satellite_used
    stDy.snr_max            = 25 ; //snr_max
    stDy.snr_mix            = 26 ; //snr_mix
    stDy.snr_avr            = 27 ; //snr_avr
    return (sizeof(stRTKInfoNotify));
}

 // IMUInfoNotify
uint32_t SetIMUInfoNotify2(stIMUInfoNotify& stDy)
{
    stDy.Checksum                  = 1  ; //Checksum
    stDy.Counter                   = 2  ; //Counter
    stDy.angular_velocity_x        = 3  ; //angular_velocity_x
    stDy.angular_velocity_y        = 4  ; //angular_velocity_y
    stDy.angular_velocity_z        = 5  ; //angular_velocity_z  
    stDy.acc_speed_x               = 6  ; //acc_speed_x
    stDy.acc_speed_y               = 7  ; //acc_speed_y
    stDy.acc_speed_z               = 8  ; //acc_speed_z
    stDy.IMU_status                = 9  ; //IMU_status
    stDy.IMU_current_temperature   = 10  ; //IMU current temperature
    stDy.sys_time_us               = 11  ; //sys_time_us
    stDy.is_calibrated             = 12  ; //is_calibrated
    return (sizeof(stIMUInfoNotify));
}

// ObstacleInfoNotify
uint32_t SetObstacleInfoNotify2(stObstacleInfoNotify& stDy)
{
    int count = 0, len;
    stDy.Checksum                                    = 1;   //Checksum
    stDy.Counter                                     = 2;   //Counter
    stDy.target_flag                                 = 3;   //target_flag
    stDy.FieldLength_Object_len                      = DYNAMIC_CNT*sizeof(stObstacleInfoNotifyFLO);   //FieldLength_Object
    if (stDy.FieldLength_Object_len > 0)
    {
        stDy.FieldLength_Object = new stObstacleInfoNotifyFLO[DYNAMIC_CNT];
        memset(stDy.FieldLength_Object, 0, sizeof(stObstacleInfoNotifyFLO)*DYNAMIC_CNT);
        for (int i = 0; i < DYNAMIC_CNT; ++i)
        {
            (stDy.FieldLength_Object+i)->ObstacleType              = 1;     //ObstacleType
            (stDy.FieldLength_Object+i)->confidence                = 2;     //confidence
            (stDy.FieldLength_Object+i)->Obstacle_Id_i             = 3;     //Obstacle Id_i
            (stDy.FieldLength_Object+i)->ObstacleDistance_X_i      = 4;     //ObstacleDistance_X_i
            (stDy.FieldLength_Object+i)->ObstacleDistance_Y_i      = 5;     //ObstacleDistance_Y_i
            (stDy.FieldLength_Object+i)->ObstacleDistance_Z_i      = 6;     //ObstacleDistance_Z_i
            (stDy.FieldLength_Object+i)->Bounding_box_length_i     = 7;     //Bounding_box_length_i
            (stDy.FieldLength_Object+i)->Bounding_box_width_i      = 8;     //Bounding_box_width_i
            (stDy.FieldLength_Object+i)->Bounding_box_height_i     = 9;     //Bounding_box_height_i
            (stDy.FieldLength_Object+i)->break_light               = 10;    //break_light
            (stDy.FieldLength_Object+i)->indicator_light           = 11;    //indicator_light
            (stDy.FieldLength_Object+i)->obj_speed                 = 12;    //obj_speed
            (stDy.FieldLength_Object+i)->ObstacleState             = 13;    //ObstacleState
            (stDy.FieldLength_Object+i)->obstacle_timestamp        = 14;    //obstacle_timestamp
            (stDy.FieldLength_Object+i)->obstacle_camera_timestamp = 15;    //obstacle_camera_timestamp
            (stDy.FieldLength_Object+i)->moving                    = 16;    //moving
            (stDy.FieldLength_Object+i)->obj_heading               = 17;    //obj_heading
            (stDy.FieldLength_Object+i)->Obj_direction             = 18;    //Obj_direction
            (stDy.FieldLength_Object+i)->ObstacleWarningBrakeState = 19;    //ObstacleWarningBrakeState
        }
    }
    return (sizeof(stObstacleInfoNotify) - sizeof(uint32_t*) + stDy.FieldLength_Object_len);
}

uint32_t SetLanelineDataNotify2(stLanelineDataNotify& stDy)
{
    return SetLanelineDataNotify(stDy);
}

// ChangeLaneDataNotify
uint32_t SetChangeLaneDataNotify2(stChangeLaneDataNotify& stDy)
{
    stDy.Checksum              = 1  ; //Checksum
    stDy.Counter               = 2  ; //Counter
    stDy.ChangeLaneState       = 3  ; //ChangeLaneState
    stDy.ChangeLaneDirection   = 4  ; //ChangeLaneDirection
    stDy.is_change_safety      = 5  ; //is_change_safety
    stDy.ChangeLane_timestamp  = 6  ; //ChangeLane_timestamp
    stDy.change_ratio          = 7  ; //change_ratio
    stDy.change_termi          = 8  ; //change_termi
    stDy.landing_center_X      = 9  ; //landing_center_X
    stDy.landing_center_Y      = 10  ; //landing_center_Y
    stDy.landing_center_Z      = 11  ; //landing_center_Z
    stDy.landing_box_length    = 12  ; //landing_box_length
    stDy.landing_box__width    = 13  ; //landing_box__width
    stDy.landing_box_height    = 14  ; //landing_box_height
    return (sizeof(stChangeLaneDataNotify));
}

// PilotStatusNotify
uint32_t SetPilotStatusNotify2(stPilotStatusNotify& stDy)
{
    stDy.Checksum                     = 1   ; //Checksum
    stDy.Counter                      = 2   ; //Counter
    stDy.ACCStatus                    = 3   ; //ACCStatus
    stDy.ICCStatus                    = 4   ; //ICCStatus
    stDy.DNPStatus                    = 5   ; //DNPStatus
    stDy.TakeoverStatus               = 6   ; //TakeoverStatus
    stDy.driving_time                 = 7   ; //driving_time
    return (sizeof(stPilotStatusNotify));
}

// PilotAlarmAndNoticeInfoNotify
uint32_t SetPilotAlarmAndNoticeInfoNotify2(stPilotAlarmAndNoticeInfoNotify& stDy)
{
    stDy.Checksum         = 1   ; //Checksum
    stDy.Counter          = 2   ; //Counter
    stDy.PilotAlarmReason = 3   ; //PilotAlarmReason
    stDy.alarm_distance   = 4   ; //alarm_distance
    stDy.alarm_stage      = 5   ; //alarm_stage
    stDy.alarm_timestamp  = 6   ; //alarm_timestamp
    stDy.PilotNotice      = 7   ; //PilotNotice
    stDy.notice_distance  = 8   ; //notice_distance
    stDy.notice_timestamp = 9   ; //notice_timestamp
    return (sizeof(stPilotAlarmAndNoticeInfoNotify));
}

// BroadcastInfoNotify
uint32_t SetBroadcastInfoNotify2(stBroadcastInfoNotify& stDy)
{
    stDy.Checksum                    = 1    ; //Checksum
    stDy.Counter                     = 2    ; //Counter
    stDy.driver_attention            = 3    ; //driver_attention
    stDy.large_vehicles              = 4    ; //large_vehicles
    stDy.dangerous_vehicle           = 5    ; //dangerous_vehicle
    stDy.pedestrians                 = 6    ; //pedestrians
    return (sizeof(stBroadcastInfoNotify));
}

// // PlanningLineInfoNotify
// uint32_t SetPlanningLineInfoNotify2(stPlanningLineInfoNotify& stDy)
// {
//     SetPlanningLineInfoNotify(stDy);
// }

// HudRoadInfoNotify
uint32_t SetHudRoadInfoNotify2(stHudRoadInfoNotify& stDy)
{
    int count = 0;
    std::string str;
    stDy.Checksum                 = 1   ; //Checksum
    stDy.Counter                  = 2   ; //Counter
    stDy.car_2_dest               = 3   ; //car_2_dest
    stDy.time_of_car_2_dest       = 4   ; //time_of_car_2_dest
    stDy.Num_of_lanes             = 5   ; //Num_of_lanes
    stDy.Current_road_level       = 6   ; //Current_road_level
    str                           = "7"   ; //Permissible_direction

    std::mutex mt;
    std::unique_lock<std::mutex> itslock(mt);

    stDy.Permissible_direction_len = 3;
    count = stDy.Permissible_direction_len / 1;//sizeof(uint8_t);
    stDy.Permissible_direction = new uint8_t[count];
    memset(stDy.Permissible_direction, 1, sizeof(uint8_t)*count);

    stDy.Recommended_driving_directions_for_AJOTP_len = 3;
    count = stDy.Recommended_driving_directions_for_AJOTP_len / 1;//sizeof(uint8_t);
    stDy.Recommended_driving_directions_for_AJOTP = new uint8_t[count];
    memset(stDy.Recommended_driving_directions_for_AJOTP, 2, sizeof(uint8_t)*count);

    stDy.POI_information="11";
    stDy.distance_2_intersection         = 11    ; //distance_2_intersection
    stDy.next_road_name                  = "next_road_name"    ; //next_road_name
    stDy.Current_max_speed_limit         = 13    ; //Current_max_speed_limit
    stDy.Current_speed                   = 14    ; //Current_speed
    stDy.Distance_2_speed_limit_zone     = 15    ; //Distance_2_speed_limit_zone
    stDy.length_of_speed_limit           = 16    ; //length_of_speed_limit
    stDy.speed_limit                     = 17    ; //speed_limit
    stDy.navigating_status               = 18    ; //navigating_status
    stDy.camera_ahead_status             = 19    ; //camera_ahead_status
    stDy.The_distance_2_camera           = 20    ; //The_distance_2_camera
    stDy.vehicle_coordinates_Longitude   = 21    ; //vehicle_coordinates_Longitude
    stDy.vehicle_coordinates_Latitude    = 22    ; //vehicle_coordinates_Latitude
    stDy.vehicle_speed                   = 23    ; //vehicle_speed
    stDy.vehicle_altitude                = 24    ; //vehicle_altitude
    stDy.Danger_signs                    = 25    ; //Danger_signs
    stDy.POI_information                 = "POI_information"    ; //POI_information
    stDy.reach_the_destination           = "reach_the_destination"    ; //reach_the_destination
    stDy.ETA_info_time                   = "ETA_info_time"    ; //ETA_info_time
    stDy.ETA_info_remain_time            = "ETA_info_remain_time"    ; //ETA_info_remain_time
    stDy.RecommendedDrivingDirectionsId  = 30    ; //RecommendedDrivingDirectionsId
    stDy.lanesPermissibleDirectionId     = "lanesPermissibleDirectionId"    ; //lanesPermissibleDirectionId
    stDy.guideLine                       = "guideLine"    ; //guideLine
    stDy.guidePoint                      = "guidePoint"    ; //guidePoint
    stDy.vehicleHeading                  = 34    ; //vehicleHeading
    stDy.Navigating_ratio                = 35    ; //Navigating_ratio

    return (77 + stDy.Permissible_direction_len + stDy.Recommended_driving_directions_for_AJOTP_len +
    stDy.next_road_name.length() + stDy.POI_information.length() + stDy.reach_the_destination.length() +
    stDy.ETA_info_time.length() + stDy.ETA_info_remain_time.length() + stDy.lanesPermissibleDirectionId.length() + 
    stDy.guideLine.length() + stDy.guidePoint.length() + 8 * 8);
}

// oshrinfo_t
uint32_t SetOverseasHudRoadInfoNotify2(oshrinfo_t& stDy)
{
    stDy.Checksum = 1   ;
    stDy.Counter = 2    ;
    stDy.car_2_dest = 3 ;
    stDy.time_of_car_2_dest = 4 ;
    stDy.Num_of_lanes = 5   ;
    stDy.Current_road_level = 6 ;

    stDy.Permissible_direction_len = DYNAMIC_CNT*sizeof(uint8_t);
    stDy.Permissible_direction = new uint8_t[DYNAMIC_CNT];
    memset(stDy.Permissible_direction, 0, DYNAMIC_CNT*sizeof(uint8_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.Permissible_direction + i) = i  ; 
    }

    stDy.Recommended_driving_directions_for_AJOTP_len = DYNAMIC_CNT*sizeof(uint8_t);
    stDy.Recommended_driving_directions_for_AJOTP = new uint8_t[DYNAMIC_CNT];
    memset(stDy.Recommended_driving_directions_for_AJOTP, 0, DYNAMIC_CNT*sizeof(uint8_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.Recommended_driving_directions_for_AJOTP + i) = i  ; 
    }

    stDy.distance_2_intersection                = 7 ;
    stDy.next_road_name                         = "next_road_name" ;
    stDy.Current_max_speed_limit                = 9 ;
    stDy.Current_speed                          = 10 ;
    stDy.Distance_2_speed_limit_zone            = 11 ;
    stDy.length_of_speed_limit                  = 12 ;
    stDy.speed_limit                            = 13 ;
    stDy.navigating_status                      = 14 ;
    stDy.camera_ahead_status                    = 15 ;
    stDy.The_distance_2_camera                  = 16 ;
    stDy.vehicle_coordinates_Longitude          = 17 ;
    stDy.vehicle_coordinates_Latitude           = 18 ;
    stDy.vehicle_speed                          = 19 ;
    stDy.vehicle_altitude                       = 20 ;
    stDy.Danger_signs                           = 21 ;
    stDy.POI_information                        = "POI_information" ;
    stDy.reach_the_destination                  = "reach_the_destination" ;
    stDy.ETA_info_time                          = "ETA_info_time" ;
    stDy.ETA_info_remain_time                   = "ETA_info_remain_time" ;
    stDy.RecommendedDrivingDirectionsId         = 26 ;
    stDy.lanesPermissibleDirectionId            = "lanesPermissibleDirectionId" ;
    stDy.guideLine                              = "guideLine" ;
    stDy.guidePoint                             = "guidePoint" ;
    stDy.vehicleHeading                         = 30 ;
    stDy.Navigating_ratio                       = 31 ;
    stDy.mapProviders                           = 32 ;
    stDy.carToDestDistance                      = "carToDestDistance" ;
    stDy.distanceToIntersection                 = "distanceToIntersection" ;
    stDy.timeToDest                             = "timeToDest" ;
    stDy.recommendedDrivingDirectionsIdOverseas = 36 ;

    stDy.reservedDataLength1 = DYNAMIC_CNT*sizeof(uint8_t);
    stDy.reserved1 = new uint8_t[DYNAMIC_CNT];
    memset(stDy.reserved1, 0, DYNAMIC_CNT*sizeof(uint8_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved1 + i) = i  ; 
    }

    stDy.reservedDataLength2 = DYNAMIC_CNT*sizeof(uint16_t);
    stDy.reserved2 = new uint16_t[DYNAMIC_CNT];
    memset(stDy.reserved2, 0, DYNAMIC_CNT*sizeof(uint16_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved2 + i) = i  ; 
    }
    
    stDy.reservedDataLength3 = DYNAMIC_CNT*sizeof(uint32_t);
    stDy.reserved3 = new uint32_t[DYNAMIC_CNT];
    memset(stDy.reserved3, 0, DYNAMIC_CNT*sizeof(uint32_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved3 + i) = i  ; 
    }

    stDy.reservedDataLength4 = DYNAMIC_CNT*sizeof(double);
    stDy.reserved4 = new double[DYNAMIC_CNT];
    memset(stDy.reserved4, 0, DYNAMIC_CNT*sizeof(double));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved4 + i) = i  ; 
    }

    stDy.reservedDataLength5 = DYNAMIC_CNT*sizeof(float);
    stDy.reserved5 = new float[DYNAMIC_CNT];
    memset(stDy.reserved5, 0, DYNAMIC_CNT*sizeof(float));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved5 + i) = i  ; 
    }

    return sizeof(oshrinfo_t) + stDy.Permissible_direction_len + stDy.Recommended_driving_directions_for_AJOTP_len + stDy.reservedDataLength1
    + stDy.reservedDataLength2 + stDy.reservedDataLength3 + stDy.reservedDataLength4 + stDy.reservedDataLength5;
}

// HudMappathInfo_EG
uint32_t SetHudMappathInfo_EG2(stHudMappathInfo_EG& stDy)
{
    stDy.Checksum            = 1    ; //Checksum
    stDy.Counter             = 2    ; //Counter
    stDy.is_on_the_path      = 3    ; //is_on_the_path
    stDy.road_angle          = 4    ; //road_angle
    stDy.road_slope          = 5    ; //road_slope
    stDy.all_EHP_v2_info     = "all_EHP_v2_info"    ; //all_EHP_v2_info
    return sizeof(stHudMappathInfo_EG) + stDy.all_EHP_v2_info.length();
}

// HudNavigationmap
uint32_t SetHudNavigationmap2(stHudNavigationmap& stDy)
{
    int count = 0;

    stDy.Navigation_map_len = DYNAMIC_CNT*sizeof(uint8_t);
    uint8_t* pdata = new uint8_t[DYNAMIC_CNT];
    memset(pdata, 0, sizeof(uint8_t)*DYNAMIC_CNT);
    stDy.Navigation_map.assign((const char*)pdata, count);

    return (sizeof(stHudNavigationmap) + stDy.Navigation_map.length());
}


//14.NewLanelineDataNotify
uint32_t SetNewLanelineDataNotify2(stNewLanelineDataNotify& stDy)
{
    int count = 0, nLen = 0;
    stDy.Checksum = 1;
    stDy.Counter = 2;

    stDy.FieldLength_Line_len = DYNAMIC_CNT*sizeof(stNLLDN_FieldLength_Line);
    stDy.FieldLength_Line = new stNLLDN_FieldLength_Line[DYNAMIC_CNT];
    memset(stDy.FieldLength_Line, 0, DYNAMIC_CNT*sizeof(stNLLDN_FieldLength_Line));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_Line + i)->New_LineID            = 1   ;
        (stDy.FieldLength_Line + i)->LineID                = 2   ;
        (stDy.FieldLength_Line + i)->LineType              = 3   ;
        (stDy.FieldLength_Line + i)->New_LineWarningColor  = 4   ;
        (stDy.FieldLength_Line + i)->LineColor             = 5   ;
        (stDy.FieldLength_Line + i)->LineWidth             = 6   ;
        (stDy.FieldLength_Line + i)->Line_confidence       = 7   ;
        (stDy.FieldLength_Line + i)->CurvatureEquation_c0  = 8   ;
        (stDy.FieldLength_Line + i)->CurvatureEquation_c1  = 9   ;
        (stDy.FieldLength_Line + i)->CurvatureEquation_c2  = 10   ;
        (stDy.FieldLength_Line + i)->CurvatureEquation_c3  = 11   ;
        (stDy.FieldLength_Line + i)->Line_Startpoint_x     = 12   ;
        (stDy.FieldLength_Line + i)->Line_Startpoint_y     = 13   ;
        (stDy.FieldLength_Line + i)->Line_Startpoint_z     = 14   ;
        (stDy.FieldLength_Line + i)->Line_Endpoint_x       = 15   ;
        (stDy.FieldLength_Line + i)->Line_Endpoint_y       = 16   ;
        (stDy.FieldLength_Line + i)->Line_Endpoint_z       = 17   ;

        (stDy.FieldLength_Line + i)->New_FieldLength_LinePoints_len = DYNAMIC_CNT*sizeof(stNLLDN_New_FieldLength_LinePoints);
        (stDy.FieldLength_Line + i)->New_FieldLength_LinePoints = new stNLLDN_New_FieldLength_LinePoints[DYNAMIC_CNT];
        memset((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints, 0, DYNAMIC_CNT*sizeof(stNLLDN_New_FieldLength_LinePoints));
        for (int j = 0; j < DYNAMIC_CNT; ++j)
        {
            ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->New_LinePointsID_i = 1  ;
            ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->New_LinePoints_X   = 2  ;
            ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->New_LinePoints_Y   = 3  ;
            ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->New_LinePoints_Z   = 4  ;
            // ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->sys_time_us        = 5  ;
            // ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->LineI_Reserved1    = 6  ;
            // ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->LineI_Reserved2    = 7  ;
            // ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->LineI_Reserved3    = 8  ;
            // ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->LineI_Reserved4    = 9  ;
            // ((stDy.FieldLength_Line + i)->New_FieldLength_LinePoints + i)->LineI_Reserved5    = 10  ;
        }

        (stDy.FieldLength_Line + i)->sys_time_us        = 18   ;
        (stDy.FieldLength_Line + i)->lineI_Reserved1    = 19   ;
        (stDy.FieldLength_Line + i)->lineI_Reserved2    = 20   ;
        (stDy.FieldLength_Line + i)->lineI_Reserved3    = 21   ;
        (stDy.FieldLength_Line + i)->lineI_Reserved4    = 22   ;
        (stDy.FieldLength_Line + i)->lineI_Reserved5    = 23   ;
    }


    stDy.FieldLength_TLA_len = DYNAMIC_CNT*sizeof(stNLLDN_FieldLength_TLA);
    stDy.FieldLength_TLA = new stNLLDN_FieldLength_TLA[DYNAMIC_CNT];
    memset(stDy.FieldLength_TLA, 0, DYNAMIC_CNT*sizeof(stNLLDN_FieldLength_TLA));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_TLA + i)->TLAID_i                = 1  ;
        (stDy.FieldLength_TLA + i)->TLA_Distance_X         = 2  ;
        (stDy.FieldLength_TLA + i)->TLA_Distance_Y         = 3  ;
        (stDy.FieldLength_TLA + i)->TLA_Distance_Z         = 4  ;
        (stDy.FieldLength_TLA + i)->TLAPosition_confidence = 5  ;
        (stDy.FieldLength_TLA + i)->LeftTLA_Color          = 6  ;
        (stDy.FieldLength_TLA + i)->LeftTLA_Type           = 7  ;
        (stDy.FieldLength_TLA + i)->StraightTLA_Color      = 8  ;
        (stDy.FieldLength_TLA + i)->StraightTLA_Type       = 9  ;
        (stDy.FieldLength_TLA + i)->RightTLA_Color         = 10  ;
        (stDy.FieldLength_TLA + i)->RightTLA_Type          = 11  ;
        (stDy.FieldLength_TLA + i)->New_LeftTLA_Second     = 12  ;
        (stDy.FieldLength_TLA + i)->New_StraightTLA_Second = 13  ;
        (stDy.FieldLength_TLA + i)->New_RightTLA_Second    = 14  ;
        (stDy.FieldLength_TLA + i)->TLA_Reserved1          = 15  ;
        (stDy.FieldLength_TLA + i)->TLA_Reserved2          = 16  ;
        (stDy.FieldLength_TLA + i)->TLA_Reserved3          = 17  ;
        (stDy.FieldLength_TLA + i)->TLA_Reserved4          = 18  ;
        (stDy.FieldLength_TLA + i)->TLA_Reserved5          = 19  ;
    }

    stDy.New_FieldLength_TSR_len = DYNAMIC_CNT*sizeof(stNLLDN_New_FieldLength_TSR);
    stDy.New_FieldLength_TSR = new stNLLDN_New_FieldLength_TSR[DYNAMIC_CNT];
    memset(stDy.New_FieldLength_TSR, 0, DYNAMIC_CNT*sizeof(stNLLDN_New_FieldLength_TSR));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.New_FieldLength_TSR + i)->New_TSRID_i                = 1  ;
        (stDy.New_FieldLength_TSR + i)->New_TSR_Distance_X         = 2  ;
        (stDy.New_FieldLength_TSR + i)->New_TSR_Distance_Y         = 3  ;
        (stDy.New_FieldLength_TSR + i)->New_TSR_Distance_Z         = 4  ;
        (stDy.New_FieldLength_TSR + i)->New_TSRPosition_confidence = 5  ;
        (stDy.New_FieldLength_TSR + i)->New_TSR_Type               = 6  ;
        (stDy.New_FieldLength_TSR + i)->New_Speed_Limit            = 7  ;
        (stDy.New_FieldLength_TSR + i)->tolColor                   = 8  ;
        (stDy.New_FieldLength_TSR + i)->tsrHeading                 = 9  ;
        (stDy.New_FieldLength_TSR + i)->TSR_Reserved3              = 10  ;
        (stDy.New_FieldLength_TSR + i)->TSR_Reserved4              = 11  ;
        (stDy.New_FieldLength_TSR + i)->TSR_Reserved5              = 12  ;
    }

    stDy.FieldLength_LanelineReserved_len = DYNAMIC_CNT*sizeof(stNLLDN_FieldLength_LanelineReserved);
    stDy.FieldLength_LanelineReserved = new stNLLDN_FieldLength_LanelineReserved[DYNAMIC_CNT];
    memset(stDy.FieldLength_LanelineReserved, 0, DYNAMIC_CNT*sizeof(stNLLDN_FieldLength_LanelineReserved));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_LanelineReserved+i)->Reserved1 = i  ; 
    }

    return (sizeof(stNewLanelineDataNotify) + stDy.FieldLength_Line_len + DYNAMIC_CNT*DYNAMIC_CNT*sizeof(stNLLDN_New_FieldLength_LinePoints) + stDy.FieldLength_TLA_len 
    + stDy.New_FieldLength_TSR_len + stDy.FieldLength_LanelineReserved_len);
}

//15.NewBroadcastInfoNotify
uint32_t SetNewBroadcastInfoNotify2(stNewBroadcastInfoNotify& stDy)
{
    stDy.Checksum       = 1  ;
    stDy.Counter        = 2  ;
    stDy.NOAMode        = 3  ;
    stDy.notice         = 4  ;
    stDy.Info_Reserved1 = 5  ;
    stDy.Info_Reserved2 = 6  ;
    stDy.Info_Reserved3 = 7  ;
    stDy.Info_Reserved4 = 8  ;
    stDy.Info_Reserved5 = 9  ;

    return sizeof(stNewBroadcastInfoNotify);
}

//16.PlanningLineInfoNotify
uint32_t SetPlanningLineInfoNotify2(stPlanningLineInfoNotify& stDy)
{
    stDy.Checksum             = 1    ;
    stDy.Counter              = 2    ;
    stDy.PlanningLineStatus   = 3    ;
    stDy.planning_timestamp   = 4    ;

    stDy.FieldLength_PlanningLinePoints_len = DYNAMIC_CNT*sizeof(stPlanningLineInfoNotifyFPLP);
    stDy.FieldLength_PlanningLinePoints = new stPlanningLineInfoNotifyFPLP[DYNAMIC_CNT];
    memset(stDy.FieldLength_PlanningLinePoints, 0, DYNAMIC_CNT*sizeof(stPlanningLineInfoNotifyFPLP));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_PlanningLinePoints + i)->PlanningLinePointsID_i = 1  ; 
        (stDy.FieldLength_PlanningLinePoints + i)->points_X               = 2  ; 
        (stDy.FieldLength_PlanningLinePoints + i)->points_Y               = 3  ; 
        (stDy.FieldLength_PlanningLinePoints + i)->points_Z               = 4  ; 
    }

    return sizeof(stPlanningLineInfoNotify) + stDy.FieldLength_PlanningLinePoints_len;
}

//17.NavigationStatus_LinkInfoNotify
uint32_t SetNavigationStatus_LinkInfoNotify2(stNavigationStatus_LinkInfoNotify& stDy)
{
    stDy.Checksum             = 1    ;
    stDy.Counter              = 2    ;
    stDy.timestamp            = 3    ;
    stDy.NavigationStatus     = 4    ;
    stDy.MatchingTableStatus  = 5    ;
    stDy.RemainDistance       = 6    ;
    stDy.ViaPointDistance     = 7    ;
    stDy.HDStartDistance      = 8    ;
    stDy.DNP_Switch           = 9    ;
    stDy.ANP_road             = 10    ;
    stDy.MapVersion           = 11    ;
    stDy.FieldLength_LinK     = 12    ;
    //stDy.LinkID               = 13    ;
    // stDy.reserve1             = 14    ;
    // stDy.reserve2             = 15    ;
    // stDy.reserve3             = 16    ;
    
    stDy.FieldLength_LinK = DYNAMIC_CNT*sizeof(uint64_t);
    stDy.LinkID = new uint64_t[DYNAMIC_CNT];
    memset(stDy.LinkID, 0, DYNAMIC_CNT*sizeof(uint64_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        stDy.LinkID[i] = i  ;
    }

    return sizeof(stNavigationStatus_LinkInfoNotify);
}

//18.NewParkingRealTimeDataNotify
uint32_t SetNewParkingRealTimeDataNotify2(stNewParkingRealTimeDataNotify& stDy)
{
    stDy.Checksum   = 1  ;
    stDy.Counter    = 2  ;
    stDy.timestamp  = 3  ;

    stDy.FieldLength_Object_len = DYNAMIC_CNT*sizeof(stFieldLength_ObjectNPRTDN);
    stDy.FieldLength_Object = new stFieldLength_ObjectNPRTDN[DYNAMIC_CNT];
    memset(stDy.FieldLength_Object, 0, DYNAMIC_CNT*sizeof(stFieldLength_ObjectNPRTDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_Object + i)->ObjectID_i                   = 1    ;
        (stDy.FieldLength_Object + i)->shape_height_i               = 2    ;
        (stDy.FieldLength_Object + i)->shape_length_i               = 3    ;
        (stDy.FieldLength_Object + i)->shape_width_i                = 4    ;
        (stDy.FieldLength_Object + i)->position_x_i                 = 5    ;
        (stDy.FieldLength_Object + i)->position_y_i                 = 6    ;
        (stDy.FieldLength_Object + i)->position_z_i                 = 7    ;
        (stDy.FieldLength_Object + i)->Heading_i                    = 8    ;
        (stDy.FieldLength_Object + i)->TypeInfo                     = 9    ;
        (stDy.FieldLength_Object + i)->CrashRisk                    = 10    ;
        (stDy.FieldLength_Object + i)->NewMoveST                    = 11    ;
        (stDy.FieldLength_Object + i)->NewAbsoluteVelocity          = 12    ;
        (stDy.FieldLength_Object + i)->NewTurnSignalLampSt          = 13    ;
        (stDy.FieldLength_Object + i)->NewHigh_lowBeamLampsSt       = 14    ;
        (stDy.FieldLength_Object + i)->NewBrakeLightSt              = 15    ;
        (stDy.FieldLength_Object + i)->NewReversingLightSt          = 16    ;
        (stDy.FieldLength_Object + i)->ParkingObjectInfo_Reserved1  = 17    ;
        (stDy.FieldLength_Object + i)->blockingBarStatus            = 18    ;
        (stDy.FieldLength_Object + i)->blockingBarTypeInfo          = 19    ;
        (stDy.FieldLength_Object + i)->blockingBarDirInfo           = 20    ;
        (stDy.FieldLength_Object + i)->ParkingObjectInfo_Reserved5  = 21    ; 
    }

    stDy.FieldLength_ParkingSlot_len = DYNAMIC_CNT*sizeof(stFieldLength_ParkingSlotNPRTDN);
    stDy.FieldLength_ParkingSlot = new stFieldLength_ParkingSlotNPRTDN[DYNAMIC_CNT];
    memset(stDy.FieldLength_ParkingSlot, 0, DYNAMIC_CNT*sizeof(stFieldLength_ParkingSlotNPRTDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_ParkingSlot + i)->ParkngSpcID_i             = 1   ;
        (stDy.FieldLength_ParkingSlot + i)->ParkngSpcSts              = 2   ;
        (stDy.FieldLength_ParkingSlot + i)->ParkngSpcCode_i           = 3   ;
        (stDy.FieldLength_ParkingSlot + i)->x1_i                      = 4   ;
        (stDy.FieldLength_ParkingSlot + i)->y1_i                      = 5   ;
        (stDy.FieldLength_ParkingSlot + i)->x2_i                      = 6   ;
        (stDy.FieldLength_ParkingSlot + i)->y2_i                      = 7   ;
        (stDy.FieldLength_ParkingSlot + i)->x3_i                      = 8   ;
        (stDy.FieldLength_ParkingSlot + i)->y3_i                      = 9   ;
        (stDy.FieldLength_ParkingSlot + i)->x4_i                      = 10   ;
        (stDy.FieldLength_ParkingSlot + i)->y4_i                      = 11   ;
        (stDy.FieldLength_ParkingSlot + i)->ParkngSpcType             = 12   ;
        (stDy.FieldLength_ParkingSlot + i)->ParkngSpcNum              = 13   ;
        (stDy.FieldLength_ParkingSlot + i)->E4CornerMark              = 14   ;
        (stDy.FieldLength_ParkingSlot + i)->parkngSlotNumber          = 15   ;
        (stDy.FieldLength_ParkingSlot + i)->ParkingSlotInfo_Reserved2 = 16   ;
        (stDy.FieldLength_ParkingSlot + i)->ParkingSlotInfo_Reserved3 = 17   ;
        (stDy.FieldLength_ParkingSlot + i)->ParkingSlotInfo_Reserved4 = 18   ;
        (stDy.FieldLength_ParkingSlot + i)->ParkingSlotInfo_Reserved5 = 19   ;
    }

    stDy.Position_x                = 20   ;
    stDy.Position_y                = 21   ;
    stDy.Position_z                = 22   ;
    stDy.Roll                      = 23   ;
    stDy.Yaw                       = 24   ;
    stDy.Pitch                     = 25   ;

    stDy.FieldLength_RealTimeTrackPoint_len = DYNAMIC_CNT*sizeof(stFieldLength_RealTimeTrackPointNPRTDN);
    stDy.FieldLength_RealTimeTrackPoint = new stFieldLength_RealTimeTrackPointNPRTDN[DYNAMIC_CNT];
    memset(stDy.FieldLength_RealTimeTrackPoint, 0, DYNAMIC_CNT*sizeof(stFieldLength_RealTimeTrackPointNPRTDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_RealTimeTrackPoint + i)->RealTimeTrackPointID_i  = 1 ;
        (stDy.FieldLength_RealTimeTrackPoint + i)->x_i                     = 2 ;
        (stDy.FieldLength_RealTimeTrackPoint + i)->y_i                     = 3 ;
        (stDy.FieldLength_RealTimeTrackPoint + i)->heading_i               = 4 ;
        (stDy.FieldLength_RealTimeTrackPoint + i)->stopLine                = 5 ;
        (stDy.FieldLength_RealTimeTrackPoint + i)->GuideLineInfo_Reserved2 = 6 ;
        (stDy.FieldLength_RealTimeTrackPoint + i)->GuideLineInfo_Reserved3 = 7 ;
        (stDy.FieldLength_RealTimeTrackPoint + i)->GuideLineInfo_Reserved4 = 8 ;
        (stDy.FieldLength_RealTimeTrackPoint + i)->GuideLineInfo_Reserved5 = 9 ;
    }

    stDy.FieldLength_HistoryTrackPoint_len = DYNAMIC_CNT*sizeof(stFieldLength_HistoryTrackPointNPRTDN);
    stDy.FieldLength_HistoryTrackPoint = new stFieldLength_HistoryTrackPointNPRTDN[DYNAMIC_CNT];
    memset(stDy.FieldLength_HistoryTrackPoint, 0, DYNAMIC_CNT*sizeof(stFieldLength_HistoryTrackPointNPRTDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_HistoryTrackPoint + i)->HistoryTrackPointID_i          = 1  ;
        (stDy.FieldLength_HistoryTrackPoint + i)->x_i                            = 2  ;
        (stDy.FieldLength_HistoryTrackPoint + i)->y_i                            = 3  ;
        (stDy.FieldLength_HistoryTrackPoint + i)->z_i                            = 4  ;
        (stDy.FieldLength_HistoryTrackPoint + i)->Width_Learning                 = 5  ;
        (stDy.FieldLength_HistoryTrackPoint + i)->cruiseHistoryTrackPointID_i    = 6  ;
        (stDy.FieldLength_HistoryTrackPoint + i)->cruiseHistoryX                 = 7  ;
        (stDy.FieldLength_HistoryTrackPoint + i)->cruiseHistoryY                 = 8  ;
        (stDy.FieldLength_HistoryTrackPoint + i)->cruiseHistoryZ                 = 9  ;
        (stDy.FieldLength_HistoryTrackPoint + i)->parkinglotLevel                = 10  ;
    }

    stDy.Parking_distance_left          = 11  ;
    stDy.Cruising_distance_left         = 12  ;
    stDy.Learning_distance              = 13  ;
    stDy.PathVeriRate                   = 14  ;
    stDy.Avoid_pedestrians_number       = 15  ;
    stDy.Avoid_vehicles_number          = 16  ;
    stDy.PathLearnFailDisp              = 17  ;
    stDy.Speed_Bump_Number              = 18  ;
    stDy.ViewAngleReq                   = 19  ;
    stDy.NRPX1NoPassing                 = 20  ;
    stDy.NRPY1NoPassing                 = 21  ;
    stDy.NRPX2NoPassing                 = 22  ;
    stDy.NRPY2NoPassing                 = 23  ;
    stDy.ParkingRealTimeData_Reserved5  = 24  ;

    return sizeof(stNewParkingRealTimeDataNotify) + stDy.FieldLength_Object_len + stDy.FieldLength_ParkingSlot_len
    + stDy.FieldLength_RealTimeTrackPoint_len  + stDy.FieldLength_HistoryTrackPoint_len;
}

//19.NavigationHDLink2Info
uint32_t SetNavigationHDLink2Info2(stNavigationHDLink2Info& stDy)
{
    stDy.Checksum             = 1  ;
    stDy.Counter              = 2  ;
    stDy.NavigationPathValid1 = 3  ;
    stDy.RoutePntCnt1         = 4  ;
    stDy.RouteLinkCnt1        = 5  ;
    stDy.RoutePathID1         = 6  ;

    stDy.LinkItemInfo_len = DYNAMIC_CNT*sizeof(stLinkItemInfoNHDLI);
    stDy.LinkItemInfo = new stLinkItemInfoNHDLI[DYNAMIC_CNT];
    memset(stDy.LinkItemInfo, 0, DYNAMIC_CNT*sizeof(stLinkItemInfoNHDLI));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.LinkItemInfo + i)->LinkItemFormway1   = 1  ;
        (stDy.LinkItemInfo + i)->LinkItemLinktype1  = 2  ;
        (stDy.LinkItemInfo + i)->LinkItemRoadclass1 = 3  ;
        (stDy.LinkItemInfo + i)->LinkItemBegIdx1    = 4  ;
        (stDy.LinkItemInfo + i)->LinkItemPntCnt1    = 5  ;
        (stDy.LinkItemInfo + i)->LinkItemRoadname_1 = "6"  ;
        (stDy.LinkItemInfo + i)->LinkItemLen1       = 7  ;
    }

    stDy.PntItemInfo_len = DYNAMIC_CNT*sizeof(stPntItemInfoNHDLI);
    stDy.PntItemInfo = new stPntItemInfoNHDLI[DYNAMIC_CNT];
    memset(stDy.PntItemInfo, 0, DYNAMIC_CNT*sizeof(stPntItemInfoNHDLI));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.PntItemInfo + i)->PntItem_X1           = 1    ;
        (stDy.PntItemInfo + i)->PntItem_Y1           = 2    ;
    }

    stDy.reserve1_9           = 3    ;
    stDy.reserve2_10          = 4    ;
    stDy.reserve3_11          = 5    ;
    stDy.NavigationPathValid2 = 6    ;
    stDy.RoutePntCnt2         = 7    ;
    stDy.RouteLinkCnt2        = 8    ;
    stDy.RoutePathID2         = 9    ;

    stDy.LinkItemInfo2_len = DYNAMIC_CNT*sizeof(stLinkItemInfo2NHDLI);
    stDy.LinkItemInfo2 = new stLinkItemInfo2NHDLI[DYNAMIC_CNT];
    memset(stDy.LinkItemInfo2, 0, DYNAMIC_CNT*sizeof(stLinkItemInfo2NHDLI));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.LinkItemInfo2 + i)->LinkItemFormway2   = 1  ;
        (stDy.LinkItemInfo2 + i)->LinkItemLinktype2  = 2  ;
        (stDy.LinkItemInfo2 + i)->LinkItemRoadclass2 = 3  ;
        (stDy.LinkItemInfo2 + i)->LinkItemBegIdx2    = 4  ;
        (stDy.LinkItemInfo2 + i)->LinkItemPntCnt2    = 5  ;
        (stDy.LinkItemInfo2 + i)->LinkItemRoadname_2 = "6";
        (stDy.LinkItemInfo2 + i)->LinkItemLen2       = 7  ;
    }

    stDy.PntItemInfo2_len = DYNAMIC_CNT*sizeof(stPntItemInfo2NHDLI);
    stDy.PntItemInfo2 = new stPntItemInfo2NHDLI[DYNAMIC_CNT];
    memset(stDy.PntItemInfo2, 0, DYNAMIC_CNT*sizeof(stPntItemInfo2NHDLI));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.PntItemInfo2 + i)->PntItem_X2             = 1    ;
        (stDy.PntItemInfo2 + i)->PntItem_Y2             = 2    ;
    }

    stDy.reserve1_18            = 3    ;
    stDy.reserve2_25            = 4    ;
    stDy.reserve3_20            = 5    ;
    stDy.NavigationPathValid3   = 6    ;
    stDy.RoutePntCnt3           = 7    ;
    stDy.RouteLinkCnt3          = 8    ;
    stDy.RoutePathID3           = 9    ;

    stDy.LinkItemInfo3_len = DYNAMIC_CNT*sizeof(stLinkItemInfo3NHDLI);
    stDy.LinkItemInfo3 = new stLinkItemInfo3NHDLI[DYNAMIC_CNT];
    memset(stDy.LinkItemInfo3, 0, DYNAMIC_CNT*sizeof(stLinkItemInfo3NHDLI));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.LinkItemInfo3 + i)->LinkItemFormway3   = 1  ;
        (stDy.LinkItemInfo3 + i)->LinkItemLinktype3  = 2  ;
        (stDy.LinkItemInfo3 + i)->LinkItemRoadclass3 = 3  ;
        (stDy.LinkItemInfo3 + i)->LinkItemBegIdx3    = 4  ;
        (stDy.LinkItemInfo3 + i)->LinkItemPntCnt3    = 5  ;
        (stDy.LinkItemInfo3 + i)->LinkItemRoadname3  = "LinkItemRoadname3"  ;
        (stDy.LinkItemInfo3 + i)->LinkItemLen3       = 7  ;
    }

    stDy.PntItemInfo3_len = DYNAMIC_CNT*sizeof(stPntItemInfo3NHDLI);
    stDy.PntItemInfo3 = new stPntItemInfo3NHDLI[DYNAMIC_CNT];
    memset(stDy.PntItemInfo3, 0, DYNAMIC_CNT*sizeof(stPntItemInfo3NHDLI));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.PntItemInfo3 + i)->PntItem_X3 = 1  ;
        (stDy.PntItemInfo3 + i)->PntItem_Y3 = 2  ;
    }

    stDy.reserve1_27   = 3  ;
    stDy.reserve2_28   = 4  ;
    stDy.reserve3_29   = 5  ;

    return sizeof(stNavigationHDLink2Info)  + stDy.LinkItemInfo_len + stDy.PntItemInfo_len + stDy.LinkItemInfo2_len
    + stDy.PntItemInfo2_len + stDy.LinkItemInfo3_len + stDy.PntItemInfo3_len;
}


//20.sdTraffiIncident
uint32_t SetsdTraffiIncident2(stsdTraffiIncident& stDy)
{
    stDy.TraffiIncident_len = DYNAMIC_CNT*sizeof(stTraffiIncidentTI);
    stDy.TraffiIncident = new stTraffiIncidentTI[DYNAMIC_CNT];
    memset(stDy.TraffiIncident, 0, DYNAMIC_CNT*sizeof(stTraffiIncidentTI));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.TraffiIncident + i)->naviCongestionInfo    = 1   ;
        (stDy.TraffiIncident + i)->occupiedLane          = 2   ;
        (stDy.TraffiIncident + i)->cnstrctnCrdLatitude   = 3   ;
        (stDy.TraffiIncident + i)->cnstrctnCrdLongitude  = 4   ;
        (stDy.TraffiIncident + i)->naviCongestionDistLen = 5   ;
        (stDy.TraffiIncident + i)->occupiedLaneDtl       = 6   ;
        (stDy.TraffiIncident + i)->reserve3              = 7   ;
    }

    return sizeof(stsdTraffiIncident) + stDy.TraffiIncident_len;
}


//21.newPlanningLineInfo
uint32_t SetnewPlanningLineInfo2(stnewPlanningLineInfo& stDy)
{
    stDy.checksum            = 1  ;
    stDy.counter             = 2  ;
    stDy.planningLineStatus  = 3  ;
    stDy.planningTimestamp   = 4  ;

    stDy.fieldLengthPlanningLinePoints_len = DYNAMIC_CNT*sizeof(stfieldLengthPlanningLinePointsNPLI);
    stDy.fieldLengthPlanningLinePoints = new stfieldLengthPlanningLinePointsNPLI[DYNAMIC_CNT];
    memset(stDy.fieldLengthPlanningLinePoints, 0, DYNAMIC_CNT*sizeof(stfieldLengthPlanningLinePointsNPLI));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.fieldLengthPlanningLinePoints + i)->PlanningLinePointsID         = 1    ;
        (stDy.fieldLengthPlanningLinePoints + i)->pointsX                      = 2    ;
        (stDy.fieldLengthPlanningLinePoints + i)->pointsY                      = 3    ;
        (stDy.fieldLengthPlanningLinePoints + i)->pointsZ                      = 4    ;
    }

    stDy.accelerationDeceleration     = 5    ;
    stDy.navigationPlanningLineStatus = 6    ;
    stDy.navigationPlanningTimestamp  = 7    ;

    stDy.navFieldLengthNavigationPlanningLinePoints_len = DYNAMIC_CNT*sizeof(stnavFieldLengthNavigationPlanningLinePointsNPLI);
    stDy.navFieldLengthNavigationPlanningLinePoints = new stnavFieldLengthNavigationPlanningLinePointsNPLI[DYNAMIC_CNT];
    memset(stDy.navFieldLengthNavigationPlanningLinePoints, 0, DYNAMIC_CNT*sizeof(stnavFieldLengthNavigationPlanningLinePointsNPLI));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.navFieldLengthNavigationPlanningLinePoints + i)->navPlanningLinePointsID = 1 ;
        (stDy.navFieldLengthNavigationPlanningLinePoints + i)->navPointsX              = 2 ;
        (stDy.navFieldLengthNavigationPlanningLinePoints + i)->navPointsY              = 3 ;
        (stDy.navFieldLengthNavigationPlanningLinePoints + i)->navPointsZ              = 4 ;
    }

    return sizeof(stnewPlanningLineInfo)  + stDy.fieldLengthPlanningLinePoints_len + stDy.navFieldLengthNavigationPlanningLinePoints_len + stDy.reservedDataLength1 + stDy.reservedDataLength2 + stDy.reservedDataLength3 + stDy.reservedDataLength4 + stDy.reservedDataLength5;
}


//22.drivingAreaIdentification
uint32_t SetdrivingAreaIdentification2(stdrivingAreaIdentification& stDy)
{
    stDy.checksum                         = 1  ;
    stDy.counter                          = 2  ;
    stDy.drivingAreaIdentificationStatus  = 3  ;

    stDy.drivingAreaIdentificationPoints_len = DYNAMIC_CNT*sizeof(uint8_t);
    stDy.drivingAreaIdentificationPoints = new uint8_t[DYNAMIC_CNT];
    memset(stDy.drivingAreaIdentificationPoints, 0, DYNAMIC_CNT*sizeof(uint8_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        stDy.drivingAreaIdentificationPoints[i]       = i   ;
    }

    stDy.sizetBevh                             = 3   ;
    stDy.sizetBevw                             = 4   ;
    stDy.xBoundMin                             = 5   ;
    stDy.xBoundMax                             = 6   ;
    stDy.yBoundMin                             = 7   ;
    stDy.yBoundMax                             = 8   ;
    stDy.meterPerPixelX                        = 9   ;
    stDy.meterPerPixelY                        = 10   ;
    stDy.maskThreshold                         = 11   ;

    stDy.reservedDataLength1 = DYNAMIC_CNT*sizeof(uint8_t);
    stDy.reserved1 = new uint8_t[DYNAMIC_CNT];
    memset(stDy.reserved1, 0, DYNAMIC_CNT*sizeof(uint8_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved1 + i) = i  ; 
    }

    stDy.reservedDataLength2 = DYNAMIC_CNT*sizeof(uint16_t);
    stDy.reserved2 = new uint16_t[DYNAMIC_CNT];
    memset(stDy.reserved2, 0, DYNAMIC_CNT*sizeof(uint16_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved2 + i) = i  ; 
    }

    stDy.reservedDataLength3 = DYNAMIC_CNT*sizeof(uint32_t);
    stDy.reserved3 = new uint32_t[DYNAMIC_CNT];
    memset(stDy.reserved3, 0, DYNAMIC_CNT*sizeof(uint32_t));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved3 + i) = i  ; 
    }

    stDy.reservedDataLength4 = DYNAMIC_CNT*sizeof(double);
    stDy.reserved4 = new double[DYNAMIC_CNT];
    memset(stDy.reserved4, 0, DYNAMIC_CNT*sizeof(double));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved4 + i) = i  ; 
    }

    stDy.reservedDataLength5 = DYNAMIC_CNT*sizeof(float32);
    stDy.reserved5 = new float32[DYNAMIC_CNT];
    memset(stDy.reserved5, 0, DYNAMIC_CNT*sizeof(float32));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        *(stDy.reserved5 + i) = i  ; 
    }

    return sizeof(stdrivingAreaIdentification) + stDy.drivingAreaIdentificationPoints_len +  stDy.reservedDataLength1 + stDy.reservedDataLength2 + stDy.reservedDataLength3 + stDy.reservedDataLength4 + stDy.reservedDataLength5;
}

//23.HPAMapDataNotify
uint32_t SetHPAMapDataNotify2(stHPAMapDataNotify& stDy)
{
    stDy.Checksum     = 1  ;
    stDy.Counter      = 2  ;
    stDy.timestamp    = 3  ;

    stDy.FieldLength_GlobalTrackPoint_len = DYNAMIC_CNT*sizeof(stFieldLength_GlobalTrackPointHPAMDN);
    stDy.FieldLength_GlobalTrackPoint = new stFieldLength_GlobalTrackPointHPAMDN[DYNAMIC_CNT];
    memset(stDy.FieldLength_GlobalTrackPoint, 0, DYNAMIC_CNT*sizeof(stFieldLength_GlobalTrackPointHPAMDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_GlobalTrackPoint + i)->GlobalTrackPointID_i  = 1  ;
        (stDy.FieldLength_GlobalTrackPoint + i)->x_i                   = 2  ;
        (stDy.FieldLength_GlobalTrackPoint + i)->y_i                   = 3  ;
        (stDy.FieldLength_GlobalTrackPoint + i)->z_i                   = 4  ;
        (stDy.FieldLength_GlobalTrackPoint + i)->Width                 = 5  ;
    }

    stDy.BuildMapStartPoint_len = DYNAMIC_CNT*sizeof(stBuildMapStartPointHPAMDN);
    stDy.BuildMapStartPoint = new stBuildMapStartPointHPAMDN[DYNAMIC_CNT];
    memset(stDy.BuildMapStartPoint, 0, DYNAMIC_CNT*sizeof(stBuildMapStartPointHPAMDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.BuildMapStartPoint + i)->x_start         = 6  ;
        (stDy.BuildMapStartPoint + i)->y_start         = 7  ;
        (stDy.BuildMapStartPoint + i)->z_start         = 8  ;
        (stDy.BuildMapStartPoint + i)->x_stop          = 9  ;
        (stDy.BuildMapStartPoint + i)->y_stop          = 10 ;
        (stDy.BuildMapStartPoint + i)->z_stop          = 11 ;
    }

    stDy.FieldLength_Rampway_len = DYNAMIC_CNT*sizeof(stFieldLength_RampwayHPAMDN);
    stDy.FieldLength_Rampway = new stFieldLength_RampwayHPAMDN[DYNAMIC_CNT];
    memset(stDy.FieldLength_Rampway, 0, DYNAMIC_CNT*sizeof(stFieldLength_RampwayHPAMDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_Rampway + i)->RampwayID_i  = 1 ;
        (stDy.FieldLength_Rampway + i)->x1_i         = 2 ;
        (stDy.FieldLength_Rampway + i)->y1_i         = 3 ;
        (stDy.FieldLength_Rampway + i)->z1_i         = 4 ;
        (stDy.FieldLength_Rampway + i)->x2_i         = 5 ;
        (stDy.FieldLength_Rampway + i)->y2_i         = 6 ;
        (stDy.FieldLength_Rampway + i)->z2_i         = 7 ;
    }

    stDy.FieldLength_SpeedBumps_len = DYNAMIC_CNT*sizeof(stFieldLength_SpeedBumpsHPAMDN);
    stDy.FieldLength_SpeedBumps = new stFieldLength_SpeedBumpsHPAMDN[DYNAMIC_CNT];
    memset(stDy.FieldLength_SpeedBumps, 0, DYNAMIC_CNT*sizeof(stFieldLength_SpeedBumpsHPAMDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_SpeedBumps + i)->SpeedBumpsID_i  = 1 ;
        (stDy.FieldLength_SpeedBumps + i)->x_i_Left        = 2 ;
        (stDy.FieldLength_SpeedBumps + i)->y_i_Left        = 3 ;
        (stDy.FieldLength_SpeedBumps + i)->z_i_Left        = 4 ;
        (stDy.FieldLength_SpeedBumps + i)->x_i_Right       = 5 ;
        (stDy.FieldLength_SpeedBumps + i)->y_i_Right       = 6 ;
        (stDy.FieldLength_SpeedBumps + i)->z_i_Right       = 7 ;
        (stDy.FieldLength_SpeedBumps + i)->SpeedBumpsWidth = 8 ;
    }

    stDy.FieldLength_UprightColumn_len = DYNAMIC_CNT*sizeof(stFieldLength_UprightColumnHPAMDN);
    stDy.FieldLength_UprightColumn = new stFieldLength_UprightColumnHPAMDN[DYNAMIC_CNT];
    memset(stDy.FieldLength_UprightColumn, 0, DYNAMIC_CNT*sizeof(stFieldLength_UprightColumnHPAMDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_UprightColumn + i)->UprightColumnID_i = 1   ;
        (stDy.FieldLength_UprightColumn + i)->x1_i              = 2   ;
        (stDy.FieldLength_UprightColumn + i)->y1_i              = 3   ;
        (stDy.FieldLength_UprightColumn + i)->z1_i              = 4   ;
        (stDy.FieldLength_UprightColumn + i)->x2_i              = 5   ;
        (stDy.FieldLength_UprightColumn + i)->y2_i              = 6   ;
        (stDy.FieldLength_UprightColumn + i)->z2_i              = 7   ;
        (stDy.FieldLength_UprightColumn + i)->x3_i              = 8   ;
        (stDy.FieldLength_UprightColumn + i)->y3_i              = 9   ;
        (stDy.FieldLength_UprightColumn + i)->z3_i              = 10   ;
        (stDy.FieldLength_UprightColumn + i)->x4_i              = 11   ;
        (stDy.FieldLength_UprightColumn + i)->y4_i              = 12   ;
        (stDy.FieldLength_UprightColumn + i)->z4_i              = 13   ;
        (stDy.FieldLength_UprightColumn + i)->height_i          = 14   ;
    }

    stDy.FieldLength_ParkngSpcI_len = DYNAMIC_CNT*sizeof(stFieldLength_ParkngSpcIHPAMDN);
    stDy.FieldLength_ParkngSpcI = new stFieldLength_ParkngSpcIHPAMDN[DYNAMIC_CNT];
    memset(stDy.FieldLength_ParkngSpcI, 0, DYNAMIC_CNT*sizeof(stFieldLength_ParkngSpcIHPAMDN));
    for (int i = 0; i < DYNAMIC_CNT; ++i)
    {
        (stDy.FieldLength_ParkngSpcI + i)->ParkngSpcID_i  = 1  ;
        (stDy.FieldLength_ParkngSpcI + i)->ParkngSpcSts   = 2  ;
        (stDy.FieldLength_ParkngSpcI + i)->x1_i           = 3  ;
        (stDy.FieldLength_ParkngSpcI + i)->y1_i           = 4  ;
        (stDy.FieldLength_ParkngSpcI + i)->z1_i           = 5  ;
        (stDy.FieldLength_ParkngSpcI + i)->x2_i           = 6  ;
        (stDy.FieldLength_ParkngSpcI + i)->y2_i           = 7  ;
        (stDy.FieldLength_ParkngSpcI + i)->z2_i           = 8  ;
        (stDy.FieldLength_ParkngSpcI + i)->x3_i           = 9  ;
        (stDy.FieldLength_ParkngSpcI + i)->y3_i           = 10  ;
        (stDy.FieldLength_ParkngSpcI + i)->z3_i           = 11  ;
        (stDy.FieldLength_ParkngSpcI + i)->x4_i           = 12  ;
        (stDy.FieldLength_ParkngSpcI + i)->y4_i           = 13  ;
        (stDy.FieldLength_ParkngSpcI + i)->z4_i           = 14  ;
        (stDy.FieldLength_ParkngSpcI + i)->TargetSlotID   = 15  ;
    }

    return sizeof(stHPAMapDataNotify) + stDy.FieldLength_GlobalTrackPoint_len + stDy.FieldLength_Rampway_len
    + stDy.FieldLength_SpeedBumps_len + stDy.FieldLength_UprightColumn_len + stDy.FieldLength_ParkngSpcI_len;
}





//-----------------------------------------------display data---------------------------------------
//VehiclePositionInfoNotify
void DisplayVehiclePositionInfoNotify(stVehiclePositionInfoNotify& stDy)
{
    printf("VehiclePositionInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        Longitude:%lf\r\n\
        Latitude:%lf\r\n\
        altitude:%lf\r\n\
        Heading:%lf\r\n\
        hd_lane_left_angle:%lf\r\n\
        Hd_lane_right_angle:%lf\r\n\
        VehicleSpeed:%lf\r\n\
        acceleration:%lf\r\n\
        x_speed:%lf\r\n\
        y_speed:%lf\r\n\
        z_speed:%lf\r\n\
        timestamp:%lf\r\n\
        hd_link_id:%u\r\n\
        hd_lane_id:%u\r\n\
        hd_lane_type:%u\r\n\
        on_lane_offset:%lf\r\n\
        hd_lane_seq:%u\r\n\
        hd_lane_num:%u\r\n\
        hd_lane_left_lateral_offset:%lf\r\n\
        hd_lane_right_lateral_offset:%lf\r\n\
        roll:%lf\r\n\
        pitch:%lf\r\n\
        HdStatus:%u\r\n\
        hdmap_version:%u\r\n\
        fusion_status:%u\r\n\
        pos_confidence:%lf\r\n\
        position_type:%u\r\n\
        break_light:%u\r\n\
        indicator_light:%u\r\n\
        Lights:%u\r\n\
        Weather:%u\r\n\
        target_cruise_speed:%f\r\n\
        FieldLength_target_lane:%u\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.Longitude
        ,stDy.Latitude
        ,stDy.altitude
        ,stDy.Heading
        ,stDy.hd_lane_left_angle
        ,stDy.Hd_lane_right_angle
        ,stDy.VehicleSpeed
        ,stDy.acceleration
        ,stDy.x_speed
        ,stDy.y_speed
        ,stDy.z_speed
        ,stDy.timestamp
        ,stDy.hd_link_id
        ,stDy.hd_lane_id
        ,stDy.hd_lane_type
        ,stDy.on_lane_offset
        ,stDy.hd_lane_seq
        ,stDy.hd_lane_num
        ,stDy.hd_lane_left_lateral_offset
        ,stDy.hd_lane_right_lateral_offset
        ,stDy.roll
        ,stDy.pitch
        ,stDy.HdStatus
        ,stDy.hdmap_version
        ,stDy.fusion_status
        ,stDy.pos_confidence
        ,stDy.position_type
        ,stDy.break_light
        ,stDy.indicator_light
        ,stDy.Lights
        ,stDy.Weather
        ,stDy.target_cruise_speed
        ,stDy.FieldLength_target_lane);

    int count = stDy.FieldLength_target_lane / 4;//sizeof(uint32_t);
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
        printf("            target_lane_id[%d]:%u\r\n", i, *(stDy.target_lane_id+i));
    printf("        }\r\n");

    printf("        FieldLength_target_lane_id_segment:%u\r\n", stDy.FieldLength_target_lane_id_segment);
    count = stDy.FieldLength_target_lane_id_segment / 4;//sizeof(uint32_t);
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
        printf("            target_lane_id_segment[%d]:%u\r\n", i, *(stDy.target_lane_id_segment+i));
    printf("        }\r\n");

    printf("        localization_output_offset:%u\r\n}\r\n\r\n", stDy.localization_output_offset);
}

//RTKInfoNotify         
void DisplayRTKInfoNotify(stRTKInfoNotify& stDy)       
{
    printf("RTKInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        rtk_status:%u\r\n\
        utc_time_us:%lf\r\n\
        sys_time_us:%lf\r\n\
        longitude:%lf\r\n\
        latitude:%lf\r\n\
        altitude:%lf\r\n\
        longitude_acc:%lf\r\n\
        latitude_acc:%lf\r\n\
        altitude_acc:%lf\r\n\
        heading_move:%lf\r\n\
        heading_double_ant:%lf\r\n\
        heading_move_acc:%lf\r\n\
        speed_2d:%lf\r\n\
        speed_acc:%lf\r\n\
        speed_n:%lf\r\n\
        speed_e:%lf\r\n\
        speed_u:%lf\r\n\
        g_dop:%lf\r\n\
        h_dop:%lf\r\n\
        v_dop:%lf\r\n\
        satellite_num:%u\r\n\
        satellite_used:%u\r\n\
        snr_max:%lf\r\n\
        snr_mix:%lf\r\n\
        snr_avr:%lf\r\n}\r\n\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.rtk_status
        ,stDy.utc_time_us
        ,stDy.sys_time_us
        ,stDy.longitude
        ,stDy.latitude
        ,stDy.altitude
        ,stDy.longitude_acc
        ,stDy.latitude_acc
        ,stDy.altitude_acc
        ,stDy.heading_move
        ,stDy.heading_double_ant
        ,stDy.heading_move_acc
        ,stDy.speed_2d
        ,stDy.speed_acc
        ,stDy.speed_n
        ,stDy.speed_e
        ,stDy.speed_u
        ,stDy.g_dop
        ,stDy.h_dop
        ,stDy.v_dop
        ,stDy.satellite_num
        ,stDy.satellite_used
        ,stDy.snr_max
        ,stDy.snr_mix
        ,stDy.snr_avr
        );
}

//IMUInfoNotify                
void DisplayIMUInfoNotify(stIMUInfoNotify& stDy)
{
    printf("IMUInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        angular_velocity_x:%lf\r\n\
        angular_velocity_y:%lf\r\n\
        angular_velocity_z:%lf\r\n\
        acc_speed_x:%lf\r\n\
        acc_speed_y:%lf\r\n\
        acc_speed_z:%lf\r\n\
        IMU_status:%u\r\n\
        IMU current temperature:%lf\r\n\
        sys_time_us:%lf\r\n\
        is_calibrated:%d\r\n}\r\n\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.angular_velocity_x
        ,stDy.angular_velocity_y
        ,stDy.angular_velocity_z
        ,stDy.acc_speed_x
        ,stDy.acc_speed_y
        ,stDy.acc_speed_z
        ,stDy.IMU_status
        ,stDy.IMU_current_temperature
        ,stDy.sys_time_us
        ,stDy.is_calibrated
        );
}

//ObstacleInfoNotify         
void DisplayObstacleInfoNotify(stObstacleInfoNotify& stDy)  
{
    printf("ObstacleInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        target_flag:%d\r\n\
        FieldLength_Object_len:%u\r\n"
        
        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.target_flag
        ,stDy.FieldLength_Object_len);
    
    int count = stDy.FieldLength_Object_len / 97;//sizeof(stObstacleInfoNotifyFLO);
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                ObstacleType:%u\r\n",               (stDy.FieldLength_Object+i)->ObstacleType);
        printf("                confidence:%lf\r\n",                (stDy.FieldLength_Object+i)->confidence);
        printf("                Obstacle_Id_i:%u\r\n",              (stDy.FieldLength_Object+i)->Obstacle_Id_i);
        printf("                ObstacleDistance_X_i:%lf\r\n",      (stDy.FieldLength_Object+i)->ObstacleDistance_X_i);
        printf("                ObstacleDistance_Y_i:%lf\r\n",      (stDy.FieldLength_Object+i)->ObstacleDistance_Y_i);
        printf("                ObstacleDistance_Z_i:%lf\r\n",      (stDy.FieldLength_Object+i)->ObstacleDistance_Z_i);
        printf("                Bounding_box_length_i:%f\r\n",      (stDy.FieldLength_Object+i)->Bounding_box_length_i);
        printf("                Bounding_box_width_i:%f\r\n",       (stDy.FieldLength_Object+i)->Bounding_box_width_i);
        printf("                Bounding_box_height_i:%f\r\n",      (stDy.FieldLength_Object+i)->Bounding_box_height_i);
        printf("                break_light:%u\r\n",                (stDy.FieldLength_Object+i)->break_light);
        printf("                indicator_light:%u\r\n",            (stDy.FieldLength_Object+i)->indicator_light);
        printf("                obj_speed:%lf\r\n",                 (stDy.FieldLength_Object+i)->obj_speed);
        printf("                ObstacleState:%u\r\n",              (stDy.FieldLength_Object+i)->ObstacleState);
        printf("                obstacle_timestamp:%lf\r\n",        (stDy.FieldLength_Object+i)->obstacle_timestamp);
        printf("                obstacle_camera_timestamp:%lf\r\n", (stDy.FieldLength_Object+i)->obstacle_camera_timestamp);
        printf("                moving:%d\r\n",                     (stDy.FieldLength_Object+i)->moving);
        printf("                obj_heading:%lf\r\n",               (stDy.FieldLength_Object+i)->obj_heading);
        printf("                Obj_direction:%lf\r\n",             (stDy.FieldLength_Object+i)->Obj_direction);
        printf("                ObstacleWarningBrakeState:%u\r\n", (stDy.FieldLength_Object+i)->ObstacleWarningBrakeState);
        printf("            }\r\n");
    }
    printf("        }\r\n}\r\n\r\n");
}

//LanelineDataNotify      
void DisplayLanelineDataNotify(stLanelineDataNotify& stDy)     
{
    printf("LanelineDataNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n"
        ,stDy.Checksum
        ,stDy.Counter
    );

    int count = stDy.FieldLength_Line_len / 66;//sizeof(stLanelineDataNotifyFLL);
    printf("        FieldLength_Line_len:%u\r\n", stDy.FieldLength_Line_len);
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                LineID:%d\r\n",                     (stDy.FieldLength_Line+i)->LineID                 );
        printf("                LineType:%u\r\n",                   (stDy.FieldLength_Line+i)->LineType               );
        printf("                LineColor:%u\r\n",                  (stDy.FieldLength_Line+i)->LineColor              );
        printf("                LineWidth:%lf\r\n",                 (stDy.FieldLength_Line+i)->LineWidth              );
        printf("                Line_confidence:%lf\r\n",           (stDy.FieldLength_Line+i)->Line_confidence        );
        printf("                CurvatureEquation_c0:%lf\r\n",      (stDy.FieldLength_Line+i)->CurvatureEquation_c0   );
        printf("                CurvatureEquation_c1:%lf\r\n",      (stDy.FieldLength_Line+i)->CurvatureEquation_c1   );
        printf("                CurvatureEquation_c2:%lf\r\n",      (stDy.FieldLength_Line+i)->CurvatureEquation_c2   );
        printf("                CurvatureEquation_c3:%lf\r\n",      (stDy.FieldLength_Line+i)->CurvatureEquation_c3   );
        printf("                Line_Startpoint_x:%lf\r\n",         (stDy.FieldLength_Line+i)->Line_Startpoint_x      );
        printf("                Line_Startpoint_y:%lf\r\n",         (stDy.FieldLength_Line+i)->Line_Startpoint_y      );
        printf("                Line_Startpoint_z:%lf\r\n",         (stDy.FieldLength_Line+i)->Line_Startpoint_z      );
        printf("                Line_Endpoint_x:%lf\r\n",           (stDy.FieldLength_Line+i)->Line_Endpoint_x        );
        printf("                Line_Endpoint_y:%lf\r\n",           (stDy.FieldLength_Line+i)->Line_Endpoint_y        );
        printf("                Line_Endpoint_z:%lf\r\n",           (stDy.FieldLength_Line+i)->Line_Endpoint_z        );
        printf("                sys_time_us:%lf\r\n",               (stDy.FieldLength_Line+i)->sys_time_us            );
        printf("            }\r\n");
    }
    printf("        }\r\n\r\n");

    count = stDy.FieldLength_RoadMarking_len / 57;//sizeof(stLanelineDataNotifyFLRM);
    printf("        FieldLength_RoadMarking_len:%u\r\n", stDy.FieldLength_RoadMarking_len);
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                RoadMarkingID_i:%u\r\n",                (stDy.FieldLength_RoadMarking+i)->RoadMarkingID_i                );
        printf("                RoadMarkingType_i:%u\r\n",              (stDy.FieldLength_RoadMarking+i)->RoadMarkingType_i              );
        printf("                RoadMarkingType_confidence_i:%lf\r\n",  (stDy.FieldLength_RoadMarking+i)->RoadMarkingType_confidence_i   );
        printf("                RoadMarking_length_i:%f\r\n",           (stDy.FieldLength_RoadMarking+i)->RoadMarking_length_i           );
        printf("                RoadMarking_width_i:%f\r\n",            (stDy.FieldLength_RoadMarking+i)->RoadMarking_width_i            );
        printf("                RoadMarking_height_i:%f\r\n",           (stDy.FieldLength_RoadMarking+i)->RoadMarking_height_i           );
        printf("                RoadMarking_Distance_X_i:%lf\r\n",      (stDy.FieldLength_RoadMarking+i)->RoadMarking_Distance_X_i       );
        printf("                RoadMarking_Distance_Y_i:%lf\r\n",      (stDy.FieldLength_RoadMarking+i)->RoadMarking_Distance_Y_i       );
        printf("                RoadMarking_Distance_Z_i:%lf\r\n",      (stDy.FieldLength_RoadMarking+i)->RoadMarking_Distance_Z_i       );
        printf("                RoadMarkingPosition_confidence:%lf\r\n",(stDy.FieldLength_RoadMarking+i)->RoadMarkingPosition_confidence );
        printf("            }\r\n");
    }
    printf("        }\r\n\r\n");

    count = stDy.FieldLength_TLA_len / 42;//sizeof(stLanelineDataNotifyFLTLA);
    printf("        FieldLength_TLA_len:%u\r\n", stDy.FieldLength_TLA_len);
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                TLAID_i:%u\r\n",                    (stDy.FieldLength_TLA+i)->TLAID_i                );
        printf("                TLA_Distance_X:%lf\r\n",            (stDy.FieldLength_TLA+i)->TLA_Distance_X         );
        printf("                TLA_Distance_Y:%lf\r\n",            (stDy.FieldLength_TLA+i)->TLA_Distance_Y         );
        printf("                TLA_Distance_Z:%lf\r\n",            (stDy.FieldLength_TLA+i)->TLA_Distance_Z         );
        printf("                TLAPosition_confidence:%lf\r\n",    (stDy.FieldLength_TLA+i)->TLAPosition_confidence );
        printf("                LeftTLA_Color:%u\r\n",              (stDy.FieldLength_TLA+i)->LeftTLA_Color          );
        printf("                LeftTLA_Type:%u\r\n",               (stDy.FieldLength_TLA+i)->LeftTLA_Type           );
        printf("                StraightTLA_Color:%u\r\n",          (stDy.FieldLength_TLA+i)->StraightTLA_Color      );
        printf("                StraightTLA_Type:%u\r\n",           (stDy.FieldLength_TLA+i)->StraightTLA_Type       );
        printf("                RightTLA_Color:%u\r\n",             (stDy.FieldLength_TLA+i)->RightTLA_Color         );
        printf("                RightTLA_Type:%u\r\n",              (stDy.FieldLength_TLA+i)->RightTLA_Type          );
        printf("            }\r\n");
    }
    printf("        }\r\n}\r\n\r\n");
}

//ChangeLaneDataNotify         
void DisplayChangeLaneDataNotify(stChangeLaneDataNotify& stDy)
{
    printf("ChangeLaneDataNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        ChangeLaneState:%u\r\n\
        ChangeLaneDirection:%u\r\n\
        is_change_safety:%d\r\n\
        ChangeLane_timestamp:%u\r\n\
        change_ratio:%lf\r\n\
        change_termi:%u\r\n\
        landing_center_X:%lf\r\n\
        landing_center_Y:%lf\r\n\
        landing_center_Z:%lf\r\n\
        landing_box_length:%lf\r\n\
        landing_box__width:%lf\r\n\
        landing_box_height:%lf\r\n}\r\n\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.ChangeLaneState
        ,stDy.ChangeLaneDirection
        ,stDy.is_change_safety
        ,stDy.ChangeLane_timestamp
        ,stDy.change_ratio
        ,stDy.change_termi
        ,stDy.landing_center_X
        ,stDy.landing_center_Y
        ,stDy.landing_center_Z
        ,stDy.landing_box_length
        ,stDy.landing_box__width
,stDy.landing_box_height
    );
}

//PilotStatusNotify            
void DisplayPilotStatusNotify(stPilotStatusNotify& stDy)
{
    printf("PilotStatusNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        ACCStatus:%u\r\n\
        ICCStatus:%u\r\n\
        DNPStatus:%u\r\n\
        TakeoverStatus:%d\r\n\
        driving_time:%u\r\n}\r\n\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.ACCStatus
        ,stDy.ICCStatus
        ,stDy.DNPStatus
        ,stDy.TakeoverStatus
        ,stDy.driving_time
    );
}

//PilotAlarmAndNoticeInfoNotify
void DisplayPilotAlarmAndNoticeInfoNotify(stPilotAlarmAndNoticeInfoNotify& stDy)
{
    printf("PilotAlarmAndNoticeInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        PilotAlarmReason:%u\r\n\
        alarm_distance:%u\r\n\
        alarm_stage:%u\r\n\
        alarm_timestamp:%lf\r\n\
        PilotNotice:%u\r\n\
        notice_distance:%u\r\n\
        notice_timestamp:%lf\r\n}\r\n\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.PilotAlarmReason
        ,stDy.alarm_distance
        ,stDy.alarm_stage
        ,stDy.alarm_timestamp
        ,stDy.PilotNotice
        ,stDy.notice_distance
        ,stDy.notice_timestamp
    );
}

//BroadcastInfoNotify          
void DisplayBroadcastInfoNotify(stBroadcastInfoNotify& stDy)
{
    printf("BroadcastInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        driver_attention:%d\r\n\
        large_vehicles:%d\r\n\
        dangerous_vehicle:%d\r\n\
        pedestrians:%d\r\n}\r\n\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.driver_attention
        ,stDy.large_vehicles
        ,stDy.dangerous_vehicle
        ,stDy.pedestrians
    );
}

// //PlanningLineInfoNotify     
// void DisplayPlanningLineInfoNotify(stPlanningLineInfoNotify& stDy)  
// {
//     printf("PlanningLineInfoNotify:\r\n{\r\n");
//     printf("\
//         Checksum:%u\r\n\
//         Counter:%u\r\n\
//         PlanningLineStatus:%d\r\n\
//         planning_timestamp:%lf\r\n\
//         FieldLength_PlanningLinePoints_len:%u\r\n"

//         ,stDy.Checksum
//         ,stDy.Counter
//         ,stDy.PlanningLineStatus
//         ,stDy.planning_timestamp
//         ,stDy.FieldLength_PlanningLinePoints_len
//     );

//     int count = stDy.FieldLength_PlanningLinePoints_len / 28;//sizeof(stPlanningLineInfoNotifyFPLP);
//     printf("        {\r\n");
//     for (int i = 0; i < count; ++i)
//     {
//         printf("            {\r\n");
//         printf("                PlanningLinePointsID_i:%u\r\n", (stDy.FieldLength_PlanningLinePoints+i)->PlanningLinePointsID_i);
//         printf("                points_X:%lf\r\n", (stDy.FieldLength_PlanningLinePoints+i)->points_X);
//         printf("                points_Y:%lf\r\n", (stDy.FieldLength_PlanningLinePoints+i)->points_Y);
//         printf("                points_Z:%lf\r\n", (stDy.FieldLength_PlanningLinePoints+i)->points_Z);
//         printf("            }\r\n");
//     }
//     printf("        }\r\n}\r\n\r\n");
// }

//HudRoadInfoNotify    
int gHRINcount = 0; 
void DisplayHudRoadInfoNotify(stHudRoadInfoNotify& stDy)      
{
    printf("HudRoadInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        car_2_dest:%u\r\n\
        time_of_car_2_dest:%u\r\n\
        Num_of_lanes:%u\r\n\
        Current_road_level:%u\r\n\
        Permissible_direction_len:%u\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.car_2_dest
        ,stDy.time_of_car_2_dest
        ,stDy.Num_of_lanes
        ,stDy.Current_road_level
        ,stDy.Permissible_direction_len);

printf("\
        Recommended_driving_directions_for_AJOTP_len:%u\r\n",  stDy.Permissible_direction_len);

    int count = stDy.Permissible_direction_len / 1;//sizeof(uint8_t);
    if (count > 0) printf("        {\r\n");
    //for (int i = 0; i < count; ++i)
    //  printf("            Permissible_direction[%d]:%d\r\n", i, *(stDy.Permissible_direction+i));
    if (count > 0) printf("        }\r\n");

    std::mutex mt;
    std::unique_lock<std::mutex> itslock(mt);
    if (count > 0)
    {
        std::string sfile;
        std::stringstream sstream;
        sstream<<gpath<<"out/"<<"Permissible_direction"<<++gHRINcount<<".png";
        std::getline(sstream, sfile);
        std::ofstream fout(sfile);
        if (fout.is_open())
        {
            fout.write((char*)stDy.Permissible_direction, stDy.Permissible_direction_len);
        }
        fout.close();
        if (stDy.Permissible_direction != NULL)
        {
            delete[] stDy.Permissible_direction;
            stDy.Permissible_direction = nullptr;
        }
    }

    printf("        Recommended_driving_directions_for_AJOTP_len:%u\r\n",  stDy.Recommended_driving_directions_for_AJOTP_len);
    count = stDy.Recommended_driving_directions_for_AJOTP_len / 1;//sizeof(uint8_t);
    if (count > 0) printf("        {\r\n");
    //for (int i = 0; i < count; ++i)
    //    printf("            Recommended_driving_directions_for_AJOTP[%d]:%d\r\n", i, *(stDy.Recommended_driving_directions_for_AJOTP+i));
    if (count > 0) printf("        }\r\n");

    if (count > 0)
    {
        std::string sfile;
        std::stringstream sstream;
        sstream<<gpath<<"out/"<<"Recommended_driving_directions_for_AJOTP"<<++gHRINcount<<".png";
        std::getline(sstream, sfile);
        std::ofstream fout(sfile);
        if (fout.is_open())
        {
            fout.write((char*)stDy.Recommended_driving_directions_for_AJOTP, stDy.Recommended_driving_directions_for_AJOTP_len);
        }
        fout.close();
        if (stDy.Recommended_driving_directions_for_AJOTP != NULL)
        {
            delete[] stDy.Recommended_driving_directions_for_AJOTP;
            stDy.Recommended_driving_directions_for_AJOTP = nullptr;
        }
    }

printf("\
        distance_2_intersection:%u\r\n\
        next_road_name:%s\r\n\
        Current_max_speed_limit:%u\r\n\
        Current_speed:%u\r\n\
        Distance_2_speed_limit_zone:%u\r\n\
        length_of_speed_limit:%u\r\n\
        speed_limit:%u\r\n\
        navigating_status:%u\r\n\
        camera_ahead_status:%u\r\n\
        The_distance_2_camera:%u\r\n\
        vehicle_coordinates_Longitude:%lf\r\n\
        vehicle_coordinates_Latitude:%lf\r\n\
        vehicle_speed:%u\r\n\
        vehicle_altitude:%u\r\n\
        Danger_signs:%u\r\n\
        POI_information:%s\r\n\
        reach_the_destination:%s\r\n\
        ETA_info_time:%s\r\n\
        ETA_info_remain_time:%s\r\n\
        RecommendedDrivingDirectionsId:%u\r\n\
        lanesPermissibleDirectionId:%s\r\n\
        guideLine:%s\r\n\
        guidePoint:%s\r\n\
        vehicleHeading:%lf\r\n\
        Navigating_ratio:%lf\r\n}\r\n\r\n"

        ,stDy.distance_2_intersection
        ,stDy.next_road_name.c_str()
        ,stDy.Current_max_speed_limit
        ,stDy.Current_speed
        ,stDy.Distance_2_speed_limit_zone
        ,stDy.length_of_speed_limit
        ,stDy.speed_limit
        ,stDy.navigating_status
        ,stDy.camera_ahead_status
        ,stDy.The_distance_2_camera
        ,stDy.vehicle_coordinates_Longitude
        ,stDy.vehicle_coordinates_Latitude
        ,stDy.vehicle_speed
        ,stDy.vehicle_altitude
        ,stDy.Danger_signs
        ,stDy.POI_information.c_str()
        ,stDy.reach_the_destination.c_str()
        ,stDy.ETA_info_time.c_str()
        ,stDy.ETA_info_remain_time.c_str()
        ,stDy.RecommendedDrivingDirectionsId
        ,stDy.lanesPermissibleDirectionId.c_str()
        ,stDy.guideLine.c_str()
        ,stDy.guidePoint.c_str()
        ,stDy.vehicleHeading
        ,stDy.Navigating_ratio
    );
}

// oshrinfo_t;
int gHRINcount2 = 0; 
void DisplayOverseasHudRoadInfoNotify(oshrinfo_t& stDy)      
{
    printf("OverseasHudRoadInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        car_2_dest:%u\r\n\
        time_of_car_2_dest:%u\r\n\
        Num_of_lanes:%u\r\n\
        Current_road_level:%u\r\n\
        Permissible_direction_len:%u\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.car_2_dest
        ,stDy.time_of_car_2_dest
        ,stDy.Num_of_lanes
        ,stDy.Current_road_level
        ,stDy.Permissible_direction_len);

printf("\
        Recommended_driving_directions_for_AJOTP_len:%u\r\n",  stDy.Permissible_direction_len);

    int count = stDy.Permissible_direction_len / sizeof(uint8_t);
    if (count > 0) printf("        {\r\n");
    //for (int i = 0; i < count; ++i)
    //   printf("            Permissible_direction[%d]:%d\r\n", i, *(stDy.Permissible_direction+i));
    if (count > 0) printf("        }\r\n");

    std::mutex mt;
    std::unique_lock<std::mutex> itslock(mt);
    if (count > 0)
    {
        std::string sfile;
        std::stringstream sstream;
        sstream<<gpath<<"out/"<<"Permissible_direction"<<++gHRINcount2<<".png";
        std::getline(sstream, sfile);
        std::ofstream fout(sfile);
        if (fout.is_open())
        {
            fout.write((char*)stDy.Permissible_direction, stDy.Permissible_direction_len);
        }
        fout.close();
        if (stDy.Permissible_direction != NULL)
        {
            delete[] stDy.Permissible_direction;
            stDy.Permissible_direction = nullptr;
        }
    }

    printf("        Recommended_driving_directions_for_AJOTP_len:%u\r\n",  stDy.Recommended_driving_directions_for_AJOTP_len);
    count = stDy.Recommended_driving_directions_for_AJOTP_len / 1;//sizeof(uint8_t);
    if (count > 0) printf("        {\r\n");
    //for (int i = 0; i < count; ++i)
    //    printf("            Recommended_driving_directions_for_AJOTP[%d]:%d\r\n", i, *(stDy.Recommended_driving_directions_for_AJOTP+i));
    if (count > 0) printf("        }\r\n");

    if (count > 0)
    {
        std::string sfile;
        std::stringstream sstream;
        sstream<<gpath<<"out/"<<"Recommended_driving_directions_for_AJOTP"<<++gHRINcount2<<".png";
        std::getline(sstream, sfile);
        std::ofstream fout(sfile);
        if (fout.is_open())
        {
            fout.write((char*)stDy.Recommended_driving_directions_for_AJOTP, stDy.Recommended_driving_directions_for_AJOTP_len);
        }
        fout.close();
        if (stDy.Recommended_driving_directions_for_AJOTP != NULL)
        {
            delete[] stDy.Recommended_driving_directions_for_AJOTP;
            stDy.Recommended_driving_directions_for_AJOTP = nullptr;
        }
    }

printf("\
        distance_2_intersection:%u\r\n\
        next_road_name:%s\r\n\
        Current_max_speed_limit:%u\r\n\
        Current_speed:%u\r\n\
        Distance_2_speed_limit_zone:%u\r\n\
        length_of_speed_limit:%u\r\n\
        speed_limit:%u\r\n\
        navigating_status:%u\r\n\
        camera_ahead_status:%u\r\n\
        The_distance_2_camera:%u\r\n\
        vehicle_coordinates_Longitude:%lf\r\n\
        vehicle_coordinates_Latitude:%lf\r\n\
        vehicle_speed:%u\r\n\
        vehicle_altitude:%u\r\n\
        Danger_signs:%u\r\n\
        POI_information:%s\r\n\
        reach_the_destination:%s\r\n\
        eta_info_time:%s\r\n\
        eta_info_remain_time:%s\r\n\
        recommendeddrivingdirectionsid:%u\r\n\
        lanesPermissibleDirectionId:%s\r\n\
        guideLine:%s\r\n\
        guidePoint:%s\r\n\
        vehicleHeading:%lf\r\n\
        Navigating_ratio:%lf\r\n\
        mapProviders:%u\r\n\
        carToDestDistance:%s\r\n\
        distanceToIntersection:%s\r\n\
        timeToDest:%s\r\n\
        recommendedDrivingDirectionsIdOverseas:%u\r\n\
        reservedDataLength1:%u\r\n\
        reservedDataLength2:%u\r\n\
        reservedDataLength3:%u\r\n\
        reservedDataLength4:%u\r\n\
        reservedDataLength5:%u\r\n}\r\n\r\n"
        ,stDy.distance_2_intersection
        ,stDy.next_road_name.c_str()
        ,stDy.Current_max_speed_limit
        ,stDy.Current_speed
        ,stDy.Distance_2_speed_limit_zone
        ,stDy.length_of_speed_limit
        ,stDy.speed_limit
        ,stDy.navigating_status
        ,stDy.camera_ahead_status
        ,stDy.The_distance_2_camera
        ,stDy.vehicle_coordinates_Longitude
        ,stDy.vehicle_coordinates_Latitude
        ,stDy.vehicle_speed
        ,stDy.vehicle_altitude
        ,stDy.Danger_signs
        ,stDy.POI_information.c_str()
        ,stDy.reach_the_destination.c_str()
        ,stDy.ETA_info_time.c_str()
        ,stDy.ETA_info_remain_time.c_str()
        ,stDy.RecommendedDrivingDirectionsId
        ,stDy.lanesPermissibleDirectionId.c_str()
        ,stDy.guideLine.c_str()
        ,stDy.guidePoint.c_str()
        ,stDy.vehicleHeading
        ,stDy.Navigating_ratio

        ,stDy.mapProviders
        ,stDy.carToDestDistance.c_str()
        ,stDy.distanceToIntersection.c_str()
        ,stDy.timeToDest.c_str()
        ,stDy.recommendedDrivingDirectionsIdOverseas
        ,stDy.reservedDataLength1
        ,stDy.reservedDataLength2
        ,stDy.reservedDataLength3
        ,stDy.reservedDataLength4
        ,stDy.reservedDataLength5
    );
}

//HudMappathInfo_EG      
void DisplayHudMappathInfo_EG(stHudMappathInfo_EG& stDy)   
{
    printf("HudMappathInfo_EG:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        is_on_the_path:%u\r\n\
        road_angle:%u\r\n\
        road_slope:%f\r\n\
        all_EHP_v2_info:%s\r\n}\r\n\r\n"

        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.is_on_the_path
        ,stDy.road_angle
        ,stDy.road_slope
        ,stDy.all_EHP_v2_info.c_str()
    );
}


//HudNavigationmap
int gcount = 0; 
void DisplayHudNavigationmap(stHudNavigationmap& stDy)
{
    printf("HudNavigationmap:\r\n{\r\n");
    printf("        Navigation_map_len:%u\r\n", stDy.Navigation_map_len);
    int count = stDy.Navigation_map_len / sizeof(uint8_t);
    printf("        {\r\n");
    //for (int i = 0; i < count; ++i)
    //  printf("            Navigation_map[%d]:%d\r\n", i, *(stDy.Navigation_map+i));
    printf("        }\r\n}\r\n\r\n");


    int decodeMapLength = 0;
    std::string decodeMapData = Decode((const char*)(stDy.Navigation_map.c_str()), stDy.Navigation_map_len, decodeMapLength);
    if (stDy.Navigation_map_len > 0)
    {
        std::mutex mt;
        std::unique_lock<std::mutex> itslock(mt);
        std::string sfile;
        std::stringstream sstream;
        sstream<<gpath<<"out/"<<"Navigation_map"<<++gcount<<"_"<<stDy.Navigation_map_len<<"_"<<decodeMapLength<<".png";
        std::getline(sstream, sfile);
        std::ofstream fout(sfile);
        if (fout.is_open())
        {
            fout.write((const char*)decodeMapData.c_str(), decodeMapLength);
        }
        fout.close();
    }
}



//14.NewLanelineDataNotify
void DisplayNewLanelineDataNotify(stNewLanelineDataNotify& stDy)  
{
    printf("NewLanelineDataNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n"
        ,stDy.Checksum
        ,stDy.Counter
    );

    int count = stDy.FieldLength_Line_len / sizeof(stNLLDN_FieldLength_Line);
    printf("        FieldLength_Line:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                New_LineID:%d\r\n",             (stDy.FieldLength_Line+i)->New_LineID);
        printf("                LineID:%d\r\n",                 (stDy.FieldLength_Line+i)->LineID);
        printf("                LineType:%u\r\n",               (stDy.FieldLength_Line+i)->LineType);
        printf("                New_LineWarningColor:%u\r\n",   (stDy.FieldLength_Line+i)->New_LineWarningColor);
        printf("                LineColor:%u\r\n",              (stDy.FieldLength_Line+i)->LineColor);
        printf("                LineWidth:%lf\r\n",             (stDy.FieldLength_Line+i)->LineWidth);
        printf("                Line_confidence:%lf\r\n",       (stDy.FieldLength_Line+i)->Line_confidence);
        printf("                CurvatureEquation_c0:%lf\r\n",  (stDy.FieldLength_Line+i)->CurvatureEquation_c0);
        printf("                CurvatureEquation_c1:%lf\r\n",  (stDy.FieldLength_Line+i)->CurvatureEquation_c1);
        printf("                CurvatureEquation_c2:%lf\r\n",  (stDy.FieldLength_Line+i)->CurvatureEquation_c2);
        printf("                CurvatureEquation_c3:%lf\r\n",  (stDy.FieldLength_Line+i)->CurvatureEquation_c3);
        printf("                Line_Startpoint_x:%lf\r\n",     (stDy.FieldLength_Line+i)->Line_Startpoint_x);
        printf("                Line_Startpoint_y:%lf\r\n",     (stDy.FieldLength_Line+i)->Line_Startpoint_y);
        printf("                Line_Startpoint_z:%lf\r\n",     (stDy.FieldLength_Line+i)->Line_Startpoint_z);
        printf("                Line_Endpoint_x:%lf\r\n",       (stDy.FieldLength_Line+i)->Line_Endpoint_x);
        printf("                Line_Endpoint_y:%lf\r\n",       (stDy.FieldLength_Line+i)->Line_Endpoint_y);
        printf("                Line_Endpoint_z:%lf\r\n",       (stDy.FieldLength_Line+i)->Line_Endpoint_z);

        int count1 = (stDy.FieldLength_Line+i)->New_FieldLength_LinePoints_len / sizeof(stNLLDN_New_FieldLength_LinePoints);
        printf("                New_FieldLength_LinePoints:\r\n");
        printf("                {\r\n");
        for (int j = 0; j < count1; ++j)
        {
            printf("                {\r\n");
            printf("                    New_LinePointsID_i:%u\r\n",     ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->New_LinePointsID_i);
            printf("                    New_LinePoints_X:%lf\r\n",      ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->New_LinePoints_X);
            printf("                    New_LinePoints_Y:%lf\r\n",      ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->New_LinePoints_Y);
            printf("                    New_LinePoints_Z:%lf\r\n",      ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->New_LinePoints_Z);
            // printf("                    sys_time_us:%lf\r\n",           ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->sys_time_us);
            // printf("                    LineI_Reserved1:%lf\r\n",       ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->LineI_Reserved1);
            // printf("                    LineI_Reserved2:%lf\r\n",       ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->LineI_Reserved2);
            // printf("                    LineI_Reserved3:%lf\r\n",       ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->LineI_Reserved3);
            // printf("                    LineI_Reserved4:%lf\r\n",       ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->LineI_Reserved4);
            // printf("                    LineI_Reserved5:%lf\r\n",       ((stDy.FieldLength_Line+i)->New_FieldLength_LinePoints+j)->LineI_Reserved5);
            printf("                }\r\n");
        }

        printf("                sys_time_us:%lf\r\n",           (stDy.FieldLength_Line+i)->sys_time_us);
        printf("                lineI_Reserved1:%lf\r\n",       (stDy.FieldLength_Line+i)->lineI_Reserved1);
        printf("                lineI_Reserved2:%lf\r\n",       (stDy.FieldLength_Line+i)->lineI_Reserved2);
        printf("                lineI_Reserved3:%lf\r\n",       (stDy.FieldLength_Line+i)->lineI_Reserved3);
        printf("                lineI_Reserved4:%lf\r\n",       (stDy.FieldLength_Line+i)->lineI_Reserved4);
        printf("                lineI_Reserved5:%lf\r\n",       (stDy.FieldLength_Line+i)->lineI_Reserved5);
        printf("                }\r\n");
        printf("            }\r\n");
    }
    printf("        }\r\n");



    count = stDy.FieldLength_TLA_len / sizeof(stNLLDN_FieldLength_TLA);
    printf("        FieldLength_TLA:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                TLAID_i:%u\r\n",       (stDy.FieldLength_TLA+i)->TLAID_i);
        printf("                TLA_Distance_X:%lf\r\n",       (stDy.FieldLength_TLA+i)->TLA_Distance_X);
        printf("                TLA_Distance_Y:%lf\r\n",       (stDy.FieldLength_TLA+i)->TLA_Distance_Y);
        printf("                TLA_Distance_Z:%lf\r\n",       (stDy.FieldLength_TLA+i)->TLA_Distance_Z);
        printf("                TLAPosition_confidence:%lf\r\n",       (stDy.FieldLength_TLA+i)->TLAPosition_confidence);
        printf("                LeftTLA_Color:%u\r\n",       (stDy.FieldLength_TLA+i)->LeftTLA_Color);
        printf("                LeftTLA_Type:%u\r\n",       (stDy.FieldLength_TLA+i)->LeftTLA_Type);
        printf("                StraightTLA_Color:%u\r\n",       (stDy.FieldLength_TLA+i)->StraightTLA_Color);
        printf("                StraightTLA_Type:%u\r\n",       (stDy.FieldLength_TLA+i)->StraightTLA_Type);
        printf("                RightTLA_Color:%u\r\n",       (stDy.FieldLength_TLA+i)->RightTLA_Color);
        printf("                RightTLA_Type:%u\r\n",       (stDy.FieldLength_TLA+i)->RightTLA_Type);
        printf("                New_LeftTLA_Second:%u\r\n",       (stDy.FieldLength_TLA+i)->New_LeftTLA_Second);
        printf("                New_StraightTLA_Second:%u\r\n",       (stDy.FieldLength_TLA+i)->New_StraightTLA_Second);
        printf("                New_RightTLA_Second:%u\r\n",       (stDy.FieldLength_TLA+i)->New_RightTLA_Second);
        printf("                TLA_Reserved1:%lf\r\n",       (stDy.FieldLength_TLA+i)->TLA_Reserved1);
        printf("                TLA_Reserved2:%lf\r\n",       (stDy.FieldLength_TLA+i)->TLA_Reserved2);
        printf("                TLA_Reserved3:%lf\r\n",       (stDy.FieldLength_TLA+i)->TLA_Reserved3);
        printf("                TLA_Reserved4:%lf\r\n",       (stDy.FieldLength_TLA+i)->TLA_Reserved4);
        printf("                TLA_Reserved5:%lf\r\n",       (stDy.FieldLength_TLA+i)->TLA_Reserved5);
        printf("            }\r\n");
    }
    printf("        }\r\n");

    count = stDy.New_FieldLength_TSR_len / sizeof(stNLLDN_New_FieldLength_TSR);
    printf("        New_FieldLength_TSR:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                New_TSRID_i:%u\r\n",       (stDy.New_FieldLength_TSR+i)->New_TSRID_i);
        printf("                New_TSR_Distance_X:%lf\r\n",       (stDy.New_FieldLength_TSR+i)->New_TSR_Distance_X);
        printf("                New_TSR_Distance_Y:%lf\r\n",       (stDy.New_FieldLength_TSR+i)->New_TSR_Distance_Y);
        printf("                New_TSR_Distance_Z:%lf\r\n",       (stDy.New_FieldLength_TSR+i)->New_TSR_Distance_Z);
        printf("                New_TSRPosition_confidence:%lf\r\n",       (stDy.New_FieldLength_TSR+i)->New_TSRPosition_confidence);
        printf("                New_TSR_Type:%u\r\n",       (stDy.New_FieldLength_TSR+i)->New_TSR_Type);
        printf("                New_Speed_Limit:%u\r\n",       (stDy.New_FieldLength_TSR+i)->New_Speed_Limit);
        printf("                tolColor:%lf\r\n",       (stDy.New_FieldLength_TSR+i)->tolColor);
        printf("                tsrHeading:%lf\r\n",       (stDy.New_FieldLength_TSR+i)->tsrHeading);
        printf("                TSR_Reserved3:%lf\r\n",       (stDy.New_FieldLength_TSR+i)->TSR_Reserved3);
        printf("                TSR_Reserved4:%lf\r\n",       (stDy.New_FieldLength_TSR+i)->TSR_Reserved4);
        printf("                TSR_Reserved5:%lf\r\n",       (stDy.New_FieldLength_TSR+i)->TSR_Reserved5);
        printf("            }\r\n");
    }
    printf("        }\r\n");

    count = stDy.FieldLength_LanelineReserved_len / sizeof(stNLLDN_FieldLength_LanelineReserved);
    printf("        FieldLength_LanelineReserved:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                Reserved1:%u\r\n",       (stDy.FieldLength_LanelineReserved+i)->Reserved1);
        printf("            }\r\n");
    }

    printf("        }\r\n}\r\n\r\n");
}

//15.NewBroadcastInfoNotify
void DisplayNewBroadcastInfoNotify(stNewBroadcastInfoNotify& stDy)  
{
    printf("NewBroadcastInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        NOAMode:%u\r\n\
        notice:%u\r\n\
        Info_Reserved1:%lf\r\n\
        Info_Reserved2:%lf\r\n\
        Info_Reserved3:%lf\r\n\
        Info_Reserved4:%lf\r\n\
        Info_Reserved5:%lf\r\n"
        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.NOAMode
        ,stDy.notice
        ,stDy.Info_Reserved1
        ,stDy.Info_Reserved2
        ,stDy.Info_Reserved3
        ,stDy.Info_Reserved4
        ,stDy.Info_Reserved5
    );
    
    printf("\r\n}\r\n\r\n");
}

//16.PlanningLineInfoNotify
void DisplayPlanningLineInfoNotify(stPlanningLineInfoNotify& stDy)  
{
    printf("PlanningLineInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        PlanningLineStatus:%u\r\n\
        planning_timestamp:%lf\r\n"
        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.PlanningLineStatus
        ,stDy.planning_timestamp
    );
    
    int count = stDy.FieldLength_PlanningLinePoints_len / sizeof(stPlanningLineInfoNotifyFPLP);
    printf("        FieldLength_PlanningLinePoints:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                PlanningLinePointsID_i;:%u\r\n",       (stDy.FieldLength_PlanningLinePoints+i)->PlanningLinePointsID_i);
        printf("                points_X;:%lf\r\n",       (stDy.FieldLength_PlanningLinePoints+i)->points_X);
        printf("                points_Y;:%lf\r\n",       (stDy.FieldLength_PlanningLinePoints+i)->points_Y);
        printf("                points_Z;:%lf\r\n",       (stDy.FieldLength_PlanningLinePoints+i)->points_Z);
        printf("            }\r\n");
    }

    printf("        }\r\n}\r\n\r\n");
}

//17.NavigationStatus_LinkInfoNotify
void DisplayNavigationStatus_LinkInfoNotify(stNavigationStatus_LinkInfoNotify& stDy)  
{
    printf("NavigationStatus_LinkInfoNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        timestamp:%lf\r\n\
        NavigationStatus:%u\r\n\
        MatchingTableStatus:%u\r\n\
        RemainDistance:%u\r\n\
        ViaPointDistance:%u\r\n\
        HDStartDistance:%u\r\n\
        DNP_Switch:%u\r\n\
        ANP_road:%u\r\n\
        MapVersion:%u\r\n\
        FieldLength_LinK:%u\r\n"
        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.timestamp
        ,stDy.NavigationStatus
        ,stDy.MatchingTableStatus
        ,stDy.RemainDistance
        ,stDy.ViaPointDistance
        ,stDy.HDStartDistance
        ,stDy.DNP_Switch
        ,stDy.ANP_road
        ,stDy.MapVersion
        ,stDy.FieldLength_LinK
    );
    
    printf("\r\n}\r\n\r\n");
}

//18.NewParkingRealTimeDataNotify
void DisplayNewParkingRealTimeDataNotify(stNewParkingRealTimeDataNotify& stDy)  
{
    printf("NewParkingRealTimeDataNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        timestamp:%lf\r\n"
        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.timestamp
    );
    
    int count = stDy.FieldLength_Object_len / sizeof(stFieldLength_ObjectNPRTDN);
    printf("        FieldLength_Object:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                ObjectID_i:%lu\r\n",       (stDy.FieldLength_Object+i)->ObjectID_i);
        printf("                shape_height_i:%lf\r\n",       (stDy.FieldLength_Object+i)->shape_height_i);
        printf("                shape_length_i:%lf\r\n",       (stDy.FieldLength_Object+i)->shape_length_i);
        printf("                shape_width_i:%lf\r\n",       (stDy.FieldLength_Object+i)->shape_width_i);
        printf("                position_x_i:%lf\r\n",       (stDy.FieldLength_Object+i)->position_x_i);
        printf("                position_y_i:%lf\r\n",       (stDy.FieldLength_Object+i)->position_y_i);
        printf("                position_z_i:%lf\r\n",       (stDy.FieldLength_Object+i)->position_z_i);
        printf("                Heading_i:%lf\r\n",       (stDy.FieldLength_Object+i)->Heading_i);
        printf("                TypeInfo:%u\r\n",       (stDy.FieldLength_Object+i)->TypeInfo);
        printf("                CrashRisk:%u\r\n",       (stDy.FieldLength_Object+i)->CrashRisk);
        printf("                NewMoveST:%u\r\n",       (stDy.FieldLength_Object+i)->NewMoveST);
        printf("                NewAbsoluteVelocity:%u\r\n",       (stDy.FieldLength_Object+i)->NewAbsoluteVelocity);
        printf("                NewTurnSignalLampSt:%u\r\n",       (stDy.FieldLength_Object+i)->NewTurnSignalLampSt);
        printf("                NewHigh_lowBeamLampsSt:%u\r\n",       (stDy.FieldLength_Object+i)->NewHigh_lowBeamLampsSt);
        printf("                NewBrakeLightSt:%u\r\n",       (stDy.FieldLength_Object+i)->NewBrakeLightSt);
        printf("                NewReversingLightSt:%u\r\n",       (stDy.FieldLength_Object+i)->NewReversingLightSt);
        printf("                ParkingObjectInfo_Reserved1:%lf\r\n",       (stDy.FieldLength_Object+i)->ParkingObjectInfo_Reserved1);
        printf("                blockingBarStatus:%lf\r\n",       (stDy.FieldLength_Object+i)->blockingBarStatus);
        printf("                blockingBarTypeInfo:%lf\r\n",       (stDy.FieldLength_Object+i)->blockingBarTypeInfo);
        printf("                blockingBarDirInfo:%lf\r\n",       (stDy.FieldLength_Object+i)->blockingBarDirInfo);
        printf("                ParkingObjectInfo_Reserved5:%lf\r\n",       (stDy.FieldLength_Object+i)->ParkingObjectInfo_Reserved5);
        printf("            }\r\n");
    }

    count = stDy.FieldLength_ParkingSlot_len / sizeof(stFieldLength_ParkingSlotNPRTDN);
    printf("        FieldLength_ParkingSlot:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                ParkngSpcID_i:%u\r\n",       (stDy.FieldLength_ParkingSlot+i)->ParkngSpcID_i);
        printf("                ParkngSpcSts:%u\r\n",       (stDy.FieldLength_ParkingSlot+i)->ParkngSpcSts);
        printf("                ParkngSpcCode_i:%u\r\n",       (stDy.FieldLength_ParkingSlot+i)->ParkngSpcCode_i);
        printf("                x1_i:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->x1_i);
        printf("                y1_i:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->y1_i);
        printf("                x2_i:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->x2_i);
        printf("                y2_i:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->y2_i);
        printf("                x3_i:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->x3_i);
        printf("                y3_i:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->y3_i);
        printf("                x4_i:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->x4_i);
        printf("                y4_i:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->y4_i);
        printf("                ParkngSpcType:%u\r\n",       (stDy.FieldLength_ParkingSlot+i)->ParkngSpcType);
        printf("                ParkngSpcNum:%lu\r\n",       (stDy.FieldLength_ParkingSlot+i)->ParkngSpcNum);
        printf("                E4CornerMark:%u\r\n",       (stDy.FieldLength_ParkingSlot+i)->E4CornerMark);
        printf("                parkngSlotNumber:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->parkngSlotNumber);
        printf("                ParkingSlotInfo_Reserved2:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved2);
        printf("                ParkingSlotInfo_Reserved3:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved3);
        printf("                ParkingSlotInfo_Reserved4:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved4);
        printf("                ParkingSlotInfo_Reserved5:%lf\r\n",       (stDy.FieldLength_ParkingSlot+i)->ParkingSlotInfo_Reserved5);
        printf("                Position_x:%lf\r\n",       stDy.Position_x);
        printf("                Position_y:%lf\r\n",       stDy.Position_y);
        printf("                Position_z:%lf\r\n",       stDy.Position_z);
        printf("                Roll:%lf\r\n",      stDy.Roll);
        printf("                Yaw:%lf\r\n",       stDy.Yaw);
        printf("                Pitch:%lf\r\n",     stDy.Pitch);
        printf("            }\r\n");
    }

    count = stDy.FieldLength_RealTimeTrackPoint_len / sizeof(stFieldLength_RealTimeTrackPointNPRTDN);
    printf("        FieldLength_RealTimeTrackPoint:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                RealTimeTrackPointID_i:%u\r\n",       (stDy.FieldLength_RealTimeTrackPoint+i)->RealTimeTrackPointID_i);
        printf("                x_i:%lf\r\n",       (stDy.FieldLength_RealTimeTrackPoint+i)->x_i);
        printf("                y_i:%lf\r\n",       (stDy.FieldLength_RealTimeTrackPoint+i)->y_i);
        printf("                heading_i:%lf\r\n",       (stDy.FieldLength_RealTimeTrackPoint+i)->heading_i);
        printf("                stopLine:%lf\r\n",       (stDy.FieldLength_RealTimeTrackPoint+i)->stopLine);
        printf("                GuideLineInfo_Reserved2:%lf\r\n",       (stDy.FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved2);
        printf("                GuideLineInfo_Reserved3:%lf\r\n",       (stDy.FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved3);
        printf("                GuideLineInfo_Reserved4:%lf\r\n",       (stDy.FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved4);
        printf("                GuideLineInfo_Reserved5:%lf\r\n",       (stDy.FieldLength_RealTimeTrackPoint+i)->GuideLineInfo_Reserved5);
        printf("            }\r\n");
    }

    count = stDy.FieldLength_HistoryTrackPoint_len / sizeof(stFieldLength_HistoryTrackPointNPRTDN);
    printf("        FieldLength_HistoryTrackPoint:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                HistoryTrackPointID_i:%u\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->HistoryTrackPointID_i);
        printf("                x_i:%lf\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->x_i);
        printf("                y_i:%lf\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->y_i);
        printf("                z_i:%lf\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->z_i);
        printf("                Width_Learning:%u\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->Width_Learning);
        printf("                cruiseHistoryTrackPointID_i:%lf\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->cruiseHistoryTrackPointID_i);
        printf("                cruiseHistoryX:%lf\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->cruiseHistoryX);
        printf("                cruiseHistoryY:%lf\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->cruiseHistoryY);
        printf("                cruiseHistoryZ:%lf\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->cruiseHistoryZ);
        printf("                parkinglotLevel:%lf\r\n",       (stDy.FieldLength_HistoryTrackPoint+i)->parkinglotLevel);
        printf("                Parking_distance_left:%lf\r\n",         stDy.Parking_distance_left);
        printf("                Cruising_distance_left:%lf\r\n",        stDy.Cruising_distance_left);
        printf("                Learning_distance:%lf\r\n",             stDy.Learning_distance);
        printf("                PathVeriRate:%u\r\n",                   stDy.PathVeriRate);
        printf("                Avoid_pedestrians_number:%u\r\n",       stDy.Avoid_pedestrians_number);
        printf("                Avoid_vehicles_number:%u\r\n",          stDy.Avoid_vehicles_number);
        printf("                PathLearnFailDisp:%u\r\n",              stDy.PathLearnFailDisp);
        printf("                Speed_Bump_Number:%u\r\n",              stDy.Speed_Bump_Number);
        printf("                ViewAngleReq:%u\r\n",                   stDy.ViewAngleReq);
        printf("                NRPX1NoPassing:%lf\r\n",                stDy.NRPX1NoPassing);
        printf("                NRPY1NoPassing:%lf\r\n",                stDy.NRPY1NoPassing);
        printf("                NRPX2NoPassing:%lf\r\n",                stDy.NRPX2NoPassing);
        printf("                NRPY2NoPassing:%lf\r\n",                stDy.NRPY2NoPassing);
        printf("                ParkingRealTimeData_Reserved5:%lf\r\n", stDy.ParkingRealTimeData_Reserved5);
        printf("            }\r\n");
    }

    printf("        }\r\n}\r\n\r\n");
}

//19.NavigationHDLink2Info
void DisplayNavigationHDLink2Info(stNavigationHDLink2Info& stDy)  
{
    printf("NewLanelineDataNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        NavigationPathValid1:%u\r\n\
        RoutePntCnt1:%u\r\n\
        RouteLinkCnt1:%d\r\n\
        RoutePathID1:%lu\r\n"
        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.NavigationPathValid1
        ,stDy.RoutePntCnt1
        ,stDy.RouteLinkCnt1
        ,stDy.RoutePathID1
    );
    
    int count = stDy.LinkItemInfo_len / sizeof(stLinkItemInfoNHDLI);
    printf("        LinkItemInfo:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                LinkItemFormway1:%d\r\n",       (stDy.LinkItemInfo+i)->LinkItemFormway1);
        printf("                LinkItemLinktype1:%d\r\n",       (stDy.LinkItemInfo+i)->LinkItemLinktype1);
        printf("                LinkItemRoadclass1:%d\r\n",       (stDy.LinkItemInfo+i)->LinkItemRoadclass1);
        printf("                LinkItemBegIdx1:%d\r\n",       (stDy.LinkItemInfo+i)->LinkItemBegIdx1);
        printf("                LinkItemPntCnt1:%d\r\n",       (stDy.LinkItemInfo+i)->LinkItemPntCnt1);
        printf("                LinkItemRoadname_1:%s\r\n",       (stDy.LinkItemInfo+i)->LinkItemRoadname_1.c_str());
        printf("                LinkItemLen1:%lf\r\n",       (stDy.LinkItemInfo+i)->LinkItemLen1);
        printf("            }\r\n");
    }

    count = stDy.PntItemInfo_len / sizeof(stPntItemInfoNHDLI);
    printf("        PntItemInfo:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                PntItem_X1:%lf\r\n",            (stDy.PntItemInfo+i)->PntItem_X1);
        printf("                PntItem_Y1:%lf\r\n",            (stDy.PntItemInfo+i)->PntItem_Y1);
        printf("            }\r\n");
    }

    printf("        reserve1_9:%lu\r\n",            stDy.reserve1_9);
    printf("        reserve2_10:%u\r\n",            stDy.reserve2_10);
    printf("        reserve3_11:%lf\r\n",           stDy.reserve3_11);
    printf("        NavigationPathValid2:%u\r\n",   stDy.NavigationPathValid2);
    printf("        RoutePntCnt2:%u\r\n",           stDy.RoutePntCnt2);
    printf("        RouteLinkCnt2:%u\r\n",          stDy.RouteLinkCnt2);
    printf("        RoutePathID2:%lu\r\n",          stDy.RoutePathID2);

    count = stDy.LinkItemInfo2_len / sizeof(stLinkItemInfo2NHDLI);
    printf("        LinkItemInfo2:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                LinkItemFormway2:%d\r\n",       (stDy.LinkItemInfo2+i)->LinkItemFormway2);
        printf("                LinkItemLinktype2:%d\r\n",       (stDy.LinkItemInfo2+i)->LinkItemLinktype2);
        printf("                LinkItemRoadclass2:%d\r\n",       (stDy.LinkItemInfo2+i)->LinkItemRoadclass2);
        printf("                LinkItemBegIdx2:%d\r\n",       (stDy.LinkItemInfo2+i)->LinkItemBegIdx2);
        printf("                LinkItemPntCnt2:%d\r\n",       (stDy.LinkItemInfo2+i)->LinkItemPntCnt2);
        printf("                LinkItemRoadname_2:%s\r\n",       (stDy.LinkItemInfo2+i)->LinkItemRoadname_2.c_str());
        printf("                LinkItemLen2:%lf\r\n",       (stDy.LinkItemInfo2+i)->LinkItemLen2);
        printf("            }\r\n");
    }

    count = stDy.PntItemInfo2_len / sizeof(stPntItemInfo2NHDLI);
    printf("        PntItemInfo2:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                PntItem_X2:%lf\r\n",            (stDy.PntItemInfo2+i)->PntItem_X2);
        printf("                PntItem_Y2:%lf\r\n",            (stDy.PntItemInfo2+i)->PntItem_Y2);
        printf("            }\r\n");
    }

    printf("        reserve1_18:%lu\r\n",           stDy.reserve1_18);
    printf("        reserve2_25:%u\r\n",            stDy.reserve2_25);
    printf("        reserve3_20:%lf\r\n",           stDy.reserve3_20);
    printf("        NavigationPathValid3:%u\r\n",   stDy.NavigationPathValid3);
    printf("        RoutePntCnt3:%d\r\n",           stDy.RoutePntCnt3);
    printf("        RouteLinkCnt3:%d\r\n",          stDy.RouteLinkCnt3);
    printf("        RoutePathID3:%lu\r\n",          stDy.RoutePathID3);

    count = stDy.LinkItemInfo3_len / sizeof(stLinkItemInfo3NHDLI);
    printf("        LinkItemInfo3:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                LinkItemFormway3:%d\r\n",       (stDy.LinkItemInfo3+i)->LinkItemFormway3);
        printf("                LinkItemLinktype3:%d\r\n",       (stDy.LinkItemInfo3+i)->LinkItemLinktype3);
        printf("                LinkItemRoadclass3:%d\r\n",       (stDy.LinkItemInfo3+i)->LinkItemRoadclass3);
        printf("                LinkItemBegIdx3:%d\r\n",       (stDy.LinkItemInfo3+i)->LinkItemBegIdx3);
        printf("                LinkItemPntCnt3:%d\r\n",       (stDy.LinkItemInfo3+i)->LinkItemPntCnt3);
        printf("                LinkItemRoadname3:%s\r\n",       (stDy.LinkItemInfo3+i)->LinkItemRoadname3.c_str());
        printf("                LinkItemLen3:%lf\r\n",       (stDy.LinkItemInfo3+i)->LinkItemLen3);
        printf("            }\r\n");
    }

    count = stDy.PntItemInfo3_len / sizeof(stPntItemInfo3NHDLI);
    printf("        PntItemInfo3:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                PntItem_X3:%lf\r\n",       (stDy.PntItemInfo3+i)->PntItem_X3);
        printf("                PntItem_Y3:%lf\r\n",       (stDy.PntItemInfo3+i)->PntItem_Y3);
        printf("            }\r\n");
    }

    printf("                reserve1_27:%lu\r\n",       stDy.reserve1_27);
    printf("                reserve2_28:%u\r\n",        stDy.reserve2_28);
    printf("                reserve3_29:%lf\r\n",       stDy.reserve3_29);

    printf("        }\r\n}\r\n\r\n");
}

//20.sdTraffiIncident
void DisplaysdTraffiIncident(stsdTraffiIncident& stDy)  
{
    printf("sdTraffiIncident:\r\n{\r\n");
    
    int count = stDy.TraffiIncident_len / sizeof(stTraffiIncidentTI);
    printf("        TraffiIncident:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                naviCongestionInfo:%u\r\n",       (stDy.TraffiIncident+i)->naviCongestionInfo);
        printf("                occupiedLane:%u\r\n",       (stDy.TraffiIncident+i)->occupiedLane);
        printf("                cnstrctnCrdLatitude:%lf\r\n",       (stDy.TraffiIncident+i)->cnstrctnCrdLatitude);
        printf("                cnstrctnCrdLongitude:%lf\r\n",       (stDy.TraffiIncident+i)->cnstrctnCrdLongitude);
        printf("                naviCongestionDistLen:%lu\r\n",       (stDy.TraffiIncident+i)->naviCongestionDistLen);
        printf("                occupiedLaneDtl:%u\r\n",       (stDy.TraffiIncident+i)->occupiedLaneDtl);
        printf("                reserve3:%lf\r\n",       (stDy.TraffiIncident+i)->reserve3);
        printf("            }\r\n");
    }

    printf("        }\r\n}\r\n\r\n");
}

//21.newPlanningLineInfo
void DisplaynewPlanningLineInfo(stnewPlanningLineInfo& stDy)  
{
    printf("newPlanningLineInfo:\r\n{\r\n");
    printf("\
        checksum:%u\r\n\
        counter:%u\r\n\
        planningLineStatus:%u\r\n\
        planningTimestamp:%lf\r\n"
        ,stDy.checksum
        ,stDy.counter
        ,stDy.planningLineStatus
        ,stDy.planningTimestamp
    );
    
    int count = stDy.fieldLengthPlanningLinePoints_len / sizeof(stfieldLengthPlanningLinePointsNPLI);
    printf("        fieldLengthPlanningLinePoints:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                PlanningLinePointsID:%u\r\n",       (stDy.fieldLengthPlanningLinePoints+i)->PlanningLinePointsID);
        printf("                pointsX:%lf\r\n",       (stDy.fieldLengthPlanningLinePoints+i)->pointsX);
        printf("                pointsY:%lf\r\n",       (stDy.fieldLengthPlanningLinePoints+i)->pointsY);
        printf("                pointsZ:%lf\r\n",       (stDy.fieldLengthPlanningLinePoints+i)->pointsZ);
        printf("            }\r\n");
    }

    printf("                accelerationDeceleration:%lf\r\n",          stDy.accelerationDeceleration);
    printf("                navigationPlanningLineStatus:%d\r\n",       stDy.navigationPlanningLineStatus);
    printf("                navigationPlanningTimestamp:%lf\r\n",       stDy.navigationPlanningTimestamp);

    count = stDy.navFieldLengthNavigationPlanningLinePoints_len / sizeof(stnavFieldLengthNavigationPlanningLinePointsNPLI);
    printf("        navFieldLengthNavigationPlanningLinePoints:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                navPlanningLinePointsID:%u\r\n",       (stDy.navFieldLengthNavigationPlanningLinePoints+i)->navPlanningLinePointsID);
        printf("                navPointsX:%lf\r\n",       (stDy.navFieldLengthNavigationPlanningLinePoints+i)->navPointsX);
        printf("                navPointsY:%lf\r\n",       (stDy.navFieldLengthNavigationPlanningLinePoints+i)->navPointsY);
        printf("                navPointsZ:%lf\r\n",       (stDy.navFieldLengthNavigationPlanningLinePoints+i)->navPointsZ);
        printf("            }\r\n");
    }

    printf("        reservedDataLength1:%u\r\n", stDy.reservedDataLength1);
    printf("        reservedDataLength2:%u\r\n", stDy.reservedDataLength2);
    printf("        reservedDataLength3:%u\r\n", stDy.reservedDataLength3);
    printf("        reservedDataLength4:%u\r\n", stDy.reservedDataLength4);
    printf("        reservedDataLength5:%u\r\n", stDy.reservedDataLength5);
    printf("        }\r\n}\r\n\r\n");
}

//22.drivingAreaIdentification
void DisplaydrivingAreaIdentification(stdrivingAreaIdentification& stDy)  
{
    printf("drivingAreaIdentification:\r\n{\r\n");
    printf("\
        checksum:%u\r\n\
        counter:%u\r\n\
        drivingAreaIdentificationStatus:%u\r\n"
        ,stDy.checksum
        ,stDy.counter
        ,stDy.drivingAreaIdentificationStatus
    );
    
    int count = stDy.drivingAreaIdentificationPoints_len / sizeof(uint8_t);
    printf("        drivingAreaIdentificationPoints:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("                drivingAreaIdentificationPoints[%d]:%u\r\n", i, stDy.drivingAreaIdentificationPoints[i]);
    }
    printf("        }\r\n");

    printf("        sizetBevh:%u\r\n",              stDy.sizetBevh);
    printf("        sizetBevw:%u\r\n",              stDy.sizetBevw);
    printf("        xBoundMin:%lf\r\n",             stDy.xBoundMin);
    printf("        xBoundMax:%lf\r\n",             stDy.xBoundMax);
    printf("        yBoundMin:%lf\r\n",             stDy.yBoundMin);
    printf("        yBoundMax:%lf\r\n",             stDy.yBoundMax);
    printf("        meterPerPixelX:%lf\r\n",        stDy.meterPerPixelX);
    printf("        meterPerPixelY:%lf\r\n",        stDy.meterPerPixelY);
    printf("        maskThreshold:%lf\r\n",         stDy.maskThreshold);
    
    printf("}\r\n\r\n");
}

//23.HPAMapDataNotify
void DisplayHPAMapDataNotify(stHPAMapDataNotify& stDy)  
{
    printf("HPAMapDataNotify:\r\n{\r\n");
    printf("\
        Checksum:%u\r\n\
        Counter:%u\r\n\
        timestamp:%lf\r\n"
        ,stDy.Checksum
        ,stDy.Counter
        ,stDy.timestamp
    );
    
    int count = stDy.FieldLength_GlobalTrackPoint_len / sizeof(stFieldLength_GlobalTrackPointHPAMDN);
    printf("        FieldLength_GlobalTrackPoint:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                GlobalTrackPointID_i:%u\r\n",     (stDy.FieldLength_GlobalTrackPoint+i)->GlobalTrackPointID_i);
        printf("                x_i:%lf\r\n",                     (stDy.FieldLength_GlobalTrackPoint+i)->x_i);
        printf("                y_i:%lf\r\n",                     (stDy.FieldLength_GlobalTrackPoint+i)->y_i);
        printf("                z_i:%lf\r\n",                     (stDy.FieldLength_GlobalTrackPoint+i)->z_i);
        printf("                Width:%lf\r\n",                   (stDy.FieldLength_GlobalTrackPoint+i)->Width);
        printf("            }\r\n");
    }
    printf("        }\r\n");

    count = stDy.BuildMapStartPoint_len / sizeof(stBuildMapStartPointHPAMDN);
    printf("        BuildMapStartPoint:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                x_start:%lf\r\n",                 (stDy.BuildMapStartPoint+i)->x_start);
        printf("                y_start:%lf\r\n",                 (stDy.BuildMapStartPoint+i)->y_start);
        printf("                z_start:%lf\r\n",                 (stDy.BuildMapStartPoint+i)->z_start);
        printf("                x_stop:%lf\r\n",                 (stDy.BuildMapStartPoint+i)->x_stop);
        printf("                y_stop:%lf\r\n",                 (stDy.BuildMapStartPoint+i)->y_stop);
        printf("                z_stop:%lf\r\n",                 (stDy.BuildMapStartPoint+i)->z_stop);
        printf("            }\r\n");
    }
    printf("        }\r\n");

    count = stDy.FieldLength_Rampway_len / sizeof(stFieldLength_RampwayHPAMDN);
    printf("        FieldLength_Rampway:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                RampwayID_i:%u\r\n",           (stDy.FieldLength_Rampway+i)->RampwayID_i);
        printf("                x1_i:%lf\r\n",                 (stDy.FieldLength_Rampway+i)->x1_i);
        printf("                y1_i:%lf\r\n",                 (stDy.FieldLength_Rampway+i)->y1_i);
        printf("                z1_i:%lf\r\n",                 (stDy.FieldLength_Rampway+i)->z1_i);
        printf("                x2_i:%lf\r\n",                 (stDy.FieldLength_Rampway+i)->x2_i);
        printf("                y2_i:%lf\r\n",                 (stDy.FieldLength_Rampway+i)->y2_i);
        printf("                z2_i:%lf\r\n",                 (stDy.FieldLength_Rampway+i)->z2_i);
        printf("            }\r\n");
    }
    printf("        }\r\n");

    count = stDy.FieldLength_SpeedBumps_len / sizeof(stFieldLength_SpeedBumpsHPAMDN);
    printf("        FieldLength_SpeedBumps:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                SpeedBumpsID_i:%u\r\n",                 (stDy.FieldLength_SpeedBumps+i)->SpeedBumpsID_i);
        printf("                x_i_Left:%lf\r\n",                      (stDy.FieldLength_SpeedBumps+i)->x_i_Left);
        printf("                y_i_Left:%lf\r\n",                      (stDy.FieldLength_SpeedBumps+i)->y_i_Left);
        printf("                z_i_Left:%lf\r\n",                      (stDy.FieldLength_SpeedBumps+i)->z_i_Left);
        printf("                x_i_Right:%lf\r\n",                     (stDy.FieldLength_SpeedBumps+i)->x_i_Right);
        printf("                y_i_Right:%lf\r\n",                     (stDy.FieldLength_SpeedBumps+i)->y_i_Right);
        printf("                z_i_Right:%lf\r\n",                     (stDy.FieldLength_SpeedBumps+i)->z_i_Right);
        printf("                SpeedBumpsWidth:%u\r\n",               (stDy.FieldLength_SpeedBumps+i)->SpeedBumpsWidth);
        printf("            }\r\n");
    }
    printf("        }\r\n");

    count = stDy.FieldLength_UprightColumn_len / sizeof(stFieldLength_UprightColumnHPAMDN);
    printf("        FieldLength_UprightColumn:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                UprightColumnID_i:%u\r\n",     (stDy.FieldLength_UprightColumn+i)->UprightColumnID_i);
        printf("                x1_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->x1_i);
        printf("                y1_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->y1_i);
        printf("                z1_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->z1_i);
        printf("                x2_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->x2_i);
        printf("                y2_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->y2_i);
        printf("                z2_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->z2_i);
        printf("                x3_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->x3_i);
        printf("                y3_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->y3_i);
        printf("                z3_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->z3_i);
        printf("                x4_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->x4_i);
        printf("                y4_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->y4_i);
        printf("                z4_i:%lf\r\n",                 (stDy.FieldLength_UprightColumn+i)->z4_i);
        printf("                height_i:%lf\r\n",             (stDy.FieldLength_UprightColumn+i)->height_i);
        printf("            }\r\n");
    }
    printf("        }\r\n");

    count = stDy.FieldLength_ParkngSpcI_len / sizeof(stFieldLength_ParkngSpcIHPAMDN);
    printf("        FieldLength_ParkngSpcI:\r\n");
    printf("        {\r\n");
    for (int i = 0; i < count; ++i)
    {
        printf("            {\r\n");
        printf("                ParkngSpcID_i:%u\r\n",         (stDy.FieldLength_ParkngSpcI+i)->ParkngSpcID_i);
        printf("                ParkngSpcSts:%u\r\n",         (stDy.FieldLength_ParkngSpcI+i)->ParkngSpcSts);
        printf("                x1_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->x1_i);
        printf("                y1_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->y1_i);
        printf("                z1_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->z1_i);
        printf("                x2_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->x2_i);
        printf("                y2_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->y2_i);
        printf("                z2_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->z2_i);
        printf("                x3_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->x3_i);
        printf("                y3_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->y3_i);
        printf("                z3_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->z3_i);
        printf("                x4_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->x4_i);
        printf("                y4_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->y4_i);
        printf("                z4_i:%lf\r\n",                 (stDy.FieldLength_ParkngSpcI+i)->z4_i);
        printf("                TargetSlotID:%u\r\n",         (stDy.FieldLength_ParkngSpcI+i)->TargetSlotID);
        printf("            }\r\n");
    }

    printf("        }\r\n}\r\n\r\n");
}

char* unix_time_to_string_ms(uint64_t timeStampUs) {
    // 将微秒拆分为秒和微秒部分
    time_t seconds = (time_t)(timeStampUs / 1000000);
    long milliseconds = timeStampUs % 1000;  // 修正为取余1000000

    //struct tm *tm = gmtime(&seconds);
    struct tm local_tm;
    localtime_r(&seconds, &local_tm);

    char *buffer = (char *)malloc(64 * sizeof(char));
    if (buffer == NULL) {
        fprintf(stderr, "Memory allocation failed\n");
        return NULL;
    }

    if (strftime(buffer, 64, "%Y-%m-%d %H:%M:%S", &local_tm) == 0) {
        fprintf(stderr, "strftime failed\n");
        free(buffer);
        return NULL;
    }

    snprintf(buffer + strlen(buffer), 64 - strlen(buffer), ".%03ld", milliseconds);

    return buffer;
}

//LanelineDataNotify
void DisplayLanelineDataNotify2(stLanelineDataNotify& stDy)     
{
    printf("LanelineDataNotify:     Counter:%u ", stDy.Counter);
    int count = stDy.FieldLength_Line_len / 66;//sizeof(stLanelineDataNotifyFLL);
    for (int i = 0; i < count; ++i)
    {
        char* ptm = unix_time_to_string_ms((stDy.FieldLength_Line+i)->sys_time_us);
        printf("Checksum:%12u sys_time_us:%lf %s", stDy.Checksum, (stDy.FieldLength_Line+i)->sys_time_us, ptm);
        if (ptm != NULL)
        {
            free(ptm);
            ptm = NULL;
        }
        break;
    }
}

//14.NewLanelineDataNotify
void DisplayNewLanelineDataNotify2(stNewLanelineDataNotify& stDy)  
{
    printf("NewLanelineDataNotify:  Counter:%u ", stDy.Counter);
    int len = 0, sum_len = 0;

    char* ptmp = (char*)stDy.FieldLength_Line;
    stNLLDN_FieldLength_Line *pdy = (stNLLDN_FieldLength_Line*)ptmp;
    for (int i = 0; stDy.FieldLength_Line_len > sum_len; ++i) //new_lineidobj
    {
        char* ptm = unix_time_to_string_ms((stDy.FieldLength_Line+i)->sys_time_us);
        printf("Checksum:%12u sys_time_us:%lf %s", stDy.Checksum, (stDy.FieldLength_Line+i)->sys_time_us, ptm);
        if (ptm != NULL)
        {
            free(ptm);
            ptm = NULL;
        }
        sum_len += (stDy.FieldLength_Line+i)->len;
        break;
        // ptmp += (pdy->len);
        // pdy = (stNLLDN_FieldLength_Line*)ptmp;
    }
}

// uint32_t SPSet(std::shared_ptr<stVehiclePositionInfoNotify> stDy)         {return SetVehiclePositionInfoNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stRTKInfoNotify> stDy)                     {return SetRTKInfoNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stIMUInfoNotify> stDy)                     {return SetIMUInfoNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stObstacleInfoNotify> stDy)                {return SetObstacleInfoNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stLanelineDataNotify> stDy)                {return SetLanelineDataNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stChangeLaneDataNotify> stDy)              {return SetChangeLaneDataNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stPilotStatusNotify> stDy)                 {return SetPilotStatusNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> stDy)     {return SetPilotAlarmAndNoticeInfoNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stBroadcastInfoNotify> stDy)               {return SetBroadcastInfoNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stPlanningLineInfoNotify> stDy)            {return SetPlanningLineInfoNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stHudRoadInfoNotify> stDy)                 {return SetHudRoadInfoNotify(*stDy);}
// uint32_t SPSet(std::shared_ptr<stHudMappathInfo_EG> stDy)                 {return SetHudMappathInfo_EG(*stDy);}
// uint32_t SPSet(std::shared_ptr<stHudNavigationmap> stDy)                  {return SetHudNavigationmap(*stDy);}
// uint32_t SPSet(std::shared_ptr<oshrinfo_t> stDy)                          {return SetOverseasHudRoadInfoNotify(*stDy);}




uint32_t SPSet(std::shared_ptr<stVehiclePositionInfoNotify> stDy)         {return SetVehiclePositionInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stRTKInfoNotify> stDy)                     {return SetRTKInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stIMUInfoNotify> stDy)                     {return SetIMUInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stObstacleInfoNotify> stDy)                {return SetObstacleInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stLanelineDataNotify> stDy)                {return SetLanelineDataNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stChangeLaneDataNotify> stDy)              {return SetChangeLaneDataNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stPilotStatusNotify> stDy)                 {return SetPilotStatusNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> stDy)     {return SetPilotAlarmAndNoticeInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stBroadcastInfoNotify> stDy)               {return SetBroadcastInfoNotify2(*stDy);}
//uint32_t SPSet(std::shared_ptr<stPlanningLineInfoNotify> stDy)            {return SetPlanningLineInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stHudRoadInfoNotify> stDy)                 {return SetHudRoadInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stHudMappathInfo_EG> stDy)                 {return SetHudMappathInfo_EG2(*stDy);}
uint32_t SPSet(std::shared_ptr<stHudNavigationmap> stDy)                  {return SetHudNavigationmap2(*stDy);}
uint32_t SPSet(std::shared_ptr<oshrinfo_t> stDy)                          {return SetOverseasHudRoadInfoNotify2(*stDy);}

uint32_t SPSet(std::shared_ptr<stNewLanelineDataNotify             >stDy) {return SetNewLanelineDataNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stNewBroadcastInfoNotify            >stDy) {return SetNewBroadcastInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stPlanningLineInfoNotify            >stDy) {return SetPlanningLineInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stNavigationStatus_LinkInfoNotify   >stDy) {return SetNavigationStatus_LinkInfoNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stNewParkingRealTimeDataNotify      >stDy) {return SetNewParkingRealTimeDataNotify2(*stDy);}
uint32_t SPSet(std::shared_ptr<stNavigationHDLink2Info             >stDy) {return SetNavigationHDLink2Info2(*stDy);}
uint32_t SPSet(std::shared_ptr<stsdTraffiIncident                  >stDy) {return SetsdTraffiIncident2(*stDy);}
uint32_t SPSet(std::shared_ptr<stnewPlanningLineInfo               >stDy) {return SetnewPlanningLineInfo2(*stDy);}
uint32_t SPSet(std::shared_ptr<stdrivingAreaIdentification         >stDy) {return SetdrivingAreaIdentification2(*stDy);}
uint32_t SPSet(std::shared_ptr<stHPAMapDataNotify                  >stDy) {return SetHPAMapDataNotify2(*stDy);}



void SPDisplay(std::shared_ptr<stVehiclePositionInfoNotify> stDy)         {DisplayVehiclePositionInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stRTKInfoNotify> stDy)                     {DisplayRTKInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stIMUInfoNotify> stDy)                     {DisplayIMUInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stObstacleInfoNotify> stDy)                {DisplayObstacleInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stLanelineDataNotify> stDy)                {DisplayLanelineDataNotify(*stDy);}
void SPDisplay(std::shared_ptr<stChangeLaneDataNotify> stDy)              {DisplayChangeLaneDataNotify(*stDy);}
void SPDisplay(std::shared_ptr<stPilotStatusNotify> stDy)                 {DisplayPilotStatusNotify(*stDy);}
void SPDisplay(std::shared_ptr<stPilotAlarmAndNoticeInfoNotify> stDy)     {DisplayPilotAlarmAndNoticeInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stBroadcastInfoNotify> stDy)               {DisplayBroadcastInfoNotify(*stDy);}
//void SPDisplay(std::shared_ptr<stPlanningLineInfoNotify> stDy)            {DisplayPlanningLineInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stHudRoadInfoNotify> stDy)                 {DisplayHudRoadInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stHudMappathInfo_EG> stDy)                 {DisplayHudMappathInfo_EG(*stDy);}
void SPDisplay(std::shared_ptr<stHudNavigationmap> stDy)                  {DisplayHudNavigationmap(*stDy);}
void SPDisplay(std::shared_ptr<oshrinfo_t> stDy)                          {DisplayOverseasHudRoadInfoNotify(*stDy);}

void SPDisplay(std::shared_ptr<stNewLanelineDataNotify> stDy)             {DisplayNewLanelineDataNotify(*stDy);}
void SPDisplay(std::shared_ptr<stNewBroadcastInfoNotify> stDy)            {DisplayNewBroadcastInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stPlanningLineInfoNotify> stDy)            {DisplayPlanningLineInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stNavigationStatus_LinkInfoNotify> stDy)   {DisplayNavigationStatus_LinkInfoNotify(*stDy);}
void SPDisplay(std::shared_ptr<stNewParkingRealTimeDataNotify> stDy)      {DisplayNewParkingRealTimeDataNotify(*stDy);}
void SPDisplay(std::shared_ptr<stNavigationHDLink2Info> stDy)             {DisplayNavigationHDLink2Info(*stDy);}
void SPDisplay(std::shared_ptr<stsdTraffiIncident> stDy)                  {DisplaysdTraffiIncident(*stDy);}
void SPDisplay(std::shared_ptr<stnewPlanningLineInfo> stDy)               {DisplaynewPlanningLineInfo(*stDy);}
void SPDisplay(std::shared_ptr<stdrivingAreaIdentification> stDy)         {DisplaydrivingAreaIdentification(*stDy);}
void SPDisplay(std::shared_ptr<stHPAMapDataNotify> stDy)                  {DisplayHPAMapDataNotify(*stDy);}

