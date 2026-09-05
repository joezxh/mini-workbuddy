# MinWorkBuddy Backend - v0.1.0
# 多阶段构建: 依赖层 + 运行层分离, 减小镜像体积
FROM python:3.11-slim AS deps

WORKDIR /app

# 系统依赖 (psycopg2 / cryptography / pgvector 所需)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
        && rm -rf /var/lib/apt/lists/*

# Python 依赖 (从 requirements 复制后安装)
COPY pyproject.toml requirements*.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 运行层 (精简)
FROM python:3.11-slim AS runtime

WORKDIR /app

# 运行时系统依赖 (libpq 用于 psycopg2, git 用于 skill_hub 仓库克隆)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        git \
        && rm -rf /var/lib/apt/lists/*

# 复制依赖
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# 复制应用代码
COPY app ./app
# 可选: data 目录 (种子数据 / 业务字典)
# COPY data ./data

# 环境变量默认值 (运行时 override)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    LOG_LEVEL=INFO

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令 (uvicorn async workers)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]


# --- Local dev (单层) ---
# FROM python:3.11-slim
# WORKDIR /app
# COPY pyproject.toml ./
# RUN pip install --no-cache-dir -e .
# COPY app ./app
# CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
