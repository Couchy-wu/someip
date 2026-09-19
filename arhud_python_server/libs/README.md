# libs —— SOME/IP 协议栈（SP 分支）与架构相关说明

```
libs/
├── arm64/     aarch64 用（板端）：libsomeip.so / libsomeip-cfg.so / libsomeip-sd.so / libsomeip-e2e.so
└── x86_64/    x86_64 用（PC 联调）：同上（**库文件不入 git**，见下）
```

## 来源与版本（2026-02 对齐参考实现 lipeng20260228）

| 目录 | 来源 | 版本日期 |
|------|------|----------|
| `arm64/` | 参考实现 `libs.zip → libs/lib_bst_t517` | 2025-12-15 |
| `x86_64/` | 参考实现 `libs.zip → libs/lib_x86` | 2025-12-23 |

更新方式：解压参考实现的 `libs.zip`，用 `lib_bst_t517/*` 覆盖 `arm64/`、`lib_x86/*` 覆盖 `x86_64/`
（SONAME 均为 `libsomeip*.so`，可直接替换），再 `make -C src` 重新链接并跑一次回放验证。

## 为什么 x86_64 库不入 git

`arm64/` 四个库共约 4.4 MB，随仓库分发（板端部署需要）；
`x86_64/` 同名库合计约 64 MB（`libsomeip.so` 单个 49 MB），入库会让仓库体积翻倍且几乎无法增量拉取，
因此 `.gitignore` 忽略了 `libs/x86_64/*.so`，只保留本说明。需要时按上面的方式从参考实现获取。

## 编译

```bash
make -C src ARCH=aarch64                      # 默认：arm64/（板端/容器）
make -C src ARCH=x86_64                       # x86_64/（PC 联调）
ARHUD_SERVICE_PROFILE=bplus python main.py    # 运行期切换服务表代（见 src/arhud_services.h）
```
