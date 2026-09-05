<p align="center">
  <a href="readme_cn.md">
    <img src="https://img.shields.io/badge/简体中文-点击查看-blue?style=for-the-badge" alt="简体中文">
  </a>
</p>

# MiniWorkBuddy

> A lightweight, general-purpose **AI workbench** inspired by Tencent WorkBuddy,
> built on **AgentScope 2.0.7**.
>
> Multi-agent collaboration, skill plugins, deep research, a knowledge base with
> ontology reasoning, full-duplex text/voice conversation, and automated scheduling —
> all in one extensible platform.

MiniWorkBuddy is a full-stack intelligent workspace. The **frontend** is a Vue 3
workbench with agent/orchestration visualization, rich charts, and Markdown/code
rendering. The **backend** is a FastAPI service whose AI layer is powered by
[AgentScope 2.0.7](https://github.com/modelscope/agentscope): it runs individual
**Agent experts**, **AgentTeam expert groups**, a **skill** plugin system, **deep
thinking / deep research**, a vector **knowledge base** plus **ontology** reasoning,
and **full-duplex text/voice AI customer service**, with **automated scheduling**.

---

## ✨ Features

1. **AI Conversation** — Multi-turn chat with Server-Sent Events (SSE) streaming,
   conversation memory, and context management.
2. **Deep Thinking** — A step-by-step reasoning mode for careful, transparent answers.
3. **Deep Research** — Autonomous multi-step research (`research/` module): planning,
   web search, knowledge synthesis, and citation-backed reports.
4. **Skills** — A plugin-style **skill** system (`skills/`) with skill rules and
   skill-evolution for self-improving capabilities.
5. **Agent Experts** — Configure and run individual specialized agents (`agent/`
   module), with agent config and execution history.
6. **AgentTeam Expert Groups** — Multi-agent **teams** (`team/` module) that
   collaborate to solve complex problems.
7. **Automated Scheduling** — Schedule agents/skills/tasks to run automatically via
   `agent_scheduled_task` + APScheduler / ARQ / Celery.
8. **Full-duplex Text/Voice AI Customer Service** — Duplex conversation over
   WebSocket streaming with ASR/TTS for seamless text **and** voice interaction.
9. **Knowledge Base** — Vector knowledge base (pgvector + embeddings) with retrieval,
   plus a `wiki/` knowledge space and web-search grounding.
10. **Ontology** — Domain **ontology** reasoning (OWL / RDF(SPARQL) / Prolog / Fuzzy)
    for structured, rule-based inference over the knowledge base.

Additional platform capabilities: **MCP** tool ecosystem (MCP client + server
endpoint), **multi-tenant** isolation, **tool management**, **API-key management**,
and **OpenTelemetry** tracing.

---

## 🧱 Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Vue 3, Vite 5, TypeScript, Pinia, Vue Router, Ant Design Vue, ECharts, vue-flow, vue-i18n |
| Backend | FastAPI 0.115+, SQLAlchemy 2.0, PostgreSQL, Redis, Pydantic v2, python-jose (JWT) |
| AI Core | **AgentScope 2.0.7** (multi-agent, Agent Team), MCP protocol, knowledge base (pgvector + embeddings), ontology reasoning (OWL / SPARQL / Prolog / Fuzzy) |
| Automation | APScheduler, ARQ, Celery |
| Voice (optional) | ASR / TTS + WebSocket duplex streaming |
| Infra | Docker, Docker Compose |
| Observability | OpenTelemetry (console / Jaeger / OTLP) |

> Optional integration: a `dify_client` is included for Dify workflow interoperability.

---

## 📂 Project Structure

```
MinWorkBuddy/
├── backend/                        # FastAPI backend
│   ├── app/
│   │   ├── main.py                 # FastAPI entrypoint (router registration, lifespan)
│   │   ├── config.py               # Settings (pydantic-settings)
│   │   ├── deps.py                 # Dependency injection
│   │   ├── ai/                     # AI orchestration layer (AgentScope-based)
│   │   │   ├── agent_factory.py    # Agent construction
│   │   │   ├── team_manager.py     # AgentTeam management
│   │   │   ├── embedding_client.py # Embedding for knowledge base
│   │   │   ├── dify_client.py      # (optional) Dify interop
│   │   │   ├── sse.py / sse_bridge.py
│   │   │   ├── knowledge/          # Knowledge base + ontology reasoning
│   │   │   ├── research/           # Deep thinking / deep research
│   │   │   ├── skills/             # Skill plugin system
│   │   │   ├── team/               # AgentTeam expert groups
│   │   │   ├── mcp/                # MCP client & server
│   │   │   ├── memory/             # Conversation memory
│   │   │   ├── web_search/         # Web search grounding
│   │   │   ├── tool_manager/       # Tool registry & execution
│   │   │   ├── workspace/          # Workspace management
│   │   │   └── telemetry/          # OpenTelemetry
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── routers/                # API routes (/api/v1/*)
│   │   │   ├── auth.py             # Authentication
│   │   │   ├── admin.py            # Admin + tenant + keys + tools + MCP
│   │   │   ├── dictionary.py       # Dictionaries
│   │   │   ├── agent/              # Agent / Team / scheduled tasks
│   │   │   ├── ai/                 # AI Agent execution, skills, chat, workspace
│   │   │   ├── sys/                # System (notifications, ...)
│   │   │   └── wiki/               # Knowledge-space
│   │   ├── services/               # Business logic
│   │   ├── middleware/             # Auth (JWT), tenant, audit
│   │   ├── core/                   # Cross-cutting utilities
│   │   └── db/                     # DB engine + Alembic migrations
│   ├── alembic/                    # Migration scripts
│   ├── tests/                      # Backend tests
│   ├── Dockerfile(.dev/.prod)
│   ├── env.example                 # Environment template
│   └── requirements*.txt
├── frontend/                       # Vue 3 frontend (miniworkbuddy-frontend)
│   ├── src/                        # Source code
│   ├── scripts/                    # Build scripts
│   └── package.json
├── docs/                           # Documentation
├── logs/, scripts/
└── docker-compose.{dev,infra,prod}.yml
```

---

## 🚀 Quick Start

### Prerequisites

- **Node.js** ≥ 18
- **Python** ≥ 3.11
- **Docker** & **Docker Compose** (recommended), or local PostgreSQL + Redis

### Option A — Docker Compose (recommended)

```bash
# 1. Prepare environment
cp backend/env.example backend/.env
#    then edit secrets (JWT_SECRET_KEY, ENCRYPTION_KEY, AgentScope/LLM keys, ...)

# 2. Start the full stack (postgres + redis + backend + frontend)
docker compose -f docker-compose.dev.yml up -d --build
```

- Frontend:  http://localhost:3000
- Backend API + Docs: http://localhost:8000/docs  (ReDoc: http://localhost:8000/redoc)
- MCP Server endpoint:  `http://localhost:8000/mcp`

### Option B — Run locally

**Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp env.example .env                  # edit as needed

# Apply database migrations (if using Alembic)
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
npm run dev                         # dev server on http://localhost:3000
```

---

## ⚙️ Configuration

Backend configuration lives in `backend/.env` (copy from `backend/env.example`).
Key groups:

| Group | Key variables |
|-------|---------------|
| App / Server | `APP_NAME`, `APP_VERSION`, `ENVIRONMENT`, `DEBUG`, `API_PREFIX`, `CORS_ORIGINS`, `HOST`, `PORT` |
| Database | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_POOL_SIZE` |
| Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `CACHE_EXPIRE_TIME` |
| JWT | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` |
| Encryption | `ENCRYPTION_KEY` (32-byte AES-256), `ENCRYPTION_ALGORITHM` |
| AgentScope / LLM | model / API-base / API-key settings for the AgentScope runtime |
| Knowledge Base | pgvector / embedding settings (`EMBEDDING_*`, vector store connection) |
| Ontology | ontology store settings (OWL / RDF / Prolog / Fuzzy) |
| MCP | `MCP_*` client & server settings |
| Web Search | `BOCHA_*`, `SHUYAN_*`, `ANSPIRE_*`, `FIRECRAWL_*` (each with `*_ENABLED`) |
| Scheduler | `SCHEDULER_ENABLED`, `SCHEDULER_TIMEZONE`, ... |
| Voice (AI客服) | ASR / TTS provider settings for full-duplex conversation |
| Security | `RATE_LIMIT_PER_MINUTE`, `MAX_LOGIN_ATTEMPTS`, `CSRF_ENABLED`, `XSS_PROTECTION`, `CSP_ENABLED` |
| Observability | `OTEL_ENABLED`, `OTEL_EXPORTER` (console | jaeger | otlp) |

The frontend reads `VITE_API_BASE_URL` (default `http://localhost:8000` in dev).

> ⚠️ Change `JWT_SECRET_KEY` and `ENCRYPTION_KEY` before any non-local deployment.

---

## 🗄️ Database Migrations

Schema is managed with **Alembic** (development environments can also auto-create
tables via `AUTO_CREATE_TABLES`).

```bash
cd backend
alembic upgrade head                              # apply all migrations
alembic revision --autogenerate -m "describe change"   # generate a new migration
```

---

## 🔌 API

The backend exposes its REST API under `/api/v1` and mounts an MCP server at `/mcp`.
Major router groups (see `/docs` for the full schema):

| Module | Prefix | Purpose |
|--------|--------|---------|
| Auth | `/api/v1/auth` | Login, token refresh, user auth |
| Admin | `/api/v1/admin` | Users, roles, tenant & packages, API keys, tool/MCP management, notifications |
| Dictionary | `/api/v1/dictionary` | System dictionaries |
| AI Agent (unified) | `/api/v1` (`ai_agent`) | Unified agent execution entrypoint |
| Agent / Config / Execution | `/api/v1` (`agent*`) | Individual Agent experts, config, run history |
| AgentTeam | `/api/v1` (`agent_team`) | Multi-agent expert groups |
| Agent Scheduled Task | `/api/v1` (`agent_scheduled_task`) | Automated scheduling |
| Skills | `/api/v1/ai-assistant/skills` | Skill plugin registry |
| AI Session | `/api/v1/admin` (`ai_chat`) | Conversation / session management |
| Workspace | `/api/v1` (`workspace`) | Workspace management |
| Wiki / Knowledge | `/api/v1/wiki` | Knowledge-space |
| System | `/api/v1/admin` (`sys`) | Notifications, etc. |
| MCP Server | `/mcp` | Streamable HTTP / SSE endpoint for MCP clients |

Interactive docs: **Swagger UI** at `/docs`, **ReDoc** at `/redoc`.

---

## 🤖 AI Orchestration

Built on **AgentScope 2.0.7**:

- **Agent Experts** — configurable individual agents (persona, tools, model).
- **AgentTeam Expert Groups** — teams of agents collaborating on a task
  (`ai/team/` + `team_manager.py`).
- **Skill system** — plugin skills with rule-based triggering and self-evolution
  (`ai/skills/`).
- **Deep Thinking / Deep Research** — `ai/research/` plans and executes multi-step
  reasoning and web-grounded research.
- **Knowledge Base + Ontology** — `ai/knowledge/` combines vector retrieval with
  OWL/RDF/Prolog/Fuzzy ontology reasoning.
- **MCP ecosystem** — `ai/mcp/` provides both an MCP client and a server endpoint
  (`/mcp`) so external tools can be plugged in.
- **Tool management** — `ai/tool_manager/` registers and executes tools.
- **(Optional) Dify** — `dify_client.py` for Dify workflow interop.

---

## 🛠️ Development

**Backend**

```bash
cd backend
pytest                              # run tests
black . && isort .                 # format (PEP 8)
```

Conventions: PEP 8, full type annotations, Pydantic for validation,
`HTTPException` for errors, unified error format, structured logging.

**Frontend**

```bash
cd frontend
npm run lint                        # ESLint with --fix
npm run build                      # production build (node scripts/build.cjs production)
npm run build:daily                # daily-channel build
```

Conventions: ESLint + TypeScript strict, Composition API, Pinia stores, `vue-i18n` for i18n.

---

## 📦 Deployment

**Production (Docker Compose)**

```bash
cp backend/env.example backend/.env     # set production secrets
docker compose -f docker-compose.prod.yml up -d --build
```

**Backend only (gunicorn)**

```bash
cd backend
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

> For HTTPS, set `HTTPS_ENABLED=True` and provide `SSL_CERT_PATH` / `SSL_KEY_PATH`.

---

## 📄 License

Released under the [MIT License](LICENSE).
