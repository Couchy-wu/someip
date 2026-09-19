# drivers/someip（旧位置，已迁移）

SOME/IP 服务端运行时库的**首选位置已改为 `thirdparty/arhud_someip/<平台>/`**
（第三方运行时库统一收纳在 `thirdparty/` 下）。

本目录仍被探测链兼容：若 `thirdparty/arhud_someip/<平台>/` 中没有库，
程序会继续在 `drivers/someip/<平台>/` 查找，方便既有部署平滑过渡。

- 放置与编译说明：见 [`../thirdparty/arhud_someip/README.md`](../../thirdparty/arhud_someip/README.md)
- 功能说明：见 [`../docs/SOMEIP_REPLAY.md`](../../docs/SOMEIP_REPLAY.md)
