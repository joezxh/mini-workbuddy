<p align="center">
  <a href="readme.md">
    <img src="https://img.shields.io/badge/English-Click%20here-blue?style=for-the-badge" alt="English">
  </a>
</p>

# MiniWorkBuddy

> 基于 **AgentScope 2.0.7** 构建、仿腾讯 WorkBuddy 的轻量通用 **AI 工作台**。
>
> 多智能体协作、技能插件、深度研究、带本体推理的知识库、全双工文字/语音对话、
> 自动化调度 —— 一站式可扩展的 AI 工作平台。

MiniWorkBuddy 是一站式智能工作台。前端是基于 Vue 3 的工作台界面，支持智能体 /
编排可视化、丰富图表与 Markdown/代码渲染；后端的 AI 层以
[AgentScope 2.0.7](https://github.com/modelscope/agentscope) 为核心：运行单个
**Agent 专家**、**AgentTeam 专家组**、**技能**插件系统、**深度思考 / 深度研究**、
带向量检索与**本体**推理的**知识库**，以及**全双工文字/语音 AI 客服**，并支持
**自动化调度**。

---

## ✨ 功能特性

1. **AI 对话** —— 多轮对话，Server-Sent Events（SSE）流式输出，含对话记忆与上下文管理。
2. **深度思考** —— 分步推理模式，给出可追溯、透明的思考过程。
3. **深度研究** —— 自主多步研究（`research/` 模块）：任务规划、联网检索、知识综合，
   产出带引用的研究报告。
4. **技能** —— 插件式 **技能**系统（`skills/`），含技能规则与技能进化，支持能力自迭代。
5. **Agent 专家** —— 配置并运行单个专精智能体（`agent/` 模块），含智能体配置与执行历史。
6. **AgentTeam 专家组** —— 多智能体 **团队**（`team/` 模块）协同解决复杂问题。
7. **自动化调度任务** —— 通过 `agent_scheduled_task` + APScheduler / ARQ / Celery，
   定时自动运行智能体 / 技能 / 任务。
8. **全双工 文字/语音对话【AI 客服】** —— 基于 WebSocket 流式传输 + ASR/TTS 的全双工
   对话，无缝支持文字 **与** 语音交互。
9. **知识库** —— 向量知识库（pgvector + 向量嵌入）检索，配合 `wiki/` 知识空间与联网搜索 grounding。
10. **本体** —— 基于领域 **本体**的推理（OWL / RDF(SPARQL) / Prolog / 模糊推理），
    对知识库做结构化、规则化推断。

平台附加能力：**MCP** 工具生态（MCP 客户端 + 服务端端点）、**多租户**隔离、**工具管理**、
**API 密钥管理**、**OpenTelemetry** 链路追踪。

---

## 🧱 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3、Vite 5、TypeScript、Pinia、Vue Router、Ant Design Vue、ECharts、vue-flow、vue-i18n |
| 后端 | FastAPI 0.115+、SQLAlchemy 2.0、PostgreSQL、Redis、Pydantic v2、python-jose（JWT） |
| AI 核心 | **AgentScope 2.0.7**（多智能体 / Agent Team）、MCP 协议、知识库（pgvector + 向量嵌入）、本体推理（OWL / SPARQL / Prolog / 模糊） |
| 自动化 | APScheduler、ARQ、Celery |
| 语音（可选） | ASR / TTS + WebSocket 全双工流式 |
| 基础设施 | Docker、Docker Compose |
| 可观测性 | OpenTelemetry（console / Jaeger / OTLP） |

> 可选集成：内置 `dify_client`，用于与 Dify 工作流互通。

---

## 📂 项目结构

```
MinWorkBuddy/
├── backend/                        # FastAPI 后端
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口（路由注册、生命周期）
│   │   ├── config.py               # 配置（pydantic-settings）
│   │   ├── deps.py                 # 依赖注入
│   │   ├── ai/                     # AI 编排层（基于 AgentScope）
│   │   │   ├── agent_factory.py    # 智能体构建
│   │   │   ├── team_manager.py     # AgentTeam 管理
│   │   │   ├── embedding_client.py # 知识库向量嵌入
│   │   │   ├── dify_client.py      # （可选）Dify 互通
│   │   │   ├── sse.py / sse_bridge.py
│   │   │   ├── knowledge/          # 知识库 + 本体推理
│   │   │   ├── research/           # 深度思考 / 深度研究
│   │   │   ├── skills/             # 技能插件系统
│   │   │   ├── team/               # AgentTeam 专家组
│   │   │   ├── mcp/                # MCP 客户端与服务端
│   │   │   ├── memory/             # 对话记忆
│   │   │   ├── web_search/         # 联网搜索 grounding
│   │   │   ├── tool_manager/       # 工具注册与执行
│   │   │   ├── workspace/          # 工作空间管理
│   │   │   └── telemetry/          # OpenTelemetry
│   │   ├── models/                 # SQLAlchemy ORM 模型
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── routers/                # API 路由（/api/v1/*）
│   │   │   ├── auth.py             # 认证
│   │   │   ├── admin.py            # 管理 + 租户 + 密钥 + 工具 + MCP
│   │   │   ├── dictionary.py       # 字典
│   │   │   ├── agent/              # Agent / Team / 定时任务
│   │   │   ├── ai/                 # AI Agent 执行、技能、对话、工作空间
│   │   │   ├── sys/                # 系统（通知等）
│   │   │   └── wiki/               # 知识空间
│   │   ├── services/               # 业务逻辑
│   │   ├── middleware/             # 中间件（JWT 认证、租户、审计）
│   │   ├── core/                   # 横切工具
│   │   └── db/                     # 数据库引擎 + Alembic 迁移
│   ├── alembic/                    # 迁移脚本
│   ├── tests/                      # 后端测试
│   ├── Dockerfile(.dev/.prod)
│   ├── env.example                 # 环境变量模板
│   └── requirements*.txt
├── frontend/                       # Vue 3 前端（miniworkbuddy-frontend）
│   ├── src/                        # 源代码
│   ├── scripts/                    # 构建脚本
│   └── package.json
├── docs/                           # 文档
├── logs/、scripts/
└── docker-compose.{dev,infra,prod}.yml
```

---

## 🚀 快速开始

### 环境要求

- **Node.js** ≥ 18
- **Python** ≥ 3.11
- **Docker** 与 **Docker Compose**（推荐），或本地 PostgreSQL + Redis

### 方式一 —— Docker Compose（推荐）

```bash
# 1. 准备环境配置
cp backend/env.example backend/.env
#    然后修改密钥（JWT_SECRET_KEY、ENCRYPTION_KEY、AgentScope/LLM 密钥等）

# 2. 启动完整服务（postgres + redis + backend + frontend）
docker compose -f docker-compose.dev.yml up -d --build
```

- 前端：http://localhost:3000
- 后端 API 与文档：http://localhost:8000/docs （ReDoc：http://localhost:8000/redoc）
- MCP 服务端端点：`http://localhost:8000/mcp`

### 方式二 —— 本地运行

**后端**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows：.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp env.example .env                  # 按需修改

# 执行数据库迁移（如使用 Alembic）
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端**

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
npm run dev                         # 开发服务器 http://localhost:3000
```

---

## ⚙️ 配置说明

后端配置位于 `backend/.env`（由 `backend/env.example` 复制而来）。主要配置分组：

| 分组 | 关键变量 |
|------|----------|
| 应用 / 服务器 | `APP_NAME`、`APP_VERSION`、`ENVIRONMENT`、`DEBUG`、`API_PREFIX`、`CORS_ORIGINS`、`HOST`、`PORT` |
| 数据库 | `DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`、`DB_POOL_SIZE` |
| Redis | `REDIS_HOST`、`REDIS_PORT`、`REDIS_PASSWORD`、`CACHE_EXPIRE_TIME` |
| JWT | `JWT_SECRET_KEY`、`JWT_ALGORITHM`、`JWT_ACCESS_TOKEN_EXPIRE_MINUTES` |
| 数据加密 | `ENCRYPTION_KEY`（32 字节 AES-256）、`ENCRYPTION_ALGORITHM` |
| AgentScope / 大模型 | AgentScope 运行时的模型 / API 地址 / API 密钥配置 |
| 知识库 | 向量嵌入相关（`EMBEDDING_*`、向量库连接） |
| 本体 | 本体存储配置（OWL / RDF / Prolog / 模糊） |
| MCP | `MCP_*` 客户端与服务端配置 |
| 联网搜索 | `BOCHA_*`、`SHUYAN_*`、`ANSPIRE_*`、`FIRECRAWL_*`（各含 `*_ENABLED` 开关） |
| 定时任务 | `SCHEDULER_ENABLED`、`SCHEDULER_TIMEZONE` 等 |
| 语音（AI 客服） | 全双工对话的 ASR / TTS 服务商配置 |
| 安全 | `RATE_LIMIT_PER_MINUTE`、`MAX_LOGIN_ATTEMPTS`、`CSRF_ENABLED`、`XSS_PROTECTION`、`CSP_ENABLED` |
| 可观测性 | `OTEL_ENABLED`、`OTEL_EXPORTER`（console | jaeger | otlp） |

前端读取 `VITE_API_BASE_URL`（开发环境默认 `http://localhost:8000`）。

> ⚠️ 任何非本地部署前，请务必修改 `JWT_SECRET_KEY` 与 `ENCRYPTION_KEY`。

---

## 🗄️ 数据库迁移

表结构由 **Alembic** 管理（开发环境也可通过 `AUTO_CREATE_TABLES` 自动建表）。

```bash
cd backend
alembic upgrade head                              # 应用全部迁移
alembic revision --autogenerate -m "变更说明"      # 生成新迁移
```

---

## 🔌 API 接口

后端在 `/api/v1` 下提供 REST API，并在 `/mcp` 挂载 MCP 服务端。主要路由分组
（完整字段见 `/docs`）：

| 模块 | 路由前缀 | 说明 |
|------|----------|------|
| 认证 | `/api/v1/auth` | 登录、令牌刷新、用户认证 |
| 管理 | `/api/v1/admin` | 用户、角色、租户与套餐、API 密钥、工具/MCP 管理、通知 |
| 字典 | `/api/v1/dictionary` | 系统字典 |
| AI Agent（统一执行） | `/api/v1`（`ai_agent`） | AI Agent 统一执行入口 |
| Agent / 配置 / 执行 | `/api/v1`（`agent*`） | 单个 Agent 专家、配置、执行历史 |
| AgentTeam | `/api/v1`（`agent_team`） | 多智能体专家组 |
| Agent 定时任务 | `/api/v1`（`agent_scheduled_task`） | 自动化调度 |
| 技能 | `/api/v1/ai-assistant/skills` | 技能插件注册 |
| AI 会话 | `/api/v1/admin`（`ai_chat`） | 对话 / 会话管理 |
| 工作空间 | `/api/v1`（`workspace`） | 工作空间管理 |
| Wiki / 知识 | `/api/v1/wiki` | 知识空间 |
| 系统 | `/api/v1/admin`（`sys`） | 通知等 |
| MCP 服务端 | `/mcp` | 供外部 MCP Client 连接的 Streamable HTTP / SSE 端点 |

交互式文档：**Swagger UI** 位于 `/docs`，**ReDoc** 位于 `/redoc`。

---

## 🤖 AI 编排

基于 **AgentScope 2.0.7** 构建：

- **Agent 专家** —— 可配置的单个智能体（人设、工具、模型）。
- **AgentTeam 专家组** —— 多个智能体协作完成任务的团队
  （`ai/team/` + `team_manager.py`）。
- **技能系统** —— 带规则触发与自我进化的插件技能（`ai/skills/`）。
- **深度思考 / 深度研究** —— `ai/research/` 规划并执行多步推理与联网研究。
- **知识库 + 本体** —— `ai/knowledge/` 将向量检索与 OWL/RDF/Prolog/模糊本体推理结合。
- **MCP 生态** —— `ai/mcp/` 同时提供 MCP 客户端与服务端端点（`/mcp`），可接入外部工具。
- **工具管理** —— `ai/tool_manager/` 注册并执行工具。
- **（可选）Dify** —— `dify_client.py` 用于与 Dify 工作流互通。

---

## 🛠️ 开发指南

**后端**

```bash
cd backend
pytest                              # 运行测试
black . && isort .                 # 格式化（PEP 8）
```

编码规范：遵循 PEP 8；所有函数添加类型注解；使用 Pydantic 校验；
`HTTPException` 抛出错误；统一错误格式；结构化日志记录。

**前端**

```bash
cd frontend
npm run lint                        # ESLint 自动修复
npm run build                      # 生产构建（node scripts/build.cjs production）
npm run build:daily                # daily 渠道构建
```

编码规范：ESLint + TypeScript strict、Composition API、Pinia 状态管理、`vue-i18n` 国际化。

---

## 📦 部署

**生产环境（Docker Compose）**

```bash
cp backend/env.example backend/.env     # 配置生产密钥
docker compose -f docker-compose.prod.yml up -d --build
```

**仅后端（gunicorn）**

```bash
cd backend
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

> 启用 HTTPS：设置 `HTTPS_ENABLED=True` 并配置 `SSL_CERT_PATH` / `SSL_KEY_PATH`。

---

## 📄 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
