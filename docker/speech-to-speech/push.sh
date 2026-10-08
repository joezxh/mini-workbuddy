#!/usr/bin/env bash
# =============================================================
# 推送 speech-to-speech 镜像到阿里云 ACR
#   ./push.sh [--tag 1.0.0] [--dry-run]
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ENV="$(dirname "$SCRIPT_DIR")/registry.env"

TAG=""
DRY_RUN=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag) TAG="$2"; shift 2 ;;
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

REMOTE="$REGISTRY/s2s-pipeline:$TAG"
if [[ -z "$(docker images -q "$REMOTE" 2>/dev/null)" ]]; then
    echo "[FAIL] 本地镜像不存在：$REMOTE，请先 build" >&2
    exit 1
fi

echo "[PUSH] $REMOTE（镜像约数 GB，首次推送较慢）"
if [[ "$DRY_RUN" -eq 0 ]]; then
    docker push "$REMOTE" || { echo "[FAIL] 推送失败" >&2; exit 1; }
fi
echo "[ OK ] $REMOTE"
