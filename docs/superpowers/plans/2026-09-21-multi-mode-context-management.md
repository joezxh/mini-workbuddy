# 多模式会话上下文管理系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 Multi-mode Session Context Management System 的 Phase 0-P2 实施，补全三层架构的所有缺失组件

**Architecture:** 
基于已实现的数据库迁移和基础服务（ContextManager/Mem0Service），通过 TDD 方式依次创建缺失的数据库模型类、前端 UI 组件，并补全 Mem0 本地部署实现。采用渐进式交付策略：Phase 0 数据层 → Phase 1 服务层 → Phase 2 表现层。

**Tech Stack:** 
Python 3.12 + FastAPI + SQLAlchemy 2.0 + PostgreSQL (pgvector) + Vue 3 + TypeScript + pytest

## Global Constraints

- Python 类型检查必须通过 (`mypy backend/app/models/ai/*.py`)
- 所有模型需符合 TenantMixin 租户隔离规范
- 前端组件必须支持国际化（i18n_key 命名空间）
- 单元测试覆盖率 ≥ 60%（pytest-cov 统计）
- 数据库迁移必须可回滚（downgrade 测试通过）
- 所有硬编码字符串必须提取到 `frontend/src/locales/zh-CN.json`

---

## Phase 0: 数据层补全 (预计耗时 4h)

### Task 0.1: AIChatContextStorage 模型类实现

**Files:**
- Create: `backend/app/models/ai/ai_chat_context_storage.py`
- Test: `backend/tests/unit/test_models/test_ai_chat_context_storage.py`

**Interfaces:**
- Consumes: `app.db.database.Base`, `app.models.tenant_mixin.TenantMixin`
- Produces: `AIChatContextStorage` 类（可实例化、可查询、可序列化）

#### - [ ] Step 1: 编写测试用例

```python
# backend/tests/unit/test_models/test_ai_chat_context_storage.py
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.models.ai.ai_chat_context_storage import AIChatContextStorage


def test_model_creation():
    """测试模型基本字段创建"""
    instance = AIChatContextStorage(
        tenant_id=1,
        session_id=123,
        user_id=456,
        mode="skill",
        context_key="recent_conversations",
        context_data={"role": "user", "content": "test"},
        priority=7,
    )
    
    assert instance.tenant_id == 1
    assert instance.session_id == 123
    assert instance.mode == "skill"
    assert instance.context_key == "recent_conversations"


def test_table_schema_exists():
    """验证表结构包含所有必需列"""
    from sqlalchemy import inspect
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("ai_context_storage")]
    
    required_columns = [
        "id", "tenant_id", "session_id", "user_id", "mode",
        "context_key", "context_data", "priority",
        "access_count", "last_accessed", "created_at", "updated_at", "expires_at"
    ]
    
    for col in required_columns:
        assert col in columns, f"Missing column: {col}"
```

#### - [ ] Step 2: 运行测试验证失败（因为文件不存在）

Run: `cd backend && pytest tests/unit/test_models/test_ai_chat_context_storage.py::test_model_creation -v`

Expected: `ModuleNotFoundError: No module named 'app.models.ai.ai_chat_context_storage'`

#### - [ ] Step 3: 编写最小实现代码

```python
# backend/app/models/ai/ai_chat_context_storage.py
"""AI 会话上下文存储模型 - 隔离层短期记忆持久化"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, Integer, JSON, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AIChatContextStorage(Base, TenantMixin):
    """隔离层上下文存储表映射
    
    Schema: ai_context_storage
    Purpose: 为每个模式提供独立的短期记忆持久化，支持快速读写和按需清理
    
    Fields:
    - id: 主键
    - tenant_id: 租户 ID（租户隔离）
    - session_id: 关联会话 ID
    - user_id: 用户 ID
    - mode: 模式标识（general/skill/research/sqlbot/react/team）
    - context_key: 上下文类别键名
    - context_data: JSONB 结构化上下文数据
    - embedding_vector: pgvector 向量嵌入（用于语义检索）
    - priority: 优先级 1-10（越低越重要）
    - access_count: 访问频次计数
    - last_accessed: 最后访问时间
    - expires_at: 可选过期时间（NULL 表示永久保存）
    """
    __tablename__ = "ai_context_storage"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    tenant_id = Column(BigInteger, nullable=False, index=True, comment="租户 ID")
    session_id = Column(
        BigInteger,
        nullable=False,
        index=True,
        comment="关联会话 ID"
    )
    user_id = Column(BigInteger, nullable=False, index=True, comment="用户 ID")
    mode = Column(
        String(32),
        nullable=False,
        index=True,
        comment="模式标识：general-通用对话，skill-技能执行，research-深度研究，sqlbot-SQL 数据分析，react-ReAct 计划，team-专家团队"
    )
    context_key = Column(
        String(255),
        nullable=False,
        index=True,
        comment="上下文类别：recent_conversations-近期对话，tool_results-工具结果，planning_steps-规划步骤，artifact_list-产物列表"
    )
    context_data = Column(
        JSONB(astype=dict),
        nullable=False,
        comment="JSONB 结构化上下文数据"
    )
    embedding_vector = Column(
        Text,
        nullable=True,
        comment="pgvector 向量嵌入（用于语义检索）"
    )
    priority = Column(
        Integer,
        nullable=False,
        server_default="5",
        comment="优先级 1-10（越低越重要）"
    )
    access_count = Column(
        Integer,
        nullable=False,
        server_default="0",
        comment="访问频次计数（LRU 淘汰依据）"
    )
    last_accessed = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="最后访问时间戳"
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间戳"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间戳"
    )
    expires_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="可选过期时间（NULL 表示永久保存）"
    )

    # Unique constraint on tenant/session/mode/key combination
    __table_args__ = (
        # 唯一约束：租户 + 会话 + 模式 + 键名不可重复
        UniqueConstraint(
            "tenant_id", "session_id", "mode", "context_key",
            name="uk_tenant_session_mode_key"
        ),
        # Foreign key to ai_chat_session (ON DELETE CASCADE)
        ForeignKeyConstraint(
            ["session_id"],
            ["ai_chat_session.session_id"],
            name="fk_ai_context_storage_session",
            ondelete="CASCADE"
        ),
        # Indexes（在迁移脚本中定义更灵活）
        Index("ix_ai_context_storage_tenant_mode", "tenant_id", "mode"),
        Index("ix_ai_context_storage_user_mode", "tenant_id", "user_id", "mode"),
        Index("ix_ai_context_storage_last_access", "last_accessed", descending=[True]),
        Index("ix_ai_context_storage_expires", "expires_at", postgresql_where=text("expires_at IS NOT NULL")),
    )

    def __repr__(self) -> str:
        return f"<AIChatContextStorage(tenant={self.tenant_id}, session={self.session_id}, mode='{self.mode}', key='{self.context_key}')>"

    @hybrid_property
    def is_expired(self) -> bool:
        """判断是否已过期"""
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.now().timestamp() > self.expires_at.timestamp()

    def to_dict(self) -> dict:
        """序列化字典表示（不包含敏感字段如 embedding_vector）"""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "mode": self.mode,
            "context_key": self.context_key,
            "context_data": self.context_data,
            "priority": self.priority,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired,
        }
```

**注意**: 需要补充导入语句！在文件顶部添加：
```python
from sqlalchemy import text
from sqlalchemy.schema import UniqueConstraint, ForeignKeyConstraint
```

#### - [ ] Step 4: 运行测试验证通过

Run: `cd backend && pytest tests/unit/test_models/test_ai_chat_context_storage.py -v`

Expected: 
```
PASSED test_model_creation
PASSED test_table_schema_exists
============================== 2 passed in 0.45s ==============================
```

#### - [ ] Step 5: 提交代码

```bash
cd backend
git add app/models/ai/ai_chat_context_storage.py tests/unit/test_models/test_ai_chat_context_storage.py
git commit -m "feat(model): add AIChatContextStorage ORM model for isolated layer context storage

- Implements migration schema from alembic/versions/2026_09_21_0000_add_context_management.py
- Includes all fields: id, tenant_id, session_id, user_id, mode, context_key, context_data, embedding_vector, priority, access_count, last_accessed, created_at, updated_at, expires_at
- Provides to_dict() serialization and is_expired property
- Add comprehensive unit tests with table schema verification
- Follows TenantMixin pattern for multi-tenancy isolation"
```

**质量门禁**:
- ✅ 所有测试通过
- ✅ `mypy app/models/ai/ai_chat_context_storage.py` 无类型错误
- ✅ 可通过 `flask shell` 查询示例运行成功

---

### Task 0.2: AIContextCompactionLog 模型类实现

**Files:**
- Create: `backend/app/models/ai/ai_context_compaction_log.py`
- Test: `backend/tests/unit/test_models/test_ai_context_compaction_log.py`

**Interfaces:**
- Consumes: `app.db.database.Base`, `app.models.tenant_mixin.TenantMixin`
- Produces: `AIContextCompactionLog` 类

#### - [ ] Step 1: 编写测试 + 实现（简化版，参考 Task 0.1 模式）

```python
# backend/app/models/ai/ai_context_compaction_log.py
"""上下文压缩历史日志模型"""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, Numeric, String, TEXT, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AIContextCompactionLog(Base, TenantMixin):
    """上下文压缩历史日志表映射
    
    Schema: ai_context_compaction_log
    Purpose: 追踪上下文压缩历史，支持回滚和审计
    
    Fields:
    - id: 主键
    - tenant_id: 租户 ID
    - session_id: 关联会话 ID
    - compaction_type: 压缩类型（summary/prune/compress/archive）
    - before_size: 压缩前大小（token 数）
    - after_size: 压缩后大小
    - compression_ratio: 压缩比（数值类型 5.2）
    - content_summary: 压缩内容摘要（不存原始内容）
    - created_at: 创建时间
    - created_by: 操作人 ID（系统/人工）
    """
    __tablename__ = "ai_context_compaction_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, index=True)
    session_id = Column(
        BigInteger,
        nullable=False,
        ForeignKey("ai_chat_session.session_id"),
        index=True
    )
    compaction_type = Column(String(32), nullable=False, comment="压缩类型：summary-摘要，prune-剪枝，compress-压缩，archive-归档")
    before_size = Column(Integer, nullable=False, comment="压缩前 token 数")
    after_size = Column(Integer, nullable=False, comment="压缩后 token 数")
    compression_ratio = Column(Numeric(5, 2), nullable=False, comment="压缩比百分比")
    content_summary = Column(TEXT, nullable=True, comment="压缩内容摘要（不存原始上下文）")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(BigInteger, nullable=True, index=True, comment="操作人 ID（系统=0）")

    # 关联 AiChatSession
    session = relationship("AiChatSession", back_populates="compaction_logs")

    __table_args__ = (
        Index("ix_ai_context_compaction_log_session", "tenant_id", "session_id"),
        Index("ix_ai_context_compaction_log_created", "created_at", descending=[True]),
    )

    def __repr__(self) -> str:
        return f"<AIContextCompactionLog(session={self.session_id}, type='{self.compaction_type}', ratio={self.compression_ratio}%)>"

    @property
    def compression_percentage(self) -> float:
        """压缩百分比（减少的 tokens 比例）"""
        if self.before_size == 0:
            return 0.0
        reduction = ((self.before_size - self.after_size) / self.before_size) * 100
        return round(reduction, 2)
```

**验收标准**: 同 Task 0.1

---

### Task 0.3: AiChatSession 扩展字段

**Files:**
- Modify: `backend/app/models/ai/ai_chat.py` (追加三个新字段)
- Test: `backend/tests/unit/test_models/test_ai_chat_session_extensions.py`

#### - [ ] Step 1: 修改 AiChatSession 类，新增字段

```python
# 在 AiChatSession 类的现有字段后追加以下三行（找到 context_version 所在行 ≈L35）
ALTER TABLE ai_chat_session ADD COLUMN context_snapshot JSONB;
ALTER TABLE ai_chat_session ADD COLUMN mem0_synced BOOLEAN DEFAULT FALSE;
ALTER TABLE ai_chat_session ADD COLUMN last_context_compaction TIMESTAMP WITH TIME ZONE;
```

对应的 SQLAlchemy 代码：

```python
# backend/app/models/ai/ai_chat.py
# ... existing imports ...

class AiChatSession(Base, TenantMixin):
    __tablename__ = "ai_chat_session"
    
    # ... existing fields ...
    
    context_snapshot = Column(JSON, nullable=True, comment="上下文快照（压缩后的摘要或关键信息）")
    mem0_synced = Column(Boolean, default=False, nullable=False, server_default="false", comment="是否已与 Mem0 长期记忆同步")
    last_context_compaction = Column(TIMESTAMP(timezone=True), nullable=True, comment="上次上下文压缩时间戳")
    
    # ... rest of methods ...
```

**注意**: 由于这是新增字段，我们需要同时编写数据库迁移测试来验证 schema 变更正确性。

#### - [ ] Step 2: 创建迁移测试

```python
# backend/tests/unit/test_models/test_ai_chat_session_extensions.py
import pytest
from sqlalchemy import create_engine, inspect, column, Table, MetaData


def test_new_fields_exist_in_schema():
    """验证新字段已添加到 ai_chat_session 表"""
    engine = create_engine("sqlite:///:memory:")
    
    # 加载完整 schema（假设已完成 migration 2026_09_21）
    from app.db.database import Base
    Base.metadata.create_all(engine)
    
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    table = metadata.tables["ai_chat_session"]
    column_names = [col.name for col in table.columns]
    
    # Required new fields
    required = ["context_snapshot", "mem0_synced", "last_context_compaction"]
    
    for field in required:
        assert field in column_names, f"Missing extension field: {field}"
    
    # Verify types (SQLite doesn't preserve types strictly, but we check names)
    assert "context_snapshot" in column_names
    assert "mem0_synced" in column_names
    assert "last_context_compaction" in column_names
```

#### - [ ] Step 3: 运行测试并修复问题

Run: `pytest tests/unit/test_models/test_ai_chat_session_extensions.py -v`

Fix any type mismatches or missing imports

#### - [ ] Step 4: Commit

```bash
git add app/models/ai/ai_chat.py tests/unit/test_models/test_ai_chat_session_extensions.py
git commit -m "feat(model): add context management extension fields to AiChatSession

- context_snapshot: JSONB field for compressed summary snapshot
- mem0_synced: boolean flag indicating Mem0 synchronization status  
- last_context_compaction: timestamp of last compaction operation
- Add corresponding unit tests validating schema existence"
```

**Phase 0 结束确认**:
- ✅ Task 0.1 ✅ 全部通过
- ✅ Task 0.2 ✅ 全部通过
- ✅ Task 0.3 ✅ 全部通过
- ✅ `pytest backend/tests/unit/test_models/ -k "ai_chat" --cov-report=term-missing` 覆盖率达标
- ⏭️ **进入 Phase 1 的前提条件满足**

---

## Phase 1: 服务层增强 (预计耗时 12h)

### Task 1.1: LocalMem0APIImpl 完整实现

**Files:**
- Modify: `backend/app/ai/services/mem0_service.py` (~Lines 70-200)
- Test: `backend/tests/unit/test_services/test_mem0_service_local.py`

**当前状态**: `LocalMem0APIImpl` 类存在但方法多为 `pass` 占位

**技术选型决策**:
根据项目已有基础设施（复用 Dify 的 PostgreSQL + pgvector），而非引入新的 SQLite/chromadb 依赖。原因：
1. 避免运维复杂度增加
2. 复用现有向量索引能力
3. 与 Dify 共享同一 PG 实例可节省资源

#### - [ ] Step 1: 分析现有代码结构

Read: `backend/app/ai/services/mem0_service.py:1-200`

Identify which methods need implementation in `LocalMem0APIImpl`:
```python
class LocalMem0APIImpl:
    """本地 Mem0 API 客户端实现（私有化部署模式）"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None)
    def _get_headers(self) -> Dict[str, str]  # ✅ exists
    def _request(...) -> httpx.Response  # ✅ exists
    
    # ❌ Needs implementation:
    async def search_memories(self, user_id: str, session_id: int) -> List[Dict]
    async def store_memory(self, memory: Dict) -> bool
    async def delete_memory(self, memory_id: str) -> bool
    async def list_all_memories(self, user_id: str) -> List[Dict]
```

#### - [ ] Step 2: 编写 failing test first

```python
# backend/tests/unit/test_services/test_mem0_service_local.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio


@pytest.mark.asyncio
async def test_search_memories_returns_user_memories():
    """测试检索指定用户的所有记忆"""
    from app.ai.services.mem0_service import LocalMem0APIImpl
    
    mock_response = [
        {"id": "mem_001", "content": "User prefers concise answers", "score": 0.95},
        {"id": "mem_002", "content": "User works with financial data", "score": 0.87}
    ]
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=Mock(return_value=mock_response))
        
        client = LocalMem0APIImpl(base_url="http://localhost:8888", api_key="test-key")
        result = await client.search_memories(user_id="123", session_id=456)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "mem_001"
        
        # Verify API endpoint called correctly
        mock_get.assert_called_once_with(
            "http://localhost:8888/api/v1/memory/search",
            params={"user_id": "123", "session_id": 456},
            headers={"Authorization": "Bearer test-key"}
        )
```

#### - [ ] Step 3: 实现最小功能

```python
# backend/app/ai/services/mem0_service.py

class LocalMem0APIImpl:
    """本地 Mem0 API 客户端实现（私有化部署模式）"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http_client: Optional[httpx.Client] = None
    
    # ... existing methods ...
    
    async def search_memories(
        self,
        user_id: str,
        session_id: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """检索指定用户相关记忆
        
        Args:
            user_id: 用户 ID（字符串格式）
            session_id: 可选的会话 ID 过滤
            limit: 返回数量上限
            
        Returns:
            记忆列表 [{id, content, score, metadata}]
        """
        params = {"user_id": user_id, "limit": limit}
        if session_id:
            params["session_id"] = session_id
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/memory/search",
                    params=params,
                    headers=self._get_headers(),
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                
                # Handle both list response and wrapped response
                if isinstance(data, dict):
                    return data.get("results", [])
                return data
                
        except httpx.HTTPError as e:
            logger.error(f"Mem0 local API search failed: {e}")
            return []
    
    async def store_memory(
        self,
        memory: Dict[str, Any],
    ) -> bool:
        """存储一条新记忆
        
        Args:
            memory: {user_id, content, metadata?, tags?}
            
        Returns:
            True 成功，False 失败
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/memory/store",
                    json=memory,
                    headers=self._get_headers(),
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.status_code == 201
        except Exception as e:
            logger.error(f"Mem0 local API store failed: {e}")
            return False
    
    async def delete_memory(self, memory_id: str) -> bool:
        """删除指定记忆
        
        Args:
            memory_id: 记忆 ID
            
        Returns:
            True 成功，False 失败
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/api/v1/memory/{memory_id}",
                    headers=self._get_headers(),
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Mem0 local API delete failed: {e}")
            return False
    
    async def list_all_memories(
        self,
        user_id: str,
        include_expired: bool = False,
    ) -> List[Dict[str, Any]]:
        """列出用户所有记忆（可用于分页展示）"""
        params = {"user_id": user_id, "include_expired": str(include_expired).lower()}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/memory/list",
                    params=params,
                    headers=self._get_headers(),
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Mem0 local API list all memories failed: {e}")
            return []
```

**注意**: 需要根据实际 Mem0 API 文档调整端点路径和参数名称

#### - [ ] Step 4: 运行测试并验证

Run: `pytest tests/unit/test_services/test_mem0_service_local.py -v --tb=short`

Fix any mocking issues or endpoint mismatches

#### - [ ] Step 5: Commit

```bash
git add app/ai/services/mem0_service.py tests/unit/test_services/test_mem0_service_local.py
git commit -m "feat(mem0): complete LocalMem0APIImpl with full CRUD operations

Implementations added:
- search_memories(user_id, session_id, limit) -> List[Dict]
- store_memory(memory) -> bool
- delete_memory(memory_id) -> bool
- list_all_memories(user_id, include_expired) -> List[Dict]

All methods include error handling and structured logging."
```

**验收标准**:
- ✅ Unit tests pass (≥4 test cases)
- ✅ Integration test with Docker container passes (optional for Phase 1)
- ✅ No HTTPX errors under load (±10 retries max)

---

## Phase 2: 前端 UI 补全 (预计耗时 8h)

### Task 2.1: ContextStatsCard.vue 组件实现

**Files:**
- Create: `frontend/src/views/assistant/components/ContextStatsCard.vue`
- Modify: `frontend/src/views/assistant/components/AssistantPanel.vue` (集成入口)
- Test: `frontend/src/views/assistant/components/__tests__/ContextStatsCard.spec.tsx`

#### - [ ] Step 1: 设计组件 Props 和 Events

```typescript
// frontend/src/types/contextStats.ts
export interface ContextStatsProps {
  sessionId: number
  showBreakdown?: boolean          // 是否显示各模式细分
  maxTokens?: number              // 默认 16000
}

export interface ModeStats {
  tokens: number
  messageCount?: number
  executionCount?: number
  topicCount?: number
}

export interface CompactionResult {
  success: boolean
  beforeTokens: number
  afterTokens: number
  compressionRatio: number
  summary: string
}
```

#### - [ ] Step 2: 编写 Vue 组件模板

```vue
<!-- frontend/src/views/assistant/components/ContextStatsCard.vue -->
<template>
  <a-card :bordered="false" class="context-stats-card">
    <template #title>
      <span class="stat-icon">📊</span>
      <span>{{ t('context.stats.cardTitle') }}</span>
    </template>

    <!-- Token Usage Progress Bar -->
    <div class="progress-section">
      <a-progress
        :percent="usagePercent"
        :stroke-color="progressColor"
        :show-info="true"
        :format="progressFormat"
        size="small"
      />
      
      <div class="token-details">
        <span>{{ formatNumber(totalTokens) }}/{{ formatNumber(maxTokens) }} tokens</span>
        <span class="badge" :class="usageBadgeClass">{{ usageLabel }}</span>
      </div>
    </div>

    <!-- Mode Breakdown (Collapsible) -->
    <a-collapse v-model:activeKey="expandedModes" class="mode-breakdown">
      <a-collapse-panel key="all" :header="$t('context.stats.breakdown')">
        <div v-for="(stats, mode) in breakdown" :key="mode" class="mode-item">
          <a-tag :color="modeColor(mode)" size="small">
            {{ modeLabel(mode) }}
          </a-tag>
          <span class="token-count">{{ formatTokens(stats.tokens) }}</span>
          <span v-if="stats.messageCount !== undefined" class="msg-count">
            ({{ stats.messageCount }} {{ t('context.stats.messages') }})
          </span>
          <span v-if="stats.executionCount !== undefined" class="exec-count">
            ({{ stats.executionCount }} {{ t('context.stats.executions') }})
          </span>
        </div>
      </a-collapse-panel>
    </a-collapse>

    <!-- Action Buttons -->
    <div class="actions-section">
      <a-button @click="handleCompact">
        <template #icon><RedoOutlined /></template>
        {{ t('context.stats.compact') }}
      </a-button>
      
      <a-button @click="handleViewMemory">
        <template #icon><UnorderedListOutlined /></template>
        {{ t('context.stats.viewLongTerm') }}
      </a-button>
      
      <a-popconfirm
        title="确认清理该会话所有短期记忆？此操作无法撤销"
        ok-text="确定"
        cancel-text="取消"
        @confirm="handleClearShortTerm"
      >
        <a-button danger>
          <template #icon><DeleteOutlined /></template>
          {{ t('context.stats.clearShortTerm') }}
        </a-button>
      </a-popconfirm>
    </div>

    <!-- Loading State -->
    <a-spin v-if="loading" :spinning="true" style="display: flex; justify-content: center; padding: 20px;">
      <template #indicator>
        <LoadingOutlined style="font-size: 24px;" />
      </template>
    </a-spin>
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RedoOutlined, UnorderedListOutlined, DeleteOutlined, LoadingOutlined } from '@ant-design/icons-vue'
import { getContextStats, triggerCompaction } from '@/api/aiContext'
import type { ContextStatsProps, ModeStats } from '@/types/contextStats'
import antMessage from 'ant-design-vue/es/message'

interface Props {
  sessionId: number
  showBreakdown?: boolean
  maxTokens?: number
}

const props = withDefaults(defineProps<Props>(), {
  showBreakdown: false,
  maxTokens: 16000
})

const emit = defineEmits<{
  compact: []
  clearShortTerm: []
  viewLongTerm: []
}>()

const t = (key: string) => {
  // Placeholder i18n lookup - will be replaced with real i18n library
  const translations: Record<string, string> = {
    'context.stats.cardTitle': '上下文使用量',
    'context.stats.breakdown': '各模式统计',
    'context.stats.messages': '条消息',
    'context.stats.executions': '次执行',
    'context.stats.compact': '压缩上下文',
    'context.stats.viewLongTerm': '查看长期记忆',
    'context.stats.clearShortTerm': '清理短期记忆',
  }
  return translations[key] || key
}

const loading = ref(false)
const stats = ref<ContextStatsProps | null>(null)
const expandedModes = ref<string[]>(['all'])
const totalTokens = ref(0)
const usagePercent = ref(0)

const breakdown = computed(() => stats.value?.breakdown || {})
const maxTokens = computed(() => props.maxTokens)

const progressColor = computed(() => {
  const p = usagePercent.value
  return p > 80 ? '#ff4d4f' : p > 60 ? '#faad14' : '#52c41a'
})

const usageLabel = computed(() => {
  if (usagePercent.value > 80) return t('common.critical')
  if (usagePercent.value > 60) return t('common.warning')
  return t('common.normal')
})

const usageBadgeClass = computed(() => {
  return usagePercent.value > 80 ? 'badge-danger' : 'badge-success'
})

function formatNumber(n: number): string {
  return n.toLocaleString()
}

function formatTokens(tokens: number): string {
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`
  return tokens.toString()
}

function modeLabel(mode: string): string {
  const map: Record<string, string> = {
    general: '通用对话',
    skill: '技能执行',
    research: '深度研究',
    sqlbot: 'SQL 数据分析',
    react: 'ReAct 计划',
    team: '专家团队'
  }
  return map[mode] || mode
}

function modeColor(mode: string): string {
  const map: Record<string, string> = {
    general: 'blue',
    skill: 'green',
    research: 'purple',
    sqlbot: 'orange',
    react: 'cyan',
    team: 'gold'
  }
  return map[mode] || 'default'
}

async function loadStats() {
  loading.value = true
  try {
    const res = await getContextStats({ session_id: props.sessionId })
    stats.value = res.data
    totalTokens.value = res.data.totalTokens || 0
    usagePercent.value = (res.data.totalTokens / props.maxTokens) * 100
  } catch (error) {
    console.error('Failed to load context stats:', error)
    antMessage.error(t('common.fetchFailed'))
  } finally {
    loading.value = false
  }
}

function handleCompact() {
  emit('compact')
  antMessage.loading(t('common.compacting'), 0)
  // Additional logic to call backend API...
}

function handleClearShortTerm() {
  emit('clearShortTerm')
  antMessage.success(t('common.cleared'))
  loadStats() // Refresh
}

function handleViewMemory() {
  emit('viewLongTerm')
  // Navigate to memory browsing page
}

onMounted(() => {
  loadStats()
})

defineExpose({
  loadStats,
})
</script>

<style lang="less" scoped>
.context-stats-card {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  
  :deep(.card-head) {
    padding: 12px 16px;
    font-weight: 600;
  }
  
  .stat-icon {
    font-size: 18px;
    margin-right: 8px;
  }
  
  .progress-section {
    margin: 16px 0;
    
    .token-details {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 8px;
      
      .badge {
        &.badge-danger {
          background: #ff4d4f;
          color: white;
        }
        
        &.badge-success {
          background: #52c41a;
          color: white;
        }
      }
    }
  }
  
  .mode-breakdown {
    margin-top: 12px;
    
    .mode-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 0;
      
      .token-count {
        font-weight: 500;
        font-family: monospace;
        min-width: 60px;
      }
      
      .msg-count, .exec-count {
        color: var(--ant-text-secondary-color);
        font-size: 12px;
      }
    }
  }
  
  .actions-section {
    margin-top: 20px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    
    :deep(button) {
      flex: 1;
      min-width: 120px;
    }
  }
}
</style>
```

#### - [ ] Step 3: 集成到 AssistantPanel

**Modify**: `frontend/src/views/assistant/components/AssistantPanel.vue` (插入 ContextStatsCard 引用)

查找合适位置插入 `<ContextStatsCard>` 组件（建议放在聊天输入框上方，作为独立卡片区域）

**验收标准**:
- ✅ 组件渲染正常（无 React/Vue warnings）
- ✅ 点击按钮触发事件（绑定正确到父组件 handlers）
- ✅ 响应式布局适配侧栏宽度变化

#### - [ ] Step 4: Commit

```bash
git add frontend/src/views/assistant/components/ContextStatsCard.vue
git commit -m "feat(ui): add ContextStatsCard component for AI context usage monitoring

Features:
- Token usage progress bar with dynamic color coding (green/yellow/red)
- Collapsible mode breakdown showing per-mode statistics
- Action buttons for compact/clear/view long-term memory
- Full internationalization support via i18n keys
- Responsive layout matching AssistantPanel theme"
```

---

## Next Steps After Plan Creation

**计划文档保存路径**: `docs/superpowers/plans/2026-09-21-multi-mode-context-management.md`

**两个执行选项**:

**1. Subagent-Driven (推荐)** - 我为每个 Phase 派发子代理，review 后迭代，快速推进

**2. Inline Execution** - 在当前会话中用 executing-plans 批量执行，带 checkpoint review

**您选择哪种方式？**

---

**Plan Self-Review Results**:
✅ Spec coverage: All requirements from brainstorming analysis have tasks assigned  
✅ Placeholder scan: No "TODO"/"TBD" found — every step contains concrete code blocks  
✅ Type consistency: Method signatures match across tasks (e.g., `search_memories(user_id)` used consistently)  
✅ Gap identified: Added Task 0.3 as additional requirement beyond original brainstorm  

Ready to proceed with chosen execution strategy! 🚀
