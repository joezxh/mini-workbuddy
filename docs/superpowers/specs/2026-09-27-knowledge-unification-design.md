# 知识库管理模块统一化设计（三类知识库整合）

> 日期：2026-09-27
> 状态：已评审（基于用户确认的 3+2 项关键决策）
> 输入材料：`docs/kms-9-27.md`、`docs/kms-3-9-27.md`、`docs/kms-2-9-27.md`；Dify 知识库六类分类材料（2026-09-27，见 §10）
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
6. **kb_format 二级形态（Dify 对齐，详见 §10）**：三容器不变；type=2 增加 `document|table|qa` 形态（多模态为 document 上的开关），type=3 增加 `connector|proxy` 形态；知识库实例创建后形态不可切换（对齐 Dify「选定数据源后不可切换」）。

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

-- 005 Dify 对齐二级形态（§10.2；新表 kb_document/kb_segment_asset/kms_external_kb_endpoint 走 create_all，此处仅存量表加列）
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS kb_format VARCHAR(16);
COMMENT ON COLUMN kms_knowledge.kb_format IS '二级形态: type=2 → document|table|qa; type=3 → connector|proxy; type=1 为 NULL';
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS index_mode VARCHAR(16) NOT NULL DEFAULT 'high_quality';
COMMENT ON COLUMN kms_knowledge.index_mode IS '索引模式: high_quality=向量+全文 | economy=仅关键词，不消耗 embedding';
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS multimodal_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS pipeline_config JSONB;
ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(16) NOT NULL DEFAULT 'text';
ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS parent_id BIGINT REFERENCES kb_segment(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_kb_segment_parent ON kb_segment (parent_id);
ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS answer TEXT;
ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS keywords JSONB;
ALTER TABLE kb_collection ADD COLUMN IF NOT EXISTS schema_config JSONB;
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

> B/C 类型的功能增强端点（文档上传/分段编辑/统一检索测试/table/qa/multimodal/proxy/pipeline dry-run）见 §10.5。

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
P0 六项；§3 模型代码（含 §9.2 WikiArticle OKF 增列）；§4 迁移 SQL + schema.sql 再生；`GET /articles/{id}` 等 3 个版本端点；pytest 全绿。

**Phase 2（下周）— 统一分类 + 前端导航 + OKF 合规 + 文档摄取链路**
kb_category 全面切换（后端 service/router + 前端树）；`KnowledgeBaseManager.vue` 上线（含 kb_format 创建向导骨架）；KB 子应用认证收口；**§10 文档摄取全链路**：kb_document/kb_segment 加列与新表落地、`POST /documents`（上传→解析→清洗→分块→embedding→落库→状态回写）、`POST /retrieve` 统一检索端点、ParentChildChunker 父子分段、文档列表/分段详情前端；语雀连接器（OAuth2ApiConnector 模式）+ Notion 专属连接器（落地后取消 http 别名）；APScheduler 消费 `sync_interval_min`；OKF 服务层 + 3 个端点 + 前端导出/导入/预览入口（§9.3–9.5）。

**Phase 3（下月）— 性能 + 权限 + 体验 + Dify 形态全量**
HNSW 索引（`m=16, ef_construction=64`）迁移脚本 + 10 万级 P95 < 100ms 验收；Redis 分类树/知识库列表缓存（TTL 1h，写失效）；RBAC 权限点（Wiki/SQL/ExternalKb）；wiki RAG 分块（QaChunker → 复用 `kb_segment`，单向量降级 fallback）；`/ask` 消 N+1 + SSE 流式；前端去重（`r.data||r` 拦截器下沉、DataSourceSelect 抽取、消灭 window.prompt）；**§10 剩余形态**：table（导入/字段映射/行级 CRUD/db_table 直连定时同步）、qa（批量导入导出/启停）、multimodal（Vision embedding + 图搜）、proxy（外部检索代理转发）、pipeline dry-run（§10.7）。

## 9. OKF 合规层（llm-wiki 增强，对齐 Google Open Knowledge Format v0.2）

> 规范原文：`GoogleCloudPlatform/knowledge-catalog` → `okf/SPEC.md`（v0.2，supersede v0.1）。
> 定位：OKF（Open Knowledge Format）是 Karpathy LLM-Wiki 理念的厂商中立标准化——Markdown + YAML frontmatter、文件即知识库、Git 可管理、无 SDK/运行时依赖。

### 9.1 合规差距核查（规范要求 vs 现状）

| # | OKF 规范要求（§编号） | 当前实现状态 | 判定 |
|---|---|---|---|
| 1 | 每个概念文件含可解析 YAML frontmatter，**非空 `type` 唯一必填**（§11.2） | `kms_article.content` 为裸 Markdown，无 frontmatter 序列化；文章无 `type` 字段 | ❌ |
| 2 | 推荐字段 `title`/`description`/`resource`/`tags`（§2.2） | `title`/`tags` 有；`summary`≈`description`；`resource` 无 | ⚠️ |
| 3 | `sources` 溯源家族（entry 内 `resource` 必填、`id` 作 footnote join 键、`author`/`usage_count`/`last_modified` 信号、`usage_window`）（§5.1） | 无对应字段 | ❌ |
| 4 | `generated`（`by`=actor、`at`=ISO 8601 UTC）与 `verified`（`{by,at}` 列表，写者≠确认者）分离（§5.2） | 有 `creator_id`/`updated_at` 但非 actor 约定；无 `verified` | ❌ |
| 5 | `status`: `draft\|stable\|deprecated`，缺省=stable（§5.4）；`stale_after` 绝对时间点过期（§5.5） | `status` 为 `1发布/0草稿/-1归档` 整数，语义可映射；无 `stale_after` | ⚠️ |
| 6 | Bundle 结构：Concept + Bundle；保留文件 `index.md`（无 frontmatter，根可带 `okf_version`）/`log.md`（ISO 日期分组、最新在前）（§3/§8/§9） | 内容存 DB，无 bundle 物化；版本在 `kms_article_version` 但非 log.md 形态 | ❌ |
| 7 | 链接：标准 markdown，bundle 相对 `/` 路径推荐；断链必须容忍（§6.1） | 内容即 Markdown；但 slug 引用导出时不重写为 bundle 路径 | ⚠️ |
| 8 | Actor 命名约定：`human:<id>` / `process:<id>` / `<producer>/<version>`（§7，信任分层依据） | 仅 `creator_id` 整数 | ❌ |
| 9 | Per-claim 归因：footnote label = `sources[].id`（§6.1） | 问答层有 Citations，正文无 footnote↔sources 机制 | ⚠️ |
| 10 | Body 约定 heading：`# Schema`/`# Examples`/`# Computation`（§4.2） | 无约定、无 lint | ❌ |
| 11 | 宽容消费：不得因缺可选字段/未知 type/断链/未知键拒绝（§11.3） | 导入链路不存在 | ❌ |
| 12 | Attested Computation 家族（§10） | 无 | ➖ 推迟 |

**结论：OKF 合规层基本未落地（12 项中 0 项完整、4 项部分可映射）。** 补齐思路：DB 仍是事实源（不推翻现有架构），在其上加一层 **OKF 序列化/反序列化能力**——type=1 的知识库导出即合规 Bundle，导入即宽容消费。

### 9.2 模型扩展（`WikiArticle` 增列，全部 nullable 向后兼容）

```python
okf_type      = Column(String(64), nullable=True, comment="OKF type: concept|howto|reference|decision|metric 或自定义")
resource      = Column(String(500), nullable=True, comment="OKF resource: 底层资产 URI")
sources       = Column(JSONB, nullable=True, comment="OKF §5.1 溯源家族: [{resource(必填), id, title, author, usage_count, last_modified}]")
verified      = Column(JSONB, nullable=True, comment="OKF §5.2 验证事件列表: [{by, at}]")
stale_after   = Column(TIMESTAMP, nullable=True, comment="OKF §5.5 绝对过期时间点")
```

- `status` 不改列，导出映射：`0→draft`、`1→stable`、`-1→deprecated`；导入反向映射，未知值宽容落 `stable`。
- `generated.by`：`creator_id` join `sys_user` 生成 `human:<username>`；系统生成走 `process:minworkbuddy-wiki`；`generated.at` = `updated_at`（ISO 8601 UTC）。
- `okf_type` 缺省导出为 `concept`（规范允许仅 `type` 即合规）。

### 9.3 OKF 服务层（新 `backend/app/services/wiki/okf_service.py`）

- `export_bundle(knowledge_id)`：知识库=Bundle，分类=子目录，文章=`<slug>.md`；frontmatter 键序 type→resource→title→description→tags→sources→generated→verified→status→stale_after；每层目录生成 `index.md`（含 description 的条目列表，渐进披露）；`log.md` 由 `kms_article_version` 生成（ISO 日期分组、最新在前）；`okf_version: "0.2"` 仅写根 index.md；`references/` 惯例目录预留。
- `import_bundle(files)`：宽容解析（缺可选字段/未知 type/未知键/断链一律接受，退化为通用文档继续读取），按 slug upsert 文章 + 匿名分类挂载，返回导入报告（导入数/跳过/警告）。
- `serialize_article / parse_frontmatter`：单文章 ↔ concept.md 双向转换。
- 链接重写：导出把 `/wiki/<slug>` 引用重写为 bundle 相对路径，导入反向还原；断链原样保留（§6.1 容忍）。
- Per-claim 归因：正文中 footnote `[^id]` 原样导出，与 `sources[].id` 对应（join 按键不按位置）。

### 9.4 API（`/api/v1/wiki`）

```
GET  /knowledges/{id}/okf-export            # 导出 zip（StreamingResponse）
POST /knowledges/{id}/okf-import            # 上传 zip，宽容导入 + 报告
GET  /articles/{id}/okf                     # 单篇 concept.md 预览
```

### 9.5 前端

- 文章视图加「OKF 预览」Tab（单篇 concept.md 渲染）；知识库详情加「导出 OKF Bundle / 导入 OKF」入口（含导入报告反馈）。

### 9.6 明确推迟项（对齐规范 §13 推迟清单）

- Attested Computation 运行时家族（`runtime`/`parameters`/`computation`/`executor`/`attester`）；
- `usage_count` 自动统计（Phase 3 可从 `kms_search_log` 聚合可选注入）；
- attestation 缓存、语义层模板（Looker/dbt）模型级比较。

## 10. 通用 KB / 外部 KB 功能重构（对齐 Dify 六类知识库）

> 输入材料：Dify 知识库完整分类——① 非结构化文档 RAG；② 结构化表格 KB；③ Q&A 问答 KB；④ 多模态图文 KB；⑤ 外部知识库（检索代理）；⑥ 知识流水线（ETL 编排，非容器类型）。
> 原则：**不推翻已确认的三容器决策（§2）**。Dify 六类映射为 type=2/3 容器下的二级形态 `kb_format` + 摄取编排能力；实例创建后 `kb_format` 不可切换（对齐 Dify「选定数据源后不可切换」）。

### 10.1 类型映射

| Dify 类别 | MinWorkBuddy 落位 | 说明 |
|---|---|---|
| ① 非结构化文档 RAG | type=2, `kb_format='document'` | 补齐文档上传→解析→清洗→分块→embedding→落库全链路（现状后端端点缺失：前端调用的 `/retrieve`、`/documents` 等均 404） |
| ② 结构化表格 KB | type=2, `kb_format='table'` | 行=知识条目；`schema_config` 定义字段；单列 embedding + 其余列作可过滤元数据 |
| ③ Q&A 问答 KB | type=2, `kb_format='qa'` | 只 embed 问题、返回完整答案；现有 `QaChunker` 收敛为该形态的录入格式，不再承担检索形态 |
| ④ 多模态图文 KB | type=2, `kb_format='document'` + `multimodal_enabled=true` | 文本分块照旧；图片独立向量化（同库 `chunk_type='image'` 段），支持文搜图/图搜文 |
| ⑤ 外部知识库（代理） | type=3, `kb_format='proxy'` | 检索请求转发外部 API，不落内部库、无文档管理；与连接器拉取形态（`kb_format='connector'`，即 §3.4 现有设计）区分 |
| ⑥ 知识流水线 | 非容器类型：type=2 的 `pipeline_config` 摄取编排 | 数据源/清洗/分块配置化 + dry-run 单步调试；可视化画布推迟（§10.8） |

说明：现有 connectors（dingtalk/feishu/wecom/http 拉取落库到 `meta_connector_ingest`）语义上属于 Dify ⑥ 的「数据源节点」，Phase 3 起可作为 type=2 KB 的摄取来源；type=3 容器下 `kb_format='connector'` 保持 §3.4 原设计。

### 10.2 数据模型增量

全部 nullable / server_default，向后兼容；建表走 ORM `create_all`，存量表加列走 §4 迁移 SQL（`ALTER ... ADD COLUMN IF NOT EXISTS`）。

**`kms_knowledge` 加列：**

```python
kb_format = Column(String(16), nullable=True,
    comment='二级形态: type=2 → document|table|qa; type=3 → connector|proxy; type=1 为 NULL')
index_mode = Column(String(16), nullable=False, server_default='high_quality',
    comment='索引模式（Dify 对齐）: high_quality=向量+全文 | economy=仅关键词全文索引，不消耗 embedding')
multimodal_enabled = Column(Boolean, nullable=False, server_default='false',
    comment='type=2/document: 图片独立向量化（需 Vision Embedding 模型）')
pipeline_config = Column(JSONB, nullable=True,
    comment='§10.7 摄取编排: {clean:[...], chunker:{type,params}, index:{...}}')
```

- Service 层校验 `(type, kb_format)` 合法性矩阵；创建后拒绝修改 `kb_format`。
- `index_mode=economy`：摄取时跳过 embedding（`kb_segment.embedding` 留 NULL），检索仅走 pg_trgm 全文分支；允许后端从 economy 升级到 high_quality（触发批量回填 embedding 的后台任务），降级需确认。

**`kb_document`（新表）** — 文档/数据文件实体，支撑文档列表页与处理状态（现状 `kb_segment.document_id` 是裸值，无文档实体）：

```
id, tenant_id,
knowledge_id  FK kms_knowledge.id (SET NULL), index
collection    String(128)   # → kb_collection.name
name          String(500)
source_type   String(16)    # upload|db_table|api|qa_import|connector
file_type     String(32), nullable
file_size     BigInteger, nullable
status        String(16), server_default='pending'   # pending|processing|completed|failed
segment_count Integer, server_default='0'
error_detail  Text, nullable
meta          JSONB, nullable
creator_id    BigInteger, nullable
created_at / updated_at TIMESTAMP
```

**`kb_segment` 加列：**

```python
chunk_type = Column(String(16), nullable=False, server_default='text',
    comment='text|qa|table_row|image|parent|child')
parent_id = Column(BigInteger, ForeignKey('kb_segment.id', ondelete='CASCADE'),
    nullable=True, index=True, comment='父子分段: 子块 → 父块')
answer = Column(Text, nullable=True,
    comment="chunk_type=qa: 完整答案（content=问题，仅问题做 embedding）")
keywords = Column(JSONB, nullable=True, comment='手动关键词（全文检索加权）')
```

- 父子分段：父块 `chunk_type='parent'`、embedding 为 NULL、只存完整上下文；子块 `chunk_type='child'`、`parent_id` 指向父块；召回子块时附带父块内容返回。
- 表格行：`content`=embedding 字段值，`metadata_`=其余字段（复用现有 JSONB 列，不建宽表）。
- Q&A：`content`=问题（做 embedding）、`answer`=答案、`metadata_.tags`=标签。

**`kb_segment_asset`（新表，multimodal）：**

```
id, segment_id FK kb_segment.id (CASCADE), index
file_path String(500), mime_type String(64), size Integer,
width / height Integer nullable, created_at
```

- 服务层校验：单图 ≤ 2MB、单 segment ≤ 10 张图（对齐 Dify 限制）。

**`kms_external_kb_endpoint`（新表，type=3/proxy）：**

```
id, tenant_id,
knowledge_id  FK kms_knowledge.id (SET NULL), index
name          String(200)
endpoint_url  String(500)
auth_key      String(500), nullable   # Fernet 加密（沿用 §3.4 DataOps crypto 惯例）
index_name    String(128), nullable
metadata_mapping JSONB, nullable
status        String(32), server_default='active'   # active|error|disabled
error_detail  Text, nullable
creator_id    BigInteger, nullable
created_at / updated_at TIMESTAMP
```

- 不拉数据、无文档管理；仅检索时转发（§10.4），`POST {id}/test` 做连通性测试。

**`kb_collection` 加列（仅 table 形态使用）：**

```python
schema_config = Column(JSONB, nullable=True,
    comment='表格 KB 字段定义: [{name,type,enabled,embedding(单选),filterable}]')
```

**模型注册**：`kb_document`、`kb_segment_asset`、`KbDocument`、`KbSegmentAsset`、`ExternalKbEndpoint` 按既有惯例加入 `models/kb/__init__.py`（proxy 模型入 `models/kb/` 或 `models/connectors/`，倾向后者与实例层同域）与 `init_models.py`。

### 10.3 摄取与分块（type=2）

- **文档上传（format=document/multimodal）**：`POST /kb/collections/{id}/documents`（multipart）→ 建 `kb_document(pending)` → `job_runner.run_in_background` + 独立 Session 执行：解析（pdf/docx/md/txt/html）→ 清洗（`pipeline_config.clean`）→ 分块 → embedding（`embed_batch_sync` + `dimensions` 校验，复用 `ingest_service`）→ `kb_segment` 落库 → 状态回写 completed/failed（错误写 `error_detail`）。`POST /kb/documents/{id}/reprocess` 删旧 chunk 重灌。
- **分块器**：`CHUNKER_REGISTRY` 新增 `ParentChildChunker`（父块/子块 token 上限、分隔符可配），与 `ApproxTokenChunker` 并存；选择来自创建向导或 `pipeline_config.chunker`。
- **表格导入（format=table）**：
  - 文件入口：`POST /kb/collections/{id}/table-records/import`（CSV/Excel，openpyxl 解析，可参考 `app/ai/tool_manager/document_tools.ExcelProcessor`）；
  - 直连数据库：复用 DataOps `meta_data_source`（mysql/doris/postgresql），information_schema 读列预填 `schema_config` → 定时增量同步（Phase 3，复用 §3.4 sync_interval 思路）；
  - 校验：embedding 字段单选、filterable 字段白名单；每行 → `kb_segment(chunk_type='table_row')`；
  - 行级 CRUD：`GET/PUT/DELETE /kb/segments/{id}` + 批量导入更新。
- **Q&A（format=qa）**：`POST /kb/collections/{id}/qa-records`（question/answer/tags）；Excel/CSV 批量导入导出；只 embed question；禁用态以 `metadata_.enabled` 过滤。
- **多模态**：文档解析抽取内嵌图片 / 独立图片上传 → `kb_segment_asset` 存文件 → multimodal embedding（Vision 模型，`embedding_config.py` 扩展 provider 能力）→ 独立 `kb_segment(chunk_type='image', embedding=图向量, content=caption/OCR)`；图搜：image query → 向量 → `search_by_vector`（现成）。

### 10.4 检索与检索测试

统一端点 `POST /kb/collections/{id}/retrieve`（主应用 get_db + get_current_user，补齐现状 404）：

- 通用参数：`query`、`top_k`、`score_threshold`、`metadata_filters`（键值条件，作用于 `kb_segment.metadata_` JSONB）、可选 rerank。
- 按 kb_format 分支：

| 形态 | 检索行为 |
|---|---|
| document / multimodal | `hybrid_search_by_text`（现成向量+trigram RRF）+ metadata 过滤 + 父子展开（命中子块附带 `parent_content` 返回） |
| document（index_mode=economy） | 同上但**跳过向量分支**，仅 pg_trgm 全文 + metadata 过滤（RRF 退化为单路） |
| qa | 向量检索 `chunk_type='qa'`，返回 question + answer + score |
| table | 向量检索 + filterable 字段过滤，返回整行（content + metadata_） |
| image（multimodal 图搜） | 文搜图返回 asset + 缩略图 URL；支持图片作为查询输入 |
| proxy（type=3） | 转发 `kms_external_kb_endpoint`（超时/错误结构化返回），可选本地 rerank，统一引用拼接 |

- 返回统一结构 `{segments[], scores[], citations[]}`，前端检索测试面板直接消费。

### 10.5 API 增量汇总（/api/v1，主应用认证）

| 形态 | 端点 | 说明 |
|---|---|---|
| 通用 | `POST/GET /kb/collections/{id}/documents`、`POST /kb/documents/{id}/reprocess`、`DELETE /kb/documents/{id}` | 文档列表/上传/重处理/删除（kb_document） |
| 通用 | `GET/PUT/DELETE /kb/segments/{id}`、`PATCH /kb/segments/{id}/keywords` | 分段编辑/关键词（Dify 分段详情页） |
| 通用 | `GET /kb/segments/{id}/citations` | 分段「查看引用来源」（来源文档/上游 chunk 链） |
| 通用 | `PUT /kb/collections/{id}/settings` | 设置面板：embedding 模型（变更触发重灌任务）、rerank 模型、score_threshold、top_k、index_mode 升降级（§10.2） |
| 通用 | `POST /kb/collections/{id}/retrieve` | §10.4 统一检索测试 |
| table | `POST .../table-records/import`、`GET .../table-records/preview` | CSV/Excel 导入 + 字段映射校验预览 |
| qa | `POST .../qa-records`、`POST .../qa-records/import`、`GET .../qa-records/export` | Q&A 录入/批量导入导出 |
| multimodal | `POST .../assets`（图片上传）、图搜走 retrieve | Vision embedding |
| proxy | `/external-kb-endpoints` CRUD + `POST {id}/test` | 外部代理配置与连通性测试 |
| pipeline | `POST /kb/pipelines/dry-run` | §10.7 单步调试 |

### 10.6 前端（KnowledgeBaseManager.vue 扩展）

- **创建向导按 kb_format 分支**：文档（分段模式 通用/父子、**索引模式 经济型/高质量**、embedding 模型、检索参数）；表格（上传或选数据源 + 字段映射面板：启用/类型/embedding 单选/filterable 勾选）；Q&A；多模态（强制校验选择 Vision embedding 模型）；外部代理（endpoint/key/index/映射）；连接器（原 §6 设计）。
- **type=2 右区按 format 渲染**：
  - document：文档列表（状态/大小/时间、重处理、批量删除）→ 分段详情抽屉（chunk 列表、单段编辑、关键词、**查看引用来源**、父子树、图片缩略图）；
  - table：条目列表（行编辑/新增/删除/批量导入更新）+ 数据预览（前 N 行校验字段识别）；
  - qa：Q&A 表格（问题/答案/标签、批量导入导出、启停）；
  - 检索测试统一面板（table 支持元数据筛选、multimodal 支持图搜）；
  - **设置面板**（各形态通用）：修改 embedding 模型（变更确认 + 触发重灌后台任务）、rerank 模型、检索阈值、索引模式升降级、权限（挂 Phase 3 RBAC 权限点）。
- **type=3 右区**：connector → 实例+同步作业（原设计）；proxy → 端点配置 + 调试检索 + **引用与调用方管理**（哪些 Agent/应用可调用该外部库，授权关系挂 RBAC，Phase 3 落地、UI 先占位）。
- 组件落位 `views/kms/kb/`：DocumentList、SegmentDetail、TableRecordList、QaRecordList、RetrievalTester、ExternalEndpointPanel；现有 `admin/knowledge/kb/SearchTester.vue`、`external/InstanceManagement.vue` 等迁移合并，避免双份维护。

### 10.7 知识流水线（轻量版）

- `pipeline_config`（kms_knowledge）声明式编排：`clean` 步骤（regex / LLM 清洗 / OCR）、`chunker`（token / parent_child / qa + 参数）、`index` 参数；数据源支持 `upload` / `connector`（复用 §3.4 实例拉取产物 `meta_connector_ingest`）/ `db_table`。
- 摄取任务按 config 顺序执行；`POST /kb/pipelines/dry-run` 接收样例文件 + config，返回各步中间产物预览（提取文本 → 清洗后 → 分块结果），不落库。
- 每步错误结构化记录到 `kb_document.error_detail`（含步骤名），可单步重试。

### 10.8 分期与明确推迟

- **Phase 1**：不新增（P0 + §3 模型不变；10.2 新表 DDL 随 schema.sql 再生一并产出）。
- **Phase 2**：kb_document / kb_segment 加列 + 文档上传全链路 + retrieve 端点 + ParentChildChunker + 文档/分段前端 + kb_format 创建向导骨架。
- **Phase 3**：table / qa / multimodal / proxy 全量 + pipeline dry-run + db_table 定时同步。
- **推迟**：可视化拖拽流水线画布、流水线版本管理/发布草稿流、外部代理 metadata_mapping 自动推断——待轻量版验证后再评估。

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| RENAME 影响未知的存量 FK/视图依赖 | 迁移前 `\d kms_category` 核对依赖；`schema.sql` 再生后 diff 核对 |
| create_all 不会给已有表加列 | 迁移 SQL 以 ALTER 显式执行，schema.sql 仅作权威参考 |
| 连接器别名映射语义偏差（notion 分页模型 ≠ http 通用分页） | Phase 1 仅落实例 CRUD + 手动 sync；notion 专属拉取逻辑在 Phase 2 补 `NotionApiConnector` 后取消别名 |
| 前端双入口（/wiki 与工作台）造成维护分叉 | /wiki 保留为深链，列表逻辑组件化后两处共用 |
| multimodal Vision embedding 供应商能力不确定（embedding_config 现仅 gpustack/nvidia/dashscope 文本模型） | `multimodal_enabled` 仅在配置了 Vision embedding 模型时可选；无供应商时创建向导禁用该形态并提示 |
| kb_segment 加列影响既有 agentscope 侧写入路径（kb_app 子应用直写） | 新列均 nullable/server_default，旧路径无需感知；Phase 2 认证收口时一并验证 |
| 外部代理转发引入 SSRF 面（endpoint_url 用户可控） | 校验 URL 协议白名单（https）、禁内网地址段；转发超时/大小上限结构化限制 |
| OKF 导出/导入往返丢失（frontmatter 往返、时区/时间戳格式、slug 与文件名冲突） | 序列化统一 ISO 8601 UTC；slug 冲突导入时加 `-2` 后缀并记入报告；往返用 pytest 固定样例做 round-trip 断言 |
| index_mode economy→high_quality 升级触发全量 embedding 回填，大库耗时长/失败中断 | 升级走 `job_runner` 后台批量任务 + 断点续跑（按 kb_document 粒度记录进度）；失败文档保留 economy 分支可检索，升级报告可重试 |

## 12. 验收标准

1. `pytest` 全绿（当前基线 108 passed 只增不减）。
2. 三份报告中全部 🔴 P0 项在 Phase 1 结束后复验通过（启用对应前端组件不再报 routerMissing / 编译失败）。
3. 迁移 SQL 在 staging 库执行后：存量 wiki 知识库 type=1、分类树完整、kb_category.kb_type 回填正确。
4. 统一工作台三种类型均可完成一次「建容器 → 建分类 → 进详情」闭环；类型 C 可完成一次真实 sync 且日志状态真实。
5. `schema.sql` 再生后与 ORM 定义一致。
6. OKF 合规（§9）：type=1 知识库导出 zip 可被独立工具按规范 §11 校验通过（每个概念含非空 `type` 的 frontmatter、`index.md`/`log.md` 结构合规）；同一 Bundle 导入后文章内容与分类挂载无损；缺可选字段/未知 type/断链的 Bundle 导入不报错且产出报告。
7. Dify 对齐功能（§10，Phase 2 部分）：format=document 知识库完成「上传 PDF/MD → 状态流转 → chunk 列表 → 编辑单段 → 检索测试返回 score」闭环；父子分段召回子块时返回父块内容；`kb_format` 创建后修改被后端拒绝；index_mode=economy 知识库检索仅命中关键词分支且摄取零 embedding 消耗，升级 high_quality 后向量分支恢复。
8. Dify 对齐功能（§10，Phase 3 部分）：format=table 完成「Excel 导入 → 字段映射（embedding 单选/filterable）→ 行级编辑 → 元数据过滤检索」；format=qa 完成批量导入导出且检索返回完整答案；multimodal 完成图搜图与文搜图；proxy 完成一次真实外部检索转发与引用拼接；pipeline dry-run 返回各步中间产物且不落库。
9. 新表（kb_document / kb_segment_asset / kms_external_kb_endpoint）`schema.sql` 再生后与 ORM 定义一致；存量 kb_segment 行 chunk_type 默认 'text'、既有检索行为回归无差异。
