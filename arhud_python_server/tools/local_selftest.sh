#!/usr/bin/env bash
# local_selftest.sh —— 本机（macOS/Linux，无需协议栈）自测：解析/重组/回放引擎/Python 层
# ==============================================================================
# 覆盖内容：
#   1. 编译 pcap_selftest（纯 C++ 解析器）与 replay_selftest（回放引擎 + C 接口）
#   2. 编译"演练版" libarhud_server（tools/dryrun_server.cpp，不联网）
#   3. 合成 pcap 边界用例（大端/纳秒/VLAN/SLL/SD/TCP/pcapng/未知 linktype）
#   4. 用 pcap_selftest 与 tools/analyze_pcap.py（纯 Python 独立实现）交叉比对条数
#   5. 回放引擎自测（按抓包节奏 + 事件覆盖率）
#   6. 用 python/demo_replay.py 跑目录回放，核对 report 里的总数
#
# 用法： tools/local_selftest.sh [pcap目录...]
#        不给参数时用 PCAPS_DIR 环境变量；都没有就只做编译自检。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${OUT:-/tmp/arhud_selftest}"
mkdir -p "$OUT"

DIRS=("$@")
if [ ${#DIRS[@]} -eq 0 ] && [ -n "${PCAPS_DIR:-}" ]; then DIRS=("$PCAPS_DIR"); fi

echo "== ① 编译：pcap_selftest / replay_selftest（纯数据层，不需协议栈）"
CXX="${CXX:-g++}"
$CXX -std=c++14 -O2 -Wall -Wextra -I src src/arhud_pcap.cpp tools/pcap_selftest.cpp -o "$OUT/pcap_selftest"
$CXX -std=c++14 -O2 -Wall -Wextra -I src src/arhud_pcap.cpp src/arhud_replay.cpp tools/replay_selftest.cpp -o "$OUT/replay_selftest"
echo "   OK → $OUT/pcap_selftest , $OUT/replay_selftest"

echo "== ② 编译：演练版 libarhud_server（不联网，供 Python 层验证）"
SHARED_FLAG="-shared"; [ "$(uname -s)" = "Darwin" ] && SHARED_FLAG="-dynamiclib"
$CXX -std=c++14 -O2 -Wall -I src src/arhud_pcap.cpp src/arhud_replay.cpp src/arhud_types.cpp \
     tools/dryrun_server.cpp $SHARED_FLAG -fPIC -o "$OUT/libarhud_server.so" -lz
echo "   OK → $OUT/libarhud_server.so"

echo "== ③ 解析器边界用例（大端/纳秒/VLAN/SLL/SD/TCP/pcapng/未知 linktype）"
python3 tools/pcap_edge_cases.py "$OUT/pcap_selftest" || exit 1

if [ ${#DIRS[@]} -eq 0 ]; then
  echo "== 没给 pcap 目录，跳过回放自测（可加参数：tools/local_selftest.sh /path/to/pcap_dir）"
  exit 0
fi

PCAPS=()
for d in "${DIRS[@]}"; do
  while IFS= read -r f; do PCAPS+=("$f"); done < <(find "$d" -maxdepth 1 -name '*.pcap' | sort)
done
echo "== ④ 交叉比对：C++ 解析器 vs 纯 Python 独立实现（共 ${#PCAPS[@]} 个 pcap）"
for f in "${PCAPS[@]}"; do
  cpp=$("$OUT/pcap_selftest" "$f" | tr '\n' ' ' | sed -E 's/.*包=([0-9]+)  SOME\/IP=([0-9]+).*通知=([0-9]+)  TP分片=[0-9]+  TP消息=([0-9]+).*消息=([0-9]+)  时间跨度=([0-9.]+) 秒.*/包=\1 SOME\/IP=\2 通知=\3 TP消息=\4 合计=\5 时长=\6s/')
  py=$(python3 tools/analyze_pcap.py --quiet "$f" | tail -1 | sed -E 's/^[^ ]+ +//')
  echo "   $(basename "$f")"
  echo "     C++ : $cpp"
  echo "     Py  : $py"
done

echo "== ⑤ 回放引擎自测（按抓包节奏 + 覆盖率检查）"
"$OUT/replay_selftest" "${PCAPS[@]}" --profile old-capture --speed 50 --loops 1 | grep -E "^==|parsed=|覆盖率|不在表里|合计"

echo "== ⑥ Python 层 + 演练库：目录整体回放"
ARHUD_LIB_PATH="$OUT/libarhud_server.so" python3 python/demo_replay.py "${DIRS[0]}" \
  --once --profile auto --timing capture --speed 100 --report-json "$OUT/report.json" \
  | grep -E "^\[demo\]|^\[报告\]|^\[体检\]"
python3 - "$OUT/report.json" <<'EOF'
import json, sys
r = json.load(open(sys.argv[1]))
assert r["parsed"] == r["sent"] + r["failed"], "parsed != sent + failed"
assert r["unregistered"] == 0, "还有事件不在服务表里（profile 选错？）"
print("== 自测通过：%d 条全部发布成功，覆盖 %d 个事件" % (r["parsed"], len(r["events"])))
EOF
