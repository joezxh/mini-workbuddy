#!/usr/bin/env bash
# =============================================================
# 构建 PaddleOCR 的 OCR 服务镜像（Linux 端）
#
#   ./build.sh [--component ppocrv6|structurev3|all] [--source-root /opt/PaddleOCR]
#              [--paddle-version 3.3.0] [--tag 1.0.0] [--force] [--no-cache]
#
# wheels/ 缺 paddlepaddle wheel 时自动从华为云镜像源下载后离线安装。
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ENV="$(dirname "$SCRIPT_DIR")/registry.env"

COMPONENT="ppocrv6"
SOURCE_ROOT="${PADDLE_SRC:-/opt/PaddleOCR}"
PADDLE_VERSION="3.3.0"
TAG=""
FORCE=0
NO_CACHE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --component)      COMPONENT="$2"; shift 2 ;;
        --source-root)    SOURCE_ROOT="$2"; shift 2 ;;
        --paddle-version) PADDLE_VERSION="$2"; shift 2 ;;
        --tag)            TAG="$2"; shift 2 ;;
        --force)          FORCE=1; shift ;;
        --no-cache)       NO_CACHE=1; shift ;;
        -h|--help)        sed -n '2,11p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

[[ -f "$REGISTRY_ENV" ]] || { echo "[ERROR] 找不到 $REGISTRY_ENV" >&2; exit 1; }
get_var() { sed -n -E "s/^$1=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'; }

REGISTRY="$(get_var REGISTRY)"
[[ -z "$TAG" ]] && TAG="$(get_var IMAGE_TAG)"

[[ -d "$SOURCE_ROOT" ]] || { echo "[ERROR] 源码目录不存在: $SOURCE_ROOT" >&2; exit 1; }

WHEEL_DIR="$SCRIPT_DIR/wheels"
mkdir -p "$WHEEL_DIR"

if ! ls "$WHEEL_DIR"/paddlepaddle*.whl >/dev/null 2>&1; then
    echo "[PREP] 下载 paddlepaddle==$PADDLE_VERSION wheel 到 wheels/（华为云源）..."
    if ! pip download -i https://repo.huaweicloud.com/repository/pypi/simple --no-deps -d "$WHEEL_DIR" "paddlepaddle==$PADDLE_VERSION"; then
        echo "[ERROR] wheel 下载失败，可手动下载后放入 wheels/ 目录" >&2
        exit 1
    fi
else
    echo "[PREP] 复用已有 wheel: $(ls "$WHEEL_DIR"/paddlepaddle*.whl | head -n1 | xargs basename)"
fi

build_target() {
    local name="$1" image="$2" dockerfile="$3"
    local remote="$REGISTRY/$image:$TAG"
    local local_tag="$image:local"

    if [[ "$FORCE" -eq 0 ]] && [[ -n "$(docker images -q "$remote" 2>/dev/null)" ]]; then
        echo "[SKIP] $remote 已存在"
        return 0
    fi

    echo "[BUILD] $image（首次构建会下载 PP-OCRv6 权重，耗时较长）"
    local -a args=(build -f "$dockerfile" -t "$remote" -t "$local_tag")
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
echo "  PaddleOCR 构建  tag=$TAG"
echo "  源码：$SOURCE_ROOT"
echo "========================================"
echo ""

failed=0
IFS=',' read -ra comps <<< "$COMPONENT"
for comp in "${comps[@]}"; do
    case "$comp" in
        all)
            build_target ppocrv6 pp-ocrv6 "$SCRIPT_DIR/Dockerfile.ppocrv6" || failed=1
            build_target structurev3 pp-structurev3 "$SCRIPT_DIR/Dockerfile.structurev3" || failed=1
            ;;
        ppocrv6)     build_target ppocrv6 pp-ocrv6 "$SCRIPT_DIR/Dockerfile.ppocrv6" || failed=1 ;;
        structurev3) build_target structurev3 pp-structurev3 "$SCRIPT_DIR/Dockerfile.structurev3" || failed=1 ;;
        *)           echo "[WARN] 未知变体: $comp" ;;
    esac
done

echo ""
[[ "$failed" -ne 0 ]] && { echo "构建存在失败项" >&2; exit 1; }
echo "PaddleOCR 构建完成。下一步：./push.sh"
