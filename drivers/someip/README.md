# SOME/IP 服务端库放置目录

程序按 `drivers/someip/<平台>/` → `vendor/arhud_someip/<平台>/` → 项目根 → 系统路径 的顺序查找库，
也可用环境变量 `HUD_SOMEIP_LIB`（完整文件路径）或 `HUD_SOMEIP_LIB_DIR`（目录）直接指定。

| 平台 | 需要的文件 | 说明 |
|------|-----------|------|
| Linux | `libarhud_server.so` + `libsomeip*.so` | **必须放在同一目录**；运行前设 `LD_LIBRARY_PATH` 指向该目录（SP 版 libsomeip 由插件方式加载） |
| Windows | `libarhud_server.dll` | **当前尚无产物**（需 MSVC 编译，见 docs/SOMEIP_REPLAY.md §3）；缺失时界面会显示"库不可用"并置灰动作按钮 |

编译（Linux，源码在 someip 工程的 arhud_python_server/src）：

```bash
make libarhud_server.so ARCH=aarch64 SP_LIBS=<SP库目录>   # 或 ARCH=x86_64
cp libarhud_server.so libsomeip*.so <本项目>/drivers/someip/linux/
```

> 本目录下的 `*.so` / `*.dll` 已在 `.gitignore` 中忽略，不会误提交大文件。
