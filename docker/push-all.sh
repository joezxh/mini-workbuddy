#!/usr/bin/env bash
# =============================================================
# 一键推送所有组件镜像到阿里云 ACR（Linux 端）
#
#   ./push-all.sh [--component mem0,sqlbot] [--tag 1.0.0] [--dry-run]
#
# 先校验 docker login 状态，未登录直接退出；凭据不落盘。
# =============================================================
set -uo pipefail

DOCKER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ENV="$DOCKER_ROOT/registry.env"

COMPONENT="all"
TAG=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --component) COMPONENT="$2"; shift 2 ;;
        --tag)       TAG="$2"; shift 2 ;;
        --dry-run)   DRY_RUN=1; shift ;;
        -h|--help)   sed -n '2,10p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

[[ -f "$REGISTRY_ENV" ]] || { echo "[ERROR] 找不到 $REGISTRY_ENV" >&2; exit 1; }
get_var() { sed -n -E "s/^$1=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'; }

REGISTRY_HOST="$(get_var REGISTRY_HOST)"
[[ -z "$TAG" ]] && TAG="$(get_var IMAGE_TAG)"

echo ""
echo "=================================================="
echo "  推送到 $REGISTRY_HOST（tag=$TAG）"
echo "=================================================="

DOCKER_CONFIG_DIR="${DOCKER_CONFIG:-$HOME/.docker}"
if [[ ! -f "$DOCKER_CONFIG_DIR/config.json" ]] || ! grep -q "$REGISTRY_HOST" "$DOCKER_CONFIG_DIR/config.json"; then
    echo "" >&2
    echo "[ERROR] 未检测到 $REGISTRY_HOST 的登录凭据。" >&2
    echo "        请先执行：docker login $REGISTRY_HOST" >&2
    exit 1
fi

map_dir() {
    case "$1" in
        mem0) echo "mem0" ;;
        nginx) echo "nginx" ;;
        sqlbot) echo "sqlbot" ;;
        paddleocr) echo "paddleOCR" ;;
        s2s) echo "speech-to-speech" ;;
        gander) echo "gander" ;;
        *) echo "" ;;
    esac
}

if [[ "$COMPONENT" == "all" ]]; then
    selected=(mem0 nginx sqlbot paddleocr s2s gander)
else
    IFS=',' read -ra selected <<< "$COMPONENT"
fi

declare -a results=()
failed=0

for name in "${selected[@]}"; do
    dir="$(map_dir "$name")"
    [[ -z "$dir" ]] && { echo "[WARN] 未知组件: $name"; continue; }

    script="$DOCKER_ROOT/$dir/push.sh"
    [[ ! -f "$script" ]] && { results+=("$name=SKIP"); continue; }

    echo ""
    echo ">>> [$name]"
    args=()
    [[ -n "$TAG" ]] && args+=(--tag "$TAG")
    [[ "$DRY_RUN" -eq 1 ]] && args+=(--dry-run)

    if bash "$script" "${args[@]}"; then
        results+=("$name=OK")
    else
        results+=("$name=FAIL")
        failed=1
    fi
done

echo ""
echo "=================================================="
echo "  推送结果汇总"
echo "=================================================="
for item in "${results[@]}"; do echo "  $item"; done

[[ "$failed" -ne 0 ]] && { echo "存在失败组件，详见上方日志。" >&2; exit 1; }
echo "全部推送完成。"
