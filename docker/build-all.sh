#!/usr/bin/env bash
# =============================================================
# 一键构建全部（或指定）组件镜像（Linux 端）
#
#   ./build-all.sh [--component mem0,sqlbot] [--tag 1.0.0]
#                  [--skip-prepull] [--force] [--no-cache]
#
# 步骤与 build-all.ps1 完全一致：
#   1) _common/prepull.sh 做基础镜像中转（幂等）
#   2) 按依赖顺序调用各组件 build.sh
# =============================================================
set -uo pipefail

DOCKER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPONENT="all"
TAG=""
SKIP_PREPULL=0
FORCE=0
NO_CACHE=0
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --component)    COMPONENT="$2"; shift 2 ;;
        --tag)          TAG="$2"; shift 2 ;;
        --skip-prepull) SKIP_PREPULL=1; shift ;;
        --force)        FORCE=1; shift ;;
        --no-cache)     NO_CACHE=1; shift ;;
        -h|--help)      sed -n '2,12p' "$0"; exit 0 ;;
        # 透传给组件脚本的源码路径
        --mem0-src|--sqlbot-src|--paddle-src|--s2s-src|--gander-src)
                        EXTRA_ARGS+=("$1" "$2"); shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

echo ""
echo "=================================================="
echo "  MinWorkBuddy 组件镜像构建"
echo "=================================================="

if [[ "$SKIP_PREPULL" -eq 0 ]]; then
    echo ""
    echo "--- [1/2] 基础镜像中转（幂等，已有则跳过）---"
    if ! "$DOCKER_ROOT/_common/prepull.sh"; then
        echo "[ERROR] 基础镜像中转失败，后续构建大概率会去拉海外源，已中止。" >&2
        exit 1
    fi
else
    echo ""
    echo "--- [1/2] 已跳过基础镜像中转 ---"
fi

echo ""
echo "--- [2/2] 组件镜像构建 ---"

map_dir() {
    case "$1" in
        mem0)      echo "mem0" ;;
        nginx)     echo "nginx" ;;
        sqlbot)    echo "sqlbot" ;;
        paddleocr) echo "paddleOCR" ;;
        s2s)       echo "speech-to-speech" ;;
        gander)    echo "gander" ;;
        *)         echo "" ;;
    esac
}

src_flag() {
    case "$1" in
        mem0)      echo "--mem0-src" ;;
        sqlbot)    echo "--sqlbot-src" ;;
        paddleocr) echo "--paddle-src" ;;
        s2s)       echo "--s2s-src" ;;
        gander)    echo "--gander-src" ;;
        *)         echo "" ;;
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
    if [[ -z "$dir" ]]; then
        echo "[WARN] 未知组件: $name"
        continue
    fi

    script="$DOCKER_ROOT/$dir/build.sh"
    if [[ ! -f "$script" ]]; then
        echo "[SKIP] $name 缺少 build.sh"
        results+=("$name=SKIP")
        continue
    fi

    echo ""
    echo ">>> [$name] $dir"

    args=()
    [[ -n "$TAG" ]] && args+=(--tag "$TAG")
    [[ "$FORCE" -eq 1 ]] && args+=(--force)
    [[ "$NO_CACHE" -eq 1 ]] && args+=(--no-cache)
    [[ "$name" == "gander" ]] && args+=(--variant all)

    # 源码路径透传：--xxx-src <path> → 组件脚本的 --source-root
    for i in "${!EXTRA_ARGS[@]}"; do
        if [[ "${EXTRA_ARGS[$i]}" == "$(src_flag "$name")" ]]; then
            args+=(--source-root "${EXTRA_ARGS[$((i+1))]}")
        fi
    done

    if bash "$script" "${args[@]}"; then
        results+=("$name=OK")
    else
        results+=("$name=FAIL")
        failed=1
    fi
done

echo ""
echo "=================================================="
echo "  构建结果汇总"
echo "=================================================="
for item in "${results[@]}"; do echo "  $item"; done

[[ "$failed" -ne 0 ]] && { echo "存在失败组件，详见上方日志。" >&2; exit 1; }
echo "全部完成。下一步：./push-all.sh"
