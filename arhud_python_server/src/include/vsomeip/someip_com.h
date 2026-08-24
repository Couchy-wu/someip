/******************************************************************************
*brief:     SOME/IP C interface
*version:   1.0
*author:    li.peng89
*time:      2023/07/30
******************************************************************************/
#ifndef SOMEIP_COMMON_H
#define SOMEIP_COMMON_H

#include <stdint.h>
#include <stdbool.h>

#if _WIN32
    #ifdef SOMEIP_DLL_EXPORT
        #define SOMEIP_EXPORT __declspec(dllexport)  // 导出符号
    #else
        #define SOMEIP_EXPORT __declspec(dllimport)
    #endif
    #define SOMEIP_EXPORT_CLASS_EXPLICIT

    #if SOMEIP_DLL_COMPILATION
        #define SOMEIP_IMPORT_EXPORT __declspec(dllexport)
    #else
        #define SOMEIP_IMPORT_EXPORT __declspec(dllimport)
    #endif

    #if SOMEIP_DLL_COMPILATION_CONFIG
        #define SOMEIP_IMPORT_EXPORT_CONFIG __declspec(dllexport)
    #else
        #define SOMEIP_IMPORT_EXPORT_CONFIG __declspec(dllimport)
    #endif
#else
    #define SOMEIP_EXPORT
    #define SOMEIP_IMPORT_EXPORT
    #define SOMEIP_IMPORT_EXPORT_CONFIG
#endif

//SOME/IP
#define SP_NAME_LEN                 100
#define CONFIGURE_PATH_LEN          256

typedef enum{
    OT_METHOD   = 0x00,
    OT_FIELD    = 0x01,
    OT_EVENT    = 0X02,
    OT_UNKNOWN  = 0XFF
}OFFER_TYPE;

typedef enum{
    MT_SYNC     = 0x00,
    MT_ASYNC    = 0x01,
    MT_UNKNOWN  = 0XFF
}METHOD_TYPE;

typedef struct st_method_event
{
    OFFER_TYPE  ot;
    METHOD_TYPE mt;
    char        name[SP_NAME_LEN];
    uint16_t    usServiceId;
    uint16_t    usInstanceId;
    uint16_t    usMethodId;
    uint16_t    usEventGroup;
    uint16_t    usSessionId;
    uint16_t    usNotifyPeriod;
    uint16_t    usClientID;
    uint16_t    usPort;
    uint8_t     ucReliability;
    bool        bOffer;
    void*       pCallback;
    void*       pParam;
}stMethodEvent;

typedef struct stSPInstance
{
    void*   spImpl;
    void*   resverse1;
    int     iServer;
    bool    bUseMessageQueue;
    char    sAppName[SP_NAME_LEN];
    char    sCfgPath[CONFIGURE_PATH_LEN];
}SPInstance;

//回调接口均不应进行耗时操作(回调最大耗时不应超过100ms)，建议只处理数据的收发
/*请求/响应模式回调函数类型(服务端用)：usService(服务ID)、usInstance(实例ID)、usMethod(方法ID)、pcInput(从客户端接收的数据)、
uInLen(接收长度)、pcOutput(发送给客户端的数据)、puOutLen(发送长度)、pParam(附加参数，默认给NULL)*/
typedef int32_t (*SPServerRRCallback)(uint16_t usService, uint16_t usInstance, uint16_t usMethod, 
                uint8_t* pcInput, uint32_t uInLen, uint8_t** pcOutput, uint32_t* puOutLen, void* pParam);

/*事件/通知模式回调函数类型(服务端用)：usMethod(事件ID)、pcNotifyData(发送给客户端的通知数据)、pcNotifyDataLen(发送长度)、
pParam(附加参数，默认给NULL), *pcNotifyDataLen值为0xFFFFFFFF时不发送通知*/
typedef int32_t (*SPServerNotifyCallback)(uint16_t usService, uint16_t usInstance, uint16_t usMethod, 
                uint8_t** pcNotifyData, uint32_t* pcNotifyDataLen, void* pParam);

/*请求/响应模式、事件/通知模式回调函数类型(客户端用)：usMethod(方法ID)、pcInput(从服务端接收的数据)、uInLen(接收长度)、pParam(附加参数，默认给NULL)*/
typedef int32_t (*SPClientCallback)(uint16_t usService, uint16_t usInstance, uint16_t usMethod, 
                uint8_t* pcInput, uint32_t uInLen, void* pParam);

/*Field的Set/Get/Notify回调函数类型：usService(服务ID)、usInstance(实例ID)、usMethod(方法ID)、pcInput(从客户端接收的数据)、
uInLen(接收长度)、pcOutput(发送给客户端的数据)、pParam(附加参数，默认给NULL)*/
//typedef int32_t (*SPServerFieldCallback)(uint16_t usService, uint16_t usInstance, uint16_t usMethod, 
//                uint8_t* pcInput, uint32_t uInLen, uint8_t* pcOutput, void* pParam);

#ifdef __cplusplus 
extern "C"
{
#endif
    /*初始化SPInstance*/
    SOMEIP_EXPORT int32_t   SPInit(SPInstance* pInst, char* pcName, char* pcCfgFileName);

    /*请求/响应模式，服务端注册回调*/
    SOMEIP_EXPORT int32_t   SPServerResponseCallbackFuncRegist(SPInstance* pInst, uint16_t usService, uint16_t usInstance, 
                            uint16_t usMethod, SPServerRRCallback pCallback, void* pParam);

    /*请求/响应模式，Fire&Forget方式，客户端请求无返回数据*/
    SOMEIP_EXPORT int32_t   SPClientRequestNoResponse(SPInstance* pInst, uint16_t usService, uint16_t usInstance, 
                            uint16_t usMethod, uint8_t *pcInput, uint32_t uInLen);

    /*请求/响应模式，客户端同步请求*/
    SOMEIP_EXPORT int32_t   SPClientRequestInvoke(SPInstance* pInst, uint16_t usService, uint16_t usInstance, 
                            uint16_t usMethod, uint8_t *pcInput, uint32_t uInLen, uint8_t** pcOutput, uint32_t* puOutLen, uint32_t uTimeoutMs);

    /*请求/响应模式，客户端异步请求*/
    SOMEIP_EXPORT int32_t   SPClientRequestInvokeAsync(SPInstance* pInst, uint16_t usService, uint16_t usInstance, 
                            uint16_t usMethod, uint8_t *pcInput, uint32_t uInLen, SPClientCallback pCallback, void* pParam);

    /*周期性事件/通知模式，服务端注册回调*/
    SOMEIP_EXPORT int32_t   SPServerNotifyCallbackFuncRegist(SPInstance* pInst, uint16_t usService, uint16_t usInstance, 
                            uint16_t usMethod,  uint16_t usEventGroup, SPServerNotifyCallback pCallback, void* pParam);

    /*周期性事件/通知模式，客户端注册回调*/
    SOMEIP_EXPORT int32_t   SPClientSubscribeCallbackFuncRegist(SPInstance* pInst, uint16_t usService, uint16_t usInstance, 
                            uint16_t usMethod,  uint16_t usEventGroup, SPClientCallback pCallback, void* pParam);

    /*事件/通知模式，服务端主动发送一次通知*/
    SOMEIP_EXPORT int32_t   SPServerSendNotify(SPInstance* pInst, uint16_t usServiceId, uint16_t usInstanceId, 
                            uint16_t usMethodId, uint8_t *pcInput, uint32_t uInLen);

    /*Field的Set/Get Notify模式，用于需要访问和修改服务属性，并在属性变化时通知客户端*/
    //SOMEIP_EXPORT int32_t   SPClientFieldSet(SPInstance* pInst, uint16_t usServiceId, uint16_t usInstanceId, 
    //                        uint16_t usMethodId, SPServerFieldCallback pCallback, void* pParam);

    /*Field的Set/Get Notify模式，用于需要访问和修改服务属性，并在属性变化时通知客户端*/
    //SOMEIP_EXPORT int32_t   SPClientFieldGet(SPInstance* pInst, uint16_t usServiceId, uint16_t usInstanceId, 
    //                        uint16_t usMethodId, SPServerFieldCallback pCallback, void* pParam);

    /*开始消息处理*/
    SOMEIP_EXPORT int32_t   SPStart(SPInstance* pInstance);
    /*停止消息处理*/
    SOMEIP_EXPORT int32_t   SPStop(SPInstance* pInst);
    /*销毁SPInstance*/
    SOMEIP_EXPORT int32_t   SPRelease(SPInstance* pInstance);

    /*获取实例名称*/
    SOMEIP_EXPORT int32_t   SPGetName(SPInstance* pInst, char* pcName);
    /*获取实例ID*/
    SOMEIP_EXPORT uint16_t  SPGetClient(SPInstance* pInst);
    /*提供服务*/
    SOMEIP_EXPORT int32_t   SPOfferService(SPInstance* pInst, uint16_t usService, uint16_t usInstance, bool bEnable);
    /*提供事件*/
    SOMEIP_EXPORT int32_t   SPOfferEvent(SPInstance* pInst, uint16_t usService, uint16_t usInstance, uint16_t usEvent, uint16_t pEventGroups, bool bEnable);
    /*请求服务*/
    SOMEIP_EXPORT int32_t   SPRequestService(SPInstance* pInst, uint16_t usService, uint16_t usInstance);
    /*注销服务*/
    SOMEIP_EXPORT int32_t   SPReleaseService(SPInstance* pInst, uint16_t usService, uint16_t usInstance);
    /*请求事件*/
    SOMEIP_EXPORT int32_t   SPRequestEvent(SPInstance* pInst, uint16_t usService, uint16_t usInstance, uint16_t usEvent, uint16_t pEventGroups);
    /*注销事件*/
    SOMEIP_EXPORT int32_t   SPReleaseEvent(SPInstance* pInst, uint16_t usService, uint16_t usInstance, uint16_t usEvent);
    /*订阅事件组*/
    SOMEIP_EXPORT int32_t   SPSubscribe(SPInstance* pInst, uint16_t usService, uint16_t usInstance, uint16_t usEvent, uint16_t usEventgroup);
    /*取消订阅事件组*/
    SOMEIP_EXPORT int32_t   SPUnSubscribe(SPInstance* pInst, uint16_t usService, uint16_t usInstance, uint16_t usEvent, uint16_t usEventgroup);
    /*检测服务是否存在*/
    SOMEIP_EXPORT bool      SPIsAvailable(SPInstance* pInst, uint16_t usService, uint16_t usInstance);
    /*获取方法/事件数据*/
    SOMEIP_EXPORT int32_t   SPGetMethodEventFromConfig(SPInstance* pInst, stMethodEvent** pme, uint32_t *puCount);
#ifdef __cplusplus 
} 
#endif

#endif