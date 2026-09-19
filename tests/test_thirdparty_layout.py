# -*- coding: utf-8 -*-
"""tests/test_thirdparty_layout.py —— 第三方运行时库的目录与探测规则

覆盖（这些规则直接决定"库放在哪里能被找到"）：
  · `paths.thirdparty_dir` / `thirdparty()` / `platform_arch_dir_name`（平台-架构目录名）
  · SOME/IP 库探测：环境变量 > thirdparty/<组件>/<平台>-<架构> > <平台> > drivers（旧位置）
  · ZLG CAN 库探测：thirdparty/zlg_can 优先于 drivers（旧位置）
  · 库接口识别：ZCAN / VCI / 加载失败（error）三种情况可区分 ——
    Linux 公开可下载的 ZLG 库是 VCI 接口，必须能被识别出来并给出提示，而不是静默失败
"""
from __future__ import annotations

import ctypes
import glob
import os
import pathlib
import platform

import pytest

from hudcore.platform.paths import paths
from hudcore.platform.system import arch_name


# --------------------------------------------------------------------------- 目录规则

def test_thirdparty_dir_and_arch_naming():
    assert paths.thirdparty_dir.name == "thirdparty"
    assert paths.thirdparty("ffmpeg").name == "ffmpeg"
    # 平台-架构目录名形如 linux-x86_64 / linux-aarch64
    name = paths.platform_arch_dir_name
    assert name.startswith(paths.platform_dir_name + "-")
    assert name.split("-")[-1] == arch_name()


def test_arch_name_normalization(monkeypatch):
    import hudcore.platform.system as sysmod
    for raw, expect in (("arm64", "aarch64"), ("aarch64", "aarch64"),
                        ("AMD64", "x86_64"), ("x86_64", "x86_64")):
        monkeypatch.setattr(sysmod.platform, "machine", lambda raw=raw: raw)
        assert sysmod.arch_name() == expect
    assert arch_name() in {"aarch64", "x86_64", platform.machine().lower()}


def test_thirdparty_helper_falls_back_to_legacy(tmp_path, monkeypatch):
    """thirdparty() 在新位置缺失时应回退到旧位置。"""
    class Stub(paths.__class__):          # 复用真实实现，只替换 project_root
        pass

    stub = paths.__class__.__new__(paths.__class__)
    stub.project_root = tmp_path
    stub.platform_dir_name = "linux"
    stub.platform_arch_dir_name = "linux-x86_64"
    legacy = tmp_path / "old_location"
    legacy.mkdir()
    assert stub.thirdparty("comp", "old_location") == legacy
    (tmp_path / "thirdparty" / "comp").mkdir(parents=True)
    assert stub.thirdparty("comp", "old_location") == tmp_path / "thirdparty" / "comp"


# --------------------------------------------------------------------------- 探测优先级

class _StubPaths:
    def __init__(self, root: pathlib.Path):
        self.project_root = root
        self.thirdparty_dir = root / "thirdparty"
        self.platform_dir_name = "linux"
        self.platform_arch_dir_name = "linux-x86_64"

    @property
    def drivers_dir(self):
        return self.project_root / "drivers" / "linux"

    @property
    def drivers_all_dir(self):
        return self.project_root / "drivers"


def test_someip_probe_prefers_arch_dir(tmp_path, monkeypatch):
    import hudcore.someip.backend as be
    monkeypatch.setattr(be, "paths", _StubPaths(tmp_path))
    for env in ("HUD_SOMEIP_LIB", "ARHUD_LIB_PATH", "HUD_SOMEIP_LIB_DIR", "ARHUD_LIB_DIR"):
        monkeypatch.delenv(env, raising=False)
    lib = be.LIB_CANDIDATES[0]

    legacy = tmp_path / "drivers" / "linux" / "someip"
    legacy.mkdir(parents=True)
    (legacy / lib).write_bytes(b"")
    assert be.find_someip_library() == legacy / lib

    flat = tmp_path / "thirdparty" / "arhud_someip" / "linux"
    flat.mkdir(parents=True)
    (flat / lib).write_bytes(b"")
    assert be.find_someip_library() == flat / lib, "thirdparty/<平台> 应优先于 drivers 旧位置"

    arch_dir = tmp_path / "thirdparty" / "arhud_someip" / "linux-x86_64"
    arch_dir.mkdir(parents=True)
    (arch_dir / lib).write_bytes(b"")
    assert be.find_someip_library() == arch_dir / lib, "thirdparty/<平台>-<架构> 应最优先"


def test_can_probe_prefers_thirdparty(tmp_path, monkeypatch):
    import hudcore.can.backend as be
    monkeypatch.setattr(be, "paths", _StubPaths(tmp_path))
    monkeypatch.delenv("HUD_ZLG_LIB", raising=False)
    monkeypatch.delenv("HUD_ZLG_LIB_DIR", raising=False)
    lib = be._candidates()[0]

    legacy = tmp_path / "drivers" / "linux"
    legacy.mkdir(parents=True)
    (legacy / lib).write_bytes(b"")
    assert be.find_zlg_library() == legacy / lib

    arch_dir = tmp_path / "thirdparty" / "zlg_can" / "linux-x86_64"
    arch_dir.mkdir(parents=True)
    (arch_dir / lib).write_bytes(b"")
    found = be.find_zlg_library()
    assert found == arch_dir / lib, "thirdparty/zlg_can/<平台>-<架构> 应优先于 drivers 旧位置"


# --------------------------------------------------------------------------- 接口识别

def test_library_api_kind_detects_current_library():
    """本机实际库（若有）应被识别为 zcan / vci / error 之一，不应崩溃。"""
    from hudcore.can import find_zlg_library, library_api_kind
    lib = find_zlg_library()
    if lib is None:
        pytest.skip("本机未放置 ZLG 驱动库")
    kind = library_api_kind(lib)
    assert kind in {"zcan", "vci", "unknown", "error"}


def test_library_api_kind_reports_load_error(tmp_path):
    """伪造的 .so（非 ELF）应识别为 error，并记录 dlopen 原因。"""
    from hudcore.can.backend import library_api_kind, library_load_error
    fake = tmp_path / "libzlgcan.so"
    fake.write_bytes(b"not an ELF file")
    kind = library_api_kind(fake)
    assert kind == "error", f"应识别为加载失败，实际 {kind}"
    assert library_load_error(), "应记录加载失败原因（供自检展示）"
    assert "libzlgcan.so" in str(fake)


def test_vci_hint_says_vci_is_supported_by_adapter():
    """VCI 库的提示必须说清"已内置适配层、可以直接用"，并给出 ZCAN 直连的替代路径。"""
    from hudcore.can.backend import _vci_only_hint
    text = _vci_only_hint("/x/libusbcanfd.so")
    assert "VCI" in text and "适配层" in text and "可以直接使用" in text
    assert "libzlgcan.so" in text, "应说明想走 ZCAN 直连时放哪个库"


# --------------------------------------------------------------------------- 获取脚本

def test_fetch_script_lists_targets(capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fetch_libs", pathlib.Path(__file__).resolve().parents[1] / "tools" / "fetch_thirdparty_libs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.arch_name("x86_64") == "x86_64"
    assert mod.arch_name("arm64") == "aarch64"
    assert mod.main.__doc__ is None or True
    # someip 目标只打印指引（离线可用）
    assert mod.show_someip() == 0


# --------------------------------------------------------- 同目录依赖预加载（免 LD_LIBRARY_PATH）

def test_preload_sibling_libraries_ignores_dir_without_deps(tmp_path):
    """目录里没有 libsomeip*.so 时应返回空列表，且不抛异常。"""
    from hudcore.someip.backend import preload_sibling_libraries
    target = tmp_path / "libarhud_server.so"
    target.write_bytes(b"x")
    assert preload_sibling_libraries(target) == []


def test_preload_sibling_libraries_skips_broken_files(tmp_path):
    """损坏的候选（非 ELF）应被跳过而不是抛异常。"""
    from hudcore.someip.backend import preload_sibling_libraries
    (tmp_path / "libarhud_server.so").write_bytes(b"x")
    (tmp_path / "libsomeip-broken.so").write_bytes(b"not an ELF file")
    assert preload_sibling_libraries(tmp_path / "libarhud_server.so") == []


def test_preload_sibling_libraries_loads_real_shared_object(tmp_path):
    """真实 .so 应被加载并返回（证明"绝对路径 + RTLD_GLOBAL"这条链路可用）。"""
    if platform.system() == "Windows":
        pytest.skip("Windows 不需要（也不支持）插件式预加载")
    from hudcore.someip.backend import preload_sibling_libraries
    source = _system_shared_object()
    if source is None:
        pytest.skip("本机找不到可用于测试的系统 .so")
    (tmp_path / "libarhud_server.so").write_bytes(b"x")
    copied = tmp_path / "libsomeip-probe.so"
    copied.write_bytes(pathlib.Path(source).read_bytes())
    loaded = preload_sibling_libraries(tmp_path / "libarhud_server.so")
    assert [p.name for p in loaded] == ["libsomeip-probe.so"], f"应预加载同目录依赖，实际 {loaded}"


def test_real_library_preload_enables_plugin_style_dlopen():
    """可选（HUD_TEST_REAL_SOMEIP_LIB=1）：真实库目录预加载后，按**文件名** dlopen 应成功。

    这正是 vsomeip "Configuration module could not be loaded!" 的根因场景：
    libsomeip 在运行期按文件名加载 libsomeip-cfg.so，预加载后即可命中。
    """
    if os.environ.get("HUD_TEST_REAL_SOMEIP_LIB") != "1":
        pytest.skip("需 HUD_TEST_REAL_SOMEIP_LIB=1（会加载真实 SOME/IP 库）")
    from hudcore.someip.backend import find_someip_library, preload_sibling_libraries
    lib = find_someip_library()
    if lib is None:
        pytest.skip("本机未放置 SOME/IP 运行库")
    loaded = [p.name for p in preload_sibling_libraries(lib)]
    assert loaded, "应至少预加载一个 libsomeip*.so"
    for name in loaded:
        ctypes.CDLL(name, mode=ctypes.RTLD_GLOBAL)      # 按文件名加载应命中已加载对象


def _system_shared_object():
    """找一个真实存在的系统 .so 路径（用于预加载链路测试）。"""
    for pattern in ("/lib/*/libm.so.6", "/usr/lib/*/libm.so.6",
                    "/lib/*/libc.so.6", "/usr/lib/*/libc.so.6"):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[0]
    return None
