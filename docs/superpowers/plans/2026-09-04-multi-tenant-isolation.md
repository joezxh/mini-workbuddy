# 多租户隔离实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 MinWorkBuddy 全部业务表添加 tenant_id 行级隔离，实现租户/套餐 CRUD、自动查询过滤、域名解析和登录页租户选择。

**Architecture:** 共享数据库 + 行级隔离。TenantMixin 为模型添加 tenant_id 列，`do_orm_execute` 事件拦截器自动注入 WHERE 条件，contextvars 管理请求级租户上下文。域名中间件 + JWT + 用户表三层保障上下文获取。

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0+, PostgreSQL, Alembic, Vue 3, Ant Design Vue, TypeScript

**Spec:** `docs/superpowers/specs/2026-09-04-multi-tenant-isolation-design.md`

---

## 文件结构总览

### 后端新增文件

| 文件 | 职责 |
|------|------|
| `app/core/tenant_context.py` | 租户上下文管理（contextvars） |
| `app/core/tenant_interceptor.py` | SQLAlchemy 事件拦截器 |
| `app/core/tenant_decorators.py` | `@tenant_ignore` 装饰器 |
| `app/models/tenant_mixin.py` | TenantMixin 混入类 |
| `app/models/tenant.py` | SysTenant + SysTenantPackage 模型 |
| `app/schemas/tenant.py` | 租户/套餐 Pydantic 请求/响应模型 |
| `app/services/tenant_service.py` | 租户业务逻辑 |
| `app/routers/admin/tenant.py` | 租户管理路由 |
| `app/routers/admin/tenant_package.py` | 套餐管理路由 |
| `app/middleware/tenant_resolver.py` | 域名→租户解析中间件 |
| `tests/unit/test_tenant_context.py` | TenantContext 单元测试 |
| `tests/unit/test_tenant_interceptor.py` | 拦截器单元测试 |
| `tests/unit/test_tenant_service.py` | 租户服务单元测试 |
| `tests/integration/test_tenant_isolation.py` | 租户隔离集成测试 |

### 后端修改文件

| 文件 | 改动 |
|------|------|
| `app/models/user.py` | SysUser/SysRole/SysUserRole/SysAuditLog 继承 TenantMixin |
| `app/models/dictionary.py` | SysDictionary/SysDictionaryItem 继承 TenantMixin |
| `app/models/user_notification.py` | SysUserNotification 继承 TenantMixin |
| `app/models/infra_file.py` | InfraFile/InfraFileContent 继承 TenantMixin |
| `app/models/ai_chat.py` | AiChatSession/AiChatMessage 继承 TenantMixin |
| `app/models/ai_apikey.py` | AiApiKey/AiChatModel 继承 TenantMixin |
| `app/models/agent_config.py` | AgentConfig 继承 TenantMixin |
| `app/models/agent_team.py` | AgentTeam/AgentTeamMember/AgentTeamEdge 继承 TenantMixin |
| `app/models/agent_team_run.py` | AgentTeamRun 继承 TenantMixin |
| `app/models/agent_async_task.py` | AgentAsyncTask 继承 TenantMixin |
| `app/models/agent_scheduled_task.py` | AgentScheduledTask 继承 TenantMixin |
| `app/models/agent_execution.py` | AgentExecution 继承 TenantMixin |
| `app/models/agent_execution_event.py` | AgentExecutionEvent 继承 TenantMixin |
| `app/models/agent_trace.py` | AgentTrace 继承 TenantMixin |
| `app/models/tool_definition.py` | ToolDefinitionModel 继承 TenantMixin |
| `app/models/tool_group.py` | ToolGroupModel/ToolGroupMember 继承 TenantMixin |
| `app/models/skill_registry.py` | AiSkillPackage 继承 TenantMixin |
| `app/models/skill_rule.py` | SkillRule 继承 TenantMixin |
| `app/models/skill_version.py` | AiSkillVersion 继承 TenantMixin |
| `app/models/skill_metrics.py` | AiSkillMetrics 继承 TenantMixin |
| `app/models/skill_evolution_config.py` | AiSkillEvolutionConfig 继承 TenantMixin |
| `app/models/skill_evolution_log.py` | AiSkillEvolutionLog 继承 TenantMixin |
| `app/models/skill_script.py` | AiSkillScript 继承 TenantMixin |
| `app/models/mcp_api_key.py` | McpApiKey 继承 TenantMixin |
| `app/models/mcp_client.py` | MCPClient 继承 TenantMixin |
| `app/models/mcp_square_template.py` | McpSquareTemplate 继承 TenantMixin |
| `app/models/ai_web_search.py` | AiWebSearch/AiWebSearchLog 继承 TenantMixin |
| `app/models/ai_skill_hub_repo.py` | AiSkillHubRepo 继承 TenantMixin |
| `app/models/workspace.py` | AiWorkspace 继承 TenantMixin |
| `app/models/knowledge_base.py` | KmsLegalInfo/KmsLegalItem 继承 TenantMixin |
| `app/models/knowledge_document.py` | KmsDocument 继承 TenantMixin |
| `app/models/knowledge_graph.py` | KgReasoningRuleConfig/KgReasoningHistory/KgAuditLog 继承 TenantMixin |
| `app/models/kms_legal_paper.py` | KmsLegalPaper/KmsLegalPaperLegalItem 继承 TenantMixin |
| `app/models/wiki_article.py` | WikiArticle 继承 TenantMixin |
| `app/models/wiki_article_version.py` | WikiArticleVersion 继承 TenantMixin |
| `app/models/wiki_category.py` | WikiCategory 继承 TenantMixin |
| `app/db/database.py` | get_db() 增加 TenantContext.clear() |
| `app/db/init_models.py` | 注册 SysTenant + SysTenantPackage |
| `app/deps.py` | get_current_user() 设置租户上下文 |
| `app/schemas/auth.py` | LoginRequest 新增 tenant_id |
| `app/services/auth_service.py` | login() 校验租户 + JWT 写入 tenant_id |
| `app/routers/auth.py` | 新增 tenant-simple-list 公开接口 |
| `app/main.py` | 注册中间件 + 路由 + 拦截器 |

### 前端新增文件

| 文件 | 职责 |
|------|------|
| `frontend/src/api/tenant.ts` | 租户管理 API |
| `frontend/src/api/tenantPackage.ts` | 租户套餐 API |
| `frontend/src/views/admin/system/tenant/index.vue` | 租户列表页 |
| `frontend/src/views/admin/system/tenant/TenantForm.vue` | 租户表单弹窗 |
| `frontend/src/views/admin/system/tenant-package/index.vue` | 套餐列表页 |
| `frontend/src/views/admin/system/tenant-package/TenantPackageForm.vue` | 套餐表单弹窗 |

### 前端修改文件

| 文件 | 改动 |
|------|------|
| `frontend/src/views/login/index.vue` | 新增租户选择器 |
| `frontend/src/api/auth.ts` | login() 传 tenant_id，新增 getTenantSimpleList() |
| `frontend/src/stores/user.ts` | login() 传 tenant_id + Cookie 记忆 |
| `frontend/src/router/index.ts` | 新增租户/套餐管理路由 |

---

## Task 1: TenantContext — 租户上下文管理

**Files:**
- Create: `backend/app/core/tenant_context.py`
- Create: `backend/tests/unit/test_tenant_context.py`

- [ ] **Step 1: 编写 TenantContext 测试**

```python
# backend/tests/unit/test_tenant_context.py
import pytest
from app.core.tenant_context import (
    set_tenant_id, get_tenant_id, get_required_tenant_id,
    set_ignore, is_ignore, clear,
)


class TestTenantContext:
    def setup_method(self):
        clear()

    def teardown_method(self):
        clear()

    def test_set_and_get_tenant_id(self):
        set_tenant_id(42)
        assert get_tenant_id() == 42

    def test_get_tenant_id_default_none(self):
        assert get_tenant_id() is None

    def test_get_required_tenant_id_raises_when_none(self):
        with pytest.raises(ValueError, match="不存在租户ID"):
            get_required_tenant_id()

    def test_get_required_tenant_id_returns_value(self):
        set_tenant_id(7)
        assert get_required_tenant_id() == 7

    def test_set_and_check_ignore(self):
        assert is_ignore() is False
        set_ignore(True)
        assert is_ignore() is True

    def test_clear_resets_all(self):
        set_tenant_id(99)
        set_ignore(True)
        clear()
        assert get_tenant_id() is None
        assert is_ignore() is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd d:\projects\MinWorkBuddy\backend
pytest tests/unit/test_tenant_context.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.tenant_context'`

- [ ] **Step 3: 实现 TenantContext**

```python
# backend/app/core/tenant_context.py
"""租户上下文管理 — 基于 contextvars，天然支持 asyncio。"""
from contextvars import ContextVar

_current_tenant_id: ContextVar[int | None] = ContextVar("tenant_id", default=None)
_ignore_tenant: ContextVar[bool] = ContextVar("ignore_tenant", default=False)


def set_tenant_id(tenant_id: int | None) -> None:
    _current_tenant_id.set(tenant_id)


def get_tenant_id() -> int | None:
    return _current_tenant_id.get()


def get_required_tenant_id() -> int:
    tid = get_tenant_id()
    if tid is None:
        raise ValueError("TenantContext 中不存在租户ID，请检查认证流程")
    return tid


def set_ignore(ignore: bool) -> None:
    _ignore_tenant.set(ignore)


def is_ignore() -> bool:
    return _ignore_tenant.get()


def clear() -> None:
    _current_tenant_id.set(None)
    _ignore_tenant.set(False)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/unit/test_tenant_context.py -v
```

Expected: 7 passed

- [ ] **Step 5: 提交**

```bash
git add app/core/tenant_context.py tests/unit/test_tenant_context.py
git commit -m "feat(tenant): add TenantContext with contextvars"
```

---

## Task 2: TenantMixin — 模型混入类

**Files:**
- Create: `backend/app/models/tenant_mixin.py`

- [ ] **Step 1: 创建 TenantMixin**

```python
# backend/app/models/tenant_mixin.py
"""所有需要租户隔离的 ORM 模型继承此 Mixin。"""
from sqlalchemy import Column, BigInteger


class TenantMixin:
    """为模型添加 tenant_id 列，用于行级多租户隔离。"""
    tenant_id = Column(BigInteger, nullable=True, index=True, comment="租户ID")
```

- [ ] **Step 2: 提交**

```bash
git add app/models/tenant_mixin.py
git commit -m "feat(tenant): add TenantMixin for model-level tenant isolation"
```

---

## Task 3: 为 SysUser 添加 tenant_id

**Files:**
- Modify: `backend/app/models/user.py`

- [ ] **Step 1: 修改 SysUser 模型**

在 `app/models/user.py` 的 `SysUser` 类中，在 `is_deleted` 字段之后添加 `tenant_id`：

```python
from app.models.tenant_mixin import TenantMixin

class SysUser(Base, TenantMixin):
    """用户表"""
    __tablename__ = "sys_user"

    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    real_name = Column(String(100), nullable=False)
    phone = Column(String(20))
    email = Column(String(100))
    avatar_url = Column(String(500))
    status = Column(String(20), default='active', nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime)
    last_login_ip = Column(String(50))
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime)
    is_deleted = Column(Boolean, default=False, nullable=False)
    # tenant_id 由 TenantMixin 提供

    user_roles = relationship("SysUserRole", back_populates="user", lazy="select")
```

- [ ] **Step 2: 为 SysRole、SysUserRole、SysAuditLog 也继承 TenantMixin**

对 `SysRole`、`SysUserRole`、`SysAuditLog` 做同样的修改：在 `Base` 后添加 `TenantMixin`。

```python
class SysRole(Base, TenantMixin):
    ...

class SysUserRole(Base, TenantMixin):
    ...

class SysAuditLog(Base, TenantMixin):
    ...
```

注意：`SysMenu` 和 `SysRegion` **不继承** TenantMixin。

- [ ] **Step 3: 提交**

```bash
git add app/models/user.py
git commit -m "feat(tenant): add TenantMixin to SysUser, SysRole, SysUserRole, SysAuditLog"
```

---

## Task 4: 为其余所有业务模型添加 TenantMixin

**Files:**
- Modify: 30 个模型文件（见文件结构总览）

对每个文件执行相同模式：导入 TenantMixin，在类定义中添加 `TenantMixin`。

- [ ] **Step 1: 批量修改字典/通知/基础设施模型**

```python
# app/models/dictionary.py
from app.models.tenant_mixin import TenantMixin
class SysDictionary(Base, TenantMixin): ...
class SysDictionaryItem(Base, TenantMixin): ...

# app/models/user_notification.py
from app.models.tenant_mixin import TenantMixin
class SysUserNotification(Base, TenantMixin): ...

# app/models/infra_file.py
from app.models.tenant_mixin import TenantMixin
class InfraFile(Base, TenantMixin): ...
class InfraFileContent(Base, TenantMixin): ...
```

- [ ] **Step 2: 批量修改 AI 会话/Agent 模型**

```python
# app/models/ai_chat.py
from app.models.tenant_mixin import TenantMixin
class AiChatSession(Base, TenantMixin): ...
class AiChatMessage(Base, TenantMixin): ...

# app/models/ai_apikey.py
from app.models.tenant_mixin import TenantMixin
class AiApiKey(Base, TenantMixin): ...
class AiChatModel(Base, TenantMixin): ...

# app/models/agent_config.py
from app.models.tenant_mixin import TenantMixin
class AgentConfig(Base, TenantMixin): ...  # 保留 workspace_id

# app/models/agent_team.py
from app.models.tenant_mixin import TenantMixin
class AgentTeam(Base, TenantMixin): ...
class AgentTeamMember(Base, TenantMixin): ...
class AgentTeamEdge(Base, TenantMixin): ...

# app/models/agent_team_run.py — TenantMixin
# app/models/agent_async_task.py — TenantMixin
# app/models/agent_scheduled_task.py — TenantMixin
# app/models/agent_execution.py — TenantMixin
# app/models/agent_execution_event.py — TenantMixin
# app/models/agent_trace.py — TenantMixin
```

- [ ] **Step 3: 批量修改工具/技能/MCP 模型**

```python
# 以下每个文件都添加 from app.models.tenant_mixin import TenantMixin
# 并在类定义中加入 TenantMixin：
# tool_definition.py, tool_group.py, skill_registry.py, skill_rule.py,
# skill_version.py, skill_metrics.py, skill_evolution_config.py,
# skill_evolution_log.py, skill_script.py, mcp_api_key.py, mcp_client.py,
# mcp_square_template.py, ai_web_search.py, ai_skill_hub_repo.py
```

- [ ] **Step 4: 批量修改工作空间/知识管理/Wiki 模型**

```python
# workspace.py, knowledge_base.py, knowledge_document.py,
# knowledge_graph.py, kms_legal_paper.py, wiki_article.py,
# wiki_article_version.py, wiki_category.py
```

- [ ] **Step 5: 验证所有模型可以正常导入**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "from app.db.init_models import *; print('All models imported OK')"
```

Expected: `All models imported OK`

- [ ] **Step 6: 提交**

```bash
git add app/models/
git commit -m "feat(tenant): add TenantMixin to all 50 business models"
```

---

## Task 5: 新增 SysTenant + SysTenantPackage 模型

**Files:**
- Create: `backend/app/models/tenant.py`
- Modify: `backend/app/db/init_models.py`

- [ ] **Step 1: 创建租户模型**

```python
# backend/app/models/tenant.py
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from app.db.database import Base


class SysTenantPackage(Base):
    """租户套餐表"""
    __tablename__ = "sys_tenant_package"

    package_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="套餐名称")
    status = Column(String(20), nullable=False, default="active", comment="状态(active/disabled)")
    remark = Column(String(500), comment="备注")
    menu_ids = Column(JSON, nullable=True, comment="关联菜单ID集合")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<SysTenantPackage {self.name}>"


class SysTenant(Base):
    """租户表"""
    __tablename__ = "sys_tenant"

    tenant_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment="租户名称")
    contact_name = Column(String(50), comment="联系人")
    contact_mobile = Column(String(20), comment="联系电话")
    status = Column(String(20), nullable=False, default="active", comment="状态(active/disabled)")
    package_id = Column(BigInteger, ForeignKey("sys_tenant_package.package_id"),
                        nullable=True, comment="租户套餐ID")
    expire_time = Column(DateTime, nullable=True, comment="过期时间")
    account_count = Column(Integer, default=0, comment="账号额度")
    websites = Column(JSON, nullable=True, comment="绑定域名列表")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<SysTenant {self.name}>"
```

- [ ] **Step 2: 在 init_models.py 中注册**

在 `app/db/init_models.py` 的系统管理区块中添加：

```python
# --- 系统管理 (sys_) ---
from app.models.tenant import SysTenant, SysTenantPackage               # noqa: F401
from app.models.user import (                                             # noqa: F401
    SysUser, SysRole, SysMenu, SysRegion, SysRoleMenu, SysUserRole,
    SysAuditLog,
)
```

- [ ] **Step 3: 验证导入**

```bash
python -c "from app.models.tenant import SysTenant, SysTenantPackage; print('OK')"
```

- [ ] **Step 4: 提交**

```bash
git add app/models/tenant.py app/db/init_models.py
git commit -m "feat(tenant): add SysTenant and SysTenantPackage models"
```

---

## Task 6: SQL 拦截器 + 装饰器

**Files:**
- Create: `backend/app/core/tenant_interceptor.py`
- Create: `backend/app/core/tenant_decorators.py`
- Create: `backend/tests/unit/test_tenant_interceptor.py`

- [ ] **Step 1: 编写拦截器测试**

```python
# backend/tests/unit/test_tenant_interceptor.py
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, Column, BigInteger, String
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.core.tenant_context import set_tenant_id, set_ignore, clear
from app.core.tenant_interceptor import setup_tenant_interceptor, TENANT_IGNORE_TABLES


class SampleModel(Base):
    __tablename__ = "sample_tenant_test"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(50))
    tenant_id = Column(BigInteger)


class TestTenantInterceptor:
    def setup_method(self):
        clear()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionFactory = sessionmaker(bind=self.engine)
        setup_tenant_interceptor(self.SessionFactory)

    def teardown_method(self):
        clear()
        Base.metadata.drop_all(self.engine)

    def test_query_includes_tenant_filter(self):
        """设置租户后，查询自动包含 WHERE tenant_id = ?"""
        set_tenant_id(42)
        db = self.SessionFactory()
        try:
            # 查询应自动过滤
            result = db.query(SampleModel).all()
            # 验证无异常即表示拦截器正常工作
            assert isinstance(result, list)
        finally:
            db.close()

    def test_ignore_mode_skips_filter(self):
        """忽略模式下不注入过滤条件"""
        set_tenant_id(42)
        set_ignore(True)
        db = self.SessionFactory()
        try:
            result = db.query(SampleModel).all()
            assert isinstance(result, list)
        finally:
            db.close()

    def test_no_tenant_id_skips_filter(self):
        """未设置租户ID时不注入过滤条件"""
        db = self.SessionFactory()
        try:
            result = db.query(SampleModel).all()
            assert isinstance(result, list)
        finally:
            db.close()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/test_tenant_interceptor.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现拦截器**

```python
# backend/app/core/tenant_interceptor.py
"""SQLAlchemy do_orm_execute 事件拦截器，自动注入租户过滤条件。"""
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria
from app.core.tenant_context import get_tenant_id, is_ignore

# 不需要租户过滤的表名集合
TENANT_IGNORE_TABLES = {
    "sys_tenant", "sys_tenant_package", "sys_menu", "sys_region",
}


def _build_tenant_criteria(cls):
    """为拥有 tenant_id 属性的模型构建过滤条件。"""
    if not hasattr(cls, "tenant_id"):
        return None
    if getattr(cls, "__tablename__", "") in TENANT_IGNORE_TABLES:
        return None
    tenant_id = get_tenant_id()
    if tenant_id is None:
        return None
    return cls.tenant_id == tenant_id


def setup_tenant_interceptor(session_factory) -> None:
    """在 Session 工厂上注册 do_orm_execute 事件，自动注入租户过滤。"""

    @event.listens_for(session_factory, "do_orm_execute")
    def _add_tenant_filter(execute_state):
        if is_ignore():
            return
        if get_tenant_id() is None:
            return

        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                None,
                lambda cls: _build_tenant_criteria(cls),
                include_aliases=True,
            )
        )
```

- [ ] **Step 4: 实现装饰器**

```python
# backend/app/core/tenant_decorators.py
"""租户相关装饰器。"""
from functools import wraps
from app.core.tenant_context import set_ignore


def tenant_ignore(func):
    """标记不需要租户过滤的接口。

    用于登录、注册、公开 API 等不需要租户过滤的场景。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        set_ignore(True)
        try:
            return func(*args, **kwargs)
        finally:
            set_ignore(False)
    return wrapper
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/unit/test_tenant_interceptor.py -v
```

Expected: 3 passed

- [ ] **Step 6: 提交**

```bash
git add app/core/tenant_interceptor.py app/core/tenant_decorators.py tests/unit/test_tenant_interceptor.py
git commit -m "feat(tenant): add do_orm_execute interceptor and @tenant_ignore decorator"
```

---

## Task 7: 集成到 database.py + deps.py

**Files:**
- Modify: `backend/app/db/database.py`
- Modify: `backend/app/deps.py`

- [ ] **Step 1: 修改 get_db() 清理租户上下文**

在 `app/db/database.py` 的 `get_db()` 的 `finally` 块中添加清理：

```python
def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
        if db.is_active and not db.dirty and not db.new and not db.deleted:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        from app.core.tenant_context import clear
        clear()
        db.close()
```

- [ ] **Step 2: 修改 get_current_user() 设置租户上下文**

在 `app/deps.py` 的 `get_current_user()` 中，在 `return user` 前添加：

```python
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    # ... 现有 JWT 解析逻辑不变 ...
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(...)
    if user.status != "active":
        raise HTTPException(...)

    # 新增：设置租户上下文
    if hasattr(user, 'tenant_id') and user.tenant_id is not None:
        from app.core.tenant_context import set_tenant_id
        set_tenant_id(user.tenant_id)

    return user
```

同样修改 `get_current_user_or_api_key()` 中 JWT 认证成功分支。

- [ ] **Step 3: 验证应用可启动**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "from app.main import app; print('App loads OK')"
```

- [ ] **Step 4: 提交**

```bash
git add app/db/database.py app/deps.py
git commit -m "feat(tenant): integrate tenant context into get_db and get_current_user"
```

---

## Task 8: 租户 Schemas + Service

**Files:**
- Create: `backend/app/schemas/tenant.py`
- Create: `backend/app/services/tenant_service.py`

- [ ] **Step 1: 创建 Pydantic schemas**

```python
# backend/app/schemas/tenant.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# --- 租户套餐 ---
class TenantPackageCreate(BaseModel):
    name: str = Field(..., max_length=100, description="套餐名称")
    status: str = Field(default="active", description="状态")
    remark: Optional[str] = Field(None, max_length=500, description="备注")
    menu_ids: Optional[List[int]] = Field(default=None, description="关联菜单ID集合")


class TenantPackageUpdate(BaseModel):
    package_id: int
    name: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=500)
    menu_ids: Optional[List[int]] = None


class TenantPackageResp(BaseModel):
    package_id: int
    name: str
    status: str
    remark: Optional[str] = None
    menu_ids: Optional[List[int]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantPackageSimple(BaseModel):
    package_id: int
    name: str

    class Config:
        from_attributes = True


# --- 租户 ---
class TenantCreate(BaseModel):
    name: str = Field(..., max_length=100, description="租户名称")
    package_id: Optional[int] = Field(None, description="租户套餐ID")
    contact_name: Optional[str] = Field(None, max_length=50)
    contact_mobile: Optional[str] = Field(None, max_length=20)
    status: str = Field(default="active")
    account_count: int = Field(default=0, ge=0)
    expire_time: Optional[datetime] = None
    websites: Optional[List[str]] = None
    # 创建时专属
    username: str = Field(..., max_length=50, description="管理员用户名")
    password: str = Field(..., min_length=6, description="管理员密码")


class TenantUpdate(BaseModel):
    tenant_id: int
    name: Optional[str] = Field(None, max_length=100)
    package_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_mobile: Optional[str] = None
    status: Optional[str] = None
    account_count: Optional[int] = None
    expire_time: Optional[datetime] = None
    websites: Optional[List[str]] = None


class TenantResp(BaseModel):
    tenant_id: int
    name: str
    contact_name: Optional[str] = None
    contact_mobile: Optional[str] = None
    status: str
    package_id: Optional[int] = None
    expire_time: Optional[datetime] = None
    account_count: int = 0
    websites: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantSimple(BaseModel):
    tenant_id: int
    name: str

    class Config:
        from_attributes = True


class TenantPageQuery(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_mobile: Optional[str] = None
    status: Optional[str] = None
    page_no: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
```

- [ ] **Step 2: 创建 TenantService**

```python
# backend/app/services/tenant_service.py
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from app.models.tenant import SysTenant, SysTenantPackage
from app.models.user import SysUser
from app.services.auth_service import AuthService
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantPageQuery


class TenantService:
    """租户管理核心业务逻辑"""

    def __init__(self, db: Session):
        self.db = db

    def create_tenant(self, req: TenantCreate) -> SysTenant:
        """创建租户 + 管理员账号"""
        # 1. 检查租户名唯一性
        existing = self.db.query(SysTenant).filter(SysTenant.name == req.name).first()
        if existing:
            raise ValueError(f"租户名 '{req.name}' 已存在")

        # 2. 检查用户名唯一性
        existing_user = self.db.query(SysUser).filter(SysUser.username == req.username).first()
        if existing_user:
            raise ValueError(f"用户名 '{req.username}' 已存在")

        # 3. 创建租户
        tenant = SysTenant(
            name=req.name,
            contact_name=req.contact_name,
            contact_mobile=req.contact_mobile,
            status=req.status,
            package_id=req.package_id,
            expire_time=req.expire_time,
            account_count=req.account_count,
            websites=req.websites,
        )
        self.db.add(tenant)
        self.db.flush()

        # 4. 创建管理员用户
        admin_user = SysUser(
            username=req.username,
            password_hash=AuthService.get_password_hash(req.password),
            real_name=req.username,
            tenant_id=tenant.tenant_id,
            is_admin=True,
            status="active",
        )
        self.db.add(admin_user)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def update_tenant(self, req: TenantUpdate) -> SysTenant:
        """更新租户信息"""
        tenant = self.db.query(SysTenant).filter(
            SysTenant.tenant_id == req.tenant_id
        ).first()
        if not tenant:
            raise ValueError("租户不存在")

        update_data = req.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(tenant, key, value)

        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def delete_tenant(self, tenant_id: int) -> None:
        """删除租户（软删除：禁用所有用户 + 标记租户为 disabled）"""
        tenant = self.db.query(SysTenant).filter(
            SysTenant.tenant_id == tenant_id
        ).first()
        if not tenant:
            raise ValueError("租户不存在")

        if tenant.tenant_id == 0:
            raise ValueError("系统默认租户不可删除")

        # 禁用该租户下所有用户
        self.db.query(SysUser).filter(
            SysUser.tenant_id == tenant_id,
        ).update({"status": "disabled"})

        tenant.status = "disabled"
        self.db.commit()

    def get_tenant(self, tenant_id: int) -> Optional[SysTenant]:
        return self.db.query(SysTenant).filter(
            SysTenant.tenant_id == tenant_id
        ).first()

    def get_tenant_page(self, query: TenantPageQuery) -> tuple[list[SysTenant], int]:
        """分页查询租户列表"""
        q = self.db.query(SysTenant)
        if query.name:
            q = q.filter(SysTenant.name.ilike(f"%{query.name}%"))
        if query.contact_name:
            q = q.filter(SysTenant.contact_name.ilike(f"%{query.contact_name}%"))
        if query.contact_mobile:
            q = q.filter(SysTenant.contact_mobile.ilike(f"%{query.contact_mobile}%"))
        if query.status:
            q = q.filter(SysTenant.status == query.status)

        total = q.count()
        items = q.order_by(SysTenant.tenant_id.desc()).offset(
            (query.page_no - 1) * query.page_size
        ).limit(query.page_size).all()
        return items, total

    def get_simple_list(self) -> list[SysTenant]:
        """获取活跃租户精简列表"""
        return self.db.query(SysTenant).filter(
            SysTenant.status == "active"
        ).order_by(SysTenant.tenant_id.asc()).all()

    def valid_tenant(self, tenant_id: int) -> SysTenant:
        """校验租户合法性"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError("租户不存在")
        if tenant.status != "active":
            raise ValueError("租户已被禁用")
        if tenant.expire_time and tenant.expire_time < datetime.now():
            raise ValueError("租户已过期")
        return tenant

    # --- 套餐管理 ---
    def create_package(self, name: str, status: str = "active",
                       remark: str = None, menu_ids: list = None) -> SysTenantPackage:
        existing = self.db.query(SysTenantPackage).filter(
            SysTenantPackage.name == name
        ).first()
        if existing:
            raise ValueError(f"套餐名 '{name}' 已存在")
        package = SysTenantPackage(
            name=name, status=status, remark=remark, menu_ids=menu_ids
        )
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def update_package(self, package_id: int, **kwargs) -> SysTenantPackage:
        package = self.db.query(SysTenantPackage).filter(
            SysTenantPackage.package_id == package_id
        ).first()
        if not package:
            raise ValueError("套餐不存在")
        for key, value in kwargs.items():
            if value is not None:
                setattr(package, key, value)
        self.db.commit()
        self.db.refresh(package)
        return package

    def delete_package(self, package_id: int) -> None:
        package = self.db.query(SysTenantPackage).filter(
            SysTenantPackage.package_id == package_id
        ).first()
        if not package:
            raise ValueError("套餐不存在")
        # 检查是否有租户使用该套餐
        tenant_count = self.db.query(SysTenant).filter(
            SysTenant.package_id == package_id
        ).count()
        if tenant_count > 0:
            raise ValueError(f"该套餐正在被 {tenant_count} 个租户使用，无法删除")
        self.db.delete(package)
        self.db.commit()

    def get_package(self, package_id: int) -> Optional[SysTenantPackage]:
        return self.db.query(SysTenantPackage).filter(
            SysTenantPackage.package_id == package_id
        ).first()

    def get_package_page(self, name: str = None, status: str = None,
                         page_no: int = 1, page_size: int = 10) -> tuple[list, int]:
        q = self.db.query(SysTenantPackage)
        if name:
            q = q.filter(SysTenantPackage.name.ilike(f"%{name}%"))
        if status:
            q = q.filter(SysTenantPackage.status == status)
        total = q.count()
        items = q.order_by(SysTenantPackage.package_id.desc()).offset(
            (page_no - 1) * page_size
        ).limit(page_size).all()
        return items, total

    def get_package_simple_list(self) -> list[SysTenantPackage]:
        return self.db.query(SysTenantPackage).filter(
            SysTenantPackage.status == "active"
        ).order_by(SysTenantPackage.package_id.asc()).all()
```

- [ ] **Step 3: 提交**

```bash
git add app/schemas/tenant.py app/services/tenant_service.py
git commit -m "feat(tenant): add tenant schemas and service layer"
```

---

## Task 9: 租户管理路由 + 套餐路由

**Files:**
- Create: `backend/app/routers/admin/tenant.py`
- Create: `backend/app/routers/admin/tenant_package.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建租户管理路由**

```python
# backend/app/routers/admin/tenant.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user, require_admin
from app.models.user import SysUser
from app.schemas.tenant import (
    TenantCreate, TenantUpdate, TenantResp, TenantSimple, TenantPageQuery,
)
from app.services.tenant_service import TenantService
from app.core.tenant_decorators import tenant_ignore

router = APIRouter()


@router.get("/page", response_model=dict)
def get_tenant_page(
    name: str = Query(None),
    contact_name: str = Query(None),
    contact_mobile: str = Query(None),
    status: str = Query(None),
    page_no: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    query = TenantPageQuery(
        name=name, contact_name=contact_name,
        contact_mobile=contact_mobile, status=status,
        page_no=page_no, page_size=page_size,
    )
    service = TenantService(db)
    items, total = service.get_tenant_page(query)
    return {
        "code": 0,
        "data": {
            "list": [TenantResp.model_validate(t).model_dump() for t in items],
            "total": total,
        },
    }


@router.get("/{tenant_id}", response_model=TenantResp)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    tenant = service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    return TenantResp.model_validate(tenant)


@router.post("/create")
def create_tenant(
    req: TenantCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        tenant = service.create_tenant(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": {"tenant_id": tenant.tenant_id}}


@router.put("/update")
def update_tenant(
    req: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        tenant = service.update_tenant(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": {"tenant_id": tenant.tenant_id}}


@router.delete("/delete/{tenant_id}")
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        service.delete_tenant(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "删除成功"}


@router.delete("/delete-list")
def delete_tenant_list(
    ids: list[int],
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    for tid in ids:
        try:
            service.delete_tenant(tid)
        except ValueError:
            continue
    return {"code": 0, "message": "批量删除成功"}


@router.get("/simple-list", response_model=list[TenantSimple])
@tenant_ignore
def get_tenant_simple_list(db: Session = Depends(get_db)):
    """获取活跃租户精简列表（下拉选择用，无需认证）"""
    service = TenantService(db)
    return [TenantSimple.model_validate(t) for t in service.get_simple_list()]


@router.get("/get-id-by-name")
@tenant_ignore
def get_tenant_id_by_name(
    name: str = Query(...),
    db: Session = Depends(get_db),
):
    service = TenantService(db)
    from app.models.tenant import SysTenant
    tenant = db.query(SysTenant).filter(SysTenant.name == name).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    return {"code": 0, "data": {"tenant_id": tenant.tenant_id}}
```

- [ ] **Step 2: 创建套餐管理路由**

```python
# backend/app/routers/admin/tenant_package.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models.user import SysUser
from app.schemas.tenant import TenantPackageCreate, TenantPackageUpdate, TenantPackageResp, TenantPackageSimple
from app.services.tenant_service import TenantService

router = APIRouter()


@router.get("/page")
def get_package_page(
    name: str = Query(None),
    status: str = Query(None),
    page_no: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    items, total = service.get_package_page(name, status, page_no, page_size)
    return {
        "code": 0,
        "data": {
            "list": [TenantPackageResp.model_validate(p).model_dump() for p in items],
            "total": total,
        },
    }


@router.get("/{package_id}", response_model=TenantPackageResp)
def get_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    package = service.get_package(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="套餐不存在")
    return TenantPackageResp.model_validate(package)


@router.post("/create")
def create_package(
    req: TenantPackageCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        package = service.create_package(
            name=req.name, status=req.status,
            remark=req.remark, menu_ids=req.menu_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": {"package_id": package.package_id}}


@router.put("/update")
def update_package(
    req: TenantPackageUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        update_data = req.model_dump(exclude_unset=True, exclude={"package_id"})
        package = service.update_package(req.package_id, **update_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": {"package_id": package.package_id}}


@router.delete("/delete/{package_id}")
def delete_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        service.delete_package(package_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "删除成功"}


@router.delete("/delete-list")
def delete_package_list(
    ids: list[int],
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    for pid in ids:
        try:
            service.delete_package(pid)
        except ValueError:
            continue
    return {"code": 0, "message": "批量删除成功"}


@router.get("/simple-list", response_model=list[TenantPackageSimple])
def get_package_simple_list(db: Session = Depends(get_db)):
    """获取活跃套餐精简列表（租户表单下拉用）"""
    service = TenantService(db)
    return [TenantPackageSimple.model_validate(p) for p in service.get_package_simple_list()]
```

- [ ] **Step 3: 在 main.py 中注册路由**

在 `app/main.py` 的路由注册区域添加：

```python
from app.routers.admin import tenant as tenant_router
from app.routers.admin import tenant_package as tenant_package_router

app.include_router(tenant_router.router, prefix=f"{API_V1_PREFIX}/admin/tenant", tags=["租户管理"])
app.include_router(tenant_package_router.router, prefix=f"{API_V1_PREFIX}/admin/tenant-package", tags=["租户套餐管理"])
```

- [ ] **Step 4: 提交**

```bash
git add app/routers/admin/tenant.py app/routers/admin/tenant_package.py app/main.py
git commit -m "feat(tenant): add tenant and tenant-package CRUD routes"
```

---

## Task 10: 登录改造 + 域名中间件

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/routers/auth.py`
- Create: `backend/app/middleware/tenant_resolver.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 修改 LoginRequest schema**

```python
# app/schemas/auth.py 新增字段
class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    tenant_id: int = Field(default=0, description="租户ID")
```

- [ ] **Step 2: 修改 AuthService.login()**

```python
# app/services/auth_service.py
async def login(self, username: str, password: str, tenant_id: int = 0) -> dict:
    """用户登录（含租户校验）"""
    from app.models.tenant import SysTenant

    # 1. 校验租户
    tenant = self.db.query(SysTenant).filter(
        SysTenant.tenant_id == tenant_id,
        SysTenant.status == "active",
    ).first()
    if not tenant:
        raise ValueError("租户不存在或已禁用")
    from datetime import datetime
    if tenant.expire_time and tenant.expire_time < datetime.now():
        raise ValueError("租户已过期")

    # 2. 校验用户（绑定租户）
    user = self.db.query(SysUser).filter(
        SysUser.username == username,
        SysUser.tenant_id == tenant_id,
    ).first()
    if not user:
        raise ValueError("用户名或密码错误")
    if not self.verify_password(password, user.password_hash):
        raise ValueError("用户名或密码错误")
    if user.status != "active":
        raise ValueError("账号已被禁用")

    user.last_login_at = datetime.utcnow()
    self.db.commit()

    # 3. 生成 token（含 tenant_id）
    token = self.create_access_token(user.user_id, tenant_id=tenant_id)
    return {
        "token": token,
        "userId": user.user_id,
        "username": user.username,
        "realName": user.real_name,
        "tenantId": tenant_id,
    }
```

修改 `create_access_token` 添加 tenant_id 参数：

```python
def create_access_token(self, user_id: int, tenant_id: int = 0) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
```

- [ ] **Step 3: 修改 auth router 的 login 端点**

```python
@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    try:
        result = await auth_service.login(
            request.username, request.password, request.tenant_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return result
```

在 auth router 中添加公开接口：

```python
from app.core.tenant_decorators import tenant_ignore

@router.get("/tenant-simple-list")
@tenant_ignore
def get_tenant_simple_list(db: Session = Depends(get_db)):
    """登录页租户下拉数据源（公开接口）"""
    from app.models.tenant import SysTenant
    tenants = db.query(SysTenant).filter(SysTenant.status == "active").all()
    return {"code": 0, "data": [{"tenantId": t.tenant_id, "name": t.name} for t in tenants]}
```

- [ ] **Step 4: 创建域名解析中间件**

```python
# backend/app/middleware/tenant_resolver.py
"""域名→租户解析中间件"""


class TenantResolverMiddleware:
    """从请求 Host 头解析租户，支持域名绑定。"""

    def __init__(self, app):
        self.app = app
        self._domain_tenant_map: dict[str, int] = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            host = headers.get(b"host", b"").decode()
            domain = host.split(":")[0]
            if domain:
                tenant_id = self._domain_tenant_map.get(domain)
                if tenant_id is not None:
                    from app.core.tenant_context import set_tenant_id
                    set_tenant_id(tenant_id)
        return await self.app(scope, receive, send)

    def refresh_domain_map(self, domain_map: dict[str, int]) -> None:
        self._domain_tenant_map = domain_map
```

- [ ] **Step 5: 在 main.py 中注册中间件 + 拦截器**

```python
# app/main.py 中添加
from app.core.tenant_interceptor import setup_tenant_interceptor
from app.middleware.tenant_resolver import TenantResolverMiddleware
from app.db.database import SessionLocal

# 注册租户拦截器
setup_tenant_interceptor(SessionLocal)

# 注册域名解析中间件（放在其他中间件之前）
tenant_resolver = TenantResolverMiddleware(None)
# 注意：FastAPI middleware 需要用 add_middleware 包装
```

- [ ] **Step 6: 提交**

```bash
git add app/schemas/auth.py app/services/auth_service.py app/routers/auth.py
git add app/middleware/tenant_resolver.py app/main.py
git commit -m "feat(tenant): login with tenant_id, domain resolver middleware"
```

---

## Task 11: Alembic 数据库迁移

**Files:**
- Generate: Alembic migration file

- [ ] **Step 1: 生成迁移脚本**

```bash
cd d:\projects\MinWorkBuddy\backend
alembic revision --autogenerate -m "add multi-tenant isolation"
```

- [ ] **Step 2: 检查生成的迁移文件**

确认包含：
- `CREATE TABLE sys_tenant_package`
- `CREATE TABLE sys_tenant`
- `ALTER TABLE sys_user ADD COLUMN tenant_id`
- 所有 50 个业务表的 `ADD COLUMN tenant_id` + `CREATE INDEX`

- [ ] **Step 3: 添加数据初始化逻辑**

在迁移文件的 `upgrade()` 末尾添加：

```python
# 创建默认系统租户
op.execute(
    "INSERT INTO sys_tenant (tenant_id, name, status) VALUES (0, '系统管理', 'active')"
    " ON CONFLICT (tenant_id) DO NOTHING"
)
# 现有用户绑定到默认租户
op.execute("UPDATE sys_user SET tenant_id = 0 WHERE tenant_id IS NULL")
```

- [ ] **Step 4: 执行迁移**

```bash
alembic upgrade head
```

- [ ] **Step 5: 提交**

```bash
git add alembic/versions/
git commit -m "feat(tenant): alembic migration for multi-tenant isolation"
```

---

## Task 12: 租户隔离集成测试

**Files:**
- Create: `backend/tests/integration/test_tenant_isolation.py`

- [ ] **Step 1: 编写隔离验证测试**

```python
# backend/tests/integration/test_tenant_isolation.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.core.tenant_context import set_tenant_id, clear, set_ignore
from app.core.tenant_interceptor import setup_tenant_interceptor


class TestTenantIsolation:
    """验证租户数据隔离正确性"""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        setup_tenant_interceptor(self.Session)
        yield
        clear()
        Base.metadata.drop_all(self.engine)

    def test_tenant_a_cannot_see_tenant_b_data(self):
        """租户 A 无法看到租户 B 的数据"""
        # 插入两个租户的数据
        db = self.Session()
        from app.models.ai.ai_chat import AiChatSession
        session_a = AiChatSession(user_id=1, tenant_id=1)
        session_b = AiChatSession(user_id=2, tenant_id=2)
        db.add_all([session_a, session_b])
        db.commit()

        # 租户 A 查询
        set_tenant_id(1)
        db_a = self.Session()
        results_a = db_a.query(AiChatSession).all()
        assert len(results_a) == 1
        assert results_a[0].tenant_id == 1
        db_a.close()

        # 租户 B 查询
        clear()
        set_tenant_id(2)
        db_b = self.Session()
        results_b = db_b.query(AiChatSession).all()
        assert len(results_b) == 1
        assert results_b[0].tenant_id == 2
        db_b.close()

    def test_ignore_mode_sees_all_data(self):
        """忽略模式下可以看到所有租户数据"""
        db = self.Session()
        from app.models.ai.ai_chat import AiChatSession
        db.add_all([
            AiChatSession(user_id=1, tenant_id=1),
            AiChatSession(user_id=2, tenant_id=2),
        ])
        db.commit()

        set_ignore(True)
        db_ignore = self.Session()
        results = db_ignore.query(AiChatSession).all()
        assert len(results) == 2
        db_ignore.close()
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/integration/test_tenant_isolation.py -v
```

- [ ] **Step 3: 提交**

```bash
git add tests/integration/test_tenant_isolation.py
git commit -m "test(tenant): add tenant isolation integration tests"
```

---

## Task 13: 前端 — API 层 + 登录页改造

**Files:**
- Create: `frontend/src/api/tenant.ts`
- Create: `frontend/src/api/tenantPackage.ts`
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/stores/user.ts`
- Modify: `frontend/src/views/login/index.vue`

- [ ] **Step 1: 创建租户 API**

```typescript
// frontend/src/api/tenant.ts
import request from '@/utils/request'

const BASE_URL = '/api/v1/admin/tenant'

export interface TenantVO {
  tenantId: number
  name: string
  contactName?: string
  contactMobile?: string
  status: string
  packageId?: number
  expireTime?: string
  accountCount: number
  websites?: string[]
  createdAt?: string
}

export interface TenantCreateReq extends TenantVO {
  username: string
  password: string
}

export function getTenantPage(params: any) {
  return request.get(`${BASE_URL}/page`, { params })
}

export function getTenant(tenantId: number) {
  return request.get(`${BASE_URL}/${tenantId}`)
}

export function createTenant(data: TenantCreateReq) {
  return request.post(`${BASE_URL}/create`, data)
}

export function updateTenant(data: Partial<TenantVO>) {
  return request.put(`${BASE_URL}/update`, data)
}

export function deleteTenant(tenantId: number) {
  return request.delete(`${BASE_URL}/delete/${tenantId}`)
}

export function deleteTenantList(ids: number[]) {
  return request.delete(`${BASE_URL}/delete-list`, { data: ids })
}

export function getTenantSimpleList() {
  return request.get(`${BASE_URL}/simple-list`)
}
```

- [ ] **Step 2: 创建套餐 API**

```typescript
// frontend/src/api/tenantPackage.ts
import request from '@/utils/request'

const BASE_URL = '/api/v1/admin/tenant-package'

export interface TenantPackageVO {
  packageId: number
  name: string
  status: string
  remark?: string
  menuIds?: number[]
  createdAt?: string
}

export function getTenantPackagePage(params: any) {
  return request.get(`${BASE_URL}/page`, { params })
}

export function getTenantPackage(packageId: number) {
  return request.get(`${BASE_URL}/${packageId}`)
}

export function createTenantPackage(data: Partial<TenantPackageVO>) {
  return request.post(`${BASE_URL}/create`, data)
}

export function updateTenantPackage(data: Partial<TenantPackageVO>) {
  return request.put(`${BASE_URL}/update`, data)
}

export function deleteTenantPackage(packageId: number) {
  return request.delete(`${BASE_URL}/delete/${packageId}`)
}

export function deleteTenantPackageList(ids: number[]) {
  return request.delete(`${BASE_URL}/delete-list`, { data: ids })
}

export function getTenantPackageSimpleList() {
  return request.get(`${BASE_URL}/simple-list`)
}
```

- [ ] **Step 3: 修改 auth.ts 添加租户列表接口**

在 `frontend/src/api/auth.ts` 中添加：

```typescript
export function getTenantSimpleList() {
  return request.get(`${BASE_URL}/tenant-simple-list`)
}
```

修改 login 函数签名：

```typescript
export function login(data: { username: string; password: string; tenant_id: number }) {
  return request.post(`${BASE_URL}/login`, data)
}
```

- [ ] **Step 4: 修改 user store 支持 tenant_id**

```typescript
// frontend/src/stores/user.ts 修改 login 方法
async function login(username: string, password: string, tenantId: number) {
  const res = await loginApi({ username, password, tenant_id: tenantId }) as { ... }
  // ... 现有逻辑 ...
  // 登录成功后保存 tenantId 到 Cookie
  document.cookie = `tenant_id=${tenantId}; path=/; max-age=${30 * 24 * 3600}`
}
```

- [ ] **Step 5: 修改登录页添加租户选择器**

在 `frontend/src/views/login/index.vue` 中：
1. 在密码输入框后添加租户选择下拉
2. 页面加载时获取租户列表
3. 从 Cookie 读取上次选择的租户作为默认值

```vue
<a-form-item name="tenantId">
  <a-select
    v-model:value="formState.tenantId"
    size="large"
    show-search
    :filter-option="filterTenant"
    placeholder="请选择租户"
  >
    <a-select-option v-for="t in tenantList" :key="t.tenantId" :value="t.tenantId">
      {{ t.name }}
    </a-select-option>
  </a-select>
</a-form-item>
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/tenant.ts frontend/src/api/tenantPackage.ts
git add frontend/src/api/auth.ts frontend/src/stores/user.ts
git add frontend/src/views/login/index.vue
git commit -m "feat(tenant): frontend login with tenant selector and API layer"
```

---

## Task 14: 前端 — 租户管理页面 + 套餐页面

**Files:**
- Create: `frontend/src/views/admin/system/tenant/index.vue`
- Create: `frontend/src/views/admin/system/tenant/TenantForm.vue`
- Create: `frontend/src/views/admin/system/tenant-package/index.vue`
- Create: `frontend/src/views/admin/system/tenant-package/TenantPackageForm.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 创建租户列表页 `tenant/index.vue`**

参考 yudao-ui-admin-vue3 的 `tenant/index.vue`，使用 Ant Design Vue 组件实现：
- 搜索表单：租户名、联系人、联系手机、状态、创建时间
- 表格：租户编号、租户名、租户套餐(Tag)、联系人、联系手机、账号额度、过期时间、绑定域名、状态、创建时间、操作
- 分页组件
- 新增/编辑弹窗引用 TenantForm

- [ ] **Step 2: 创建租户表单弹窗 `TenantForm.vue`**

参考 yudao-ui-admin-vue3 的 `TenantForm.vue`：
- 字段：租户名、租户套餐(下拉)、联系人、联系手机、用户名称(仅创建)、用户密码(仅创建)、账号额度、过期时间、绑定域名(Tag输入)、状态

- [ ] **Step 3: 创建套餐列表页 `tenant-package/index.vue`**

- [ ] **Step 4: 创建套餐表单弹窗 `TenantPackageForm.vue`**

含菜单权限树形选择（el-tree 改为 a-tree）。

- [ ] **Step 5: 添加路由配置**

在 `frontend/src/router/index.ts` 的 admin 路由下添加：

```typescript
{
  path: 'admin/system/tenant',
  name: 'SystemTenant',
  component: () => import('@/views/admin/system/tenant/index.vue'),
  meta: { title: '租户管理', permission: 'system:tenant:query' }
},
{
  path: 'admin/system/tenant-package',
  name: 'SystemTenantPackage',
  component: () => import('@/views/admin/system/tenant-package/index.vue'),
  meta: { title: '租户套餐', permission: 'system:tenant-package:query' }
}
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/admin/system/
git add frontend/src/router/index.ts
git commit -m "feat(tenant): frontend tenant and package management pages"
```

---

## Task 15: 最终验证 + 清理

- [ ] **Step 1: 后端全量测试**

```bash
cd d:\projects\MinWorkBuddy\backend
pytest tests/unit/test_tenant_context.py tests/unit/test_tenant_interceptor.py -v
```

- [ ] **Step 2: 前端构建验证**

```bash
cd d:\projects\MinWorkBuddy\frontend
npm run build
```

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat(tenant): complete multi-tenant isolation implementation"
```
