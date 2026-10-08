#!/usr/bin/env bash
# =============================================================
# 构建 Gander 镜像（Linux 端）
#
#   ./build.sh [--variant local|remote|all] [--source-root /opt/Omni-Interaction-Agent]
#              [--torch-index-url <url>] [--tag 1.0.0] [--force] [--no-cache]
#
# 构建上下文为源码仓库根，脚本会把 Dockerfile 同级资产暂存到源码根的 .docker-build/。
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ENV="$(dirname "$SCRIPT_DIR")/registry.env"

VARIANT="local"
SOURCE_ROOT="${GANDER_SRC:-/opt/Omni-Interaction-Agent}"
TORCH_INDEX_URL="https://mirrors.aliyun.com/pytorch-wheels/cu124"
TAG=""
FORCE=0
NO_CACHE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --variant)          VARIANT="$2"; shift 2 ;;
        --source-root)      SOURCE_ROOT="$2"; shift 2 ;;
        --torch-index-url)  TORCH_INDEX_URL="$2"; shift 2 ;;
        --tag)              TAG="$2"; shift 2 ;;
        --force)            FORCE=1; shift ;;
        --no-cache)         NO_CACHE=1; shift ;;
        -h|--help)          sed -n '2,11p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

[[ -f "$REGISTRY_ENV" ]] || { echo "[ERROR] 找不到 $REGISTRY_ENV" >&2; exit 1; }
get_var() { sed -n -E "s/^$1=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'; }

REGISTRY="$(get_var REGISTRY)"
[[ -z "$TAG" ]] && TAG="$(get_var IMAGE_TAG)"

[[ -d "$SOURCE_ROOT" ]] || { echo "[ERROR] 源码目录不存在: $SOURCE_ROOT" >&2; exit 1; }
for sub in minicpm_ft gander_runtime; do
    [[ -d "$SOURCE_ROOT/$sub" ]] || { echo "[ERROR] 源码目录缺少子目录: $sub" >&2; exit 1; }
done

STAGING="$SOURCE_ROOT/.docker-build"
echo "[PREP] 暂存构建资产 → $STAGING"
rm -rf "$STAGING"
mkdir -p "$STAGING/nginx"
cp "$SCRIPT_DIR/nginx/default.conf.tmpl" "$STAGING/nginx/"
cp "$SCRIPT_DIR/entrypoint_local.sh" "$STAGING/"

build_target() {
    local name="$1" image="$2" dockerfile="$3"
    local remote="$REGISTRY/$image:$TAG"
    local local_tag="$image:local"

    if [[ "$FORCE" -eq 0 ]] && [[ -n "$(docker images -q "$remote" 2>/dev/null)" ]]; then
        echo "[SKIP] $remote 已存在"
        return 0
    fi

    echo "[BUILD] $image（torch 从国内索引安装，首次较慢）"
    local -a args=(build -f "$dockerfile" --build-arg "TORCH_INDEX_URL=$TORCH_INDEX_URL" -t "$remote" -t "$local_tag")
    [[ "$NO_CACHE" -eq 1 ]] && args+=(--no-cache)
    args+=(--progress=plain "$SOURCE_ROOT")

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
echo "  Gander 构建  tag=$TAG  variant=$VARIANT"
echo "  源码：$SOURCE_ROOT"
echo "========================================"
echo ""

failed=0
case "$VARIANT" in
    all)
        build_target local gander-asr "$SCRIPT_DIR/Dockerfile.local" || failed=1
        build_target remote gander-thinker "$SCRIPT_DIR/Dockerfile.remote" || failed=1
        ;;
    local)  build_target local gander-asr "$SCRIPT_DIR/Dockerfile.local" || failed=1 ;;
    remote) build_target remote gander-thinker "$SCRIPT_DIR/Dockerfile.remote" || failed=1 ;;
    *)      echo "[ERROR] 未知 variant: $VARIANT" >&2; exit 1 ;;
esac

echo ""
[[ "$failed" -ne 0 ]] && { echo "构建存在失败项" >&2; exit 1; }
echo "Gander 构建完成。下一步：./push.sh --variant $VARIANT"
