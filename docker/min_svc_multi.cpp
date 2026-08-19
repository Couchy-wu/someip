// 最小 C++ 服务端（单应用提供 20 个服务）—— 验证 vsomeip "一个应用可提供任意多个服务"
// 一个 vsomeip application：
//   - 对每个服务 offer_service + offer_event（事件组 0x01，ET_FIELD，major 0）
//   - 周期 notify：payload = [服务序号, 轮次]，客户端可按服务区分
// 编译: g++ -std=c++14 -I/usr/local/include min_svc_multi.cpp -L/usr/local/lib -lvsomeip3 -o min_svc_multi
#include <vsomeip/vsomeip.hpp>
#include <iostream>
#include <thread>
#include <chrono>
#include <set>

#define SERVICES 20
#define SERVICE_ID_BASE 0x0100
#define INSTANCE_ID 0x0001
#define EVENT_ID 0x8003
#define EVENT_GROUP 0x01

int main(int argc, char **argv) {
    (void)argc; (void)argv;
    auto app = vsomeip::runtime::get()->create_application("min_svc_multi");
    if (!app->init()) {
        std::cout << "init FAILED" << std::endl;
        return 1;
    }

    // 一个应用，提供全部 20 个服务（offer_service 可在 start 前调用，会排队）
    for (int i = 0; i < SERVICES; ++i) {
        vsomeip::service_t svc = (vsomeip::service_t)(SERVICE_ID_BASE + i);
        app->offer_service(svc, INSTANCE_ID);
    }

    // start() 阻塞调用线程 → 放入独立线程（与 vsomeip_py 包装器一致）
    std::thread io_thread([&app]() { app->start(); });
    io_thread.detach();

    // start 后再 offer_event（与包装器/官方示例一致）
    for (int i = 0; i < SERVICES; ++i) {
        vsomeip::service_t svc = (vsomeip::service_t)(SERVICE_ID_BASE + i);
        std::set<vsomeip::eventgroup_t> groups = { EVENT_GROUP };
        app->offer_event(svc, INSTANCE_ID, EVENT_ID, groups,
                         vsomeip::event_type_e::ET_FIELD,
                         std::chrono::milliseconds::zero(), false, true, nullptr,
                         vsomeip::reliability_type_e::RT_UNKNOWN);
    }
    std::cout << "min_svc_multi: 1 个应用提供 " << SERVICES
              << " 个服务 (0x" << std::hex << SERVICE_ID_BASE << "..0x"
              << SERVICE_ID_BASE + SERVICES - 1 << std::dec
              << "), 事件 0x" << std::hex << EVENT_ID << std::dec
              << "，持续 notify..." << std::endl;

    // 周期 notify：每轮把 20 个服务各发一条（payload = [服务序号, 轮次]）
    int round = 0;
    for (;;) {
        for (int i = 0; i < SERVICES; ++i) {
            auto payload = vsomeip::runtime::get()->create_payload();
            std::vector<vsomeip::byte_t> data;
            data.push_back((vsomeip::byte_t)i);
            data.push_back((vsomeip::byte_t)(round & 0xFF));
            payload->set_data(data);
            app->notify((vsomeip::service_t)(SERVICE_ID_BASE + i), INSTANCE_ID,
                        EVENT_ID, payload, true);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        ++round;
        if ((round % 25) == 0)
            std::cout << "  ... 已 notify " << round << " 轮" << std::endl;
    }
    return 0;
}
