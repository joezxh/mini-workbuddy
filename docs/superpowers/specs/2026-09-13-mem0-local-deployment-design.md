# Mem0 内存服务本地部署设计

## 概述

在本地 Windows 开发机（Docker Desktop）上部署 Mem0 平台版（含 API + Dashboard），复用本地已有的 PostgreSQL (pgvector) 和 Neo4j 基础设施，为 Dify 工作流提供 AI 记忆能力。

## 架构

```
本地 Windows 开发机 (Docker Desktop)
┌──────────────────────────────────────────────────────────┐
│  mwb-infra-network (已有 bridge 网络)                      │
│                                                          │
│  ┌──────────────────┐  ┌───────────────────────┐         │
│  │ mem0-api         │  │ mem0-dashboard        │         │
│  │ (FastAPI:8888)   │  │ (Next.js:3001)        │         │
│  └──┬───────────┬───┘  └───────────────────────┘         │
│     │           │                                         │
│     ▼           ▼                                         │
│  postgres     mwb-neo4j                                   │
│  (pgvector)   (graph, APOC)                               │
│  :5432        :7687                                       │
└──────────────────────────────────────────────────────────┘
```

- **mem0-api**：FastAPI 服务，处理记忆 CRUD、向量搜索、图记忆
- **mem0-dashboard**：Next.js 管理控制台，浏览记忆、管理 API Key、配置 LLM
- 两个容器通过 Docker 内部网络通信，对外暴露独立端口

## 文件结构

```
d:\projects\MinWorkBuddy\docker\mem0\
├── api\
│   └── Dockerfile              # 基于 mem0/mem0-api-server + 图记忆依赖
├── docker-compose.yaml         # 核心编排文件
├── .env                        # 环境变量（不提交到 git）
└── build.ps1                   # 一键构建启动脚本
```

Dashboard 源码通过 git clone mem0 仓库获取，构建时引用 `mem0/server/dashboard/` 目录。

## 组件详细设计

### 1. API Dockerfile (`api/Dockerfile`)

```dockerfile
FROM mem0/mem0-api-server:latest
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    "psycopg[binary,pool]" \
    "mem0ai[graph]" \
    rank-bm25 langchain-neo4j neo4j
```

- 基于官方 `mem0/mem0-api-server:latest`
- 安装 PostgreSQL 驱动（psycopg）用于 pgvector 向量存储
- 安装图记忆依赖（mem0ai[graph]、langchain-neo4j、neo4j）
- 使用阿里云 pip 镜像加速

### 2. Dashboard 构建

直接使用 mem0 仓库中 `server/dashboard/Dockerfile`（多阶段 Next.js 构建）。该 Dockerfile 的 `entrypoint.sh` 支持运行时替换 `NEXT_PUBLIC_API_URL` 和 `NEXT_PUBLIC_INSTANCE_NAME`，无需重新构建即可修改 API 地址。

### 3. docker-compose.yaml

```yaml
name: mem0-local

services:
  mem0-api:
    build:
      context: ./api
    container_name: mem0-api
    ports:
      - "8888:8000"
    env_file:
      - .env
    environment:
      - PYTHONDONTWRITEBYTECODE=1
      - PYTHONUNBUFFERED=1
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=mem0
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_COLLECTION_NAME=memories
      - NEO4J_URI=${NEO4J_URI}
      - NEO4J_USERNAME=${NEO4J_USERNAME}
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - APP_DB_NAME=mem0_app
      - JWT_SECRET=${JWT_SECRET}
      - AUTH_DISABLED=${AUTH_DISABLED:-true}
      - DASHBOARD_URL=http://localhost:3001
      - MEM0_TELEMETRY=false
    networks:
      - mwb-infra-network
    restart: unless-stopped

  mem0-dashboard:
    build:
      context: ./mem0-source/server/dashboard
    container_name: mem0-dashboard
    ports:
      - "3001:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8888
      - API_INTERNAL_URL=http://mem0-api:8000
      - NEXT_PUBLIC_INSTANCE_NAME=Mem0
    depends_on:
      - mem0-api
    networks:
      - mwb-infra-network
    restart: unless-stopped

networks:
  mwb-infra-network:
    external: true
```

### 4. 环境变量 (.env)

```env
# PostgreSQL (本地 mwb-postgres-pgvector 容器)
POSTGRES_PASSWORD=admin123

# Neo4j (本地 mwb-neo4j 容器)
NEO4J_URI=bolt://mwb-neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=neo4j123

# Auth (本地开发关闭认证)
AUTH_DISABLED=true
JWT_SECRET=local-dev-jwt-secret-key-2026

# LLM (后续配置，暂留空)
OPENAI_API_KEY=
```

### 5. 构建脚本 (build.ps1)

```powershell
# 1. Clone mem0 源码（首次运行）
if (-not (Test-Path "./mem0-source")) {
    git clone https://github.com/mem0ai/mem0.git --depth 1 mem0-source
}

# 2. 创建 PostgreSQL 数据库（首次运行，手动执行）
# docker exec -it mwb-postgres-pgvector psql -U postgres `
#   -c "CREATE DATABASE mem0;" `
#   -c "\c mem0" `
#   -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 3. 构建并启动
docker compose up -d --build

# 4. 等待服务就绪
Write-Host "等待 API 就绪..."
Start-Sleep -Seconds 10

# 5. 验证
Write-Host "API Docs: http://localhost:8888/docs"
Write-Host "Dashboard: http://localhost:3001"
```

## 依赖项检查清单

| 依赖 | 位置 | 状态 | 操作 |
|------|------|------|------|
| PostgreSQL + pgvector | mwb-postgres-pgvector:5432 | 已有 | 创建 `mem0` 数据库 |
| Neo4j + APOC | mwb-neo4j:7687 | 已有 | APOC 已启用（已配置） |
| Docker Desktop | 本地 | 已有 | 确保运行中 |
| Git | 本地 | 需确认 | clone mem0 源码 |
| LLM/Embedder | 待定 | 待配置 | 后续通过 Dashboard 或 .env 配置 |

## 数据库准备

### PostgreSQL

在本地 PostgreSQL (mwb-postgres-pgvector) 上创建 `mem0` 数据库：

```bash
docker exec -it mwb-postgres-pgvector psql -U postgres \
  -c "CREATE DATABASE mem0;" \
  -c "\c mem0" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Neo4j

确认本地 Neo4j 启用了 APOC 插件。在 Neo4j 容器中检查：
```
NEO4J_PLUGINS=["apoc"]
```

## 验证步骤

### 1. 启动服务

```powershell
cd d:\projects\MinWorkBuddy\docker\mem0
.\build.ps1
```

### 2. API 健康检查

```powershell
# Swagger UI 应可访问
curl http://localhost:8888/docs
```

### 3. Dashboard 访问

浏览器打开 `http://localhost:3001`，应看到 Mem0 控制台界面。

### 4. 记忆 CRUD 测试

```powershell
# 添加记忆
curl -X POST http://localhost:8888/memories `
  -H "Content-Type: application/json" `
  -d '{"messages": [{"role": "user", "content": "我喜欢用 Python 写代码"}], "user_id": "test_user"}'

# 搜索记忆
curl -X POST http://localhost:8888/search `
  -H "Content-Type: application/json" `
  -d '{"query": "编程语言偏好", "user_id": "test_user"}'

# 列出所有记忆
curl http://localhost:8888/memories?user_id=test_user
```

### 5. Dify 工作流集成

在 Dify 工作流中使用 HTTP 节点调用 Mem0 API：

```python
import requests

MEM0_BASE_URL = "http://host.docker.internal:8888"

# 添加记忆
response = requests.post(f"{MEM0_BASE_URL}/memories", json={
    "messages": [{"role": "user", "content": "用户偏好中文界面"}],
    "user_id": "dify_user_001"
})

# 搜索记忆
response = requests.post(f"{MEM0_BASE_URL}/search", json={
    "query": "界面语言偏好",
    "user_id": "dify_user_001"
})
```

## 国内镜像加速

| 组件 | 镜像源 | 配置方式 |
|------|--------|---------|
| pip (API 依赖) | 阿里云 | Dockerfile 中 `-i https://mirrors.aliyun.com/pypi/simple/` |
| npm (Dashboard 构建) | 淘宝 | Dockerfile 中 `npm config set registry https://registry.npmmirror.com` |
| Docker 基础镜像 | Docker Desktop 加速器 | Settings → Docker Engine → registry-mirrors |

推荐的 Docker 镜像加速器：
- 阿里云容器镜像服务（需注册）
- DaoCloud: `https://docker.m.daocloud.io`
- 中科大: `https://docker.mirrors.ustc.edu.cn`

## LLM/Embedder 后续配置

LLM 和 Embedder 暂不配置，Mem0 API 和 Dashboard 可正常启动。后续通过以下方式之一配置：

1. **Dashboard 配置页面**：访问 http://localhost:3001 → Configuration → 选择 LLM/Embedder 提供商
2. **环境变量**：在 `.env` 中添加 `OPENAI_API_KEY` 或其他提供商密钥
3. **Ollama 本地模型**：配置 `MEM0_DEFAULT_LLM_MODEL` 和 `MEM0_DEFAULT_EMBEDDER_MODEL` 指向本地 Ollama

## 注意事项

- `AUTH_DISABLED=true` 仅用于本地开发，生产环境必须启用认证
- 切换 Embedder 模型（如从 OpenAI 换到 Ollama）需要清空向量数据重建，因为向量维度不同
- `.env` 文件包含敏感信息，不应提交到 git
- Mem0 API 默认 CORS 为 `allow_origins=["*"]`，本地开发无需额外配置
