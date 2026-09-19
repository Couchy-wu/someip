# -*- coding: utf-8 -*-
"""hudcore.someip.backend —— SOME/IP 服务端库的探测与加载（跨平台）

搜索顺序（先命中先用）：
    1. 环境变量 HUD_SOMEIP_LIB / ARHUD_LIB_PATH（完整文件路径，便于现场临时替换）
    2. 环境变量 HUD_SOMEIP_LIB_DIR（所在目录）
    3. 项目内 thirdparty/arhud_someip/<平台>-<架构>/（**首选**，如 linux-x86_64、linux-aarch64）
    4. 项目内 thirdparty/arhud_someip/<平台>/
    5. 项目内 thirdparty/arhud_someip/
    6. 项目内 drivers/someip/<平台>/            （旧位置，兼容既有部署）
    7. 项目根目录
    8. 系统库路径（LD_LIBRARY_PATH / 系统目录，由动态加载器自行查找）

放置规则见 thirdparty/README.md：**第三方运行时库（按平台区分）** 统一放
thirdparty/<组件>/<平台>/；drivers/<平台>/ 与 bin/<平台>/ 为历史部署目录，仍兼容。

加载器选择：
    Windows → ctypes.WinDLL（stdcall；本库导出为 C 接口，x64 下与 CDLL 等价）
    Linux   → ctypes.CDLL

同目录依赖：Linux 上加载 libarhud_server.so 之前，会先用绝对路径 + RTLD_GLOBAL
**预加载同目录的 `libsomeip*.so`**（`preload_sibling_libraries()`）。SP 版
libsomeip 在运行期按文件名插件式 dlopen 这些库，预加载后即可命中，
因此**不需要用户手工设置 LD_LIBRARY_PATH**。

注意（现状）：Windows 侧 **暂无 DLL 产物**（需要 MSVC 编译，见 docs/SOMEIP_REPLAY.md），
因此 Windows 上会走"找不到库 → 返回 None + 修复提示"的路径，界面会显示明确的
不可用提示而不是崩溃。
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Optional

from ..platform.paths import paths
from ..platform.system import IS_WINDOWS, lib_suffix

# 库文件名候选（按平台生成，保留多种命名以便兼容不同构建产物）
LIB_CANDIDATES: tuple[str, ...] = (
    f"libarhud_server{lib_suffix}",
    f"arhud_server{lib_suffix}",
)

# 环境变量（两个都支持：HUD_* 为本项目约定，ARHUD_* 为原 someip 工程约定）
_ENV_FILE = ("HUD_SOMEIP_LIB", "ARHUD_LIB_PATH")
_ENV_DIR = ("HUD_SOMEIP_LIB_DIR", "ARHUD_LIB_DIR")

# 已缓存的加载结果（避免重复 dlopen）
_CACHE: dict[str, object] = {}

# 已预加载过同目录依赖的目录（避免重复 RTLD_GLOBAL 加载）
_PRELOADED_DIRS: set[str] = set()


def preload_sibling_libraries(target: Path) -> list[Path]:
    """把库所在目录中的 `libsomeip*.so` 预加载进来（返回成功预加载的文件）。

    为什么需要：SP 版 libsomeip 通过 **插件方式** 在运行期按**文件名** dlopen
    依赖（如 `libsomeip-cfg.so`，缺了就会报
    `Configuration module could not be loaded!`，甚至让 `create()` 长时间阻塞），
    仅靠 `libarhud_server.so` 的 NEEDED 记录不足以让加载器找到同目录的插件。
    这里用**绝对路径 + RTLD_GLOBAL** 先把它们加载进来，之后按文件名的 dlopen
    会直接命中已加载对象，因此**不再需要用户手工设置 LD_LIBRARY_PATH**。

    注意：必须**多轮**加载 —— `libsomeip-cfg/sd/e2e.so` 自身 NEEDED `libsomeip.so`，
    而后者位于同目录却不在加载器搜索路径里；只有先加载 `libsomeip.so`
    （其 SONAME 进内存后）才能按 SONAME 满足后续依赖。因此循环到"一轮无进展"为止。

    预加载失败不抛异常（缺依赖/架构不符时交给后续 libarhud_server 加载去报错）。
    """
    if IS_WINDOWS:
        return []
    try:
        target = Path(target).resolve()
        directory = target.parent
    except OSError:                                  # pragma: no cover - 极端路径异常
        return []

    pending = [p for p in sorted(directory.glob("libsomeip*.so*")) if p.resolve() != target]
    done: list[Path] = []
    while pending:
        progressed = False
        for lib in list(pending):
            try:
                ctypes.CDLL(str(lib), mode=ctypes.RTLD_GLOBAL)
            except OSError:
                continue                             # 依赖尚未就绪 → 下一轮重试
            pending.remove(lib)
            done.append(lib)
            progressed = True
        if not progressed:                           # 全部剩余候选都加载不了
            break
    return done


def _search_dirs() -> list[Path]:
    """按优先级列出搜索目录（不存在的会被过滤掉）。"""
    dirs: list[Path] = []
    for env in _ENV_DIR:
        v = os.environ.get(env)
        if v:
            dirs.append(Path(v))
    tp = paths.thirdparty_dir / "arhud_someip"          # 首选：第三方统一收纳目录
    dirs += [
        tp / paths.platform_arch_dir_name,             # thirdparty/arhud_someip/<平台>-<架构>/（推荐）
        tp / paths.platform_dir_name,                  # thirdparty/arhud_someip/<平台>/
        tp,                                            # thirdparty/arhud_someip/
        paths.drivers_dir / "someip",                  # drivers/<平台>/someip/（旧位置，兼容）
        paths.project_root,
    ]
    return [d for d in dirs if d]


def find_someip_library() -> Optional[Path]:
    """返回可用的库文件路径；找不到返回 None。"""
    # 1) 环境变量直接指定文件
    for env in _ENV_FILE:
        v = os.environ.get(env)
        if v:
            p = Path(v).expanduser()
            if p.is_file():
                return p
    # 2) 目录搜索
    for d in _search_dirs():
        if not d.is_dir():
            continue
        for name in LIB_CANDIDATES:
            p = d / name
            if p.is_file():
                return p
    return None


def load_someip_library(path: Optional[Path | str] = None):
    """加载 SOME/IP 服务端库并返回句柄；未找到时返回 None（不抛异常）。

    :param path: 显式指定库文件（覆盖自动探测）
    """
    key = str(path) if path else "<auto>"
    if key in _CACHE:
        return _CACHE[key]

    target = Path(path) if path else find_someip_library()
    if target is None or not Path(target).is_file():
        _CACHE[key] = None
        return None

    try:
        if IS_WINDOWS:
            handle = ctypes.WinDLL(str(target))
        else:
            # 先用绝对路径 RTLD_GLOBAL 预加载同目录 libsomeip*.so：
            # 免去手工设置 LD_LIBRARY_PATH（插件式 dlopen 按文件名加载它们）
            if str(target.resolve().parent) not in _PRELOADED_DIRS:
                preload_sibling_libraries(target)
                _PRELOADED_DIRS.add(str(target.resolve().parent))
            handle = ctypes.CDLL(str(target))
    except OSError as exc:                      # 依赖缺失 / 架构不符
        print(f"[SOME/IP] 库加载失败：{target}\n         {exc}\n"
              f"         提示：Linux 需把 libsomeip*.so 与 libarhud_server.so 放在同一目录"
              f"（同目录依赖会被自动预加载）；也可手工设置 LD_LIBRARY_PATH；"
              f"Windows 需提供 libarhud_server.dll")
        _CACHE[key] = None
        return None

    _CACHE[key] = handle
    return handle


def is_library_available() -> bool:
    """库是否已就绪（可加载）。"""
    return load_someip_library() is not None


def describe_library_status() -> str:
    """人类可读的库状态描述（用于界面状态栏/自检输出）。"""
    lib = find_someip_library()
    if lib is None:
        return _not_found_hint()
    handle = load_someip_library()
    if handle is None:
        return f"SOME/IP 库已找到但加载失败：{lib}"
    return f"SOME/IP 库就绪：{lib}"


def _not_found_hint() -> str:
    """找不到库时的中文修复提示（区分平台，Windows 说明暂无产物）。"""
    names = " / ".join(LIB_CANDIDATES)
    where = "thirdparty/arhud_someip/windows/" if IS_WINDOWS else "thirdparty/arhud_someip/linux/"
    lines = [f"未找到 SOME/IP 服务端库（{names}）"]
    if IS_WINDOWS:
        lines += [
            f"  1) 把 libarhud_server.dll 放到 {where}（或设置 HUD_SOMEIP_LIB=<完整路径>）；"
            f"旧位置 drivers/someip/windows/ 仍兼容",
            "  2) 当前仓库**暂无 Windows DLL 产物**：需用 MSVC 编译 arhud_python_server",
            "     （编译方式见 docs/SOMEIP_REPLAY.md「Windows 支持」一节）",
            "  3) 临时替代：在 Ubuntu 上运行本功能，或用 WSL/容器承载 SOME/IP 回放",
        ]
    else:
        lines += [
            f"  1) 把 libarhud_server.so 与 libsomeip*.so 放到 {where}"
            f"（或设置 HUD_SOMEIP_LIB=<完整路径>）；旧位置 drivers/someip/linux/ 仍兼容",
            "  2) 同目录的 libsomeip*.so 会被自动预加载，一般无需设置 LD_LIBRARY_PATH；",
            "     若仍报 `Configuration module could not be loaded!`，"
            "可导出 LD_LIBRARY_PATH 指向该目录后重试",
            "  3) 就地编译：arhud_python_server/src 下 `make libarhud_server.so`",
        ]
    return "\n".join(lines)


def platforms_note() -> str:
    """在界面上展示的简短说明（当前平台库是否具备）。"""
    if IS_WINDOWS and find_someip_library() is None:
        return "Windows 暂缺 libarhud_server.dll（留占位，稍后补上）"
    if sys.platform.startswith("linux") and find_someip_library() is None:
        return "未发现 libarhud_server.so（请按提示放置或编译）"
    return describe_library_status()
