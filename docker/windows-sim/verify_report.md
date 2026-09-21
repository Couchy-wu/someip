# HudAutoTest — 环境功能验证报告（Windows（Wine 容器内 + Windows 版 CPython））

**✅ 结果：19 通过 / 0 失败 / 0 跳过**（共 19 项，通过率 100.0%，耗时 93.47s）

- 生成时间: `2026-09-21 16:03:42`
- 复现命令: `C:\Python313\python.exe verify_windows.py --expect win`

## 运行环境

| 项 | 值 |
|----|----|
| 平台 | Windows-2008ServerR2-6.1.7601-SP1 |
| 系统 | Windows 2008ServerR2 |
| 机器 | AMD64 |
| Python | 3.13.15 |
| 解释器 | C:\Python313\python.exe |
| 项目根 | Z:\work |
| 运行方式 | Wine 容器内运行 Windows 版 CPython |
| CAN 驱动 | Z:\work\drivers\windows\zlgcan.dll； 接口形态：unknown； 警告：接口形态无法识别（缺 ZCAN: ZCAN_OpenDevice, ZCAN_CloseDevice, ZCAN_InitCAN, ZCAN_StartCAN, ZCAN_Transmit, ZCAN_Receive, ZCAN_GetReceiveNum, ZCAN_SetValue, ZCAN_GetDeviceInf；缺 VCI: VCI_OpenDevice, VCI_CloseDevice, VCI_InitCAN, VCI_StartCAN, VCI_Transmit, VCI_Receive, VCI_GetReceiveNum） |
| SOME/IP 库 | 未找到 SOME/IP 服务端库（libarhud_server.dll / arhud_server.dll）； 1) 把 libarhud_server.dll 放到 thirdparty/arhud_someip/windows/（或设置 HUD_SOMEIP_LIB=<完整路径>）；旧位置 drivers/someip/windows/ 仍兼容； 2) 当前仓库**暂无 Windows DLL 产物**：需用 MSVC 编译 arhud_python_server； （编译方式见 docs/SOMEIP_REPLAY.md「Windows 支持」一节）； 3) 临时替代：在 Ubuntu 上运行本功能，或用 WSL/容器承载 SOME/IP 回放 |

## 与上次运行对比

- 上次运行: `2026-09-21 15:59:19`（判定 PASS）
- 上次运行: `2026-09-21 15:59:19`（判定 PASS）
- 无变化（与上次逐项一致）

## 逐项结果

| # | 验证项 | 结果 | 耗时(s) | 证据 |
|---|--------|------|---------|------|
| 1 | 1. 运行时环境（OS / Python / 架构） | ✅ PASS | 0.1 | platform.system()=Windows, sys.platform=win32, Python=3.13.15, arch=AMD64, 64bit=True, exe=python.exe |
| 2 | 2. hudcore 平台探测（system） | ✅ PASS | 0.0 | OS=Windows Python=3.13.15 arch=AMD64 \| exe_suffix='.exe' \| py_status=ok |
| 3 | 3. 路径层 + 中文路径读写 | ✅ PASS | 0.0 | root=Z:\work; 中文写入/读取成功 |
| 4 | 4. 界面字体与中文渲染字体 | ✅ PASS | 0.1 | selected='微软雅黑', 可用字体=0, PIL字体=<_io.BytesIO object at 0x00000000012F0360> |
| 5 | 5. Tk 窗口创建（虚拟显示） | ✅ PASS | 2.2 | Tk 8.6 创建并销毁成功, geometry=320x120+0+0 |
| 6 | 6. Theme 样式 + TextRedirector 重定向 | ✅ PASS | 2.4 | Theme 样式数=12, TextRedirector 捕获：'重定向-测试-中文' |
| 7 | 7. main.py 导入链（不启动 GUI 主循环） | ✅ PASS | 1.9 | import main 成功；MainWindow/TextRedirector 可用；导出=3 项 |
| 8 | 8. 全部界面与工具模块导入 | ✅ PASS | 0.3 | 72/72 模块全部导入成功 |
| 9 | 9. CAN 驱动库探测与加载（桩库） | ✅ PASS | 0.0 | 桩库加载成功并通过调用验证：Py_GetVersion()=607270176；本机库 zlgcan.dll(接口=unknown) |
| 10 | 10. CAN 驱动缺失时的报错友好性 | ✅ PASS | 0.0 | 已按 HUD_ZLG_LIB 覆盖路径 |
| 11 | 11. 外部程序探测不抛异常 | ✅ PASS | 0.1 | ffmpeg=命中; office=未找到; editor=未找到; terminal=未找到; where_python=命中 |
| 12 | 12. 图标相似度比较（dHash） | ✅ PASS | 0.1 | 相同图→True, 不同图→False, hash 差异=32 bit |
| 13 | 13. GIF 合成（Pillow，含中文输出路径） | ✅ PASS | 0.1 | 结果.gif 生成成功, 5 帧, 723 bytes |
| 14 | 14. 图像增强 / 透视标定模块可用（cv2 链路） | ✅ PASS | 0.0 | cv2 5.0.0 中文路径读写 OK；ImageEnhancer 方法数=1 |
| 15 | 15. CAN 信号 → 数据字节（outputMatrix.csv） | ✅ PASS | 0.7 | 信号 0x095/Eng_Start_Result_Fdbk_Info_S（位=1.0-1.1, 长度=8）: 枚举0→[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00] 枚举1→[0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00] 值随枚举变化=True |
| 16 | 16. 信号矩阵 XLSX → CSV 转换 | ✅ PASS | 0.4 | openpyxl 读写 OK，模块入口=XlsmToCsvConverter |
| 17 | 17. 项目自带自检脚本可运行 | ✅ PASS | 12.9 | check_imports.py rc=0 (项目内部导入全部可解析 ✓); check_static.py rc=0 (静态检查通过 ✓); selftest.py rc=0 (============================================================) |
| 18 | 18. 单元测试（pytest） | ✅ PASS | 69.4 | ...........ss........................................ [100%] |
| 19 | 19. SOME/IP 回放窗口（布局与降级） | ✅ PASS | 2.7 | 23 个事件，字段数 {'RTK': 27, 'PilotStatus': 7, 'VehiclePosition': 34, 'HudNavmap': 3}；状态=SOME/IP 库不可用（动作已置灰）｜原因：未找到 S；库不可用(已降级) |

## 说明

- 容器/虚拟显示内无法验证：真实 CAN 硬件、外部程序界面、GPU 路径（详见 docker/windows-sim/README.md §6）
- 逐项超时上限 180s（可用 HUD_VERIFY_TIMEOUT 调整），超时项判 FAIL 但会继续后续验证
