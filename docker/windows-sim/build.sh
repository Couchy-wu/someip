#!/usr/bin/env bash
# =====================================================================
# build.sh —— 构建 Windows 环境验证镜像
# =====================================================================
# 用法：
#   ./build.sh                  # 默认标签 hudautotest-win:py313
#   ./build.sh --no-cache       # 强制重建（Wine/CPython 安装失败时用）
#   PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple ./build.sh
#
# 说明：宿主为 Apple Silicon 时镜像以 linux/amd64 构建（Rosetta 加速），
#       容器内 Wine 直接运行 Windows x64 的 CPython，无需嵌套模拟。
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-hudautotest-win:py313}"
PY_VER="${PY_VER:-3.13.7}"
PIP_INDEX="${PIP_INDEX:-https://mirrors.aliyun.com/pypi/simple/}"
APT_MIRROR="${APT_MIRROR:-http://mirrors.aliyun.com/ubuntu}"
WITH_MINGW="${WITH_MINGW:-0}"
PLATFORM="${PLATFORM:-linux/amd64}"

echo "== 构建 ${IMAGE}（平台 ${PLATFORM}，Windows CPython ${PY_VER}）=="
docker build \
    --platform "${PLATFORM}" \
    --build-arg "PY_VER=${PY_VER}" \
    --build-arg "PIP_INDEX=${PIP_INDEX}" \
    --build-arg "APT_MIRROR=${APT_MIRROR}" \
    --build-arg "WITH_MINGW=${WITH_MINGW}" \
    -f Dockerfile \
    -t "${IMAGE}" \
    "$@" \
    .

echo
echo "== 构建完成 =="
docker image inspect "${IMAGE}" --format '镜像: {{.RepoTags}} 架构: {{.Architecture}} 大小: {{.Size}}'
echo "下一步：  ./run_verify.sh        # 挂载项目并运行验证套件"
