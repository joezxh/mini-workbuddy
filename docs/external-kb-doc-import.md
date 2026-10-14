---
name: external-kb-doc-import
overview: 完善「新建/编辑知识库」：①类别默认带出当前选中类别；②外部知识库向导改为分步流程（选平台→填凭据→测试连通→浏览目录/文档→设切片→导入），为飞书/钉钉/语雀/企微/Notion 五平台写真实文档枚举与正文拉取（Block→Markdown）；③外部知识库支持随时手动「重新选择文档」，按 kb_external_doc_map 映射表做到已有覆盖、缺失新建；④编辑知识库时锁定类型不可变更；⑤按已确认的预览原型统一知识库管理页界面——左树「分类+三类知识库叶子用不同图标」，右侧 Wiki 面板与通用面板按预览重做（统计卡/工具栏/表格/分页/空态）。
design:
  architecture:
    framework: vue
  styleKeywords:
    - Yao Agents CUI
    - Ant Design Vue v6
    - 两栏树+内容
    - 分步向导
    - 克制微交互
  fontSystem:
    fontFamily: Outfit
    heading:
      size: 16px
      weight: 600
    subheading:
      size: 14px
      weight: 500
    body:
      size: 13px
      weight: 400
  colorSystem:
    primary:
      - "#3371fc"
      - "#2b5fd9"
    background:
      - "#ffffff"
      - "#f5f7fa"
      - "#e6f0ff"
    text:
      - "#1f2329"
      - "#646a73"
    functional:
      - "#52c41a"
      - "#3371fc"
      - "#d0d5dd"
      - "#ff4d4f"
todos:
  - id: ui-left-tree
    content: 左树按预览统一（分类为父节点、三类知识库叶子用不同图标、计数徽标、可折叠、未分类分组）
    status: pending
  - id: ui-wiki-pane
    content: Wiki 面板按预览重做（统计卡/面板头/工具栏+分类筛选/文章表/分页/空态）
    status: pending
  - id: ui-general-pane
    content: 通用面板按预览重做（形态分段控件/统计卡/文档表含状态与分段数/空态）
    status: pending
  - id: doc-source-abstraction
    content: 新增 doc_sources 抽象层（BaseDocSource/注册表/Markdown 转换器）与 kb_external_doc_map 映射表模型
    status: pending
    dependencies:
      - ui-general-pane
  - id: provider-impls
    content: 实现飞书、钉钉文档、语雀、企业微信文档、Notion 五个平台的连通性测试、目录枚举与正文转 Markdown
    status: pending
    dependencies:
      - doc-source-abstraction
  - id: import-api
    content: 新增 external_import_service 与 external-sources 路由（providers/test/nodes/import/列表），实现覆盖或新建
    status: pending
    dependencies:
      - provider-impls
  - id: backend-tests
    content: 编写 5 平台文档源与导入服务单测（含覆盖/跳过/失败隔离/租户隔离），注册路由
    status: pending
    dependencies:
      - import-api
  - id: wizard-component
    content: 新增 kbExternalSource API 封装与 ExternalSourceWizard 五步向导组件（复用切片动态表单）
    status: pending
    dependencies:
      - import-api
  - id: kb-manager-integration
    content: 改造 KnowledgeBaseManager 接入向导、编辑态锁定类型、收敛类别默认带出
    status: pending
    dependencies:
      - wizard-component
  - id: external-pane-i18n
    content: 改造 ExternalLinkPane 为文档列表+重新选择文档入口，补齐四语 i18n 文案
    status: pending
    dependencies:
      - kb-manager-integration
  - id: verify-e2e
    content: 运行后端 pytest 与前端定向 build，用 [mcp:Playwright MCP Server] 实机走查向导全流程与三类面板界面
    status: pending
    dependencies:
      - backend-tests
      - external-pane-i18n
      - ui-left-tree
      - ui-wiki-pane
      - ui-general-pane
---

## 用户需求

完善「新建 / 编辑知识库」功能，按以下四条规则处理。

## 核心功能

### 1. 所属类别默认带出

新建知识库时，「所属类别」默认选中用户当前点击过的类别；编辑知识库时，默认与该知识库所在类别保持一致。

### 2. 外部知识库文档导入向导（类型选「外部知识库」时）

在原有「检索代理（proxy）」之外，新增「文档导入」方式，按分步向导完成：

- **第 1 步 选择平台**：飞书、钉钉文档、语雀、企业微信文档、Notion。
- **第 2 步 填写凭据**：按平台填写 API Key / App ID / Secret /仓库（Namespace）等参数，并可**测试连通性**，连通后才可继续。
- **第 3 步 选择文档**：浏览目标知识库的**目录（空间/知识库节点）与具体文档**，目录可下钻，文档可勾选。
- **第 4 步 设置切片方案**：选择切片方式与参数。
- **第 5 步 导入**：将选中的外部文档正文导入为知识库文档并完成切片入库。

### 3. 随时重新选择外部文档

外部知识库配置完成后，提供「**重新选择文档 / 重新同步**」入口，可随时再次从外部平台挑选文档导入；**已存在的文档执行覆盖（更新正文并重新切片），不存在的文档新建文件**。

### 4. 编辑时锁定类型

编辑已有知识库时，类型不可变更（只读展示并提示），仅可修改名称、描述、所属类别等。

### 5. 按预览原型统一界面（含 Wiki 与通用知识库）

已生成两份可交互 HTML 原型并经 review，作为本次 UI 实现的**视觉与功能基准**：

- `docs/prototypes/external-kb-import-preview.html`：外部知识库面板（统计卡 + 平台彩色标签 + 文档表 +「重新选择文档」入口 + 空态）与五步导入向导。
- `docs/prototypes/kb-manager-preview.html`：知识库管理页统一风格，左侧「类别 + 知识库」树；右侧按类型切换 6 态 —— 空态·未选择 / Wiki / 通用·有文档 / 通用·空态 / 外部·有文档 / 外部·空态。

需按预览改造：

1. **左树**：分类为父节点（可折叠、带计数徽标），知识库为叶子；三类用不同图标区分 **Wiki / 通用 / 外部**；「未分类」作兜底分组。
2. **Wiki 面板**：补统计卡（总数/已发布/草稿/本月新增）、面板头（标题+副标题+操作区）、工具栏补分类筛选；文章表含 slug·版本/分类/状态/更新时间/浏览量/操作；分页；无文章时的空态。
3. **通用面板**：补统计卡（文档数/已完成/处理中/失败）；文档表含状态标签（completed/processing/failed）、**分段数**、更新时间、操作（分段/流程/重试/删除）；无文档时的大空态 + 上传引导；表格/问答/流水线子面板视觉统一。

## 视觉效果

沿用工作台既有设计语言（antd v6、左侧树 + 右侧内容两栏、主色 `#3371fc`）。向导以弹窗分步卡片呈现，每步带步骤条与「上一步 / 下一步 / 测试连通 / 开始导入」操作区；平台选择以卡片网格呈现并带平台图标；文档浏览区为可展开目录树 + 勾选框，显示标题、更新时间、导入状态标签；导入结果以「新增 / 更新 / 未变更 / 失败」四类统计汇总展示。

**三类面板（Wiki / 通用 / 外部）共用同一套视觉基准**，以 `docs/prototypes/kb-manager-preview.html` 为准：顶部面板头（标题 + 副标题 + 右侧操作区）→ 形态分段控件（仅通用）→ 四格统计卡（hover 轻抬升）→ 工具栏（搜索 / 筛选 / 排序）→ 数据表格（行 hover 浅底、状态用彩色标签）→ 分页；无数据时统一使用大空态（图标 + 标题 + 说明 + 主行动按钮）。设计 token：主色 `#3371fc`、浅底 `#e6f0ff`、圆角 8px、过渡 0.15–0.2s。

## 一、技术栈与约束（基于现有代码确认）

- **后端**：Python 3.12 / FastAPI / SQLAlchemy 2.0 / Pydantic v2 / httpx；PostgreSQL。
- **前端**：Vue 3 + TypeScript + Vite + **Ant Design Vue v6**（项目既有 UI 库，`App.vue` 已全局 `app.use(Antd)`，勿引入第二套组件库）+ vue-i18n（四语）。
- **ORM 建表**：`app/main.py` L86-96 `Base.metadata.create_all`（`AUTO_CREATE_TABLES` 开启时），元数据靠**导入模型模块**注册 → 新模型必须在 `app/models/connectors/__init__.py` 导出并被路由间接导入。无 alembic。
- **路由注册**：集中式 `app/core/router_registry.py`（现有 connectors L160 / kb L184 / kb_proxy L186）。
- **复用既有模式（重要，避免重复造轮子）**：
- 令牌获取与缓存：`app/connectors/types/oauth2.py` 的 `_resolve_token()` 惰性缓存 + `_fetch_token()`；
- 平台默认端点预置：`types/feishu.py` / `dingtalk.py` / `wecom.py` 在 `__init__` 里 `model_copy` 后填默认 token_url；
- 类型分派注册表：`app/connectors/registry.py` 的 `register_connector / get_connector`（同构新增 `doc_sources` 注册表）；
- 敏感字段加密：`ExternalKbEndpoint.auth_key` 的 **Fernet** 方案；
- 文档入库：`app/routers/kb/kb.py` L92 `upload_document()` 建 `KbDocument(pending)` → `flush()` 生成 `uuid_code` → `doc.meta.file_path` → `run_in_background(_run)` → `run_document_ingest()`（`app/services/kb/document_pipeline.py` L76）；
- 后台任务：`app/core/job_runner.run_in_background`（独立 Session，禁止绑 FastAPI BackgroundTasks）；
- 切片参数：`app/services/kb/rag/chunker_factory.CHUNKER_REGISTRY / chunker_schemas`（前端已按 JSON Schema 动态渲染表单）。
- **既有可复用字段**：`KbDocument.source_type` 注释**已预留 `connector`**（`app/models/kb/kb_document.py` L29），本次正式启用。

## 二、实现方案

### 2.1 总体策略

现有 `BaseConnector`（`app/connectors/base.py`）是**面向「记录流」**的抽象（`pull() -> List[dict]` + `records_path` 字段映射 + 影子表 `meta_connector_ingest`），**无法表达「目录树 / 文档正文」**。因此**不改造它**，而是新增一套**同构但独立**的「文档源」抽象 `BaseDocSource`，专门负责 *列举节点 → 拉取正文 → 转 Markdown*，再由一个导入服务把 Markdown 落成 `KbDocument`。

这样做的理由：

- **零侵入**：不改动已被 `POST /{id}/sync` 使用的记录拉取链路，避免回归；
- **职责分离**：`ConnectorInstance` 管「连到哪个外部系统」，`KbExternalDocMap` 管「外部文档 ↔ 本地文档」映射，`KbDocument` 管正文与切片，三者边界清晰；
- **可扩展**：后续新增平台只需实现3 个方法并注册，不触碰导入服务。

### 2.2 后端：文档源抽象（新增）

`app/connectors/doc_sources/base.py` 定义：

- `ExternalDocRef`：`doc_id`（平台内稳定唯一标识）、`title`、`node_type`（`space|folder|doc`）、`parent_id`、`updated_at`、`url`；
- `DocConnResult`：`ok: bool` + `message: str`（把平台原始报错映射为可读中文，直接回显前端）；
- `FetchDocResult`：`title`、`markdown`、`updated_at`、`content_hash`；
- `BaseDocSource`（ABC，与 `BaseConnector` 同构的 `source_type` + 注册表模式）：
- `async test_connection() -> DocConnResult`
- `async list_nodes(parent_id: str | None) -> list[ExternalDocRef]`
- `async fetch_doc(doc_id: str) -> FetchDocResult`
- 内置 `_http()` 统一 `httpx.AsyncClient(timeout)` 与**令牌缓存**，子类只写端点与解析。

`app/connectors/doc_sources/markdown.py` 提供共享的 **Block → Markdown** 转换器（标题、段落、有序/无序列表、todo、引用、代码块、分割线、图片、超链接、表格、callout 提示块），各平台只提供「块 → 中间结构」的薄适配。

### 2.3 后端：五个平台实现（新增，真实 API）

| 平台 | 文件 | 认证 | 目录/文档枚举 | 正文 |
| --- | --- | --- | --- | --- |
| 飞书 | `doc_sources/feishu.py` | `tenant_access_token`（沿用现有 feishu 端点） | Wiki 空间节点树 `/open-apis/wiki/v2/spaces/{space_id}/nodes`（分页 + 递归） | 云文档 `/open-apis/docx/v1/documents/{token}/blocks` 分页拉取 → Markdown |
| 钉钉文档 | `doc_sources/dingtalk.py` | `gettoken`（query传 access_token） | 钉钉文档空间/节点列表 `/v1.0/doc/...`（按空间分页） | `/v1.0/doc/documents/{id}` 拉正文 → Markdown |
| 语雀 | `doc_sources/yuque.py`（**新建**） | `X-Auth-Token` Header | `GET /api/v2/repos/{ns}/docs`（列表）+ `GET /api/v2/repos/{ns}/toc`（目录树） | `GET /api/v2/repos/{ns}/docs/{slug}` 取 `body` → Markdown |
| 企业微信文档 | `doc_sources/wecom.py` | `gettoken`（query） | WeDoc 空间文档列表 `/cgi-bin/wedoc/spi_list` | `/cgi-bin/wedoc/document` 取正文 → Markdown |
| Notion | `doc_sources/notion.py`（**新建**） | `Authorization: Bearer <secret>` + `Notion-Version` 头 | `POST /v1/search`（按 `page`/`data_source` 过滤） | `GET /v1/blocks/{id}/children` 递归分页 → Markdown |


**安全要点（必须遵守）**：五个平台的**主机域名一律硬编码为常量**（复用现有 `kb_proxy.validate_endpoint_url` 的 SSRF 防护思路做二次校验），**不接受前端传入任意 `base_url`**，从根上消除 SSRF 风险；令牌只写库不返回前端（列表接口返回掩码）。

### 2.4 后端：映射表（新增，落地既有设计）

`app/models/connectors/external_doc_map.py` → 表 `kb_external_doc_map`，按 `docs/superpowers/specs/2026-09-10-third-party-kb-connectors-design.md` §5 设计落地：

- `id / tenant_id / knowledge_id / source_type / external_doc_id / external_title / node_type / external_updated_at / document_id(FK kms_document.id, ondelete SET NULL) / content_hash / deleted / created_at / updated_at`
- **唯一约束 `uq_ext_doc(tenant_id, knowledge_id, source_type, external_doc_id)`** —— 这是「覆盖 or 新建」幂等判定的唯一依据。
- 在 `app/models/connectors/__init__.py` 导出（触发 `create_all`）。

### 2.5 后端：导入服务与路由（新增）

`app/services/kb/external_import_service.py`（对齐 `table_sync_service.py` 的服务层范式）：

- `test_source(...)` / `list_nodes(...)`：薄封装文档源；
- `import_documents(db, tenant_id, knowledge_id, source_type, credentials, doc_refs, chunker_type, chunker_params, embedding_model, ...)`：
- 单文档流程 =拉 Markdown → `sha256(归一化 markdown)` 得 `content_hash` → 查映射：
    - 映射不存在 → **新建** `KbDocument(source_type='connector', file_type='md', status='pending')`；
    - 映射存在且 `content_hash` 相同 → 跳过（记 `unchanged`，**不重复调嵌入**）；
    - 映射存在且 hash 不同 → **覆盖**：复用同一 `uuid_code`（保证 `kb_segment.document_id` 命中同一批切片），清理旧切片、`status='pending'`、`segment_count=0`；
- 全部 `commit()` 后用 `run_in_background` 逐篇跑 `run_document_ingest`（传 `file_bytes=markdown.encode()`、`filename=<title>.md`），**不阻塞请求**；
- 返回 `ImportSummary{total, created, updated, unchanged, failed, items[]}`。

`app/routers/kb/kb_external_source.py`（prefix `/api/v1/kb/external-sources`）：

- `GET  /providers` → 五个平台元数据 + 各自凭据字段 schema（驱动前端动态表单，避免前后端硬编码两份）
- `POST /test` → 连通性测试（返回 `DocConnResult`）
- `POST /nodes` → 目录/文档浏览
- `POST /import` → 导入 / 重新导入（同一端点天然幂等，复用即覆盖）
- `GET  /knowledges/{kid}/external-documents` → 已导入文档列表（映射 join `kms_document`，含状态/更新时间）
- 在 `router_registry.py` 注册。

### 2.6 前端

- **新增** `frontend/src/api/kbExternalSource.ts`：上述 5 个端点的薄封装（沿用 `api/kb.ts` 的 request风格）。
- **新增** `frontend/src/views/kms/kb/ExternalSourceWizard.vue`：分步向导（`a-steps` + 步骤内容区）。以 `v-model:open` + `steps` 受控；对外暴露 `knowledgeId`、`presetSourceType`、`presetNodeIds`，成功后 `emit('imported')`。
- 平台卡片网格 → 凭据表单（按 `/providers` 返回的 schema 动态渲染，`a-input-password`）→「测试连通」按钮（结果 `a-alert`）
- 文档浏览：`a-tree`（`loadData` 懒加载目录）+ 勾选，`a-checkbox` 全选
- 切片方案：**复用 `KnowledgeBaseManager.vue` 已有的 `chunkerOptions` / `chunkerFields` 动态表单逻辑**（`visibleChunkers` / `onChunkerChange` / `buildPipelineConfig` 同款算法）
- 导入结果：`a-result` + `a-descriptions` 展示 created/updated/unchanged/failed
- **改** `KnowledgeBaseManager.vue`：
- type=3 分支新增 `connector`（文档导入）与既有 `proxy`（检索代理）两个并列子形态；选 `connector` 时内嵌「平台 / 凭据 / 测试 / 导入」区并复用 `ExternalSourceWizard`；
- 编辑态 `:disabled="!!editingId"` 锁 type（需求 4），并加一行 `a-alert` 说明类型不可变更；
- 类别默认带出收敛（需求 1）：`openCreate` 用 `selectedCategoryId`，`openEdit` 用 `kb.category_id ?? selectedCategoryId`（现有逻辑已正确，补充「点击分类后必然更新 `selectedCategoryId`」的回归用例即可）。
- **改** `ExternalLinkPane.vue`：从 15 行空态占位改为**已导入文档列表**（表格：标题 /平台 / 更新时间 / 状态 / 操作）+ 顶部「**重新选择文档**」按钮 → 打开 `ExternalSourceWizard`（预填平台与已选节点），实现需求 3。
- **i18n**：4语（`zh-CN` / `zh-CN-tw` / `en-US` / `ja-JP`）补齐向导与错误文案 key。

### 2.7 性能与可靠性

- **令牌复用**：一次导入会话内令牌只取一次（`_resolve_token` 惰性缓存），避免 test/list/fetch 各取一次令牌；令牌缓存带 TTL（默认300s），过期提前刷新。
- **拉取并发**：单次导入对多文档用 `asyncio.Semaphore`限并发（默认 5），防止打爆平台限流；`list_nodes` 只拉当前层级（懒加载），不做全量预取。
- **避免重复嵌入**：`content_hash` 命中即跳过，未变更文档**不触发** `run_document_ingest`，这是最重要的一处成本优化。
- **幂等**：唯一约束 + 事务内先写 `pending` 再提交后台任务，避免「提交了但任务丢了」；后台任务用独立 Session（复用 `run_in_background` 既有约定）。
- **失败隔离**：单篇文档失败不影响其它文档，失败原因写 `KbDocument.error_detail`（与既有 `meta.failed_step` 约定一致），并计入 `failed`。
- **安全**：凭据 Fernet 加密落库、接口不回传明文；平台域名硬编码防 SSRF；`require_kb_permission(KB_UPLOAD)` 沿用既有鉴权。

### 2.8 前端：按预览统一界面（新增）

**A1 左树** `views/kms/KnowledgeBaseManager.vue`（模板 `#title` + `rebuildTree()`）：分类为父节点（📁 可折叠 + 计数徽标），知识库为叶子；三类图标区分 —— Wiki `ReadOutlined` / 通用 `BookOutlined` / 外部 `LinkOutlined`（叶子已带 `kbType`，模板已用静态图标，本步统一视觉：节点密度、计数徽标、折叠箭头、选中态）；「未分类」兜底分组；树头保留「＋分类 / ＋知识库」。

**A2 Wiki 面板** `views/kms/wiki/index.vue`（聚焦态内容区）：现有 `wiki-main__toolbar`（L67 搜索+排序）、`a-table`（L132）、`a-pagination`（L224）。按预览补/改：
- 统计卡：文章总数 / 已发布 / 草稿 / 本月新增
- 面板头：标题 + 副标题（已聚焦该知识库）+ 操作区（分类管理 / 导出 OKF / 新建文章）
- 工具栏补**分类筛选**；表格列：标题 + slug·版本、分类、状态（已发布 / 草稿）、更新时间、浏览量、操作
- 该 Wiki 无文章时的空态

**A3 通用面板** `views/kms/kb/KbDocumentPane.vue`：现有 `a-radio-group` 形态分段控件（L4 document/table/qa/pipeline）、文档表（L29）、头部操作区（L13 重新切片/上传）、表格导入（L59）、问答导入（L86）、流水线试运行（L100）。按预览补/改：
- 统计卡：文档数 / 已完成 / 处理中 / 失败
- 文档表列：文档名 + 大小·类型、状态标签（completed / processing / failed）、**分段数**、更新时间、操作（分段 / 流程 / 重试 / 删除）
- 无文档时的大空态 + 「上传第一个文档」引导
- 三个子面板视觉统一

## 三、目录结构

```
backend/
├── app/
│   ├── connectors/
│   │   └── doc_sources/                     # [NEW] 文档源抽象（与既有 records 型 connectors 并列，不改动原 connectors/）
│   │       ├── __init__.py                  # [NEW] 导出 BaseDocSource / get_doc_source / PROVIDER 元数据（含各平台凭据 schema）
│   │       ├── base.py                      # [NEW] ExternalDocRef / DocConnResult / FetchDocResult / BaseDocSource(ABC: test_connection/list_nodes/fetch_doc) + 注册表 get_doc_source + 统一 httpx 客户端与令牌 TTL 缓存
│   │       ├── markdown.py                  # [NEW] 共享 Block→Markdown 转换器（标题/段落/列表/todo/引用/代码块/分割线/图片/链接/表格/callout）
│   │       ├── feishu.py                    # [NEW] 飞书：tenant_access_token + wiki 节点树分页递归 + docx blocks 拉取转 Markdown
│   │       ├── dingtalk.py                  # [NEW] 钉钉文档：gettoken + 空间文档列表分页 + 正文拉取转 Markdown
│   │       ├── yuque.py                     # [NEW] 语雀（新建）：X-Auth-Token + /api/v2/repos/{ns}/docs + /toc + 文档 body→Markdown
│   │       ├── wecom.py                     # [NEW] 企业微信文档：gettoken + wedoc 文档列表 + 正文转 Markdown
│   │       └── notion.py                    # [NEW] Notion（新建）：Bearer secret + Notion-Version 头 + /v1/search + blocks children 递归转 Markdown
│   ├── models/connectors/
│   │   ├── external_doc_map.py              # [NEW] KbExternalDocMap（表 kb_external_doc_map）落地 spec §5 设计；唯一约束 uq_ext_doc(tenant_id, knowledge_id, source_type, external_doc_id) 是覆盖/新建幂等依据；document_id FK→kms_document.id ondelete SET NULL；含 external_title/node_type/external_updated_at/content_hash/deleted
│   │   └── __init__.py                      # [MODIFY] 追加导出 KbExternalDocMap（触发 create_all 建表）
│   ├── services/kb/
│   │   └── external_import_service.py       # [NEW] 导入服务：test_source/list_nodes 薄封装 + import_documents（拉 Markdown→sha256 content_hash→按映射表判定 新建/覆盖/跳过→commit 后 run_in_background 跑 run_document_ingest，返回 ImportSummary{created,updated,unchanged,failed,items}）；Fernet 凭据加解密；asyncio.Semaphore 限并发
│   ├── routers/kb/
│   │   └── kb_external_source.py            # [NEW] prefix /api/v1/kb/external-sources：GET /providers、POST /test、POST /nodes、POST /import、GET /knowledges/{kid}/external-documents；沿用 require_kb_permission(KB_UPLOAD)
│   └── core/router_registry.py              # [MODIFY] 注册 kb_external_source 路由
└── tests/
    ├── connectors/
    │   └── test_doc_sources.py              # [NEW] 5 个平台单测：mock httpx（respx 或 monkeypatch）验证端点拼接、令牌缓存只取一次、分页递归、块→Markdown 输出、错误映射为 DocConnResult.message
    └── kb/
        └── test_external_import_service.py   # [NEW] 导入服务单测：首次导入建映射+建文档；同 doc 同 hash 跳过（不重复嵌入）；同 doc 变 hash 覆盖且 uuid_code 不变；新 doc 新建；单篇失败隔离；租户隔离

frontend/src/
├── api/
│   └── kbExternalSource.ts                   # [NEW] 5 个端点薄封装（providers/test/nodes/import/knowledges/{kid}/external-documents），沿用 api/kb.ts 的 request 风格
├── views/kms/kb/
│   ├── ExternalSourceWizard.vue             # [NEW] 外部知识库文档导入分步向导：平台卡片→凭据动态表单+测试连通→目录懒加载树勾选→切片方案（复用 chunker_schemas 动态渲染）→导入结果四类统计；props: open/knowledgeId/presetSourceType/presetNodeIds；emit imported
│   ├── ExternalLinkPane.vue                 # [MODIFY] 由 15 行空态占位改为已导入文档列表（表格：标题/平台/更新时间/状态/操作）+「重新选择文档」按钮打开 ExternalSourceWizard（预填平台与已选），实现需求 3 的手动重导入
│   └── KbDocumentPane.vue                   # [MODIFY] 通用知识库面板按预览重做：统计卡（文档数/已完成/处理中/失败）、文档表补状态标签与分段数、无文档大空态+上传引导、三子面板视觉统一
├── views/kms/
│   ├── KnowledgeBaseManager.vue             # [MODIFY] ① type=3 增加 connector（文档导入）子形态并内嵌 ExternalSourceWizard，既有 proxy 分支保留；② 编辑态锁 type（:disabled="!!editingId" + a-alert 提示），需求 4；③ 收敛类别默认带出逻辑（新建=当前点击类别，编辑=知识库所在类别优先），需求 1；④ 左树按预览统一（分类+三类叶子图标/计数徽标/折叠/未分类分组）
│   └── wiki/index.vue                       # [MODIFY] Wiki 聚焦面板按预览重做：统计卡（总数/已发布/草稿/本月新增）、面板头、工具栏补分类筛选、文章表列与分页、无文章空态
└── i18n/locales/
    ├── zh-CN.ts / zh-TW.ts / en-US.ts / ja-JP.ts   # [MODIFY] 补齐向导步骤、平台名、凭据字段、浏览/导入/覆盖/未变更等文案 key（四语齐备）
```

## 四、关键接口定义

```python
# app/connectors/doc_sources/base.py
@dataclass(frozen=True)
class ExternalDocRef:
    doc_id: str            # 平台内稳定唯一标识（覆盖判定的外部键）
    title: str
    node_type: str         # space | folder | doc
    parent_id: str | None
    updated_at: str | None
    url: str | None

class BaseDocSource(ABC):
    source_type: str
    def __init__(self, credentials: dict) -> None: ...
    @abstractmethod
    async def test_connection(self) -> DocConnResult: ... # ok + 可读中文 message
    @abstractmethod
    async def list_nodes(self, parent_id: str | None) -> list[ExternalDocRef]: ...
    @abstractmethod
    async def fetch_doc(self, doc_id: str) -> FetchDocResult: ...  # markdown + content_hash

# app/services/kb/external_import_service.py
class ImportSummary(BaseModel):
    total: int = 0
    created: int = 0
    updated: int = 0        # 覆盖
    unchanged: int = 0      # content_hash 命中，跳过嵌入
    failed: int = 0
    items: list[dict] = []  # [{external_doc_id, title, action: created|updated|unchanged|failed, detail}]
```

## 设计定位

工作台既有设计语言为 **Yao Agents CUI + Ant Design Vue v6**（主色 `#3371fc`、Outfit 字体、64px 图标轨、左树+右内容两栏）。本次新增 UI 属于**既有管理台内的功能向导**，必须严格沿用项目现有 antd 组件与 CSS 变量（`--accent` / `--fg-secondary` / `--bg-subtle`），不引入第二套组件库，不做视觉体系重构。

## 页面/区块设计（新建向导 `ExternalSourceWizard.vue`）

### 1. 步骤条区（顶部）

`a-steps` 五步横向步骤条：选择平台 → 配置凭据 → 选择文档 → 切片方案 → 导入结果。当前步高亮为 `--accent`，已完成步骤打勾。可点击已完成的步骤回退修改，**未通过连通性测试不能进入「选择文档」**，用 `a-steps` 的 disabled 态表达。

### 2. 平台选择区

2 列卡片网格（窄屏 1 列），每张卡片含平台图标 + 名称 + 一行能力说明（"云文档 / 知识库"，"语雀仓库文档"等）。选中态为 `--accent` 描边 + 浅色底 `#e6f0ff` + 轻微 `translateY(-1px)` 抬升，hover 阴影加深。卡片圆角 8px。

### 3. 凭据表单区

按平台 schema 动态渲染字段，标签在上、输入在下；密钥类字段用 `a-input-password` 并附「显示/隐藏」切换。底部左侧「测试连通」主按钮，点击中显示 loading，通过后其上方出现绿色 `a-alert`（含账号/空间等探测到的标识），失败显示红色 `a-alert` 并给出平台返回的可读原因，**失败时禁用「下一步」**。

### 4. 文档浏览区

左侧目录树（`a-tree`懒加载，展开即请求下一层），右侧所选文档清单（可删除）。每行展示文档标题、更新时间、已导入状态标签（未导入/已同步）。顶部「全选本层」复选框与已选计数。空目录用 `a-empty` 兜底。加载中用骨架/_spin，避免空白闪烁。

### 5. 切片方案区

复用现有 chunker 动态表单：切片方式下拉 + 参数行（布尔开关 / 数字输入 / 文本输入），下方 `a-alert info` 一行提示说明。整体左对齐、字段宽度固定（开关 140px 内），保持与新建通用知识库向导一致的视觉。

### 6. 导入结果区

`a-result` 展示成功/部分成功/失败，标题下方 `a-descriptions` 四列统计：新增、更新、未变更、失败（分别用 success / processing / default / error 色）。下方表格列出每篇文档的标题与动作明细，失败项展示原因。可直接触发「重新选择文档」再次导入。

## 右侧外部知识库面板（`ExternalLinkPane.vue` 改版）

顶部标题栏 +「重新选择文档」主按钮；下方为已导入文档表格（标题 / 平台标签 / 更新时间 / 状态标签 / 操作），平台标签用不同色区分五类来源。空态保留 `a-empty` 并将行动按钮直接指向向导第一步。

## 左侧知识库树（`KnowledgeBaseManager.vue` 左栏改版）

分类为父节点（📁 可折叠 + 文档计数徽标），知识库为叶子；三类叶子用不同图标区分 —— **Wiki 📖 / 通用 📘 / 外部 🔗**，图标色沿用 `--accent` 系；「未分类」作为兜底分组（不可选中，仅作容器）。选中态为浅底 + 主色加粗；树头保留「＋分类 / ＋知识库」两个图标按钮（hover 变主色）。

## 右侧 Wiki 知识库面板（`wiki/index.vue` 聚焦态改版）

聚焦模式（传入 `wikiId`）下隐藏内部分类树，仅显示该 Wiki 的内容区：

1. **面板头**：标题（📖 Wiki 名）+ 副标题（已聚焦该知识库 + 文章数）+ 右侧操作区（分类管理 / 导出 OKF / ＋新建文章）
2. **统计卡** 4 格：文章总数 / 已发布 / 草稿 / 本月新增
3. **工具栏**：搜索框 + 分类筛选下拉 + 排序下拉 + 升降序切换
4. **文章表**：标题 + slug·版本、分类、状态标签（已发布 / 草稿）、更新时间、浏览量、操作（查看 / 编辑 / 删除）
5. **分页**；无文章时大空态 + 新建引导

## 右侧通用知识库面板（`KbDocumentPane.vue` 改版）

1. **形态分段控件**：文档 / 表格 / 问答 / 流水线调试（按二级形态过滤可见项）
2. **统计卡** 4 格：文档数 / 已完成 / 处理中 / 失败
3. **文档表**：文档名 + 大小·类型、状态标签（completed 绿 / processing 蓝 / failed 红）、**分段数**、更新时间、操作（分段 / 流程 / 重试 / 删除）
4. **空态**：无文档时大空态（📄 + 「还没有任何文档」+ 说明 +「上传第一个文档」主按钮）
5. 表格导入 / 问答导入 / 流水线试运行三个子面板视觉与上面统一

## 交互与响应式

- 向导弹窗宽度自适应（`a-modal` 860px，窄屏全屏），内容区最大高度 `70vh` 内部滚动；
- 步骤切换保留已填参数（凭据、切片配置存于组件内 `reactive` 状态），回退不丢失；
- 所有异步按钮均有 loading 态与禁用态，连通性测试与导入期间禁止重复提交；
- 动效克制：卡片/按钮0.15–0.2s 过渡，不做大幅位移。

## Agent Extensions

### MCP

- **Playwright MCP Server**
- Purpose: 启动前端 dev server 后，在真实浏览器中走通外部知识库导入向导的完整交互链路（选平台 → 填凭据 → 测试连通 → 浏览目录勾选文档 → 设切片 → 导入），并验证 `ExternalLinkPane` 文档列表与「重新选择文档」入口；同时验证左树三类图标与 Wiki / 通用 / 外部三类面板界面与空态；抓取 console 报错确认无渲染异常。
- Expected outcome: 产出向导 5 个步骤 + 三类面板（含空态）的实机截图与 console 日志，确认步骤流转、校验拦截（未测连通不可进入下一步）、平台卡片选中态、结果四类统计、左树图标区分与面板统计卡/表格/空态均符合预览原型，且控制台无 error。