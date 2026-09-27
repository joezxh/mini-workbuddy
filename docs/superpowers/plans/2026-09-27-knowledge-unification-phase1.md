# 知识库统一化 Phase 1 收尾 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐并验收 spec `docs/superpowers/specs/2026-09-27-knowledge-unification-design.md` 的 Phase 1（阻断修复 + 统一模型 + 迁移 SQL），使 ORM / 启动期迁移 / 手动迁移 SQL 三者一致，并修正 spec 中与项目现实不符的表述。

**Architecture:** DB 仍是事实源，迁移走三层机制——ORM `create_all`（新表）、`backend/app/db/startup_migrations.py`（启动期幂等 ALTER/RENAME，权威）、`docs/sql/kms_unify_20260927.sql`（手动执行兜底/DBA 参考）。代码遵循 `api/v1 → services → repositories` 三层与 TenantMixin 租户隔离。

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0（declarative_base）+ pgvector + pytest；前端 Vue 3 + antd v6 + TypeScript + oxlint。

## 现状盘点（执行前必读，2026-09-27 实测）

P0 六项与统一模型**大部分已由并行会话完成**，以下为实测结论：

| spec 项 | 状态 | 证据 |
|---|---|---|
| P0-1 版本 diff/回滚（端点+API+组件接线） | ✅ 完成 | `wiki.py:224/241/255`、`api/wiki.ts:64/71`、`ArticleView.vue:82` 接线 VersionTimeline |
| P0-2 connectors 模型+注册+真实 sync | ✅ 完成 | `connector_record.py:36/77`、`router_registry.py:160`、`connector.py:203` 调 run_connector |
| P0-3 dataops select import | ✅ 完成 | `dataops.py:14` |
| P0-4 StandardManagement 编辑/删除 | ✅ 完成 | `StandardManagement.vue:77/89` |
| P0-5 RAG 索引 job_runner | ✅ 完成 | `article_service.py:242` |
| P0-6 wiki_admin/ontology 注册 | ✅ 完成 | `router_registry.py:163/166` |
| §3.1 WikiKnowledge type/枚举 | ✅ 完成 | `wiki_knowledge.py:19/40` |
| §3.2 KbCategory RENAME | ✅ 完成 | `models/kb/kb_category.py`（表名 kb_category） |
| §3.3 KbCollection.knowledge_id | ✅ 完成 | `kb_collection.py:21` |
| §4 迁移 SQL + startup_migrations | ✅ 完成（有缺列） | `docs/sql/kms_unify_20260927.sql`、`startup_migrations.py` |
| §9.2 WikiArticle OKF 五列 | ✅ 完成 | `wiki_article.py:63+` |
| 回归测试 | ✅ 12 passed | `tests/unit/test_kms_unify_phase1.py` |

**本计划要补的缺口（按优先级）：**

1. `WikiKnowledge` 缺 `index_mode`、`pipeline_config` 两列（spec §10.2；SQL 文件有 pipeline_config 无 index_mode，startup_migrations 两者皆无）
2. `KbSegment` ORM 缺 `chunk_type`/`parent_id`/`answer`/`keywords` 四列（SQL 与 startup_migrations 均已有，ORM 未同步 → 三层不一致）
3. `ArticleEdit.vue:118` 仍用 `page_size=1000` 列表遍历找 slug（G4 前端残留；`getArticle` API 已存在未用）
4. `WikiCategoryService` 类名未随模型改名（spec §3.2「类名同步改」残留）
5. spec 验收标准 5 / §4 引用 `schema.sql` 再生——**本项目不存在 schema.sql**，权威机制是 startup_migrations（需修正 spec 表述）

## Global Constraints

- 无 Alembic / 无 schema.sql：迁移权威 = `backend/app/db/startup_migrations.py`（幂等，启动执行）+ `docs/sql/kms_unify_20260927.sql`（手动兜底）
- 新增 Model 必须在 `app/db/init_models.py` import（否则 `create_all` 不拾取）
- 所有迁移 SQL 必须幂等（`ADD COLUMN IF NOT EXISTS` / 先检查再执行）
- 存量数据零迁移原则：新列 nullable 或带 server_default，旧行自动兼容
- Service 层禁止 `with self.db.begin()`；用 flush + commit
- 需要租户隔离的模型继承 `TenantMixin`
- Service/Router 类与模型类命名同步（模型已 `Kb` 前缀化的，服务层跟随）
- 前端 lint 用 `npm run lint`（oxlint），不是 eslint
- pytest 基线：`tests/unit/test_kms_unify_phase1.py` 当前 12 passed，只增不减

---

### Task 1: `WikiKnowledge` 补 `index_mode` / `pipeline_config` 列

**Files:**
- Modify: `backend/app/models/wiki/wiki_knowledge.py`
- Test: `backend/tests/unit/test_kms_unify_phase1.py`

**Interfaces:**
- Produces: `WikiKnowledge.index_mode: str`（默认 `'high_quality'`，Phase 2 检索分支按它路由）、`WikiKnowledge.pipeline_config: dict|None`（Phase 2 摄取编排消费）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_kms_unify_phase1.py` 的 `test_collection_has_knowledge_link` 之后追加：

```python
def test_knowledge_index_mode_and_pipeline_config_columns():
    """spec §10.2：索引模式（economy 零 embedding）与摄取编排列。"""
    col = WikiKnowledge.__table__.c["index_mode"]
    assert col.nullable is False
    assert "high_quality" in str(col.server_default.arg if col.server_default else "")
    assert "pipeline_config" in WikiKnowledge.__table__.c
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend; python -m pytest tests/unit/test_kms_unify_phase1.py::test_knowledge_index_mode_and_pipeline_config_columns -q`
Expected: FAIL（KeyError: 'index_mode'）

- [ ] **Step 3: 实现模型列**

`backend/app/models/wiki/wiki_knowledge.py` 顶部 import 行增加 JSONB：

```python
from sqlalchemy import Boolean, Column, BigInteger, String, Text, Integer, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import JSONB
```

`multimodal_enabled` 列定义之后追加：

```python
    # 索引模式（spec §10.2，Dify 对齐）：economy=仅关键词全文，摄取不消耗 embedding
    index_mode = Column(
        String(16), nullable=False, server_default='high_quality',
        comment='索引模式: high_quality=向量+全文 | economy=仅关键词，不消耗 embedding',
    )
    # 摄取编排（spec §10.7）
    pipeline_config = Column(
        JSONB, nullable=True,
        comment='摄取编排: {clean:[...], chunker:{type,params}, index:{...}}',
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend; python -m pytest tests/unit/test_kms_unify_phase1.py -q`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/wiki/wiki_knowledge.py backend/tests/unit/test_kms_unify_phase1.py
git commit -m "feat(kms): kms_knowledge 补 index_mode/pipeline_config 列（spec §10.2）"
```

---

### Task 2: `KbSegment` ORM 补类型化切片四列

**Files:**
- Modify: `backend/app/models/kb/kb_segment.py`
- Test: `backend/tests/unit/test_kms_unify_phase1.py`

**Interfaces:**
- Produces: `KbSegment.chunk_type: str`、`KbSegment.parent_id: int|None`（自引用 FK）、`KbSegment.answer: str|None`、`KbSegment.keywords: list|None`——Phase 2 文档/Q&A/父子分段检索全部消费这四列；DB 侧列已由 startup_migrations/SQL 建好，本任务消除 ORM 与 DB 的漂移

- [ ] **Step 1: 写失败测试**

`test_kms_unify_phase1.py` 追加：

```python
def test_segment_typed_columns_added():
    """spec §10.2：kb_segment 类型化切片列（DB 侧已有，ORM 必须同步）。"""
    from app.models.kb.kb_segment import KbSegment

    for col in ("chunk_type", "parent_id", "answer", "keywords"):
        assert col in KbSegment.__table__.c
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend; python -m pytest tests/unit/test_kms_unify_phase1.py::test_segment_typed_columns_added -q`
Expected: FAIL（KeyError: 'chunk_type'）

- [ ] **Step 3: 实现模型列**

`backend/app/models/kb/kb_segment.py`：

import 区改为（增加 ForeignKey 与 Index）：

```python
from sqlalchemy import (
    BigInteger, Column, ForeignKey, Index, Integer, String, Text, TIMESTAMP,
    UniqueConstraint, func,
)
```

`class_uris` 列之后、`created_at` 之前追加：

```python
    # ── 类型化切片（spec §10.2，Dify 对齐）────────────────────────────────
    chunk_type = Column(
        String(16), nullable=False, server_default='text',
        comment='切片类型: text|qa|table_row|image|parent|child',
    )
    # 父子分段：父块 chunk_type='parent'（embedding 为 NULL），子块指向父块
    parent_id = Column(
        BigInteger, ForeignKey('kb_segment.id', ondelete='CASCADE'),
        nullable=True, index=True, comment='父子分段: 子块 → 父块',
    )
    answer = Column(
        Text, nullable=True,
        comment='chunk_type=qa: 完整答案（content=问题，仅问题做 embedding）',
    )
    keywords = Column(JSONB, nullable=True, comment='手动关键词（全文检索加权）')
```

`__table_args__` 元组追加父块索引（保留原 UniqueConstraint）：

```python
    __table_args__ = (
        UniqueConstraint(
            "collection", "document_id", "chunk_index", name="uq_kb_segment"
        ),
        Index("idx_kb_segment_parent", "parent_id"),
    )
```

注意：`answer` 用到 `Text`、`keywords` 用到 `JSONB`，两者已在文件现有 import 中；自引用 FK 的字符串形式 `'kb_segment.id'` 在本表定义内安全（SQLAlchemy 运行时解析）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend; python -m pytest tests/unit/test_kms_unify_phase1.py -q`
Expected: 14 passed

- [ ] **Step 5: 回归确认既有 kb_app 写入路径不受影响**

Run: `cd backend; python -m pytest tests -q -k "kb or segment" 2>&1 | Select-Object -Last 5`
Expected: 无新增失败（新列均 nullable/server_default，旧构造函数无需感知；若出现历史遗留失败，用 `git stash` 前后对比确认与本次改动无关并记录）

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/kb/kb_segment.py backend/tests/unit/test_kms_unify_phase1.py
git commit -m "feat(kms): kb_segment ORM 补 chunk_type/parent_id/answer/keywords（消除 DB 漂移）"
```

---

### Task 3: startup_migrations 与手动 SQL 补齐缺列

**Files:**
- Modify: `backend/app/db/startup_migrations.py:85`（`multimodal_enabled` 行之后）
- Modify: `docs/sql/kms_unify_20260927.sql:22`（001b 块 `multimodal_enabled` COMMENT 之后）
- Test: 无新测试（幂等 SQL，由 Task 5 全量 pytest 与启动验证覆盖）

**Interfaces:**
- Consumes: Task 1 的 `index_mode`/`pipeline_config` 列名（必须逐字符一致）

- [ ] **Step 1: startup_migrations 补 2 条 ALTER**

`_COLUMN_MIGRATIONS` 列表中，`"ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS multimodal_enabled ..."` 行之后插入：

```python
    "ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS index_mode VARCHAR(16) NOT NULL DEFAULT 'high_quality'",
    "ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS pipeline_config JSONB",
```

- [ ] **Step 2: 手动 SQL 文件 001b 块补 index_mode**

`docs/sql/kms_unify_20260927.sql` 中 `--COMMENT ON COLUMN kms_knowledge.multimodal_enabled ...` 行之后插入：

```sql
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS index_mode VARCHAR(16) NOT NULL DEFAULT 'high_quality';
COMMENT ON COLUMN kms_knowledge.index_mode IS '索引模式: high_quality=向量+全文 | economy=仅关键词，不消耗 embedding';
```

- [ ] **Step 3: 回滚脚本同步**

同文件末尾回滚区，`-- ALTER TABLE kms_knowledge DROP COLUMN IF EXISTS pipeline_config,` 行改为：

```sql
-- ALTER TABLE kms_knowledge DROP COLUMN IF EXISTS pipeline_config, DROP COLUMN IF EXISTS index_mode,
```

- [ ] **Step 4: 验证 startup_migrations 可执行且幂等**

Run: `cd backend; python -c "from app.db.startup_migrations import _COLUMN_MIGRATIONS; sqls=[s for s in _COLUMN_MIGRATIONS if 'kms_knowledge' in s]; [print(s) for s in sqls]"`
Expected: 输出含 `type` / `kb_format` / `multimodal_enabled` / `index_mode` / `pipeline_config` 五条 ALTER（index_mode 与 pipeline_config 为本次新增）

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/startup_migrations.py docs/sql/kms_unify_20260927.sql
git commit -m "feat(kms): 迁移链补 index_mode/pipeline_config（startup_migrations + 手动 SQL + 回滚脚本）"
```

---

### Task 4: `ArticleEdit.vue` 消除 slug hack（G4 前端残留）

**Files:**
- Modify: `frontend/src/views/kms/wiki/ArticleEdit.vue:94`（import 行）与 `:110-132`（loadArticle）

**Interfaces:**
- Consumes: `getArticle(id: number)`（`api/wiki.ts:23`，后端 `GET /wiki/articles/{id}` 已上线）

- [ ] **Step 1: 修改 import**

第 94 行：

```ts
// 原：import { getArticleBySlug, updateArticle, listCategories } from '@/api/wiki'
import { getArticle, updateArticle, listCategories } from '@/api/wiki'
```

（`getArticleBySlug` 在本文件仅被删除的 hack 使用，改后若无其他引用即移除；`oxlint` 会报 unused import 作为验证手段。）

- [ ] **Step 2: 重写 loadArticle**

110-132 行整体替换为：

```ts
async function loadArticle() {
  const articleId = Number(route.params.id)
  if (!Number.isFinite(articleId) || articleId <= 0) {
    message.error(t('kmsWiki.notFound'))
    router.push('/wiki')
    return
  }
  try {
    // 直接按 ID 获取（后端 GET /wiki/articles/{id}，G4：消除 page_size=1000 列表遍历 hack）
    article.value = await getArticle(articleId)
  } catch (e) {
    message.error(t('wikiMgmt.art.loadFailed'))
    router.push('/wiki')
  }
}
```

（`request` 拦截器已解包 `response.data`，`await getArticle(id)` 直接得到文章对象，与原 `detailRes` 用法一致。）

- [ ] **Step 3: lint 验证**

Run: `cd frontend; npm run lint 2>&1 | Select-Object -Last 10`
Expected: 无新增 error（特别确认无 `getArticleBySlug` unused 告警——若仓库其他文件仍用它则保留其导出，仅本文件不再引用）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/kms/wiki/ArticleEdit.vue
git commit -m "fix(kms): ArticleEdit 改用 getArticle(id)，消除 1000 条列表遍历 hack（G4）"
```

---

### Task 5: `WikiCategoryService` → `KbCategoryService` 改名

**Files:**
- Modify: `backend/app/services/wiki/category_service.py`（类定义，L36）
- Modify: `backend/app/routers/wiki/wiki_admin.py`（import + 5 处调用）

**Interfaces:**
- Produces: `WikiCategoryService` 的唯一公开新名 `KbCategoryService`，构造签名不变 `(db: Session)`，方法集不变（create/tree/get/update/move/delete）——后续 Task/Phase 2 一律引用新名

- [ ] **Step 1: 确认引用面完整**

Run: `cd backend; git grep -l "WikiCategoryService"`
Expected: 仅 `app/services/wiki/category_service.py` 与 `app/routers/wiki/wiki_admin.py`（若出现第三个文件，一并纳入本任务替换）

- [ ] **Step 2: 全量替换**

两个文件内 `WikiCategoryService` → `KbCategoryService`（类定义、import、所有调用点）。

- [ ] **Step 3: 回归**

Run: `cd backend; python -m pytest tests/unit/test_kms_unify_phase1.py -q; git grep -n "WikiCategoryService" || echo "no residual"`
Expected: 14 passed；`no residual`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/wiki/category_service.py backend/app/routers/wiki/wiki_admin.py
git commit -m "refactor(kms): WikiCategoryService 更名 KbCategoryService，对齐 kb_category 模型（spec §3.2）"
```

---

### Task 6: spec 表述修正（schema.sql 机制不存在于本项目）

**Files:**
- Modify: `docs/superpowers/specs/2026-09-27-knowledge-unification-design.md`

**Interfaces:**
- Consumes: 实测事实——项目无 `schema.sql`/Alembic，迁移权威是 `startup_migrations.py` + `docs/sql/` 手动脚本

- [ ] **Step 1: 修正 §4 迁移说明**

将 §4 末尾：

```
- `schema.sql` 按文件末尾命令再生；`kms_article.category_id` FK 补充放在 schema 再生后核对（create_all 不改已有表，需 ALTER 手动补）。
```

替换为：

```
- 本项目**无 schema.sql / Alembic**（设计早期引用了其他项目的惯例，实测不存在）：迁移权威 = `backend/app/db/startup_migrations.py`（启动期幂等执行）+ `docs/sql/kms_unify_20260927.sql`（不重启服务的手动兜底 / DBA 复核）；§10.2 三张新表（kb_document / kb_segment_asset / kms_external_kb_endpoint）由 Phase 2 模型落地时 `create_all` 建表，Phase 1 不产出其 DDL。
```

- [ ] **Step 2: 修正验收标准第 5 条**

将：

```
5. `schema.sql` 再生后与 ORM 定义一致。
```

替换为：

```
5. `startup_migrations.py` 幂等重跑后，DB schema 与 ORM 定义一致（`docs/sql/kms_unify_20260927.sql` 与之逐条对应，含回滚脚本）。
```

- [ ] **Step 3: 修正验收标准第 9 条**

将：

```
9. 新表（kb_document / kb_segment_asset / kms_external_kb_endpoint）`schema.sql` 再生后与 ORM 定义一致；存量 kb_segment 行 chunk_type 默认 'text'、既有检索行为回归无差异。
```

替换为：

```
9. Phase 2 新表（kb_document / kb_segment_asset / kms_external_kb_endpoint）由模型 create_all 建表且与 ORM 定义一致；存量 kb_segment 行 chunk_type 默认 'text'、既有检索行为回归无差异。
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-09-27-knowledge-unification-design.md
git commit -m "docs(spec): 修正迁移机制表述——startup_migrations 为权威，无 schema.sql"
```

---

### Task 7: Phase 1 终验（全量测试 + 前端构建 + 验收核对）

**Files:**
- 无新文件；产出验收记录（写入 PR/commit message，不新增文档）

- [ ] **Step 1: 后端全量测试**

Run: `cd backend; python -m pytest -q 2>&1 | Select-Object -Last 10`
Expected: 记录结果；`test_kms_unify_phase1.py` 全过。若有失败：先用 `git stash` 复跑区分「本次引入」vs「历史遗留」——本次引入必须修复后才可继续；历史遗留记录到交付说明（spec §11.1 要求基线只增不减）。

- [ ] **Step 2: 前端 lint + build**

Run: `cd frontend; npm run lint 2>&1 | Select-Object -Last 5; npm run build 2>&1 | Select-Object -Last 5`
Expected: lint 无 error；build 成功（版本链组件 `VersionTimeline/VersionDiffView/VersionRollbackButton` 编译通过即证明 P0-1 断链已闭合）。

- [ ] **Step 3: 对照 spec §11 验收清单逐条勾选**

逐条核对 §11.1–11.5（Phase 1 范围）：

1. pytest 全绿 / 基线只增不减 —— Step 1 结果
2. 六项 P0 复验 —— 现状盘点表（全部 ✅）
3. 迁移 SQL 语义正确 —— Task 3 输出核对（五条 kms_knowledge ALTER + kb_type 回填 + 两张连接器表）
4. 三类型闭环 / 真实 sync —— 属 Phase 2 前端任务，Phase 1 记「后端就绪」
5. 迁移一致性 —— Task 1/2/3 完成即满足（ORM = startup_migrations = 手动 SQL）

- [ ] **Step 4: 更新 spec 状态行并提交**

`docs/superpowers/specs/2026-09-27-knowledge-unification-design.md` 头部状态行改为：

```
> 状态：已评审 · Phase 1 已实施并通过验收（2026-09-27，见 docs/superpowers/plans/2026-09-27-knowledge-unification-phase1.md）
```

```bash
git add docs/superpowers/specs/2026-09-27-knowledge-unification-design.md
git commit -m "docs(spec): Phase 1 验收完成标记"
```

---

## 后续计划（不在本文件范围）

- **Phase 2 计划**（另行编写）：KbDocument/KbSegmentAsset/ExternalKbEndpoint 模型 + create_all、kb_format 校验矩阵与创建后不可切换、文档上传全链路 + retrieve 统一端点、ParentChildChunker、`KnowledgeBaseManager.vue` 创建向导与各形态右区、KB 子应用认证收口、OKF 服务层三端点、语雀/Notion 连接器 + APScheduler。
- **Phase 3 计划**（另行编写）：HNSW 索引、Redis 缓存、RBAC、多模态/表格/qa/proxy 全量、pipeline dry-run、index_mode economy→high_quality 回填任务。
