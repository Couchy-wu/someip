// 最小 C++ 测试服务端：提供 0x000C/0x000C + 事件 0x8003(组 0x01)，周期 notify
// 编译: g++ -std=c++14 -I/usr/local/include min_svc.cpp -L/usr/local/lib -lvsomeip3 -o min_svc
#include <vsomeip/vsomeip.hpp>
#include <iostream>
#include <thread>
#include <chrono>
#include <set>

static vsomeip::service_t service_id = 0x000C;
static vsomeip::instance_t service_instance_id = 0x000C;
static vsomeip::event_t event_id = 0x8003;
static vsomeip::eventgroup_t event_group = 0x01;

int main(int argc, char **argv) {
    (void)argc; (void)argv;
    auto app = vsomeip::runtime::get()->create_application("min_svc");
    if (!app->init()) {
        std::cout << "init FAILED" << std::endl;
        return 1;
    }
    app->offer_service(service_id, service_instance_id);

    std::set<vsomeip::eventgroup_t> groups;
    groups.insert(event_group);
    app->offer_event(service_id, service_instance_id, event_id, groups,
                     vsomeip::event_type_e::ET_FIELD,
                     std::chrono::milliseconds::zero(), false, true, nullptr,
                     vsomeip::reliability_type_e::RT_UNKNOWN);

    app->start();
    std::cout << "min_svc started, notifying every 1s..." << std::endl;

    for (int i = 0; i < 12; ++i) {
        auto payload = vsomeip::runtime::get()->create_payload();
        std::vector<vsomeip::byte_t> data = {0x00, 0x01, 0x11, 0x22, 0x33,
                                             static_cast<vsomeip::byte_t>(0x40 + i)};
        payload->set_data(data);
        app->notify(service_id, service_instance_id, event_id, payload, true);
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    std::cout << "min_svc done" << std::endl;
    app->stop();
    return 0;
}
