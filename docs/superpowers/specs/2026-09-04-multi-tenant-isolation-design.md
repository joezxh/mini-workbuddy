# MinWorkBuddy 多租户隔离设计

> 日期：2026-09-04  
> 状态：待审阅  
> 参考项目：yudao-boot-mini（Java）、yudao-ui-admin-vue3（Vue3 前端）

## 1. 概述

为 MinWorkBuddy 项目添加完整的多租户（Multi-Tenant）隔离能力，采用**共享数据库 + 行级隔离**模式。所有业务表（54 个现有模型 + 2 个新增租户表）通过 `tenant_id` 字段实现数据隔离，SQLAlchemy Event 拦截器自动为所有查询注入租户过滤条件，业务代码零侵入。

### 1.1 核心设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 隔离范围 | 全部业务表 | 所有 37 个模型中除全局系统表外均添加 tenant_id |
| Workspace 与 Tenant 关系 | 两者并存 | Workspace 是用户级工作空间，Tenant 是组织级租户隔离 |
| 租户上下文传播 | 用户表绑定 + JWT + 域名解析 | 三层保障，登录时写入 JWT，域名自动匹配 |
| 自动过滤机制 | SQLAlchemy `do_orm_execute` + `with_loader_criteria` | 官方推荐的多租户实现方式，对业务代码零侵入 |
| 超管跨租户 | 允许 | 超管通过 `@tenant_ignore` 装饰器跳过过滤 |

### 1.2 参考架构对照

| Java 参考项目 | MinWorkBuddy 对应 |
|--------------|------------------|
| `TenantBaseDO`（基类含 tenantId） | `TenantMixin`（混入类含 tenant_id） |
| `TenantDatabaseInterceptor`（MyBatis Plus 拦截器） | `tenant_interceptor.py`（`do_orm_execute` 事件） |
| `TenantContextHolder`（ThreadLocal） | `TenantContext`（contextvars） |
| `TenantSecurityWebFilter`（Servlet Filter） | `TenantResolverMiddleware`（FastAPI Middleware） |
| `@TenantIgnore`（注解） | `@tenant_ignore`（装饰器） |
| `TenantProperties.ignoreTables` | `TENANT_IGNORE_TABLES` 配置常量 |

## 2. 数据模型设计

### 2.1 新增模型

#### SysTenant（租户表）

```python
class SysTenant(Base):
    __tablename__ = "sys_tenant"

    tenant_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment="租户名称")
    contact_name = Column(String(50), comment="联系人")
    contact_mobile = Column(String(20), comment="联系电话")
    status = Column(String(20), nullable=False, default="active",
                    comment="状态(active/disabled)")
    package_id = Column(BigInteger, ForeignKey("sys_tenant_package.package_id"),
                        nullable=True, comment="租户套餐ID")
    expire_time = Column(DateTime, nullable=True, comment="过期时间")
    account_count = Column(Integer, default=0, comment="账号额度")
    websites = Column(JSON, nullable=True, comment="绑定域名列表")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

#### SysTenantPackage（租户套餐表）

```python
class SysTenantPackage(Base):
    __tablename__ = "sys_tenant_package"

    package_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="套餐名称")
    status = Column(String(20), nullable=False, default="active", comment="状态")
    remark = Column(String(500), comment="备注")
    menu_ids = Column(JSON, nullable=True, comment="关联菜单ID集合")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

### 2.2 TenantMixin

```python
# app/models/tenant_mixin.py
from sqlalchemy import Column, BigInteger

class TenantMixin:
    """所有需要租户隔离的模型继承此 Mixin，自动获得 tenant_id 列。"""
    tenant_id = Column(BigInteger, nullable=True, index=True, comment="租户ID")
```

### 2.3 模型改造清单

**继承 TenantMixin 的模型（50 个）**：

| 分类 | 模型 |
|------|------|
| 系统管理 | SysUser（新增 tenant_id）、SysRole、SysRoleMenu、SysUserRole、SysAuditLog |
| 基础设施 | InfraFile、InfraFileContent |
| 字典/通知 | SysDictionary、SysDictionaryItem、SysUserNotification |
| AI 会话 | AiChatSession、AiChatMessage |
| API Key/模型 | AiApiKey、AiChatModel |
| Agent | AgentConfig（保留 workspace_id，新增 tenant_id）、AgentTeam、AgentTeamMember、AgentTeamEdge |
| Agent 运行 | AgentTeamRun、AgentAsyncTask、AgentScheduledTask、AgentExecution、AgentExecutionEvent、AgentTrace |
| 工具/技能 | ToolDefinitionModel、ToolGroupModel、ToolGroupMember |
| 技能包 | AiSkillPackage、SkillRule、AiSkillVersion、AiSkillMetrics |
| 技能进化 | AiSkillEvolutionConfig、AiSkillEvolutionLog、AiSkillScript |
| MCP | McpApiKey、MCPClient、McpSquareTemplate |
| 搜索 | AiWebSearch、AiWebSearchLog、AiSkillHubRepo |
| 工作空间 | AiWorkspace |
| 知识管理 | KmsLegalInfo、KmsLegalItem、KmsDocument |
| 知识图谱 | KgReasoningRuleConfig、KgReasoningHistory、KgAuditLog |
| 法律文献 | KmsLegalPaper、KmsLegalPaperLegalItem |
| Wiki | WikiArticle、WikiArticleVersion、WikiCategory |
| 通知 | SysUserNotification |
| 字典 | SysDictionary、SysDictionaryItem |

**不继承 TenantMixin 的表（4 个）**：

| 模型 | 原因 |
|------|------|
| SysTenant | 租户表自身，无需隔离 |
| SysTenantPackage | 套餐表，全局管理 |
| SysMenu | 全局菜单定义，套餐通过 menu_ids 关联 |
| SysRegion | 全局行政区划数据 |

### 2.4 特殊字段处理

- `AgentConfig.workspace_id`：保留不变，与新增的 `tenant_id` 并存。workspace 是用户级概念，tenant 是组织级。
- `SysUser.tenant_id`：用户归属的租户，登录时用于设置租户上下文。

## 3. 租户基础设施层

### 3.1 租户上下文（TenantContext）

文件：`app/core/tenant_context.py`

使用 Python `contextvars`（天然支持 asyncio），对标 Java 的 `TenantContextHolder`。

```python
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

### 3.2 SQL 拦截器（TenantInterceptor）

文件：`app/core/tenant_interceptor.py`

利用 SQLAlchemy 2.0 的 `do_orm_execute` 事件 + `with_loader_criteria`，对标 Java 的 `TenantDatabaseInterceptor`。

```python
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria
from app.core.tenant_context import get_tenant_id, is_ignore

# 不需要租户过滤的表
TENANT_IGNORE_TABLES = {
    "sys_tenant", "sys_tenant_package", "sys_menu", "sys_region",
}

def _build_tenant_criteria(cls):
    """为拥有 tenant_id 属性的模型构建过滤条件"""
    if hasattr(cls, "tenant_id") and cls.__tablename__ not in TENANT_IGNORE_TABLES:
        tenant_id = get_tenant_id()
        if tenant_id is not None:
            return cls.tenant_id == tenant_id
    return None

def setup_tenant_interceptor(session_factory):
    """在 Session 工厂上注册租户过滤事件"""

    @event.listens_for(session_factory, "do_orm_execute")
    def _add_tenant_filter(execute_state):
        # 跳过：忽略模式 或 未设置租户上下文
        if is_ignore():
            return
        if get_tenant_id() is None:
            return

        # 为所有拥有 tenant_id 的模型自动注入 WHERE tenant_id = ?
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                None,  # 对所有实体生效
                lambda cls: _build_tenant_criteria(cls),
                include_aliases=True,
            )
        )
```

**关键机制**：
- `with_loader_criteria` 在 ORM 查询编译阶段自动追加 `WHERE tenant_id = ?`
- 只对拥有 `tenant_id` 属性的模型生效，无此列的模型自动跳过
- `TENANT_IGNORE_TABLES` 中的表始终跳过过滤
- 当 `is_ignore() == True` 时全局跳过（用于 `@tenant_ignore` 装饰器、超管跨租户等场景）

### 3.3 装饰器

文件：`app/core/tenant_decorators.py`

```python
from functools import wraps
from app.core.tenant_context import set_ignore

def tenant_ignore(func):
    """标记不需要租户过滤的接口"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        set_ignore(True)
        try:
            return func(*args, **kwargs)
        finally:
            set_ignore(False)
    return wrapper
```

### 3.4 Session 生命周期集成

修改 `app/db/database.py` 的 `get_db()`：

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
        if db.is_active and not db.dirty and not db.new and not db.deleted:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        from app.core.tenant_context import TenantContext
        TenantContext.clear()  # 请求结束清理租户上下文
        db.close()
```

### 3.5 认证层集成

修改 `app/deps.py` 的 `get_current_user()`：

```python
def get_current_user(credentials, db) -> User:
    # ... 现有 JWT 解析逻辑 ...
    user = db.query(User).filter(User.user_id == user_id).first()
    # 新增：设置租户上下文
    if user and user.tenant_id is not None:
        from app.core.tenant_context import set_tenant_id
        set_tenant_id(user.tenant_id)
    return user
```

### 3.6 域名解析中间件

文件：`app/middleware/tenant_resolver.py`

```python
class TenantResolverMiddleware:
    """从请求 Host 头解析租户，支持域名绑定"""

    def __init__(self, app):
        self.app = app
        self._domain_tenant_map: dict[str, int] = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            host = dict(scope["headers"]).get(b"host", b"").decode()
            domain = host.split(":")[0]  # 去除端口
            tenant_id = self._domain_tenant_map.get(domain)
            if tenant_id is not None:
                from app.core.tenant_context import set_tenant_id
                set_tenant_id(tenant_id)
        return await self.app(scope, receive, send)

    def refresh_domain_map(self, domain_map: dict[str, int]):
        """刷新域名→租户映射缓存"""
        self._domain_tenant_map = domain_map
```

**域名缓存**：
- 应用启动时从 `sys_tenant` 表加载所有 `websites` 构建映射
- 租户创建/更新/删除时调用 `refresh_domain_map()` 刷新
- 避免每次请求查数据库

### 3.7 租户上下文获取优先级

```
请求进入
  │
  ├─ 1. TenantResolverMiddleware：域名匹配 → set_tenant_id()
  │
  ├─ 2. get_current_user()：JWT 解析 → 从 user.tenant_id → set_tenant_id()
  │     （覆盖域名结果，以用户实际归属为准）
  │
  └─ 3. 业务查询：do_orm_execute 自动注入 WHERE tenant_id = ?
```

**冲突处理**：如果域名解析的租户与用户归属租户不一致，以用户归属租户为准（防止越权）。

## 4. API 接口设计

### 4.1 租户管理 API

路由前缀：`/api/admin/tenant`，文件：`app/routers/admin/tenant.py`

| 方法 | 路径 | 功能 | 权限 | 备注 |
|------|------|------|------|------|
| GET | `/page` | 分页查询租户列表 | `system:tenant:query` | 支持 name/contactName/contactMobile/status/createTime 筛选 |
| GET | `/{tenant_id}` | 获取租户详情 | `system:tenant:query` | |
| POST | `/create` | 创建租户 | `system:tenant:create` | 同时创建管理员账号 |
| PUT | `/update` | 更新租户信息 | `system:tenant:update` | |
| DELETE | `/delete/{tenant_id}` | 删除租户 | `system:tenant:delete` | |
| DELETE | `/delete-list` | 批量删除租户 | `system:tenant:delete` | Body: `{ids: [...]}` |
| GET | `/simple-list` | 精简列表（下拉用） | 无特殊权限 | 返回 `[{tenant_id, name}]` |
| GET | `/get-id-by-name` | 按名称获取 ID | `@tenant_ignore` | |
| GET | `/get-by-website` | 按域名获取租户 | `@tenant_ignore` | |

### 4.2 租户套餐管理 API

路由前缀：`/api/admin/tenant-package`，文件：`app/routers/admin/tenant_package.py`

| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| GET | `/page` | 分页查询套餐列表 | `system:tenant-package:query` |
| GET | `/{package_id}` | 获取套餐详情 | `system:tenant-package:query` |
| POST | `/create` | 创建套餐 | `system:tenant-package:create` |
| PUT | `/update` | 更新套餐 | `system:tenant-package:update` |
| DELETE | `/delete/{package_id}` | 删除套餐 | `system:tenant-package:delete` |
| DELETE | `/delete-list` | 批量删除套餐 | `system:tenant-package:delete` |
| GET | `/simple-list` | 精简列表（租户表单下拉用） | 无特殊权限 |

### 4.3 登录 API 改造

修改 `POST /api/auth/login`：

```python
# 请求体新增 tenant_id
class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: int  # 新增：用户选择的租户 ID

# 登录逻辑
def login(req: LoginRequest, db: Session):
    # 1. 校验租户状态（是否 active、是否过期）
    tenant = db.query(SysTenant).filter(
        SysTenant.tenant_id == req.tenant_id,
        SysTenant.status == "active"
    ).first()
    if not tenant:
        raise HTTPException(401, "租户不存在或已禁用")
    if tenant.expire_time and tenant.expire_time < datetime.now():
        raise HTTPException(401, "租户已过期")

    # 2. 校验用户名密码 + 租户归属
    user = db.query(SysUser).filter(
        SysUser.username == req.username,
        SysUser.tenant_id == req.tenant_id,
    ).first()
    if not user:
        raise HTTPException(401, "用户名或密码错误")

    # 3. 生成 JWT（包含 tenant_id claim）
    payload = {
        "sub": str(user.user_id),
        "tenant_id": user.tenant_id,  # 新增
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}
```

### 4.4 公开接口（@tenant_ignore）

以下接口需要标记 `@tenant_ignore`，跳过租户过滤：

- 登录/注册接口
- `GET /api/auth/tenant-simple-list`（登录页租户下拉数据源）
- 超管跨租户管理接口

### 4.5 业务逻辑层

文件：`app/services/tenant_service.py`

```python
class TenantService:
    """租户管理核心业务逻辑"""

    def create_tenant(self, db, req: TenantCreateRequest) -> SysTenant:
        """创建租户 + 管理员账号"""
        # 1. 创建租户记录
        tenant = SysTenant(name=req.name, ...)
        db.add(tenant)
        db.flush()

        # 2. 创建管理员用户
        admin_user = SysUser(
            username=req.username,
            password=hash_password(req.password),
            tenant_id=tenant.tenant_id,
            is_admin=True,
            status="active",
        )
        db.add(admin_user)
        db.commit()
        return tenant

    def valid_tenant(self, db, tenant_id: int) -> None:
        """校验租户合法性（是否存在、是否禁用、是否过期）"""
        ...

    def delete_tenant(self, db, tenant_id: int) -> None:
        """删除租户（级联处理：禁用该租户下所有用户）"""
        ...
```

## 5. 数据库迁移方案

### 5.1 迁移步骤

**Step 1：新增租户基础设施表**

```sql
-- 创建租户套餐表
CREATE TABLE sys_tenant_package (
    package_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    remark VARCHAR(500),
    menu_ids JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 创建租户表
CREATE TABLE sys_tenant (
    tenant_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    contact_name VARCHAR(50),
    contact_mobile VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    package_id BIGINT REFERENCES sys_tenant_package(package_id),
    expire_time TIMESTAMP,
    account_count INTEGER DEFAULT 0,
    websites JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- sys_user 新增 tenant_id
ALTER TABLE sys_user ADD COLUMN tenant_id BIGINT;
CREATE INDEX ix_sys_user_tenant_id ON sys_user(tenant_id);
```

**Step 2：初始化默认数据**

```sql
-- 创建默认系统租户
INSERT INTO sys_tenant (tenant_id, name, status) VALUES (0, '系统管理', 'active');

-- 现有用户绑定到默认租户
UPDATE sys_user SET tenant_id = 0;
```

**Step 3：为所有业务表添加 tenant_id**

对 50 个业务表逐一执行（Alembic 自动生成）：

```sql
ALTER TABLE ai_chat_session ADD COLUMN tenant_id BIGINT;
CREATE INDEX ix_ai_chat_session_tenant_id ON ai_chat_session(tenant_id);
-- ... 其余 49 个表类似
```

### 5.2 数据回填

- 所有现有数据的 `tenant_id` 统一设为 `0`（系统默认租户）
- 后续通过管理后台创建新租户并迁移数据

### 5.3 索引策略

- 所有 `tenant_id` 列创建普通 B-tree 索引
- 高频查询表考虑 `(tenant_id, 业务外键)` 复合索引

### 5.4 回滚方案

- 迁移脚本支持 `downgrade()`：删除 `tenant_id` 列
- 数据不做硬删除，回滚时仅移除列

## 6. 前端设计

### 6.1 登录页改造

在现有登录表单（`views/login/index.vue`）中新增「租户」选择器：

```vue
<el-form-item label="租户" prop="tenantId">
  <el-select
    v-model="loginForm.tenantId"
    filterable
    placeholder="请选择租户"
    class="w-full"
  >
    <el-option
      v-for="item in tenantList"
      :key="item.tenantId"
      :label="item.name"
      :value="item.tenantId"
    />
  </el-select>
</el-form-item>
```

**数据加载逻辑**：
1. 页面加载时调用 `GET /api/auth/tenant-simple-list` 获取租户列表
2. 默认值：Cookie 中的 `tenant_id` > 域名解析结果 > 空
3. 登录成功后将 `tenant_id` 写入 Cookie（`max-age=30d`）

### 6.2 租户管理页面

路径：`/admin/system/tenant`

**列表页**（`tenant/index.vue`）：
- 搜索：租户名、联系人、联系手机、状态、创建时间范围
- 表格列：租户编号、租户名、租户套餐（Tag）、联系人、联系手机、账号额度、过期时间、绑定域名、状态、创建时间、操作
- 操作：编辑、删除、批量删除

**表单弹窗**（`tenant/TenantForm.vue`）：
- 字段：租户名、租户套餐（下拉选择）、联系人、联系手机、用户名称（仅创建时显示）、用户密码（仅创建时显示）、账号额度、过期时间、绑定域名（Tag 输入）、状态

### 6.3 租户套餐管理页面

路径：`/admin/system/tenant-package`

**列表页**（`tenant-package/index.vue`）：
- 搜索：套餐名、状态、创建时间范围
- 表格列：套餐编号、套餐名、状态、备注、创建时间、操作

**表单弹窗**（`tenant-package/TenantPackageForm.vue`）：
- 字段：套餐名、菜单权限（`el-tree` 树形勾选，全选/全不选开关）、状态、备注

### 6.4 前端文件结构

```
frontend/src/
├── api/
│   ├── tenant.ts              # 租户管理 API
│   └── tenantPackage.ts       # 租户套餐 API
├── views/admin/system/
│   ├── tenant/
│   │   ├── index.vue          # 租户列表页
│   │   └── TenantForm.vue     # 租户表单弹窗
│   └── tenant-package/
│       ├── index.vue          # 套餐列表页
│       └── TenantPackageForm.vue  # 套餐表单弹窗
└── views/login/
    └── index.vue              # 登录页（新增租户选择器）
```

### 6.5 路由配置

```typescript
// router/index.ts 新增路由
{
  path: '/admin/system/tenant',
  name: 'SystemTenant',
  component: () => import('@/views/admin/system/tenant/index.vue'),
  meta: { title: '租户管理', permission: 'system:tenant:query' }
},
{
  path: '/admin/system/tenant-package',
  name: 'SystemTenantPackage',
  component: () => import('@/views/admin/system/tenant-package/index.vue'),
  meta: { title: '租户套餐', permission: 'system:tenant-package:query' }
}
```

## 7. 后端文件结构总览

```
app/
├── models/
│   ├── tenant.py              # SysTenant, SysTenantPackage（新增）
│   ├── tenant_mixin.py        # TenantMixin（新增）
│   └── ... (54 个现有模型，50 个继承 TenantMixin)
├── schemas/
│   └── tenant.py              # 请求/响应 Pydantic 模型（新增）
├── routers/admin/
│   ├── tenant.py              # 租户管理路由（新增）
│   └── tenant_package.py      # 套餐管理路由（新增）
├── services/
│   └── tenant_service.py      # 租户业务逻辑（新增）
├── middleware/
│   └── tenant_resolver.py     # 域名→租户解析中间件（新增）
├── core/
│   ├── tenant_context.py      # 租户上下文管理（新增）
│   ├── tenant_interceptor.py  # SQL 租户拦截器（新增）
│   └── tenant_decorators.py   # @tenant_ignore 装饰器（新增）
└── db/
    ├── database.py            # get_db() 增加 TenantContext.clear()
    └── init_models.py         # 注册新模型
```

## 8. 测试建议

### 8.1 单元测试

- **TenantContext**：测试 set/get/clear/is_ignore 各状态
- **TenantInterceptor**：验证查询自动包含 `WHERE tenant_id = ?`
- **@tenant_ignore**：验证装饰器正确切换忽略模式
- **TenantService**：创建租户（含管理员账号）、删除租户、校验租户合法性

### 8.2 集成测试

- **租户隔离验证**：创建两个租户，验证 A 租户无法查询到 B 租户的数据
- **超管跨租户**：验证超管可以通过 `@tenant_ignore` 查询所有数据
- **域名解析**：验证不同域名请求自动路由到对应租户
- **登录流程**：验证带 tenant_id 的登录、JWT 中包含 tenant_id

### 8.3 安全测试

- **越权访问**：租户 A 的用户尝试访问租户 B 的数据 → 应返回空或 403
- **JWT 篡改**：修改 JWT 中的 tenant_id → 应与用户实际归属校验一致
- **域名冲突**：两个租户绑定相同域名 → 应拒绝并报错
