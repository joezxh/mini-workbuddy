# =============================================================
# speech-to-speech pipeline（VAD + STT + LLM + TTS）
#
# 构建上下文：speech-to-speech 源码仓库根目录
#   docker build -f docker/speech-to-speech/Dockerfile <speech-to-speech 根目录>
#
# 相对上游 Dockerfile 的改造（都是实测踩过的坑）：
#   1) 基础镜像改用个人 ACR 中转的 nvidia/cuda:12.8.1（直连 Docker Hub 会卡死）
#   2) apt 换阿里云；额外安装 sox（消除运行期 "SoX could not be found" 告警）
#   3) uv 索引指向阿里云 PyPI，HF_ENDPOINT 指向 hf-mirror
#   4) torch / torchaudio 重新从 cu128 索引安装 —— 默认 wheel 是 cu130，
#      与宿主驱动 12.8 不匹配时 torch.cuda.is_available() 为 False，
#      STT/TTS 会静默回退 CPU（Qwen3-TTS RTF 从 0.69 劣化到 3.7）
#   5) Silero VAD 必须预置：容器内连不上 github.com，torch.hub 拉不上来
#      会直接 FileNotFoundError 导致 8765 无人监听
#   6) 构建末期应用 patches/apply_patches.py 修两个运行期缺陷
# =============================================================
# syntax=docker/dockerfile:1

ARG BASE_REGISTRY=crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com/llm-basic/base
ARG CUDA_IMAGE_TAG=12.8.1-cudnn-runtime-ubuntu24.04

FROM ${BASE_REGISTRY}/nvidia-cuda:${CUDA_IMAGE_TAG}

ARG UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple
ARG TORCH_INDEX_URL=https://mirrors.aliyun.com/pytorch-wheels/cu128
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/src/app/.venv/bin:${PATH}" \
    HF_ENDPOINT=https://hf-mirror.com \
    UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX} \
    UV_HTTP_TIMEOUT=180 \
    TORCH_INDEX_URL=${TORCH_INDEX_URL}

WORKDIR /usr/src/app

# ---------- apt 换国内源 ----------
RUN sed -i 's#archive.ubuntu.com#mirrors.aliyun.com#g; s#security.ubuntu.com#mirrors.aliyun.com#g' \
        /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list 2>/dev/null || true

# ---------- 系统依赖 ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git curl \
        libportaudio2 libsndfile1 \
        python3 python3-pip python3-venv \
        sox libsox-fmt-all \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
        -i ${PIP_INDEX_URL} uv

# ---------- 依赖层（先只放元数据，源码变动不必重装依赖）----------
COPY pyproject.toml README.md LICENSE MANIFEST.in ./
RUN uv sync --python /usr/bin/python3 --no-install-project --no-dev

# ---------- 源码 + 补丁 + Silero VAD ----------
COPY patches /opt/patches
# Silero VAD 由构建脚本从本地准备目录搬运到上下文的 .docker-build/silero-vad，
# 见 silero-vad/.gitkeep 中的说明（容器内连不上 github.com，必须离线预置）。
COPY .docker-build/silero-vad /opt/silero-vad
COPY src ./src

RUN uv sync --python /usr/bin/python3 --no-dev

# torch / torchaudio 换成与宿主驱动 12.8 匹配的 cu128 wheel。
# 不需要时可用 --build-arg SKIP_TORCH_REINSTALL=1 跳过。
ARG SKIP_TORCH_REINSTALL=0
RUN if [ "$SKIP_TORCH_REINSTALL" != "1" ]; then \
        uv pip install --no-deps --index-url "${TORCH_INDEX_URL}" torch torchaudio; \
    else \
        echo "[skip] 跳过 torch 重装"; \
    fi

# ---------- 应用运行期补丁（幂等，失败不阻断）----------
RUN python /opt/patches/apply_patches.py || true

# ---------- nltk 资源（容器内 nltk.org 常不可达，失败不致命：补丁已提供正则兜底）----------
RUN python -c "import nltk; nltk.download('punkt')" || true
RUN python -c "import nltk; nltk.download('punkt_tab')" || true
RUN python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng')" || true

# ---------- 模型缓存（运行时挂载卷，避免重启重下）----------
VOLUME ["/root/.cache"]

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import socket; s=socket.create_connection(('127.0.0.1',8765),3); s.close()" || exit 1

CMD ["speech-to-speech", "serve", "--host", "0.0.0.0", "--port", "8765"]
