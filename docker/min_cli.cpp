// 最小 C++ 测试客户端：请求服务并打印 availability
// 编译: g++ -std=c++14 -I/usr/local/include min_cli.cpp -L/usr/local/lib -lvsomeip3 -o min_cli
#include <vsomeip/vsomeip.hpp>
#include <iostream>
#include <thread>
#include <chrono>

static vsomeip::service_t service_id = 0x000C;
static vsomeip::instance_t service_instance_id = 0x000C;

int main(int argc, char **argv) {
    (void)argc; (void)argv;
    auto app = vsomeip::runtime::get()->create_application("min_cli");
    if (!app->init()) {
        std::cout << "init FAILED" << std::endl;
        return 1;
    }
    app->register_availability_handler(service_id, service_instance_id,
        [](vsomeip::service_t s, vsomeip::instance_t i, bool avail) {
            std::cout << "AVAILABILITY: " << std::hex << (int)s << "." << (int)i
                      << " = " << (avail ? "true" : "false") << std::endl;
        });
    app->request_service(service_id, service_instance_id);
    app->start();
    std::cout << "min_cli started, waiting 10s..." << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(10));
    std::cout << "min_cli done" << std::endl;
    app->stop();
    return 0;
}
