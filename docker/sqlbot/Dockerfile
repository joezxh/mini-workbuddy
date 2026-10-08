# =============================================================
# SQLBot 镜像（离线向：不拉 ghcr 的向量模型阶段）
#
# 构建上下文：SQLBot 源码仓库根目录（含 backend/ frontend/ g2-ssr/ start.sh）
#   docker build -f docker/sqlbot/Dockerfile --build-arg SQLBOT_SECRET_KEY=xxx <SQLBot 根目录>
#
# 与上游 installer/sqlbot/Dockerfile 的差异：
#   1) 移除 ghcr.io/1panel-dev/maxkb-vector-model 阶段（762MB，国内拉取极慢）。
#      本部署 EMBEDDING_ENABLED=false / TABLE_EMBEDDING_ENABLED=false，
#      embedding 模型为惰性加载且失败会优雅降级，运行期不需要 /opt/sqlbot/models。
#   2) 基础镜像改用个人 ACR 中转的 sqlbot-base / sqlbot-python-pg。
#   3) npm 走 npmmirror，uv 走阿里云 PyPI，torch 默认走阿里云 PyTorch 镜像。
#   4) VITE_SECRET_KEY 由 build-arg 注入，缺失即构建失败（避免产出"能跑但登不了"的镜像）。
# =============================================================
# syntax=docker/dockerfile:1

ARG BASE_REGISTRY=crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com/llm-basic/base

# ------------------------- 前端构建 -------------------------
FROM --platform=${BUILDPLATFORM} ${BASE_REGISTRY}/sqlbot-base:latest AS sqlbot-ui-builder

ENV SQLBOT_HOME=/opt/sqlbot
ENV APP_HOME=${SQLBOT_HOME}/app
ENV UI_HOME=${SQLBOT_HOME}/frontend
ENV DEBIAN_FRONTEND=noninteractive

# 前端 Vite 构建时会把 VITE_* 内联进产物；这里的 VITE_SECRET_KEY 必须与运行期
# 后端 SECRET_KEY[:32] 一致，否则登录接口解密出乱码账号。
ARG SQLBOT_SECRET_KEY
ENV VITE_SECRET_KEY=${SQLBOT_SECRET_KEY}

ARG NPM_REGISTRY=https://registry.npmmirror.com

RUN mkdir -p ${APP_HOME} ${UI_HOME}

COPY frontend /tmp/frontend

# 自检：密钥未注入直接终止构建
RUN test -n "${VITE_SECRET_KEY}" || \
    (echo "ERROR: 缺少 --build-arg SQLBOT_SECRET_KEY，前端加密密钥未注入，构建终止" && false)

RUN cd /tmp/frontend && \
    npm config set registry ${NPM_REGISTRY} && \
    npm config set fund false && \
    npm config set audit false && \
    npm config set progress false && \
    npm install && \
    npm run build && \
    mv dist ${UI_HOME}/dist

# ------------------------- 后端依赖 -------------------------
FROM ${BASE_REGISTRY}/sqlbot-base:latest AS sqlbot-builder

ENV PYTHONUNBUFFERED=1
ENV SQLBOT_HOME=/opt/sqlbot
ENV APP_HOME=${SQLBOT_HOME}/app
ENV UI_HOME=${SQLBOT_HOME}/frontend
ENV PYTHONPATH=${SQLBOT_HOME}/app
ENV PATH="${APP_HOME}/.venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV DEBIAN_FRONTEND=noninteractive

# uv 走阿里云 PyPI，并抬高超时容忍网络抖动
ARG UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple
ARG TORCH_INDEX_URL=https://mirrors.aliyun.com/pytorch-wheels/cpu

ENV UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX}
ENV UV_HTTP_TIMEOUT=180

RUN mkdir -p ${APP_HOME} ${UI_HOME}
WORKDIR ${APP_HOME}

COPY --from=sqlbot-ui-builder ${UI_HOME} ${UI_HOME}

COPY backend ${APP_HOME}

# 依赖安装要点：
#   1) uv sync 先在 PyPI 源装齐非 torch 依赖（torch 是 extra，不带 --extra 则不装）
#   2) torch 单独从 PyTorch 索引装 CPU 版，避开约 3GB 的 nvidia-* CUDA 依赖
#   3) mcp 必须降级到 <2.0.0：mcp>=2.0 的 Server.__init__ 第二参数改为仅关键字，
#      fastapi-mcp(<0.4.0) 的老式调用会 TypeError。uv sync 不读 pip constraints，
#      只能在 sync 之后用 uv pip install 覆盖。
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --extra cpu && \
    uv pip install torch --index-url ${TORCH_INDEX_URL} && \
    uv pip install --index-url ${UV_DEFAULT_INDEX} "mcp<2.0.0"

# ------------------------- g2-ssr 图表渲染 -------------------------
FROM ${BASE_REGISTRY}/sqlbot-base:latest AS ssr-builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential python3 pkg-config \
        libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev \
        libpixman-1-dev libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

ARG NPM_REGISTRY=https://registry.npmmirror.com

RUN npm config set registry ${NPM_REGISTRY} && \
    npm config set fund false && \
    npm config set audit false && \
    npm config set progress false

COPY g2-ssr/app.js g2-ssr/package.json /app/
COPY g2-ssr/charts/* /app/charts/
RUN npm install

# ------------------------- 运行 -------------------------
FROM ${BASE_REGISTRY}/sqlbot-python-pg:latest

RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

ENV PYTHONUNBUFFERED=1
ENV SQLBOT_HOME=/opt/sqlbot
ENV PYTHONPATH=${SQLBOT_HOME}/app
ENV PATH="${SQLBOT_HOME}/app/.venv/bin:$PATH"

ENV POSTGRES_DB=sqlbot
ENV POSTGRES_USER=root
ENV POSTGRES_PASSWORD=Password123@pg

COPY start.sh /opt/sqlbot/app/start.sh
COPY g2-ssr/*.ttf /usr/share/fonts/truetype/liberation/
COPY --from=sqlbot-builder ${SQLBOT_HOME} ${SQLBOT_HOME}
COPY --from=ssr-builder /app /opt/sqlbot/g2-ssr

# 关闭 embedding 时无需真实模型文件，保持目录占位即可
RUN mkdir -p /opt/sqlbot/models /opt/sqlbot/images /opt/sqlbot/g2-ssr

WORKDIR ${SQLBOT_HOME}/app

EXPOSE 3000 8000 8001 5432

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000 || exit 1

ENTRYPOINT ["sh", "start.sh"]
