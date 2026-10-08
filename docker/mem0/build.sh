#!/usr/bin/env bash
# =============================================================
# 构建 mem0 的 API 与 Dashboard 镜像（Linux 端）
#
# 参数与 build.ps1 一一对应：
#   --component all|api|dashboard   （可逗号分隔，默认 all）
#   --source-root <path>            （mem0 源码 checkout 根目录）
#   --tag <tag>                     （缺省取 registry.env 的 IMAGE_TAG）
#   --force / --no-cache
#
# 用法：
#   ./build.sh --source-root /opt/mem0
#   ./build.sh --component api --force
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_ROOT="$(dirname "$SCRIPT_DIR")"
REGISTRY_ENV="$DOCKER_ROOT/registry.env"

COMPONENT="all"
SOURCE_ROOT="${SRC_MEM0:-/opt/mem0}"
TAG=""
FORCE=0
NO_CACHE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --component)    COMPONENT="$2"; shift 2 ;;
        --source-root)  SOURCE_ROOT="$2"; shift 2 ;;
        --tag)          TAG="$2"; shift 2 ;;
        --force)        FORCE=1; shift ;;
        --no-cache)     NO_CACHE=1; shift ;;
        -h|--help)      sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

if [[ ! -f "$REGISTRY_ENV" ]]; then
    echo "[ERROR] 找不到 $REGISTRY_ENV" >&2
    exit 1
fi

get_var() { sed -n -E "s/^$1=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'; }

REGISTRY="$(get_var REGISTRY)"
[[ -z "$TAG" ]] && TAG="$(get_var IMAGE_TAG)"

if [[ -z "$REGISTRY" || -z "$TAG" ]]; then
    echo "[ERROR] registry.env 缺少 REGISTRY / IMAGE_TAG" >&2
    exit 1
fi

build_target() {
    local name="$1" image="$2" context="$3" dockerfile="$4"
    local remote="$REGISTRY/$image:$TAG"
    local local_tag="$image:local"

    if [[ ! -d "$context" ]]; then
        echo "[ERROR] 源码目录不存在: $context"
        echo "        请确认 mem0 源码已 clone，或用 --source-root 指定路径。"
        return 1
    fi

    if [[ "$FORCE" -eq 0 ]] && [[ -n "$(docker images -q "$remote" 2>/dev/null)" ]]; then
        echo "[SKIP] $remote 已存在"
        return 0
    fi

    echo "[BUILD] $image  <-  $context"
    local -a args=(build -f "$dockerfile" -t "$remote" -t "$local_tag")
    [[ "$NO_CACHE" -eq 1 ]] && args+=(--no-cache)
    args+=(--progress=plain "$context")

    if docker "${args[@]}"; then
        echo "[ OK ] $remote"
        return 0
    else
        echo "[FAIL] $image 构建失败"
        return 1
    fi
}

echo ""
echo "========================================"
echo "  mem0 构建  tag=$TAG"
echo "  源码：$SOURCE_ROOT"
echo "========================================"
echo ""

failed=0
IFS=',' read -ra comps <<< "$COMPONENT"

for comp in "${comps[@]}"; do
    case "$comp" in
        all)
            build_target api mem0-api "$SOURCE_ROOT/server" "$SCRIPT_DIR/api/Dockerfile" || failed=1
            build_target dashboard mem0-dashboard "$SOURCE_ROOT/server/dashboard" "$SCRIPT_DIR/dashboard/Dockerfile" || failed=1
            ;;
        api)       build_target api mem0-api "$SOURCE_ROOT/server" "$SCRIPT_DIR/api/Dockerfile" || failed=1 ;;
        dashboard) build_target dashboard mem0-dashboard "$SOURCE_ROOT/server/dashboard" "$SCRIPT_DIR/dashboard/Dockerfile" || failed=1 ;;
        *)         echo "[WARN] 未知组件: $comp" ;;
    esac
done

echo ""
if [[ "$failed" -ne 0 ]]; then
    echo "mem0 构建存在失败项" >&2
    exit 1
fi
echo "mem0 构建完成。下一步：./push.sh"
