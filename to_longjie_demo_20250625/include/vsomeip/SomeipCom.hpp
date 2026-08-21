#ifndef SOMEIPIMPL_H
#define SOMEIPIMPL_H

#include <thread>
#include <vector>
#include <queue>
#include <map>
#include <memory>
#include <mutex>
#include <atomic>
#include <condition_variable>

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

//客户端请求关闭服务端
#define SP_SHUTDOWN_SERVICEID           0x1234
#define SP_SHUTDOWN_INSTANCEID          0x5678
#define SP_SHUTDOWN_METHODID            0x7777

#define SP_NAME_LEN                     100

namespace vsomeip_v3
{
    class message;
    class runtime;
    class application;
    enum  class state_type_e :uint8_t;
}

namespace SomeipNS
{
    //回调接口均不应进行耗时操作，建议只处理数据的收发
    /*服务端注册请求回调函数类型：usService(服务ID)、usInstance(实例ID)、usMethod(方法ID)、pcInput(从客户端接收的数据)、
    uInLen(接收长度)、pcOutput(发送给客户端的数据)、puOutLen(发送长度)、pParam(附加参数，默认给NULL)*/
    typedef int32_t (*SPServerRRCallback)(uint16_t usService, uint16_t usInstance, uint16_t usMethod, 
                    uint8_t* pcInput, uint32_t uInLen, uint8_t** pcOutput, uint32_t* puOutLen, void* pParam);

    /*服务端注册事件回调函数类型：usMethod(事件ID)、pcNotifyData(发送给客户端的通知数据)、pcNotifyDataLen(发送长度)、
    pParam(附加参数，默认给NULL)*/
    typedef int32_t (*SPServerNotifyCallback)(uint16_t usService, uint16_t usInstance, uint16_t usMethod, 
                    uint8_t** pcNotifyData, uint32_t* pcNotifyDataLen, void* pParam);

    /*客户端注册请求/事件回调函数类型：usMethod(方法ID)、pcInput(从服务端接收的数据)、uInLen(接收长度)、pParam(附加参数，默认给NULL)*/
    typedef int32_t (*SPClientCallback)(uint16_t usService, uint16_t usInstance, uint16_t usMethod, 
                    uint8_t* pcInput, uint32_t uInLen, void* pParam);

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

        st_method_event(){
            ot = OT_UNKNOWN;
            mt = MT_UNKNOWN;
            usServiceId = usInstanceId = usMethodId = usEventGroup = usSessionId = usNotifyPeriod = usClientID = usPort = ucReliability = 0;
            bOffer = false;
            pCallback = pParam =  nullptr;
        }
    }stMethodEvent;

    typedef struct st_map_key
    {
        uint16_t    usServiceId;
        uint16_t    usInstanceId;
        uint16_t    usMethodId;

        st_map_key()
        {
            usServiceId = usInstanceId = usMethodId = 0u;
        }

        bool operator<(const st_map_key& other) const;
    }stMapKey;

    typedef struct st_recv_data_queue
    {
        uint8_t *pData;
        uint32_t nLen;

        st_recv_data_queue()
        {
            pData = nullptr;
            nLen = 0;
        }

        ~st_recv_data_queue()
        {
			if (pData != nullptr)
			{
            	free(pData);
            	pData = nullptr;
			}
        }
    }stRecvDataQueue;


    class SOMEIP_EXPORT SomeipCom
    {
        public:
                            SomeipCom(std::string sName = ""); 
                            ~SomeipCom();

        bool  setConfigurePath(std::string sFile, std::string sPath = ""); 
        bool  init();
        void  start();

        void  serverResponseCallbackFuncRegist(uint16_t usServiceId, uint16_t usInstanceId,
                            uint16_t usMethodId, SPServerRRCallback pCallback, void* pParam = nullptr);     /*请求/响应模式，服务端注册回调*/

        void  clientRequestNoResponse(uint16_t usServiceId, uint16_t usInstanceId, 
                            uint16_t usMethodId, uint8_t *pcInput, uint32_t uInLen);                        /*Fire&Forget方式，客户端请求无返回数据*/

        void  clientRequestInvoke(uint16_t usServiceId, uint16_t usInstanceId, 
                            uint16_t usMethodId, uint8_t *pcInput, uint32_t uInLen, uint8_t** ppcOutput, 
                            uint32_t* puOutLen, uint32_t uTimeoutMs = 3000);                                /*客户端同步请求*/

        void  clientRequestInvokeAsync(uint16_t usServiceId, uint16_t usInstanceId,
                            uint16_t usMethodId, uint8_t *pcInput, uint32_t uInLen, 
                            SPClientCallback pCallback, void* pParam = nullptr);                            /*客户端异步请求*/

        void  serverNotifyCallbackFuncRegist(uint16_t usServiceId, uint16_t usInstanceId, 
                            uint16_t usMethodId, uint16_t usEventGroup, 
                            SPServerNotifyCallback pCallback, void* pParam = nullptr);                      /*周期性事件/通知模式，服务端注册回调*/

        void  clientSubscribeCallbackFuncRegist(uint16_t usServiceId, uint16_t usInstanceId, 
                            uint16_t usMethodId, uint16_t usEventGroup, 
                            SPClientCallback pCallback, void* pParam = nullptr);                            /*周期性事件/通知模式，客户端注册回调*/

        void  serverSendNotify(uint16_t usServiceId, uint16_t usInstanceId, 
                            uint16_t usMethodId, uint8_t *pcInput, uint32_t uInLen);                        /*事件/通知模式，服务端主动发送一次通知*/


        std::shared_ptr<uint8_t[]> dealloc(int iSize); //for test shared_ptr

        // 为兼容C风格调用
        void uninit();
        void setCStyleInterface(bool bFlag = false);
        stMethodEvent*     find(uint16_t usService, uint16_t usInstance, uint16_t usMethod);
        void  startTimeout(uint32_t uMilliseconds);
    
        void*                                       m_pCallbackParam;
        std::shared_ptr<vsomeip_v3::runtime>        m_rtm;
        std::shared_ptr<vsomeip_v3::application>    m_app;
        std::vector<stMethodEvent>                  m_vecMethodEvents;

        protected:
        void    _run(uint32_t uMilliseconds);
        void    _offer();
        void    _stop_offer();
        void    _notify();  // 订阅-通知:服务端下发通知
        void    _getMethodEventFromeConfig();
        void    _waitOnCondition(std::unique_lock<std::mutex>&& mxLock, bool *bPredicate, 
                std::condition_variable&& cnCondition, std::uint32_t uiTimeout);
   
        void    _stateHandler(vsomeip_v3::state_type_e stState);
        void    _availableHandler(uint16_t snService, uint16_t stInstance, bool bAvailable);
        void    _shutdownCalled(const std::shared_ptr<vsomeip_v3::message> &_message);
        void    _messageHandler(const std::shared_ptr<vsomeip_v3::message> &msMessage);

        private:
        std::atomic<bool>           m_bShutdown;
        bool                        m_bCStyleInterface;                     // 为兼容C接口
        bool                        m_bIsCom;
        bool                        m_bWaitAvailability;
        bool                        m_bHasMsg;
        bool                        m_bStart;
        bool                        m_bAvailable;
        bool                        m_bOffer;
        bool                        m_bRun;
    
        std::string		            m_appName;
        std::string		            m_cfgFile;
        std::string		            m_cfgPath;
        std::mutex		            m_mutex;
        std::mutex		            m_msgMutex;
        std::mutex                  m_rspMutex;
        std::condition_variable     m_startCondition;
        std::condition_variable     m_availableCondition;
        std::condition_variable     m_runCondition;
        std::condition_variable     m_msgCondition;
        std::condition_variable     m_offerCondition;
        std::condition_variable     m_msgResponseCondition;
        std::condition_variable     m_msgShutdownCondition;

        std::thread*                m_pRunThread;
        std::thread*                m_pServiceThread;
        std::thread*                m_pApplicationThread;

        std::map<uint16_t, bool>    m_mapMsgType;               //记录session id对应的请求类型是同步还是异步
        stMethodEvent               m_syncRequest;              //同步请求消息
        std::shared_ptr<vsomeip_v3::message> m_syncMsgResponse; //同步响应消息
        stMethodEvent               m_asyncRequest;             //异步请求消息
        
        std::map<std::pair<uint16_t,uint16_t>, std::pair<bool, bool>>   m_mapServiceAvailable;
    };
}

#endif