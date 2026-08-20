// AR-HUD 23 服务 SOME/IP 客户端 —— C++（vsomeip 库 + 自研大端编解码 "sp" 层）
// ===========================================================================
// 单个 vsomeip application 订阅全部 23 个事件（11 个服务）：
//   - request_service + request_event + subscribe 每 (service, instance, event)
//   - register_message_handler 按 (service, instance, event) 注册（共用同一回调）
//   - 载荷解析：hud_data_types（大端，与 Python hud_data_types.py 一致）
// 运行：
//   g++ -std=c++14 -I/usr/local/include hud_client.cpp hud_data_types.cpp \
//       -L/usr/local/lib -lvsomeip3 -o hud_client
//   ./hud_client     （配置 vsomeip.json，routing=arhud01）
// 环境变量：
//   VSOMEIP_CONFIGURATION=./vsomeip.json   （默认 ./vsomeip.json）
//   HUD_EXIT_ALL=1  收齐 23 个事件后退出（测试用）
#include <vsomeip/vsomeip.hpp>

#include <atomic>
#include <chrono>
#include <cstdio>
#include <iostream>
#include <mutex>
#include <set>
#include <string>
#include <thread>

#include "hud_data_types.hpp"

// ---------------- 全局接收统计（跨 io 线程） ----------------
static std::mutex g_mtx;
static std::set<std::pair<uint16_t, uint16_t>> g_received;  // (service, event)
static std::atomic<int> g_total(0);
static std::atomic<bool> g_all_received(false);

static const char* g_app_name = "hud_client_cpp";

// ---------------- 事件回调 ----------------
static void on_message(const std::shared_ptr<vsomeip::message>& msg) {
    const uint16_t svc = msg->get_service();
    const uint16_t event = msg->get_method();
    auto payload = msg->get_payload();
    const uint8_t* data = payload->get_data();
    const size_t len = payload->get_length();

    // 查找事件信息（name/kind）
    const hud::EventInfo* info = nullptr;
    for (int i = 0; i < hud::HUD_EVENTS_COUNT; ++i) {
        if (hud::HUD_EVENTS[i].service == svc && hud::HUD_EVENTS[i].event == event) {
            info = &hud::HUD_EVENTS[i];
            break;
        }
    }
    const char* name = info ? info->name : "unknown";
    hud::Kind kind = info ? info->kind : hud::Kind::Opaque;

    std::string detail;
    if (info && kind != hud::Kind::Opaque) {
        if (hud::deserialize_by_kind(kind, data, len, detail)) {
            detail = "  " + detail;
        } else {
            detail = "  [解析失败]";
        }
    } else {
        // Opaque：hex 展示
        char hex[64];
        int n = (int)(len < 16 ? len : 16);
        for (int i = 0; i < n; ++i) snprintf(hex + i * 2, 3, "%02X", data[i]);
        detail = std::string("  HEX=") + hex;
    }

    {
        std::lock_guard<std::mutex> lock(g_mtx);
        g_received.insert({svc, event});
    }
    int total = ++g_total;
    int got = (int)g_received.size();
    printf("[recv] #%d svc=0x%04X inst=0x%04X event=0x%04X %-34s len=%zu 已收 %d/23%s\n",
           total, svc, msg->get_instance(), event, name, len, got, detail.c_str());
    fflush(stdout);

    if (got >= hud::HUD_EVENTS_COUNT) {
        if (!g_all_received.exchange(true)) {
            printf("[done] 全部 %d 个事件均已收到，退出\n", hud::HUD_EVENTS_COUNT);
            fflush(stdout);
            {   // 独立标记文件（供测试脚本断言，规避 stdout 与 vsomeip 日志交错）
                FILE* f = fopen("/tmp/hud_cpp_done.marker", "w");
                if (f) { fprintf(f, "DONE %d/%d", got, hud::HUD_EVENTS_COUNT); fclose(f); }
            }
            std::_Exit(0);   // 跳过 vsomeip stop()（已知可能挂起）
        }
    }
}

// ---------------- 可用性回调 ----------------
static void on_availability(vsomeip::service_t svc, vsomeip::instance_t inst, bool available) {
    printf("[avail] svc=0x%04X inst=0x%04X %s\n", svc, inst, available ? "available" : "unavailable");
    fflush(stdout);
}

int main(int argc, char** argv) {
    (void)argc; (void)argv;

    // 0) 字节序/编解码自测（与主机端序无关）
    if (!hud::self_test()) {
        std::cerr << "hud_data_types 自测失败" << std::endl;
        return 1;
    }
    std::cout << "[hud_cpp] 大端编解码自测通过 ✓  订阅 " << hud::HUD_EVENTS_COUNT << " 个事件" << std::endl;

    // 1) 创建 vsomeip 应用
    auto app = vsomeip::runtime::get()->create_application(g_app_name);
    if (!app->init()) {
        std::cerr << "app->init() 失败（检查 ./vsomeip.json 与 routing=arhud01）" << std::endl;
        return 1;
    }

    // 2) 订阅全部 23 个事件（每个服务 request_service + request_event + subscribe）
    for (int i = 0; i < hud::HUD_EVENTS_COUNT; ++i) {
        const auto& e = hud::HUD_EVENTS[i];
        app->request_service(e.service, e.instance);
        std::set<vsomeip::eventgroup_t> groups = { e.group };
        app->request_event(e.service, e.instance, e.event, groups,
                           vsomeip::event_type_e::ET_FIELD);
        app->subscribe(e.service, e.instance, e.group, 0x00 /* DEFAULT_MAJOR: 与服务端 offer 一致 */);
        app->register_message_handler(e.service, e.instance, e.event, on_message);
        app->register_availability_handler(e.service, e.instance, on_availability);
    }

    // 3) start() 阻塞调用线程 → 独立线程（与 vsomeip_py 包装器一致）
    std::thread io_thread([&app]() { app->start(); });
    io_thread.detach();
    std::cout << "[hud_cpp] 客户端已启动，等待事件（Ctrl+C 退出）..." << std::endl;

    // 4) 等待收齐（HUD_EXIT_ALL=1 时回调里已 _Exit，这里仅兜底防主线程退出）
    for (;;) std::this_thread::sleep_for(std::chrono::hours(24));
    return 0;
}
