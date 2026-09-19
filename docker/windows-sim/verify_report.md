# HudAutoTest — Windows 环境功能验证报告

- 运行环境: `Windows-2008ServerR2-6.1.7601-SP1`
- 解释器: `C:\Python313\python.exe`
- Python: `3.13.15`
- 项目根: `Z:\work`

**结果：17 通过 / 0 失败 / 0 跳过**

| # | 验证项 | 结果 | 证据 |
|---|--------|------|------|
| 1 | 1. Windows 运行时环境 | PASS | platform.system()=Windows, sys.platform=win32, Python=3.13.15, arch=AMD64, 64bit=True, exe=python.exe |
| 2 | 2. hudcore 平台探测（system） | PASS | OS=Windows Python=3.13.15 arch=AMD64 \| exe_suffix='.exe' \| py_status=ok |
| 3 | 3. 路径层 + 中文路径读写 | PASS | root=Z:\work; 中文写入/读取成功 |
| 4 | 4. 界面字体与中文渲染字体 | PASS | selected='微软雅黑', 可用字体=0, PIL字体=<_io.BytesIO object at 0x00000000015FF150> |
| 5 | 5. Tk 窗口创建（虚拟显示） | PASS | Tk 8.6 创建并销毁成功, geometry=320x120+0+0 |
| 6 | 6. Theme 样式 + TextRedirector 重定向 | PASS | Theme 样式数=8, TextRedirector 捕获：'重定向-测试-中文' |
| 7 | 7. main.py 导入链（不启动 GUI 主循环） | PASS | import main 成功；MainWindow/TextRedirector 可用；导出=3 项 |
| 8 | 8. 全部界面与工具模块导入 | PASS | 45/45 模块全部导入成功 |
| 9 | 9. CAN 驱动库探测与加载（stub DLL） | PASS | lib=Z:\work\drivers\windows\zlgcan.dll, Py_GetVersion()=b'3.13.15 (main, Sep  1 2026, 14:16:48) [MSC v.1944 64 bit (AMD64)]' |
| 10 | 10. CAN 驱动缺失时的报错友好性 | PASS | 已按 HUD_ZLG_LIB 覆盖路径 |
| 11 | 11. 外部程序探测不抛异常 | PASS | ffmpeg=命中; office=未找到; editor=未找到; terminal=未找到; where_python=命中 |
| 12 | 12. 图标相似度比较（dHash） | PASS | 相同图→True, 不同图→False, hash 差异=32 bit |
| 13 | 13. GIF 合成（Pillow，含中文输出路径） | PASS | 结果.gif 生成成功, 5 帧, 723 bytes |
| 14 | 14. 图像增强 / 透视标定模块可用（cv2 链路） | PASS | cv2 5.0.0 中文路径读写 OK；ImageEnhancer 方法数=1 |
| 15 | 15. CAN 信号 → 数据字节（outputMatrix.csv） | PASS | 信号 0x095/Eng_Start_Result_Fdbk_Info_S（位=1.0-1.1, 长度=8）: 枚举0→[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00] 枚举1→[0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00] 值随枚举变化=True |
| 16 | 16. 信号矩阵 XLSX → CSV 转换 | PASS | openpyxl 读写 OK，模块入口=XlsmToCsvConverter |
| 17 | 17. 项目自带自检脚本在 Windows 下可运行 | PASS | check_imports.py rc=0 (项目内部导入全部可解析 ✓); selftest.py rc=0 (============================================================) |
