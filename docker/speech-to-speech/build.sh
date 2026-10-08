#!/usr/bin/env bash
# =============================================================
# 构建 speech-to-speech pipeline 镜像（Linux 端）
#
#   ./build.sh [--source-root /opt/speech-to-speech] [--silero-vad-dir <dir>]
#              [--torch-index-url <url>] [--skip-torch-reinstall] [--tag 1.0.0]
#              [--force] [--no-cache]
#
# 会把本地 Silero VAD 仓库搬运进构建上下文；缺 hubconf.py 时直接报错。
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ENV="$(dirname "$SCRIPT_DIR")/registry.env"

SOURCE_ROOT="${S2S_SRC:-/opt/speech-to-speech}"
SILERO_DIR="$SCRIPT_DIR/silero-vad"
TORCH_INDEX_URL="https://mirrors.aliyun.com/pytorch-wheels/cu128"
TAG=""
SKIP_TORCH=0
FORCE=0
NO_CACHE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source-root)        SOURCE_ROOT="$2"; shift 2 ;;
        --silero-vad-dir)     SILERO_DIR="$2"; shift 2 ;;
        --torch-index-url)    TORCH_INDEX_URL="$2"; shift 2 ;;
        --skip-torch-reinstall) SKIP_TORCH=1; shift ;;
        --tag)                TAG="$2"; shift 2 ;;
        --force)              FORCE=1; shift ;;
        --no-cache)           NO_CACHE=1; shift ;;
        -h|--help)            sed -n '2,13p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

[[ -f "$REGISTRY_ENV" ]] || { echo "[ERROR] 找不到 $REGISTRY_ENV" >&2; exit 1; }
get_var() { sed -n -E "s/^$1=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'; }

REGISTRY="$(get_var REGISTRY)"
[[ -z "$TAG" ]] && TAG="$(get_var IMAGE_TAG)"

[[ -d "$SOURCE_ROOT" ]] || { echo "[ERROR] 源码目录不存在: $SOURCE_ROOT" >&2; exit 1; }

if [[ ! -f "$SILERO_DIR/hubconf.py" ]]; then
    echo "[ERROR] Silero VAD 仓库未就位: $SILERO_DIR" >&2
    echo "" >&2
    echo "  VAD/vad_handler.py 使用 torch.hub.load('/opt/silero-vad', source='local')，" >&2
    echo "  容器内连不上 github.com，必须离线预置：" >&2
    echo "    git clone --depth 1 https://github.com/snakers4/silero-vad.git" >&2
    echo "    cp -r silero-vad/* $SILERO_DIR" >&2
    exit 1
fi

STAGING="$SOURCE_ROOT/.docker-build/silero-vad"
echo "[PREP] 准备 Silero VAD → $STAGING"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -r "$SILERO_DIR"/. "$STAGING"/

REMOTE="$REGISTRY/s2s-pipeline:$TAG"
LOCAL="s2s-pipeline:local"

if [[ "$FORCE" -eq 0 ]] && [[ -n "$(docker images -q "$REMOTE" 2>/dev/null)" ]]; then
    echo "[SKIP] $REMOTE 已存在（重建加 --force）"
    exit 0
fi

echo ""
echo "========================================"
echo "  speech-to-speech 构建  tag=$TAG"
echo "  源码：$SOURCE_ROOT"
echo "========================================"
echo ""

args=(
    build
    -f "$SCRIPT_DIR/Dockerfile"
    --build-arg "TORCH_INDEX_URL=$TORCH_INDEX_URL"
    --build-arg "SKIP_TORCH_REINSTALL=$SKIP_TORCH"
    -t "$REMOTE"
    -t "$LOCAL"
)
[[ "$NO_CACHE" -eq 1 ]] && args+=(--no-cache)
args+=(--progress=plain "$SOURCE_ROOT")

if docker "${args[@]}"; then
    echo "[ OK ] $REMOTE"
    echo ""
    echo "下一步：./push.sh   启动：docker compose -f docker-compose.gpustack.yml up -d"
else
    echo "[FAIL] 构建失败" >&2
    exit 1
fi
