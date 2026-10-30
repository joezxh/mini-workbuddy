# P0→P1 · 知识图谱知识库（type=4）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 MinWorkBuddy 现有知识库体系内新增**独立图谱知识库类型** `type=4`（kb_format=`graph`），落地实例层（实体/关系/属性）的存储、CRUD 与评审流转，并交付最小可用的前端管理面板。产物契约（`RetrieveResult`）与既有三个 type 的行为**零变化**。

**Architecture:** `kms_knowledge` 容器新增 `type=4` → 复用 `kb_format` 二级形态矩阵（`validated_kb_format` 直接覆盖 admin/用户两条创建链路）→ 实例层 4 张新表（`kg_entity` / `kg_entity_mention` / `kg_triple` / `kg_triple_mention`），全部带 `tenant_id` 并继承 `TenantMixin` → 服务层 `kg_service` 提供实体/关系 CRUD + 评审流转 → 路由层 `routers/kb/kg.py`（前缀 `/api/v1/kb/knowledges/{kid}/graph`）复用 `require_kb_permission` → 前端 `KnowledgeBaseManager.vue` 加类型分支并分发到 `KbGraphPane.vue`。模式层（CDM）零新增，复用 `meta_object_standard` / `meta_object_relation` 作为 type_code / relation_code 的来源约束。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / PostgreSQL 17 + pgvector / Alembic / pytest · Vue 3 + TypeScript + Ant Design Vue（既有范式）· i18n 自研模块（见 R16）

**Spec:** `docs/superpowers/specs/2026-10-30-kg-knowledge-base-design.md`（§2 类型与数据模型、§3.3–§3.6 实例层表、§4.3–§4.4 前端、§6 阶段 P0/P1）
**依赖：** 无（P1 为地基，自身不依赖其他阶段）
**被依赖：** P2（Neo4j 投影）、P3（构建管线）、P4（检索增强）、P5（图谱浏览治理）、P6（Agent 工具）
**上游门禁（P0，必须最先验证）：** semantica 迁移完成、ontology 清理完成、CDM 模式层 API 可用、Neo4j 可连通

---

## 文件结构

| 路径 | 职责 |
|---|---|
| `backend/app/models/wiki/wiki_knowledge.py` | 改：`KnowledgeType.GRAPH_KB = 4` + 列注释 |
| `backend/app/services/kb/kb_format.py` | 改：`VALID_KB_FORMATS[4] = ("graph",)` + type=4 的 index_mode/multimodal 强制规则 |
| `backend/app/models/kb/kg_entity.py` | 新增：实体实例（节点，含向量列） |
| `backend/app/models/kb/kg_entity_mention.py` | 新增：实体↔切片提及（溯源/幂等，P3 填充） |
| `backend/app/models/kb/kg_triple.py` | 新增：关系实例（边，含向量列） |
| `backend/app/models/kb/kg_triple_mention.py` | 新增：关系↔切片提及（P3 填充） |
| `backend/app/db/init_models.py` | 改：注册 4 个新模型 |
| `backend/app/services/kb/kg/kg_service.py` | 新增：实体/关系 CRUD + 评审流转 + 租户过滤 |
| `backend/app/routers/kb/kg.py` | 新增：图谱端点（前缀 `/api/v1/kb/knowledges/{kid}/graph`） |
| `backend/app/core/router_registry.py` | 改：`ROUTER_SPECS` 增加 `app.routers.kb.kg` |
| `backend/alembic/versions/xxxx_kg_tables.py` | 新增：4 张表迁移（含唯一约束、GIN、pgvector HNSW 索引） |
| `backend/tests/kb/test_kg_crud.py` | 新增：CRUD + 校验契约测试 |
| `backend/tests/kb/test_kg_permissions.py` | 新增：租户隔离 + 权限 + 评审流转测试 |
| `frontend/src/views/kms/KnowledgeBaseManager.vue` | 改：类型下拉 +4、向导分支、树节点图标、面板分发 |
| `frontend/src/views/kms/kg/KbGraphPane.vue` | 新增：主面板（工具栏 + Tabs + 右侧检视面板占位） |
| `frontend/src/views/kms/kg/KgOverview.vue` | 新增：概览 Tab（统计/分布/构建状态占位） |
| `frontend/src/views/kms/kg/KgEntityTable.vue` | 新增：实体 Tab（列表 + 评审操作） |
| `frontend/src/views/kms/kg/KgTripleTable.vue` | 新增：关系 Tab（列表 + 评审操作） |
| `frontend/src/api/kg.ts` | 新增：图谱 API 封装（不复用已重复的 `kb.ts`/`knowledgeBase.ts`） |
| `frontend/src/i18n/locales/*.json` | 改：新增 `kbMgmt.kg.*` 命名空间 key |

约定：`Base` 从 `app.db.database` 导入；租户表继承 `app.models.tenant_mixin.TenantMixin`；迁移用 Alembic；权限统一经 `require_kb_permission`（见 `app/services/kb/kb_permissions.py`，码 `KB_VIEW`/`KB_ADMIN` 等）。

---

## P0 · 前置门禁验证（非交付代码，先验证后开工）

> P0 是**外部依赖门禁**，不由本计划写代码。任一检查不过则暂停并回报，不进入 P1。

- [x] **Step 1: semantica 迁移完成** — 确认 `app.services.semantica` 公开方法存在：`extract_triplets` / `deduplicate` / `detect_conflicts`（P2/P3 将消费，P1 仅确认可用，不调用）。
- [x] **Step 2: ontology 清理完成** — 全局搜索 `from app.routers.ontology` / `owl_engine` 的残留 import 为 0；确认本计划改动面（wiki_knowledge / kb_format / kg_* / KnowledgeBaseManager）**不引用** ontology 任何符号（grep 校验）。
- [x] **Step 3: CDM 模式层 API 可用** — `GET /api/v1/dataops/standard/graph` 返回 `{nodes, edges}`，且 `meta_object_standard` / `meta_object_relation` 表可读（P1 仅做类型合法性参考，不强制校验）。
- [x] **Step 4: Neo4j 可连通** — 运行一次性脚本：`from neo4j import GraphDatabase; GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)).session().run("RETURN 1")` 成功（环境 `NEO4J_ENABLED=true`）。
- [x] **Step 5: Commit / 记录** — 在 spec §9.2 的「依赖核实」处勾选门禁通过，附验证命令输出。

---

## P1 · 类型骨架 + 实例层

### Task 1: 类型枚举 + 格式矩阵（后端地基）

**Files:**
- Modify: `backend/app/models/wiki/wiki_knowledge.py`
- Modify: `backend/app/services/kb/kb_format.py`
- Modify: `backend/app/services/wiki/knowledge_service.py`（admin 创建链路，line ~79 索引模式处理）
- Modify: `backend/app/routers/kb/knowledge_mgnt.py`（用户创建链路，line ~266 校验后 index_mode 赋值）

- [x] **Step 1: 枚举加 type=4**

```python
# backend/app/models/wiki/wiki_knowledge.py
class KnowledgeType(IntEnum):
    LLM_WIKI = 1
    GENERAL_KB = 2
    EXTERNAL_KB = 3
    GRAPH_KB = 4      # 知识图谱：实体/关系实例层（kb_format='graph'）
```

- [x] **Step 2: 格式矩阵加 type=4**

```python
# backend/app/services/kb/kb_format.py
VALID_KB_FORMATS: dict[int, tuple[str, ...]] = {
    1: (),
    2: ("document", "table", "qa"),
    3: ("connector", "proxy"),
    4: ("graph",),   # 图谱库形态固定为 graph
}

def normalize_graph_kb(kb_type: int, data: dict) -> None:
    """type=4 强制约束：kb_format='graph'、index_mode='high_quality'、
    multimodal_enabled=False、external_type 必须 NULL（validate_external_type 的 type≠3 分支已拒绝，自动生效）。"""
    if kb_type != 4:
        return
    data["kb_format"] = "graph"
    data["index_mode"] = "high_quality"          # economy 无向量则实体无法召回
    data["multimodal_enabled"] = False
```

- [x] **Step 3: 两条创建链路调用强制约束**

  在 `knowledge_service.py` 的 `validate_kb_format(kb_type, ...)` 之后、`knowledge_mgnt.py` 的 `validate_kb_format(body.type, ...)` 之后，各插入一行 `normalize_graph_kb(kb_type, data)` / `normalize_graph_kb(body.type, vars(body))`。确保 type=4 时 `index_mode` 落到 `WikiKnowledge.index_mode`、且 `external_type` 保持 None。

  > 注意：`validate_external_type(kb_type=4, ...)` 走 `type != 3` 分支直接返回 None，无需改动即可满足「external_type 必须为 NULL」。

- [x] **Step 4: pytest 契约测试（失败→实现→通过）**

```python
# backend/tests/kb/test_kg_format.py
def test_type4_format_matrix():
    from app.services.kb.kb_format import validate_kb_format, normalize_graph_kb
    assert validate_kb_format(4, "graph") == "graph"
    import pytest
    with pytest.raises(Exception):
        validate_kb_format(4, "document")          # 非法形态
    d = {"kb_format": "document", "index_mode": "economy", "multimodal_enabled": True}
    normalize_graph_kb(4, d)
    assert d == {"kb_format": "graph", "index_mode": "high_quality", "multimodal_enabled": False}
    assert normalize_graph_kb(2, dict(d)) is None    # 不影响其它类型
```

- [x] **Step 5: 跑测试确认通过** — `cd backend && python -m pytest tests/kb/test_kg_format.py -v`
- [x] **Step 6: Commit**

```bash
git commit -m "feat(kb): add KnowledgeType.GRAPH_KB=4 and graph format matrix with forced constraints"
```

---

### Task 2: 实例层 4 张表 ORM + 迁移

**Files:**
- Create: `backend/app/models/kb/kg_entity.py`
- Create: `backend/app/models/kb/kg_entity_mention.py`
- Create: `backend/app/models/kb/kg_triple.py`
- Create: `backend/app/models/kb/kg_triple_mention.py`
- Modify: `backend/app/db/init_models.py`
- Create: `backend/alembic/versions/xxxx_add_kg_tables.py`

- [x] **Step 1: 写失败测试（表可创建、唯一约束生效）**

```python
# backend/tests/kb/test_kg_models.py
def test_kg_tables_created(db_session):
    from app.models.kb.kg_entity import KgEntity
    from app.models.kb.kg_triple import KgTriple
    e = KgEntity(tenant_id=1, knowledge_id=10, entity_key="客户:1001", name="星海科技",
                  type_code="OBJ_CUSTOMER", status="suggested")
    db_session.add(e); db_session.commit()
    assert db_session.query(KgEntity).filter_by(entity_key="客户:1001").one()
```

- [x] **Step 2: 实现 ORM（沿用 `TenantMixin`，字段对齐 spec §3.3–§3.6）**

```python
# backend/app/models/kb/kg_entity.py
class KgEntity(Base, TenantMixin):
    __tablename__ = "kg_entity"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    knowledge_id = Column(BigInteger, nullable=False, index=True)
    collection = Column(String(128), nullable=False, default="")
    entity_key = Column(String(512), nullable=False)          # 规范化去重键
    name = Column(String(500), nullable=False)
    type_code = Column(String(64), nullable=True)             # → meta_object_standard.code
    aliases = Column(JSONB, nullable=True)
    properties = Column(JSONB, nullable=True)                 # {属性code: 值}
    source_segment_ids = Column(JSONB, nullable=True)
    source_document_ids = Column(JSONB, nullable=True)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=True)
    status = Column(String(16), nullable=False, server_default="suggested")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("tenant_id", "knowledge_id", "entity_key", name="uq_kg_entity_key"),
        Index("idx_kg_entity_tenant_kb_type", "tenant_id", "knowledge_id", "type_code"),
    )
```

`kg_triple`：`from_entity_id` / `to_entity_id`（`BigInteger`，FK→`kg_entity.id` `ondelete=CASCADE`）、`relation_code`（`String64`→`meta_object_relation.code`）、`predicate`（`String200`）、`weight`（`Float`）、`properties`/`evidence`/`source_*`（`JSONB`）、`embedding`（`Vector`，P3/P4 填充）、`status`（`suggested|accepted|rejected`，默认 `suggested`）；唯一约束 `Unique(tenant_id, knowledge_id, from_entity_id, relation_code, to_entity_id)`。

`kg_entity_mention` / `kg_triple_mention`：`kg_*_id` FK `CASCADE` + `segment_id`（`BigInteger`，→`kms_segment.id`，nullable）+ `document_id`（`String128`，→`kb_document.uuid_code`）+ `created_at`；唯一约束 `(kg_*_id, segment_id)`。P1 仅建表，P3 填充。

- [x] **Step 3: 注册 `init_models.py`** — 在现有 `kb` 模型导入段追加 `from app.models.kb.kg_entity import KgEntity` 等 4 个（参照文件内既有 `kb_segment` 注册写法）。
- [x] **Step 4: Alembic 迁移** — 建 4 表 + 唯一约束 + 索引 + `GIN(aliases)`/`GIN(properties)` + `kg_entity.embedding` / `kg_triple.embedding` 的 HNSW 索引（`USING hnsw ... vector_cosine_ops`）；`knowledge_id` 外键 `REFERENCES kms_knowledge(id) ON DELETE CASCADE`。
- [x] **Step 5: 跑迁移 + 测试** — `cd backend && alembic upgrade head`；`python -m pytest tests/kb/test_kg_models.py -v` 通过。
- [x] **Step 6: Commit**

```bash
git commit -m "feat(kb): add kg_entity/kg_triple and mention tables with tenant isolation"
```

---

### Task 3: 实例层服务（CRUD + 评审流转）

**Files:**
- Create: `backend/app/services/kb/kg/kg_service.py`
- Test: `backend/tests/kb/test_kg_crud.py`

- [x] **Step 1: 写失败测试**（实体创建/查重、关系创建、评审流转、租户隔离）

```python
def test_create_and_review_entity(db_session):
    from app.services.kb.kg.kg_service import KgService
    svc = KgService(db_session, tenant_id=1, knowledge_id=10)
    e = svc.create_entity(name="星海科技", entity_key="客户:1001", type_code="OBJ_CUSTOMER")
    assert e.id and e.status == "suggested"
    svc.accept_entity(e.id)                       # suggested → active
    assert svc.get_entity(e.id).status == "active"
    # 重复 entity_key 不增行（幂等）
    e2 = svc.create_entity(name="星海科技", entity_key="客户:1001", type_code="OBJ_CUSTOMER")
    assert e2.id == e.id

def test_tenant_isolation(db_session):
    from app.services.kb.kg.kg_service import KgService
    KgService(db_session, tenant_id=1, knowledge_id=10).create_entity(name="A", entity_key="k:A", type_code="X")
    assert KgService(db_session, tenant_id=2, knowledge_id=10).list_entities() == []
```

- [x] **Step 2: 实现 `KgService`**

```python
# backend/app/services/kb/kg/kg_service.py
class KgService:
    def __init__(self, db, tenant_id, knowledge_id): ...
    # 实体
    def create_entity(self, *, name, entity_key, type_code=None, aliases=None,
                      properties=None, source_segment_ids=None, source_document_ids=None) -> KgEntity
    def list_entities(self, *, type_code=None, status=None, keyword=None, limit=200, offset=0) -> list[KgEntity]
    def get_entity(self, entity_id) -> KgEntity | None
    def update_entity(self, entity_id, **fields) -> KgEntity          # name/type_code/aliases/properties
    def delete_entity(self, entity_id) -> None                        # 级联删关系（FK CASCADE）
    def accept_entity(self, entity_id) -> KgEntity                    # suggested → active
    # 关系（from_entity_id/to_entity_id 必须属于本 knowledge_id，否则 422）
    def create_triple(self, *, from_entity_id, to_entity_id, relation_code=None,
                      predicate=None, weight=0.0, properties=None, evidence=None,
                      source_segment_ids=None, source_document_ids=None) -> KgTriple
    def list_triples(self, *, relation_code=None, status=None, limit=200, offset=0) -> list[KgTriple]
    def review_triple(self, triple_id, verdict: "accepted|rejected") -> KgTriple   # suggested → accepted/rejected
    def delete_triple(self, triple_id) -> None
```

> 所有查询强制 `tenant_id` + `knowledge_id` 过滤；写操作前校验 `knowledge_id` 对应的 `kms_knowledge.type == 4`，否则 422。
> 评审语义沿用 dataops 既有词表：`entity.suggested→active`、`triple.suggested→accepted/rejected`，**不发明新词**。

- [x] **Step 3: 跑测试确认通过**
- [x] **Step 4: Commit**

```bash
git commit -m "feat(kb): KgService entity/relation CRUD with review transitions"
```

---

### Task 4: 图谱路由（端点 + 权限）

**Files:**
- Create: `backend/app/routers/kb/kg.py`
- Modify: `backend/app/core/router_registry.py`

- [x] **Step 1: 写失败测试**（端点可达 + 权限 + 校验）

```python
def test_kg_endpoints_require_view(client, auth_view_user):
    r = client.get("/api/v1/kb/knowledges/10/graph/entities", headers=auth_view_user)
    assert r.status_code == 200
    r = client.post("/api/v1/kb/knowledges/10/graph/entities", json={...}, headers=auth_view_user)
    assert r.status_code == 403        # 缺 kb:admin
```

- [x] **Step 2: 实现路由**（前缀 `/api/v1/kb/knowledges/{kid}/graph`）

| 方法 / 路径 | 权限 | 说明 |
|---|---|---|
| `GET /entities` | `KB_VIEW` | 列表（type_code/status/keyword/分页） |
| `POST /entities` | `KB_ADMIN` | 创建 |
| `GET /entities/{id}` | `KB_VIEW` | 详情 + 邻接边 |
| `PUT /entities/{id}` | `KB_ADMIN` | 编辑 |
| `DELETE /entities/{id}` | `KB_ADMIN` | 删除 |
| `PATCH /entities/{id}/accept` | `KB_ADMIN` | 评审 accepted |
| `GET /relations` | `KB_VIEW` | 关系列表 |
| `POST /relations` | `KB_ADMIN` | 创建（校验 from/to 归属） |
| `GET /relations/{id}` | `KB_VIEW` | 详情 |
| `DELETE /relations/{id}` | `KB_ADMIN` | 删除 |
| `PATCH /relations/{id}/review` | `KB_ADMIN` | 评审 accepted/rejected |
| `GET /stats` | `KB_VIEW` | 实体/关系计数 + 类型分布（概览 Tab 用） |

> 响应体字段对齐 spec §4.4.3/§4.4.5/§4.4.6；`stats` 返回 `{entities, relations, by_type:{...}, by_relation:{...}}`。
> 全部经 `require_kb_permission(code)` 闭合，前端隐藏非授权操作只是 UX 层。

- [x] **Step 3: 注册路由** — 在 `router_registry.py` 的 `knowledge_mgnt` 条目（28.4）之后追加：

```python
# --- 28.4.1 图谱知识库（type=4 实例层；router 自带完整 prefix /api/v1/kb/knowledges/{kid}/graph）---
RouterSpec("app.routers.kb.kg", tags=["图谱知识库"]),
```

- [x] **Step 4: 跑测试确认通过**（含 `python -m pytest tests/kb/test_kg_permissions.py`）
- [x] **Step 5: Commit**

```bash
git commit -m "feat(kb): graph knowledge base router with RBAC and stats endpoint"
```

---

### Task 5: 后端契约测试补全

**Files:**
- Create: `backend/tests/kb/test_kg_permissions.py`

- [x] **Step 1: 租户隔离** — 租户 A 的实体不可被租户 B 读取（即使伪造 kid）。
- [x] **Step 2: 权限矩阵** — `KB_VIEW` 可读不可写；`KB_ADMIN` 可写；非管理员无 `kb:admin` 写操作返回 403。
- [x] **Step 3: 评审流转** — `suggested→accepted/rejected`；非法流转（如 `accepted→suggested`）应拒绝。
- [x] **Step 4: 类型守卫** — 对非 `type=4` 的 knowledge_id 调图谱端点返回 422。
- [x] **Step 5: Commit**

```bash
git commit -m "test(kb): tenant isolation, RBAC and review-transition tests for graph KB"
```

---

### Task 6: 前端向导 type=4 分支

**Files:**
- Modify: `frontend/src/views/kms/KnowledgeBaseManager.vue`

- [x] **Step 1: 类型下拉加选项** — 类型 a-select 的 `:options` 增加 `{ label: t('kbMgmt.typeGraph'), value: 4 }`（复用既有 `typeOptions`/`kbTypeOptions` 定义处）。
- [x] **Step 2: `syncFormatForType` 处理 type=4** — 在 `allowed` 分支补充：

```ts
if (form.type === 4) {
  form.kb_format = 'graph'
  externalTab.value = 'connector'   // 无外部接入，保持中性
}
```

  并在模板中**隐藏** `index_mode` 与 `multimodal_enabled` 表单项（v-if 排除 `form.type === 4`）；提交时 type=4 不传 `index_mode`/`multimodal_enabled`（后端强制 high_quality/false）。
- [x] **Step 3: 树节点图标** — 左树渲染 `type=4` 时改用 `PartitionOutlined`（与 type=1/2/3 的 `ReadOutlined`/`BookOutlined`/`LinkOutlined` 区分），复用既有 `kbType` → icon 映射。
- [x] **Step 4: 面板分发** — 在模板 `selectedKbType === 2/3` 分支后加：

```vue
<KbGraphPane v-else-if="selectedKbType === 4 && selectedId"
  :knowledge-id="selectedId" :knowledge-name="selectedKbName" />
```

  并在 `<script>` 顶部 `import KbGraphPane from './kg/KbGraphPane.vue'`。
- [x] **Step 5: 构建验证（见 R9/R16）** — `cd frontend && npm run build 2>&1 | Select-String "KnowledgeBaseManager"` 确认无新增编译错误。
- [x] **Step 6: Commit**

```bash
git commit -m "feat(kb): frontend wizard + tree icon + pane dispatch for graph KB type=4"
```

---

### Task 7: 前端 `KbGraphPane` 主面板 + 4 个 Tab（P1 范围）

**Files:**
- Create: `frontend/src/views/kms/kg/KbGraphPane.vue`
- Create: `frontend/src/views/kms/kg/KgOverview.vue`
- Create: `frontend/src/views/kms/kg/KgEntityTable.vue`
- Create: `frontend/src/views/kms/kg/KgTripleTable.vue`
- Create: `frontend/src/api/kg.ts`

- [x] **Step 1: `api/kg.ts`** — 封装 `listEntities`/`createEntity`/`getEntity`/`updateEntity`/`deleteEntity`/`acceptEntity`/`listRelations`/`createRelation`/`reviewRelation`/`deleteRelation`/`getStats`，基准 `BASE = '/api/v1/kb/knowledges'`，走 `request`。**不复用** `kb.ts`/`knowledgeBase.ts`。
- [x] **Step 2: `KbGraphPane.vue`** — 骨架：工具栏（状态徽标占位 `未构建` + `构建图谱` 按钮 disabled 占位，真实构建在 P3）+ 8 Tab（`a-tabs`）；P1 实现 **概览 / 实体 / 关系 / 文档** 四个 Tab，**图谱 / 溯源 / 检索测试 / 配置** 四个 Tab 渲染 `a-empty` 占位「P2/P3/P5 交付」；右侧 `KgInspector` 占位区（P5 实现）。交互范式对标 `StandardManagement.vue`（Tabs + 检视面板）。
- [x] **Step 3: `KgOverview.vue`** — 调 `getStats`：统计卡片（实体/关系/类型/切片占位）+ 类型分布（`a-progress`）+ 构建状态占位（P3 接真实进度）。
- [x] **Step 4: `KgEntityTable.vue`** — 调 `listEntities`：表格列 名称/类型(type_code + CDM code 徽标)/别名/属性摘要/提及数/状态彩色 Tag/操作（检视/编辑/删除 `a-popconfirm`/评审接受）；批量操作栏（接受/删除）。编辑复用 P5 的 `KgEntityFormModal`（P1 先用 `a-modal` 内联简单表单）。
- [x] **Step 5: `KgTripleTable.vue`** — 调 `listRelations`：源→关系类型→目标 + 权重（<0.5 红/0.5–0.8 橙/>0.8 绿，同 `StdInspector.verdictColor` 写法）+ 状态 + 评审（接受/驳回 `PATCH`）。
- [x] **Step 6: 构建验证** — `npm run build 2>&1 | Select-String "kg/KbGraphPane|kg/Kg"` 无新增错误。
- [x] **Step 7: Commit**

```bash
git commit -m "feat(kb): KbGraphPane shell with overview/entity/relation tabs for graph KB"
```

---

### Task 8: i18n 占位（最小集）

**Files:**
- Modify: `frontend/src/i18n/locales/zh-CN.json`（按现有 locale 集补齐；`en-US.json` 等同步）
- Modify: `frontend/src/i18n/_kb_keys.json`（如存在 key 登记表，同步登记）

- [x] **Step 1: 新增 `kbMgmt.kg` 子树** — 仅 P1 用到的 key：`typeGraph` / `paneTitle` / `tabOverview` / `tabEntity` / `tabRelation` / `tabDoc` / `tabGraph`(占位) / `statEntities` / `statRelations` / `statusSuggested` / `statusAccepted` / `statusRejected` / `actionBuild`(disabled) / `placeholderLaterPhase`。
- [x] **Step 2: 复用既有 `t('kbMgmt.*')` 调用约定**，新增组件用 `useI18n()` 的同款写法（见 R16：自研 i18n 需按 locale 重挂子树才刷新，勿用模块级缓存 `t`）。
- [x] **Step 3: 构建验证** — `npm run build 2>&1 | Select-String "i18n"` 无报错。
- [x] **Step 4: Commit**

```bash
git commit -m "i18n(kb): add kbMgmt.kg namespace keys for graph KB P1"
```

---

### Task 9: 端到端冒烟

- [x] **Step 1: 后端 E2E 脚本** — 建 type=4 知识库 → `POST /graph/entities` → `GET /graph/entities` 可见 → `PATCH /graph/entities/{id}/accept` → `POST /graph/relations` → `GET /graph/stats` 计数正确 → 租户 B 读取返回空。
- [x] **Step 2: 前端冒烟** — `npm run dev` 后：新建「知识图谱」类型知识库 → 左树显示 `PartitionOutlined` → 主区进入 `KbGraphPane` → 概览/实体/关系 Tab 可增删改与评审 → 其它 Tab 显示占位 → 切换 locale 文案刷新正常（R16）。
- [x] **Step 3: 兼容性回归** — 确认 type=1/2/3 的创建、列表、检索行为在改 `kb_format`/`knowledge_service` 后**零变化**（跑既有 `tests/kb/*` 与 `tests/wiki/*`）。
- [x] **Step 4: Commit**

```bash
git commit -m "test(kb): e2e smoke for graph KB type=4 and regression on existing types"
```

---

## 验收标准

| 项 | 标准 |
|---|---|
| 类型落地 | `KnowledgeType.GRAPH_KB=4`；`VALID_KB_FORMATS[4]=("graph",)`；DB `type` 列零迁移（Integer 已兼容） |
| 强制约束 | type=4 创建后 `index_mode='high_quality'`、`multimodal_enabled=False`、`external_type=None`、`kb_format='graph'`（admin 与用户两条链路均生效） |
| 实例层 | `kg_entity`/`kg_triple`/`kg_entity_mention`/`kg_triple_mention` 4 表创建成功；`Unique(tenant_id, knowledge_id, entity_key)` 等约束生效 |
| CRUD | 实体/关系可增删改查；重复 `entity_key` 幂等不增行 |
| 评审闭环 | `suggested→active`（实体）/ `suggested→accepted|rejected`（关系），沿用 dataops 词表 |
| 租户隔离 | 租户 A 无法读取租户 B 的实体/关系，即使伪造 kid |
| 权限 | `KB_VIEW` 可读不可写；`KB_ADMIN` 可写；缺权写操作 403 |
| 类型守卫 | 对非 type=4 的 kid 调图谱端点返回 422 |
| 前端 | 向导可选 type=4 且隐藏 index_mode/multimodal；左树图标区分；`KbGraphPane` 概览/实体/关系 Tab 可用；其余 Tab 占位 |
| 契约不变 | 既有 `RetrieveResult` 与 type=1/2/3 行为零变化；`tests/kb/*`、`tests/wiki/*` 全绿 |
| 构建 | 前端 `npm run build` 过滤路径无新增编译错误 |

## 风险与退路

| 风险 | 退路 |
|---|---|
| R1 并行改造冲突（semantica/ontology 另一进程） | P0 门禁先验证；本计划只新增 `kg_*` 文件 + 改枚举/格式矩阵两处，不碰 ontology/semantica 内部；对 `SemanticaClient` 依赖仅经公开方法 |
| R9 前端工具链损坏（全仓 380 lint Parsing error） | 验证一律 `npm run build 2>&1 \| Select-String "<路径>"` 过滤；不在本计划修工具链 |
| R16 i18n 自研 locale 刷新陷阱 | 新增组件沿用既有 `useI18n()` 写法；locale 切换后实测图谱库各 Tab 文案刷新；新增 key 同步登记 |
| R4 向量维度不一致（历史高发） | `embedding` 列用 `Vector(settings.EMBEDDING_DIMENSION)`，P3 写入前 `fit_vector_dimension` 对齐；P1 列存在但留空，不引入第二套 embedder |
| R10 范围蔓延 | P1 严格限定「类型骨架 + 实例层 CRUD + 4 个 Tab 空壳」；图谱可视化/构建/检索/Neo4j 全部归属 P2–P6，不在本计划 |
| 迁移与外键级联 | `knowledge_id` FK `ON DELETE CASCADE`；测试覆盖删除知识库后 `kg_*` 行级联清理 |

---

## 执行记录（2026-10-30，全部步骤已完成）

提交（后端 → 前端）：

| # | commit | 内容 |
|---|---|---|
| 1 | `659019f` | Task 1 类型枚举 + 格式矩阵 + 强制约束 |
| 2 | `d8d1e8c` | Task 2 实例层 4 表 ORM + Alembic 迁移 |
| 3 | `8f6a4b1` | Task 3 KgService CRUD + 评审流转 |
| 4 | `150e972` | Task 4 图谱路由 12 端点 + RBAC + 路由注册 |
| 5 | `9c9b4cf` | Task 6/7 前端向导 + 主面板 + API + 组件 |
| 6 | `989d83d` | Task 8 i18n `kbMgmt.kg.*`（4 locale）+ 类型修复 |
| 7 | `ec660d6` | Task 9 e2e 冒烟 + **租户归属前置修复** |

验证结果：

| 项 | 结果 |
|---|---|
| 后端 `tests/kb` 全量 | **313 passed**（含 56 项图谱测试），存量 type=1/2/3 零回归 |
| 前端 `npm run build` | 本次改动文件 **0 类型错误**（仓库既有 vue-tsc 报错未触碰） |
| Alembic | `2026_10_30_0004_add_kg_tables` 已应用到 `miniworkbuddy`，4 表落地 |
| P0 门禁 | semantica 方法齐备 / ontology 残留 import = 0 / `GET /api/v1/dataops/standards/graph` 可用 / Neo4j `RETURN 1` 成功 |

### 执行中发现的偏差与决策

| # | 偏差 | 决策与理由 |
|---|---|---|
| D1 | 迁移创建 **HNSW 向量索引失败**：`column cannot have more than 2000 dimensions` | 实测生效维度为 **2048**（`settings.EMBEDDING_DIMENSION`），超出 pgvector HNSW 上限；且既有 `kms_segment.embedding`（同为 `vector(2048)`）**全库无 ANN 索引**——项目在 2048 维下本就顺序扫描。故 **kg_* 不建向量索引**，P3/P4 按实测选型（IVFFlat / halfvec）。避免无性能数据支撑的投机性索引 |
| D2 | `validate_kb_format(4, None)` 由「报错」改为**自动补齐 `graph`** | type=4 形态唯一，「固定」语义优于「必填」；避免 admin 面板 / 脚本 / 未来 MCP 工具都要记住 magic 字符串。测试同步调整 |
| D3 | 图谱端点需要 **total 计数** | 服务层补 `count_entities` / `count_triples`，与列表**共用过滤构造**，保证两者口径一致（避免分页 total 与实际不符） |
| D4 | 别名检索 `JSONB ILIKE` 不可用（PG 无 `jsonb ~~*`） | 改 `cast(aliases, String).ilike(...)` 显式转文本匹配 |
| D5 | **发现既有缺陷**：KB 创建未写 `tenant_id`，而生产 `tenant_interceptor` 按 `tenant_id` 自动过滤（`with_loader_criteria`）→ `tenant_id=NULL` 的知识库**对任何租户都不可见**（实测 `tenant=1` 查询返回 0/12） | **前置修复**：`knowledge_mgnt.create_knowledge` 与 `knowledge_service.create` 显式落 `tenant_id`（沿用 `article_service` 的既有写法）。否则图谱库「建了但看不见、也打不开」，功能不可用。此修复同时惠及 type=1/2/3 |
| D6 | 跨租户判定依赖 `kb.tenant_id`，而历史库为 NULL | 服务层守卫对「双方均非 NULL 且不相等」判 404；生产环境另有拦截器兜底（NULL 租户库对任何租户不可见）。测试覆盖两种路径 |
| D7 | P1 前端 8 Tab 中 5 个（文档/图谱/溯源/检索测试/配置）属后续阶段 | 实现为 **disabled 占位 Tab**（而非可点开的空面板），避免「点了是空白」的困惑；主面板 3 个可用 Tab（概览/实体/关系）+ 检视抽屉 |
| D8 | spec R16「i18n 为自研实现，模块级 `t` 需重挂子树才刷新」 | **事实更正**：现为标准 `vue-i18n`（`legacy: false`），点号路径与 locale 切换均原生响应式，R16 风险不成立 → spec 已修正 |
| D9 | 工作区混有另一进程（ontology 清理）的未提交改动 | 提交严格隔离：`router_registry.py` 与 4 个 locale 文件用**锚点定位补丁**只暂存本方案 hunk（`+75/-0`），他人改动留在工作区未被我提交 |

### 交付边界（P1 到此为止）

已交付：类型=4 容器、实例层 4 表、实体/关系 CRUD + 评审流转、12 个图谱端点（RBAC 闭合）、
前端向导 + 主面板（概览/实体/关系）+ 检视抽屉、4 locale i18n。

**未交付（按计划归后续阶段）**：文档上传与抽取管线（P3）、Neo4j 投影（P2）、
图谱可视化/溯源/检索测试/配置 Tab（P4/P5）、`kg_query` Agent 工具与 CDM 双向校验（P6）。


---

## P2–P6 执行记录（2026-10-31，全部阶段已完成）

### 提交序列

| # | commit | 内容 |
|---|---|---|
| 1 | `dd655ce` | P2 Neo4j 投影层（Cypher 模板集中 / label 白名单 / 幂等 MERGE / 可重建） |
| 2 | `b27ea0e` | P2 PG→Neo4j 投影接入实例层 CRUD（best-effort 降级） |
| 3 | `b43cfbd` | P3 抽取器 + 两阶段构建编排 + 单库互斥 + 构建端点 |
| 4 | `9ccdcde` | P3 前端构建配置 Tab / 状态轮询徽标 / 失败清单 |
| 5 | `bc158aa` | P4 图谱检索通道（PPR + 加权 RRF + 降级） |
| 6 | `42e2684` | P5 子图/路径端点 + CDM 校验 + `kg_query` 工具（P6） |
| 7 | `cfbe824` | P5 实体溯源端点 |
| 8 | `f5bfa03` | P4–P6 前端（图谱视图 / 检视面板 / 溯源 / 检索测试 / CDM 摘要） |

### 验证结果

| 项 | 结果 |
|---|---|
| `tests/kb` 全量 | **437 passed**（P1 时 313 → 新增 124 项） |
| 其余后端目录 | dataops/agent/connectors/unit/workflow/ai/semantica/integration 全绿（workflow 1 项与 integration 4 项为**基线既有失败**，已在 `799793c` 复现验证） |
| 前端 `npm run build` | 本次改动文件 **0 类型错误**（仓库既有 vue-tsc 报错未触碰） |
| Alembic | `2026_10_31_0005_add_kms_segment_graph_columns` 已应用 |

### 执行中新增的设计决策

| # | 决策 | 理由 |
|---|---|---|
| D10 | PPR 采用**无向图**传播 | Neo4j 的 MENTIONS 方向是「切片→实体」，有向图下种子实体永远无法把分数传到切片（切片为纯汇点，得分恒 0）。PPR 只承担相关性扩散、不承载方向语义，故取无向；方向语义由子图响应的 from/to 表达 |
| D11 | CDM 校验中「标准未覆盖的边」**不计入 conflict**，单列 `uncovered` 诊断 | spec §6.5 的 conflict 严格指「违反基数等约束」；CDM 目录未必覆盖全图，把未覆盖当冲突会淹没真冲突。hit/missing/conflict 三态词表保持不变 |
| D12 | 子图/路径查询走 **PG BFS**（跳数≤3 + 节点限流），不强制走 Neo4j | PG 是可见性权威；交互式查询规模下 BFS 足够，避免「Neo4j 不可用则整个图谱页不可用」 |
| D13 | `kg_query` 工具加 `tenant_resolver` 注入口 | 测试 schema 不含 `sys_user`；生产仍走 SysUser 查询（fail-closed 不变） |
| D14 | 溯源经**独立端点** `/graph/entities/{id}/mentions` 取切片正文 | 实体详情里的 `source_segment_ids` 只有 ID 没有正文，前端无法展示「这条实体出现在哪句话里」 |
| D15 | `networkx` 在 requirements.txt **显式声明** | spec §9.1 要求不可依赖传递依赖；实测环境虽已装 3.6.1，仍须显式声明 |

### 已知遗留（非本计划范围）

* **文档 Tab 仍为占位**：图谱库的文档上传/列表需等 P3 的摄取链路在真实图谱库上跑通后再开放 UI 入口。
* **`kg_entity.embedding` 无 ANN 索引**：生效维度 2048 超出 pgvector HNSW 上限（2000），与既有 `kms_segment` 保持同一策略；索引选型待实测（见 spec §9.2）。
* **PPR 规模上限**：子图取自 Neo4j 种子扩展（`graph_max_nodes` 默认 10000），万级节点下 networkx PPR 耗时需实测评估，超出即评估 Neo4j GDS（spec P7 可选项）。
