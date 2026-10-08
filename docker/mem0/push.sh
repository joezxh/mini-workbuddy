#!/usr/bin/env bash
# =============================================================
# 推送 mem0 镜像到阿里云 ACR（Linux 端）
#
#   ./push.sh [--tag v1.0.0] [--dry-run]
#
# 只做 tag + push，凭据依赖宿主机 docker login，脚本不接受密码。
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
        -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
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

failed=0
for img in mem0-api mem0-dashboard; do
    remote="$REGISTRY/$img:$TAG"
    local_tag="$img:local"

    if [[ -z "$(docker images -q "$remote" 2>/dev/null)" ]]; then
        if [[ -n "$(docker images -q "$local_tag" 2>/dev/null)" ]]; then
            echo "[TAG ] $local_tag -> $remote"
            [[ "$DRY_RUN" -eq 0 ]] && docker tag "$local_tag" "$remote"
        else
            echo "[FAIL] 本地既无 $remote 也无 $local_tag，请先 build"
            failed=1
            continue
        fi
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
echo "mem0 镜像推送完成。"
