#!/usr/bin/env bash
# build_package.sh —— 一键组装 arhud_python_server 自包含部署包
# =========================================================================
# 产物：out/arhud-python-server/ 目录，可直接拷贝到部署机：
#   libarhud_server.so      C++ 服务端库（SP 版，按目标架构编译）
#   libs/                   SP 分支库（arm64 已内置；x86_64 从工程 zip 提取）
#   python/                 ctypes 封装 + 示例 + 业务脚本
#   config/                 配置模板（可选）
#   data/                   回放 pcap（可选，-p 指定）
# 用法：
#   ./build_package.sh                    # 默认 aarch64，从仓库内置 libs/arm64
#   ./build_package.sh --arch x86_64      # x86_64（自动从 to_longjie_demo_20250625.zip 提取 SP 库）
#   ./build_package.sh --arch x86_64 --pcap out.pcap --out /opt/arhud-server
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
ZIP="$ROOT/to_longjie_demo_20250625.zip"
ARCH="aarch64"
OUT="$HERE/out/arhud-python-server"
PCAP=""

while [ $# -gt 0 ]; do
    case "$1" in
        --arch) ARCH="$2"; shift 2 ;;
        --pcap) PCAP="$2"; shift 2 ;;
        --out)  OUT="$2"; shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

echo "=== 组装部署包: $OUT (arch=$ARCH) ==="
rm -rf "$OUT"
mkdir -p "$OUT/libs" "$OUT/python" "$OUT/config" "$OUT/data"

# 1) SP 分支库
if [ "$ARCH" = "x86_64" ]; then
    if [ -d "$HERE/libs/x86_64" ] && [ -f "$HERE/libs/x86_64/libsomeip.so" ]; then
        cp "$HERE"/libs/x86_64/*.so "$OUT/libs/"
    else
        [ -f "$ZIP" ] || { echo "缺少 $ZIP，无法提取 x86_64 SP 库"; exit 1; }
        TMPX="$(mktemp -d)"
        unzip -o -q "$ZIP" -d "$TMPX" 'to_longjie_demo_20250625/libs/lib_x86/*' 2>/dev/null \
            || unzip -o -q "$ZIP" -d "$TMPX" '*/lib_x86/*' 2>/dev/null
        LIBS="$(find "$TMPX" -type d -name lib_x86 | head -1)"
        [ -n "$LIBS" ] || { echo "zip 中未找到 x86_64 SP 库"; exit 1; }
        cp "$LIBS"/*.so "$OUT/libs/"
    fi
else
    cp "$HERE"/libs/arm64/*.so "$OUT/libs/"
fi

# 2) 编译 C++ 服务端库
BUILD="$(mktemp -d)"
cp -r "$HERE/src/"* "$BUILD/"
if [ "$ARCH" = "x86_64" ]; then
    (cd "$BUILD" && make libarhud_server.so ARCH=x86_64 SP_LIBS="$OUT/libs")
else
    (cd "$BUILD" && make libarhud_server.so SP_LIBS="$OUT/libs")
fi
cp "$BUILD/libarhud_server.so" "$OUT/python/"
cp "$BUILD/libarhud_server.so" "$OUT/"
rm -rf "$BUILD"

# 3) Python 封装与示例
cp "$HERE"/python/*.py "$OUT/python/"

# 4) 配置模板（SP 分支格式，unicast 占位）
if [ -f "$HERE/config/someip_arhud01_pcap_server.json" ]; then
    cp "$HERE/config/someip_arhud01_pcap_server.json" "$OUT/config/"
fi

# 5) 回放 pcap（可选）
if [ -n "$PCAP" ] && [ -f "$PCAP" ]; then
    cp "$PCAP" "$OUT/data/out.pcap"
fi

# 6) 文档
cp "$HERE/README.md" "$HERE/DEPLOYMENT.md" "$OUT/" 2>/dev/null || true

echo "=== 部署包就绪 ==="
find "$OUT" -maxdepth 2 -type f | sed "s|$OUT/||" | sort
echo
echo "部署到目标机后："
echo "  cd $OUT"
echo "  LD_LIBRARY_PATH=$OUT/libs python3 python/demo_replay.py data/out.pcap <本机IP>"
