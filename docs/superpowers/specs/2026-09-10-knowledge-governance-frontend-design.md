# 知识治理 · 前端（管理台）设计

> 状态：待评审
> 日期：2026-09-10
> 对应后端 spec：P2 业务数据集成 / P1 PGVector 知识库 / P3 第三方知识库 / P4 本体层
> 信息架构：统一一级目录「知识治理」，下挂 4 个二级菜单（数据源 / 知识库 / 外部知识库 / 本体）
> i18n 范围：`zh-CN` + `en-US`，`zh-TW` / `ja-JP` 回落 `en-US`

---

## 1. 管理台接入机制（先理解这个，否则页面做了也出不来）

MinWorkBuddy 的管理台是 **Tab 容器 + 后端菜单驱动**，不是"加个路由就能看见"：

```
后端 sys_menu 插菜单行（menuKey / i18n_key / permission / sort）
        ↓  /me 接口随用户信息一并返回 menus
AppSidebar（stores/menu）渲染左侧 rail —— 菜单完全来自后端，前端无硬编码
        ↓  点击菜单
views/admin/index.vue 用 componentMap[menuKey] 渲染为 Tab
```

**新增一个管理台页面必须做三件事**（缺一不可）：

| # | 位置 | 动作 |
|---|---|---|
| 1 | 后端 `sys_menu` | 插入目录/菜单行，填 `menu_key`、`i18n_key`、`permission`、`component`、`sort` |
| 2 | `src/views/admin/componentMap.ts` | 加 `menuKey → markRaw(组件)` 映射 |
| 3 | 新建 `.vue` 页面组件 | 页面本体 |

> 前端 `src/router/index.ts` 里同样需补路由（供直接 URL 访问与刷新保持），但**侧栏显示与否由后端菜单决定**。

---

## 2. 信息架构

```
知识治理 (DatabaseOutlined)                    ← 一级目录，type=1
├── 数据源        /admin/knowledge/data-source   menuKey: kg-data-source
├── 知识库        /admin/knowledge/kb            menuKey: kg-kb
├── 外部知识库    /admin/knowledge/external-kb   menuKey: kg-external-kb
└── 本体          /admin/knowledge/ontology      menuKey: kg-ontology
```

**每个二级菜单 = 1 个容器组件，容器内用 `a-tabs` 组织子页面**（与现有 `SkillManagement.vue` 的做法一致）。子页面拆成独立 `.vue` 文件，避免单个文件膨胀到不可维护。

---

## 3. 目录结构

```
src/views/admin/knowledge/
├── DataSourcePanel.vue              容器（5 tabs）
│   └── data-source/
│       ├── SourceManagement.vue     数据源管理
│       ├── MetadataExplorer.vue     元数据浏览（库→表→列 + 列画像）
│       ├── StandardManagement.vue   元数据标准
│       ├── BindingWorkbench.vue     字段绑定工作台
│       └── SqlWorkbench.vue         SQL 工作台（只读查询 + 写操作申请/审批）
│
├── KnowledgeBasePanel.vue           容器（4 tabs）
│   └── kb/
│       ├── DatasetManagement.vue    数据集管理
│       ├── DocumentManagement.vue   文档管理（上传/状态/切片预览）
│       ├── SearchTester.vue         检索测试
│       └── IngestionJobs.vue        入库任务
│
├── ExternalKbPanel.vue              容器（2 tabs）
│   └── external/
│       ├── InstanceManagement.vue   连接器实例（声明式表单动态渲染）
│       └── SyncJobs.vue             同步任务
│
└── OntologyPanel.vue                容器（4 tabs）
    └── ontology/
        ├── OntologyList.vue         本体列表（TTL 导入导出）
        ├── ClassHierarchy.vue       类层级编辑器
        ├── ModelingWorkbench.vue    建模（对象类型/属性/关系/CQ/映射）
        └── ReviewVersion.vue        评审与版本
```

**API 封装**（沿用 `src/api/*.ts` 现有风格，一个模块一个文件）：
`src/api/dataops.ts` · `src/api/knowledgeBase.ts` · `src/api/externalKb.ts` · `src/api/ontology.ts`

---

## 4. 权限标识建议

| 标识 | 说明 |
|---|---|
| `kg:datasource:read` / `kg:datasource:write` | 数据源 CRUD、扫描 |
| `kg:datasource:query` | 只读 SQL 执行 |
| `kg:datasource:write-request` | 提交写操作申请 |
| `kg:datasource:write-approve` | **批准**写操作申请（与执行分离，需独立授权） |
| `kg:kb:read` / `kg:kb:write` | 数据集与文档 |
| `kg:external:read` / `kg:external:write` | 外部知识库实例与同步 |
| `kg:ontology:read` / `kg:ontology:write` | 本体建模 |
| `kg:ontology:review` | 本体评审（accepted/rejected） |

> `write-approve` 必须独立于 `write-request`：同一人既能申请又能批准等于审批形同虚设。

---

## 5. i18n 策略

- **key 前缀**：`knowledge.*`（如 `knowledge.dataSource.title`）
- **只写 `zh-CN` 与 `en-US` 两个 locale 文件**
- `zh-TW` / `ja-JP` **不写 key** —— `src/i18n/index.ts` 已配置 `fallbackLocale: 'en-US'`，缺失 key 会自动回落到英文，**无需改动 i18n 配置**
- 菜单标题：后端 `sys_menu.i18n_key` 填 `knowledge.menu.*`；`i18n` 映射字段可留空（走 i18n_key 优先）

---

## 6. 组件复用

### 6.1 直接复用现有

| 组件 | 用途 |
|---|---|
| `components/common/DataTable/` | 所有列表（已封装 `a-table` + 分页 + loading + 列配置） |
| `components/common/StatusTag.vue` | 状态标签（数据源 online/offline、文档 parsing/ready/failed、申请 pending/approved…） |
| `components/common/StateWrapper.vue` | 加载 / 空 / 错误三态统一 |
| `components/common/DataCard.vue` · `TechCard.vue` | 概览卡片 |

### 6.2 需新建（跨模块共用）

| 组件 | 用途 | 被谁用 |
|---|---|---|
| `JsonViewer.vue` | 展示 `profile_json` / `impact_json` / `evidence_json` / `seg_metadata` | P2 画像、P2 影响预估、P4 证据 |
| `SchemaTree.vue` | 库 → 表 → 列 三级树 + 搜索 + 虚拟滚动 | P2 元数据浏览、P4 映射选择 |
| `ChunkPreview.vue` | 切片文本 + 序号 + token 数 | P1 文档管理、P1 检索测试 |
| `DiffView.vue` | 标准项/本体版本快照对比 | P4 版本、P2 标准版本 |

---

## 7. P2 · 数据源（`DataSourcePanel.vue`）

### 7.1 数据源管理

- **列表**：`DataTable` 展示 名称 / 类型(mysql|doris|postgresql) / 地址 / 默认库 / 状态 / 最近探活
  **密码列不展示**，只显示 `has_password` 徽标
- **新建/编辑**：`a-modal` 表单（名称、类型、主机、端口、用户名、密码、默认库、字符集）
  密码框 `type="password"`，编辑时留空表示不修改
- **探活**：行内按钮 → 调 `/sources/test`，展示 `latency_ms` 与 `server_info`
- **危险操作**：删除需二次确认（`a-popconfirm`）

### 7.2 元数据浏览

- **布局**：左侧 `SchemaTree`（库 → 表 → 列，支持搜索、虚拟滚动，应对上千表），右侧详情
- **表详情**：表注释、行数、引擎、列数、`biz_name`/`domain`
- **列详情**：类型、可空、注释、`semantic_type`、`pii_level`
- **列画像**：抽屉/侧栏展示 `JsonViewer(profile_json)` + 可视化（`null_rate` / `distinct_ratio` 用进度条，Top-K 值分布用小柱状图）
  → 提供"重新画像"按钮（触发单列 profile）
- **触发扫描**：顶部按钮 → 选择库 + `with_profile` 开关 → 提交后跳到任务进度

### 7.3 元数据标准

- 标准项列表 + CRUD（`code` / `name` / `aliases` / `semantic_type` / `data_type_expect` / `security_level` / `domain`）
- **版本历史**：抽屉展示 `meta_standard_version` 快照，`DiffView` 对比版本间差异

### 7.4 字段绑定工作台

- 左：待绑定列（可按 `semantic_type` / `pii_level` / 关键词过滤）
- 右：标准项选择（支持按 `aliases` 模糊匹配）
- **建议区**：`status=suggested && source=rule` 的绑定，可批量 接受 / 拒绝
- 绑定结果展示 `confidence` 与 `evidence_json`（`JsonViewer`）

### 7.5 SQL 工作台（**交互上必须强隔离**）

```
┌─ Tab A：只读查询 ────────────────┬─ Tab B：写操作 ────────────────┐
│ SQL 编辑器（只读提示语）          │ ① 提交申请                     │
│ 执行 → 结果表（≤1000 行）        │    粘贴 SQL → Dry-run 影响预估  │
│ 显示耗时 / 截断提示              │    → 展示 impact_json          │
│                                 │ ② 我的申请（状态跟踪）          │
│                                 │ ③ 待我审批（仅 write-approve）  │
│                                 │ ④ 执行（需一次性令牌）          │
└─────────────────────────────────┴──────────────────────────────┘
```

**UI 必须体现的三件事**：
1. **只读区与写区物理分离**（两个 Tab），只读区有明确的"只读"标识，避免误把写语句粘到只读框（会被后端拒绝，但提示要友好）
2. **Dry-run 影响预估在提交前必看**：`impact_json` 用醒目卡片展示（影响表、估算行数、结构性变更告警）
3. **批准与执行分离**：审批人批准后，执行页展示令牌与有效期；执行时若 SQL 被篡改（哈希不匹配）要给出明确错误提示，而不是静默失败

---

## 8. P1 · 知识库（`KnowledgeBasePanel.vue`）

> **v2 变更**：P1 后端改为挂载 AgentScope 原生 RAG Service（见 P1 spec v2），
> 因此**不再自研知识库 REST API**，前端改调挂载后的 `/knowledge_bases/*`。

### 8.0 对接方式与能力发现

- 后端 `app.mount("/agentscope", create_app(...))` → 前端 API 前缀 `/agentscope/knowledge_bases`
- **四个能力发现端点让前端几乎零硬编码**（与 P3 声明式表单思路一致）：

| 端点 | 前端用途 |
|---|---|
| `GET /knowledge_bases/embedding_models` | 动态渲染 embedding 模型下拉（已按维度策略过滤，不会出现选了就报错的模型） |
| `GET /knowledge_bases/supported_content_types` | 上传控件的 `accept` 属性 |
| `GET /knowledge_bases/chunkers` | 切片策略下拉 + 参数表单（返回 JSON Schema，动态渲染） |
| `GET /knowledge_bases/middleware/parameters_schema` | RAG 检索参数表单 |

- 可参考 AgentScope 仓库 `examples/web_ui`（React）的上传 / 进度 / 检索 UI 设计，省一轮交互设计

### 8.1 数据集管理
列表 + CRUD（走原生端点）。字段：名称 / embedding 模型 / 维度 / 切片器 / 文档数 / 切片数。
- **维度策略为 `ANY`**（`CollectionPerKbManager`）：每个知识库可独立选维度，与 768 / 1024 混用兼容
- **更换 embedding 模型需重建索引** → 提供"重建索引"入口并二次确认
- MWB 侧 `kb_ref` 表补充显示名与权限，前端列表以它为准做权限过滤

### 8.2 文档管理
- 上传（拖拽 + 多文件）→ 立即返回 `pending`，索引在后台跑
- 列表：标题 / 类型 / 状态 / 切片数
- **状态机用 RAG Service 定义**（`StatusTag` 配色）：
  `pending → parsing → chunking → indexing → ready / error`
- **进度**：批量轮询 `GET /documents/status?ids=a,b,c`，前端渲染进度条与失败提示（不阻塞、不弹窗转圈）
- `error` 行可查看错误摘要并**重新上传**
- **切片预览**：抽屉，分页展示该文档切片（内容 + 序号 + token 数）

### 8.3 检索测试
- 输入 query → 展示 top-K 结果（内容 + `score` + 来源文档）
- **对比模式**：同一 query 分别走"纯向量"与"向量 + `pg_trgm` 混合"，左右对照 —— 用于验证中文混合检索的实际增益
- 结果标注召回来源（向量侧 / 关键词侧 / 两者命中）

### 8.4 索引状态
原"入库任务"改为**索引状态聚合视图**：
- 按状态分组统计（pending / processing / ready / error）
- 卡住的 `pending` 由后端 Index Sweeper 自动重派发，前端只需展示"已自动重试 N 次"
- 长耗时任务的进度一律走状态列表 + 轮询，**不在弹窗里阻塞**（遵循 §11 通用规范）

---

## 9. P3 · 外部知识库（`ExternalKbPanel.vue`）

### 9.1 实例管理（**声明式表单驱动**）

后端 `get_create_params_config()` 返回：
```json
{"options":[{"key":"token","label":"Token","type":"password","required":true,
             "placeholder":"...","description":"...","min":1,"max":50}]}
```

前端**按 schema 动态渲染表单**，新增连接器零前端改动：

| `type` | 渲染为 |
|---|---|
| `password` | `a-input-password` |
| `text` | `a-input` |
| `number` | `a-input-number`（带 `min`/`max`） |
| `select` | `a-select`（带 `options`） |

- 列表展示 名称 / 类型 / 同步开关 / 目标数据集 / 最近同步时间
- **凭据不回显**，编辑时留空表示不修改
- 若开启同步：需选择目标 `kb_dataset`、`sync_interval_min`

### 9.2 同步任务
任务列表（实例 / 状态 / 新增 / 更新 / 删除 计数 / 耗时），失败项可展开看错误。

---

## 10. P4 · 本体（`OntologyPanel.vue`）

### 10.1 本体列表
列表（编码 / 名称 / 命名空间 / 版本 / 状态）+ CRUD + **TTL 导入/导出**。
导入支持拖拽 `.ttl` 文件；导出为 `.ttl` 下载。

### 10.2 类层级编辑器
- 左侧 `a-tree`（类层级，可展开/折叠/拖拽调整父子）
- 右侧类详情（URI / label / comment / 父类）
- 顶部：新增类、删除（有子类时需提示）、校验（悬空父类/循环继承）

### 10.3 建模工作台
四个子区（`a-tabs` 或分区卡片）：
- **对象类型**：列表 + CRUD；来自 P2 的候选（`source=rule`）标注"建议"徽标，可 接受/拒绝
- **属性**：挂在对象类型下
- **关系类型**：源类型 → 目标类型 + 基数；可展示 `overlap_ratio` 候选及其分值
- **映射**：对象类型 ↔ P2 的物理表/列（用 `SchemaTree` 选择器）
- **能力问题（CQ）**：问题列表 + 关联的对象类型；提供"覆盖度"提示（有多少 CQ 能被引擎回答）

### 10.4 评审与版本
- 待评审项（`status=suggested`）列表，支持批量接受/拒绝，展示 `confidence` 与 `evidence_json`
- 版本历史：`DiffView` 对比快照，支持查看（**回滚不在本阶段**）

---

## 11. 通用交互规范

| 场景 | 规范 |
|---|---|
| 加载 / 空 / 错误 | 统一用 `StateWrapper`，不各写各的 |
| 列表分页 | 统一用 `DataTable` 的分页，不直接用 `a-table` |
| 删除等危险操作 | `a-popconfirm` 二次确认，文案说明后果 |
| 长耗时操作（扫描、入库、同步、画像） | 提交后走任务列表 + 进度，**不阻塞在弹窗里转圈** |
| 表单校验 | 前端做基础校验，后端校验错误要能映射回字段展示 |
| 大数据量（上千表/列） | 树与列表必须支持搜索 + 虚拟滚动 |
| 主题 | 只用 CSS 变量（`--bg-surface` / `--accent` / `--border` / `--radius-sm`），不写死颜色 |

---

## 12. 测试

- **组件测试**：4 个容器组件的 tab 切换与子页面挂载；声明式表单渲染器对 4 种 `type` 的正确渲染
- **交互测试**：危险操作二次确认；写操作四步（dry-run → 申请 → 批准 → 令牌执行）全链路
- **i18n 测试**：切到 `ja-JP` 时新页面应回落为英文且不出现 key 原文泄漏（如 `knowledge.dataSource.title`）
- **空/错误态**：接口 500、空列表、超大数据量下的表现

---

## 13. 影响面

| 项 | 说明 |
|---|---|
| 修改 | `src/router/index.ts`（4 条路由）、`src/views/admin/componentMap.ts`（4 个映射） |
| 修改 | `src/i18n/locales/zh-CN.ts`、`en-US.ts`（`knowledge.*` 键）；`zh-TW`/`ja-JP` **不改** |
| 新增 | 4 个容器 + 15 个子页面 + 4 个 API 文件 + 4 个共享组件 |
| 后端配合 | `sys_menu` 插 1 目录 + 4 菜单行；权限标识（§4）注册 |
| 不受影响 | 现有管理台页面、`AppSidebar`、`admin/index.vue` 机制本身 |

---

## 14. 风险

1. **`sys_menu` 漏插** —— 页面做完但侧栏看不到，是最容易踩的坑；实施时第一步就该先把菜单数据灌进去验证链路
2. **单个容器组件膨胀** —— P2 有 5 个子页、P4 有 4 个子区，必须拆子组件，否则会重演 `SkillManagement.vue` 700+ 行的维护困境
3. **超大数据量卡顿** —— 元数据浏览可能面对上千表、上万列；虚拟滚动与后端分页必须一开始就有，不能事后补
4. **i18n key 泄漏** —— 只写两个 locale 时，若误用不存在的 key 会直接显示 key 原文；需在测试里专门验证回落
