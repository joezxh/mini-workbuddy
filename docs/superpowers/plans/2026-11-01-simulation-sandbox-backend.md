# 推演沙盘 · 沙箱域后端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地推演沙盘 MVP 的沙箱域后端：9 张新表 + 确定性 Tick 引擎 + S1–S21 API + 只读 AI 顾问，全程不写生产本体/数据。

**Architecture:** 沙箱域（`onto_sandbox_*`）与生产域（`onto_ontology*`/`meta_*`）物理分表；世界状态从已发布本体版本的映射下推只读 SQL 克隆一次（脱敏在 SELECT 层以 `'***'` 字面量替换，明文不出源库）；推演由确定性引擎（受控 AST 求值 + 固定顺序 + Decimal）逐 Tick 计算并落观察时序；AI 顾问走"确定性证据收集 + LLM 解释"，零写权限。

**Tech Stack:** Python / FastAPI / SQLAlchemy（PostgreSQL + JSONB）/ Alembic / pytest（per-schema 隔离，复用 `tests/ontology/conftest.py` 模式）/ `app.ai.research.llm.llm_json`。

**Spec:** `docs/superpowers/specs/2026-11-01-simulation-sandbox-design.md`（四项裁决 V1–V4、§3 数据模型、§4 API、§10 验收断言 A1–A8 随本计划执行）

## Global Constraints

每任务隐含遵守，值逐字抄自 spec：

- 沙箱域例外物化（V1）：任何代码不得写 `onto_ontology*`、`meta_*` 表，不得对源库发非只读 SQL；克隆唯一入口 `ReadonlyQueryService.run`。
- 确定性（V2/A1）：引擎求值顺序固定（同层按 `element.code` 字典序）、数值一律 `Decimal`（字符串入、`str` 出，量化 4 位小数 `quantize(Decimal("0.0001"))`）、禁止 `eval`/`exec`/任意代码执行。
- D3 防线（V2/A8）：`origin='llm'` 的 element 只能 `status='suggested'`；引擎只加载 `status='accepted'` 元素。
- 行动不落模式层（V3）：行动仅引用 `onto_action_template`；被否目标返回 `denied` 且**必须**落 `onto_sandbox_action` 审计。
- 脱敏在克隆期落盘（V4/A3）：`MetaStandard.mask_rule` 非空或 `MetaColumn.pii_level == 'L3'` 的映射列，SELECT 列表中以 `'***' AS <col>` 替换并记入 `masked_columns[]`，明文不出源库；实体置 `masked=true`。
- 检查点上限：**场景级合计 5**（含克隆完成时自动创建的 Tick0 基线快照，占 1 格，对齐原型「检查点 1/5」）。
- 克隆上限默认：`max_entities=500`、`max_relations=2000`（场景可配，硬顶 5000/20000）。
- 表名单数、`TenantMixin`、状态 `String` + comment 枚举、审计列 `creator_id/created_at/updated_at`（服务构造无 `tenant_id` 直接 `raise ValueError`，与既有服务同纪律）。
- API 路径前缀 `/ontologies/sandbox`（在 dataops 父 router 下注册，最终 `/api/v1/dataops/ontologies/sandbox/...`）；路由风格抄 `backend/app/routers/ontology/ontology.py`（无 prefix、全路径声明、`_get_service(db, current_user)`）。
- 迁移：文件命名 `2026_11_01_0011_add_sandbox_tables.py`，`down_revision = "2026_11_01_0010_add_source_external_type"`。
- 测试：`backend/tests/sandbox/`，跑法 `cd backend && python -m pytest tests/sandbox -v`（需要 `.env` 配置的 PostgreSQL 测试库 `minworkbuddy_test`，conftest 自建）。

## File Structure（本计划落定的文件地图）

| 文件 | 动作 | 职责 |
|---|---|---|
| `backend/app/models/sandbox/__init__.py` | Create | 导出模型类 |
| `backend/app/models/sandbox/sandbox.py` | Create | 8 张 `onto_sandbox_*` 表模型 |
| `backend/app/models/sandbox/action_template.py` | Create | 平台级 `onto_action_template`（无 TenantMixin） |
| `backend/app/db/init_models.py` | Modify | 注册 sandbox 模型 import（照 onto 段注释风格） |
| `backend/alembic/versions/2026_11_01_0011_add_sandbox_tables.py` | Create(autogenerate+seed) | 建 9 表 + 4 条模板种子 |
| `backend/app/services/sandbox/__init__.py` | Create | — |
| `backend/app/services/sandbox/ast_eval.py` | Create | 受控 AST 求值器（纯函数） |
| `backend/app/services/sandbox/sandbox_scene_service.py` | Create | 场景生命周期 + 校验钉版 |
| `backend/app/services/sandbox/sandbox_clone_service.py` | Create | 克隆计划 + 下推取数（fetcher 注入）+ 基线检查点 |
| `backend/app/services/sandbox/sandbox_engine_service.py` | Create | `load_world/run_tick/advance/preview_future/checkpoint/replay/branch/compare` |
| `backend/app/services/sandbox/sandbox_element_service.py` | Create | element CRUD + review + llm-draft |
| `backend/app/services/sandbox/sandbox_action_service.py` | Create | 门禁求值 + 两段式确认 + 审计 |
| `backend/app/services/sandbox/sandbox_advisor_service.py` | Create | 只读证据三法 + LLM 解释（S20） |
| `backend/app/routers/sandbox/__init__.py` / `sandbox.py` | Create | S1–S21 端点 |
| `backend/app/routers/dataops/dataops.py` | Modify | `include_router(sandbox_router)`（紧跟 ontology_router 那行） |
| `backend/app/core/api_error.py` | Modify | 9 个新错误码常量 |
| `backend/tests/sandbox/conftest.py` | Create | 仿 `tests/ontology/conftest.py` |
| `backend/tests/sandbox/test_*.py` | Create | 各任务测试（任务内列出） |

**MVP 决策记录（对 spec 的两处收口，执行者无需再决策）：**
1. 克隆脱敏采用 **SELECT 层 `'***'` 字面量替换**（spec §4.1 原文允许"无 mask_rule 整列 '***'"；统一为无论有无规则都不出明文，比 SQL 包裹函数更强且免方言函数依赖）。
2. S20 顾问采用**确定性证据收集 + LLM 解释**（固定调用三个只读证据法，非 LLM 自主 tool-calling）——spec §8 MVP"S20 最小工具面"的落地形态；动态 tool-calling 回路列 P1。

---

### Task 1: 沙箱域数据模型 + 迁移 + 种子模板

**Files:**
- Create: `backend/app/models/sandbox/__init__.py`
- Create: `backend/app/models/sandbox/sandbox.py`
- Create: `backend/app/models/sandbox/action_template.py`
- Modify: `backend/app/db/init_models.py`（在第 84-89 行 onto 注册段之后追加）
- Create: `backend/alembic/versions/2026_11_01_0011_add_sandbox_tables.py`
- Create: `backend/tests/sandbox/__init__.py`、`backend/tests/sandbox/conftest.py`
- Test: `backend/tests/sandbox/test_models.py`

**Interfaces:**
- Consumes: 无（起点）
- Produces: ORM 类 `SandboxScene/SandboxBranch/SandboxCheckpoint/SandboxEntity/SandboxRelation/SandboxElement/SandboxAction/SandboxObservation/SandboxActionTemplate` 及全部列名（后续任务的唯一字段真源）；pytest fixtures `db/client_a/client_b/TENANT_A=100/TENANT_B=200`

- [ ] **Step 1: 写模型文件 `sandbox.py`（全文照录）**

```python
"""沙箱域 8 表（spec 2026-11-01-simulation-sandbox-design.md §3.1-§3.8）。

约定（与 app/models/ontology/ontology.py 同纪律）：TenantMixin、表名单数、
状态 String + comment、审计列；onto_sandbox_* 与生产域 onto_ontology* 物理分表，
本文件所有模型的任何写路径都不构成对生产表的写（V1 红线，验收 A7）。
"""
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, Float, ForeignKey, Index,
    Integer, String, Text, TIMESTAMP, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class SandboxScene(Base, TenantMixin):
    """推演场景（沙盘实例，spec §3.1）。"""

    __tablename__ = "onto_sandbox_scene"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False,
        comment="世界来源本体（只读引用）",
    )
    ontology_version = Column(Integer, nullable=False, comment="钉住的已发布版本")
    name = Column(String(200), nullable=False, comment="场景名")
    clone_scope_json = Column(
        JSONB, nullable=True,
        comment="{object_codes[],relation_codes[],max_entities,max_relations}",
    )
    exec_mode = Column(
        String(16), nullable=False, server_default="auto",
        comment="auto|stepwise|replay（语义 spec §5.4）",
    )
    tick_now = Column(Integer, nullable=False, server_default="0", comment="基线分支推进位")
    tick_max = Column(Integer, nullable=False, server_default="12", comment="推演窗口上限")
    status = Column(
        String(16), nullable=False, server_default="draft",
        comment="draft|cloning|running|completed|failed|archived",
    )
    clone_stats_json = Column(JSONB, nullable=True, comment="克隆统计 {entities,relations,masked_columns[]}")
    error_detail = Column(Text, nullable=True, comment="克隆失败摘要（≤2000）")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        CheckConstraint("exec_mode IN ('auto','stepwise','replay')", name="ck_sandbox_scene_exec_mode"),
        CheckConstraint(
            "status IN ('draft','cloning','running','completed','failed','archived')",
            name="ck_sandbox_scene_status",
        ),
        Index("idx_sandbox_scene_tenant_ontology_status", "tenant_id", "ontology_id", "status"),
    )


class SandboxBranch(Base, TenantMixin):
    """分支（平行世界线，spec §3.2）。"""

    __tablename__ = "onto_sandbox_branch"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    name = Column(String(200), nullable=False, comment="分支名")
    color = Column(String(16), nullable=True, comment="画布色")
    base_checkpoint_id = Column(
        BigInteger, ForeignKey("onto_sandbox_checkpoint.id", ondelete="SET NULL"), nullable=True,
        comment="空=基线分支；非空=检查点派生",
    )
    tick_now = Column(Integer, nullable=False, server_default="0", comment="分支推进位（真源）")
    status = Column(String(16), nullable=False, server_default="active", comment="active|sealed")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        CheckConstraint("status IN ('active','sealed')", name="ck_sandbox_branch_status"),
        UniqueConstraint("scene_id", "name", name="uq_sandbox_branch_name"),
        Index("idx_sandbox_branch_scene", "scene_id"),
    )


class SandboxCheckpoint(Base, TenantMixin):
    """检查点（不可变世界快照，场景级合计上限 5，spec §3.3）。"""

    __tablename__ = "onto_sandbox_checkpoint"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    branch_id = Column(
        BigInteger, ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False, comment="来源分支"
    )
    tick = Column(Integer, nullable=False, comment="快照时点")
    seq = Column(Integer, nullable=False, server_default="0", comment="场景内序号（基线=0）")
    label = Column(String(200), nullable=False, comment="展示名，如 T5 快照")
    stats_json = Column(JSONB, nullable=True, comment="{entities,relations,kpi{}} 摘要")
    creator_id = Column(BigInteger, nullable=True, comment="创建者（基线自动快照=NULL）")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_sandbox_checkpoint_scene", "scene_id", "tick"),
        Index("idx_sandbox_checkpoint_branch", "branch_id"),
    )


class SandboxEntity(Base, TenantMixin):
    """世界实体行（当前态 checkpoint_id IS NULL；快照行非空，spec §3.4）。"""

    __tablename__ = "onto_sandbox_entity"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    branch_id = Column(
        BigInteger, ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False, comment="分支"
    )
    checkpoint_id = Column(
        BigInteger, ForeignKey("onto_sandbox_checkpoint.id", ondelete="CASCADE"), nullable=True,
        comment="NULL=当前态行；非空=检查点快照行",
    )
    entity_code = Column(String(64), nullable=False, comment="沙箱代理键（SUP006 等，不暴露源库主键）")
    object_code = Column(String(200), nullable=False, comment="本体对象 code（逻辑引用，不建 FK）")
    props_json = Column(JSONB, nullable=False, server_default="{}", comment="属性载荷（数值一律字符串）")
    risk_score = Column(Float, nullable=False, server_default="0", comment="风险分 0~1")
    masked = Column(Boolean, nullable=False, server_default="false", comment="存在脱敏列（门禁输入）")
    source_ref_json = Column(
        JSONB, nullable=True, comment="{source_id,db,table,pk} 仅展示；禁止据此回查/回写（V1）"
    )
    origin = Column(String(8), nullable=False, server_default="clone", comment="clone|derived（引擎派生事件）")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        CheckConstraint("origin IN ('clone','derived')", name="ck_sandbox_entity_origin"),
        Index("uq_sandbox_entity_current", "branch_id", "entity_code", unique=True,
              postgresql_where=text("checkpoint_id IS NULL")),
        Index("uq_sandbox_entity_snapshot", "checkpoint_id", "entity_code", unique=True,
              postgresql_where=text("checkpoint_id IS NOT NULL")),
        Index("idx_sandbox_entity_scene_object", "scene_id", "object_code"),
    )
```

> 注意：上方 `SandboxEntity.__table_args__` 已按 spec §3.4 的"当前态唯一 + 快照唯一"两段式写成两个**部分唯一索引**（`postgresql_where=text(...)`，故文件头 sqlalchemy import 含 `text`）。

继续在同文件追加 `SandboxRelation/SandboxElement/SandboxAction/SandboxObservation`（列与 spec §3.5–§3.8 一一对应，风格同上）：

- `SandboxRelation`（表 `onto_sandbox_relation`）：`scene_id/branch_id/checkpoint_id` 同 Entity 三件套；`rel_code`（分支内唯一，含快照两段式部分唯一索引，规则同 Entity）、`link_type_code`、`from_entity_code`、`to_entity_code`、`props_json`、`origin` CHECK `IN ('clone','causal')`。
- `SandboxElement`（表 `onto_sandbox_element`）：`scene_id`、`kind` CHECK `IN ('causal_edge','rule','goal','future_event')`、`code`（`uq (scene_id,kind,code)`）、`label`、`from_ref`/`to_ref`（String(64) 可空）、`condition_expr_json`/`effect_expr_json`（JSONB 可空）、`activation_tick`（Integer 可空）、`origin` CHECK `IN ('rule','llm','human')`、`status` CHECK `IN ('suggested','accepted','rejected')`、`confidence` Float 可空；索引 `(scene_id,status)`、`(scene_id,origin,status)`。
- `SandboxAction`（表 `onto_sandbox_action`）：`scene_id`、`branch_id`、`tick`、`template_code` String(64)、`target_entity_code` String(64)、`params_json` JSONB、`gate_result` CHECK `IN ('allowed','denied','pending')`、`gate_reason` String(64) 可空、`confirm_token` String(64) 可空、`operator_id`、`created_at`；索引 `(scene_id, branch_id, tick)`。
- `SandboxObservation`（表 `onto_sandbox_observation`）：`scene_id`、`branch_id`、`tick`、`kind` CHECK `IN ('observation','kpi_point','risk_point','rule_fired','goal_eval','action_effect','event_fired','edge_fired','deadline_missed')`、`severity` CHECK `IN ('info','warn','err')`、`title` String(200)、`detail_json` JSONB、`source` CHECK `IN ('engine','advisor')`；索引 `(branch_id, tick, kind)`。

- [ ] **Step 2: 写 `action_template.py`（平台级，无 TenantMixin）**

```python
class SandboxActionTemplate(Base):
    """内置行动模板（spec §3.9；平台级种子，P2 才评估租户化）。"""

    __tablename__ = "onto_action_template"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    code = Column(String(64), nullable=False, comment="supply_cut|delay|price_up|reroute")
    name = Column(String(200), nullable=False, comment="展示名")
    description = Column(Text, nullable=True, comment="说明")
    domain_hint = Column(String(64), nullable=True, comment="适用域提示（如 supply_chain）")
    param_schema_json = Column(JSONB, nullable=False, comment="F7 表单参数 schema")
    effect_spec_json = Column(JSONB, nullable=False,
                              comment='{"fire_delay_tick":1,"writes":[{"entity":"<target>","prop":"...","expr":{...}}]}')
    status = Column(String(16), nullable=False, server_default="enabled", comment="enabled|disabled")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("code", name="uq_action_template_code"),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_action_template_status"),
    )
```

`__init__.py` 导出全部 9 类；`init_models.py` 追加：

```python
# --- 推演沙盘沙箱域 (onto_sandbox_* / onto_action_template) 2026-11-01 ---
from app.models.sandbox.sandbox import (  # noqa: F401
    SandboxScene, SandboxBranch, SandboxCheckpoint, SandboxEntity,
    SandboxRelation, SandboxElement, SandboxAction, SandboxObservation,
)
from app.models.sandbox.action_template import SandboxActionTemplate  # noqa: F401
```

- [ ] **Step 3: 写测试 conftest 与模型测试（先红）**

`backend/tests/sandbox/conftest.py`：**整文件复制** `backend/tests/ontology/conftest.py` 后做三处修改——(a) `_tables()` 里追加 `import app.models.sandbox.sandbox` 与 `import app.models.sandbox.action_template`；(b) 文件 docstring 改述为 sandbox；(c) `build_client` 中 `from app.routers.dataops.dataops import router` 不变（sandbox router 将挂在同一 dataops 父 router 下，Task 3 起生效）。

`test_models.py`（断言建表与 CHECK 生效、租户隔离）：

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.sandbox.sandbox import SandboxScene
from tests.sandbox.conftest import TENANT_A, TENANT_B


def test_scene_crud_and_tenant_isolation(db, client_a, client_b):
    s = SandboxScene(tenant_id=TENANT_A, ontology_id=1, ontology_version=1, name="a场景")
    db.add(s); db.commit()
    from sqlalchemy import select
    got = db.execute(select(SandboxScene).where(SandboxScene.tenant_id == TENANT_B)).scalar()
    assert got is None  # B 租户读不到 A 的场景


def test_scene_exec_mode_check(db):
    s = SandboxScene(tenant_id=TENANT_A, ontology_id=1, ontology_version=1,
                     name="x", exec_mode="turbo")
    db.add(s)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_action_templates_seeded(db):
    from sqlalchemy import select
    from app.models.sandbox.action_template import SandboxActionTemplate
    codes = {t.code for t in db.execute(select(SandboxActionTemplate)).scalars()}
    assert {"supply_cut", "delay", "price_up", "reroute"} <= codes
```

Run: `cd backend && python -m pytest tests/sandbox/test_models.py -v` → Expected: FAIL（表不存在/种子缺失）。

- [ ] **Step 4: 生成迁移并加种子**

```bash
cd backend
python -m alembic -c alembic.ini revision --autogenerate -m "add_sandbox_tables"
```

把生成文件重命名为 `alembic/versions/2026_11_01_0011_add_sandbox_tables.py`，文件头改为：

```python
revision: str = "2026_11_01_0011_add_sandbox_tables"
down_revision: Union[str, None] = "2026_11_01_0010_add_source_external_type"
```

审查 upgrade：**只应包含 9 张新表的 create_table/索引/约束**，其余对象（如 meta_* 漂移）逐条删除。在 upgrade 末尾追加种子（effect_spec 的 AST 节点形状以 Task 2 定义为准）：

```python
_TPL = sa.table(
    "onto_action_template",
    sa.column("code"), sa.column("name"), sa.column("domain_hint"),
    sa.column("param_schema_json"), sa.column("effect_spec_json"), sa.column("status"),
)
import json as _json
# 数值在 props/AST 中一律字符串（Decimal 纪律）；<target> 占位由行动目标解析
_SEEDS = [
    ("supply_cut", "断供", "supply_chain",
     {"type": "object", "props": {"ratio": {"type": "number", "default": 100}}, "required": ["ratio"]},
     {"fire_delay_tick": 1, "writes": [
         {"entity": "<target>", "prop": "supply_cut", "expr": {"op": "num", "v": "1"}},
         {"entity": "<target>", "prop": "risk_score", "expr": {"op": "num", "v": "0.9"}}]}),
    ("delay", "延迟交付", "supply_chain",
     {"type": "object", "props": {"days": {"type": "number", "default": 5}}, "required": ["days"]},
     {"fire_delay_tick": 1, "writes": [
         {"entity": "<target>", "prop": "delay_days", "expr": {"op": "param", "key": "days"}}]}),
    ("price_up", "提价", "supply_chain",
     {"type": "object", "props": {"pct": {"type": "number", "default": 10}}, "required": ["pct"]},
     {"fire_delay_tick": 1, "writes": [
         {"entity": "<target>", "prop": "price_up_pct", "expr": {"op": "param", "key": "pct"}}]}),
    ("reroute", "切换供应商", "supply_chain",
     {"type": "object", "props": {"alt_entity": {"type": "string"}}, "required": ["alt_entity"]},
     {"fire_delay_tick": 1, "writes": [
         {"entity": "<target>", "prop": "rerouted_to", "expr": {"op": "param", "key": "alt_entity"}},
         {"entity": "<target>", "prop": "risk_score",
          "expr": {"op": "sub", "a": {"op": "prop", "entity": "<target>", "key": "risk_score"},
                   "b": {"op": "num", "v": "0.3"}}}]}),
]


def _seed_templates() -> None:
    bind = op.get_bind()
    for code, name, domain, ps, es in _SEEDS:
        exists = bind.execute(
            sa.text("SELECT 1 FROM onto_action_template WHERE code = :c"), {"c": code}
        ).scalar()
        if not exists:
            op.bulk_insert(_TPL, [{
                "code": code, "name": name, "domain_hint": domain,
                "param_schema_json": _json.dumps(ps), "effect_spec_json": _json.dumps(es),
                "status": "enabled",
            }])
```

在 `upgrade()` 建表之后调用 `_seed_templates()`；`downgrade()` 按逆序 drop 9 表。执行：

```bash
python -m alembic -c alembic.ini upgrade head
python -m pytest tests/sandbox/test_models.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/sandbox backend/app/db/init_models.py backend/alembic/versions/2026_11_01_0011_add_sandbox_tables.py backend/tests/sandbox
git commit -m "feat(sandbox): 沙箱域 9 表模型 + 迁移 0011 + 行动模板种子"
```

---

### Task 2: 受控 AST 求值器（确定性内核，无 DB）

**Files:**
- Create: `backend/app/services/sandbox/__init__.py`（空）
- Create: `backend/app/services/sandbox/ast_eval.py`
- Test: `backend/tests/sandbox/test_ast_eval.py`

**Interfaces:**
- Consumes: 无
- Produces: `eval_expr(node: dict, get_prop: Callable[[str, str], Decimal], get_param: Callable[[str], Decimal]) -> Union[Decimal, bool]`；`class AstEvalError(Exception)`（属性 `code ∈ {BAD_OP, UNKNOWN_OP, MISSING_PROP, DIV_ZERO, BAD_SHAPE}`）。Task 5 引擎与 Task 7 行动以 `get_prop(entity_code, prop_key)`、`get_param(key)` 取值。

- [ ] **Step 1: 写失败测试（节点文法全覆盖）**

```python
from decimal import Decimal
import pytest
from app.services.sandbox.ast_eval import AstEvalError, eval_expr

WORLD = {"SUP006": {"risk_score": Decimal("0.64"), "supply_cut": Decimal("1")},
         "FAC007": {"capacity": Decimal("100")}}
GP = lambda e, k: WORLD[e][k] if e in WORLD and k in WORLD[e] else (_ for _ in ()).throw(
    AstEvalError("MISSING_PROP", f"{e}.{k}"))
GPARAM = lambda k: Decimal("5")


def test_arith_decimal_exact():
    n = {"op": "sub", "a": {"op": "prop", "entity": "FAC007", "key": "capacity"},
         "b": {"op": "mul", "a": {"op": "prop", "entity": "FAC007", "key": "capacity"},
               "b": {"op": "num", "v": "0.38"}}}
    assert eval_expr(n, GP, GPARAM) == Decimal("62.00")


def test_cmp_logic_agg_clip_if_param():
    assert eval_expr({"op": "ge", "a": {"op": "prop", "entity": "SUP006", "key": "risk_score"},
                      "b": {"op": "num", "v": "0.6"}}, GP, GPARAM) is True
    assert eval_expr({"op": "and", "items": [
        {"op": "eq", "a": {"op": "prop", "entity": "SUP006", "key": "supply_cut"}, "b": {"op": "num", "v": "1"}},
        {"op": "not", "a": {"op": "lt", "a": {"op": "num", "v": "2"}, "b": {"op": "num", "v": "1"}}}]}, GP, GPARAM) is True
    assert eval_expr({"op": "max", "items": [{"op": "num", "v": "1"}, {"op": "num", "v": "3"}]}, GP, GPARAM) == Decimal("3")
    assert eval_expr({"op": "clip", "x": {"op": "num", "v": "1.8"},
                      "lo": {"op": "num", "v": "0"}, "hi": {"op": "num", "v": "1"}}, GP, GPARAM) == Decimal("1")
    assert eval_expr({"op": "if", "cond": {"op": "gt", "a": {"op": "num", "v": "2"}, "b": {"op": "num", "v": "1"}},
                      "a": {"op": "num", "v": "9"}, "b": {"op": "num", "v": "0"}}, GP, GPARAM) == Decimal("9")
    assert eval_expr({"op": "param", "key": "days"}, GP, GPARAM) == Decimal("5")


def test_div_zero_and_missing_prop_and_unknown_op():
    with pytest.raises(AstEvalError) as e:
        eval_expr({"op": "div", "a": {"op": "num", "v": "1"}, "b": {"op": "num", "v": "0"}}, GP, GPARAM)
    assert e.value.code == "DIV_ZERO"
    with pytest.raises(AstEvalError) as e:
        eval_expr({"op": "prop", "entity": "NOPE", "key": "x"}, GP, GPARAM)
    assert e.value.code == "MISSING_PROP"
    with pytest.raises(AstEvalError) as e:
        eval_expr({"op": "system", "cmd": "rm"}, GP, GPARAM)
    assert e.value.code == "UNKNOWN_OP"
```

Run: `python -m pytest tests/sandbox/test_ast_eval.py -v` → FAIL（模块不存在）。

- [ ] **Step 2: 实现 `ast_eval.py`（全文照录）**

```python
"""受控 AST 求值器（spec §4.1：仅字面量/属性引用/四则/比较/逻辑/聚合/clip/if）。

确定性纪律：数值一律 Decimal（入参字符串，结果量化 4 位）；禁止 eval/exec；
节点形状非法或引用缺失抛 AstEvalError —— 引擎侧按“配置期 warn”处理，不中断 Tick。
"""
from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Callable, Union

Value = Union[Decimal, bool]

_ARITH = {"add", "sub", "mul", "div", "mod"}
_CMP = {"gt", "ge", "lt", "le", "eq", "ne"}
_AGG = {"min", "max", "sum", "avg", "count"}
_Q = Decimal("0.0001")


class AstEvalError(Exception):
    def __init__(self, code: str, msg: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {msg}")


def _d(x) -> Decimal:
    if isinstance(x, bool):
        raise AstEvalError("BAD_SHAPE", "bool 不作数值")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _truthy(v: Value) -> bool:
    return bool(v) if isinstance(v, bool) else v != 0


def eval_expr(node: dict, get_prop: Callable[[str, str], Decimal],
              get_param: Callable[[str], Decimal]) -> Value:
    if not isinstance(node, dict) or "op" not in node:
        raise AstEvalError("BAD_SHAPE", f"节点非法: {node!r}")
    op = node["op"]
    if op == "num":
        try:
            return _d(node["v"]).quantize(_Q)
        except (InvalidOperation, KeyError):
            raise AstEvalError("BAD_SHAPE", f"num 值非法: {node!r}")
    if op == "prop":
        return _d(get_prop(node["entity"], node["key"])).quantize(_Q)
    if op == "param":
        return _d(get_param(node["key"])).quantize(_Q)
    if op in _ARITH:
        a, b = _d(eval_expr(node["a"], get_prop, get_param)), _d(eval_expr(node["b"], get_prop, get_param))
        try:
            if op == "add": r = a + b
            elif op == "sub": r = a - b
            elif op == "mul": r = a * b
            elif op == "div":
                if b == 0:
                    raise AstEvalError("DIV_ZERO")
                r = a / b
            else:
                if b == 0:
                    raise AstEvalError("DIV_ZERO")
                r = a % b
        except (DivisionByZero, InvalidOperation):
            raise AstEvalError("DIV_ZERO")
        return r.quantize(_Q)
    if op in _CMP:
        a, b = _d(eval_expr(node["a"], get_prop, get_param)), _d(eval_expr(node["b"], get_prop, get_param))
        return {"gt": a > b, "ge": a >= b, "lt": a < b, "le": a <= b,
                "eq": a == b, "ne": a != b}[op]
    if op in ("and", "or"):
        vals = [_truthy(eval_expr(x, get_prop, get_param)) for x in node["items"]]
        return all(vals) if op == "and" else any(vals)
    if op == "not":
        return not _truthy(eval_expr(node["a"], get_prop, get_param))
    if op in _AGG:
        items = [_d(eval_expr(x, get_prop, get_param)) for x in node["items"]]
        if op == "count":
            return Decimal(len(items))
        if not items:
            raise AstEvalError("BAD_SHAPE", "空聚合")
        if op == "min": return min(items)
        if op == "max": return max(items)
        if op == "sum": return sum(items, Decimal(0)).quantize(_Q)
        return (sum(items, Decimal(0)) / Decimal(len(items))).quantize(_Q)  # avg
    if op == "clip":
        x = _d(eval_expr(node["x"], get_prop, get_param))
        lo, hi = _d(eval_expr(node["lo"], get_prop, get_param)), _d(eval_expr(node["hi"], get_prop, get_param))
        return max(lo, min(hi, x))
    if op == "if":
        c = _truthy(eval_expr(node["cond"], get_prop, get_param))
        return eval_expr(node["a"] if c else node["b"], get_prop, get_param)
    raise AstEvalError("UNKNOWN_OP", op)
```

- [ ] **Step 3: 运行确认通过** — `python -m pytest tests/sandbox/test_ast_eval.py -v` → PASS。
- [ ] **Step 4: Commit** — `git add backend/app/services/sandbox backend/tests/sandbox/test_ast_eval.py && git commit -m "feat(sandbox): 受控 AST 求值器（Decimal 确定性，A1 内核）"`

---

### Task 3: 场景生命周期 + 克隆链路（S1–S5）+ 错误码 + router 挂载

**Files:**
- Create: `backend/app/services/sandbox/sandbox_scene_service.py`、`backend/app/services/sandbox/sandbox_clone_service.py`
- Create: `backend/app/routers/sandbox/__init__.py`、`backend/app/routers/sandbox/sandbox.py`
- Modify: `backend/app/core/api_error.py`（追加 9 常量，见下）、`backend/app/routers/dataops/dataops.py`（`include_router(ontology_router)` 行后追加 `include_router(sandbox_router)`）
- Test: `backend/tests/sandbox/test_scene_clone.py`

**Interfaces:**
- Consumes: Task 1 模型全部列名；`OntologyAppPublishService.list_publishes`（判 `enabled` 且 `stale=False`）；`MetaOntologyVersion.snapshot_json` 形状（objects/mappings.table/mappings.column/properties，键名见 `ontology_publish_service.py:175-213`）；`MetaTable(source_id,db_name,database,table_name)`、`MetaColumn(table_id,column_name,pii_level)`、`MetaStandard(code,mask_rule)`、`ReadonlyQueryService.run(source_id, sql, limit) -> {columns,rows,row_count,truncated}`。
- Produces:
  - `SandboxSceneService(db, tenant_id)`：`create_scene(*, ontology_id, name, clone_scope, tick_max=12, exec_mode="auto", creator_id=None) -> dict`（校验钉版 → 落 scene(draft) + 基线分支 → `_EXECUTOR.submit(_run_clone, scene_id, tenant_id)` → 返回 `{"scene_id","status":"draft"}`）；`get_scene(scene_id) -> dict`；`list_scenes(ontology_id=None, status=None) -> list[dict]`；`patch_scene(scene_id, *, name=None, exec_mode=None) -> dict`；`delete_scene(scene_id) -> None`（CASCADE 回收）。
  - `SandboxCloneService(db, tenant_id)`：`build_select(snapshot, object_code, masked_out) -> tuple[str, dict] | None`（纯函数，可单测）；`clone_scene(scene_id: int) -> None`（幂等：仅 `status in (draft, failed)` 可跑）；构造参数 `fetcher: Callable[[int, str, int], dict] | None = None`——测试注入假取数器，缺省用 `ReadonlyQueryService(db, tenant_id).run`。
  - 克隆完成态：基线分支写入 entity 当前态行 + `SandboxCheckpoint(seq=0,label="基线快照")` + 其快照行；`status=running`；`clone_stats_json={entities,relations:0,masked_columns[]}`。
  - 错误码常量（`api_error.py` 追加，命名与 spec §4.2 逐字一致）：`SCENE_NOT_FOUND`、`ONTOLOGY_NOT_PUBLISHED`、`CLONE_LIMIT_EXCEEDED`、`CHECKPOINT_LIMIT`、`GATE_DENIED_MASKED`、`GATE_DENIED_MODE`、`ELEMENT_NOT_ADOPTED`、`ACTION_TEMPLATE_DISABLED`、`CONFIRM_EXPIRED`。
  - 端点：S1 `POST /ontologies/sandbox/scenes`、S2 `GET /ontologies/sandbox/scenes`、S3 `GET /ontologies/sandbox/scenes/{scene_id}`、S4 `DELETE .../scenes/{scene_id}` (204)、S5 `PATCH .../scenes/{scene_id}`。

- [ ] **Step 1: 写失败测试（三段：钉版校验 / SQL 计划纯函数 / 端到端假取数克隆）**

```python
# backend/tests/sandbox/test_scene_clone.py（要点节选，实现时补全 import）
def _seed_published_ontology(db):
    """建 MetaOntology(status=published,current_version=1) + MetaOntologyVersion(version=1,
    snapshot_json 含 objects[code=Supplier] + mappings.table[{id:1,table_id:1,object_standard_id:11}]
    + mappings.column[{column_id:101,standard_id:201}...] + properties[...]），
    MetaTable(id=1,source_id=1,database='dwh',table_name='dwd_supp_item',tenant_id=TENANT_A)，
    MetaColumn(id=101,table_id=1,column_name='supp_name') / MetaColumn(id=102,column_name='mobile',pii_level='L3')，
    MetaStandard(id=201,code='name') / MetaStandard(id=202,code='mobile',mask_rule='mask_left(mobile,3,4)')，
    MetaOntologyPublish(target_type='skill',code='sk1',version=1,status='enabled') 后 return ontology.id"""


def test_create_scene_requires_published(db, client_a):
    r = client_a.post("/ontologies/sandbox/scenes",
                      json={"ontology_id": 999, "name": "断供传导", "clone_scope": {}})
    assert r.status_code == 404 and r.json()["code"] == "ONTOLOGY_NOT_FOUND"
    oid = _seed_published_ontology(db)
    r2 = client_a.post("/ontologies/sandbox/scenes",
                       json={"ontology_id": oid, "name": "断供传导",
                             "clone_scope": {"object_codes": ["Supplier"]}})
    assert r2.status_code == 201 and r2.json()["status"] == "draft"


def test_build_select_masks_sensitive_columns_in_sql(db):
    svc = SandboxCloneService(db, TENANT_A)
    snapshot = ...  # 与 _seed_published_ontology 同构的最小快照
    sql, meta = svc.build_select(snapshot, "Supplier", [])
    assert 'FROM "dwh"."dwd_supp_item"' in sql
    assert "SELECT" in sql and '"supp_name"' in sql
    assert "'***' AS mobile" in sql          # 脱敏在字面量层，明文不出源库（V4/A3）
    assert meta["masked_columns"] == ["mobile"]
    assert "DELETE" not in sql.upper()


def test_clone_with_fake_fetcher(db):
    """注入 fetcher 返回 3 行（含 mobile 明文列——服务必须丢弃非'***'值），
    clone_scene 后断言：branch 基线 + 3 条 entity 当前态行 + seq=0 基线检查点 +
    checkpoint_id 快照行 3 条 + clone_stats_json.entities==3 + status=='running'；
    再调 clone_scene 一次断言幂等（行数不变）。"""
```

Run: `python -m pytest tests/sandbox/test_scene_clone.py -v` → FAIL。

- [ ] **Step 2: 实现 `sandbox_scene_service.py`**

关键校验（`create_scene` 内，代码要点）：

```python
on = self.db.get(MetaOntology, ontology_id)  # 再校验 tenant
if on is None: raise ApiError(ONTOLOGY_NOT_FOUND, ...)
if on.status != "published" or (on.current_version or 0) == 0:
    raise ApiError(ONTOLOGY_NOT_PUBLISHED, "世界来源必须为已发布本体应用", http_status=400)
pubs = OntologyAppPublishService(self.db, self.tenant_id).list_publishes(ontology_id)
if not any(p["status"] == "enabled" and not p["stale"] for p in pubs):
    raise ApiError(ONTOLOGY_NOT_PUBLISHED, "无 enabled 且未过期的应用发布登记", http_status=400)
ver = self.db.execute(select(MetaOntologyVersion).where(
    MetaOntologyVersion.ontology_id == ontology_id,
    MetaOntologyVersion.version == on.current_version)).scalar_one_or_none()
if ver is None: raise ApiError(ONTOLOGY_NOT_PUBLISHED, ...)
max_entities = min(int(scope.get("max_entities", 500)), 5000)   # 硬顶（Global Constraints）
max_relations = min(int(scope.get("max_relations", 2000)), 20000)
scene = SandboxScene(..., ontology_version=on.current_version, status="draft")
branch = SandboxBranch(scene_id=scene.id, name="基线分支", color="#4aa3ff", tick_now=0)
```

`patch_scene` 仅允许改 `name/exec_mode`；`delete_scene` 只删 `SandboxScene`（FK CASCADE 回收全链）；均先 `_scene_or_404`（tenant 过滤，`SCENE_NOT_FOUND` 404）。

- [ ] **Step 3: 实现 `sandbox_clone_service.py`**

`build_select(snapshot, object_code, masked_out)` 逻辑：由快照派生——object(id) → `mappings.table` 里 `object_standard_id==object.id` 的 table_id → `MetaTable`；`properties` 中 `object_id==object.id` 的 standard_id 集合 → `mappings.column` 命中 (这些 standard_id) 的 column_id → `MetaColumn`；对每列查 `MetaStandard`：`mask_rule` 非空 **或** `MetaColumn.pii_level=='L3'` → SELECT 列表写 `'***' AS <列名>` 并把列名加入 `masked_columns`，否则 `"列名"`。表标识带 schema 限定：`f'"{tbl.database}"."{tbl.table_name}"'`；SQL 为 `SELECT <cols> FROM <tbl> ORDER BY 1 LIMIT {max_entities+1}`（+1 探测超限；`ORDER BY 1` 保证取数确定性）。**不 SELECT 未被映射的列**。

`clone_scene(scene_id)`：幂等守卫 → 载入 scene/ver.snapshot_json/基线分支 → 对 `scope.object_codes` 逐对象 `build_select` → `self._fetch(source_id, sql, max_entities+1)` → 行数 > max_entities 抛 `ApiError(CLONE_LIMIT_EXCEEDED, http_status=400, detail={"object_code","count"})` → 每行建 `SandboxEntity(branch_id=基线, entity_code=f"{object_code[:3].upper()}{i:03d}", object_code, props_json=<脱敏后的行转 dict，数值 str()>, masked=<该行含'***'>, source_ref_json={"source_id","db","table","pk":<首个映射列值>}, origin="clone")`（行序按 SQL 结果序，entity_code 确定性）→ 建基线检查点（`seq=0,label="基线快照",tick=0`）并复制快照行（`checkpoint_id` 同 set）→ `scene.status="running"`，`clone_stats_json` → commit。异常路径：`scene.status="failed"; error_detail=str(exc)[:2000]`。

后台执行（照 `ontology_build_service.py:100-123` 全文模式）：

```python
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sandbox-clone")

def submit_clone(scene_id: int, tenant_id: int) -> None:
    _EXECUTOR.submit(_run_clone, scene_id, tenant_id)

def _run_clone(scene_id: int, tenant_id: int) -> None:
    db = SessionLocal()
    try:
        SandboxCloneService(db, tenant_id).clone_scene(scene_id)
    except Exception as exc:
        logger.exception(f"沙箱克隆 worker 异常 scene={scene_id}: {exc}")
        db.rollback()
        s = db.get(SandboxScene, scene_id)
        if s is not None:
            s.status = "failed"; s.error_detail = str(exc)[:2000]; db.commit()
    finally:
        db.close()
```

`create_scene` 末尾调用 `submit_clone(scene.id, self.tenant_id)`。测试中为避免线程竞态，S1 后**轮询** `GET /scenes/{id}` 至 status∈{running,failed}（上限 5s，间隔 50ms）——conftest `db` fixture 为同步 Session，worker 用独立连接读同一测试 schema：可行，因为 engine 的 `search_path` 已固定在 conftest 引擎事件里，但 `SessionLocal` 走生产 engine 会落 public schema —— 因此测试**不依赖后台线程**：`client_a` 建景后直接以 service 层同步调 `SandboxCloneService(db, TENANT_A, fetcher=fake).clone_scene(scene_id)`（后台线程在真实运行路径才触发；`patch/delete/get` 走端点测）。router 的 S1 仍只 submit。

- [ ] **Step 4: 实现 router（S1–S5）并挂载**

`backend/app/routers/sandbox/sandbox.py` 骨架（照 `routers/ontology/ontology.py:38-52` 的 deps 模式）：

```python
router = APIRouter(tags=["推演沙盘 沙箱域"])

def _tenant(current_user: SysUser) -> int:
    tid = getattr(current_user, "tenant_id", None)
    if tid is None:
        raise ApiError("TENANT_REQUIRED", "缺少租户上下文", http_status=403)
    return tid
```

五个端点函数体各 ≤6 行（构造 service → 调方法 → dict/list 直返；S4 `status_code=204`）。`dataops.py` 在 `include_router(ontology_router)` 后加 `from app.routers.sandbox.sandbox import router as sandbox_router` 与 `router.include_router(sandbox_router)`。`api_error.py` 常量区追加 9 个（带 spec §4.2 注释）。

- [ ] **Step 5: 运行** — `python -m pytest tests/sandbox/test_scene_clone.py -v` → PASS。全量回归：`python -m pytest tests/sandbox tests/ontology -v`（dataops 挂载变更不得破坏既有 15+ 路由）。
- [ ] **Step 6: Commit** — `git commit -am "feat(sandbox): 场景生命周期 + 克隆链路 S1-S5 + 错误码 + router 挂载"`

---

### Task 4: 配置元素与 D3 审阅（S13–S15）

**Files:**
- Create: `backend/app/services/sandbox/sandbox_element_service.py`
- Modify: `backend/app/routers/sandbox/sandbox.py`（追加 S13/S14/S15）
- Test: `backend/tests/sandbox/test_elements.py`

**Interfaces:**
- Consumes: `SandboxElement` 模型（Task 1）；`llm_json(prompt: str, model_id=None) -> dict`（`app.ai.research.llm`，调用姿势照 `ontology_assistant_service.py:414-422` 的 `asyncio.run` + 降级 try/except）；`SandboxEntity`（llm-draft 提示词取世界实体清单）。
- Produces: `SandboxElementService(db, tenant_id)`：
  - `list_elements(scene_id, *, kind=None, status=None) -> list[dict]`
  - `upsert_element(scene_id, payload: dict, *, origin="human") -> dict`——payload 键即模型列（`kind,code,label,from_ref,to_ref,condition_expr_json,effect_expr_json,activation_tick`）；重复 `(scene_id,kind,code)` → 覆盖非空字段；`origin='llm'` 强制 `status='suggested'`；
  - `review_element(element_id, decision: str) -> dict`——`accept|reject`；llm 元素 accept → `status='accepted'`（D3 允许人审采纳）；suggested 之外的重复审阅 → 400；
  - `draft_llm(scene_id, branch_id=None, model_id=None) -> list[dict]`——组提示词（世界实体清单 + 指令输出 `{"elements":[{kind:'causal_edge',...}]}` JSON），`llm_json` 结果逐条校验（AST 节点用 `ast_eval.eval_expr` 试编译：以恒 0 prop 源跑一次，`BAD_SHAPE/UNKNOWN_OP` 拒绝该条）→ 落 `origin='llm', status='suggested'`；LLM 失败 → 返回 `[]`（降级不抛）。
  - 引擎加载入口：`load_accepted(scene_id) -> list[dict]`（`status=='accepted'` 全量按 `(kind, code)` 排序——**固定序，A1 前提**）。
- 端点：S13 `GET/POST /scenes/{id}/elements` + `PUT /elements/{eid}` + `DELETE /elements/{eid}`；S14 `POST /scenes/{id}/elements/llm-draft`；S15 `POST /elements/{eid}/review`。

- [ ] **Step 1: 写失败测试**

```python
def test_llm_origin_forced_suggested(svc):
    e = svc.upsert_element(SC, {"kind": "causal_edge", "code": "CE-1",
                                "from_ref": "SUP006", "to_ref": "FAC007"}, origin="llm")
    assert e["status"] == "suggested"          # V2：llm 永不自动采纳

def test_accept_then_load_accepted(svc):
    e = svc.upsert_element(SC, {"kind": "rule", "code": "R-1", "origin": "human"})
    assert [x["code"] for x in svc.load_accepted(SC)] == []
    svc.review_element(e["id"], "accept")
    assert [x["code"] for x in svc.load_accepted(SC)] == ["R-1"]

def test_draft_rejects_bad_ast(db, svc, monkeypatch):
    fake = {"elements": [
        {"kind": "causal_edge", "code": "CE-BAD", "effect_expr_json": {"op": "system", "cmd": "x"}},
        {"kind": "causal_edge", "code": "CE-OK", "condition_expr_json":
            {"op": "eq", "a": {"op": "prop", "entity": "SUP006", "key": "supply_cut"},
             "b": {"op": "num", "v": "1"}}}]}
    monkeypatch.setattr("app.services.sandbox.sandbox_element_service.llm_json",
                        lambda p, model_id=None: fake)
    out = svc.draft_llm(SC)
    assert [x["code"] for x in out] == ["CE-OK"]           # 坏 AST 条被拒
    assert all(x["origin"] == "llm" and x["status"] == "suggested" for x in out)

def test_load_accepted_sorted(svc):  # 造 R-2/R-1/R-10 → 断言 == ["R-1","R-10","R-2"]
```

- [ ] **Step 2: 实现服务**（各方法 ≤20 行；`load_accepted` 的排序键 `(kind, code)` 是字符串元组排序，测试 `R-10` 用例锁定行为）。
- [ ] **Step 3: 端点追加 + 运行 PASS**
- [ ] **Step 4: Commit** — `"feat(sandbox): element 配置与 D3 审阅 S13-S15（含 LLM 草稿降级）"`

---

### Task 5: 确定性 Tick 引擎（S8/S19/S21 + 检查点/派生/回放/对比 S9–S12）

**Files:**
- Create: `backend/app/services/sandbox/sandbox_engine_service.py`
- Modify: `backend/app/routers/sandbox/sandbox.py`（追加 S6/S7/S8/S9/S10/S11/S12/S19/S21）
- Test: `backend/tests/sandbox/test_engine.py`

**Interfaces:**
- Consumes: Task 1 全部模型；Task 2 `eval_expr`；Task 4 `SandboxElementService.load_accepted`（固定序）；`SandboxObservation` kind 枚举全集。
- Produces（Task 6/7/8 依赖的确切签名）:
  - `SandboxEngineService(db, tenant_id)`：
    - `load_world(scene_id, branch_id) -> World`——`World` 为 dataclass：`{entities: dict[str, dict]（entity_code → {props: dict[str, Decimal], risk_score: Decimal, masked: bool, object_code}）, elements: list[dict]（accepted, (kind,code) 序）, events: list[dict]（pending derived 实体行）}`；当前态行（`checkpoint_id IS NULL`）是唯一可变真源，数值列存字符串、载入即转 Decimal。
    - `run_tick(scene_id, branch_id) -> int`——单 Tick 八段流水（见 Step 2），结束 `branch.tick_now += 1`，落 observation 全套；纯函数式：同输入 World+elements → 同输出（A1 根据）。
    - `advance(scene_id, branch_id, n) -> dict`——守卫（status/模式/tick_max：`branch.tick_now + n > scene.tick_max` → 400 `TICK_WINDOW_EXCEEDED`… **不新增错误码**，用既有 `ApiError("PARAM_INVALID", …, http_status=400)`）后循环 `run_tick`；返回 `{branch_id, tick_before, tick_after, observations_created}`。
    - `preview_future(scene_id, branch_id, depth: int = 4) -> list[dict]`——深拷贝 World 在内存沿 accepted causal_edge 正向推演 ≤depth Tick，**不落任何库**；返回 `[{element_code, expected_tick, target_ref, effect_summary}]`（expected_tick = branch.tick_now + 推演命中 Tick 偏移）。
    - `save_checkpoint(scene_id, branch_id, label, creator_id=None) -> dict`——场景级合计计数（含 seq=0 基线）`>= 5` → `ApiError(CHECKPOINT_LIMIT, http_status=400)`；复制当前态 entity/relation 行为 `checkpoint_id` 快照行；`stats_json={entities,relations,kpi}`（kpi 取该分支最近一个 kpi_point detail）；返回 `{id, seq, tick, label, count_used}`。
    - `derive_branch(scene_id, checkpoint_id, name) -> dict`——新 branch（`base_checkpoint_id=checkpoint_id`，`tick_now=checkpoint.tick`）；把该检查点快照行复制为新分支当前态行（`checkpoint_id=NULL`）；`(scene_id,name)` 冲突 → 400。
    - `replay_to(scene_id, branch_id, to_tick) -> dict`——分支从检查点回放：删除该分支当前态行与 `tick > to_tick` 的 observation，以该分支可达的最近 `tick<=to_tick` 快照/重放序列恢复当前态；MVP 实现口径：**从基线 seq=0 快照恢复 + 按存档 observation 的 action_effect 顺序重放 run_tick 至 to_tick**（无中间检查点时用基线重放，A1 确定性保证结果与原生推进一致）。返回 `{tick_now, restored_entities}`。
    - `compare(scene_id, branch_ids: list[int]) -> dict`——`{branches:[{branch_id,name}], series:[{tick, {branch_id: {health, risk_top3}}}], diff_table:[{kpi, branch_a_final, branch_b_final, delta}]}`；全部值聚合自 observation，**不做任何前端可算之外的计算**（A6）。
    - `world_view(scene_id, branch_id, tick=None, view="world") -> dict`（S6）与 `entity_detail(scene_id, branch_id, entity_code) -> dict`（S7）：只读渲染查询；tick 参数 MVP 允许 NULL=当前态（历史 Tick 渲染走 replay，P1 优化为时态查询）。
  - 端点：S8 `POST /scenes/{id}/branches/{bid}/advance`、S9 `POST .../checkpoints`、S10 `POST /scenes/{id}/branches`、S11 `GET /scenes/{id}/compare?branches=1,2`、S12 `POST .../replay {to_tick}`、S6 `GET /scenes/{id}/world`、S7 `GET /scenes/{id}/entities/{code}`、S19 `GET /scenes/{id}/observations`（`kind=future` 时内部调 `preview_future`）、S21 `GET /scenes/{id}/kpis`。

- [ ] **Step 1: 写失败测试（确定性 + 检查点 + 派生 + 回放 + 对比 + 上限六组）**

```python
# backend/tests/sandbox/test_engine.py（要点；fixture 造 scene+branch+3 entity+2 accepted element）
def test_run_tick_deterministic(db):
    """同初态同配置连跑两次（第二次先 replay_to(0) 复位），逐 Tick 断言：
    entity props（str 化）/ observation (kind,tick,title,detail_json) 序列完全一致（A1）。"""


def test_supply_cut_propagation(db):
    """CE: SUP006.supply_cut==1 → FAC007.capacity = capacity*0.62; R-1: risk>=0.9 → rule_fired。
    advance(n=3) 后断言 FAC007.props['capacity']=='38.0000'（Decimal 字符串）、
    observation 含 edge_fired/rule_fired/kpi_point 各 3 条、branch.tick_now==3。"""


def test_checkpoint_limit_and_derive(db):
    """基线 seq=0 已占 1 格 → 再存 4 个成功、第 5 个（合计第 6）400 CHECKPOINT_LIMIT；
    derive_branch 后原分支当前态行不变（行数+tick_now 断言，A5）。"""


def test_delete_checkpoint_with_dependent_branch_rejected(db):
    """存在 base_checkpoint_id 指向的分支 → 删除接口 400（A5）。"""


def test_replay_restores_identical_state(db):
    """分支 A advance(5) 记录 observation 指纹 → replay_to(0) → 再 advance(5) 指纹一致（A1 回放面）。"""


def test_compare_series_from_observations(db):
    """两分支各推进 → compare 的 series/diff_table 数值与直接 SQL 聚合 observation 一致（A6）。"""
```

Run: `python -m pytest tests/sandbox/test_engine.py -v` → FAIL。

- [ ] **Step 2: 实现 `run_tick` 八段流水（顺序即语义，逐段落 observation，source='engine'）**

```python
def run_tick(self, scene_id: int, branch_id: int) -> int:
    """单 Tick：全部计算在本方法内完成，顺序固定（A1/R3）。"""
    world = self.load_world(scene_id, branch_id)
    tick = self._branch(branch_id).tick_now + 1
    # ① 事件到期：pending derived 实体（origin='derived' 且 activation_tick<=tick）转生效
    self._fire_events(scene_id, branch_id, tick, world)
    # ② 因果边传播：accepted causal_edge 按 load_accepted 固定序逐条——
    #    condition_expr_json 求值（AstEvalError→warn 观察并跳过该条，不中断 Tick，R2）
    #    命中 → effect_expr_json 求值 → 写回目标实体属性（Decimal quantize 4 位）
    #    → 落 edge_fired 观察 {element_code, from, to, effect}
    self._propagate_edges(scene_id, branch_id, tick, world)
    # ③ 规则求值：kind='rule'，命中落 rule_fired（首次命中/失效再命中都算）；
    #    「错过 deadline」：rule 带 deadline_tick 且 tick>deadline_tick 未满足 → deadline_missed(err)
    self._eval_rules(scene_id, branch_id, tick, world)
    # ④ 目标求值：kind='goal' 判据 → goal_eval {goal_code, status: reached|watching|threatened}
    #    受威胁判定：目标 prop 引用链上出现 warn 级观察 → threatened
    self._eval_goals(scene_id, branch_id, tick, world)
    # ⑤ 行动效应到期：Task 6 在 apply/confirm 时只写 pending 事件行（derived 实体，origin='derived'），
    #    到期消费与生效观察（action_effect）由本方法完成；四元写入 effect_spec.writes 已在行动提交时
    #    转为属性改写，此处仅清理事件队列并落 action_effect 观察（实现归 Task 6 对 `_apply_due_actions`
    #    的填充，Task 5 先以空实现占位——本任务测试不覆盖行动链）
    self._apply_due_actions(scene_id, branch_id, tick, world)
    # ⑥ KPI 采样：health = clip(avg(1 - risk_score), 0, 1)；controllability = 1 - 生效edge数/accepted_edge数
    self._obs(scene_id, branch_id, tick, "kpi_point", "info", f"Tick{tick} KPI",
              {"health": str(health.quantize(_Q)), "controllability": str(ctrl.quantize(_Q))})
    # ⑦ 风险 TOP3：按 entity.risk_score 降序（同分按 entity_code 字典序——固定全序）
    self._obs(scene_id, branch_id, tick, "risk_point", "warn", "风险TOP3",
              [{"entity_code": c, "score": str(s)} for c, s in top3])
    # ⑧ 落库：world 脏实体写回当前态行（props 数值 str() 序列化），branch.tick_now = tick
    self._flush_world(scene_id, branch_id, world)
    return tick
```

实现要点：
- `_propagate_edges` 目标解析：`to_ref` 支持 `"<entity>.<prop>"` 与 `"<object_code>:<prop>"`（后者作用于该类型全部实体——原型 `updateKPI` 的按类改写语义）。
- `get_prop` 闭包从 `world.entities` 取 Decimal；缺失属性 → `AstEvalError(MISSING_PROP)` → 配置期 warn 观察（kind='observation', severity='warn', title=`配置告警 {code}: {err.code}`）并 continue —— **warn 也是确定性输出的一部分**。
- 所有落库数值 `str(Decimal)`；observation `detail_json` 里同样字符串，比对测试用 json 归一化。
- `preview_future`：`copy.deepcopy(world)` 后内存循环复用 `_propagate_edges` 纯计算版（不落库），命中即记录 `{element_code, expected_tick=tick_now+offset}`；depth 上限 `min(depth,4)`。

- [ ] **Step 3: 实现 checkpoint/derive/replay/compare/S6/S7/S19/S21 查询方法 + `preview_future`**

`preview_future` 实现：`copy.deepcopy(world)` 后内存循环复用 `_propagate_edges` 的纯计算变体（抽函数 `_propagate_into(world, elements, tick) -> hits`，不落库版本供 run_tick 与 preview 共用），命中即记录 `{element_code, expected_tick=tick_now+offset}`；depth 上限 `min(depth,4)`；只读、不产生任何 observation（spec §1 真前瞻语义）。

其余方法各 ≤25 行，要点：
- `save_checkpoint` 计数：`SELECT count(*) FROM onto_sandbox_checkpoint WHERE scene_id=:s`（**场景级合计**，跨分支；含基线）`>= 5` → `CHECKPOINT_LIMIT`。快照复制用 `INSERT ... SELECT checkpoint_id=新id` 单语句批量复制（entity+relation 两张）。
- 检查点删除（S9 配套 `DELETE /checkpoints/{cid}`）：`SELECT 1 FROM onto_sandbox_branch WHERE base_checkpoint_id=:cid` 命中 → 400 `CHECKPOINT_HAS_BRANCHES`（用既有通用码 `ApiError("PARAM_INVALID", "存在派生分支依赖该检查点", http_status=400)`，不扩错误码表）。
- `replay_to`：删除当前态行 → 从基线 seq=0 快照行复制恢复 → 删除 `tick>to_tick` observation → 从 `branch.tick_now=0` 循环 `run_tick` 至 `to_tick`（重放路径与原生路径共用 `run_tick`，确定性由 A1 测试锁定）。若存在 `tick<=to_tick` 的更近检查点且属于本分支，从该快照恢复可省重放步数（优化，可选实现）。
- `compare`：`kind='kpi_point'` observation 按 `(branch_id, tick)` 聚合；`risk_top3` 取各分支终值 tick 的 risk_point detail；diff_table 只列 health 与终值违约风险两类（数据来自引擎，非前端计算，A6）。
- S19 observations：过滤 `(scene_id, branch_id, tick_from..tick_to, kind)`；`kind=future` → 调 `preview_future` 结果映射为 observation 形状（不落库）。
- S21 kpis：`kind IN ('kpi_point','risk_point')` 时序直返。

- [ ] **Step 4: router 追加 S6–S12/S19/S21**（函数体各 ≤6 行；S8 需权限点 `sandbox:run`；S9/S10/S12 亦 `sandbox:run`）。
- [ ] **Step 5: 运行** `python -m pytest tests/sandbox/test_engine.py -v` → PASS；回归 `tests/sandbox`。
- [ ] **Step 6: Commit** — `git commit -am "feat(sandbox): 确定性 Tick 引擎 + 检查点/派生/回放/对比 S6-S12/S19/S21"`

---

### Task 6: 行动门禁与两段式确认（S16–S18）

**Files:**
- Create: `backend/app/services/sandbox/sandbox_action_service.py`
- Modify: `backend/app/routers/sandbox/sandbox.py`（追加 S16/S17/S18 + 确认端点 S17b）
- Test: `backend/tests/sandbox/test_actions_gate.py`

**Interfaces:**
- Consumes: Task 1 `SandboxAction`/`SandboxActionTemplate`/`SandboxEntity`；Task 5 `SandboxEngineService.run_tick` 与 `_apply_due_actions` 消费的事件队列形态（= `SandboxEntity(origin='derived')` + `SandboxAction.gate_result='allowed'` 待生效行）；spec §5.3 六步序列与 §5.4 模式语义。
- Produces:
  - `SandboxActionService(db, tenant_id, user_id)`：
    - `list_templates() -> list[dict]`（S16，仅 `status='enabled'`；含 param_schema_json 驱动 F7 表单）。
    - `apply_action(scene_id, branch_id, *, template_code, target_entity_code, params) -> dict`——返回 `{gate_result: allowed|denied|pending, action_id, tick_after?, confirm_token?, reason?}`。**六步求值序列（顺序即验收 A4/A3 语义）**：

```python
# 1. scene.exec_mode == 'replay'  → denied(MODE_READONLY)          落审计后返回（非 403，spec §5.4）
# 2. 无 sandbox:act 功能权限       → denied(NO_ACTION_PERMISSION)   落审计
# 3. 目标实体 masked               → denied(MASKED_TARGET)          落审计（A3）
# 4. 模板 disabled / 参数不合 schema → 400（ACTION_TEMPLATE_DISABLED / PARAM_INVALID）
#    —— 非法请求不进门禁留痕（spec §5.3 第 4 步）
# 5. exec_mode == 'stepwise'       → pending + confirm_token=secrets.token_urlsafe(24)
#    落审计(pending)；确认超时（token 生成后 5 分钟）→ CONFIRM_EXPIRED
# 6. exec_mode == 'auto'           → allowed → 写 SimEvent（derived 实体行, activation_tick=tick+fire_delay_tick）
#    + 目标属性改写（effect_spec_json.writes 经 eval_expr, get_param 取 params）→ run_tick 推进 1 Tick
```

    - `confirm_action(scene_id, action_id, *, token) -> dict`（S17b `POST /scenes/{id}/actions/{aid}/confirm`）——校验 pending + token 匹配 + 未过期（`created_at + 300s`）→ 执行第 6 步写入并推进；否则 `CONFIRM_EXPIRED` 400。**未经确认的 pending 行动不得改变世界**（A4：断言实体行与 observation 无新增）。
    - `list_actions(scene_id, *, branch_id=None, result=None) -> list[dict]`（S18，allowed/denied/pending 全量留痕）。
  - `_deny(scene_id, branch_id, tick, reason, …) -> dict`：先落 `SandboxAction(gate_result='denied', gate_reason=reason)` 再返回 —— 审计闭环是硬性顺序。

- [ ] **Step 1: 写失败测试（六步门禁全路径）**

```python
def test_gate_replay_denied_audited(db, svc_auto):   # exec_mode=replay → denied(MODE_READONLY) + action 行存在；世界无变化
def test_gate_masked_target(db, svc_auto):           # masked 实体 → GATE_DENIED_MASKED 语义（gate_reason='MASKED_TARGET'）+ 审计（A3/A5）
def test_gate_template_disabled_no_audit(db, svc_auto):  # disabled 模板 → 400 且 action 表无新行（第 4 步不入留痕）
def test_stepwise_pending_then_confirm(db, svc_step):    # pending → 世界不变（A4）→ confirm 正确 token → allowed + SimEvent + tick+1
def test_stepwise_confirm_expired(db, svc_step, monkeypatch):  # token 超时 → CONFIRM_EXPIRED；行动保持 pending、世界不变
def test_auto_writes_world_and_advances(db, svc_auto):   # supply_cut 100% → 目标 risk_score 改写 + derived SimEvent + tick_after==tick+1
def test_denied_always_returns_action_id(db, svc_replay):  # 三种 denied 均含 action_id（审计闭环）
```

- [ ] **Step 2: 实现服务**（`apply_action` 主体 = 上述六步的直译；参数 schema 校验用 `jsonschema` 已在 requirements，`Draft7Validator(params)` errors 取首条入 400 detail）。
- [ ] **Step 3: 权限点接入**：S17/S17b 路由 deps 加 `sandbox:act`（沿用 `sys_*` 角色校验既有姿势——照 `routers/ontology/ontology.py` 里 publish 端点的权限依赖写法）；无权限时走第 2 步 denied 而非 403（保证审计）。
- [ ] **Step 4: 运行 PASS** → **Step 5: Commit** — `"feat(sandbox): 行动门禁六步求值 + stepwise 两段式确认 S16-S18"`

---

### Task 7: AI 顾问（S20）——确定性证据收集 + LLM 解释

**Files:**
- Create: `backend/app/services/sandbox/sandbox_advisor_service.py`
- Modify: `backend/app/routers/sandbox/sandbox.py`（追加 S20）
- Test: `backend/tests/sandbox/test_advisor.py`

**Interfaces:**
- Consumes: Task 5 引擎只读查询（`load_world`/observation 检索）；`llm_json`（Task 4 同一入口）；三证据法即 MVP 决策记录 2 的「固定调用三个只读证据法」。
- Produces:
  - `SandboxAdvisorService(db, tenant_id)`：
    - `_evidence_world(scene_id, branch_id) -> str`——当前 Tick、实体概览（entity_code/object_code/risk_score/masked，props 仅键名）、KPI 最新值、目标状态。纯字符串拼装，不经 LLM。
    - `_evidence_trace(scene_id, branch_id, entity_code) -> list[dict]`——从目标实体沿 accepted causal_edge **反向**追溯（depth≤4，`(kind,code)` 固定序），返回命中链 `[{element_code, from, to, tick, title}]`（数据源 observation.edge_fired/rule_fired）。
    - `_evidence_observations(scene_id, branch_id, last_n=20) -> list[dict]`——最近 N 条 engine 观察。
    - `ask(scene_id, branch_id, question: str, model_id=None) -> dict`——组系统提示（沙箱上下文摘要 + 证据三段 + 「只引用证据中的实体与数值，不得编造；回答标注证据来源编号」）→ `llm_json` 期望 `{answer, cited_evidence:[1,2,3]}`；**LLM 失败降级**：直接返回 `{answer: 证据摘要拼接文本, degraded: true, cited_evidence: []}`，不抛异常（与 ontology_assistant 降级先例一致）。零写路径（A8：本服务不开任何 DB 写）。回答可溯源：`degraded=false` 时 `cited_evidence` 非空 → 单测断言。
  - 端点 S20 `POST /scenes/{id}/ask`：`{branch_id, question, model_id?}` → JSON（MVP 非 SSE——主规格 U8 收口前不引入第四种流式封装；spec §4.3 已列 SSE 为 P1）。

- [ ] **Step 1: 写失败测试**

```python
def test_ask_degrades_without_llm(db, monkeypatch):
    monkeypatch.setattr("app.services.sandbox.sandbox_advisor_service.llm_json",
                        lambda p, model_id=None: (_ for _ in ()).throw(RuntimeError("down")))
    r = svc.ask(SC, BR, "风险如何从 SUP006 传到 ORD012")
    assert r["degraded"] is True and r["answer"]           # 证据拼接文本非空

def test_ask_cites_trace_only_real_entities(db, monkeypatch):
    monkeypatch.setattr(..., lambda p, model_id=None: {"answer": "SUP006→FAC007→ORD012", "cited_evidence": [2]})
    r = svc.ask(SC, BR, "风险如何传导")
    assert r["degraded"] is False and set(r["cited_evidence"]) <= {1, 2, 3}

def test_advisor_has_no_write_methods(db):
    """A8/隔离面：dir(SandboxAdvisorService) 不含 commit 之外的写语义方法；
    源码文本断言：grep 本文件无 'db.add' / 'db.delete' / 'db.execute(update' / 'db.execute(delete'。"""
```

- [ ] **Step 2: 实现服务 + S20 端点（函数体 ≤6 行）** → **Step 3: 运行 PASS** → **Step 4: Commit** — `"feat(sandbox): AI 顾问只读证据三法 + LLM 解释降级 S20"`

---

### Task 8: 端到端旅程集成测试（验收 A1–A8 CI 化）+ 静态隔离断言

**Files:**
- Test: `backend/tests/sandbox/test_e2e_journey.py`
- Test: `backend/tests/sandbox/test_isolation_static.py`

**Interfaces:**
- Consumes: 全部前序任务（服务层直调为主，端点走 `client_a` 为辅）。
- Produces: spec §10 八条验收断言的 pytest 化（A1–A8 各至少一条断言，命名 `test_acceptance_a1` … `a8`）；MVP 走查脚本（spec §6 五旅程）的可执行版本。

- [ ] **Step 1: 旅程集成测试（spec §6 脚本逐行翻译）**

```python
def test_journey_supply_cut_full_chain(db, client_a):
    """旅程 2+4+5 合体：假取数克隆 3 实体 → S13 配 CE-001/CE-002/R-001/G-01（accept）→
    S17 断供 SUP006（allowed）→ S8 advance×5 → 断言：T2 FAC007 产能↓、T4 ORD012 风险↑、
    G-01 goal_eval 转 threatened、S21 健康度序列单调↓、S11 与未干预分支对比 delta==终值差、
    S20 ask 降级回答含 SUP006/FAC007/ORD012 字样、S18 审计含 allowed 行。
    异常路径（旅程 5）：masked 目标 GATE_DENIED_MASKED+审计；第 6 检查点 CHECKPOINT_LIMIT；
    推进超 tick_max → 400。"""

def test_acceptance_a1_replay_identity(db):
    """A1：同配置同行动序列推进 6 Tick → observation 全表指纹（sha256 of sorted json）
    → replay_to(0) → 重放 6 Tick → 指纹逐等。"""

def test_acceptance_a2_no_production_writes(db):
    """A2：跑完整旅程前后，对onto_ontology*/meta_* 每张表 SELECT count(*), md5(string_agg(row_text)) 
    diff 为空；源库断言：fake fetcher 记录的 SQL 全部 ~ '^SELECT' （无 DML）。"""

def test_acceptance_a7_static_scan():
    """A7：遍历 backend/app/services/sandbox/*.py 与 routers/sandbox/*.py 源码文本，
    不匹配 r'onto_ontology\w*\.(insert|update|delete)|meta_\w+\.(insert|update|delete)'
    | r'UPDATE\\s|DELETE\\s|INSERT\\s'（克隆 SQL 白名单文件 sandbox_clone_service.py 的
    build_select 除外——其产出仅 SELECT 前缀，测试内 assert sql.upper().startswith("SELECT")）。"""
```

- [ ] **Step 2: 运行** `python -m pytest tests/sandbox -v`（全套）→ PASS；全仓回归 `python -m pytest tests/ontology tests/dataops -v` 不破坏。
- [ ] **Step 3: 验收清单核对**——对照 spec §10 表逐条勾选：A1(旅程/a1) A2(a2) A3(旅程masked+Task6) A4(Task6 replay/stepwise) A5(Task5 上限+依赖) A6(Task5 compare) A7(静态) A8(Task4 D3+Task7 溯源)。任何一条无对应断言 → 回补测试。
- [ ] **Step 4: Commit** — `git add backend/tests/sandbox && git commit -m "test(sandbox): 端到端旅程与 A1-A8 验收断言 CI 化"`

---

## 与非后端范畴的接缝（本计划不含，勿在执行中扩张）

- **前端 `views/sandbox/` 八域组件**（spec §4.3）：另立前端 Implementation Plan（依赖本计划 S1–S21 冻结后的接口形状）；本计划交付即以后端 API 文档化收尾（docstring 即可，不产 OpenAPI 快照文件）。
- **SSE 进度流**：主规格 U8 三处封装选型收口前只做轮询（S8 同步返回即满足 MVP 单分支 ≤ tick_max Tick 推进耗时预期 <3s；超时再评估后台任务化，见 spec §8 P1）。
- **功能权限点种子**：`sandbox:scene:create/sandbox:run/sandbox:act/sandbox:delete` 四权限点的 `sys_*` 种子迁移如既有权限体系要求登记，并入 Task 6 Step 3 一并处理；具体登记方式以 `backend/app/models/system/` 现表为准。
