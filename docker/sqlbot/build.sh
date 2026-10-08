#!/usr/bin/env bash
# =============================================================
# 构建 SQLBot 镜像（Linux 端）
#
#   ./build.sh --source-root /opt/SQLBot [--secret-key <key>] [--tag 1.0.0] [--force] [--no-cache]
#
# 未传 --secret-key 时读取本目录 .env 的 SECRET_KEY；两者都没有则报错，
# 避免产出"能跑但登不上"的镜像。
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ENV="$(dirname "$SCRIPT_DIR")/registry.env"

SOURCE_ROOT="${SQLBOT_SRC:-/opt/SQLBot}"
SECRET_KEY=""
TAG=""
FORCE=0
NO_CACHE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source-root) SOURCE_ROOT="$2"; shift 2 ;;
        --secret-key)  SECRET_KEY="$2"; shift 2 ;;
        --tag)         TAG="$2"; shift 2 ;;
        --force)       FORCE=1; shift ;;
        --no-cache)    NO_CACHE=1; shift ;;
        -h|--help)     sed -n '2,10p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

[[ -f "$REGISTRY_ENV" ]] || { echo "[ERROR] 找不到 $REGISTRY_ENV" >&2; exit 1; }
get_var() { sed -n -E "s/^$1=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'; }

REGISTRY="$(get_var REGISTRY)"
[[ -z "$TAG" ]] && TAG="$(get_var IMAGE_TAG)"

if [[ -z "$SECRET_KEY" && -f "$SCRIPT_DIR/.env" ]]; then
    SECRET_KEY="$(sed -n -E 's/^SECRET_KEY=(.*)$/\1/p' "$SCRIPT_DIR/.env" | tail -n 1 | tr -d '\r')"
fi

if [[ -z "$SECRET_KEY" || "$SECRET_KEY" == "CHANGE_ME_RANDOM_STRING" ]]; then
    echo "[ERROR] 缺少 secret-key。" >&2
    echo "        前端会把密钥内联进构建产物，必须与运行期 SECRET_KEY 一致。" >&2
    echo "        用法：./build.sh --secret-key <密钥>  或在 .env 中配置 SECRET_KEY" >&2
    exit 1
fi

if [[ ! -d "$SOURCE_ROOT" ]]; then
    echo "[ERROR] 源码目录不存在: $SOURCE_ROOT" >&2
    exit 1
fi

REMOTE="$REGISTRY/sqlbot:$TAG"
LOCAL="sqlbot:local"

if [[ "$FORCE" -eq 0 ]] && [[ -n "$(docker images -q "$REMOTE" 2>/dev/null)" ]]; then
    echo "[SKIP] $REMOTE 已存在（重建加 --force）"
    exit 0
fi

echo ""
echo "========================================"
echo "  SQLBot 构建  tag=$TAG"
echo "  源码：$SOURCE_ROOT"
echo "========================================"
echo ""

args=(
    build
    -f "$SCRIPT_DIR/Dockerfile"
    --build-arg "SQLBOT_SECRET_KEY=$SECRET_KEY"
    -t "$REMOTE"
    -t "$LOCAL"
)
[[ "$NO_CACHE" -eq 1 ]] && args+=(--no-cache)
args+=(--progress=plain "$SOURCE_ROOT")

if docker "${args[@]}"; then
    echo "[ OK ] $REMOTE"
    echo "下一步：./push.sh"
else
    echo "[FAIL] SQLBot 构建失败" >&2
    exit 1
fi
