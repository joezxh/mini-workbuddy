#!/usr/bin/env bash
# =============================================================
# 推送 Gander 镜像到阿里云 ACR
#   ./push.sh [--variant local|remote|all] [--tag 1.0.0] [--dry-run]
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ENV="$(dirname "$SCRIPT_DIR")/registry.env"

VARIANT="all"
TAG=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --variant) VARIANT="$2"; shift 2 ;;
        --tag)     TAG="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

[[ -f "$REGISTRY_ENV" ]] || { echo "[ERROR] 找不到 $REGISTRY_ENV" >&2; exit 1; }
get_var() { sed -n -E "s/^$1=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'; }

REGISTRY_HOST="$(get_var REGISTRY_HOST)"
REGISTRY="$(get_var REGISTRY)"
[[ -z "$TAG" ]] && TAG="$(get_var IMAGE_TAG)"

DOCKER_CONFIG_DIR="${DOCKER_CONFIG:-$HOME/.docker}"
if [[ ! -f "$DOCKER_CONFIG_DIR/config.json" ]] || ! grep -q "$REGISTRY_HOST" "$DOCKER_CONFIG_DIR/config.json"; then
    echo "[ERROR] 未登录 $REGISTRY_HOST ，请先执行：docker login $REGISTRY_HOST" >&2
    exit 1
fi

image_for() {
    case "$1" in
        local)  echo "gander-asr" ;;
        remote) echo "gander-thinker" ;;
        *)      echo "" ;;
    esac
}

names=("$VARIANT")
if [[ "$VARIANT" == "all" ]]; then names=(local remote); fi

failed=0
for name in "${names[@]}"; do
    img="$(image_for "$name")"
    [[ -z "$img" ]] && { echo "[WARN] 未知 variant: $name"; continue; }

    remote="$REGISTRY/$img:$TAG"
    if [[ -z "$(docker images -q "$remote" 2>/dev/null)" ]]; then
        echo "[SKIP] 本地无 $remote（未构建则跳过）"
        continue
    fi

    echo "[PUSH] $remote"
    [[ "$DRY_RUN" -eq 1 ]] && continue
    if docker push "$remote"; then
        echo "[ OK ] $remote"
    else
        failed=1
    fi
done

[[ "$failed" -ne 0 ]] && { echo "推送存在失败项" >&2; exit 1; }
echo "Gander 镜像推送完成。"
