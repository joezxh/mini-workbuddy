# LLM Wiki 功能盘点、处理链路与 OKF v0.2 差距分析

> 本文是**现状盘点 + 差距分析**，不是实施方案。方案章节只给补齐顺序与批次，不含详细设计。
> 盘点时间：2026-10-09。kev × AgentScope 设计文档评审已搁置，不在本文范围。

## 背景与目的

`LLM Wiki`（`kms_knowledge.type=1` 容器）是MinWorkBuddy 知识体系的"人工维护"分支：用户手写
Markdown 文章，挂在分类 / 知识库树上一份，既是给人看的文档，也是喂给 wiki RAG 的语料。

它与 `type=2` 的 **KB 文档库**是两套独立实现：Wiki 不分段、不走index_mode、不进 KB 检索管线。
而 OKF（Open Knowledge Format，v0.2）合规层是2026-09-27 知识统一设计 §9 追加的增强项，
落地了导出 / 导入 / 预览三个端点与部分字段。

本文回答三个问题：

1. LLM Wiki 现在**实际能做什么**（含明确的"未实现"判定）；
2. 导入一篇文章后**实际发生了什么**，特别是 **向量化环节是否真的在跑**；
3. 对比 **OKF v0.2 规范**，还差什么、按什么顺序补。

## 结论摘要

| # | 结论 | 依据 |
|---|---|---|
| 1 | Wiki **创建/编辑/OKF 导入三条入口全部不触发向量化**，`content_vector` 恒为 NULL；语义检索对全部文章返回空集，hybrid 退化为纯关键词 | `wiki.py:165-216` / `338-376` 均未调 `_enqueue_index`；`search_service.py:117` 用 `content_vector.isnot(None)` 过滤 |
| 2 | 存量修复手段 `reindex_all()` **没有任何 HTTP 入口**（全仓搜 `reindex` 无路由命中） | `rag_ingestor.py:51-71` |
| 3 | `_enqueue_index` 唯一实现者 `WikiArticleService` **只被用于 list/get**，没有创建或更新路由走它 | `wiki_admin.py:158 / 167` 是全仓唯一调用点 |
| 4 | OKF 的 **Bundle 三件套（index.md / log.md / frontmatter 键序）与宽容消费已落地**，但 per-claim 归因所需的关键字段 `sources[].id` 在 API schema 里缺失 | `okf_service.py:23/51/96/145/185`；`wiki.py:46-52` `DocSourceItem` 无 `id` |
| 5 | `verified` / `stale_after` 有模型列、有导出读，**但 API schema 无写入路径** | `wiki_article.py:72-73` vs `wiki.py:55-69` / `72-85` |
| 6 | Wiki 与 KB **完全无同步**（`app/services/wiki` 全目录检索 `KbDocument\|kb_segment` = 0 命中） | 唯一交集是都挂在 `kms_knowledge` |
| 7 | **OKF 导入丢字段**：只持久化 title / description / tags / status，`type` / `resource` / `sources` / `generated` / `verified` / `stale_after` 六个 frontmatter 字段**全部丢弃** | `okf_service.py:219-224`（新增）/ `228-232`（更新）均不含这些字段 |
| 8 | **导入文章的 `tenant_id` 为 `None`**，且 slug 冲突处理逻辑失效并可能**跨知识库静默覆盖** | `okf_service.py:220`（tenant_id=None）、`206-218`（while 条件恒假）、`206-208`+`227-233`（existing 全局查、命中即改别的库的文章） |

---

## 一、LLM Wiki 当前已实现功能

### 1.1 前端（`frontend/src/views/kms/wiki`）

**布局**：两栏（左树 + 右主区），**没有右侧详情栏** —— 详情走 `/wiki/:slug` 路由。

| 区块 | 实现情况 |
|---|---|
| 左栏 · 分类树 | 分类为父节点、知识库按 `kb.category_id` 挂为叶子，递归任意深度；无分类的 KB 归「未分类」组（不可选中） |
| 左栏 · 操作 | 新建分类 / 新建知识库；右键菜单 view / edit / add-child / rename / delete；分类与知识库的只读信息弹窗（`index.vue:534-760`） |
| 右栏 · 工具栏 | 搜索框、RAG 入口、**OKF 导出**（`index.vue:822-839`）、**OKF 导入**（`index.vue:841-870`）、新建文章 |
| 右栏 · 筛选条 | 按 tags / okf_type / status 筛选，可清空（`clearFilter`） |
| 文章列表 | 展示 tags、okf_type、sources 数、version、view_count、更新时间；行操作**仅「查看」「编辑」** |
| 分页 | `pageSize = 20` 为硬编码常量（`index.vue:304`），无 page-size 切换 |

**文章操作面（逐项判定）**

| 能力 | 判定 | 位置 / 证据 |
|---|---|---|
| 新建文章 | 已实现 | `index.vue:894` `handleCreate` |
| 编辑文章 | 已实现 | `ArticleEdit.vue:260` `handleSave` |
| 删除文章 | **仅详情页** | `ArticleView.vue:166` `handleDelete`；列表页无入口 |
| 文档 → Markdown 导入 | 已实现 | `DocUploadPanel.vue` → `convertDocument`（`api/wiki.ts:128`） |
| OKF Bundle 导出（zip） | 已实现 | `index.vue:822-839` → `api/kb.ts:100` `exportOkfBundle` |
| OKF Bundle 导入 | 已实现 | `index.vue:841-870` → `api/kb.ts:252` `importOkfBundle`（浏览器直读 `.md`/`.markdown` 文本，无 zip 解析依赖） |
| OKF 单篇预览 + 一键复制 | 已实现 | `ArticleView.vue:96-110` 抽屉，`openOkf:187` / `copyOkf:201` → `api/kb.ts:106` |
| Markdown 预览渲染 | 已实现 | MarkdownIt + DOMPurify（`ArticleView.vue:134 / 145`） |
| 版本时间线 / diff / 回滚 | 已实现 | `VersionTimeline` → `VersionDiffView` → `VersionRollbackButton` |
| 发布 / 归档 | **仅字段级** | `ArticleEdit.vue:105-111` radio（0 草稿 / 1 发布 / -1 归档）；列表页无状态过滤入口 |
| 移动（改归属 KB / 分类） | **部分** | 仅编辑页两个选择器（`ArticleEdit.vue:56-81`），列表页无拖拽 |
| 搜索 | **有 bug** | `index.vue:877` `handleSearch` → `searchArticles`；搜索结果**覆盖列表且分页 total 不同步**，清空才回列表 |
| 复制文章 | 未实现 | 代码与 API 均无 |
| 排序 | 未实现 | 无任何 order / sort 参数，`listArticles` 亦不支持 |
| 批量操作 | 未实现 | 列表无 selection 列与批量按钮 |
| page-size 切换 | 未实现 | 固定 20 |
| 重新向量化 / 重建索引 | 未实现 | 全前端无入口；`views/kms/kb/DatasetManagement.vue:103` 的 `rebuild()` 只弹 `message.info` 占位 |

**OKF 字段在前端的形态**：前端**没有** front-matter 解析（无 `gray-matter` / `js-yaml`，全仓 0 命中）。
字段由后端文档导入时提取（`convert_document` 返回 `okf_type` / `resource` / `sources`），前端以
`ArticleExtractedFields.vue` 动态表单渲染并可编辑（`setSource` / `addSource` / `removeSource`），
类型枚举 `OKF_TYPES`（`index.vue:329`、`ArticleEdit.vue:154`）。**没有 schema 校验**，只展示后端
返回的 warnings 数量。

**RAG 测试台（`RagTest.vue`）**：hybrid / semantic / keyword 三种检索模式（`onSearch:84` →
`POST /api/v1/wiki/search`）、AI 问答（`onAsk:98` → `POST /api/v1/wiki/ask`）、最近检索日志
（`loadLogs:112` → `GET /wiki/search-logs`）。⚠️ **未传 `knowledge_id`**，检索范围不随左栏选中
知识库收敛。

**i18n**：`wikiMgmt`（含 `art.*` / `cat.*` / `kb.*` / `rag.*` / `ver.*`）与 `kmsWiki`（含 `okf*` /
`docUpload*` / `extractedFields*` / `sources*`）两组 key，四语齐备。

**测试覆盖**：`__tests__/index.spec.ts` 仅 2 个用例，只测 `index.vue` 的 `embedded` prop
（默认渲染标题、`embedded=true` 反之），mock 了 `@/api/wiki` 与 `@/api/kb`。`ArticleView` /
`ArticleEdit` / `RagTest` / OKF 导入导出 / 版本组件 / 搜索分页 CRUD **全部零覆盖**。
`components/SearchBar.vue` 是全仓无引用的孤儿组件（RagTest 自带搜索 UI）。

### 1.2 后端（`app/routers/wiki/`）

| 文件 | 能力 |
|---|---|
| `wiki.py` | 文章 CRUD、slug 唯一性、版本快照与回滚、版本 diff、backlinks 更新、文档转换、搜索、问答、检索日志、**3 个 OKF 端点** |
| `wiki_admin.py` | 分类 / 知识库 CRUD、启用停用、列表 |
| `wiki_owl.py` | OWL 本体：class 增删查、层级、TTL 导入导出、stats、按 class 取文章 |
| `app/services/wiki/okf_service.py` | OKF v0.2 合规层（236 行） |
| `app/services/wiki/doc_converter.py` | 文档 → Markdown（PDF / Word / TXT / MD / PPT / Excel） |
| `app/services/wiki/search_service.py` | semantic / keyword / hybrid（RRF）检索 |
| `app/services/wiki/llm_wiki_service.py` | `/ask` 问答 |

---

## 二、文章导入的处理链路

### 2.1 三条入口，全部收敛到 `kms_article`

```
入口 ①  文档导入（PDF/Word/TXT/MD/PPT/Excel）
  DocUploadPanel 选择文件
    → POST /api/v1/wiki/articles/convert-document          wiki.py:379
    → app/services/wiki/doc_converter.py                   只转不落库，返回 Markdown
    → 前端填充编辑器 + 提取 okf_type / resource / sources
    → 落到入口 ②

入口 ②  文章写入（前端新建 / 编辑走的就是这条）
  POST /api/v1/wiki/articles                    wiki.py:165-216
    ├ slug 唯一性检查（冲突 → 409）
    ├ 建 WikiArticle + WikiArticleVersion(version=1, change_note="初始创建")
    ├ _update_backlinks(db, article)
    └ db.commit()          ← 此处结束，没有 _enqueue_index

  PUT /api/v1/wiki/articles/{id}                wiki.py:338-376
    ├ 逐字段 setattr（exclude_none，排除 change_note）
    ├ version += 1 → 建 WikiArticleVersion 快照
    ├ _update_backlinks
    └ db.commit()          ← 此处结束，没有 _enqueue_index

入口 ③  OKF Bundle 导入
  POST /api/v1/wiki/knowledges/{id}/okf-import    wiki.py:938
    → okf_service.import_bundle(files: List[{path, content}])      okf_service.py:185
        ├ 跳过 index.md / log.md
        ├ parse_frontmatter(text)                宽容解析，YAML 失败 → type=concept 退化
        ├ 按 slug upsert 文章 + 匿名分类挂载
        └ 返回 {imported, skipped, warnings}
                                              ← 同样没有触发向量化
```

### 2.2 向量化环节（重点）

**唯一实现**：`app/services/wiki/rag_ingestor.py`

```python
def index_article(self, article_id: int) -> None:            # rag_ingestor.py:26
    article = db.get(WikiArticle, article_id)
    client = get_embedding_client()                          # app/ai/embedding_client.py:303
    vector = client.embed_sync(article.content or "")        # 整篇内容 → 一个向量
    article.content_vector = vector
    db.commit()
```

| 环节 | 事实 |
|---|---|
| 触发点 | 仅 `WikiArticleService._enqueue_index`（`article_service.py:98 / 156 / 233-246`）与 `version_service.py:91-95` |
| `WikiArticleService` 的实际使用 | 全仓**仅** `wiki_admin.py:158 / 167` 调用其 `list()` / `get()`；**没有任何创建或更新路由走它** |
| 前端实际走的路径 | `wiki.py` 的内联 `create_article` / `update_article`，两者都**没有**调用 `_enqueue_index` |
| 后果 | 前端创建 / 编辑 / OKF 导入的文章，`kms_article.content_vector` **永远是 NULL** |
| 检索侧 | `search_service.py:117` 用 `WikiArticle.content_vector.isnot(None)` 过滤 → 语义检索对全部文章返回空集；hybrid 退化为纯关键词 + 单边 RRF |
| 存量修复 | `WikiRAGIngestor.reindex_all(batch_size=200)`（`rag_ingestor.py:51-71`）存在，但**没有任何 HTTP 入口**（全仓搜 `reindex` 无路由命中） |
| 失败语义 | embedding 不可用 → `logger.warning` 后静默 `return`，**无记录、无重试、无降级标记** |

### 2.3 Wiki 向量化 vs KB 向量化（对照）

| 维度 | KB 文档链路（标准形态） | LLM Wiki 链路 |
|---|---|---|
| 分段 | `pipeline_runner.run_pipeline`：parse → clean → chunk；`ParentChildChunker` / `QaChunker` / `approx_token` | **不分段**，整篇一个向量 |
| 被向量化的对象 | text 块；QA **仅问题**（答案进 metadata，`chunker_factory.py:37-53`）；表格行 `embed_field` 列（`:56-70`）；图片 caption / OCR 文本（`content_service.py:190-242`）。`chunk_type='parent'` 与 `keywords` **不嵌**（`index_mode.py:20`、`segment_service.py:24/56-60/130-134`） | 仅整篇 `content` |
| embedding 装配 | `kb/embedding_config.py:24` `SUPPORTED_PROVIDERS=(gpustack,nvidia,dashscope)` → `resolve_embedding_config:39` → `rag/embedding_factory.build_embedding_model:30`（AgentScope `DashScopeEmbeddingModel` / `OpenAIEmbeddingModel`） | **另一套**：`app/ai/embedding_client.py:303` `get_embedding_client()`（wiki / ontology 共用） |
| 向量落库 | `kb_segment.embedding`，`Vector(settings.GPUSTACK_EMBEDDING_DIMENSION)`（`kb_segment.py:30-32`，默认 768）；真值取 `kb_collection.dimensions`（`kb_collection.py:20`），建库时写入 | `wiki_article.content_vector`（`wiki_article.py:34`） |
| 索引 | `startup_migrations.py:191-199`：`hnsw (embedding vector_cosine_ops) m=16 ef_construction=64` + `gin(content gin_trgm_ops)`；`create_performance_indexes:203` 幂等补建；含 `kms_article.content_vector` HNSW | 同库 HNSW |
| 增量 / 重建 | `index_mode.py`：`upgrade_to_high_quality:150` / `downgrade_to_economy:201` / `reembed_collection:186` / `_embed_texts:49`（64 限批）/ `_fill_documents:81`（`only_null` 区分回填与重灌）/ `_ensure_vector_indexes:215`；`collection_settings.apply_collection_settings:44` 返回后台 job；`segment_service.reembed_document_segments:137`；API `kb.py:261-312`（index-mode）、`544-592`（settings）、`399-419`（reprocess）。进度写 `kb_document.meta['index_upgrade'\|'reembed']`，**无 checkpoint** | 只有 `reindex_all()`，**无 API、无进度、无断点** |
| 后台任务 | `app/core/job_runner.run_in_background`（守护线程 + 独立 Session） | `_enqueue_index` 自己的守护线程 |
| 失败处理 | `PipelineStepError`（带 step 名，`pipeline_runner.py:74`）→ `document_pipeline._fail:27-33` 写 `status='failed'` + `error_detail='[step] ...'`；**无重试**；重嵌时单文档失败不中断整批；economy 是唯一降级路径 | 全静默降级（`rag_ingestor.py:36-40/46-49`、`search_service.py:106-113/122-126`） |
| 多模态 | 图片独立 `chunk_type='image'` 段，**仅文搜图**（`multimodal_enabled` + Vision embedding） | 无 |

**KB 侧完整链路（供对照）**：
`upload_document`（`routers/kb/kb.py:87-134`，权限 `require_kb_permission(KB_UPLOAD)`）→ 建
`KbDocument(pending)` → `job_runner.run_in_background` → `document_pipeline.run_document_ingest:50`
（置 `processing` → `_resolve_pipeline_config:43` / `_resolve_index_mode:36` → `knowledge_base:105`）
→ `pipeline_runner.run_pipeline:181`（parse `parser_selector.select_parser:69` → clean → chunk
`chunker_factory.build_chunker:15`）→ `rag/knowledge_factory.knowledge_base:35`（注入
`metadata_filter={"tenant_id": ...}`）→ `rag/pg_vector_store.insert:105`（先删后插幂等）→ 写
`KbSegment` 行。

### 2.4 两条链路的隔离现状

- **无同步**：对 `app/services/wiki` 全目录检索 `KbDocument | kb_segment` = 0 命中。wiki 文章不会
  被同步成 KB 文档，也不会分段、不走 index_mode、不进 KB 检索管线。唯一交集是都挂在
  `kms_knowledge` 下。
- **租户隔离**：KB 链路在路由层取 `current_user.tenant_id`（`kb.py:37`）→ 传入
  `PgVectorStore(tenant_id=)`（`pg_vector_store.py:41`）→ 构造期固化 `metadata_filter:61`、
  `insert` 随行写 `meta["tenant_id"]`（`:109/120`）、`search` SQL `WHERE tenant_id=:t`（`:166`）。
  Wiki 侧依赖 `TenantMixin`（`app/models/tenant_mixin.py:14`）+ `deps.get_current_user`；
  ⚠️ `search_service._apply_filters:153-158` **只按 knowledge_id / owl 过滤，未加 tenant_id 条件**，
  内联 `create_article` / `update_article` 也未显式写 tenant_id —— 此处是全仓隔离最弱的点。
- ⚠️ 更严重的是 **OKF 导入**：`import_bundle` 构造 `WikiArticle` 时写死 `tenant_id=None`
  （`okf_service.py:220`），导入的文章**不属于任何租户**，却能被无 tenant 过滤的
  `_apply_filters` 检索到 → 跨租户可见。

### 2.5 顺带发现的缺陷

| # | 缺陷 | 位置 |
|---|---|---|
| 1 | `guess_media_type` 的扩展名表含 **pptx**，但未注册 `PPTXParser` → 上传 .pptx 会在 `select_parser` 抛「不支持的文件类型」。而 wiki 侧 `doc_converter` 是支持 PPT 的，两侧能力不一致 | `kb/parser_selector.py:51 / 75` |
| 2 | 集合设置面板的 `rerank_provider` / `rerank_model` / `top_k` / `score_threshold` **只落库未被检索链路消费**（`kb.py:228-239` 未传 rerank）；`PgVectorStore.hybrid` 标志（`:45/51`）未被 `search`（`:145-178`）使用 | `kb/collection_settings.py:25-33` |
| 3 | `wiki.py` 内联实现与 `WikiArticleService` 是**重复的两套文章写入逻辑**，只有后者有 `_enqueue_index`。已核实：`WikiArticleService.create` / `update` 全仓**无调用者**（`wiki_admin.py:158/167` 只调 `list` / `get`），是死代码；注册进路由的是 `wiki.py`（`router_registry.py:171-176`），没有任何开关或配置把 type=1 指向 service | `wiki.py:165/338` vs `article_service.py:69`；`router_registry.py:171-176` |
| 4 | `doc_converter` 侧 `.pptx` 支持完整（`SUPPORTED_EXTS` 含 `.pptx`，`_from_pptx` 用 `python-pptx`），**与 KB 侧缺 `PPTXParser` 的缺陷方向相反** —— 同一份 pptx 走 wiki 导入可用、走 KB 上传被拒 | `wiki/doc_converter.py:33 / 93-94 / 198` |

---

## 三、对比 OKF v0.2 规范

### 3.1 规范基线

- 规范原文：`GoogleCloudPlatform/knowledge-catalog` → `okf/SPEC.md`（v0.2，supersede v0.1）。
- 定位：OKF 是 Karpathy LLM-Wiki 理念的厂商中立标准化 —— Markdown + YAML frontmatter、
  文件即知识库、Git 可管理、无 SDK / 运行时依赖。
- 仓库内设计基线：`docs/superpowers/specs/2026-09-27-knowledge-unification-design.md` §9
  （§9.1 合规差距核查表、§9.2 模型增列、§9.3 服务层、§9.4 端点、§9.5 前端、§9.6 推迟项）。

### 3.2 已补齐（8 项）

| 规范要求（§编号） | 实现位置 |
|---|---|
| §11.2 每个概念文件含可解析 YAML frontmatter，**非空 `type` 唯一必填** | `okf_service.serialize_article:51`（`meta["type"] = article.okf_type or "concept"`）+ `parse_frontmatter:23`；UI 侧有 `OKF_TYPES` 枚举可选（`index.vue:329`、`ArticleEdit.vue:154`） |
| §2.2 推荐字段 `title` / `description` / `tags` / `resource` | 全部有（`summary` ≈ `description`） |
| §5.4 `status`: `draft\|stable\|deprecated`，缺省 = stable | `_status_to_okf:38`，`0→draft / 1→stable / -1→deprecated`，未知值宽容落 stable |
| §3 / §8 Bundle 结构：概念文件 + 每层 `index.md` 条目列表（渐进披露） | `export_bundle:96`；`_index_md:145`；根 index.md 独占 `okf_version: "0.2"`（`:149/160`） |
| §9 `log.md`（ISO 日期分组、最新在前） | `export_bundle:162-181`，由 `kms_article_version` 生成 |
| §11.3 宽容消费：不得因缺可选字段 / 未知 type / 未知键拒绝 | `parse_frontmatter:23`（无 frontmatter 或 YAML 失败 → 退化 `type=concept` 继续）；`import_bundle:185` |
| §5.5 `stale_after` 绝对过期时间点 | 模型列 `wiki_article.py:73` + 导出 `_format_stale_after:45` |
| §5.2 `verified` 验证事件列表 | 模型列 `wiki_article.py:72` + 导出分支 `okf_service.py:64-65` |

三个端点齐备：`GET /knowledges/{id}/okf-export`（`wiki.py:890`）、`GET /articles/{id}/okf`
（`wiki.py:917`）、`POST /knowledges/{id}/okf-import`（`wiki.py:938`）。

### 3.3 差距矩阵

| # | 规范要求（§编号） | 现状（已逐行核实） | 严重度 |
|---|---|---|---|
| 1 | 导入 / 创建 / 编辑后应可被语义检索（§11.3 消费即完整） | 三条入口都不触发向量化，`content_vector` 恒 NULL；`reindex_all` 无 HTTP 入口 → 导入的 Bundle 与手写文章的语义检索**全部为空** | 🔴 阻断 |
| 2 | §6.1 Bundle 往返（导出即可导回） | **导出物是 zip，导入只接受前端直读的 `.md` / `.markdown` 文本**（`index.vue:841-870`，浏览器无 zip 解析依赖）→ 导出的 Bundle 无法导回 | 🔴 |
| 3 | **往返保真**（§2.2 / §5.1 / §5.2 / §5.5，验收标准 6「内容与分类挂载无损」） | 已核实：`import_bundle` 只持久化 `title` / `description` / `tags` / `status`，**丢弃 `type` / `resource` / `sources` / `generated` / `verified` / `stale_after` 六个 frontmatter 字段**（`okf_service.py:219-224` 新增分支、`228-232` 更新分支均不含）。导出→导入往返丢一半字段 | 🔴 |
| 4 | 租户隔离 | 已核实：导入文章写死 `tenant_id=None`（`okf_service.py:220`）；且 `search_service._apply_filters:153-158` 不按 tenant 过滤 → 导入内容对其它租户可见 | 🔴 |
| 5 | slug 作用域与冲突处理 | 已核实：`existing` 是**全局**按 slug 查，不限 `knowledge_id`（`okf_service.py:206-208`）；命中时走 update 分支且**不改 `knowledge_id`** → **跨知识库静默覆盖别人的文章**。而 `existing is None` 分支里的 while 循环条件恒为假（刚查出 existing 就是 None）→ 文档声称的「`-2` 后缀 + 计入 warnings」**永不触发**（`:210-218`） | 🔴 |
| 6 | §5.1 `sources[].id` 作 footnote join 键 | API schema `DocSourceItem`（`wiki.py:46-52`）只有 `resource` / `title` / `author` / `last_modified`，**没有 `id`**；而模型注释（`wiki_article.py:70`）声明支持 `id` / `usage_count` → 经 API 保存必然丢 `id` | 🔴 |
| 7 | §6.1 per-claim 归因：footnote label = `sources[].id` | 缺 join 键；正文无 footnote ↔ sources 机制（问答层的 Citations 是另一回事） | 🔴 |
| 8 | §5.2 `generated.by` / §7 Actor 信任分层 | 已核实：导出**硬编码** `author_actor="process:minworkbuddy-wiki"`（`okf_service.py:138`），**从不产出 `human:<username>`** → actor 信任分层实际未实现（此前判断为"导出时 creator join 拼 human actor"，**该判断错误，已更正**）；create / update 接口亦不接收 actor | 🟡 |
| 9 | §5.2 `verified` / §5.5 `stale_after` | 有列、有导出，**API schema 无写入路径**，导入侧也丢弃；且无过期提醒 / stale 标记展示 | 🟡 |
| 10 | §5.1 `usage_count` / `usage_window` | 模型注释有 `usage_count`，schema 与写入路径都没有；设计文档 §9.6 已列为推迟项 | 🟡 |
| 11 | §6.1 链接重写（导出 `/wiki/<slug>` → bundle 相对路径，导入反向还原） | 已核实：`serialize_article:69` 原样输出 `article.content`，`import_bundle:229` 原样存 `body` → **双向都无重写**。（`_index_md:155` 的 `(slug).md` 是 index 自身生成，不是正文重写） | 🟡 |
| 12 | §11.3 断链的「容忍」 | 已核实：确实容忍（body 原样存，不拒绝），但**不检测、不报告** → 报告中无断链分项 | 🟢 |
| 13 | §11.3 宽容消费的**报告化** | 后端返回 `{imported, skipped, warnings}`，无 schema 校验；前端只显示 warnings 数量，无分项明细 | 🟢 |
| 14 | §5.2 `generated.at` 时区（§11 风险表「时序往返不丢失」） | 已核实：`art.updated_at.isoformat() + "Z"` 直接拼 `Z`（`okf_service.py:139`）；若 DB 存的是本地时间，则时区标注不实 | 🟢 |
| 15 | 版本快照与反向链接（非规范项，但影响 §9 `log.md`） | 已核实：导入不建 `WikiArticleVersion` 快照、不调 `_update_backlinks` → 导入文章在 `log.md` 中无历史、无反向链接 | 🟢 |
| 16 | §4.2 Body heading 约定（`# Schema` / `# Examples` / `# Computation`） | 无约定、无 lint | 🟢 |
| 17 | §3 `references/` 惯例目录 | 已核实：`export_bundle` 只产出 `<slug>.md` / `<dir>/index.md` / `log.md`，**无 `references/`** | 🟢 |
| 18 | §10 Attested Computation 家族（`runtime` / `parameters` / `computation` / `executor` / `attester`） | 无。设计文档 §9.6 已**明确推迟** | ⚪ 推迟 |

对照设计文档 §9.1 的 12 项原始核查表：当时判定「0 项完整、4 项部分可映射」，其中 frontmatter、
`status` 映射、`index.md` / `log.md` 结构、宽容消费这 4 项现已补齐；`sources` 家族与 per-claim
归因**从"无字段"变成了"有字段但缺 join 键且导入侧整体丢弃"**，是同一处的部分推进。

**逐行核实后，🔴 项由 4 项增至 6 项**：新增「往返丢字段」（矩阵第 3 条）与「租户 / slug 作用域」
（第 4、5 条）。这三项是**实现缺陷**而非规范差距 —— 它们不在设计文档 §9.1 的差距表里，属于
Phase 2 落地时引入的问题，应优先于任何规范补齐项处理。

### 3.4 补齐顺序（三批）

**第一批 —— 阻断级：先修实现缺陷，再谈规范**

1. **导入字段往返**（矩阵第 3 条）：`import_bundle` 的构造与更新两处都要补
   `okf_type` / `resource` / `sources` / `verified` / `stale_after` 的写入，并读回 `meta["type"]`
   落到 `okf_type`。导出→导入 round-trip 用例必须进 pytest（设计文档 §11 风险表已要求）。
2. **租户与 slug 作用域**（第 4、5 条）：
   - 导入时写入 `user.tenant_id`，并把 `tenant_id` 纳入 `existing` 查询条件；
   - `existing` 查询加 `knowledge_id` 约束，命中同库文章才 upsert，跨库 slug 冲突按
     「加 `-2` 后缀新建 + 计入 warnings」处理；
   - 修掉 while 循环条件恒假的 bug（当前 `-2` 后缀与 warnings 永不触发）；
   - 顺带修 `search_service._apply_filters:153-158` 缺 tenant 过滤。
3. **打通向量化**：把 `wiki.py` 的 `create_article` / `update_article` / `okf_import_bundle` 接到
   `_enqueue_index`；更彻底的做法是删掉内联实现、统一走 `WikiArticleService`（消掉 §2.5 第 3 条的
   重复逻辑，同时让 service 的 `create` / `update` 不再是死代码）。同时补
   `POST /api/v1/wiki/reindex`（后台任务 + 逐篇进度 + 失败明细）作为存量修复入口，
   复用 `app/core/job_runner.run_in_background` 的既有约定。
4. **Bundle 往返打通**（第 2 条）：二选一 —— 前端引入 zip 解析依赖（`jszip`）；或后端 `okf-import`
   直接收 `multipart/form-data` 的 zip 并在服务端解包。**推荐后者**：解析留在服务端，浏览器不承担
   zip 依赖，且与设计文档 §9.4 的端点契约一致。
5. **`DocSourceItem` 补 `id`（必填）与 `usage_count`**：`id` 作为 footnote join 键必填，导入时若缺
   `id` 则宽容退化（不拒绝）并在 warnings 中报告。随后补 per-claim 归因：正文 `[^id]` 原样导出，
   与 `sources[].id` 按键 join（不按位置）。

**第二批 —— 合规完整性**

6. `ArticleCreateRequest` / `ArticleUpdateRequest` 补 `verified` 与 `stale_after` 写入路径（矩阵第 9 条）。
7. **产出真正的 actor**（第 8 条）：`export_bundle` 现在硬编码 `process:minworkbuddy-wiki`，
   应按 `creator_id` join `sys_user` 产出 `human:<username>`，仅当无 creator（系统生成）时才用
   `process:`；`generated.at` 统一转 UTC 后再拼 `Z`，不要直接给本地时间打 `Z` 标签（第 14 条）。
8. `okf_service` 补链接重写（第 11 条）：导出把 `/wiki/<slug>` 改写为 bundle 相对路径，导入反向还原，
   断链原样保留并计入 warnings。

**第三批 —— 体验与规范细节**

9. 导入报告升级为含 schema 校验分项（未知 type / 未知键 / 断链 / slug 冲突分别计数），前端展示明细（第 12、13 条）。
10. stale 过期提示：文章列表与详情页标记 `stale_after` 已过期；补 `references/` 目录生成（第 17 条）；
    Body heading lint（第 16 条）；导入时补建 `WikiArticleVersion` 快照与 `backlinks`（第 15 条）。
11. Wiki 前端补缺：排序、批量操作、列表页删除、page-size 切换；修「搜索覆盖列表且分页 total 不同步」
    的 bug；`RagTest` 传 `knowledge_id` 收敛检索范围；清理死代码 `components/SearchBar.vue`；
    补 `ArticleView` / `ArticleEdit` / `RagTest` / OKF 往返的测试。

---

## 附录 A：关键证据索引

| 主题 | 文件 | 关键行 |
|---|---|---|
| 文章创建（不触发向量化） | `backend/app/routers/wiki/wiki.py` | 165-216 |
| 文章更新（不触发向量化） | 同上 | 338-376 |
| OKF 溯源条目 schema（缺 `id`） | 同上 | 46-52 |
| OKF 三个端点 | 同上 | 890 / 917 / 938 |
| 向量化唯一实现 | `backend/app/services/wiki/rag_ingestor.py` | 26-49 |
| 存量重建（无入口） | 同上 | 51-71 |
| `_enqueue_index`（唯一触发点） | `backend/app/services/wiki/article_service.py` | 98 / 156 / 233-246 |
| `WikiArticleService` 唯一调用点 | `backend/app/routers/wiki/wiki_admin.py` | 158 / 167 |
| 语义检索过滤 NULL 向量 | `backend/app/services/wiki/search_service.py` | 117 |
| 租户过滤最弱处 | 同上 | 153-158 |
| OKF 合规层全貌 | `backend/app/services/wiki/okf_service.py` | 23 / 38 / 45 / 51 / 96 / 145 / 185（共 236 行，已逐行核实） |
| 导入丢字段 / tenant / slug 作用域 | 同上 | 206-233（其中 `220` tenant_id=None、`210-218` while 恒假） |
| actor 硬编码 + 时区拼 Z | 同上 | 138 / 139 |
| `_enqueue_index`（经 job_runner 后台提交） | `backend/app/services/wiki/article_service.py` | 233-246 |
| wiki router 注册（无 type=1 开关） | `backend/app/core/router_registry.py` | 171-176 |
| `doc_converter` 支持 .pptx | `backend/app/services/wiki/doc_converter.py` | 33 / 93-94 / 198 |
| OKF 模型增列 | `backend/app/models/wiki/wiki_article.py` | 34 / 56 / 63 / 67 / 68-70 / 72 / 73 |
| 向量列维度 | `backend/app/models/kb/kb_segment.py` | 30-32 |
| 集合维度真值 | `backend/app/models/kb/kb_collection.py` | 20 |
| embedding provider 选择 | `backend/app/services/kb/embedding_config.py` | 24 / 39-78 |
| embedding 模型构造 | `backend/app/services/kb/rag/embedding_factory.py` | 30-58 |
| Wiki 侧 embedding 客户端 | `backend/app/ai/embedding_client.py` | 303-349 |
| HNSW / GIN 索引 | `backend/app/db/startup_migrations.py` | 191-199 / 203 |
| 索引升降级与重灌 | `backend/app/services/kb/index_mode.py` | 20 / 49 / 81 / 150 / 186 / 201 / 215 |
| KB 摄取编排 | `backend/app/services/kb/document_pipeline.py` | 27-33 / 36 / 43 / 50-139 |
| KB 解析/清洗/切块 | `backend/app/services/kb/pipeline_runner.py` | 74 / 181-230 |
| KB 向量写入 | `backend/app/services/kb/rag/pg_vector_store.py` | 41 / 61 / 73-88 / 105-133 |
| 前端 wiki 主页| `frontend/src/views/kms/wiki/index.vue` | 304 / 322 / 408-412 / 454-499 / 534-760 / 822-870 / 877 / 894 |
| 前端文章查看/编辑 | `.../wiki/ArticleView.vue`、`ArticleEdit.vue` | 96-110 / 166 / 187 / 201；56-81 / 105-111 / 154 / 260 |

## 附录 B：逐行验证结论（2026-10-09 完成）

已逐行读完 `okf_service.py`（236 行全文）、`article_service.py:1-70 / 200-247`、`doc_converter.py`
相关段、`router_registry.py` wiki 段。原 6 条待验证项的结论如下：

| # | 原问题 | 验证结论 | 对正文的影响 |
|---|---|---|---|
| 1 | `export_bundle` 是否生成 `references/` | **确认不生成** —— 只产出 `<dir>/<slug>.md`、`<dir>/index.md`（根为 `index.md`）、`log.md`（`okf_service.py:130-182`） | 保留为差距矩阵第 17 条（🟢） |
| 2 | `import_bundle` 是否检测正文断链 | **确认不检测** —— body 原样存入（`:229`），docstring 声称的"断链一律接受"是**容忍**而非检测，报告中无断链分项 | 保留为第 12 条（🟢） |
| 3 | `doc_converter` 是否覆盖 `.pptx` | **确认支持** —— `SUPPORTED_EXTS` 含 `.pptx`（`:33`），`_from_pptx` 用 `python-pptx`（`:198`）。与 KB 侧缺 `PPTXParser` 的缺陷**方向相反** | 已写入 §2.5 第 1、4 条 |
| 4 | `_enqueue_index` 是否真起后台线程、异常是否吞掉 | **确认** —— `article_service.py:233-246` 经 `app/core/job_runner.run_in_background` 提交，`WikiRAGIngestor` 内自建 `SessionLocal`，异常在 `rag_ingestor.py:36-40 / 46-49` 被吞为 warning | 正文 §2.2 表述准确，无需修订 |
| 5 | 是否有开关把 type=1 指向 `WikiArticleService` | **确认没有** —— `router_registry.py:171-176` 注册的是 `app.routers.wiki.wiki`；`WikiArticleService.create` / `update` 全仓无调用者（`wiki_admin.py:158/167` 只调 `list` / `get`），是死代码 | **§2.2 结论成立，无需修订**；该事实已写入 §2.5 第 3 条 |
| 6 | 链接重写是否内联在 `_index_md` | **确认双向都无重写** —— `serialize_article:69` 原样输出 `article.content`，`import_bundle:229` 原样存 `body`；`_index_md:155` 的 `(slug).md` 只是 index 文件自身的相对链接生成 | 保留为第 11 条（🟡） |

### 验证中新发现的缺陷（原附录 B 未列出，已并入矩阵）

| # | 新发现 | 依据 |
|---|---|---|
| A | **导入丢弃 6 个 frontmatter 字段**：`type` / `resource` / `sources` / `generated` / `verified` / `stale_after` 在新增分支（`:219-224`）与更新分支（`:228-232`）都不写入 → 导出→导入往返不保真 | `okf_service.py:219-232`；矩阵第 3 条 |
| B | **导入文章 `tenant_id=None`**，且 `search_service._apply_filters` 无 tenant 过滤 → 跨租户可见 | `okf_service.py:220` + `search_service.py:153-158`；矩阵第 4 条 |
| C | **slug 冲突逻辑失效 + 跨库覆盖**：`existing` 全局查 slug 不限 `knowledge_id`；命中时更新别的库的文章且不改 `knowledge_id`；`existing is None` 分支的 while 条件恒假 → `-2` 后缀与 warnings 永不触发 | `okf_service.py:206-218 / 227-233`；矩阵第 5 条 |
| D | **`generated.by` 硬编码 `process:minworkbuddy-wiki`，从不产出 human actor**（此前判断"creator join 拼 human actor"是**错的**） | `okf_service.py:138`；矩阵第 8 条 |
| E | `generated.at` 直接用 `updated_at.isoformat() + "Z"`，DB 若存本地时间则时区标注不实 | `okf_service.py:139`；矩阵第 14 条 |
| F | 导入不建 `WikiArticleVersion` 快照、不调 `_update_backlinks` → 导入文章在 `log.md` 无历史、无反向链接 | `okf_service.py:219-234`；矩阵第 15 条 |

**对"是否需要补齐"的最终判断**：**需要，且优先级要重排**。原矩阵把「导入往返 / 租户 / slug」
当作规范差距的附属项，逐行核实后它们是实现缺陷 —— 应在任何规范补齐之前处理（已上调为
§3.4 第一批第 1、2 项）。规范类补齐（链接重写、actor、references/、heading lint）维持原批次不变。