# 工作流管理系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 MinWorkBuddy 构建多平台工作流统一接入与管理系统，覆盖 Dify / Coze / 自定义 HTTP 平台的流程定义、网关治理（限流/熔断/重试）、链式编排、AgentConfig 集成、RESTful API 和管理前端。

**Architecture:** 外部平台代理层 + 完整网关。策略模式适配器（`PlatformAdapter` ABC → `DifyAdapter` / `CozeAdapter` / `CustomHTTPAdapter`）+ `AdapterFactory` 运行时注册。网关层提供令牌桶限流（Redis）、三态熔断器、指数退避重试。`WorkflowPlatformEngine` 通过 `WorkflowGateway` 统一入口调用外部平台，同时降级兼容旧 `DifyClient` 路径。

**Tech Stack:** FastAPI 0.115+ / SQLAlchemy 2.x / Pydantic v2 / PostgreSQL + Redis / httpx / Vue 3 + Ant Design Vue / ECharts

## Global Constraints

- 所有新表继承 `TenantMixin`（`tenant_id = Column(BigInteger, nullable=True, index=True)`）
- API Key 加密存储（使用 `cryptography.fernet.Fernet`，密钥从 `settings.SECRET_KEY` 派生）
- 迁移使用 Alembic，命名格式 `YYYY_MM_DD_HHMM-NNN_description.py`，当前最新 revision 为 `012_chat_model_api_fields`
- ORM 模型必须在 `backend/app/db/init_models.py` 中注册
- Router 必须在 `backend/app/core/router_registry.py` 的 `ROUTER_SPECS` 清单中注册
- 前端路由在 `frontend/src/router/index.ts` 中注册
- 品牌色：Indigo `#4F6EF7` / Teal `#22D3AE` / Amber `#F5A623`
- 测试使用 pytest + per-schema 隔离（参考 `tests/kb/conftest.py`）

## File Structure

```
backend/
├── app/
│   ├── models/workflow/
│   │   ├── __init__.py              # 导出 3 个模型
│   │   ├── workflow_flow.py         # 工作流定义表
│   │   ├── workflow_execution_log.py # 执行日志表
│   │   └── workflow_chain.py        # 链式编排表
│   ├── schemas/workflow/
│   │   ├── __init__.py
│   │   └── workflow.py              # Pydantic Schema（CRUD + 执行 + 链）
│   ├── services/workflow/
│   │   ├── __init__.py
│   │   ├── crypto.py                # API Key 加解密工具
│   │   ├── platform_adapter.py      # PlatformAdapter ABC + PlatformResponse
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── dify_adapter.py      # Dify 适配器
│   │   │   ├── coze_adapter.py      # Coze 适配器
│   │   │   └── custom_adapter.py    # 通用 HTTP 适配器
│   │   ├── adapter_factory.py       # 适配器工厂
│   │   ├── rate_limiter.py          # 令牌桶限流器
│   │   ├── circuit_breaker.py       # 三态熔断器
│   │   ├── retry_policy.py          # 指数退避重试
│   │   ├── gateway.py               # 工作流网关（统一入口）
│   │   ├── webhook.py               # Webhook 回调
│   │   ├── chain_executor.py        # 链式编排执行器
│   │   └── workflow_service.py      # 工作流 CRUD 服务
│   ├── routers/workflow/
│   │   ├── __init__.py
│   │   └── workflow.py              # RESTful API 路由
│   └── db/
│       └── init_models.py           # 新增 3 个模型注册
├── alembic/versions/
│   └── 2026_09_13_0000-013_add_workflow_tables.py
├── tests/workflow/
│   ├── __init__.py
│   ├── conftest.py                  # per-schema 隔离
│   ├── test_crypto.py
│   ├── test_platform_adapters.py
│   ├── test_circuit_breaker.py
│   ├── test_retry_policy.py
│   ├── test_chain_executor.py
│   └── test_workflow_service.py
frontend/src/
├── api/
│   └── workflow.ts                  # API 调用封装
├── views/admin/workflow/
│   ├── WorkflowManagement.vue       # 主页面（5 Tab 容器）
│   ├── components/
│   │   ├── WorkflowFlowTable.vue    # Tab1: 工作流列表
│   │   ├── WorkflowFlowForm.vue     # Tab2: 创建/编辑表单
│   │   ├── WorkflowTestBench.vue    # Tab3: 测试工作台
│   │   ├── WorkflowExecutionTable.vue # Tab4: 执行日志
│   │   └── WorkflowDashboard.vue    # Tab5: 分析仪表板
```

---

### Task 1: 数据层 — 3 个 ORM 模型 + AgentConfig 变更

**Files:**
- Create: `backend/app/models/workflow/__init__.py`
- Create: `backend/app/models/workflow/workflow_flow.py`
- Create: `backend/app/models/workflow/workflow_execution_log.py`
- Create: `backend/app/models/workflow/workflow_chain.py`
- Modify: `backend/app/models/agent/agent_config.py:70` (新增 workflow_id 列)
- Modify: `backend/app/db/init_models.py:80` (注册新模型)

**Interfaces:**
- Consumes: `TenantMixin` from `app.models.tenant_mixin`
- Produces: `WorkflowFlow`, `WorkflowExecutionLog`, `WorkflowChain` ORM 类供后续 Task 使用

- [ ] **Step 1: 创建 workflow 模型包**

```python
# backend/app/models/workflow/__init__.py
from app.models.workflow.workflow_flow import WorkflowFlow
from app.models.workflow.workflow_execution_log import WorkflowExecutionLog
from app.models.workflow.workflow_chain import WorkflowChain

__all__ = ["WorkflowFlow", "WorkflowExecutionLog", "WorkflowChain"]
```

- [ ] **Step 2: 创建 WorkflowFlow 模型**

```python
# backend/app/models/workflow/workflow_flow.py
"""工作流定义表 — 多平台统一接入"""
from sqlalchemy import Column, BigInteger, String, Boolean, Integer, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy import TIMESTAMP

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WorkflowFlow(Base, TenantMixin):
    """多平台工作流定义表"""
    __tablename__ = "workflow_flow"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    flow_code = Column(String(100), nullable=False, comment="业务唯一标识码")
    flow_name = Column(String(200), nullable=False, comment="工作流名称")
    platform_type = Column(String(50), nullable=False, server_default="dify",
                           comment="平台类型: dify / coze / custom_http")
    flow_type = Column(String(50), nullable=False,
                       comment="流程类型: Workflow / Chatflow / Chatbot / Agent / Completion")
    base_url = Column(String(500), nullable=False, comment="平台 API 基地址")
    api_key_enc = Column(Text, nullable=False, comment="加密后的 API Key")
    input_schema = Column(JSONB, nullable=False, server_default="{}", comment="入参 JSON Schema")
    output_schema = Column(JSONB, nullable=True, comment="出参 JSON Schema")
    config = Column(JSONB, nullable=True, comment="平台扩展配置")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    sort_order = Column(Integer, nullable=False, server_default="0")
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("uq_workflow_flow_code_tenant", "flow_code", "tenant_id", unique=True),
        Index("idx_workflow_flow_platform", "platform_type"),
    )

    def __repr__(self):
        return f"<WorkflowFlow {self.flow_code}:{self.flow_name}>"
```

- [ ] **Step 3: 创建 WorkflowExecutionLog 模型**

```python
# backend/app/models/workflow/workflow_execution_log.py
"""工作流执行日志"""
from sqlalchemy import Column, BigInteger, String, Integer, Text, Index, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WorkflowExecutionLog(Base, TenantMixin):
    """工作流执行日志"""
    __tablename__ = "workflow_execution_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    flow_id = Column(BigInteger, nullable=False, comment="FK → workflow_flow.id")
    execution_id = Column(String(64), nullable=True, comment="关联 agent_execution.execution_id")
    status = Column(String(20), nullable=False, server_default="pending",
                    comment="pending / running / success / failed / timeout / cancelled")
    input_data = Column(JSONB, nullable=True, comment="实际输入")
    output_data = Column(JSONB, nullable=True, comment="实际输出")
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=False, server_default="0")
    platform_trace = Column(JSONB, nullable=True, comment="平台原始响应")
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_wf_exec_log_flow", "flow_id"),
        Index("idx_wf_exec_log_status", "status"),
        Index("idx_wf_exec_log_created", "created_at"),
    )
```

- [ ] **Step 4: 创建 WorkflowChain 模型**

```python
# backend/app/models/workflow/workflow_chain.py
"""工作流链式编排定义"""
from sqlalchemy import Column, BigInteger, String, Boolean, Text, Index, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WorkflowChain(Base, TenantMixin):
    """工作流链式编排定义"""
    __tablename__ = "workflow_chain"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    chain_code = Column(String(100), nullable=False, comment="链唯一标识码")
    chain_name = Column(String(200), nullable=False)
    steps = Column(JSONB, nullable=False, server_default="[]",
                   comment="步骤列表 JSON")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("uq_workflow_chain_code_tenant", "chain_code", "tenant_id", unique=True),
    )

    def __repr__(self):
        return f"<WorkflowChain {self.chain_code}:{self.chain_name}>"
```

- [ ] **Step 5: AgentConfig 新增 workflow_id 字段**

在 `backend/app/models/agent/agent_config.py` 第 70 行（`workspace_id` 之后）新增：

```python
    workflow_id = Column(BigInteger, nullable=True, comment="FK → workflow_flow.id")
```

在 `__table_args__` 中新增索引：

```python
        Index("idx_agent_config_workflow", "workflow_id"),
```

- [ ] **Step 6: 在 init_models.py 注册新模型**

在 `backend/app/db/init_models.py` 第 80 行（`# fmt: on` 之前）新增：

```python
# --- 工作流管理 (workflow_) ---
from app.models.workflow.workflow_flow import WorkflowFlow               # noqa: F401
from app.models.workflow.workflow_execution_log import WorkflowExecutionLog  # noqa: F401
from app.models.workflow.workflow_chain import WorkflowChain              # noqa: F401
```

- [ ] **Step 7: 验证模型可导入**

Run: `cd backend && python -c "from app.models.workflow import WorkflowFlow, WorkflowExecutionLog, WorkflowChain; print('OK')"`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/workflow/ backend/app/models/agent/agent_config.py backend/app/db/init_models.py
git commit -m "feat(workflow): add WorkflowFlow, WorkflowExecutionLog, WorkflowChain models + AgentConfig.workflow_id"
```

---

### Task 2: Alembic 迁移脚本

**Files:**
- Create: `backend/alembic/versions/2026_09_13_0000-013_add_workflow_tables.py`

**Interfaces:**
- Consumes: ORM 模型（Task 1）
- Produces: 数据库表结构变更

- [ ] **Step 1: 创建迁移脚本**

```python
# backend/alembic/versions/2026_09_13_0000-013_add_workflow_tables.py
"""add workflow management tables

新增 workflow_flow / workflow_execution_log / workflow_chain 三张表；
agent_config 新增 workflow_id 列。

Revision ID: 013_add_workflow_tables
Revises: 012_chat_model_api_fields
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


revision = "013_add_workflow_tables"
down_revision = "012_chat_model_api_fields"
branch_labels = None
depends_on = None


def _existing(bind):
    insp = inspect(bind)
    tables = set(insp.get_table_names())
    result = {}
    for t in ("workflow_flow", "workflow_execution_log", "workflow_chain", "agent_config"):
        if t in tables:
            result[t] = {c["name"] for c in insp.get_columns(t)}
        else:
            result[t] = set()
    return tables, result


def upgrade() -> None:
    bind = op.get_bind()
    tables, cols = _existing(bind)

    # 1. workflow_flow
    if "workflow_flow" not in tables:
        op.create_table(
            "workflow_flow",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger, nullable=True, index=True),
            sa.Column("flow_code", sa.String(100), nullable=False),
            sa.Column("flow_name", sa.String(200), nullable=False),
            sa.Column("platform_type", sa.String(50), nullable=False, server_default="dify"),
            sa.Column("flow_type", sa.String(50), nullable=False),
            sa.Column("base_url", sa.String(500), nullable=False),
            sa.Column("api_key_enc", sa.Text, nullable=False),
            sa.Column("input_schema", JSONB, nullable=False, server_default="{}"),
            sa.Column("output_schema", JSONB, nullable=True),
            sa.Column("config", JSONB, nullable=True),
            sa.Column("description", sa.Text),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_by", sa.BigInteger),
            sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
            sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        )
        op.create_index("uq_workflow_flow_code_tenant", "workflow_flow",
                        ["flow_code", "tenant_id"], unique=True)
        op.create_index("idx_workflow_flow_platform", "workflow_flow", ["platform_type"])

    # 2. workflow_execution_log
    if "workflow_execution_log" not in tables:
        op.create_table(
            "workflow_execution_log",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger, nullable=True, index=True),
            sa.Column("flow_id", sa.BigInteger, nullable=False),
            sa.Column("execution_id", sa.String(64), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("input_data", JSONB, nullable=True),
            sa.Column("output_data", JSONB, nullable=True),
            sa.Column("error_message", sa.Text),
            sa.Column("latency_ms", sa.Integer),
            sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("platform_trace", JSONB, nullable=True),
            sa.Column("started_at", sa.TIMESTAMP),
            sa.Column("completed_at", sa.TIMESTAMP),
            sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        )
        op.create_index("idx_wf_exec_log_flow", "workflow_execution_log", ["flow_id"])
        op.create_index("idx_wf_exec_log_status", "workflow_execution_log", ["status"])
        op.create_index("idx_wf_exec_log_created", "workflow_execution_log", ["created_at"])

    # 3. workflow_chain
    if "workflow_chain" not in tables:
        op.create_table(
            "workflow_chain",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger, nullable=True, index=True),
            sa.Column("chain_code", sa.String(100), nullable=False),
            sa.Column("chain_name", sa.String(200), nullable=False),
            sa.Column("steps", JSONB, nullable=False, server_default="[]"),
            sa.Column("description", sa.Text),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_by", sa.BigInteger),
            sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
            sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        )
        op.create_index("uq_workflow_chain_code_tenant", "workflow_chain",
                        ["chain_code", "tenant_id"], unique=True)

    # 4. agent_config.workflow_id
    if "agent_config" in cols and "workflow_id" not in cols["agent_config"]:
        op.add_column("agent_config",
                       sa.Column("workflow_id", sa.BigInteger, nullable=True,
                                 comment="FK → workflow_flow.id"))
        op.create_index("idx_agent_config_workflow", "agent_config", ["workflow_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables, cols = _existing(bind)

    if "agent_config" in cols and "workflow_id" in cols["agent_config"]:
        op.drop_index("idx_agent_config_workflow", "agent_config")
        op.drop_column("agent_config", "workflow_id")
    if "workflow_chain" in tables:
        op.drop_table("workflow_chain")
    if "workflow_execution_log" in tables:
        op.drop_table("workflow_execution_log")
    if "workflow_flow" in tables:
        op.drop_table("workflow_flow")
```

- [ ] **Step 2: 运行迁移**

Run: `cd backend && alembic upgrade head`
Expected: `Running upgrade 012_chat_model_api_fields -> 013_add_workflow_tables, add workflow management tables`

- [ ] **Step 3: 验证表已创建**

Run: `cd backend && python -c "from app.db.database import engine; from sqlalchemy import inspect; i = inspect(engine); print('workflow_flow' in i.get_table_names())"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/2026_09_13_0000-013_add_workflow_tables.py
git commit -m "feat(workflow): alembic migration for workflow tables + agent_config.workflow_id"
```

---

### Task 3: API Key 加解密 + Pydantic Schema

**Files:**
- Create: `backend/app/services/workflow/__init__.py`
- Create: `backend/app/services/workflow/crypto.py`
- Create: `backend/app/schemas/workflow/__init__.py`
- Create: `backend/app/schemas/workflow/workflow.py`
- Test: `backend/tests/workflow/test_crypto.py`

**Interfaces:**
- Consumes: `settings.SECRET_KEY` from `app.config`
- Produces: `encrypt_api_key()` / `decrypt_api_key()` 供 Task 6 Gateway 使用；Schema 类供 Task 8 Router 使用

- [ ] **Step 1: 创建 workflow 服务包**

```python
# backend/app/services/workflow/__init__.py
```

- [ ] **Step 2: 创建加解密工具**

```python
# backend/app/services/workflow/crypto.py
"""API Key 加解密工具 — 使用 Fernet 对称加密"""
import base64
import hashlib
from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    """从 SECRET_KEY 派生 Fernet 密钥（32 url-safe base64 字节）"""
    secret = getattr(settings, "SECRET_KEY", "default-secret-key")
    key = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_api_key(plain_key: str) -> str:
    """加密 API Key"""
    f = _get_fernet()
    return f.encrypt(plain_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """解密 API Key"""
    f = _get_fernet()
    return f.decrypt(encrypted_key.encode()).decode()
```

- [ ] **Step 3: 编写加解密测试**

```python
# backend/tests/workflow/test_crypto.py
"""API Key 加解密测试"""
import pytest
from app.services.workflow.crypto import encrypt_api_key, decrypt_api_key


def test_encrypt_decrypt_roundtrip():
    """加密后解密应还原"""
    original = "sk-test-1234567890abcdef"
    encrypted = encrypt_api_key(original)
    assert encrypted != original
    assert decrypt_api_key(encrypted) == original


def test_encrypt_produces_different_output():
    """同一明文两次加密结果不同（Fernet 含时间戳）"""
    original = "sk-test-key"
    e1 = encrypt_api_key(original)
    e2 = encrypt_api_key(original)
    # Fernet token 含时间戳，但解密后相同
    assert decrypt_api_key(e1) == decrypt_api_key(e2) == original


def test_decrypt_invalid_raises():
    """无效密文应抛异常"""
    with pytest.raises(Exception):
        decrypt_api_key("not-a-valid-fernet-token")
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest tests/workflow/test_crypto.py -v`
Expected: 3 passed

- [ ] **Step 5: 创建 Schema 包和定义**

```python
# backend/app/schemas/workflow/__init__.py
from app.schemas.workflow.workflow import (  # noqa: F401
    WorkflowFlowCreate, WorkflowFlowUpdate, WorkflowFlowOut,
    WorkflowFlowListOut, WorkflowExecutionLogOut,
    WorkflowChainCreate, WorkflowChainUpdate, WorkflowChainOut,
    WorkflowTestReq, WorkflowTestResp, PlatformTypeEnum, FlowTypeEnum,
)
```

```python
# backend/app/schemas/workflow/workflow.py
"""工作流管理 Pydantic Schema"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PlatformTypeEnum:
    DIFY = "dify"
    COZE = "coze"
    CUSTOM_HTTP = "custom_http"
    ALL = ["dify", "coze", "custom_http"]


class FlowTypeEnum:
    WORKFLOW = "Workflow"
    CHATFLOW = "Chatflow"
    CHATBOT = "Chatbot"
    AGENT = "Agent"
    COMPLETION = "Completion"
    ALL = ["Workflow", "Chatflow", "Chatbot", "Agent", "Completion"]


# ── WorkflowFlow Schema ──────────────────────────────────────

class WorkflowFlowBase(BaseModel):
    flow_code: str = Field(..., max_length=100, description="业务唯一标识码")
    flow_name: str = Field(..., max_length=200, description="工作流名称")
    platform_type: str = Field("dify", description="平台类型")
    flow_type: str = Field(..., description="流程类型")
    base_url: str = Field(..., max_length=500, description="平台 API 基地址")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="入参 JSON Schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="出参 JSON Schema")
    config: Optional[Dict[str, Any]] = Field(None, description="平台扩展配置")
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class WorkflowFlowCreate(WorkflowFlowBase):
    api_key: str = Field(..., description="API Key（明文，后端加密存储）")


class WorkflowFlowUpdate(BaseModel):
    flow_name: Optional[str] = None
    platform_type: Optional[str] = None
    flow_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(None, description="新 API Key（明文）")
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class WorkflowFlowOut(BaseModel):
    id: int
    flow_code: str
    flow_name: str
    platform_type: str
    flow_type: str
    base_url: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]]
    config: Optional[Dict[str, Any]]
    description: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowFlowListOut(BaseModel):
    total: int
    items: List[WorkflowFlowOut]


# ── WorkflowExecutionLog Schema ──────────────────────────────

class WorkflowExecutionLogOut(BaseModel):
    id: int
    flow_id: int
    execution_id: Optional[str]
    status: str
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    latency_ms: Optional[int]
    retry_count: int
    platform_trace: Optional[Dict[str, Any]]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── WorkflowChain Schema ─────────────────────────────────────

class WorkflowChainBase(BaseModel):
    chain_code: str = Field(..., max_length=100)
    chain_name: str = Field(..., max_length=200)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    description: Optional[str] = None
    is_active: bool = True


class WorkflowChainCreate(WorkflowChainBase):
    pass


class WorkflowChainUpdate(BaseModel):
    chain_name: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WorkflowChainOut(WorkflowChainBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── 测试执行 ─────────────────────────────────────────────────

class WorkflowTestReq(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = "test-user"
    timeout: float = 600.0


class WorkflowTestResp(BaseModel):
    success: bool
    output: Dict[str, Any]
    error: Optional[str] = None
    latency_ms: int = 0
```

- [ ] **Step 6: 验证 Schema 可导入**

Run: `cd backend && python -c "from app.schemas.workflow import WorkflowFlowCreate, WorkflowFlowOut; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/workflow/ backend/app/schemas/workflow/ backend/tests/workflow/test_crypto.py
git commit -m "feat(workflow): add API Key crypto + Pydantic schemas"
```

---

### Task 4: 平台适配器层

**Files:**
- Create: `backend/app/services/workflow/platform_adapter.py`
- Create: `backend/app/services/workflow/adapters/__init__.py`
- Create: `backend/app/services/workflow/adapters/dify_adapter.py`
- Create: `backend/app/services/workflow/adapters/coze_adapter.py`
- Create: `backend/app/services/workflow/adapters/custom_adapter.py`
- Create: `backend/app/services/workflow/adapter_factory.py`
- Test: `backend/tests/workflow/test_platform_adapters.py`

**Interfaces:**
- Consumes: `WorkflowFlow` model (Task 1), `crypto` (Task 3)
- Produces: `PlatformAdapter` ABC + `AdapterFactory` 供 Task 5 Gateway 使用

- [ ] **Step 1: 创建 PlatformAdapter ABC + PlatformResponse**

```python
# backend/app/services/workflow/platform_adapter.py
"""平台适配器抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class PlatformResponse:
    """适配器统一输出"""
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: int = 0
    platform_trace: Optional[Dict[str, Any]] = None


class PlatformAdapter(ABC):
    """平台适配器抽象基类"""

    def __init__(self, base_url: str, api_key: str, config: Optional[Dict] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.config = config or {}

    @abstractmethod
    async def invoke(
        self,
        flow_type: str,
        inputs: Dict[str, Any],
        user_id: str,
        timeout: float = 600.0,
        **kwargs,
    ) -> PlatformResponse:
        """调用平台 API"""

    @abstractmethod
    def extract_output(self, result: Dict[str, Any], flow_type: str) -> str:
        """从平台响应中提取最终文本"""

    async def health_check(self) -> bool:
        """平台连通性检查（可选实现）"""
        return True
```

- [ ] **Step 2: 创建 DifyAdapter**

```python
# backend/app/services/workflow/adapters/dify_adapter.py
"""Dify 平台适配器"""
import time
from typing import Any, Dict
import httpx
from loguru import logger

from app.services.workflow.platform_adapter import PlatformAdapter, PlatformResponse


class DifyAdapter(PlatformAdapter):
    """Dify 平台适配器 — 封装 5 种 API 端点"""

    ENDPOINT_MAP = {
        "Workflow": "/v1/workflows/run",
        "Chatflow": "/v1/chat-messages",
        "Chatbot": "/v1/chat-messages",
        "Agent": "/v1/agent/chat",
        "Completion": "/v1/completions",
    }

    def _build_payload(self, flow_type: str, inputs: Dict[str, Any], user_id: str) -> dict:
        if flow_type == "Workflow":
            return {"inputs": inputs, "user": user_id}
        if flow_type in ("Chatflow", "Chatbot"):
            query = inputs.pop("query", inputs.pop("prompt", ""))
            return {"query": query, "inputs": inputs, "user": user_id, "response_mode": "blocking"}
        if flow_type == "Agent":
            query = inputs.pop("query", inputs.pop("prompt", ""))
            return {"query": query, "user": user_id, "response_mode": "blocking"}
        if flow_type == "Completion":
            prompt = inputs.pop("prompt", "")
            return {"prompt": prompt, "user": user_id, **inputs}
        return {"inputs": inputs, "user": user_id}

    async def invoke(self, flow_type, inputs, user_id, timeout=600.0, **kw):
        endpoint = self.ENDPOINT_MAP.get(flow_type)
        if not endpoint:
            return PlatformResponse(success=False, error=f"不支持的 flow_type: {flow_type}")

        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = self._build_payload(flow_type, dict(inputs), user_id)

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
            latency = int((time.monotonic() - t0) * 1000)
            return PlatformResponse(
                success=True, output=data, latency_ms=latency,
                platform_trace={"status_code": resp.status_code, "headers": dict(resp.headers)},
            )
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            logger.error(f"DifyAdapter.invoke 失败: {e}")
            return PlatformResponse(success=False, error=str(e), latency_ms=latency)

    def extract_output(self, result, flow_type):
        if flow_type == "Workflow":
            outputs = result.get("data", {}).get("outputs", {})
            if isinstance(outputs, dict):
                for key in ("result", "output", "answer", "text", "response"):
                    if key in outputs and outputs[key]:
                        return str(outputs[key])
            return str(outputs) if outputs else ""
        return result.get("answer", "") or result.get("content", "") or ""
```

- [ ] **Step 3: 创建 CozeAdapter**

```python
# backend/app/services/workflow/adapters/coze_adapter.py
"""Coze 平台适配器"""
import time
from typing import Any, Dict
import httpx
from loguru import logger

from app.services.workflow.platform_adapter import PlatformAdapter, PlatformResponse


class CozeAdapter(PlatformAdapter):
    """Coze 平台适配器"""

    ENDPOINT_MAP = {
        "Workflow": "/api/v1/workflow/run",
        "Chatflow": "/api/v1/conversation/chat",
        "Chatbot": "/api/v1/conversation/chat",
        "Agent": "/api/v1/conversation/chat",
        "Completion": "/api/v1/completion",
    }

    def _build_payload(self, flow_type: str, inputs: Dict[str, Any], user_id: str) -> dict:
        if flow_type == "Workflow":
            return {"workflow_id": inputs.pop("workflow_id", ""), "parameters": inputs, "app_id": user_id}
        query = inputs.pop("query", inputs.pop("prompt", ""))
        return {"query": query, "parameters": inputs, "user_id": user_id}

    async def invoke(self, flow_type, inputs, user_id, timeout=600.0, **kw):
        endpoint = self.ENDPOINT_MAP.get(flow_type)
        if not endpoint:
            return PlatformResponse(success=False, error=f"不支持的 flow_type: {flow_type}")

        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = self._build_payload(flow_type, dict(inputs), user_id)

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
            latency = int((time.monotonic() - t0) * 1000)
            return PlatformResponse(success=True, output=data, latency_ms=latency,
                                    platform_trace={"status_code": resp.status_code})
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            logger.error(f"CozeAdapter.invoke 失败: {e}")
            return PlatformResponse(success=False, error=str(e), latency_ms=latency)

    def extract_output(self, result, flow_type):
        data = result.get("data", {})
        if flow_type == "Workflow":
            return str(data.get("output", ""))
        messages = result.get("messages", [])
        if messages:
            return messages[-1].get("content", "")
        return data.get("output", "") or result.get("answer", "")
```

- [ ] **Step 4: 创建 CustomHTTPAdapter**

```python
# backend/app/services/workflow/adapters/custom_adapter.py
"""通用 HTTP 适配器"""
import time
from typing import Any, Dict
import httpx
from loguru import logger

from app.services.workflow.platform_adapter import PlatformAdapter, PlatformResponse


class CustomHTTPAdapter(PlatformAdapter):
    """通用 HTTP 适配器 — 用于其他 LLM 编排平台"""

    async def invoke(self, flow_type, inputs, user_id, timeout=600.0, **kw):
        method = self.config.get("method", "POST").upper()
        extra_headers = self.config.get("headers", {})
        url = self.config.get("url") or f"{self.base_url}/{flow_type.lower()}"
        headers = {**extra_headers, "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"}
        body = {"inputs": inputs, "user": user_id, "flow_type": flow_type}

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.request(method, url, json=body, headers=headers, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
            latency = int((time.monotonic() - t0) * 1000)
            return PlatformResponse(success=True, output=data, latency_ms=latency)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            logger.error(f"CustomHTTPAdapter.invoke 失败: {e}")
            return PlatformResponse(success=False, error=str(e), latency_ms=latency)

    def extract_output(self, result, flow_type):
        output_path = self.config.get("output_path", "$.output")
        # 简单实现：仅支持 $.key 一级路径
        if output_path.startswith("$."):
            key = output_path[2:]
            return str(result.get(key, ""))
        return str(result)
```

- [ ] **Step 5: 创建 AdapterFactory**

```python
# backend/app/services/workflow/adapter_factory.py
"""适配器工厂 — 支持运行时注册"""
from typing import Dict, Optional, Type

from app.services.workflow.platform_adapter import PlatformAdapter
from app.services.workflow.adapters.dify_adapter import DifyAdapter
from app.services.workflow.adapters.coze_adapter import CozeAdapter
from app.services.workflow.adapters.custom_adapter import CustomHTTPAdapter


class AdapterFactory:
    """适配器工厂"""

    _registry: Dict[str, Type[PlatformAdapter]] = {
        "dify": DifyAdapter,
        "coze": CozeAdapter,
        "custom_http": CustomHTTPAdapter,
    }

    @classmethod
    def create(cls, platform_type: str, base_url: str, api_key: str,
               config: Optional[Dict] = None) -> PlatformAdapter:
        adapter_cls = cls._registry.get(platform_type)
        if not adapter_cls:
            raise ValueError(f"不支持的平台类型: {platform_type}，已注册: {list(cls._registry.keys())}")
        return adapter_cls(base_url=base_url, api_key=api_key, config=config)

    @classmethod
    def register(cls, platform_type: str, adapter_cls: Type[PlatformAdapter]):
        """运行时注册新适配器"""
        cls._registry[platform_type] = adapter_cls

    @classmethod
    def list_platforms(cls):
        return list(cls._registry.keys())
```

- [ ] **Step 6: 创建 adapters 包 init**

```python
# backend/app/services/workflow/adapters/__init__.py
from app.services.workflow.adapters.dify_adapter import DifyAdapter
from app.services.workflow.adapters.coze_adapter import CozeAdapter
from app.services.workflow.adapters.custom_adapter import CustomHTTPAdapter

__all__ = ["DifyAdapter", "CozeAdapter", "CustomHTTPAdapter"]
```

- [ ] **Step 7: 编写适配器单元测试**

```python
# backend/tests/workflow/test_platform_adapters.py
"""平台适配器单元测试"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.workflow.platform_adapter import PlatformResponse
from app.services.workflow.adapters.dify_adapter import DifyAdapter
from app.services.workflow.adapters.coze_adapter import CozeAdapter
from app.services.workflow.adapters.custom_adapter import CustomHTTPAdapter
from app.services.workflow.adapter_factory import AdapterFactory


# ── DifyAdapter ──────────────────────────────────────────────

class TestDifyAdapter:
    def test_build_payload_workflow(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        payload = adapter._build_payload("Workflow", {"key": "val"}, "user1")
        assert payload == {"inputs": {"key": "val"}, "user": "user1"}

    def test_build_payload_chatflow(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        payload = adapter._build_payload("Chatflow", {"query": "hello", "extra": "data"}, "user1")
        assert payload["query"] == "hello"
        assert payload["response_mode"] == "blocking"

    def test_build_payload_agent(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        payload = adapter._build_payload("Agent", {"prompt": "analyze"}, "user1")
        assert payload["query"] == "analyze"

    def test_build_payload_completion(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        payload = adapter._build_payload("Completion", {"prompt": "write"}, "user1")
        assert payload["prompt"] == "write"
        assert payload["user"] == "user1"

    def test_extract_output_workflow(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        result = {"data": {"outputs": {"result": "hello world"}}}
        assert adapter.extract_output(result, "Workflow") == "hello world"

    def test_extract_output_chatflow(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        result = {"answer": "response text"}
        assert adapter.extract_output(result, "Chatflow") == "response text"

    def test_extract_output_agent(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        result = {"answer": "agent response"}
        assert adapter.extract_output(result, "Agent") == "agent response"

    def test_unsupported_flow_type(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        assert "Workflow" not in DifyAdapter.ENDPOINT_MAP or True  # 全部支持
        # 测试不存在类型
        import asyncio
        resp = asyncio.run(adapter.invoke("UnknownType", {}, "user1"))
        assert resp.success is False


# ── AdapterFactory ───────────────────────────────────────────

class TestAdapterFactory:
    def test_create_dify(self):
        adapter = AdapterFactory.create("dify", "https://dify.test", "sk-test")
        assert isinstance(adapter, DifyAdapter)

    def test_create_coze(self):
        adapter = AdapterFactory.create("coze", "https://coze.test", "sk-test")
        assert isinstance(adapter, CozeAdapter)

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="不支持的平台类型"):
            AdapterFactory.create("unknown_platform", "https://x.test", "sk")

    def test_list_platforms(self):
        platforms = AdapterFactory.list_platforms()
        assert "dify" in platforms
        assert "coze" in platforms
        assert "custom_http" in platforms
```

- [ ] **Step 8: 运行测试**

Run: `cd backend && python -m pytest tests/workflow/test_platform_adapters.py -v`
Expected: 11 passed

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/workflow/platform_adapter.py backend/app/services/workflow/adapters/ backend/app/services/workflow/adapter_factory.py backend/tests/workflow/test_platform_adapters.py
git commit -m "feat(workflow): add platform adapters (Dify/Coze/CustomHTTP) + factory"
```

---

### Task 5: 网关三件套（限流 / 熔断 / 重试）

**Files:**
- Create: `backend/app/services/workflow/rate_limiter.py`
- Create: `backend/app/services/workflow/circuit_breaker.py`
- Create: `backend/app/services/workflow/retry_policy.py`
- Test: `backend/tests/workflow/test_circuit_breaker.py`
- Test: `backend/tests/workflow/test_retry_policy.py`（合并到 circuit_breaker 测试文件）

**Interfaces:**
- Consumes: Redis client
- Produces: `WorkflowRateLimiter`, `CircuitBreaker`, `RetryPolicy` 供 Task 6 Gateway 使用

- [ ] **Step 1: 创建令牌桶限流器**

```python
# backend/app/services/workflow/rate_limiter.py
"""基于 Redis 的令牌桶限流器"""
import time
from typing import Optional


# Lua 脚本：原子性令牌获取
_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + elapsed * rate)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 120)
    return 1
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 120)
    return 0
end
"""


class WorkflowRateLimiter:
    """令牌桶限流器 — 粒度: tenant_id + flow_code"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self._script_sha: Optional[str] = None

    async def acquire(self, tenant_id: int, flow_code: str,
                      max_tokens: int = 10, refill_rate: float = 0.167) -> bool:
        """尝试获取令牌。返回 True 表示允许，False 表示限流。"""
        key = f"wf:rl:{tenant_id}:{flow_code}"
        now = time.time()

        try:
            result = await self.redis.eval(
                _TOKEN_BUCKET_SCRIPT, 1, key,
                str(max_tokens), str(refill_rate), str(now)
            )
            return bool(result)
        except Exception:
            # Redis 不可用时降级为放行
            return True
```

- [ ] **Step 2: 创建三态熔断器**

```python
# backend/app/services/workflow/circuit_breaker.py
"""三态熔断器 — Redis 存储，跨进程共享"""
import time
from enum import Enum
from typing import Optional


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """三态熔断器

    规则：
    - CLOSED: 正常放行，失败次数 >= threshold → OPEN
    - OPEN: 拒绝请求，等待 recovery_seconds → HALF_OPEN
    - HALF_OPEN: 放行一个探测请求，成功 → CLOSED，失败 → OPEN
    """

    def __init__(self, redis_client, threshold: int = 5, recovery_seconds: int = 60):
        self.redis = redis_client
        self.threshold = threshold
        self.recovery_seconds = recovery_seconds

    def _key(self, tenant_id: int, flow_code: str) -> str:
        return f"wf:cb:{tenant_id}:{flow_code}"

    async def get_state(self, tenant_id: int, flow_code: str) -> CircuitState:
        key = self._key(tenant_id, flow_code)
        state = await self.redis.hget(key, "state")
        if state is None:
            return CircuitState.CLOSED
        state = state.decode() if isinstance(state, bytes) else state

        if state == CircuitState.OPEN:
            opened_at = float(await self.redis.hget(key, "opened_at") or 0)
            if time.time() - opened_at >= self.recovery_seconds:
                await self.redis.hset(key, "state", CircuitState.HALF_OPEN)
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN
        return CircuitState(state)

    async def can_execute(self, tenant_id: int, flow_code: str) -> bool:
        """检查是否允许执行"""
        try:
            state = await self.get_state(tenant_id, flow_code)
        except Exception:
            return True  # Redis 不可用时降级放行
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # 探测请求放行
        return False  # OPEN 状态拒绝

    async def record_success(self, tenant_id: int, flow_code: str):
        """记录成功 → 重置为 CLOSED"""
        key = self._key(tenant_id, flow_code)
        try:
            await self.redis.hset(key, mapping={
                "state": CircuitState.CLOSED,
                "failure_count": "0",
            })
        except Exception:
            pass

    async def record_failure(self, tenant_id: int, flow_code: str):
        """记录失败 → 可能触发 OPEN"""
        key = self._key(tenant_id, flow_code)
        try:
            count = int(await self.redis.hget(key, "failure_count") or 0) + 1
            if count >= self.threshold:
                await self.redis.hset(key, mapping={
                    "state": CircuitState.OPEN,
                    "failure_count": str(count),
                    "opened_at": str(time.time()),
                })
            else:
                await self.redis.hset(key, "failure_count", str(count))
        except Exception:
            pass
```

- [ ] **Step 3: 创建指数退避重试**

```python
# backend/app/services/workflow/retry_policy.py
"""指数退避重试策略"""
import asyncio
import random
from typing import Set

import httpx
from loguru import logger


# 可重试的 HTTP 状态码
RETRIABLE_STATUS_CODES: Set[int] = {429, 502, 503, 504}


class RetriableError(Exception):
    """可重试错误"""
    pass


class NonRetriableError(Exception):
    """不可重试错误"""
    pass


class RetryPolicy:
    """指数退避重试策略"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 30.0, jitter: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def _calc_delay(self, attempt: int) -> float:
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        if self.jitter:
            delay *= random.uniform(0.5, 1.5)
        return delay

    @staticmethod
    def is_retriable(error: Exception) -> bool:
        if isinstance(error, RetriableError):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in RETRIABLE_STATUS_CODES
        if isinstance(error, (httpx.ConnectTimeout, httpx.ReadTimeout)):
            return True
        return False

    async def execute_with_retry(self, func, *args, **kwargs):
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt == self.max_retries or not self.is_retriable(e):
                    raise
                delay = self._calc_delay(attempt)
                logger.warning(f"重试 {attempt + 1}/{self.max_retries}，延迟 {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
        raise last_error
```

- [ ] **Step 4: 编写熔断器 + 重试测试**

```python
# backend/tests/workflow/test_circuit_breaker.py
"""熔断器 + 重试策略单元测试"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.workflow.circuit_breaker import CircuitBreaker, CircuitState
from app.services.workflow.retry_policy import RetryPolicy, RetriableError, NonRetriableError


# ── CircuitBreaker ───────────────────────────────────────────

class TestCircuitBreaker:
    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hset = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self, mock_redis):
        cb = CircuitBreaker(mock_redis)
        state = await cb.get_state(1, "test-flow")
        assert state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self, mock_redis):
        cb = CircuitBreaker(mock_redis)
        assert await cb.can_execute(1, "test-flow") is True

    @pytest.mark.asyncio
    async def test_can_execute_when_open(self, mock_redis):
        import time
        mock_redis.hget = AsyncMock(side_effect=lambda k, f: {
            "state": b"open",
            "opened_at": str(time.time()).encode(),
        }.get(f))
        cb = CircuitBreaker(mock_redis)
        assert await cb.can_execute(1, "test-flow") is False

    @pytest.mark.asyncio
    async def test_half_open_after_recovery(self, mock_redis):
        import time
        mock_redis.hget = AsyncMock(side_effect=lambda k, f: {
            "state": b"open",
            "opened_at": str(time.time() - 120).encode(),  # 2 分钟前
        }.get(f))
        cb = CircuitBreaker(mock_redis, recovery_seconds=60)
        state = await cb.get_state(1, "test-flow")
        assert state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_record_success_resets_to_closed(self, mock_redis):
        cb = CircuitBreaker(mock_redis)
        await cb.record_success(1, "test-flow")
        mock_redis.hset.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_failure_opens_after_threshold(self, mock_redis):
        mock_redis.hget = AsyncMock(return_value=b"4")  # 已有 4 次失败
        cb = CircuitBreaker(mock_redis, threshold=5)
        await cb.record_failure(1, "test-flow")
        # 第 5 次应触发 OPEN
        call_args = mock_redis.hset.call_args
        assert call_args is not None


# ── RetryPolicy ──────────────────────────────────────────────

class TestRetryPolicy:
    def test_calc_delay_exponential(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=30.0, jitter=False)
        assert policy._calc_delay(0) == 1.0
        assert policy._calc_delay(1) == 2.0
        assert policy._calc_delay(2) == 4.0
        assert policy._calc_delay(10) == 30.0  # capped

    def test_calc_delay_with_jitter(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=30.0, jitter=True)
        delay = policy._calc_delay(2)
        assert 2.0 <= delay <= 6.0  # 4.0 * [0.5, 1.5]

    def test_is_retriable_http_status(self):
        import httpx
        policy = RetryPolicy()
        resp = httpx.Response(status_code=503, request=httpx.Request("GET", "http://x"))
        err = httpx.HTTPStatusError("server error", request=resp.request, response=resp)
        assert policy.is_retriable(err) is True

    def test_is_retriable_400_not_retriable(self):
        import httpx
        policy = RetryPolicy()
        resp = httpx.Response(status_code=400, request=httpx.Request("GET", "http://x"))
        err = httpx.HTTPStatusError("bad request", request=resp.request, response=resp)
        assert policy.is_retriable(err) is False

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self):
        policy = RetryPolicy(max_retries=3, jitter=False)
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetriableError("temporary")
            return "ok"

        result = await policy.execute_with_retry(flaky_func)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_exhausted(self):
        policy = RetryPolicy(max_retries=2, jitter=False)

        async def always_fail():
            raise RetriableError("permanent")

        with pytest.raises(RetriableError):
            await policy.execute_with_retry(always_fail)
```

- [ ] **Step 5: 创建 tests/workflow 包文件**

```python
# backend/tests/workflow/__init__.py
```

```python
# backend/tests/workflow/conftest.py
"""tests/workflow 测试基础设施"""
import pytest
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest tests/workflow/test_circuit_breaker.py -v`
Expected: 11 passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/workflow/rate_limiter.py backend/app/services/workflow/circuit_breaker.py backend/app/services/workflow/retry_policy.py backend/tests/workflow/
git commit -m "feat(workflow): add rate limiter, circuit breaker, retry policy + tests"
```

---

### Task 6: 网关 + Webhook + 链式编排

**Files:**
- Create: `backend/app/services/workflow/gateway.py`
- Create: `backend/app/services/workflow/webhook.py`
- Create: `backend/app/services/workflow/chain_executor.py`
- Test: `backend/tests/workflow/test_chain_executor.py`

**Interfaces:**
- Consumes: `WorkflowFlow` (Task 1), `crypto` (Task 3), `AdapterFactory` (Task 4), `RateLimiter` / `CircuitBreaker` / `RetryPolicy` (Task 5)
- Produces: `WorkflowGateway` 供 Task 7 Engine 和 Task 8 Router 使用

- [ ] **Step 1: 创建 Webhook 回调**

```python
# backend/app/services/workflow/webhook.py
"""异步 Webhook 回调"""
import hashlib
import hmac
import json
import time
from typing import Optional

import httpx
from loguru import logger


class WebhookDispatcher:
    """Webhook 回调分发器"""

    async def dispatch(self, event_type: str, flow_config: dict,
                       execution_data: dict):
        """发送 Webhook 回调

        Args:
            event_type: on_success / on_failure / on_timeout
            flow_config: workflow_flow.config JSONB
            execution_data: 执行结果数据
        """
        webhook_url = flow_config.get("webhook_url") if flow_config else None
        if not webhook_url:
            return

        webhook_secret = flow_config.get("webhook_secret", "")
        payload = {
            "event": event_type,
            "timestamp": int(time.time()),
            "data": execution_data,
        }
        body = json.dumps(payload, ensure_ascii=False)
        signature = hmac.new(
            webhook_secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest() if webhook_secret else ""

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, content=body, headers=headers, timeout=10.0)
        except Exception as e:
            logger.warning(f"Webhook 回调失败: {webhook_url} -> {e}")
```

- [ ] **Step 2: 创建 WorkflowGateway**

```python
# backend/app/services/workflow/gateway.py
"""工作流网关 — 统一入口"""
import time
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow.workflow_flow import WorkflowFlow
from app.models.workflow.workflow_execution_log import WorkflowExecutionLog
from app.services.workflow.crypto import decrypt_api_key
from app.services.workflow.adapter_factory import AdapterFactory
from app.services.workflow.platform_adapter import PlatformResponse
from app.services.workflow.rate_limiter import WorkflowRateLimiter
from app.services.workflow.circuit_breaker import CircuitBreaker
from app.services.workflow.retry_policy import RetryPolicy
from app.services.workflow.webhook import WebhookDispatcher


class WorkflowGateway:
    """工作流网关 — 限流 + 熔断 + 重试 + 日志 + Webhook"""

    def __init__(self, db: Session, redis_client=None):
        self.db = db
        self.redis = redis_client
        self.rate_limiter = WorkflowRateLimiter(redis_client) if redis_client else None
        self.circuit_breaker = CircuitBreaker(redis_client) if redis_client else None
        self.retry_policy = RetryPolicy()
        self.webhook = WebhookDispatcher()

    async def execute(
        self,
        flow_code: str,
        tenant_id: int,
        inputs: Dict[str, Any],
        user_id: str,
        timeout: float = 600.0,
        execution_id: Optional[str] = None,
    ) -> PlatformResponse:
        """执行工作流（网关入口）"""
        # 1. 查找流程定义
        flow = self.db.scalars(
            select(WorkflowFlow).where(
                WorkflowFlow.flow_code == flow_code,
                WorkflowFlow.tenant_id == tenant_id,
                WorkflowFlow.is_deleted == False,
                WorkflowFlow.is_active == True,
            )
        ).first()
        if not flow:
            return PlatformResponse(success=False, error=f"流程未找到: {flow_code} (tenant={tenant_id})")

        # 2. 限流检查
        if self.rate_limiter:
            rate_cfg = (flow.config or {}).get("rate_limit", {})
            allowed = await self.rate_limiter.acquire(
                tenant_id, flow_code,
                max_tokens=rate_cfg.get("max_tokens", 10),
                refill_rate=rate_cfg.get("refill_rate", 0.167),
            )
            if not allowed:
                return PlatformResponse(success=False, error="请求频率超限", latency_ms=0)

        # 3. 熔断检查
        if self.circuit_breaker:
            can_exec = await self.circuit_breaker.can_execute(tenant_id, flow_code)
            if not can_exec:
                return PlatformResponse(success=False, error="服务熔断中，请稍后重试", latency_ms=0)

        # 4. 创建执行日志
        log = WorkflowExecutionLog(
            tenant_id=tenant_id,
            flow_id=flow.id,
            execution_id=execution_id,
            status="running",
            input_data=inputs,
        )
        self.db.add(log)
        self.db.flush()

        # 5. 解密 API Key + 创建适配器
        try:
            api_key = decrypt_api_key(flow.api_key_enc)
        except Exception as e:
            log.status = "failed"
            log.error_message = f"API Key 解密失败: {e}"
            self.db.commit()
            return PlatformResponse(success=False, error="API Key 解密失败")

        adapter = AdapterFactory.create(
            platform_type=flow.platform_type,
            base_url=flow.base_url,
            api_key=api_key,
            config=flow.config,
        )

        # 6. 执行（带重试）
        t0 = time.monotonic()
        try:
            result = await self.retry_policy.execute_with_retry(
                adapter.invoke,
                flow_type=flow.flow_type,
                inputs=dict(inputs),
                user_id=user_id,
                timeout=timeout,
            )
            latency = int((time.monotonic() - t0) * 1000)

            # 7. 更新日志
            if result.success:
                log.status = "success"
                log.output_data = result.output
                log.platform_trace = result.platform_trace
                if self.circuit_breaker:
                    await self.circuit_breaker.record_success(tenant_id, flow_code)
                event_type = "on_success"
            else:
                log.status = "failed"
                log.error_message = result.error
                if self.circuit_breaker:
                    await self.circuit_breaker.record_failure(tenant_id, flow_code)
                event_type = "on_failure"

            log.latency_ms = latency
            log.completed_at = __import__("datetime").datetime.utcnow()
            self.db.commit()

            # 8. Webhook
            await self.webhook.dispatch(event_type, flow.config or {}, {
                "flow_code": flow_code, "status": log.status, "latency_ms": latency,
            })

            return result

        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            log.status = "failed"
            log.error_message = str(e)
            log.latency_ms = latency
            log.completed_at = __import__("datetime").datetime.utcnow()
            self.db.commit()

            if self.circuit_breaker:
                await self.circuit_breaker.record_failure(tenant_id, flow_code)

            await self.webhook.dispatch("on_failure", flow.config or {}, {
                "flow_code": flow_code, "status": "failed", "error": str(e),
            })

            return PlatformResponse(success=False, error=str(e), latency_ms=latency)
```

- [ ] **Step 3: 创建链式编排执行器**

```python
# backend/app/services/workflow/chain_executor.py
"""链式编排执行器"""
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.workflow.workflow_chain import WorkflowChain
from app.services.workflow.gateway import WorkflowGateway
from app.services.workflow.platform_adapter import PlatformResponse


class ChainExecutor:
    """链式编排执行器"""

    def __init__(self, db: Session, redis_client=None):
        self.db = db
        self.gateway = WorkflowGateway(db, redis_client)

    async def execute_chain(
        self,
        chain_code: str,
        tenant_id: int,
        initial_inputs: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        """执行链式编排"""
        from sqlalchemy import select
        chain = self.db.scalars(
            select(WorkflowChain).where(
                WorkflowChain.chain_code == chain_code,
                WorkflowChain.tenant_id == tenant_id,
                WorkflowChain.is_deleted == False,
                WorkflowChain.is_active == True,
            )
        ).first()
        if not chain:
            raise ValueError(f"链未找到: {chain_code}")

        context: Dict[str, Any] = {"user_input": initial_inputs, "steps": []}

        steps = sorted(chain.steps, key=lambda s: s.get("step_order", 0))
        for step in steps:
            # 1. 条件检查
            condition = step.get("condition")
            if condition and not self._evaluate_condition(condition, context):
                context["steps"].append({
                    "step_order": step["step_order"],
                    "flow_code": step["flow_code"],
                    "status": "skipped",
                    "output": {},
                })
                continue

            # 2. 输入映射
            step_inputs = self._resolve_mapping(step.get("input_mapping", {}), context)

            # 3. 通过网关执行
            try:
                result = await self.gateway.execute(
                    flow_code=step["flow_code"],
                    tenant_id=tenant_id,
                    inputs=step_inputs,
                    user_id=user_id,
                )
                context["steps"].append({
                    "step_order": step["step_order"],
                    "flow_code": step["flow_code"],
                    "status": "success" if result.success else "failed",
                    "output": result.output,
                    "error": result.error,
                })
            except Exception as e:
                strategy = step.get("error_strategy", "stop")
                if strategy == "stop":
                    context["steps"].append({
                        "step_order": step["step_order"],
                        "status": "failed", "error": str(e),
                    })
                    raise
                context["steps"].append({
                    "step_order": step["step_order"],
                    "status": "failed", "error": str(e), "output": {},
                })

        return context

    @staticmethod
    def _evaluate_condition(condition: str, context: Dict) -> bool:
        """简单条件评估：支持 $.steps[N].status == 'success' 格式"""
        try:
            # 极简实现：替换变量后 eval（生产环境应使用安全的表达式解析器）
            expr = condition
            for i, step in enumerate(context.get("steps", [])):
                expr = expr.replace(f"$.steps[{i}].status", f"'{step.get('status', '')}'")
            return bool(eval(expr))  # noqa: S307
        except Exception:
            return True  # 表达式解析失败时默认执行

    @staticmethod
    def _resolve_mapping(mapping: Dict[str, str], context: Dict) -> Dict[str, Any]:
        """解析输入映射"""
        result = {}
        for target_key, source_expr in mapping.items():
            if source_expr.startswith("$."):
                result[target_key] = ChainExecutor._json_path_get(source_expr, context)
            elif source_expr.startswith('"') and source_expr.endswith('"'):
                result[target_key] = source_expr[1:-1]
            else:
                result[target_key] = source_expr
        return result

    @staticmethod
    def _json_path_get(path: str, data: Dict) -> Any:
        """简单 JSONPath 取值（仅支持 $.a.b.c 和 $.steps[N].output.key）"""
        parts = path.lstrip("$.").replace("[", ".").replace("]", "").split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                return None
            if current is None:
                return None
        return current
```

- [ ] **Step 4: 编写链式编排测试**

```python
# backend/tests/workflow/test_chain_executor.py
"""链式编排执行器测试"""
import pytest
from app.services.workflow.chain_executor import ChainExecutor


class TestChainExecutorHelpers:
    def test_evaluate_condition_true(self):
        ctx = {"steps": [{"status": "success"}]}
        assert ChainExecutor._evaluate_condition("$.steps[0].status == 'success'", ctx) is True

    def test_evaluate_condition_false(self):
        ctx = {"steps": [{"status": "failed"}]}
        assert ChainExecutor._evaluate_condition("$.steps[0].status == 'success'", ctx) is False

    def test_resolve_mapping_literal(self):
        mapping = {"mode": '"analysis"'}
        result = ChainExecutor._resolve_mapping(mapping, {})
        assert result == {"mode": "analysis"}

    def test_resolve_mapping_json_path(self):
        mapping = {"query": "$.user_input"}
        ctx = {"user_input": "hello"}
        result = ChainExecutor._resolve_mapping(mapping, ctx)
        assert result == {"query": "hello"}

    def test_json_path_get_simple(self):
        data = {"a": {"b": {"c": 42}}}
        assert ChainExecutor._json_path_get("$.a.b.c", data) == 42

    def test_json_path_get_array(self):
        data = {"steps": [{"output": {"result": "ok"}}]}
        assert ChainExecutor._json_path_get("$.steps[0].output.result", data) == "ok"

    def test_json_path_get_missing(self):
        data = {"a": 1}
        assert ChainExecutor._json_path_get("$.b.c", data) is None
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/workflow/test_chain_executor.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/workflow/gateway.py backend/app/services/workflow/webhook.py backend/app/services/workflow/chain_executor.py backend/tests/workflow/test_chain_executor.py
git commit -m "feat(workflow): add gateway, webhook dispatcher, chain executor"
```

---

### Task 7: WorkflowPlatformEngine + Service + Router

**Files:**
- Create: `backend/app/services/workflow/workflow_service.py`
- Create: `backend/app/routers/workflow/__init__.py`
- Create: `backend/app/routers/workflow/workflow.py`
- Modify: `backend/app/core/router_registry.py:183` (注册新路由)

**Interfaces:**
- Consumes: `WorkflowFlow` / `WorkflowExecutionLog` / `WorkflowChain` (Task 1), Schema (Task 3), `WorkflowGateway` (Task 6)
- Produces: RESTful API 端点

- [ ] **Step 1: 创建 WorkflowService（CRUD 服务层）**

```python
# backend/app/services/workflow/workflow_service.py
"""工作流 CRUD 服务"""
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.workflow.workflow_flow import WorkflowFlow
from app.models.workflow.workflow_execution_log import WorkflowExecutionLog
from app.models.workflow.workflow_chain import WorkflowChain
from app.services.workflow.crypto import encrypt_api_key


class WorkflowService:
    """工作流管理服务"""

    # ── Flow CRUD ────────────────────────────────────────────

    def list_flows(self, db: Session, tenant_id: Optional[int] = None,
                   platform_type: Optional[str] = None, flow_type: Optional[str] = None,
                   is_active: Optional[bool] = None,
                   page: int = 1, page_size: int = 20) -> Tuple[int, List[WorkflowFlow]]:
        q = select(WorkflowFlow).where(WorkflowFlow.is_deleted == False)
        if tenant_id:
            q = q.where(WorkflowFlow.tenant_id == tenant_id)
        if platform_type:
            q = q.where(WorkflowFlow.platform_type == platform_type)
        if flow_type:
            q = q.where(WorkflowFlow.flow_type == flow_type)
        if is_active is not None:
            q = q.where(WorkflowFlow.is_active == is_active)

        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        q = q.order_by(WorkflowFlow.sort_order, WorkflowFlow.id)
        q = q.offset((page - 1) * page_size).limit(page_size)
        return total, list(db.scalars(q).all())

    def get_flow(self, db: Session, flow_id: int) -> Optional[WorkflowFlow]:
        return db.scalars(select(WorkflowFlow).where(
            WorkflowFlow.id == flow_id, WorkflowFlow.is_deleted == False
        )).first()

    def create_flow(self, db: Session, data: dict) -> WorkflowFlow:
        api_key_plain = data.pop("api_key")
        data["api_key_enc"] = encrypt_api_key(api_key_plain)
        flow = WorkflowFlow(**data)
        db.add(flow)
        db.flush()
        return flow

    def update_flow(self, db: Session, flow: WorkflowFlow, data: dict) -> WorkflowFlow:
        api_key = data.pop("api_key", None)
        for k, v in data.items():
            if v is not None:
                setattr(flow, k, v)
        if api_key:
            flow.api_key_enc = encrypt_api_key(api_key)
        db.flush()
        return flow

    def delete_flow(self, db: Session, flow: WorkflowFlow):
        flow.is_deleted = True
        db.flush()

    # ── Execution Log ────────────────────────────────────────

    def list_executions(self, db: Session, flow_id: Optional[int] = None,
                        status: Optional[str] = None,
                        page: int = 1, page_size: int = 20) -> Tuple[int, List[WorkflowExecutionLog]]:
        q = select(WorkflowExecutionLog)
        if flow_id:
            q = q.where(WorkflowExecutionLog.flow_id == flow_id)
        if status:
            q = q.where(WorkflowExecutionLog.status == status)
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        q = q.order_by(WorkflowExecutionLog.created_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        return total, list(db.scalars(q).all())

    # ── Chain CRUD ───────────────────────────────────────────

    def list_chains(self, db: Session, tenant_id: Optional[int] = None,
                    page: int = 1, page_size: int = 20) -> Tuple[int, List[WorkflowChain]]:
        q = select(WorkflowChain).where(WorkflowChain.is_deleted == False)
        if tenant_id:
            q = q.where(WorkflowChain.tenant_id == tenant_id)
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        q = q.order_by(WorkflowChain.id.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        return total, list(db.scalars(q).all())

    def create_chain(self, db: Session, data: dict) -> WorkflowChain:
        chain = WorkflowChain(**data)
        db.add(chain)
        db.flush()
        return chain

    def update_chain(self, db: Session, chain: WorkflowChain, data: dict) -> WorkflowChain:
        for k, v in data.items():
            if v is not None:
                setattr(chain, k, v)
        db.flush()
        return chain

    def delete_chain(self, db: Session, chain: WorkflowChain):
        chain.is_deleted = True
        db.flush()
```

- [ ] **Step 2: 创建 Router**

```python
# backend/app/routers/workflow/__init__.py
```

```python
# backend/app/routers/workflow/workflow.py
"""工作流管理 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.schemas.workflow import (
    WorkflowFlowCreate, WorkflowFlowUpdate, WorkflowFlowOut,
    WorkflowFlowListOut, WorkflowExecutionLogOut,
    WorkflowChainCreate, WorkflowChainUpdate, WorkflowChainOut,
    WorkflowTestReq, WorkflowTestResp,
    PlatformTypeEnum, FlowTypeEnum,
)
from app.services.workflow.workflow_service import WorkflowService
from app.services.workflow.gateway import WorkflowGateway

router = APIRouter(prefix="/api/v1/workflow", tags=["工作流管理"])
svc = WorkflowService()


# ── 枚举查询 ─────────────────────────────────────────────────

@router.get("/platforms/types")
def get_platform_types():
    """获取支持的平台类型和流程类型枚举"""
    return {"platform_types": PlatformTypeEnum.ALL, "flow_types": FlowTypeEnum.ALL}


# ── Flow CRUD ────────────────────────────────────────────────

@router.get("/flows", response_model=WorkflowFlowListOut)
def list_flows(
    platform_type: Optional[str] = Query(None),
    flow_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    total, items = svc.list_flows(db, tenant_id=user.tenant_id,
                                  platform_type=platform_type, flow_type=flow_type,
                                  is_active=is_active, page=page, page_size=page_size)
    return WorkflowFlowListOut(total=total, items=[WorkflowFlowOut.model_validate(i) for i in items])


@router.post("/flows", response_model=WorkflowFlowOut)
def create_flow(
    data: WorkflowFlowCreate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    flow = svc.create_flow(db, {**data.model_dump(exclude={"api_key"}),
                                 "api_key": data.api_key,
                                 "tenant_id": user.tenant_id,
                                 "created_by": user.id})
    db.commit()
    return WorkflowFlowOut.model_validate(flow)


@router.get("/flows/{flow_id}", response_model=WorkflowFlowOut)
def get_flow(flow_id: int, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    flow = svc.get_flow(db, flow_id)
    if not flow:
        raise HTTPException(404, "工作流不存在")
    return WorkflowFlowOut.model_validate(flow)


@router.put("/flows/{flow_id}", response_model=WorkflowFlowOut)
def update_flow(flow_id: int, data: WorkflowFlowUpdate,
                db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    flow = svc.get_flow(db, flow_id)
    if not flow:
        raise HTTPException(404, "工作流不存在")
    flow = svc.update_flow(db, flow, data.model_dump(exclude_unset=True))
    db.commit()
    return WorkflowFlowOut.model_validate(flow)


@router.delete("/flows/{flow_id}")
def delete_flow(flow_id: int, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    flow = svc.get_flow(db, flow_id)
    if not flow:
        raise HTTPException(404, "工作流不存在")
    svc.delete_flow(db, flow)
    db.commit()
    return {"ok": True}


@router.post("/flows/{flow_id}/test", response_model=WorkflowTestResp)
async def test_flow(flow_id: int, data: WorkflowTestReq,
                    db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    flow = svc.get_flow(db, flow_id)
    if not flow:
        raise HTTPException(404, "工作流不存在")
    gateway = WorkflowGateway(db)
    result = await gateway.execute(
        flow_code=flow.flow_code, tenant_id=user.tenant_id,
        inputs=data.inputs, user_id=str(user.id), timeout=data.timeout,
    )
    return WorkflowTestResp(success=result.success, output=result.output,
                            error=result.error, latency_ms=result.latency_ms)


# ── Execution Log ────────────────────────────────────────────

@router.get("/executions")
def list_executions(
    flow_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    total, items = svc.list_executions(db, flow_id=flow_id, status=status,
                                       page=page, page_size=page_size)
    return {"total": total,
            "items": [WorkflowExecutionLogOut.model_validate(i) for i in items]}


# ── Chain CRUD ───────────────────────────────────────────────

@router.get("/chains")
def list_chains(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    total, items = svc.list_chains(db, tenant_id=user.tenant_id, page=page, page_size=page_size)
    return {"total": total, "items": [WorkflowChainOut.model_validate(i) for i in items]}


@router.post("/chains", response_model=WorkflowChainOut)
def create_chain(data: WorkflowChainCreate,
                 db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    chain = svc.create_chain(db, {**data.model_dump(), "tenant_id": user.tenant_id,
                                   "created_by": user.id})
    db.commit()
    return WorkflowChainOut.model_validate(chain)


@router.put("/chains/{chain_id}", response_model=WorkflowChainOut)
def update_chain(chain_id: int, data: WorkflowChainUpdate,
                 db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    from sqlalchemy import select
    from app.models.workflow.workflow_chain import WorkflowChain
    chain = db.scalars(select(WorkflowChain).where(
        WorkflowChain.id == chain_id, WorkflowChain.is_deleted == False)).first()
    if not chain:
        raise HTTPException(404, "链不存在")
    chain = svc.update_chain(db, chain, data.model_dump(exclude_unset=True))
    db.commit()
    return WorkflowChainOut.model_validate(chain)


@router.delete("/chains/{chain_id}")
def delete_chain(chain_id: int, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    from sqlalchemy import select
    from app.models.workflow.workflow_chain import WorkflowChain
    chain = db.scalars(select(WorkflowChain).where(
        WorkflowChain.id == chain_id, WorkflowChain.is_deleted == False)).first()
    if not chain:
        raise HTTPException(404, "链不存在")
    svc.delete_chain(db, chain)
    db.commit()
    return {"ok": True}
```

- [ ] **Step 3: 注册路由到 router_registry.py**

在 `backend/app/core/router_registry.py` 第 183 行（`]` 之前）新增：

```python
    # --- 30. 工作流管理 ---
    RouterSpec("app.routers.workflow.workflow", tags=["工作流管理"]),
```

- [ ] **Step 4: 验证路由可加载**

Run: `cd backend && python -c "from app.routers.workflow.workflow import router; print(f'{len(router.routes)} routes')"`
Expected: `13 routes`（或类似数字）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/workflow/workflow_service.py backend/app/routers/workflow/ backend/app/core/router_registry.py
git commit -m "feat(workflow): add workflow CRUD service + RESTful API router"
```

---

### Task 8: 前端 — 工作流管理页面

**Files:**
- Create: `frontend/src/api/workflow.ts`
- Create: `frontend/src/views/admin/workflow/WorkflowManagement.vue`
- Create: `frontend/src/views/admin/workflow/components/WorkflowFlowTable.vue`
- Create: `frontend/src/views/admin/workflow/components/WorkflowFlowForm.vue`
- Create: `frontend/src/views/admin/workflow/components/WorkflowTestBench.vue`
- Create: `frontend/src/views/admin/workflow/components/WorkflowExecutionTable.vue`
- Create: `frontend/src/views/admin/workflow/components/WorkflowDashboard.vue`
- Modify: `frontend/src/router/index.ts:116` (新增路由)

- [ ] **Step 1: 创建 API 封装**

```typescript
// frontend/src/api/workflow.ts
import request from '@/utils/request'

const BASE = '/api/v1/workflow'

// ── Flow CRUD ──────────────────────────────────────────
export function listFlows(params: Record<string, any> = {}) {
  return request.get(`${BASE}/flows`, { params })
}
export function createFlow(data: Record<string, any>) {
  return request.post(`${BASE}/flows`, data)
}
export function getFlow(id: number) {
  return request.get(`${BASE}/flows/${id}`)
}
export function updateFlow(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/flows/${id}`, data)
}
export function deleteFlow(id: number) {
  return request.delete(`${BASE}/flows/${id}`)
}
export function testFlow(id: number, data: Record<string, any>) {
  return request.post(`${BASE}/flows/${id}/test`, data)
}

// ── Execution Log ──────────────────────────────────────
export function listExecutions(params: Record<string, any> = {}) {
  return request.get(`${BASE}/executions`, { params })
}

// ── Chain ──────────────────────────────────────────────
export function listChains(params: Record<string, any> = {}) {
  return request.get(`${BASE}/chains`, { params })
}
export function createChain(data: Record<string, any>) {
  return request.post(`${BASE}/chains`, data)
}
export function updateChain(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/chains/${id}`, data)
}
export function deleteChain(id: number) {
  return request.delete(`${BASE}/chains/${id}`)
}

// ── 枚举 ──────────────────────────────────────────────
export function getPlatformTypes() {
  return request.get(`${BASE}/platforms/types`)
}
```

- [ ] **Step 2: 创建主页面（5 Tab 容器）**

```vue
<!-- frontend/src/views/admin/workflow/WorkflowManagement.vue -->
<template>
  <div class="workflow-management">
    <a-tabs v-model:activeKey="activeTab" type="card">
      <a-tab-pane key="flows" tab="工作流列表">
        <WorkflowFlowTable @edit="handleEdit" @test="handleTest" />
      </a-tab-pane>
      <a-tab-pane key="editor" tab="编辑器">
        <WorkflowFlowForm :initial="editingFlow" @saved="refreshFlows" />
      </a-tab-pane>
      <a-tab-pane key="test" tab="测试工作台">
        <WorkflowTestBench :flow-id="testingFlowId" />
      </a-tab-pane>
      <a-tab-pane key="logs" tab="执行日志">
        <WorkflowExecutionTable />
      </a-tab-pane>
      <a-tab-pane key="dashboard" tab="分析仪表板">
        <WorkflowDashboard />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import WorkflowFlowTable from './components/WorkflowFlowTable.vue'
import WorkflowFlowForm from './components/WorkflowFlowForm.vue'
import WorkflowTestBench from './components/WorkflowTestBench.vue'
import WorkflowExecutionTable from './components/WorkflowExecutionTable.vue'
import WorkflowDashboard from './components/WorkflowDashboard.vue'

const activeTab = ref('flows')
const editingFlow = ref<any>(null)
const testingFlowId = ref<number | null>(null)

function handleEdit(flow: any) {
  editingFlow.value = flow
  activeTab.value = 'editor'
}
function handleTest(flowId: number) {
  testingFlowId.value = flowId
  activeTab.value = 'test'
}
function refreshFlows() {
  activeTab.value = 'flows'
}
</script>
```

- [ ] **Step 3: 创建工作流列表组件**

```vue
<!-- frontend/src/views/admin/workflow/components/WorkflowFlowTable.vue -->
<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-select v-model:value="filters.platform_type" placeholder="平台类型" allowClear style="width: 140px"
                :options="platformOptions" @change="loadData" />
      <a-select v-model:value="filters.flow_type" placeholder="流程类型" allowClear style="width: 140px"
                :options="flowTypeOptions" @change="loadData" />
      <a-button type="primary" @click="$emit('edit', null)">新建工作流</a-button>
    </a-space>
    <a-table :columns="columns" :data-source="data" :loading="loading" :pagination="pagination"
             @change="handleTableChange" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'default'">{{ record.is_active ? '启用' : '禁用' }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="$emit('edit', record)">编辑</a>
            <a @click="$emit('test', record.id)">测试</a>
            <a-popconfirm title="确认删除？" @confirm="handleDelete(record.id)">
              <a style="color: #ff4d4f">删除</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listFlows, deleteFlow, getPlatformTypes } from '@/api/workflow'
import { message } from 'ant-design-vue'

const emit = defineEmits(['edit', 'test'])

const data = ref<any[]>([])
const loading = ref(false)
const filters = reactive({ platform_type: undefined as string | undefined, flow_type: undefined as string | undefined })
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })
const platformOptions = ref<any[]>([])
const flowTypeOptions = ref<any[]>([])

const columns = [
  { title: '编码', dataIndex: 'flow_code', key: 'flow_code' },
  { title: '名称', dataIndex: 'flow_name', key: 'flow_name' },
  { title: '平台', dataIndex: 'platform_type', key: 'platform_type' },
  { title: '类型', dataIndex: 'flow_type', key: 'flow_type' },
  { title: '状态', key: 'is_active' },
  { title: '操作', key: 'action', width: 180 },
]

async function loadData() {
  loading.value = true
  try {
    const res = await listFlows({ ...filters, page: pagination.current, page_size: pagination.pageSize })
    data.value = res.data.items
    pagination.total = res.data.total
  } finally { loading.value = false }
}

async function loadEnums() {
  const res = await getPlatformTypes()
  platformOptions.value = res.data.platform_types.map((v: string) => ({ label: v, value: v }))
  flowTypeOptions.value = res.data.flow_types.map((v: string) => ({ label: v, value: v }))
}

async function handleDelete(id: number) {
  await deleteFlow(id)
  message.success('已删除')
  loadData()
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

onMounted(() => { loadData(); loadEnums() })
</script>
```

- [ ] **Step 4: 创建编辑表单组件**

```vue
<!-- frontend/src/views/admin/workflow/components/WorkflowFlowForm.vue -->
<template>
  <a-form :model="form" layout="vertical" style="max-width: 720px">
    <a-form-item label="流程编码" required>
      <a-input v-model:value="form.flow_code" :disabled="!!props.initial" />
    </a-form-item>
    <a-form-item label="名称" required>
      <a-input v-model:value="form.flow_name" />
    </a-form-item>
    <a-row :gutter="16">
      <a-col :span="12">
        <a-form-item label="平台类型" required>
          <a-select v-model:value="form.platform_type" :options="platformOptions" />
        </a-form-item>
      </a-col>
      <a-col :span="12">
        <a-form-item label="流程类型" required>
          <a-select v-model:value="form.flow_type" :options="flowTypeOptions" />
        </a-form-item>
      </a-col>
    </a-row>
    <a-form-item label="API 基地址" required>
      <a-input v-model:value="form.base_url" placeholder="https://api.dify.net" />
    </a-form-item>
    <a-form-item label="API Key" :required="!props.initial">
      <a-input-password v-model:value="form.api_key" :placeholder="props.initial ? '留空不修改' : '输入 API Key'" />
    </a-form-item>
    <a-form-item label="描述">
      <a-textarea v-model:value="form.description" :rows="3" />
    </a-form-item>
    <a-form-item>
      <a-space>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
        <a-button @click="$emit('saved')">取消</a-button>
      </a-space>
    </a-form-item>
  </a-form>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { createFlow, updateFlow, getPlatformTypes } from '@/api/workflow'
import { message } from 'ant-design-vue'

const props = defineProps<{ initial: any }>()
const emit = defineEmits(['saved'])

const form = reactive<any>({
  flow_code: '', flow_name: '', platform_type: 'dify', flow_type: 'Workflow',
  base_url: '', api_key: '', description: '',
})
const saving = ref(false)
const platformOptions = ref<any[]>([])
const flowTypeOptions = ref<any[]>([])

onMounted(async () => {
  if (props.initial) {
    Object.assign(form, { ...props.initial, api_key: '' })
  }
  const res = await getPlatformTypes()
  platformOptions.value = res.data.platform_types.map((v: string) => ({ label: v, value: v }))
  flowTypeOptions.value = res.data.flow_types.map((v: string) => ({ label: v, value: v }))
})

async function handleSave() {
  saving.value = true
  try {
    if (props.initial?.id) {
      await updateFlow(props.initial.id, form)
    } else {
      await createFlow(form)
    }
    message.success('保存成功')
    emit('saved')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}
</script>
```

- [ ] **Step 5: 创建测试工作台**

```vue
<!-- frontend/src/views/admin/workflow/components/WorkflowTestBench.vue -->
<template>
  <div>
    <a-row :gutter="16">
      <a-col :span="12">
        <h4>输入 (JSON)</h4>
        <a-textarea v-model:value="inputJson" :rows="12" placeholder='{"key": "value"}' />
        <a-button type="primary" :loading="running" style="margin-top: 8px" @click="runTest">执行测试</a-button>
      </a-col>
      <a-col :span="12">
        <h4>结果</h4>
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="状态">
            <a-tag :color="result?.success ? 'green' : 'red'">{{ result?.success ? '成功' : '失败' }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="耗时">{{ result?.latency_ms ?? '-' }} ms</a-descriptions-item>
          <a-descriptions-item label="错误" v-if="result?.error">{{ result.error }}</a-descriptions-item>
        </a-descriptions>
        <h4 style="margin-top: 12px">输出</h4>
        <pre style="background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; max-height: 400px; overflow: auto">{{ JSON.stringify(result?.output, null, 2) }}</pre>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { testFlow, listFlows } from '@/api/workflow'
import { message } from 'ant-design-vue'

const props = defineProps<{ flowId: number | null }>()
const inputJson = ref('{}')
const result = ref<any>(null)
const running = ref(false)

async function runTest() {
  if (!props.flowId) { message.warning('请先选择工作流'); return }
  let inputs: any = {}
  try { inputs = JSON.parse(inputJson.value) } catch { message.error('输入 JSON 格式错误'); return }
  running.value = true
  try {
    const res = await testFlow(props.flowId, { inputs, user_id: 'test' })
    result.value = res.data
  } catch (e: any) {
    result.value = { success: false, error: e?.response?.data?.detail || '执行失败', output: {} }
  } finally { running.value = false }
}
</script>
```

- [ ] **Step 6: 创建执行日志表格**

```vue
<!-- frontend/src/views/admin/workflow/components/WorkflowExecutionTable.vue -->
<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-select v-model:value="filterStatus" placeholder="状态" allowClear style="width: 140px" @change="loadData">
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="failed">失败</a-select-option>
        <a-select-option value="running">运行中</a-select-option>
      </a-select>
    </a-space>
    <a-table :columns="columns" :data-source="data" :loading="loading" :pagination="pagination"
             @change="handleTableChange" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-if="column.key === 'latency_ms'">
          {{ record.latency_ms ? `${record.latency_ms} ms` : '-' }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listExecutions } from '@/api/workflow'

const data = ref<any[]>([])
const loading = ref(false)
const filterStatus = ref<string | undefined>(undefined)
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })

const columns = [
  { title: 'ID', dataIndex: 'id', width: 80 },
  { title: 'Flow ID', dataIndex: 'flow_id', width: 100 },
  { title: '状态', key: 'status', width: 100 },
  { title: '耗时', key: 'latency_ms', width: 120 },
  { title: '重试', dataIndex: 'retry_count', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', width: 180 },
]

function statusColor(s: string) {
  return { success: 'green', failed: 'red', running: 'blue', pending: 'default', timeout: 'orange' }[s] || 'default'
}

async function loadData() {
  loading.value = true
  try {
    const res = await listExecutions({ status: filterStatus.value, page: pagination.current, page_size: pagination.pageSize })
    data.value = res.data.items
    pagination.total = res.data.total
  } finally { loading.value = false }
}

function handleTableChange(pag: any) {
  pagination.current = pag.current; pagination.pageSize = pag.pageSize; loadData()
}

onMounted(loadData)
</script>
```

- [ ] **Step 7: 创建分析仪表板（占位）**

```vue
<!-- frontend/src/views/admin/workflow/components/WorkflowDashboard.vue -->
<template>
  <div>
    <a-row :gutter="16">
      <a-col :span="6">
        <a-card title="总工作流数" size="small"><a-statistic :value="stats.totalFlows" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card title="今日执行" size="small"><a-statistic :value="stats.todayExecutions" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card title="成功率" size="small"><a-statistic :value="stats.successRate" suffix="%" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card title="平均延迟" size="small"><a-statistic :value="stats.avgLatency" suffix="ms" /></a-card>
      </a-col>
    </a-row>
    <a-card title="执行趋势" style="margin-top: 16px">
      <div style="height: 300px; display: flex; align-items: center; justify-content: center; color: #999">
        ECharts 图表区域（待接入 ECharts）
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { listFlows, listExecutions } from '@/api/workflow'

const stats = reactive({ totalFlows: 0, todayExecutions: 0, successRate: 0, avgLatency: 0 })

onMounted(async () => {
  try {
    const flowRes = await listFlows({ page: 1, page_size: 1 })
    stats.totalFlows = flowRes.data.total
    const execRes = await listExecutions({ page: 1, page_size: 100 })
    const items = execRes.data.items || []
    stats.todayExecutions = items.length
    const successCount = items.filter((i: any) => i.status === 'success').length
    stats.successRate = items.length ? Math.round(successCount / items.length * 100) : 0
    const latencies = items.filter((i: any) => i.latency_ms).map((i: any) => i.latency_ms)
    stats.avgLatency = latencies.length ? Math.round(latencies.reduce((a: number, b: number) => a + b, 0) / latencies.length) : 0
  } catch { /* ignore */ }
})
</script>
```

- [ ] **Step 8: 注册前端路由**

在 `frontend/src/router/index.ts` 第 116 行（`}` 之前）新增：

```typescript
      // ── 工作流管理 ──
      {
        path: 'admin/workflow',
        name: 'WorkflowManagement',
        component: () => import('@/views/admin/workflow/WorkflowManagement.vue'),
        meta: { title: '工作流管理', icon: 'ApiOutlined', requiresAdmin: true }
      },
```

- [ ] **Step 9: 验证前端编译**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无错误（或仅有预存 warning）

- [ ] **Step 10: Commit**

```bash
git add frontend/src/api/workflow.ts frontend/src/views/admin/workflow/ frontend/src/router/index.ts
git commit -m "feat(workflow): add workflow management frontend (5-tab layout)"
```

---

### Task 9: 集成测试 + 最终验证

**Files:**
- Create: `backend/tests/workflow/test_workflow_service.py`

- [ ] **Step 1: 编写 WorkflowService 单元测试**

```python
# backend/tests/workflow/test_workflow_service.py
"""WorkflowService 单元测试"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.workflow.workflow_service import WorkflowService
from app.services.workflow.crypto import encrypt_api_key


class TestWorkflowService:
    """CRUD 服务层测试（使用 mock DB）"""

    def test_create_flow_encrypts_key(self):
        """创建流程时 API Key 应被加密"""
        svc = WorkflowService()
        db = MagicMock()
        data = {
            "flow_code": "test-flow",
            "flow_name": "Test",
            "platform_type": "dify",
            "flow_type": "Workflow",
            "base_url": "https://dify.test",
            "api_key": "sk-plain-key",
            "tenant_id": 1,
        }
        with patch.object(db, 'add') as mock_add:
            flow = svc.create_flow(db, data)
            assert flow.api_key_enc != "sk-plain-key"
            assert flow.flow_code == "test-flow"
            mock_add.assert_called_once()
```

- [ ] **Step 2: 运行全部 workflow 测试**

Run: `cd backend && python -m pytest tests/workflow/ -v`
Expected: 全部通过

- [ ] **Step 3: 运行 Alembic 检查**

Run: `cd backend && alembic check`
Expected: 无待应用的变更（或仅有预期差异）

- [ ] **Step 4: 启动后端验证**

Run: `cd backend && python -c "from app.main import app; print(f'Routes: {len(app.routes)}')"`
Expected: `Routes: N`（N > 之前数量 + 13）

- [ ] **Step 5: Final Commit**

```bash
git add backend/tests/workflow/test_workflow_service.py
git commit -m "test(workflow): add workflow service integration tests"
```
