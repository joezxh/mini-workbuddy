# Mem0 —— 长记忆服务

REST API（向量记忆 + 图记忆）与 Next.js Dashboard 两个镜像。

| 产物 | 容器端口 | 默认宿主端口 |
|------|---------|-------------|
| `mem0-api` | 8000 | 8888 |
| `mem0-dashboard` | 3000 | 3001 |

## 目录结构

```
mem0/
├── api/Dockerfile          # REST API 镜像定义
├── dashboard/Dockerfile    # Dashboard 镜像定义
├── docker-compose.yml      # 编排（依赖外部网络 mwb-infra-network）
├── build.{ps1,sh}          # 构建
├── push.{ps1,sh}           # 推送到 ACR
├── .env.example            # 环境变量模板
└── README.md
```

## 国内化要点

| 层 | 处理 |
|----|------|
| 基础镜像 | `${BASE_REGISTRY}/python:3.12-slim`、`${BASE_REGISTRY}/node:20-alpine` |
| pip | 阿里云主源 + 华为云备源，BuildKit 缓存挂载 |
| npm / yarn / pnpm | 一律注入 `https://registry.npmmirror.com` |
| apk | 阿里云 alpine 源 |

Dashboard 的 `NEXT_PUBLIC_*` 在构建期写入占位符，容器启动时由官方 `entrypoint.sh` 做字符串替换，
因此同一个镜像可以在不同域名下复用，无需重新 npm build。

## 前置条件

```bash
# 1) 一次性的基础镜像中转
cd ../_common && ./prepull.sh        # Windows: .\prepull.ps1

# 2) 创建数据库（首次）
docker exec -it mwb-postgres-pgvector psql -U postgres \
  -c "CREATE DATABASE mem0;" \
  -c "\c mem0" -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## 构建与推送

```powershell
# Windows
cd d:\projects\MinWorkBuddy\docker\mem0
cp .env.example .env            # 填入真实口令
.\build.ps1 -SourceRoot D:\projects\github\mem0
.\push.ps1
```

```bash
# Linux
cd /path/to/MinWorkBuddy/docker/mem0
cp .env.example .env
./build.sh --source-root /opt/mem0
./push.sh
```

构建出的镜像同时带两个标签：

- `<registry>/mem0-api:<tag>`：远端标签，供 push
- `mem0-api:local`：本地标签，供 `docker-compose.yml` 直接 `up`

## 启动

```bash
export SRC_MEM0=/opt/mem0
docker compose up -d
docker compose logs -f mem0-api
```

验证：

```bash
curl http://localhost:8888/docs          # API 文档
docker inspect --format '{{.State.Health.Status}}' mem0-api
```

## 已知约束（务必先看）

1. **pgvector 列维度必须匹配嵌入模型输出**。`memories.vector` 早期按 OpenAI embedder 建成 `vector(1536)`，
   百炼 `text-embedding-v4` 输出 1024 维，写入会报维度不匹配。`CREATE TABLE IF NOT EXISTS` 不会改列，需手动：

   ```sql
   ALTER TABLE memories ALTER COLUMN vector TYPE vector(1024);
   ```

   注意提前备份向量行——不同嵌入模型的向量空间不兼容，只能重灌。
2. **LLM 供应商配置存在优先级陷阱**。Web 端 `/configure` 的 config_overrides 持久化在 Postgres `mem0.settings` 表，
   优先级高于 `.env` 默认值；overrides 被清空时会回退到 `.env`，所以两处维度参数要保持一致。
   曾经用过 NVIDIA `nemotron-3-embed-1b`，该模型在 NVIDIA 端点 404/超时导致写入全部 502，不要再回退。
3. 图记忆依赖 Neo4j，未部署时相关能力不可用但主流程不受影响。

## 安全提示

历史提交中曾经包含明文数据库口令与本地 JWT_SECRET（见已跟踪的 `.env`）。
请在生产环境轮换这些凭据，并改用 `.env`（已被 `.gitignore` 忽略）+ `.env.example` 模板管理。
