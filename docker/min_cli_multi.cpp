// 最小 C++ 客户端（单应用订阅 20 个服务）—— 验证 vsomeip "一个应用可订阅任意多个服务"
// 一个 vsomeip application 对 20 个服务分别 request_service + request_event + subscribe，
// 用 ONE 个 message handler(ANY_SERVICE, ANY_INSTANCE, EVENT_ID) 接收全部事件。
// 编译: g++ -std=c++14 -I/usr/local/include min_cli_multi.cpp -L/usr/local/lib -lvsomeip3 -o min_cli_multi
#include <vsomeip/vsomeip.hpp>
#include <iostream>
#include <thread>
#include <chrono>
#include <set>
#include <mutex>
#include <atomic>

#define SERVICES 20
#define SERVICE_ID_BASE 0x0100
#define INSTANCE_ID 0x0001
#define EVENT_ID 0x8003
#define EVENT_GROUP 0x01

static std::mutex mtx;
static std::set<int> received_services;   // 已收到事件的服务序号
static std::atomic<int> received_total(0);

static void on_notification(const std::shared_ptr<vsomeip::message> &_message) {
    auto payload = _message->get_payload();
    int idx = (int)_message->get_service() - SERVICE_ID_BASE;
    {
        std::lock_guard<std::mutex> lock(mtx);
        received_services.insert(idx);
    }
    received_total++;
    std::cout << "RECV: svc_idx=" << idx
              << " svc=0x" << std::hex << (int)_message->get_service()
              << " event=0x" << (int)_message->get_method()
              << std::dec << " payload=" << payload->get_length() << "B"
              << " 已收齐 " << received_services.size() << "/" << SERVICES << std::endl;
}

int main(int argc, char **argv) {
    (void)argc; (void)argv;
    auto app = vsomeip::runtime::get()->create_application("min_cli_multi");
    if (!app->init()) {
        std::cout << "init FAILED" << std::endl;
        return 1;
    }

    // 一个应用，订阅全部 20 个服务的事件
    // 注意: vsomeip 的消息分发按 (service, instance, method) 精确匹配，
    // 需对每个服务注册一次 handler（可共用同一个回调函数）
    for (int i = 0; i < SERVICES; ++i) {
        vsomeip::service_t svc = (vsomeip::service_t)(SERVICE_ID_BASE + i);
        app->request_service(svc, INSTANCE_ID);
        std::set<vsomeip::eventgroup_t> groups = { EVENT_GROUP };
        app->request_event(svc, INSTANCE_ID, EVENT_ID, groups,
                           vsomeip::event_type_e::ET_FIELD);
        app->subscribe(svc, INSTANCE_ID, EVENT_GROUP, 0x00 /* DEFAULT_MAJOR: 与服务端 offer 的 major 一致 */);
        app->register_message_handler(svc, INSTANCE_ID, EVENT_ID, on_notification);
    }

    // 注意: vsomeip 的 start() 会阻塞调用线程（主分发循环运行在调用线程上），
    // 需放入独立线程（vsomeip_py 包装器同样如此处理）
    std::thread io_thread([&app]() { app->start(); });
    io_thread.detach();
    std::cout << "min_cli_multi started: 1 个应用订阅 " << SERVICES << " 个服务, 等待 40s..." << std::endl;

    for (int s = 0; s < 40; ++s) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        if (received_services.size() >= SERVICES) {
            std::cout << "DONE: 全部 " << SERVICES << " 个服务均已收到事件 ✔" << std::endl;
            fflush(stdout);
            std::_Exit(0);   // 跳过 vsomeip stop()（已知可能挂起），测试场景直接退出
        }
    }
    std::cout << "TIMEOUT: 只收到 " << received_services.size() << "/" << SERVICES
              << " 个服务的事件 ✘" << std::endl;
    fflush(stdout);
    std::_Exit(1);
}
