# MiniWorkBuddy - 后端工程

> 基于 FastAPI + PostgreSQL + LangGraph + Dify

## 技术栈

- **框架**: FastAPI 0.110+
- **数据库**: PostgreSQL 15+ (SQLAlchemy ORM)
- **缓存**: Redis 7+
- **AI 编排**: LangGraph + Dify
- **任务调度**: APScheduler
- **认证**: JWT (python-jose)
- **密码加密**: bcrypt
- **数据验证**: Pydantic V2

## 项目结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── deps.py                 # 依赖注入
│   ├── middleware/             # 中间件
│   │   ├── auth.py             # JWT 认证
│   │   └── region_filter.py    # 地区权限过滤
│   ├── models/                 # SQLAlchemy ORM 模型
│   ├── schemas/                # Pydantic 请求/响应模型
│   ├── routers/                # API 路由
│   ├── services/               # 业务逻辑层
│   ├── ai/                     # AI 编排层
│   │   ├── dify_client.py      # Dify API 客户端
│   │   ├── langgraph/          # LangGraph DAG 定义
│   │   └── sse.py              # SSE 流式输出
│   ├── tasks/                  # 定时任务
│   └── db/
│       ├── database.py         # 数据库连接
│       └── migrations/         # Alembic 迁移
├── requirements.txt
├── alembic.ini
├── .env
└── README.md
```

## 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

已创建 `.env` 文件，数据库连接配置如下：

```env
DATABASE_URL=postgresql://postgres:postgres@2026!@192.168.100.80:5432/miniworkbuddy
```

如需修改其他配置，请编辑 `.env` 文件

### 数据库迁移

```bash
# 初始化迁移
alembic init alembic

# 生成迁移文件
alembic revision --autogenerate -m "Initial migration"

# 执行迁移
alembic upgrade head
```

### 运行开发服务器

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 API 文档：http://localhost:8000/docs

## API 接口

### 接口总览

- **用户认证**: `/api/v1/auth/*` (5个接口)
- **总体态势**: `/api/v1/overview/*` (4个接口)
- **全量汇聚**: `/api/v1/aggregation/*` (5个接口)
- **协同处置**: `/api/v1/disposal-collab/*` (6个接口)
- **风险识别**: `/api/v1/risk-identification/*` (4个接口)
- **重点风险**: `/api/v1/key-risks/*` (1个接口)
- **智能报表**: `/api/v1/smart-report/*` (8个接口)
- **推演模块**: `/api/v1/deduction/*` (11个接口)
- **复盘模块**: `/api/v1/review/*` (7个接口)
- **风险人员**: `/api/v1/persons/*` (6个接口)
- **风险事件**: `/api/v1/events/*` (5个接口)
- **处置管理**: `/api/v1/disposal/*` (7个接口)
- **事件聚类**: `/api/v1/cluster/*` (5个接口)
- **AI助理**: `/api/v1/ai-assistant/*` (4个接口)
- **管理员**: `/api/v1/admin/*` (21个接口)
- **系统管理**: `/api/v1/sys/*` (5个接口)

**合计**: 102 个接口

## AI 编排

### Dify 工作流 (11条)

- W1: 统计指标AI分析（通用复用）
- W2-W4: 智能报表生成（全量汇聚/协同处置/风险识别）
- W5-W7: 定时报表（日报/周报/月报）
- W8: 专报生成（含RAG）
- W9: 处置闭环分析报告
- W10: 详情页AI处置建议
- D1: 报表继续追问（对话型）
- A1: AI助理Agent（ReAct）

### LangGraph DAG (6条)

- L1: 事件推演分析
- L2: 处置路径推演
- L3: 处置措施快速评估
- L4: 历史事件深度复盘
- L5: 原始数据风险评级（定时任务）
- L6: 事件聚类分析（定时任务）

## 开发规范

### 代码风格

- 遵循 PEP 8 规范
- 使用 Black 格式化代码
- 使用 isort 排序导入

### 类型注解

- 所有函数必须添加类型注解
- 使用 Pydantic 进行数据验证

### 错误处理

- 使用 HTTPException 抛出 HTTP 错误
- 统一错误响应格式

### 日志记录

- 使用 Python logging 模块
- 记录关键操作和错误信息

## 部署

### Docker 部署

```bash
docker build -t miniworkbuddy-backend .
docker run -d -p 8000:8000 miniworkbuddy-backend
```

### 生产环境

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

## License

Copyright © 2026
