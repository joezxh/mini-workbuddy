# Plan: Wiki 模块标准化改造（基于 2026-09-12 设计 spec）

> **类型**: Implementation Plan（Superpowers `write-plans` 方法论：spec 驱动 + 任务级 TDD + 验收标准）
> **Spec 来源**: `docs/superpowers/specs/2026-09-12-wiki-module-standardization-design.md` (v2.0, 已评审通过)
> **生成日期**: 2026-09-12
> **说明**: 本环境未安装 `write_plans` skill，以下按该 skill 的标准结构（Goals / Anti-Goals / Approach / Files / Tasks / Risks）手工生成。

---

## 0. 预研结论（执行前验证，2026-09-12）

执行前对照 spec 两个阻塞点做了实际核对，结论如下：

| 验证项 | 结论 | 证据 |
|---|---|---|
| **G0 `vector` 扩展** | ✅ 已启用，**无需 CREATE EXTENSION** | 连库查询 `pg_extension` 返回 `vector` 存在 |
| **tenant_id 多租户** | ✅ 已配置 | `WikiKnowledge`/`WikiArticle`/`WikiArticleVersion` 均继承 `TenantMixin`；`middleware/tenant_resolver.py` + `core/tenant_context.py` 注入；`alembic` 已有多租户迁移 |
| **迁移机制** | ⚠️ 与 plan 初稿相反：**项目用 Alembic**（非 create_all+手写 SQL） | `backend/alembic/` 存在；`env.py` 经 `app.db.init_models` 注册全量 model 供 autogenerate |
| **已存在模型（不必重建）** | `WikiKnowledge`(G7)、`wiki_category.knowledge_id`(G7)、`WikiArticle.content_vector`(G1) | 均已落地并 import 于 `init_models.py` |
| **Embedding/LLM 配置** | ✅ 已有现成可复用 | 模型用 `settings.EMBEDDING_DIMENSION`；`app.ai.embedding_client.get_embedding_client`（`kb` 模块已用）；LLM 走现有 AI Chat 服务 |

**因此修正**：本 plan 的「迁移走手写 SQL」「不引入 Alembic」「G7 实体需新建 model」等表述不成立，已在下方相应章节订正。剩余 DB 工作仅 2 项：① `WikiArticleVersion` 加 `operation_type`（算子复用已有 `editor_id`）；② 新增 `WikiSearchLog` model。

---

## 1. Spec 摘要（Scope）

将 `MinWorkBuddy` 的 Wiki / 私有知识库模块从「用户侧单入口、内联逻辑、无语义检索」升级为「知识库→目录→文章→版本四级体系 + RAG 混合检索 + LLM Wiki 问答 + 管理后台」。

对应缺口 (doc §2)：G0 (PGVector 可用性) → G7 (知识库实体) → G3/G5 (分层重构) → G1/G9 (RAG) → G2 (版本回滚) → G8/G10 (管理后台) → G4 (编辑页 hack 消除) → G6 (LLM 成稿, 待评估, 本计划不实现)。

---

## 2. Current State（已完成项，避免重复劳动）

前期工作已落地 **Stage 1 大部分骨架**，以下视为已完成、本计划不再重做（仅补验证）：

- `app/schemas/wiki/`：`__init__.py` + `article.py`(ArticleOut) + `category.py`(CategoryCreate/Update/CategoryOut/CategoryTree) + `knowledge.py`(KnowledgeCreate/Update/KnowledgeOut) + `version.py`(VersionOut/DiffResult)。
- `app/repositories/wiki/`：`__init__.py` + `article_repo.py`(get_by_id/get_by_slug/list_filtered) + `category_repo.py`(create/get/list_by_knowledge/list_all/count_articles/update/delete) + `knowledge_repo.py`。
- `app/services/wiki/`：`knowledge_service.py`、`category_service.py`（含 tree 可选 knowledge 过滤 + 移动）、`article_service.py`（CRUD/版本快照/backlinks/搜索降级，`_serialize` 与原 `_article_to_dict` 字段一致）。
- `app/routers/wiki/wiki.py`：已瘦身为纯路由分发（G3 部分落地），响应契约不变。
- `app/routers/wiki/wiki_admin.py`：知识库 CRUD + 分类树 + 文章管理 + 按 id 取详情（G4 后端侧已具备 `GET /articles/{id}`）。

**尚未完成（本计划主体）**：所有 DB model / 迁移、RAG 写入与检索、版本回滚端点（G2）、管理后台前端（G8/G10）、检索/问答前端、菜单与权限、测试。

---

## 3. Goals（目标）

- G0：确认运行库为 PostgreSQL 且已启用 `vector` 扩展（建表前置）。
- G7：新增 `wiki_knowledge` 实体与 `wiki_category.knowledge_id` 归属字段，落库并迁移。
- G3/G5 收尾：确保全部 wiki 端点经 service 层；消除 backlinks 只加不清（G5）。
- G1/G9：激活 RAG 写入路径（ARQ 异步），实现混合检索 `WikiSearchService` 与 `LLMWikiService` 问答；前端双模式检索 + 引用卡片。
- G2：版本回滚（非破坏式）+ diff 端点；前端版本时间线/对比/回滚。
- G8/G10：管理后台 `KnowledgeManagement.vue` + 5 Tab；菜单 + 权限接入。
- G4：前端编辑页直接按 id 取详情，移除全量拉列表 hack。

## 4. Anti-Goals（非目标）

- **不实现 G6**（LLM 自动摘要/成稿），spec 标注为「待评估」。
- 不替换现有 OWL 本体引擎（`wiki_owl.py` / `owl_engine.py` 保持）。
- **迁移统一走 Alembic autogenerate**（`alembic revision --autogenerate -m "..."` → `alembic upgrade head`），新增 model 必须在 `app/db/init_models.py` 注册；不手写独立 SQL 迁移脚本。
- 不重写用户侧 `/wiki` 既有阅读/编辑流程，仅在现有组件上增量挂载新能力。
- 不新建 embedding/LLM 配置：复用 `settings.EMBEDDING_DIMENSION` + `app.ai.embedding_client.get_embedding_client` 与现有 AI Chat 服务。

---

## 5. Approach（总体方案）

1. **先数据库后代码**：G0 已确认（`vector` 已启用）→ 新增/ALTER model（`WikiSearchLog` 新建、`WikiArticleVersion` 加 `operation_type`）→ **Alembic autogenerate 迁移**。
2. **RAG 与版本沿用既有空壳**：`wiki_rag.py` 已存在 `WikiRAGIngestor`，仅需接入写路径 + `content_vector` 列（model 已声明 `Vector`）。检索/问答为新建 service。
3. **service 层为业务边界**：router 只做鉴权 + 参数绑定 + schema 映射；异步索引经 ARQ（与现有 job_runner 约定一致）。
4. **前端以组件增量挂载**：检索条、AI 答案、版本时间线、目录树为新组件；管理后台为单页 + Tab；菜单走 `sys_menu` + `componentMap`。
5. **每任务 TDD**：后端加 pytest（会话 fixture + 内存/测试库），前端加 lint + 关键交互单测；无法本地运行则在 PR 描述标注未验证范围。

---

## 6. Files（文件清单）

### New
- `backend/app/models/wiki/wiki_search_log.py` — `WikiSearchLog` model (G1 审计；继承 `TenantMixin`，含 tenant_id/user_id/query/mode/result_count/latency_ms)
- ⚠️ `WikiKnowledge` / `wiki_category.knowledge_id` / `WikiArticle.content_vector` **已存在，勿重建**
- `backend/app/services/wiki/search_service.py` — `WikiSearchService` 混合检索 + RRF + 审计 (G1/G9)
- `backend/app/services/wiki/llm_wiki_service.py` — `LLMWikiService` 问答 + 引用 (G9)
- `backend/app/services/wiki/version_service.py` — `WikiVersionService` rollback/diff (G2)
- `backend/app/services/wiki/wiki_rag_task.py` — ARQ 任务封装 `index_article` (G1)
- `backend/app/ai/knowledge/` 下挂接 embedding writer（复用 `app.ai.embedding_client.get_embedding_client`，与 `kb` 模块一致；不新建 embedding 配置）
- `frontend/src/views/kms/wiki/components/SearchBar.vue` (G9)
- `frontend/src/views/kms/wiki/components/SearchResultList.vue` (G9)
- `frontend/src/views/kms/wiki/components/LLMAnswerPanel.vue` (G9)
- `frontend/src/views/kms/wiki/components/CitationCard.vue` (G9)
- `frontend/src/views/kms/wiki/components/VersionTimeline.vue` (G2)
- `frontend/src/views/kms/wiki/components/VersionDiffView.vue` (G2)
- `frontend/src/views/kms/wiki/components/VersionRollbackButton.vue` (G2)
- `frontend/src/views/kms/wiki/components/CategoryTree.vue` (G8 提取)
- `frontend/src/views/kms/wiki/components/ArticleCard.vue` (G8 提取)
- `frontend/src/views/kms/wiki/admin/KnowledgeManagement.vue` (G10)
- `frontend/src/views/kms/wiki/admin/tabs/KnowledgeBaseTab.vue` (G10)
- `frontend/src/views/kms/wiki/admin/tabs/CategoryTab.vue` (G10)
- `frontend/src/views/kms/wiki/admin/tabs/ArticleTab.vue` (G10)
- `frontend/src/views/kms/wiki/admin/tabs/RagTestTab.vue` (G10)
- `frontend/src/views/kms/wiki/admin/tabs/VersionTab.vue` (G10)
- `frontend/src/views/kms/wiki/types/wiki.ts` — 共享类型 (G8)
- `frontend/src/views/kms/wiki/api/wiki.ts` — API 封装扩展 (G4/G9)
- ⚠️ 迁移统一走 Alembic：`alembic revision --autogenerate`；不新增手写 SQL 文件 (G0/G7/G2)

### Modified
- `backend/app/models/wiki/wiki_article.py` — `content_vector` 已存在 ✅（仅核对，无需改）
- `backend/app/models/wiki/wiki_article_version.py` — 加 `operation_type`（`'create'|'edit'|'rollback'`，默认 `'edit'`；算子复用已有 `editor_id`），并加 `idx_wiki_version_article` (G2)
- `backend/app/models/wiki/wiki_category.py` — `knowledge_id` 已存在 ✅（仅核对，无需改）
- `backend/app/services/wiki/article_service.py` — 写后触发 ARQ 索引；回滚时重建索引；修正 backlinks 清理 (G1/G2/G5)
- `backend/app/routers/wiki/wiki.py` — 新增 `POST /search`、`POST /llm-wiki/ask`、`POST /articles/{id}/rollback/{vid}`、`GET /articles/{id}/diff/{vid}` (G1/G2/G9)
- `backend/app/routers/wiki/wiki_admin.py` — 版本管理端点、search_log 接入 (G2)
- `backend/app/core/router_registry.py` — 确认 wiki/wikowl/wiki_admin 均注册（已部分）
- `frontend/src/views/kms/wiki/index.vue` — 挂载 SearchBar / 目录树提取 (G8/G9)
- `frontend/src/views/kms/wiki/ArticleEdit.vue` — 改用按 id 取详情 (G4)
- `frontend/src/router/componentMap.ts` — 加 `kg-knowledge` (G10)
- `frontend/src/` 菜单/权限配置（`sys_menu` 后端记录 + 前端守卫）(G10)

---

## 7. Tasks（TDD 任务分解）

### Task 1 — G0 数据库可用性确认与 Alembic 迁移基线
**Goal**: 已确认运行库启用 `vector`（✅ 2026-09-12 实测存在）；为剩余 2 项 DB 变更生成 Alembic 迁移：`WikiSearchLog` 新建 + `WikiArticleVersion.operation_type`。
**Files**: 新增 `backend/app/models/wiki/wiki_search_log.py`(继承 `TenantMixin`)；修改 `wiki_article_version.py` 加 `operation_type` + `idx_wiki_version_article`；在 `app/db/init_models.py` 注册 `WikiSearchLog`；`alembic revision --autogenerate -m "wiki rag log + version op_type"` → `alembic upgrade head`。
**Tests**: (1) 连库 `SELECT extname FROM pg_extension WHERE extname='vector'` 断言非空（已通过）；(2) `alembic upgrade head` 后 `\\d wiki_search_log` 存在且含 `tenant_id`；(3) `wiki_article_version` 含 `operation_type` 列。
**Steps**: 写 model → 注册 init_models → `alembic revision --autogenerate` 核对生成 diff（仅 2 项新增，勿误删既有 wiki 表）→ `alembic upgrade head` → 本地验证。
**Acceptance**: `wiki_search_log` 表就绪；`WikiArticleVersion.operation_type` 落地；无其它表被误改。
**Deps**: 无。

### Task 2 — G7 知识库实体与目录归属（核对 + 收口）
**Goal**: `WikiKnowledge`/`knowledge_id` **已存在**，本任务仅做端点-level 收口与回归，不新建 model。
**Files**: `knowledge_repo.py`/`knowledge_service.py`/`wiki_admin.py` 已有；核对 `wiki_admin.py` 知识库 CRUD + `wiki_category` tree 按 `knowledge_id` 过滤正确。
**Tests**: pytest 创建知识库→查列表→按 id 详情→启停(status)→删除全链路；分类建在指定 knowledge 下、tree 按 knowledge 过滤正确。
**Acceptance**: 能力矩阵 G7 = ✅；§7.1 知识库端点全部可通；迁移中 wiki_knowledge 未被重建。
**Deps**: Task 1。

### Task 3 — G3/G5 收尾（分层 + backlinks 清理）
**Goal**: 确认全部端点经 service；`article_service._update_backlinks` 改为「全量重算」以消除 G5（只加不清）。
**Files**: `article_service.py` 修改 `_update_backlinks`（删除旧 backlinks 后按所有文章 wiki_links 重建目标集合）；`wiki.py` 已是纯路由。
**Tests**: 建 A→链接 B，A.backlinks 含 B；改 A.wiki_links 去掉 B 后，B.backlinks 不再含 A。
**Acceptance**: G5 关闭；router 无内联 DB 逻辑（grep 校验）。
**Deps**: Task 1。

### Task 4 — G1 RAG 写入路径激活
**Goal**: 文章创建/更新后 ARQ 异步触发 embedding 写入 `content_vector`。
**Files**: `wiki_rag_task.py`(New, ARQ task)、`article_service.py` 写后 `await enqueue`、embedding 复用 `app.ai.embedding_client.get_embedding_client`（与 `kb` 模块一致，维度取 `settings.EMBEDDING_DIMENSION`）。
**Tests**: 单测 mock ARQ，断言索引任务被调用且 `content_vector` 非空（用 fake embedding client）；PGVector/embedding 不可用时降级不抛（捕获异常，仅记日志）。
**Acceptance**: §8.4「创建/更新后自动触发 RAG 索引（异步）」；主写链路不阻塞。
**Deps**: Task 1, 3。

### Task 5 — G1/G9 混合检索 + LLM 问答（后端）
**Goal**: `WikiSearchService`(语义/关键词/RRF/审计) + `WikiSearchLog` 写入；`LLMWikiService` 拼 context + 调用现有 LLM Chat + 返回引用。
**Files**: `search_service.py`(New)、`llm_wiki_service.py`(New)、`wiki.py` 加 `POST /search`、`POST /llm-wiki/ask`；`wiki_article_version` 审计字段已加。
**Tests**: pytest 注入 embedding + 测试库，hybrid 返回按 RRF 排序且带 `mode`；semantic 仅 PGVector；keyword 仅 LIKE；llm-wiki 返回 `answer`+`citations` 且 citations 引用真实文章 id；PGVector 异常时降级 keyword。
**Acceptance**: 响应结构 `{items, mode}` 与 spec §3.2.4 一致；降级不改前端契约。
**Deps**: Task 1, 4。

### Task 6 — G2 版本回滚 + diff（后端）
**Goal**: `WikiVersionService.rollback`（非破坏式，生成新版本）/ `get_diff`（unified diff）；端点 `POST /articles/{id}/rollback/{vid}`、`GET /articles/{id}/diff/{vid}`、`GET /articles/{id}/versions/{vid}`。
**Files**: `version_service.py`(New)、`wiki.py` 加端点、`wiki_admin.py` 版本管理列表、`wiki_article_version` 的 `operation_type`（算子复用 `editor_id`，Task 1 已加列）`create_version_snapshot` 时写入并落日志。
**Tests**: 建文章 v1→改 v2，回滚到 v1 生成 v3 且内容=v1；diff 返回非空前后的 unified 文本；回滚后自动重建索引（mock）。
**Acceptance**: §8.4 回滚非破坏式 + diff 段落粒度。
**Deps**: Task 1, 3, 4。

### Task 7 — 前端检索与问答 UI（G9/G8 组件）
**Goal**: `SearchBar`(语义/问AI Toggle) + `SearchResultList` + `LLMAnswerPanel`(Markdown+引用) + `CitationCard`；`index.vue` 挂载；`CategoryTree`/`ArticleCard` 从 index 提取。
**Files**: 上述 5 个 New 组件 + `index.vue` + `types/wiki.ts` + `api/wiki.ts` 扩展（search/llm-wiki）。
**Tests**: oxlint 通过；关键交互单测（模式切换、引用点击跳原文）；`npm run build` 通过。
**Acceptance**: 双模式检索可用；问 AI 答案带引用且可跳转。
**Deps**: Task 5。

### Task 8 — 前端版本 UI（G2）
**Goal**: `VersionTimeline` / `VersionDiffView` / `VersionRollbackButton`（二次确认「基于 vN 生成 vN+1」）。
**Files**: 3 个 New 组件 + `ArticleEdit.vue` 或文章详情挂载 + `api/wiki.ts` 加 rollback/diff。
**Tests**: oxlint + build；回滚按钮确认弹窗文案正确；diff 视图渲染。
**Acceptance**: 版本时间线/对比/回滚可操作。
**Deps**: Task 6, 7。

### Task 9 — G4 编辑页 hack 消除
**Goal**: `ArticleEdit.vue` 直接 `GET /articles/{id}` 取详情（后端 G4 已具备），移除全量列表按 id 找 slug。
**Files**: `ArticleEdit.vue` + `api/wiki.ts`。
**Tests**: build；编辑页仅 1 次详情请求（移除 listArticles 1000 拉取）。
**Acceptance**: §8.4「编辑页不再全量拉取」。
**Deps**: Task 2（get_by_id 已存在）, 7。

### Task 10 — G10 管理后台 + 菜单/权限（前端+配置）
**Goal**: `KnowledgeManagement.vue` + 5 Tab（KB/Category/Article/RagTest/Version）；`componentMap` 加 `kg-knowledge`；`sys_menu` 插入「知识库管理」记录；`requiresAdmin` 守卫；`v-if` 角色可见性。
**Files**: 1 New 主页 + 5 New Tab + `componentMap.ts` + 后端 `sys_menu` INSERT + 路由懒加载。
**Tests**: build；以 admin 登录可见菜单、editor 可见操作按钮、普通用户受限（后端 requiresAdmin 拒绝）。
**Acceptance**: §8.4「管理后台 5 Tab 完整、权限生效」。
**Deps**: Task 2, 5, 6, 7, 8。

---

## 8. Cross-cutting（横切关注点）

- **DB 迁移** (Task 1): 走 Alembic autogenerate —— 改 model → 在 `app/db/init_models.py` 注册 → `alembic revision --autogenerate -m "..."` → 核对生成 diff（确认只含预期新增/变更，勿误删既有表）→ `alembic upgrade head`；不手写独立 SQL。
- **异步索引**: 复用现有 ARQ/job_runner 约定，独立 Session，不绑 FastAPI 生命周期（参考 AGENTS.md `job_runner.run_in_background`）。
- **统一错误**: service 抛 `HTTPException`；全局处理器映射 `{code,message,detail}`。
- **降级契约**: RAG/embedding 缺失时自动 keyword 降级，前端响应结构不变。
- **权限边界**: 后端 `requiresAuth`/`requiresAdmin` 为安全边界；前端仅控制可见性。

## 9. Risks（风险与缓解，取自 spec §8.3 并补全）

| 风险 | 等级 | 缓解 |
|---|---|---|
| PGVector 未启用 | 低(已消除) | 2026-09-12 实测 `vector` 扩展已存在；仅当换库时需 `CREATE EXTENSION vector` |
| Embedding 未配置 | 中 | `.env` 配置项 + 降级 keyword；单测用 fake embedding |
| 分层重构影响现有功能 | 中 | Task 3 后全量回归 `/wiki` 端点；`_serialize` 字段对齐原 `_article_to_dict` |
| LLM 调用成本 | 中 | 问 AI 接口加频率限制（每用户每分钟 5 次）|
| 管理后台页面多 | 低 | 复用 antd/a-tree/a-table，减少定制 |
| 本环境无法启动后端 | 高(验证) | 每任务写明验证命令与「未验证范围」，交 PR 时由 CI/本地确认 |

## 10. Definition of Done（验收，对应 spec §8.4）

- [ ] 文章创建/更新后异步触发 RAG 索引（不阻塞主链路）
- [ ] 混合检索返回含 `mode`；降级时前端契约不变
- [ ] 问 AI 返回带引用标注、点击可跳转原文
- [ ] 版本回滚非破坏式（生成新版本，不删历史）
- [ ] 版本 diff 段落粒度可见
- [ ] 全部 wiki 端点经 service 层，router 无内联逻辑
- [ ] 管理后台 5 Tab 完整、权限生效
- [ ] 编辑页不再全量拉列表
- [ ] 每任务附 pytest / oxlint / build 证据；CI 或本地复跑通过

## 11. Open Questions（已勘定项已标注 ✅）

- ✅ **G0 `vector` 扩展**：2026-09-12 实测 `miniworkbuddy` 库已启用 `vector`，无需 `CREATE EXTENSION`，T4/T5 写入路径打通。
- ✅ **tenant_id 多租户**：已通过 `TenantMixin`（`wiki_knowledge`/`wiki_article`/`wiki_article_version` 均继承）+ `middleware/tenant_resolver.py` + `core/tenant_context.py` 启用；新增 `WikiSearchLog` 同样继承 `TenantMixin` 即可。
- ✅ **Embedding / LLM 配置**：复用现有 —— 维度 `settings.EMBEDDING_DIMENSION`、`app.ai.embedding_client.get_embedding_client`（与 `kb` 模块一致）；LLM 走现有 AI Chat 服务。无需新建配置键。
- ⬜ **G6（LLM 成稿）**：spec 标注「待评估」，本计划未含，待后续单独提案。
- ⬜ **ARQ 接入方式**：确认现有 `job_runner.run_in_background` 是否即 ARQ worker；若项目未启 ARQ，则 `wiki_rag_task` 改为 `run_in_background` 封装（Task 4 实现时定）。
