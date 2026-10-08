#!/usr/bin/env bash
# =============================================================
# 构建统一网关镜像（mwb-nginx-gateway）
#
#   ./build.sh [--tag 1.0.0] [--force] [--no-cache]
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ENV="$(dirname "$SCRIPT_DIR")/registry.env"

TAG=""
FORCE=0
NO_CACHE=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag) TAG="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        --no-cache) NO_CACHE=1; shift ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

[[ -f "$REGISTRY_ENV" ]] || { echo "[ERROR] 找不到 $REGISTRY_ENV" >&2; exit 1; }
get_var() { sed -n -E "s/^$1=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'; }

REGISTRY="$(get_var REGISTRY)"
[[ -z "$TAG" ]] && TAG="$(get_var IMAGE_TAG)"

IMAGE="mwb-nginx-gateway"
REMOTE="$REGISTRY/$IMAGE:$TAG"
LOCAL="$IMAGE:local"

if [[ "$FORCE" -eq 0 ]] && [[ -n "$(docker images -q "$REMOTE" 2>/dev/null)" ]]; then
    echo "[SKIP] $REMOTE 已存在，重建请加 --force"
    exit 0
fi

echo "[BUILD] $REMOTE"
args=(build -t "$REMOTE" -t "$LOCAL")
[[ "$NO_CACHE" -eq 1 ]] && args+=(--no-cache)
args+=(--progress=plain "$SCRIPT_DIR")

if docker "${args[@]}"; then
    echo "[ OK ] $REMOTE"
    echo "下一步：./push.sh"
else
    echo "[FAIL] 网关镜像构建失败" >&2
    exit 1
fi
