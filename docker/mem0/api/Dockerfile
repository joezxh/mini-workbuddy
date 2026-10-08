# =============================================================
# Mem0 REST API（FastAPI + 向量记忆 + 图记忆）
#
# 构建上下文：mem0 官方仓库的 server/ 目录
#   docker build -f docker/mem0/api/Dockerfile <server 目录>
#
# 国内化要点：
#   1) 基础镜像来自个人 ACR 的 base/python（避免直连 Docker Hub）
#   2) pip 走阿里云主源 + 华为云备源，所有 ARG 均可在构建时覆盖
# =============================================================
# syntax=docker/dockerfile:1

ARG BASE_REGISTRY=crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com/llm-basic/base
ARG PYTHON_IMAGE_TAG=3.12-slim

FROM ${BASE_REGISTRY}/python:${PYTHON_IMAGE_TAG}

# ---- 国内源参数（构建时可覆盖）----
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG PIP_EXTRA_INDEX_URL=https://repo.huaweicloud.com/repository/pypi/simple
ARG PIP_TRUSTED_HOST="mirrors.aliyun.com repo.huaweicloud.com"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

WORKDIR /app

# 先装依赖层，源码变动时不必重装依赖
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir \
        -r requirements.txt \
        "psycopg[binary,pool]"

# 图记忆 + 排序依赖（mem0ai 本体已在 requirements 中部分覆盖，这里补齐 extras）
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir \
        "mem0ai[graph]" \
        rank-bm25 langchain-neo4j neo4j

# 复制应用源码
COPY . .

# 历史数据与 SQLite 落盘目录
RUN mkdir -p /app/data

EXPOSE 8000

# 用 TCP 探测，避免依赖容器内的 curl / requests 路由
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import socket,sys; s=socket.create_connection(('127.0.0.1',8000),3); s.close()" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
