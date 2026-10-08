#!/usr/bin/env bash
# =============================================================
# 把 Dify 官方镜像中转进个人阿里云仓库
#
#   ./pull-mirror.sh [--force] [--dry-run]
#
# ../_common/prepull.sh 的快捷入口，幂等：已存在则跳过。
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREPULL="$(dirname "$SCRIPT_DIR")/_common/prepull.sh"

if [[ ! -f "$PREPULL" ]]; then
    echo "[ERROR] 找不到 $PREPULL" >&2
    exit 1
fi

echo "==> 中转 Dify 官方镜像到个人仓库（幂等，重跑只会补齐缺失项）"
exec "$PREPULL" "$@"
