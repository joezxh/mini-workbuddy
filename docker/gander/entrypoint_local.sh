#!/usr/bin/env bash
# =============================================================
# entrypoint_local.sh — 本地容器入口: 启动 ASR + Nginx
# =============================================================
set -euo pipefail

REMOTE_THINKER_HOST="${REMOTE_THINKER_HOST:-127.0.0.1}"
REMOTE_THINKER_PORT="${REMOTE_THINKER_PORT:-8000}"
ASR_MODEL="${ASR_MODEL_PATH:-/models/faster-whisper-large-v3}"
ASR_DEVICE="${ASR_DEVICE:-cuda}"
ASR_COMPUTE="${ASR_COMPUTE_TYPE:-float16}"

echo "[entrypoint] Configuring Nginx reverse proxy -> ${REMOTE_THINKER_HOST}:${REMOTE_THINKER_PORT}"
sed -i "s|REMOTE_THINKER_HOST|${REMOTE_THINKER_HOST}|g" /etc/nginx/sites-available/default

echo "[entrypoint] Starting Nginx..."
nginx

echo "[entrypoint] Starting ASR service on :8995 (model=${ASR_MODEL}, device=${ASR_DEVICE})"
export PYTHONPATH="/workspace/minicpm_ft:/workspace/gander_runtime${PYTHONPATH:+:$PYTHONPATH}"

exec python -m mcpmft.infer.asr \
    --model "${ASR_MODEL}" \
    --host 0.0.0.0 \
    --port 8995 \
    --device "${ASR_DEVICE}" \
    --device-index "${ASR_DEVICE_INDEX:-0}" \
    --compute-type "${ASR_COMPUTE}" \
    --beam-size "${ASR_BEAM_SIZE:-3}" \
    --log-level info
