#!/usr/bin/env bash
# =============================================================
# 第三方基础镜像中转（Linux / macOS / Git Bash）
#
# 与 prepull.ps1 行为一致：拉取 → 改标签 → 推送到阿里云个人仓库。
# 幂等：远端已存在同名镜像则跳过，--force 才重建。
#
# 用法：
#   ./prepull.sh
#   ./prepull.sh --force
#   ./prepull.sh --dry-run --list ./prepull-images.txt
#
# 前置：docker login crpi-xxx.cn-hangzhou.personal.cr.aliyuncs.com
#       本脚本不接受任何凭据参数。
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIST_FILE="${SCRIPT_DIR}/prepull-images.txt"
FORCE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)     FORCE=1; shift ;;
        --dry-run)   DRY_RUN=1; shift ;;
        --list)      LIST_FILE="$2"; shift 2 ;;
        -h|--help)   sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

REGISTRY_ENV="$(dirname "$SCRIPT_DIR")/registry.env"
if [[ ! -f "$REGISTRY_ENV" ]]; then
    echo "[ERROR] 找不到配置文件: $REGISTRY_ENV" >&2
    exit 1
fi

# 读取 registry.env（跳过注释与空行）
get_var() {
    local key="$1"
    sed -n -E "s/^${key}=(.*)\$/\1/p" "$REGISTRY_ENV" | tail -n 1 | tr -d '\r'
}

REGISTRY_HOST="$(get_var REGISTRY_HOST)"
REGISTRY="$(get_var REGISTRY)"

if [[ -z "$REGISTRY_HOST" || -z "$REGISTRY" ]]; then
    echo "[ERROR] registry.env 缺少 REGISTRY_HOST / REGISTRY" >&2
    exit 1
fi

# 登录态检查
DOCKER_CONFIG_DIR="${DOCKER_CONFIG:-$HOME/.docker}"
if [[ ! -f "$DOCKER_CONFIG_DIR/config.json" ]] || ! grep -q "$REGISTRY_HOST" "$DOCKER_CONFIG_DIR/config.json"; then
    echo "[ERROR] 未检测到 $REGISTRY_HOST 的登录凭据。" >&2
    echo "        请先执行：docker login $REGISTRY_HOST" >&2
    exit 1
fi

if [[ ! -f "$LIST_FILE" ]]; then
    echo "[ERROR] 白名单文件不存在: $LIST_FILE" >&2
    exit 1
fi

echo ""
echo "========================================"
echo "  基础镜像中转 → $REGISTRY"
echo "  白名单：$LIST_FILE"
echo "  Force  ：$FORCE"
echo "========================================"
echo ""

total=0; skipped=0; ok=0
failed=()

while read -r line; do
    line="${line%%$'\r'}"
    trimmed="$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [[ -z "$trimmed" || "$trimmed" == \#* ]] && continue

    # shellcheck disable=SC2086
    set -- $trimmed
    [[ $# -lt 2 ]] && { echo "[WARN] 忽略无效行: $line"; continue; }

    src="$1"; dst="$2"; from="${3:-$1}"
    target="$REGISTRY/$dst"

    total=$((total + 1))

    if [[ "$FORCE" -eq 0 ]]; then
        if docker manifest inspect "$target" >/dev/null 2>&1; then
            echo "[SKIP] $target 已存在"
            skipped=$((skipped + 1))
            continue
        fi
    fi

    echo "[PULL] $from"
    if [[ "$DRY_RUN" -eq 1 ]]; then ok=$((ok + 1)); continue; fi

    if ! docker pull "$from"; then
        echo "[FAIL] 拉取失败: $from"
        failed+=("$src")
        continue
    fi
    if ! docker tag "$from" "$target"; then
        echo "[FAIL] 打标签失败: $from -> $target"
        failed+=("$src")
        continue
    fi
    if ! docker push "$target"; then
        echo "[FAIL] 推送失败: $target"
        failed+=("$src")
        continue
    fi

    echo "[ OK ] $target"
    ok=$((ok + 1))
done < "$LIST_FILE"

echo ""
echo "========================================"
echo "  中转完成：总计 $total / 成功 $ok / 跳过 $skipped / 失败 ${#failed[@]}"
echo "========================================"

if [[ ${#failed[@]} -gt 0 ]]; then
    echo "失败的源镜像："
    for item in "${failed[@]}"; do echo "  - $item"; done
    echo ""
    echo "提示：Docker Hub 卡顿时，可在白名单第三列换其它 proxy registry。"
    exit 1
fi
