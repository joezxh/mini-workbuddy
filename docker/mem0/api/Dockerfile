FROM python:3.12-slim

WORKDIR /app

# 安装基础依赖（使用阿里云 pip 镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt \
    "psycopg[binary,pool]"

# 安装图记忆 + 排序依赖
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    "mem0ai[graph]" \
    rank-bm25 langchain-neo4j neo4j

# 复制应用源码
COPY . .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
