/*
 * stub_zlgcan.c —— CAN 驱动桩库（仅用于验证，不含任何真实硬件逻辑）
 * ==================================================================
 * 用途：在容器内编译成 Windows x64 的 zlgcan.dll，供 HudAutoTest 的
 *       `hudcore.can.load_zlg_library()` 走真实的 Windows 加载路径
 *       （ctypes.WinDLL → LoadLibrary），从而在没有 ZLG 硬件的环境里
 *       验证「驱动探测 → 加载 → 按约定调用」整条链路是否正常。
 *
 * 编译（容器内，MinGW-w64）：
 *   x86_64-w64-mingw32-gcc -shared -O2 -o zlgcan.dll stub_zlgcan.c
 *
 * 导出函数（签名与 ZLG 官方 ZCANAPI / VCI 接口的常见用法一致）：
 *   ZCAN_GetDeviceCount()                 返回设备数（桩：1）
 *   ZCAN_OpenDevice(type, index, reserved) 返回设备句柄（桩：0x1000）
 *   ZCAN_CloseDevice(handle)               返回 1（成功）
 *   VCI_OpenDevice(type, index, reserved)  返回 1（成功）
 *   VCI_CloseDevice(type, index)           返回 1（成功）
 *   zlgcan_stub_version()                  返回桩库版本号，便于自检确认调用到的是本桩
 *
 * 注意：调用约定在 x64 Windows 上只有一种（Microsoft x64），
 *       因此 WinDLL（stdcall）与 CDLL（cdecl）在这些导出函数上行为一致。
 */
#include <stdint.h>

#define EXPORT __declspec(dllexport)

EXPORT uint32_t ZCAN_GetDeviceCount(void)
{
    return 1;                      /* 桩：报告 1 个虚拟设备 */
}

EXPORT uint64_t ZCAN_OpenDevice(uint32_t device_type, uint32_t device_index,
                                uint32_t reserved)
{
    (void)device_type; (void)device_index; (void)reserved;
    return 0x1000;                 /* 桩：返回固定句柄 */
}

EXPORT uint32_t ZCAN_CloseDevice(uint64_t handle)
{
    (void)handle;
    return 1;
}

EXPORT uint32_t VCI_OpenDevice(uint32_t device_type, uint32_t device_index,
                               uint32_t reserved)
{
    (void)device_type; (void)device_index; (void)reserved;
    return 1;
}

EXPORT uint32_t VCI_CloseDevice(uint32_t device_type, uint32_t device_index)
{
    (void)device_type; (void)device_index;
    return 1;
}

EXPORT uint32_t zlgcan_stub_version(void)
{
    return 0x00010000;             /* 桩库版本 1.0.0 */
}
