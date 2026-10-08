#!/usr/bin/env bash
# =============================================================
# 把已构建的镜像导出为离线 tar 包到 dist/ 目录（Linux 端）
#
#   ./save-all.sh [--tag 1.0.0] [--out-dir ./dist]
#
# 本地不存在的镜像自动跳过，不会因漏构建某个组件而中断。
# =============================================================
set -uo pipefail

DOCKER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ENV="$DOCKER_ROOT/registry.env"

TAG=""
OUT_DIR="$DOCKER_ROOT/dist"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag)     TAG="$2"; shift 2 ;;
        --out-dir) OUT_DIR="$2"; shift 2 ;;
        -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

[[ -f "$REGISTRY_ENV" ]] || { echo "[ERROR] 找不到 $REGISTRY_ENV" >&2; exit 1; }
get_var() { sed -n -E "s/^$1=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'; }

REGISTRY="$(get_var REGISTRY)"
[[ -z "$TAG" ]] && TAG="$(get_var IMAGE_TAG)"

images=(
    mem0-api
    mem0-dashboard
    mwb-nginx-gateway
    sqlbot
    pp-ocrv6
    pp-structurev3
    s2s-pipeline
    gander-asr
    gander-thinker
)

mkdir -p "$OUT_DIR"

echo ""
echo "=================================================="
echo "  导出离线镜像包 → $OUT_DIR"
echo "=================================================="

saved=0; missed=0
for img in "${images[@]}"; do
    full="$REGISTRY/$img:$TAG"
    if [[ -z "$(docker images -q "$full" 2>/dev/null)" ]]; then
        echo "[MISS] $full（未构建，跳过）"
        missed=$((missed + 1))
        continue
    fi
    tar="$OUT_DIR/$img-$TAG.tar"
    echo "[SAVE] $full"
    if docker save "$full" -o "$tar"; then
        size=$(du -m "$tar" | cut -f1)
        echo "       → $tar (${size} MB)"
        saved=$((saved + 1))
    else
        echo "[FAIL] 导出失败：$full" >&2
    fi
done

echo ""
echo "导出完成：成功 $saved / 缺失 $missed"
