#!/usr/bin/env bash
# =====================================================================
# run_verify.sh —— 在 Windows 验证容器中执行检查
# =====================================================================
# 用法：
#   ./run_verify.sh                 # 完整功能验证套件（默认）
#   ./run_verify.sh check           # 项目环境自检 tools/check_env.py
#   ./run_verify.sh selftest        # hudcore 回归自测
#   ./run_verify.sh gui             # 启动 main.py 验证窗口创建
#   ./run_verify.sh py -m pip list  # 用 Windows Python 执行任意命令
#   ./run_verify.sh script tools/check_imports.py
#   ./run_verify.sh shell           # 进入容器交互
#
# 环境变量：
#   IMAGE=...        镜像名（默认 hudautotest-win:py313）
#   PROJECT=...      项目根目录（默认本脚本的上两级目录）
# =====================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="${PROJECT:-$(cd "${HERE}/../.." && pwd)}"
IMAGE="${IMAGE:-hudautotest-win:py313}"

if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
    echo "[错误] 镜像 ${IMAGE} 不存在，请先执行 ./build.sh" >&2
    exit 2
fi

echo "== 镜像: ${IMAGE} =="
echo "== 项目: ${PROJECT} → 容器 /work（Wine: Z:\\work）=="

# 仅在交互终端下附加 -it（CI / 后台执行时没有 TTY，加了会报错）
TTY_FLAG=""
if [ -t 0 ] && [ -t 1 ]; then TTY_FLAG="-it"; fi

# 入口脚本用仓库里的版本覆盖镜像内的副本：这样改 entrypoint.sh（虚拟显示参数、桩库准备等）
# 立即生效，不必重建镜像（Xvfb 的 MIT-SHM 开关就是这么修的）。
exec docker run --rm ${TTY_FLAG} \
    --platform linux/amd64 \
    -v "${PROJECT}:/work" \
    -v "${HERE}/entrypoint.sh:/usr/local/bin/entrypoint.sh:ro" \
    -w /work \
    "${IMAGE}" "$@"
