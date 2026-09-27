# 知识库管理模块统一化设计（三类知识库整合）

> 日期：2026-09-27
> 状态：已评审（基于用户确认的 3+2 项关键决策）
> 输入材料：`docs/kms-9-27.md`、`docs/kms-3-9-27.md`、`docs/kms-2-9-27.md`
> 范围：`backend/app/models/{wiki,kb,connectors}`、`backend/app/routers/*`、`frontend/src/views/kms` + `views/admin/knowledge`

---

## 1. 背景与问题

MinWorkBuddy 现存三类知识库，各自独立建表、独立前端入口，且存在多处断链：

| 类型 | 现有载体 | 后端状态 | 前端状态 |
|---|---|---|---|
| A: LLM Wiki | `kms_knowledge` / `kms_category` / `kms_article`(pgvector) / `kms_article_version` | 服务层完整；RAG 索引裸线程；版本回滚零路由引用 | 最成熟；版本 diff/回滚组件断链 |
| B: 通用 KB | `kb_collection` / `kb_segment` / `kb_ref` + `meta_data_source` 等 | pgvector 混检/ sql_guard 质量高；KB 子应用无认证、自带 get_db | 约半数操作为假实现 |
| C: 外部集成 | `meta_connector_ingest` / `meta_connector_sync_state`（落库层） | connectors 路由未注册 + import 不存在的 `ConnectorInstance/ConnectorSyncLog`（启用即崩） | `InstanceManagement.vue` 全部请求 routerMissing |

核心诉求：以 `kms_knowledge` 为统一一级容器，`kms_category` 重构为通用 `kb_category` 二级分类，三级内容层按类型动态选择，前端提供统一工作台入口。

## 2. 已确认决策

1. **容器策略 A**：`WikiKnowledge`（kms_knowledge）加 `type` 字段作为唯一一级容器；`kb_collection` 加 `knowledge_id` FK；外部连接器实例表新建并同样挂 `knowledge_id`。
2. **分类重构**：`ALTER TABLE kms_category RENAME TO kb_category` 直接改造，代码同步改类名，历史数据天然兼容。
3. **type 表示**：整数枚举（`1=llm-wiki, 2=general-kb, 3=external-kb`），代码内定义 `KnowledgeType(IntEnum)`。
4. **connector_type 统一到 registry**：以 `app/connectors/registry.py`（http/dingtalk/feishu/wecom）为唯一事实源；notion/confluence/web/s3 作为别名映射到 http 连接器配置，不再维护两套类型体系。
5. **统一工作台位置**：`frontend/src/views/kms/`（与现有 wiki 同域）。

## 3. 数据模型设计

### 3.1 `WikiKnowledge`（kms_knowledge）— 修改

新增列与索引：

```python
type = Column(
    Integer, nullable=False, server_default='1',
    comment='知识库类型: 1=llm-wiki 2=general-kb 3=external-kb',
)
# __table_args__ 增加
Index('idx_kms_knowledge_tenant_type', 'tenant_id', 'type'),
```

- `server_default='1'`：存量行自动归为类型 A，历史数据零迁移。
- 常量定义（新文件 `app/models/wiki/kb_types.py` 或放 `wiki_knowledge.py` 内）：

```python
class KnowledgeType(IntEnum):
    LLM_WIKI = 1
    GENERAL_KB = 2
    EXTERNAL_KB = 3
```

### 3.2 `KbCategory`（kb_category）— RENAME 改造

- 表：`kms_category` → `kb_category`；索引 `idx_wiki_category_*` 同步 RENAME。
- 类：`WikiCategory` → `KbCategory`；文件 `models/wiki/wiki_category.py` → `models/kb/kb_category.py`；全仓 import 同步更新。
- 新增列：

```python
kb_type = Column(
    Integer, nullable=True,
    comment='冗余的知识库类型（随 knowledge_id 回填；null=未归类）',
)
```

- 保留 `knowledge_id` FK（→ kms_knowledge.id）、`parent_id` 自引用、`owl_class_uri`（类型 A 专用，类型 B/C 留空）。
- `kms_article.category_id` 补真实 FK → `kb_category.id`（现为裸列）。

### 3.3 `KbCollection`（kb_collection）— 挂接容器

```python
knowledge_id = Column(
    BigInteger, ForeignKey('kms_knowledge.id', ondelete='SET NULL'),
    nullable=True, index=True, comment='所属统一知识库容器（type=2）',
)
```

- nullable：过渡期允许旧 collection 无容器；类型 B 容器创建流程中同步生成 `kb_<uuid>` collection 并绑定。
- `dimensions` 语义不变。

### 3.4 `ConnectorInstance`（kms_connector_instance）— 新表

```python
class ConnectorInstance(Base, TenantMixin):
    __tablename__ = 'kms_connector_instance'

    id            BigInteger PK
    knowledge_id  FK kms_knowledge.id (SET NULL), nullable, index   # type=3 容器
    code          String(200), nullable=False                        # 租户内唯一 (uq: tenant_id, code)
    name          String(200), nullable=False
    connector_type String(32), nullable=False   # registry 枚举: http|dingtalk|feishu|wecom
    config        JSONB, nullable               # 连接参数；敏感字段 Fernet 加密（沿用 DataOps crypto 惯例）
    sync_enabled  Boolean, server_default='0'
    sync_interval_min Integer, server_default='60'
    target_collection String(128), nullable      # 落库目标 → kb_collection.name
    status        String(32), server_default='active'  # active|error|disabled
    last_sync_at  TIMESTAMP, nullable
    error_detail  Text, nullable
    creator_id / updater_id BigInteger, nullable
    created_at / updated_at TIMESTAMP
```

- 修复 `routers/connectors/connector.py` 的 import 崩溃（该路由现已按此模型实现 CRUD/sync/sync-jobs 逻辑，只缺模型与注册）。
- 路由内 `CONNECTOR_PARAMS_CONFIG` 中 notion/confluence/web/s3 保留为**声明式表单 + 别名映射层**：表单字段仍按外部产品语义渲染，提交时 `adapter_alias` 映射到 registry 类型（如 notion → http + base_url/token 适配）。`connector_type` 落库值恒为 registry 枚举。

### 3.5 `ConnectorSyncLog`（kms_connector_sync_log）— 新表

```python
class ConnectorSyncLog(Base, TenantMixin):
    __tablename__ = 'kms_connector_sync_log'

    id            BigInteger PK
    instance_id   FK kms_connector_instance.id (CASCADE), index
    connector_type String(32), nullable=False
    status        String(32), server_default='pending'  # pending|running|success|failed
    added / updated / deleted  Integer, server_default='0'
    cursor_value  String(255), nullable                  # 本次同步后的增量游标
    duration_ms   Integer, nullable
    error_detail  Text, nullable
    started_at / finished_at TIMESTAMP, nullable
    creator_id    BigInteger, nullable
    created_at    TIMESTAMP
```

- `POST /{id}/sync` 改为真实调 `app/connectors/runner.run_connector`（同步触发 + job 行记录真实状态，失败写 failed），**不再预写 success 日志**。
- `meta_connector_ingest` / `meta_connector_sync_state` 保留不动（记录落库层），与新实例层职责分离。

### 3.6 模型注册

- `app/models/wiki/__init__.py`、`app/models/kb/__init__.py`、`app/models/connectors/__init__.py` 及 `app/db/init_models.py`：新增 `KnowledgeType`、`KbCategory`（换位置）、`ConnectorInstance`、`ConnectorSyncLog` 的 import 与 `__all__`。

## 4. 数据迁移 SQL（`docs/sql/`，无 Alembic，按序手动执行）

`docs/sql/kms_unify_20260927.sql`：

```sql
-- 001 统一容器 type
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS type INTEGER NOT NULL DEFAULT 1;
COMMENT ON COLUMN kms_knowledge.type IS '知识库类型: 1=llm-wiki 2=general-kb 3=external-kb';
CREATE INDEX IF NOT EXISTS idx_kms_knowledge_tenant_type ON kms_knowledge (tenant_id, type);

-- 002 分类表改造
ALTER TABLE kms_category RENAME TO kb_category;
ALTER INDEX IF EXISTS idx_wiki_category_slug   RENAME TO idx_kb_category_slug;
ALTER INDEX IF EXISTS idx_wiki_category_parent RENAME TO idx_kb_category_parent;
ALTER TABLE kb_category ADD COLUMN IF NOT EXISTS kb_type INTEGER;
COMMENT ON COLUMN kb_category.kb_type IS '冗余的知识库类型（随 knowledge_id 回填；null=未归类）';
UPDATE kb_category c SET kb_type = k.type FROM kms_knowledge k WHERE c.knowledge_id = k.id;

-- 003 kb_collection 挂接容器
ALTER TABLE kb_collection ADD COLUMN IF NOT EXISTS knowledge_id BIGINT REFERENCES kms_knowledge(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_kb_collection_knowledge ON kb_collection (knowledge_id);

-- 004 外部连接器实例层（建表 DDL 以 ORM create_all 再生 schema.sql 为准，此处为手动执行兜底）
-- CREATE TABLE kms_connector_instance (...); CREATE TABLE kms_connector_sync_log (...);
```

- `schema.sql` 按文件末尾命令再生；`kms_article.category_id` FK 补充放在 schema 再生后核对（create_all 不改已有表，需 ALTER 手动补）。
- 回滚脚本：反向 RENAME + DROP COLUMN（附同文件注释区）。

## 5. API 路由规划（统一前缀 `/api/v1`，全部走主应用 get_db + get_current_user）

| 类型 | 端点 | 说明 |
|---|---|---|
| 统一 | `GET /knowledges?type=&page=&page_size=` | 列表（新增分页，当前全量返回） |
| 统一 | `POST /knowledges` / `PUT /knowledges/{id}` / `DELETE /knowledges/{id}` | 创建时按 type 校验；type=2 同步建 collection；type=3 仅占位容器 |
| 统一 | `GET /kb-categories/tree?knowledge_id=` / `POST` / `PUT` / `DELETE` | 通用二级分类（原 wiki/categories 迁移，保留旧路径一个过渡版本） |
| A | 现有 `/wiki/articles` CRUD + `/search` + `/ask` | 不变 |
| A | `GET /wiki/articles/{id}` | 新增，消除前端 slug hack（G4） |
| A | `GET /wiki/articles/{id}/versions/{v}/diff?target=` | 新增，复用 version_service |
| A | `POST /wiki/articles/{id}/rollback` | 新增，非破坏式回滚（生成 max+1 新版本） |
| B | `GET/POST /kb/collections`、文档上传/分割/检索（收敛 kb_app 子应用） | 认证与主 get_db 收口，废除 X-Tenant-Id 自带头 |
| C | `GET/POST /connectors`、`GET /connectors/params-config`、`PUT/DELETE /connectors/{id}` | 路由注册进 router_registry |
| C | `POST /connectors/{id}/sync`、`GET /connectors/sync-jobs` | 真实 run_connector + 分页 |

注册位置：`app/core/router_registry.py` 补 `connectors`（及 wiki_admin / ontology 视 P2 决策）。

## 6. 前端统一工作台（views/kms/）

新组件 `frontend/src/views/kms/KnowledgeBaseManager.vue`：

```
┌─ Tab: LLM Wiki | 通用 KB | 外部集成        （按 type 过滤）
├─ 左树: 知识库(kms_knowledge, 按 type) → kb_category 分类（右键 CRUD）
└─ 右区:
   type A → 文章列表表（复用现有 index.vue 内列表逻辑，后续拆分 ArticleListTable）
   type B → collection/文档/切片管理 + 检索测试（复用 admin/knowledge/kb 组件）
   type C → 连接器实例表 + 同步作业（复用 external/InstanceManagement + SyncJobs）
```

- 注册：`componentMap.ts` 新增 `kg-knowledge-manager` 键挂入控制台；`/wiki` 原路由保留为类型 A 深链。
- API 层：新增 `api/kb.ts`（统一容器 + 分类）；`api/externalKb.ts` 类型枚举改为 registry 四类（http/dingtalk/feishu/wecom）+ 别名映射。
- 顺手修复接线：`ArticleView` 版本抽屉接入 `VersionTimeline`（依赖 P0-1 的 diff/rollback API）。

## 7. P0 阻塞级修复清单（Phase 1 范围）

| # | 问题（出处） | 修复 |
|---|---|---|
| 1 | 版本 diff/回滚断链（kms-3 §四.1） | 补 3 个端点 + `api/wiki.ts` 补 `getArticle/diffArticle/rollbackArticle` + 接线 VersionTimeline |
| 2 | connectors import 崩溃 + 未注册（kms-3 §四.2） | 新建 §3.4/3.5 两模型 + registry 注册路由 + sync 真实化 |
| 3 | `dataops.py:261` 缺 select import（kms-3 §四.3） | 一行修复 |
| 4 | `StandardManagement` 编辑调 create（kms-3 §四.5） | 编辑走 PUT，删除接 DELETE |
| 5 | G1 RAG 索引裸线程（kms-9 §1.4 / kms-3 §四.8） | `article_service._enqueue_index` 改 `job_runner.run_in_background` + 独立 Session |
| 6 | wiki_admin/ontology 路由 404（kms-3 §四.4） | 注册路由；前端入口随 Phase 2 工作台接通 |

## 8. 实施路线图

**Phase 1（本周）— 阻断修复 + 统一模型**
P0 六项；§3 模型代码；§4 迁移 SQL + schema.sql 再生；`GET /articles/{id}` 等 3 个版本端点；pytest 全绿。

**Phase 2（下周）— 统一分类 + 前端导航**
kb_category 全面切换（后端 service/router + 前端树）；`KnowledgeBaseManager.vue` 上线；KB 子应用认证收口；语雀连接器（OAuth2ApiConnector 模式）+ Notion 专属连接器（落地后取消 http 别名）；APScheduler 消费 `sync_interval_min`。

**Phase 3（下月）— 性能 + 权限 + 体验**
HNSW 索引（`m=16, ef_construction=64`）迁移脚本 + 10 万级 P95 < 100ms 验收；Redis 分类树/知识库列表缓存（TTL 1h，写失效）；RBAC 权限点（Wiki/SQL/ExternalKb）；wiki RAG 分块（QaChunker → 复用 `kb_segment`，单向量降级 fallback）；`/ask` 消 N+1 + SSE 流式；前端去重（`r.data||r` 拦截器下沉、DataSourceSelect 抽取、消灭 window.prompt）。

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| RENAME 影响未知的存量 FK/视图依赖 | 迁移前 `\d kms_category` 核对依赖；`schema.sql` 再生后 diff 核对 |
| create_all 不会给已有表加列 | 迁移 SQL 以 ALTER 显式执行，schema.sql 仅作权威参考 |
| 连接器别名映射语义偏差（notion 分页模型 ≠ http 通用分页） | Phase 1 仅落实例 CRUD + 手动 sync；notion 专属拉取逻辑在 Phase 2 补 `NotionApiConnector` 后取消别名 |
| 前端双入口（/wiki 与工作台）造成维护分叉 | /wiki 保留为深链，列表逻辑组件化后两处共用 |

## 10. 验收标准

1. `pytest` 全绿（当前基线 108 passed 只增不减）。
2. 三份报告中全部 🔴 P0 项在 Phase 1 结束后复验通过（启用对应前端组件不再报 routerMissing / 编译失败）。
3. 迁移 SQL 在 staging 库执行后：存量 wiki 知识库 type=1、分类树完整、kb_category.kb_type 回填正确。
4. 统一工作台三种类型均可完成一次「建容器 → 建分类 → 进详情」闭环；类型 C 可完成一次真实 sync 且日志状态真实。
5. `schema.sql` 再生后与 ORM 定义一致。
