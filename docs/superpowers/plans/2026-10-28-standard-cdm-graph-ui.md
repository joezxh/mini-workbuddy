# 标准三层语义模型（CDM）+ 目录/场景 + 图驱动标准中心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「标准」从扁平属性字典升级为「目录/场景 → 对象标准 → 属性(全局复用) + 关系标准」三层 CDM，驱动元数据绑定与关系校验，并把 standard 页签改造成图驱动标准中心（ECharts 图 + 目录树 + 检视 + 总览 + NL 查询）。

**Architecture:** 后端在 dataops 域新增 7 张表（catalog / object / object-attribute / relation / table-binding / table-binding-history / relation-check），服务层扩展 `StandardBindingService` 为「列→属性 / 表→对象 / 关系校验」三步，NL 查询复用 `app.ai.research.llm.llm_json`；前端 `StandardManagement.vue` 重构为 shell，拆出目录树 / 图 / 检视 / 总览子组件，走 `/api/v1/dataops/standards/*` 新端点。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL(JSONB) · pytest；Vue 3 `<script setup>` · Ant Design Vue · vue-echarts(ECharts5) · vue-i18n · vitest。

**Spec:** `docs/superpowers/specs/2026-10-28-standard-cdm-graph-ui-design.md`

## Global Constraints

- **纯增量**：`meta_standard` / `meta_column_standard` / `meta_relation` 与 `DataSourcePanel.vue` 的 `a-tabs` 结构均不改动；旧列绑定/规则通道不受影响。
- **租户隔离**：所有新服务构造要求 `tenant_id`，`None` 即 `raise ValueError`（对齐 `MetaStandardService`）。路由经 `_require_tenant_id`。
- **删除保护链**：属性被对象引用→RESTRICT；对象被关系引用或表绑定→RESTRICT；目录有子节点或被对象/关系引用→服务层拒绝删除。
- **无新图库依赖**：图渲染只用已有的 `echarts` + `vue-echarts`。
- **Alembic**：新 revision 依赖 head `2026_10_28_0002_add_meta_table_db_name`；建表/种子幂等；downgrade 逆序 drop。
- **测试建表**：任何新增 ORM 类，必须同步登记进 `backend/tests/dataops/conftest.py` 的 `_tables()`，否则 `create_all` 建不出表、测试全挂。
- **API 前缀**：全部端点挂在 `router = APIRouter(prefix="/api/v1/dataops")`，路径以 `/standards/...` 起。
- **NL 降级**：`llm_json` 异常→HTTP 200 + `{degraded:true, error}`，绝不 500。
- **conflict 收敛**：关系校验 `conflict` 仅在「存在推断关系但 left/right 方向与标准 from/to 相反」时判；类型不符降级为 `hit` + evidence 备注。
- **提交节奏**：每个 Task 结尾 commit 一次；commit message 用 `feat(dataops|frontend): ...`。

## File Structure（创建/修改清单）

后端：
- Create `app/models/dataops/standard_cdm.py` — 7 张新 ORM（与 `standard.py` 分文件，职责单一）
- Modify `app/ai/dataops/rule_engine.py` — 追加 `ObjectMatch` + `RuleEngine.match_object` + `BUILTIN_OBJECT_STANDARDS` / `BUILTIN_RELATION_STANDARDS`
- Modify `app/services/dataops/scan_service.py`（如涉及序列化无需）— 无
- Create `app/services/dataops/standard_catalog_service.py` — `MetaStandardCatalogService`
- Create `app/services/dataops/object_standard_service.py` — `MetaObjectStandardService`
- Create `app/services/dataops/object_relation_service.py` — `MetaObjectRelationService`
- Create `app/services/dataops/standard_query_service.py` — `StandardQueryService`（graph/stats/nl-query）
- Modify `app/services/dataops/standard_binding_service.py` — 表→对象 + 关系校验 + `BindReport` 扩展
- Modify `app/routers/dataops/dataops.py` — 新增 `/standards/catalogs|objects|relations|graph|stats|nl-query` 端点
- Create `alembic/versions/2026_10_28_0003_add_standard_cdm_tables.py` — 7 表 + 种子
- Modify `tests/dataops/conftest.py` — `_tables()` 登记新 ORM
- Create tests：`tests/dataops/test_standard_cdm.py`（CRUD/catalog/relation/graph/stats/nl）+ 扩展 `tests/dataops/test_scan_query_write.py` 或新增 `test_table_object_binding.py`

前端：
- Modify `frontend/src/api/dataops.ts` — catalog/objects/relations/graph/stats/nl-query/objects-attributes 函数
- Create `frontend/src/views/data-source/standard/StdCatalogTree.vue`
- Create `frontend/src/views/data-source/standard/StdGraphView.vue`
- Create `frontend/src/views/data-source/standard/StdInspector.vue`
- Create `frontend/src/views/data-source/standard/StdOverviewView.vue`
- Create `frontend/src/views/data-source/standard/StdGuidTour.vue`
- Create `frontend/src/views/data-source/standard/ObjectFormModal.vue` / `RelationFormModal.vue`
- Modify `frontend/src/views/data-source/StandardManagement.vue` — 重构为标准中心 shell
- Modify `frontend/src/views/data-source/DataSourcePanel.vue` — 接 `@drill-down`
- Modify i18n locale files — `kbMgmt.catalog.*` / `kbMgmt.graph.*` / `kbMgmt.overview.*`

---

## 后端 Task B1：CDM 数据模型 + Alembic 迁移 + 测试建表登记

**Files:**
- Create: `backend/app/models/dataops/standard_cdm.py`
- Create: `backend/alembic/versions/2026_10_28_0003_add_standard_cdm_tables.py`
- Modify: `backend/tests/dataops/conftest.py`（`_tables()` L52-73）

**Interfaces:**
- Produces ORM：`MetaStandardCatalog`, `MetaObjectStandard`, `MetaObjectStandardAttribute`, `MetaObjectRelation`, `MetaTableStandard`, `MetaTableStandardHistory`, `MetaRelationCheck`（均在 `app.models.dataops.standard_cdm`）
- Consumes FK：`meta_standard.id`, `meta_table.id`, `meta_data_source.id`, `meta_relation.id`

- [ ] **Step 1: 写 ORM 模型文件**

创建 `backend/app/models/dataops/standard_cdm.py`：

```python
"""标准三层语义模型（CDM）+ 目录/场景 + 表绑定/关系校验。

纯增量：不改动 standard.py 的 meta_standard / meta_column_standard。
见 spec docs/superpowers/specs/2026-10-28-standard-cdm-graph-ui-design.md。
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Float, ForeignKey, Index, Integer, String,
    Text, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class MetaStandardCatalog(Base, TenantMixin):
    """目录/场景层级树（圈定对象标准与关系标准）。"""

    __tablename__ = "meta_standard_catalog"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    parent_id = Column(BigInteger, ForeignKey("meta_standard_catalog.id", ondelete="RESTRICT"), nullable=True, comment="父节点（null=根）")
    code = Column(String(64), nullable=False, comment="目录编码（租户内唯一）")
    name = Column(String(200), nullable=False, comment="目录名称")
    description = Column(Text, nullable=True, comment="说明")
    icon = Column(String(32), nullable=True, comment="展示图标/emoji")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="同级排序")
    status = Column(String(32), nullable=False, server_default="draft", comment="draft|published")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_meta_catalog_code"),
        Index("idx_meta_catalog_tenant_parent", "tenant_id", "parent_id"),
    )


class MetaObjectStandard(Base, TenantMixin):
    """对象（表级）标准模板；catalog_id 可空=未归类。"""

    __tablename__ = "meta_object_standard"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    catalog_id = Column(BigInteger, ForeignKey("meta_standard_catalog.id", ondelete="RESTRICT"), nullable=True, comment="所属目录/场景（可空）")
    code = Column(String(64), nullable=False, comment="对象标准编码（租户内唯一）")
    name = Column(String(200), nullable=False, comment="对象名称")
    aliases_json = Column(JSONB, nullable=True, comment="别名（匹配物理表名/注释）")
    description = Column(Text, nullable=True, comment="说明")
    domain = Column(String(64), nullable=True, comment="主题域")
    status = Column(String(32), nullable=False, server_default="draft", comment="draft|published")
    current_version = Column(Integer, nullable=False, server_default="1", comment="当前版本号")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_meta_object_standard_code"),
        Index("idx_meta_object_standard_catalog", "tenant_id", "catalog_id"),
    )


class MetaObjectStandardAttribute(Base, TenantMixin):
    """对象↔属性 引用（M2M，落地属性全局复用）。"""

    __tablename__ = "meta_object_standard_attribute"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    object_id = Column(BigInteger, ForeignKey("meta_object_standard.id", ondelete="CASCADE"), nullable=False, comment="对象标准 ID")
    standard_id = Column(BigInteger, ForeignKey("meta_standard.id", ondelete="RESTRICT"), nullable=False, comment="属性标准 ID")
    required = Column(Boolean, nullable=False, server_default="false", comment="是否必填属性")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="对象内排序")
    security_level_override = Column(String(8), nullable=True, comment="对象上下文安全等级覆盖")
    note = Column(String(500), nullable=True, comment="备注")

    __table_args__ = (
        UniqueConstraint("object_id", "standard_id", name="uq_meta_object_attribute"),
        Index("idx_meta_object_attribute_object", "object_id"),
    )


class MetaObjectRelation(Base, TenantMixin):
    """关系标准（对象→对象的人工定义关系）。"""

    __tablename__ = "meta_object_relation"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    catalog_id = Column(BigInteger, ForeignKey("meta_standard_catalog.id", ondelete="RESTRICT"), nullable=True, comment="所属目录/场景（可空）")
    code = Column(String(64), nullable=False, comment="关系编码（租户内唯一）")
    name = Column(String(200), nullable=False, comment="关系名称")
    from_object_id = Column(BigInteger, ForeignKey("meta_object_standard.id", ondelete="RESTRICT"), nullable=False, comment="起始对象")
    to_object_id = Column(BigInteger, ForeignKey("meta_object_standard.id", ondelete="RESTRICT"), nullable=False, comment="目标对象")
    relation_type = Column(String(16), nullable=False, comment="1:1|1:N|N:1|N:N")
    via_attribute_ids = Column(JSONB, nullable=True, comment="连接键引用的属性标准 id 列表（有序）")
    description = Column(Text, nullable=True, comment="说明")
    status = Column(String(32), nullable=False, server_default="draft", comment="draft|published")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_meta_object_relation_code"),
        Index("idx_meta_object_relation_from", "from_object_id"),
        Index("idx_meta_object_relation_to", "to_object_id"),
        Index("idx_meta_object_relation_catalog", "tenant_id", "catalog_id"),
    )


class MetaTableStandard(Base, TenantMixin):
    """表↔对象 绑定（镜像 meta_column_standard 评审语义，表侧 1:1）。"""

    __tablename__ = "meta_table_standard"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    table_id = Column(BigInteger, ForeignKey("meta_table.id", ondelete="CASCADE"), nullable=False, comment="物理表 ID（1:1 唯一）")
    object_standard_id = Column(BigInteger, ForeignKey("meta_object_standard.id", ondelete="RESTRICT"), nullable=False, comment="对象标准 ID")
    standard_version = Column(Integer, nullable=True, comment="绑定时对象版本")
    security_level_override = Column(String(8), nullable=True, comment="覆盖")
    status = Column(String(32), nullable=False, server_default="suggested", comment="suggested|accepted|rejected")
    source = Column(String(32), nullable=False, server_default="human", comment="rule|llm|human")
    confidence = Column(Float, nullable=True, comment="置信度（rule 通道产出）")
    evidence_json = Column(JSONB, nullable=True, comment="判定依据")
    reviewed_by = Column(BigInteger, nullable=True, comment="评审人")
    reviewed_at = Column(TIMESTAMP, nullable=True, comment="评审时间")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("table_id", name="uq_meta_table_standard_table"),
    )


class MetaTableStandardHistory(Base, TenantMixin):
    """表绑定变更历史（对齐 meta_column_standard_history）。"""

    __tablename__ = "meta_table_standard_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    table_id = Column(BigInteger, nullable=False, comment="物理表 ID")
    object_standard_id = Column(BigInteger, nullable=False, comment="对象标准 ID")
    standard_version = Column(Integer, nullable=True, comment="涉及版本")
    action = Column(String(32), nullable=False, comment="bind|unbind|accept|reject|override")
    snapshot_json = Column(JSONB, nullable=True, comment="变更时绑定快照")
    actor_user_id = Column(BigInteger, nullable=True, comment="操作人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_meta_table_std_history_table", "table_id"),
    )


class MetaRelationCheck(Base, TenantMixin):
    """标准关系 vs 推断 meta_relation 的校验结论。"""

    __tablename__ = "meta_relation_check"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    standard_relation_id = Column(BigInteger, ForeignKey("meta_object_relation.id", ondelete="CASCADE"), nullable=False, comment="关系标准 ID")
    source_id = Column(BigInteger, ForeignKey("meta_data_source.id", ondelete="CASCADE"), nullable=False, comment="数据源 ID")
    database = Column(String(128), nullable=False, comment="库/schema 作用域（对齐 meta_relation.database）")
    inferred_relation_id = Column(BigInteger, ForeignKey("meta_relation.id", ondelete="SET NULL"), nullable=True, comment="命中的推断关系")
    verdict = Column(String(16), nullable=False, comment="hit|missing|conflict")
    confidence = Column(Float, nullable=True, comment="命中推断关系的置信度")
    evidence_json = Column(JSONB, nullable=True, comment="比对依据（两端表名/方向/差异）")
    checked_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="校验时间")

    __table_args__ = (
        UniqueConstraint("standard_relation_id", "source_id", "database", name="uq_meta_relation_check"),
        Index("idx_meta_relation_check_source", "source_id", "database"),
    )
```

- [ ] **Step 2: 在 `__init__`/imports 让 ORM 可被发现**

确认 `app/models/dataops/standard_cdm.py` 被 alembic autogenerate 环境与应用 models 导入链加载（`backend/alembic/env.py` 通常 `from app.models... import *`；若显式列模型，追加导入）。Run: `python -c "import app.models.dataops.standard_cdm"` Expected: 无报错。

- [ ] **Step 3: 登记测试建表清单**

Modify `backend/tests/dataops/conftest.py`，在 `_tables()` 导入块追加并返回 7 个新表：

```python
    from app.models.dataops.standard_cdm import (
        MetaObjectRelation, MetaObjectStandard, MetaObjectStandardAttribute,
        MetaRelationCheck, MetaStandardCatalog, MetaTableStandard,
        MetaTableStandardHistory,
    )
```

并在 `return [...]` 列表尾部追加：

```python
        MetaStandardCatalog.__table__,
        MetaObjectStandard.__table__,
        MetaObjectStandardAttribute.__table__,
        MetaObjectRelation.__table__,
        MetaTableStandard.__table__,
        MetaTableStandardHistory.__table__,
        MetaRelationCheck.__table__,
```

- [ ] **Step 4: 写建表冒烟测试**

Create `backend/tests/dataops/test_standard_cdm.py`：

```python
"""CDM 模型/服务 冒烟（B1）。"""
from sqlalchemy import inspect

TENANT_A = 100


def test_cdm_tables_created(db, engine):
    names = set(inspect(engine).get_table_names())
    for t in [
        "meta_standard_catalog", "meta_object_standard",
        "meta_object_standard_attribute", "meta_object_relation",
        "meta_table_standard", "meta_table_standard_history", "meta_relation_check",
    ]:
        assert t in names, f"{t} 未建出（检查 conftest._tables 登记）"
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/dataops/test_standard_cdm.py::test_cdm_tables_created -v`
Expected: PASS

- [ ] **Step 6: 写 Alembic 迁移（生产库）**

Create `backend/alembic/versions/2026_10_28_0003_add_standard_cdm_tables.py`：

```python
"""add standard CDM tables (7) + seed demo scenes

Revision ID: 2026_10_28_0003_add_standard_cdm_tables
Revises: 2026_10_28_0002_add_meta_table_db_name
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_10_28_0003_add_standard_cdm_tables"
down_revision = "2026_10_28_0002_add_meta_table_db_name"
branch_labels = None
depends_on = None

_TABLES = [
    "meta_standard_catalog", "meta_object_standard",
    "meta_object_standard_attribute", "meta_object_relation",
    "meta_table_standard", "meta_table_standard_history", "meta_relation_check",
]


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    # 逐表 create_all 风格：仅当不存在时建（幂等）
    if not _table_exists("meta_standard_catalog"):
        op.create_table(
            "meta_standard_catalog",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("parent_id", sa.BigInteger(), nullable=True),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("icon", sa.String(32), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
            sa.Column("status", sa.String(32), server_default="draft", nullable=False),
            sa.Column("creator_id", sa.BigInteger(), nullable=True),
            sa.Column("updater_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["parent_id"], ["meta_standard_catalog.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "code", name="uq_meta_catalog_code"),
        )
        op.create_index("idx_meta_catalog_tenant_parent", "meta_standard_catalog", ["tenant_id", "parent_id"])
    # ... 其余 6 表列定义与模型一一对应（此处按 standard_cdm.py 逐表 op.create_table）
    _create_object_standard()
    _create_object_standard_attribute()
    _create_object_relation()
    _create_table_standard()
    _create_table_standard_history()
    _create_relation_check()
    _seed_demo_scenes()


# 说明：_create_* / _seed_demo_scenes 的完整列/约束与 standard_cdm.py 严格一致；
# 迁移执行阶段逐函数实现（列宽/FK/ondelete 从模型抄），不在此省略。


def downgrade() -> None:
    for t in reversed(_TABLES):
        if _table_exists(t):
            op.drop_table(t)
```

> 实现要求（非占位）：6 个 `_create_*()` 各自 `if not _table_exists(...)` 后 `op.create_table`，列定义**逐字**取自 Step 1 模型；`_seed_demo_scenes()` 按 tenant 无关的全局 seed 略（种子在 B2 service `seed` 落地以复用租户逻辑；迁移仅建表，保持 schema 纯净）。若需迁移内物理种子，插入 catalog 根「电商/物流」两行并 `ON CONFLICT DO NOTHING`。

- [ ] **Step 7: 迁移往返验证（本地 PG）**

Run: `cd backend && alembic upgrade head`
Expected: `Running upgrade ... 0002 -> ...0003_add_standard_cdm_tables`
Run: `alembic downgrade -1` 然后 `alembic upgrade head`
Expected: 往返无报错，表存在性符合。

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/dataops/standard_cdm.py backend/tests/dataops/conftest.py backend/tests/dataops/test_standard_cdm.py backend/alembic/versions/2026_10_28_0003_add_standard_cdm_tables.py
git commit -m "feat(dataops): add standard CDM models, migration and test registration"
```

---

## 后端 Task B2：目录树 + 对象标准 + 引用属性 CRUD（服务 + 路由）

**Files:**
- Create: `backend/app/services/dataops/standard_catalog_service.py`
- Create: `backend/app/services/dataops/object_standard_service.py`
- Modify: `backend/app/routers/dataops/dataops.py`（新增 `/standards/catalogs*`, `/standards/objects*` 端点）
- Test: `backend/tests/dataops/test_standard_cdm.py`（追加）

**Interfaces:**
- Consumes: `MetaStandardCatalog`, `MetaObjectStandard`, `MetaObjectStandardAttribute`, `MetaStandard`（ORM）
- Produces:
  - `MetaStandardCatalogService(db, tenant_id)`：`list_tree()->list[dict]`, `create(code,name,parent_id=None,icon=None,description=None)->obj`, `update(id,**fields)->obj`, `move(id,parent_id)->obj`, `delete(id)->None`(RESTRICT), `serialize(c)->dict`
  - `MetaObjectStandardService(db, tenant_id)`：`list(catalog_id=None)->list[obj]`, `create(code,name,catalog_id=None,aliases=None,domain=None,description=None,creator_id=None)->obj`, `update(id,**fields)`, `delete(id)`, `set_attributes(object_id, items:list[dict])->None`(全量替换), `get_attributes(object_id)->list[dict]`, `serialize(o, with_attrs=False)->dict`
  - 删除保护：`delete` 命中子节点/引用抛 `ValueError`

- [ ] **Step 1: 写失败测试（catalog RESTRICT + object attrs）**

在 `test_standard_cdm.py` 追加：

```python
import pytest
from app.services.dataops.standard_catalog_service import MetaStandardCatalogService
from app.services.dataops.object_standard_service import MetaObjectStandardService
from app.services.dataops.standard_service import MetaStandardService


def _attr(db):
    return MetaStandardService(db, TENANT_A).create("std_test_col", "测试列", aliases=["col"])


def test_catalog_tree_and_delete_restricted(db):
    svc = MetaStandardCatalogService(db, TENANT_A)
    root = svc.create("scene_ec", "电商场景")
    child = svc.create("trade", "交易", parent_id=root.id)
    tree = svc.list_tree()
    assert tree[0]["code"] == "scene_ec"
    assert tree[0]["children"][0]["code"] == "trade"
    with pytest.raises(ValueError):  # 有子节点
        svc.delete(root.id)
    svc.delete(child.id)  # 叶子可删
    svc.delete(root.id)


def test_catalog_delete_blocked_by_object(db):
    cat = MetaStandardCatalogService(db, TENANT_A).create("scene_log", "物流场景")
    MetaObjectStandardService(db, TENANT_A).create("obj_order", "订单", catalog_id=cat.id)
    with pytest.raises(ValueError):
        MetaStandardCatalogService(db, TENANT_A).delete(cat.id)


def test_object_set_attributes_replaces_and_resists_attr_delete(db):
    attr = _attr(db)
    obj_svc = MetaObjectStandardService(db, TENANT_A)
    obj = obj_svc.create("obj_customer", "客户")
    obj_svc.set_attributes(obj.id, [{"standard_id": attr.id, "required": True, "sort_order": 1}])
    attrs = obj_svc.get_attributes(obj.id)
    assert len(attrs) == 1 and attrs[0]["standard_id"] == attr.id
    # 全量替换为空
    obj_svc.set_attributes(obj.id, [])
    assert obj_svc.get_attributes(obj.id) == []
    # 属性被引用时删除属性标准应被拒（RESTRICT）
    obj_svc.set_attributes(obj.id, [{"standard_id": attr.id}])
    db.flush()
    with pytest.raises(Exception):
        MetaStandardService(db, TENANT_A).delete(attr.id)
        db.flush()
    db.rollback()
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/dataops/test_standard_cdm.py -k "catalog or object_set" -v`
Expected: FAIL（模块/类不存在）

- [ ] **Step 3: 实现 MetaStandardCatalogService**

Create `backend/app/services/dataops/standard_catalog_service.py`：

```python
"""目录/场景树服务（B2）。租户隔离；删除 RESTRICT 保护。"""
from __future__ import annotations
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaStandardCatalog,
)


class MetaStandardCatalogService:
    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("MetaStandardCatalogService 要求 tenant_id")
        self.db = db
        self.tenant_id = tenant_id

    def get_or_404(self, cid: int) -> MetaStandardCatalog:
        obj = self.db.execute(select(MetaStandardCatalog).where(
            MetaStandardCatalog.tenant_id == self.tenant_id,
            MetaStandardCatalog.id == cid)).scalar_one_or_none()
        if obj is None:
            raise KeyError(cid)
        return obj

    def _by_code(self, code: str) -> Optional[MetaStandardCatalog]:
        return self.db.execute(select(MetaStandardCatalog).where(
            MetaStandardCatalog.tenant_id == self.tenant_id,
            MetaStandardCatalog.code == code)).scalar_one_or_none()

    def list_all(self) -> List[MetaStandardCatalog]:
        return list(self.db.execute(select(MetaStandardCatalog).where(
            MetaStandardCatalog.tenant_id == self.tenant_id)
            .order_by(MetaStandardCatalog.sort_order, MetaStandardCatalog.id)).scalars().all())

    def list_tree(self) -> List[dict]:
        nodes = {c.id: {**self.serialize(c), "children": []} for c in self.list_all()}
        roots: List[dict] = []
        for c in self.list_all():
            parent = nodes.get(c.parent_id) if c.parent_id else None
            (parent["children"] if parent else roots).append(nodes[c.id])
        return roots

    def create(self, code: str, name: str, *, parent_id: Optional[int] = None,
               icon: Optional[str] = None, description: Optional[str] = None,
               creator_id: Optional[int] = None) -> MetaStandardCatalog:
        if self._by_code(code):
            raise ValueError(f"目录编码已存在: {code}")
        obj = MetaStandardCatalog(tenant_id=self.tenant_id, code=code, name=name,
                                  parent_id=parent_id, icon=icon, description=description,
                                  status="published", creator_id=creator_id)
        self.db.add(obj); self.db.flush()
        return obj

    def update(self, cid: int, **fields) -> MetaStandardCatalog:
        obj = self.get_or_404(cid)
        new_code = fields.get("code")
        if new_code and new_code != obj.code:
            conflict = self._by_code(new_code)
            if conflict and conflict.id != obj.id:
                raise ValueError(f"目录编码已存在: {new_code}")
        for k, v in fields.items():
            if v is not None and hasattr(obj, k):
                setattr(obj, k, v)
        self.db.flush()
        return obj

    def move(self, cid: int, parent_id: Optional[int]) -> MetaStandardCatalog:
        obj = self.get_or_404(cid)
        if parent_id == cid:
            raise ValueError("不能移动为自身子树")
        obj.parent_id = parent_id
        self.db.flush()
        return obj

    def delete(self, cid: int) -> None:
        obj = self.get_or_404(cid)
        if self.db.execute(select(MetaStandardCatalog.id).where(
            MetaStandardCatalog.parent_id == cid)).first():
            raise ValueError("目录存在子节点，禁止删除")
        if self.db.execute(select(MetaObjectStandard.id).where(
            MetaObjectStandard.catalog_id == cid)).first():
            raise ValueError("目录被对象标准引用，禁止删除")
        if self.db.execute(select(MetaObjectRelation.id).where(
            MetaObjectRelation.catalog_id == cid)).first():
            raise ValueError("目录被关系标准引用，禁止删除")
        self.db.delete(obj); self.db.flush()

    @staticmethod
    def serialize(c: MetaStandardCatalog) -> dict:
        return {"id": c.id, "parent_id": c.parent_id, "code": c.code, "name": c.name,
                "description": c.description, "icon": c.icon, "sort_order": c.sort_order,
                "status": c.status}
```

- [ ] **Step 4: 实现 MetaObjectStandardService**

Create `backend/app/services/dataops/object_standard_service.py`：

```python
"""对象标准服务（B2）：CRUD + 引用属性（全量替换）。"""
from __future__ import annotations
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.dataops.standard import MetaColumnStandard, MetaStandard
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaObjectStandardAttribute,
    MetaTableStandard,
)


class MetaObjectStandardService:
    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("MetaObjectStandardService 要求 tenant_id")
        self.db = db
        self.tenant_id = tenant_id

    def get_or_404(self, oid: int) -> MetaObjectStandard:
        obj = self.db.execute(select(MetaObjectStandard).where(
            MetaObjectStandard.tenant_id == self.tenant_id,
            MetaObjectStandard.id == oid)).scalar_one_or_none()
        if obj is None:
            raise KeyError(oid)
        return obj

    def _by_code(self, code: str) -> Optional[MetaObjectStandard]:
        return self.db.execute(select(MetaObjectStandard).where(
            MetaObjectStandard.tenant_id == self.tenant_id,
            MetaObjectStandard.code == code)).scalar_one_or_none()

    def list(self, catalog_id: Optional[int] = None) -> List[MetaObjectStandard]:
        stmt = select(MetaObjectStandard).where(MetaObjectStandard.tenant_id == self.tenant_id)
        if catalog_id is not None:
            stmt = stmt.where(MetaObjectStandard.catalog_id == catalog_id)
        return list(self.db.execute(stmt.order_by(MetaObjectStandard.code)).scalars().all())

    def create(self, code: str, name: str, *, catalog_id: Optional[int] = None,
               aliases: Optional[list] = None, domain: Optional[str] = None,
               description: Optional[str] = None, creator_id: Optional[int] = None) -> MetaObjectStandard:
        if self._by_code(code):
            raise ValueError(f"对象标准编码已存在: {code}")
        obj = MetaObjectStandard(tenant_id=self.tenant_id, code=code, name=name,
                                 catalog_id=catalog_id, aliases_json=aliases or [],
                                 domain=domain, description=description,
                                 status="published", creator_id=creator_id)
        self.db.add(obj); self.db.flush()
        return obj

    def update(self, oid: int, **fields) -> MetaObjectStandard:
        obj = self.get_or_404(oid)
        new_code = fields.get("code")
        if new_code and new_code != obj.code:
            conflict = self._by_code(new_code)
            if conflict and conflict.id != obj.id:
                raise ValueError(f"对象标准编码已存在: {new_code}")
        aliases = fields.pop("aliases", None)
        if aliases is not None:
            obj.aliases_json = aliases
        for k, v in fields.items():
            if v is not None and hasattr(obj, k):
                setattr(obj, k, v)
        self.db.flush()
        return obj

    def delete(self, oid: int) -> None:
        obj = self.get_or_404(oid)
        if self.db.execute(select(MetaObjectRelation.id).where(
            (MetaObjectRelation.from_object_id == oid) | (MetaObjectRelation.to_object_id == oid))).first():
            raise ValueError("对象被关系引用，禁止删除")
        if self.db.execute(select(MetaTableStandard.id).where(
            MetaTableStandard.object_standard_id == oid)).first():
            raise ValueError("对象已被物理表绑定，禁止删除")
        # 引用属性是 CASCADE，直接删对象即可；解绑属性关联不残留
        self.db.delete(obj); self.db.flush()

    def set_attributes(self, object_id: int, items: List[dict]) -> None:
        obj = self.get_or_404(object_id)
        # 全量替换：先删旧关联再插新（引用标准必须存在且同租户）
        self.db.query(MetaObjectStandardAttribute).filter(
            MetaObjectStandardAttribute.object_id == obj.id).delete(synchronize_session=False)
        for i, it in enumerate(items):
            sid = it["standard_id"]
            if self.db.execute(select(MetaStandard.id).where(
                MetaStandard.id == sid, MetaStandard.tenant_id == self.tenant_id)).first() is None:
                raise ValueError(f"属性标准不存在或跨租户: {sid}")
            self.db.add(MetaObjectStandardAttribute(
                tenant_id=self.tenant_id, object_id=obj.id, standard_id=sid,
                required=bool(it.get("required", False)),
                sort_order=int(it.get("sort_order", i)),
                security_level_override=it.get("security_level_override"),
                note=it.get("note"),
            ))
        self.db.flush()

    def get_attributes(self, object_id: int) -> List[dict]:
        rows = self.db.execute(
            select(MetaObjectStandardAttribute, MetaStandard)
            .join(MetaStandard, MetaStandard.id == MetaObjectStandardAttribute.standard_id)
            .where(MetaObjectStandardAttribute.object_id == object_id)
            .order_by(MetaObjectStandardAttribute.sort_order)
        ).all()
        return [{
            "standard_id": a.standard_id, "code": s.code, "name": s.name,
            "semantic_type": s.semantic_type, "security_level": a.security_level_override or s.security_level,
            "required": a.required, "sort_order": a.sort_order, "note": a.note,
        } for a, s in rows]

    @staticmethod
    def serialize(o: MetaObjectStandard, with_attrs: bool = False) -> dict:
        return {"id": o.id, "catalog_id": o.catalog_id, "code": o.code, "name": o.name,
                "aliases": o.aliases_json or [], "domain": o.domain,
                "description": o.description, "status": o.status,
                "current_version": o.current_version}
```

- [ ] **Step 5: 运行服务测试确认通过**

Run: `pytest tests/dataops/test_standard_cdm.py -k "catalog or object_set" -v`
Expected: PASS

- [ ] **Step 6: 加路由端点**

Modify `backend/app/routers/dataops/dataops.py`：在标准区（L708 附近 import 块）追加：

```python
from app.services.dataops.object_standard_service import MetaObjectStandardService
from app.services.dataops.standard_catalog_service import MetaStandardCatalogService


class CatalogCreate(BaseModel):
    code: str
    name: str
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    description: Optional[str] = None


class CatalogUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[str] = None


class CatalogMove(BaseModel):
    parent_id: Optional[int] = None


class ObjectAttrRef(BaseModel):
    standard_id: int
    required: bool = False
    sort_order: Optional[int] = None
    security_level_override: Optional[str] = None
    note: Optional[str] = None


class ObjectCreate(BaseModel):
    code: str
    name: str
    catalog_id: Optional[int] = None
    aliases: Optional[list] = None
    domain: Optional[str] = None
    description: Optional[str] = None


class ObjectUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    catalog_id: Optional[int] = None
    aliases: Optional[list] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ObjectAttributesBody(BaseModel):
    items: List[ObjectAttrRef]


@router.get("/standards/catalogs")
def list_catalogs(db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> list:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    return svc.list_tree()


@router.post("/standards/catalogs", status_code=201)
def create_catalog(body: CatalogCreate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> dict:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    try:
        obj = svc.create(body.code, body.name, parent_id=body.parent_id, icon=body.icon,
                         description=body.description, creator_id=getattr(current_user, "user_id", None))
        db.commit()
    except ValueError as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    return MetaStandardCatalogService.serialize(obj)


@router.put("/standards/catalogs/{catalog_id}")
def update_catalog(catalog_id: int, body: CatalogUpdate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> dict:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    try:
        obj = svc.update(catalog_id, **body.model_dump(exclude_none=True))
        db.commit()
    except KeyError:
        db.rollback(); raise HTTPException(404, "目录不存在")
    except ValueError as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    return MetaStandardCatalogService.serialize(obj)


@router.put("/standards/catalogs/{catalog_id}/move")
def move_catalog(catalog_id: int, body: CatalogMove, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> dict:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    try:
        obj = svc.move(catalog_id, body.parent_id)
        db.commit()
    except KeyError:
        db.rollback(); raise HTTPException(404, "目录不存在")
    except ValueError as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    return MetaStandardCatalogService.serialize(obj)


@router.delete("/standards/catalogs/{catalog_id}")
def delete_catalog(catalog_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> dict:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    try:
        svc.delete(catalog_id); db.commit()
    except KeyError:
        db.rollback(); raise HTTPException(404, "目录不存在")
    except ValueError as exc:
        db.rollback(); raise HTTPException(409, str(exc))
    return {"deleted": catalog_id}


@router.get("/standards/objects")
def list_objects(catalog_id: Optional[int] = None, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> list:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    return [MetaObjectStandardService.serialize(o) for o in svc.list(catalog_id)]


@router.post("/standards/objects", status_code=201)
def create_object(body: ObjectCreate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        obj = svc.create(body.code, body.name, catalog_id=body.catalog_id, aliases=body.aliases,
                        domain=body.domain, description=body.description,
                        creator_id=getattr(current_user, "user_id", None))
        db.commit()
    except ValueError as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    return MetaObjectStandardService.serialize(obj)


@router.get("/standards/objects/{object_id}")
def get_object(object_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        obj = svc.get_or_404(object_id)
    except KeyError:
        raise HTTPException(404, "对象标准不存在")
    d = MetaObjectStandardService.serialize(obj, with_attrs=True)
    d["attributes"] = svc.get_attributes(object_id)
    return d


@router.put("/standards/objects/{object_id}")
def update_object(object_id: int, body: ObjectUpdate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        obj = svc.update(object_id, **body.model_dump(exclude_none=True))
        db.commit()
    except KeyError:
        db.rollback(); raise HTTPException(404, "对象标准不存在")
    except ValueError as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    return MetaObjectStandardService.serialize(obj)


@router.put("/standards/objects/{object_id}/attributes")
def set_object_attributes(object_id: int, body: ObjectAttributesBody, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        svc.set_attributes(object_id, [it.model_dump() for it in body.items])
        db.commit()
    except KeyError:
        db.rollback(); raise HTTPException(404, "对象标准不存在")
    except ValueError as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    return {"attributes": svc.get_attributes(object_id)}


@router.delete("/standards/objects/{object_id}")
def delete_object(object_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        svc.delete(object_id); db.commit()
    except KeyError:
        db.rollback(); raise HTTPException(404, "对象标准不存在")
    except ValueError as exc:
        db.rollback(); raise HTTPException(409, str(exc))
    return {"deleted": object_id}
```

- [ ] **Step 7: 路由级冒烟测试**

追加到 `test_standard_cdm.py`：

```python
def test_catalog_and_object_routes(client_a, db):
    r = client_a.post("/api/v1/dataops/standards/catalogs", json={"code": "r_scene", "name": "场景"})
    assert r.status_code == 201
    cid = r.json()["id"]
    r2 = client_a.post("/api/v1/dataops/standards/objects", json={"code": "r_obj", "name": "对象", "catalog_id": cid})
    assert r2.status_code == 201
    oid = r2.json()["id"]
    assert any(o["id"] == oid for o in client_a.get(f"/api/v1/dataops/standards/objects", params={"catalog_id": cid}).json())
    # 目录被引用→删除 409
    assert client_a.delete(f"/api/v1/dataops/standards/catalogs/{cid}").status_code == 409
```

- [ ] **Step 8: 全绿**

Run: `pytest tests/dataops/test_standard_cdm.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/dataops/standard_catalog_service.py backend/app/services/dataops/object_standard_service.py backend/app/routers/dataops/dataops.py backend/tests/dataops/test_standard_cdm.py
git commit -m "feat(dataops): catalog tree and object standard CRUD with attribute refs"
```

---

## 后端 Task B3：表→对象绑定（rule 通道）

**Files:**
- Modify: `backend/app/ai/dataops/rule_engine.py`（追加 `ObjectMatch` + `RuleEngine.match_object` + `BUILTIN_OBJECT_STANDARDS`）
- Modify: `backend/app/services/dataops/standard_binding_service.py`（`bind_table` 三步 + `BindReport` 扩展 + `_bind_table_object`）
- Modify: `backend/app/routers/dataops/dataops.py`（`bind_source` 返回体补计数）
- Test: `backend/tests/dataops/test_table_object_binding.py`（新建）

**Interfaces:**
- Consumes: `MetaTable`, `MetaObjectStandard`, `tier`, `TIER_ACCEPTED`
- Produces:
  - `RuleEngine.match_object(table_name: str, comment: Optional[str], object_standards: List[dict]) -> Optional[ObjectMatch]`（object_standards 元素形如 `{id,code,name,aliases}`）
  - `ObjectMatch(object_code: str, object_id: Optional[int], confidence: float, evidence: dict)`
  - `StandardBindingService.bind_table(table_id) -> BindReport`（现在含表→对象步骤）
  - `BindReport` 新字段：`objects_bound / objects_updated / objects_skipped_human`

- [ ] **Step 1: 写 match_object 失败单测**

Create `backend/tests/dataops/test_table_object_binding.py`：

```python
from app.ai.dataops.rule_engine import RuleEngine

OBJ_STDS = [
    {"id": 1, "code": "obj_order", "name": "订单", "aliases": ["order", "orders", "订单表"]},
    {"id": 2, "code": "obj_customer", "name": "客户", "aliases": ["customer", "客户"]},
]


def test_match_object_substr_hit():
    m = RuleEngine.match_object("t_order", "订单明细表", OBJ_STDS)
    assert m is not None and m.object_code == "obj_order"
    assert m.confidence >= 0.65


def test_match_object_none_below_min():
    assert RuleEngine.match_object("audit_log", "审计日志", OBJ_STDS) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/dataops/test_table_object_binding.py -k match_object -v`
Expected: FAIL（无 `match_object`）

- [ ] **Step 3: 实现 match_object（镜像 match_standard）**

Modify `backend/app/ai/dataops/rule_engine.py`，`__all__` 追加 `"ObjectMatch"`, `"BUILTIN_OBJECT_STANDARDS"`；文件末尾加：

```python
@dataclass
class ObjectMatch:
    """对象标准匹配结果（表→对象）。"""

    object_code: str
    object_id: Optional[int]
    confidence: float
    evidence: Dict


class _ObjMatchHolder:  # 命名空间占位，避免与 RuleEngine 静态方法定义顺序耦合
    pass


#: 内置对象标准（种子）：表级业务对象模板。
BUILTIN_OBJECT_STANDARDS: List[Dict] = [
    {"code": "obj_customer", "name": "客户", "aliases": ["customer", "user", "客户", "会员"], "domain": "客户"},
    {"code": "obj_order", "name": "订单", "aliases": ["order", "orders", "订单"], "domain": "交易"},
    {"code": "obj_product", "name": "商品", "aliases": ["product", "item", "goods", "商品"], "domain": "交易"},
]
```

并在 `RuleEngine` 类内追加静态方法（与 `match_standard` 同结构，去掉 data_type 维度）：

```python
    @staticmethod
    def match_object(table_name: str, comment: Optional[str], object_standards: List[Dict]) -> "Optional[ObjectMatch]":
        """把物理表匹配到对象标准（按 code/name/别名 精确或子串命中）。"""
        haystack = f"{table_name or ''} {(comment or '')}".lower()
        best: Optional[Dict] = None
        best_conf = 0.0
        best_why: List[str] = []
        for s in object_standards:
            conf = 0.0
            why: List[str] = []
            aliases = [str(s.get("code", "")), str(s.get("name", ""))]
            aliases += [str(a) for a in (s.get("aliases") or [])]
            for alias in aliases:
                a = (alias or "").lower().strip()
                if not a:
                    continue
                if a == haystack.strip():
                    conf = max(conf, 0.9)
                    why.append(f"alias_exact:{a}")
                elif a in haystack:
                    conf = max(conf, 0.72)
                    why.append(f"alias_substr:{a}")
            if conf > best_conf:
                best_conf = conf
                best = s
                best_why = why
        if best is None or best_conf < CONF_SUGGEST_MIN:
            return None
        return ObjectMatch(
            object_code=best["code"], object_id=best.get("id"),
            confidence=round(best_conf, 4),
            evidence={"why": best_why, "score": round(best_conf, 4)},
        )
```

删除上面为说明保留的 `_ObjMatchHolder` 占位（不需要它）。

- [ ] **Step 4: 运行 match_object 单测通过**

Run: `pytest tests/dataops/test_table_object_binding.py -k match_object -v`
Expected: PASS

- [ ] **Step 5: 扩展 BindReport + bind_table 三步**

Modify `backend/app/services/dataops/standard_binding_service.py`：

`BindReport` 追加字段：

```python
    objects_bound: int = 0
    objects_updated: int = 0
    objects_skipped_human: int = 0
```

import 追加 ORM 与服务：

```python
from app.ai.dataops.rule_engine import TIER_ACCEPTED, RuleEngine, tier
from app.models.dataops.standard_cdm import (
    MetaObjectStandard, MetaTableStandard, MetaTableStandardHistory,
)
```

在 `bind_table` 里，列循环之后追加表→对象步骤；并新增 `_object_standards()` 与 `_bind_table_object()`：

```python
    def _object_standards(self) -> List[dict]:
        objs = self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id,
                MetaObjectStandard.status == "published",
            )
        ).scalars().all()
        return [{"id": o.id, "code": o.code, "name": o.name, "aliases": o.aliases_json or []} for o in objs]

    def _bind_table_object(self, table: MetaTable, obj_stds: List[dict], report: BindReport) -> None:
        if not obj_stds:
            return
        matched = RuleEngine.match_object(table.table_name, getattr(table, "table_comment", None), obj_stds)
        if matched is None:
            return
        status = tier(matched.confidence)
        if status == "drop":
            return
        existing = self.db.execute(
            select(MetaTableStandard).where(MetaTableStandard.table_id == table.id)
        ).scalar_one_or_none()
        if existing is not None:
            if existing.source == "human" and existing.status == TIER_ACCEPTED:
                report.objects_skipped_human += 1
                report.details.append({"table": table.table_name, "action": "skip_human"})
                return
            existing.object_standard_id = matched.object_id
            existing.confidence = matched.confidence
            existing.evidence_json = matched.evidence
            existing.status = status
            existing.source = "rule"
            action = "bind_update"
            report.objects_updated += 1
        else:
            self.db.add(MetaTableStandard(
                tenant_id=self.tenant_id, table_id=table.id, object_standard_id=matched.object_id,
                confidence=matched.confidence, evidence_json=matched.evidence,
                status=status, source="rule",
            ))
            action = "bind_new"
            report.objects_bound += 1
        self.db.flush()
        self.db.add(MetaTableStandardHistory(
            tenant_id=self.tenant_id, table_id=table.id, object_standard_id=matched.object_id,
            action=action,
            snapshot_json={"object_code": matched.object_code, "confidence": matched.confidence, "status": status},
        ))
        report.details.append({"table": table.table_name, "object": matched.object_code,
                               "confidence": matched.confidence, "status": status, "action": action})
```

在 `bind_table` 末尾 `return report` 前加：

```python
        obj_stds = self._object_standards()
        self._bind_table_object(table, obj_stds, report)
```

- [ ] **Step 6: 集成测试：seed 对象标准 + scan + bind 命中**

追加到 `test_table_object_binding.py`（复用 `test_scan_query_write.py` 的 `scannable` fixture 建表建列方式；若无该 fixture，则用 `db` 手工插 `MetaTable` 行）：

```python
from app.models.dataops.meta import MetaTable
from app.models.dataops.standard_cdm import MetaObjectStandard, MetaTableStandard
from app.services.dataops.standard_binding_service import StandardBindingService
from sqlalchemy import select


def test_bind_table_creates_object_binding(db, engine):
    # 一个 published 对象标准 + 一张物理表
    db.add(MetaObjectStandard(tenant_id=100, code="obj_order", name="订单",
                              aliases_json=["order"], status="published"))
    tbl = MetaTable(tenant_id=100, source_id=1, db_name="d", database="public",
                    table_name="t_order", table_comment="订单表", scan_job_id=None)
    db.add(tbl); db.flush()
    report = StandardBindingService(db, 100).bind_table(tbl.id)
    db.flush()
    assert report.objects_bound == 1
    b = db.execute(select(MetaTableStandard).where(MetaTableStandard.table_id == tbl.id)).scalar_one()
    assert b.status in ("accepted", "suggested")
```

> 若 `MetaTable` 构造必填列与现仓不一致，按 `test_scan_query_write.py` 现有建表代码对齐字段（source_id/database/table_name 等）。

- [ ] **Step 7: 运行 B3 测试**

Run: `pytest tests/dataops/test_table_object_binding.py -v`
Expected: PASS

- [ ] **Step 8: bind 端点返回体补计数**

Modify `dataops.py` `bind_source` 返回 dict 追加：

```python
        "objects_bound": report.objects_bound,
        "objects_updated": report.objects_updated,
        "objects_skipped_human": report.objects_skipped_human,
```

- [ ] **Step 9: 全 dataops 回归 + Commit**

Run: `pytest tests/dataops -q`
Expected: 全绿（无回归）

```bash
git add backend/app/ai/dataops/rule_engine.py backend/app/services/dataops/standard_binding_service.py backend/app/routers/dataops/dataops.py backend/tests/dataops/test_table_object_binding.py
git commit -m "feat(dataops): bind physical tables to object standards via rule channel"
```

---

## 后端 Task B4：关系标准 + 校验 + graph/stats + NL 查询

**Files:**
- Create: `backend/app/services/dataops/object_relation_service.py`
- Modify: `backend/app/services/dataops/standard_binding_service.py`（`_check_relations` 步骤 + `BindReport` 校验计数）
- Create: `backend/app/services/dataops/standard_query_service.py`（graph/stats/nl-query）
- Modify: `backend/app/routers/dataops/dataops.py`（`/standards/relations*`, `/graph`, `/stats`, `/nl-query`）
- Test: `backend/tests/dataops/test_standard_cdm.py`（追加 relation/graph/stats/nl）

**Interfaces:**
- Consumes: `MetaObjectRelation`, `MetaRelationCheck`, `MetaRelation`, `MetaObjectStandard`, `MetaTableStandard`, `llm_json`
- Produces:
  - `MetaObjectRelationService(db, tenant_id)`：`list(catalog_id=None)`, `create(code,name,from_object_id,to_object_id,relation_type,catalog_id=None,via_attribute_ids=None,description=None)`, `update`, `delete`, `serialize`, 跨场景提醒由 `cross_catalog_warning(id)->Optional[str]`
  - `StandardQueryService(db, tenant_id)`：`graph(catalog_id=None)->dict{nodes,edges}`, `stats()->dict`, `nl_query(question, catalog_id=None, model_id=None)->dict`
  - `BindReport` 追加：`relation_checked / hit / missing / conflict`

- [ ] **Step 1: 关系校验三态失败单测**

追加到 `test_standard_cdm.py`（含 hit/missing/conflict 的构造）：

```python
from app.models.dataops.meta import MetaTable
from app.models.dataops.meta_relation import MetaRelation
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaRelationCheck, MetaTableStandard,
)
from app.services.dataops.standard_binding_service import StandardBindingService
from sqlalchemy import select


def _prep(db):
    a = MetaObjectStandard(tenant_id=100, code="obj_a", name="A", aliases_json=[], status="published")
    b = MetaObjectStandard(tenant_id=100, code="obj_b", name="B", aliases_json=[], status="published")
    db.add_all([a, b]); db.flush()
    ta = MetaTable(tenant_id=100, source_id=1, db_name="d", database="public", table_name="t_a", table_comment="", scan_job_id=None)
    tb = MetaTable(tenant_id=100, source_id=1, db_name="d", database="public", table_name="t_b", table_comment="", scan_job_id=None)
    db.add_all([ta, tb]); db.flush()
    db.add_all([
        MetaTableStandard(tenant_id=100, table_id=ta.id, object_standard_id=a.id, status="accepted", source="human"),
        MetaTableStandard(tenant_id=100, table_id=tb.id, object_standard_id=b.id, status="accepted", source="human"),
    ])
    rel = MetaObjectRelation(tenant_id=100, code="rel_ab", name="A到B", from_object_id=a.id,
                             to_object_id=b.id, relation_type="1:N", status="published")
    db.add(rel); db.flush()
    return rel, ta, tb


def test_relation_check_hit_missing_conflict(db, engine):
    rel, ta, tb = _prep(db)
    # hit：存在 A→B 推断关系
    inf = MetaRelation(tenant_id=100, source_id=1, database="public", left_table="t_a", left_column="id",
                       right_table="t_b", right_column="a_id", confidence=0.9, status="accepted", source="rule")
    db.add(inf); db.flush()
    StandardBindingService(db, 100)._check_relations(1, "public")
    db.flush()
    chk = db.execute(select(MetaRelationCheck).where(MetaRelationCheck.standard_relation_id == rel.id)).scalar_one()
    assert chk.verdict == "hit"
    assert chk.inferred_relation_id == inf.id


def test_relation_check_conflict_on_reverse(db, engine):
    rel, ta, tb = _prep(db)
    # conflict：只有 B→A 反方向推断
    inf = MetaRelation(tenant_id=100, source_id=1, database="public", left_table="t_b", left_column="b_id",
                       right_table="t_a", right_column="id", confidence=0.9, status="accepted", source="rule")
    db.add(inf); db.flush()
    StandardBindingService(db, 100)._check_relations(1, "public")
    db.flush()
    chk = db.execute(select(MetaRelationCheck).where(MetaRelationCheck.standard_relation_id == rel.id)).scalar_one()
    assert chk.verdict == "conflict"


def test_relation_check_missing(db, engine):
    rel, ta, tb = _prep(db)
    StandardBindingService(db, 100)._check_relations(1, "public")
    db.flush()
    chk = db.execute(select(MetaRelationCheck).where(MetaRelationCheck.standard_relation_id == rel.id)).scalar_one()
    assert chk.verdict == "missing"
    assert chk.inferred_relation_id is None
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/dataops/test_standard_cdm.py -k relation_check -v`
Expected: FAIL（无 `_check_relations`）

- [ ] **Step 3: 实现 _check_relations（关系校验）+ BindReport 计数**

Modify `standard_binding_service.py`：`BindReport` 追加 `relation_checked: int = 0; hit: int = 0; missing: int = 0; conflict: int = 0`。import 追加：

```python
from app.models.dataops.meta_relation import MetaRelation
from app.models.dataops.standard_cdm import MetaObjectRelation, MetaRelationCheck
```

新增方法（按 (source, database) 全量校验已发布关系，幂等 upsert `meta_relation_check`）：

```python
    def _bound_tables(self, object_id: int, source_id: int, database: str) -> List[str]:
        rows = self.db.execute(
            select(MetaTable.table_name)
            .join(MetaTableStandard, MetaTableStandard.table_id == MetaTable.id)
            .where(MetaTableStandard.object_standard_id == object_id,
                   MetaTable.source_id == source_id,
                   MetaTable.database == database)
        ).all()
        return [r[0] for r in rows]

    def _check_relations(self, source_id: int, database: str) -> None:
        rels = self.db.execute(
            select(MetaObjectRelation).where(
                MetaObjectRelation.tenant_id == self.tenant_id,
                MetaObjectRelation.status == "published",
            )
        ).scalars().all()
        for rel in rels:
            from_tables = self._bound_tables(rel.from_object_id, source_id, database)
            to_tables = self._bound_tables(rel.to_object_id, source_id, database)
            if not from_tables or not to_tables:
                continue  # 任一端未绑定→跳过
            ft = set(from_tables); tt = set(to_tables)
            forward = self.db.execute(select(MetaRelation).where(
                MetaRelation.tenant_id == self.tenant_id, MetaRelation.source_id == source_id,
                MetaRelation.database == database,
                MetaRelation.left_table.in_(ft), MetaRelation.right_table.in_(tt),
            )).scalars().first()
            reverse = self.db.execute(select(MetaRelation).where(
                MetaRelation.tenant_id == self.tenant_id, MetaRelation.source_id == source_id,
                MetaRelation.database == database,
                MetaRelation.left_table.in_(tt), MetaRelation.right_table.in_(ft),
            )).scalars().first()
            if forward is not None:
                verdict, inf_id, conf = "hit", forward.id, forward.confidence
            elif reverse is not None:
                verdict, inf_id, conf = "conflict", reverse.id, reverse.confidence
            else:
                verdict, inf_id, conf = "missing", None, None
            self._upsert_relation_check(rel.id, source_id, database, verdict, inf_id, conf,
                                        {"from_tables": from_tables, "to_tables": to_tables})

    def _upsert_relation_check(self, rel_id, source_id, database, verdict, inf_id, conf, evidence) -> None:
        row = self.db.execute(select(MetaRelationCheck).where(
            MetaRelationCheck.standard_relation_id == rel_id,
            MetaRelationCheck.source_id == source_id,
            MetaRelationCheck.database == database,
        )).scalar_one_or_none()
        if row is None:
            row = MetaRelationCheck(tenant_id=self.tenant_id, standard_relation_id=rel_id,
                                    source_id=source_id, database=database)
            self.db.add(row)
        row.verdict = verdict
        row.inferred_relation_id = inf_id
        row.confidence = conf
        row.evidence_json = evidence
        self.db.flush()
```

- [ ] **Step 4: bind_source 调用校验 + 运行 B4 校验测试**

在 `bind_source` 遍历 tables 之后、`return report` 前加（若 `database` 为空按 source 下各库或跳过；本仓 `bind_source(source_id, database)` 有 database 时才校验，否则遍历去重库名）：

```python
        for db_name in self._source_databases(source_id, database):
            before = self.db
            self._check_relations(source_id, db_name)
        # 统计各 verdict
        self._tally_relation_verdicts(report, source_id, database)
```

> `_source_databases` / `_tally_relation_verdicts` 为薄封装：前者返回目标库列表（显式 database 或 distinct `MetaTable.database`），后者 `select(func.count).group_by(MetaRelationCheck.verdict)` 填 `report.relation_checked/hit/missing/conflict`。实现时给出具体查询，不用占位。

Run: `pytest tests/dataops/test_standard_cdm.py -k relation_check -v`
Expected: PASS

- [ ] **Step 5: 关系标准服务 + CRUD 路由**

Create `backend/app/services/dataops/object_relation_service.py`（`MetaObjectRelationService`，结构同 object 服务：get_or_404/_by_code/list/create/update/delete/serialize；create 校验 from/to 对象存在且同租户；`cross_catalog_warning(rel_id)` 比较两端对象 `catalog_id` 是否同子树，不同返回提示串）。delete 保护：`meta_relation_check` CASCADE，无需额外校验。

在 `dataops.py` 加端点（`RelationCreate/RelationUpdate/`），镜像 objects 端点的 try/commit/except 映射：

```
GET  /standards/relations?catalog_id=
POST /standards/relations            → 201
PUT  /standards/relations/{id}
DELETE /standards/relations/{id}     → 409 on RESTRICT
```

create 成功响应额外带 `warning`（跨场景软提醒，不阻断）。

- [ ] **Step 6: graph/stats/nl-query 服务 + 路由**

Create `backend/app/services/dataops/standard_query_service.py`：

```python
"""标准中心只读查询 + NL 检索（B4）。graph/stats 纯聚合；nl_query 复用 llm_json。"""
from __future__ import annotations
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaRelationCheck,
)


class StandardQueryService:
    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("StandardQueryService 要求 tenant_id")
        self.db = db
        self.tenant_id = tenant_id

    def graph(self, catalog_id: Optional[int] = None) -> dict:
        ostmt = select(MetaObjectStandard).where(MetaObjectStandard.tenant_id == self.tenant_id)
        if catalog_id is not None:
            ostmt = ostmt.where(MetaObjectStandard.catalog_id == catalog_id)
        objs = list(self.db.execute(ostmt).scalars().all())
        obj_ids = {o.id for o in objs}
        nodes = [{"id": o.id, "code": o.code, "name": o.name, "catalog_id": o.catalog_id} for o in objs]
        rstmt = select(MetaObjectRelation).where(MetaObjectRelation.tenant_id == self.tenant_id)
        if catalog_id is not None:
            rstmt = rstmt.where(MetaObjectRelation.catalog_id == catalog_id)
        edges = []
        for r in self.db.execute(rstmt).scalars().all():
            if r.from_object_id in obj_ids and r.to_object_id in obj_ids:
                edges.append({"id": r.id, "code": r.code, "from": r.from_object_id,
                              "to": r.to_object_id, "relation_type": r.relation_type})
        return {"nodes": nodes, "edges": edges}

    def stats(self) -> dict:
        obj_count = self.db.execute(select(func.count()).select_from(MetaObjectStandard)
                                    .where(MetaObjectStandard.tenant_id == self.tenant_id)).scalar()
        rel_count = self.db.execute(select(func.count()).select_from(MetaObjectRelation)
                                    .where(MetaObjectRelation.tenant_id == self.tenant_id)).scalar()
        verdicts = dict(self.db.execute(
            select(MetaRelationCheck.verdict, func.count())
            .where(MetaRelationCheck.tenant_id == self.tenant_id)
            .group_by(MetaRelationCheck.verdict)
        ).all())
        return {
            "objects": obj_count, "relations": rel_count,
            "relation_check": {
                "hit": verdicts.get("hit", 0),
                "missing": verdicts.get("missing", 0),
                "conflict": verdicts.get("conflict", 0),
            },
        }

    async def nl_query(self, question: str, catalog_id: Optional[int] = None,
                       model_id: Optional[int] = None) -> dict:
        from app.ai.research.llm import llm_json
        g = self.graph(catalog_id)
        compact = {"objects": [{"code": n["code"], "name": n["name"]} for n in g["nodes"]],
                   "relations": [{"code": e["code"], "from": e["from"], "to": e["to"]} for e in g["edges"]]}
        # 用 id→code 反查，edges 里的 from/to 需映射回 code（实现时构建 id2code）
        prompt = (
            "你是元数据治理助手。给定标准图谱(对象/关系)与用户问题，"
            "返回 JSON：{highlight_object_codes:[], highlight_relation_codes:[], "
            "focus_catalog_code:(可空), summary:(中文一句话)}。只输出 JSON。\n"
            f"图谱：{compact}\n问题：{question}"
        )
        try:
            data = await llm_json(prompt, model_id=model_id)
        except Exception as exc:  # noqa: BLE001 降级不 500
            return {"degraded": True, "error": str(exc),
                    "highlight_object_codes": [], "highlight_relation_codes": [],
                    "focus_catalog_code": None, "summary": "AI 检索暂不可用"}
        data["degraded"] = False
        return data
```

> `edges` 的 from/to 为对象 id；prompt 里需换成 code。实现时先建 `id2code` 映射，compact.relations 用 code。此步不省略。

路由：

```
GET  /standards/graph?catalog_id=        → {nodes, edges}
GET  /standards/stats                    → stats dict
POST /standards/nl-query  {question, catalog_id?} → nl_query 结果（async handler）
```

- [ ] **Step 7: graph/stats/nl 路由测试**

追加到 `test_standard_cdm.py`（NL 用 monkeypatch 打桩 `app.ai.research.llm.llm_json`）：

```python
import asyncio


def test_graph_and_stats_routes(client_a, db):
    from app.services.dataops.standard_service import MetaStandardService
    MetaStandardService(db, 100).create("a1", "列1")
    client_a.post("/api/v1/dataops/standards/objects", json={"code": "g_o1", "name": "对象1"})
    g = client_a.get("/api/v1/dataops/standards/graph").json()
    assert any(n["code"] == "g_o1" for n in g["nodes"])
    s = client_a.get("/api/v1/dataops/standards/stats").json()
    assert s["objects"] >= 1 and "relation_check" in s


def test_nl_query_degrades_without_llm(client_a, db, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("no llm")
    monkeypatch.setattr("app.ai.research.llm.llm_json", boom)
    r = client_a.post("/api/v1/dataops/standards/nl-query", json={"question": "有哪些客户相关对象"})
    assert r.status_code == 200
    assert r.json()["degraded"] is True
```

Run: `pytest tests/dataops/test_standard_cdm.py -v`
Expected: PASS

- [ ] **Step 8: 全 dataops 回归 + Commit**

Run: `pytest tests/dataops -q`
Expected: 全绿

```bash
git add backend/app/services/dataops/object_relation_service.py backend/app/services/dataops/standard_query_service.py backend/app/services/dataops/standard_binding_service.py backend/app/routers/dataops/dataops.py backend/tests/dataops/test_standard_cdm.py
git commit -m "feat(dataops): relation standards, relation check, graph/stats and NL query"
```

---

<!-- 前端 F1–F3 见下节 -->

---

## 前端 Task F1：API 客户端 + 目录树 + 对象 CRUD（先 CRUD，无图）

**Files:**
- Modify: `frontend/src/api/dataops.ts`
- Create: `frontend/src/views/data-source/standard/StdCatalogTree.vue`
- Create: `frontend/src/views/data-source/standard/ObjectFormModal.vue`
- Modify: `frontend/src/views/data-source/StandardManagement.vue`（先接目录树+对象列表，保留属性页签）
- Test: `frontend/src/views/data-source/standard/__tests__/StdCatalogTree.spec.ts`

**Interfaces:**
- Consumes: 后端 `/standards/catalogs*`, `/standards/objects*`（B2）
- Produces: `api.dataops` 新增：`listCatalogs()`, `createCatalog(b)`, `updateCatalog(id,b)`, `moveCatalog(id,parentId)`, `deleteCatalog(id)`, `listObjects(catalogId?)`, `createObject(b)`, `getObject(id)`, `updateObject(id,b)`, `deleteObject(id)`, `setObjectAttributes(id, items)`

- [ ] **Step 1: 写 API 函数**

Modify `frontend/src/api/dataops.ts`（沿用 `request` + `BASE` 现有风格）：

```typescript
// 目录/对象/关系/图/统计/NL
export function listCatalogs() { return request.get(`${BASE}/standards/catalogs`) }
export function createCatalog(body: any) { return request.post(`${BASE}/standards/catalogs`, body) }
export function updateCatalog(id: number, body: any) { return request.put(`${BASE}/standards/catalogs/${id}`, body) }
export function moveCatalog(id: number, parentId: number | null) { return request.put(`${BASE}/standards/catalogs/${id}/move`, { parent_id: parentId }) }
export function deleteCatalog(id: number) { return request.delete(`${BASE}/standards/catalogs/${id}`) }

export function listObjects(catalogId?: number) { return request.get(`${BASE}/standards/objects`, { params: { catalog_id: catalogId } }) }
export function getObject(id: number) { return request.get(`${BASE}/standards/objects/${id}`) }
export function createObject(body: any) { return request.post(`${BASE}/standards/objects`, body) }
export function updateObject(id: number, body: any) { return request.put(`${BASE}/standards/objects/${id}`, body) }
export function deleteObject(id: number) { return request.delete(`${BASE}/standards/objects/${id}`) }
export function setObjectAttributes(id: number, items: any[]) { return request.put(`${BASE}/standards/objects/${id}/attributes`, { items }) }
```

- [ ] **Step 2: 写 StdCatalogTree 组件**

Create `frontend/src/views/data-source/standard/StdCatalogTree.vue`：

```vue
<template>
  <div class="std-tree">
    <a-tree
      v-if="treeData.length"
      :tree-data="treeData"
      :field-names="{ title: 'name', key: 'id', children: 'children' }"
      default-expand-all
      @select="onSelect"
    />
    <a-empty v-else :description="t('kbMgmt.catalog.empty')" />
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api/dataops'

const { t } = useI18n()
const treeData = ref<any[]>([])
const emit = defineEmits<{ (e: 'select', catalogId: number | null): void }>()

async function load() {
  const r: any = await api.listCatalogs()
  treeData.value = r.data || r || []
}
function onSelect(keys: (string | number)[]) {
  emit('select', keys.length ? Number(keys[0]) : null)
}
defineExpose({ load })
onMounted(load)
</script>
```

- [ ] **Step 3: 写树渲染快照测（vitest）**

Create `frontend/src/views/data-source/standard/__tests__/StdCatalogTree.spec.ts`：

```typescript
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import StdCatalogTree from '../StdCatalogTree.vue'
vi.mock('@/api/dataops', () => ({
  listCatalogs: vi.fn().mockResolvedValue({ data: [{ id: 1, name: '电商场景', children: [] }] }),
}))
describe('StdCatalogTree', () => {
  it('renders catalog nodes', async () => {
    const w = mount(StdCatalogTree, { global: { mocks: { $t: (k: string) => k } } })
    await new Promise((r) => setTimeout(r, 0))
    expect(w.html()).toContain('电商场景')
  })
})
```

Run: `npx vitest run src/views/data-source/standard/__tests__/StdCatalogTree.spec.ts`
Expected: 先 FAIL（组件不存在），实现后 PASS

- [ ] **Step 4: ObjectFormModal + StandardManagement 接线**

ObjectFormModal 用 `a-form`（code/name/catalog_id/aliases/domain/description + 引用属性多选）；StandardManagement 暂为 `a-layout`：左 `<StdCatalogTree @select="onCatalogSelect"/>`，右对象表格（`listObjects(catalogId)`）+ 新建/编辑。保留现有属性 CRUD 作为单独 `a-tab-pane`。

- [ ] **Step 5: 手动跑通 + Commit**

Run: `npm run build`（或 dev）无错；目录树选中→右侧过滤对象。

```bash
git add frontend/src/api/dataops.ts frontend/src/views/data-source/standard/StdCatalogTree.vue frontend/src/views/data-source/standard/ObjectFormModal.vue frontend/src/views/data-source/StandardManagement.vue frontend/src/views/data-source/standard/__tests__/StdCatalogTree.spec.ts
git commit -m "feat(frontend): standard center catalog tree and object CRUD"
```

---

## 前端 Task F2：ECharts 图窗体 + 检视面板 + 下钻

**Files:**
- Create: `frontend/src/views/data-source/standard/StdGraphView.vue`
- Create: `frontend/src/views/data-source/standard/StdInspector.vue`
- Create: `frontend/src/views/data-source/standard/RelationFormModal.vue`
- Modify: `frontend/src/views/data-source/StandardManagement.vue`（中央图 + 右检视 + 视图切换）
- Modify: `frontend/src/views/data-source/DataSourcePanel.vue`（接 `@drill-down`）
- Modify: `frontend/src/api/dataops.ts`（graph/relations）
- Test: `frontend/src/views/data-source/standard/__tests__/StdGraphView.spec.ts`

**Interfaces:**
- Consumes: `GET /standards/graph`, `GET/POST/PUT/DELETE /standards/relations`（B4）
- Produces: `listGraph(catalogId?)`, `listRelations(catalogId?)`, `createRelation(b)`, `updateRelation(id,b)`, `deleteRelation(id)`; `StdGraphView` props `nodes/edges`, emit `node-click`/`edge-click`; `StdInspector` props `selected`, emit `drill-down({source_id, database, table})`

- [ ] **Step 1: API 补充**

```typescript
export function listGraph(catalogId?: number) { return request.get(`${BASE}/standards/graph`, { params: { catalog_id: catalogId } }) }
export function listRelations(catalogId?: number) { return request.get(`${BASE}/standards/relations`, { params: { catalog_id: catalogId } }) }
export function createRelation(body: any) { return request.post(`${BASE}/standards/relations`, body) }
export function updateRelation(id: number, body: any) { return request.put(`${BASE}/standards/relations/${id}`, body) }
export function deleteRelation(id: number) { return request.delete(`${BASE}/standards/relations/${id}`) }
```

- [ ] **Step 2: StdGraphView（ECharts graph）**

Create `StdGraphView.vue`，用 `vue-echarts`：

```vue
<template>
  <v-chart class="std-graph" :option="option" autoresize @click="onClick" />
</template>
<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
use([GraphChart, CanvasRenderer])

const props = defineProps<{ nodes: any[]; edges: any[] }>()
const emit = defineEmits<{ (e: 'node-click', id: number): void; (e: 'edge-click', id: number): void }>()

const option = computed(() => ({
  series: [{
    type: 'graph', layout: 'force', roam: true, draggable: true,
    label: { show: true, formatter: (p: any) => p.name },
    edgeLabel: { show: true, formatter: (p: any) => p.data.relation_type },
    force: { repulsion: 240, edgeLength: 120 },
    data: props.nodes.map((n) => ({ id: String(n.id), name: n.name, symbolSize: 48 })),
    links: props.edges.map((e) => ({ source: String(e.from), target: String(e.to), relation_type: e.relation_type, edgeId: e.id })),
  }],
}))
function onClick(p: any) {
  if (p.dataType === 'node') emit('node-click', Number(p.data.id))
  else if (p.dataType === 'edge') emit('edge-click', p.data.edgeId)
}
</script>
<style scoped>.std-graph { width: 100%; height: 100%; }</style>
```

- [ ] **Step 3: StdInspector + 下钻**

`StdInspector.vue`：点对象 → `getObject(id)` 显示表定义含属性列表（`attributes`）；若该行有已绑定物理表（来自表→对象绑定查询/对象详情扩展字段），“下钻”按钮 `emit('drill-down', { source_id, database, table })`。点边 → 显示关系定义 + 该关系在各 source 的校验结论（hit/missing/conflict，来自 `listRelations` 携带的 check 或单独接口）。

> 若需关系校验明细，扩展 `GET /standards/relations` 返回体带最近 check 汇总，或新增 `GET /standards/relations/{id}/checks`（本任务内实现接口，前端消费）。

- [ ] **Step 4: StandardManagement 接线 + DataSourcePanel drill 事件**

中央顶部 `[图视图 | 总览]` `a-segmented`（总览先占位，F3 实现）；图视图放 `StdGraphView`，监听 `node-click/edge-click` 设 selected → 右 `StdInspector`。`StandardManagement` 向父 `emit('drill-down', payload)`；`DataSourcePanel.vue` 给 `<StandardManagement @drill-down="onDrillDown" />`，`onDrillDown` 将 `active='metadata'` 并把 source/scope 透给 `MetadataExplorer`（复用其现有 prop/状态）。

- [ ] **Step 5: 图测（渲染 nodes/edges）**

`__tests__/StdGraphView.spec.ts`：mock vue-echarts，断言传入 option.series[0].data 长度与 props.nodes 一致。Run: `npx vitest run`，先 FAIL 后 PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/dataops.ts frontend/src/views/data-source/standard/StdGraphView.vue frontend/src/views/data-source/standard/StdInspector.vue frontend/src/views/data-source/standard/RelationFormModal.vue frontend/src/views/data-source/StandardManagement.vue frontend/src/views/data-source/DataSourcePanel.vue frontend/src/views/data-source/standard/__tests__/StdGraphView.spec.ts
git commit -m "feat(frontend): ECharts standard graph, inspector and datasource drill-down"
```

---

## 前端 Task F3：总览视图（统计 + NL 查询）+ 建模导览

**Files:**
- Create: `frontend/src/views/data-source/standard/StdOverviewView.vue`
- Create: `frontend/src/views/data-source/standard/StdGuidTour.vue`
- Modify: `frontend/src/api/dataops.ts`（stats/nlQuery）
- Modify: `frontend/src/views/data-source/StandardManagement.vue`（总览接线 + NL→高亮 + 导览步骤条）
- Modify: i18n locale files（`kbMgmt.catalog.*` / `kbMgmt.graph.*` / `kbMgmt.overview.*` / `kbMgmt.tour.*`）
- Test: `frontend/src/views/data-source/standard/__tests__/StdOverviewView.spec.ts`

**Interfaces:**
- Consumes: `GET /standards/stats`, `POST /standards/nl-query`（B4）
- Produces: `getStats()`, `nlQuery(question, catalogId?)`; StdOverviewView emit `focus({ highlight_object_codes, highlight_relation_codes, focus_catalog_code, summary })`; NL 降级（`degraded:true`）时提示不阻断

- [ ] **Step 1: API 补充**

```typescript
export function getStats() { return request.get(`${BASE}/standards/stats`) }
export function nlQuery(question: string, catalogId?: number) { return request.post(`${BASE}/standards/nl-query`, { question, catalog_id: catalogId }) }
```

- [ ] **Step 2: StdOverviewView**

统计卡片（objects/relations 数 + hit/missing/conflict）+ 一个小 ECharts 柱状（校验三态分布）+ `a-input-search` NL 查询框；提交调 `nlQuery`，`degraded` 则 `message.warning` 并仍 emit 空高亮；成功 emit `focus`（code 列表 + summary）。

- [ ] **Step 3: StandardManagement 接线**

总览 `focus` → 切回图视图、按 code 在 `nodes/edges` 中标高亮（ECharts emphasis/焦点样式）+ 右面板显 summary。

- [ ] **Step 4: StdGuidTour 轻量步骤条**

`a-steps` 静态项：建目录→定义对象→挂属性→连关系→绑定→看统计；当前步高亮，“下一步”只滚动/提示对应区域，不做 gamified 徽章。

- [ ] **Step 5: i18n + 测**

向中英 locale 补 key；`StdOverviewView.spec.ts` mock `getStats`/`nlQuery`，断言卡片文案与 degraded 提示。Run: `npx vitest run`。

- [ ] **Step 6: 构建 + 全前端测 + Commit**

Run: `npm run build`；`npx vitest run src/views/data-source/standard`
Expected: 无错

```bash
git add frontend/src/api/dataops.ts frontend/src/views/data-source/standard/StdOverviewView.vue frontend/src/views/data-source/standard/StdGuidTour.vue frontend/src/views/data-source/StandardManagement.vue frontend/src/locales
git commit -m "feat(frontend): standard overview with stats and NL query, guided tour"
```

---

## 验收标准

- 后端 `pytest tests/dataops -q` 全绿（含新增 B1-B4 测）；`alembic upgrade head`/`downgrade -1` 往返无错。
- 前端 `npm run build` 通过；`src/views/data-source/standard` vitest 全绿。
- 手工：建目录→定义对象(挂属性)→连关系→绑定数据源→图窗体看到节点/边→点选显详情→总览看统计与 NL 高亮。
- 旧属性页签、列绑定、关系推断行为不回退。
