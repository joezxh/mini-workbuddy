# 知识治理 · 前端（管理台）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 MinWorkBuddy 管理台新增「知识治理」一级目录及 4 个二级菜单（数据源 / 知识库 / 外部知识库 / 本体），共 15 个子页面。

**Architecture:** 管理台是 **Tab 容器 + 后端菜单驱动**：后端 `sys_menu` 插行 → `/me` 返回 → `AppSidebar` 渲染 → `admin/index.vue` 用 `componentMap[menuKey]` 渲染 Tab。**每个二级菜单 = 1 个容器组件（`a-tabs`）+ 若干独立子页面组件**（不写成单个巨型 .vue）。

**Tech Stack:** Vue 3 + TypeScript + Vite 5 + Ant Design Vue + vue-i18n + Pinia；复用 `components/common/` 的 `DataTable` / `StatusTag` / `StateWrapper` / `DataCard` / `TechCard`

**Spec:** `docs/superpowers/specs/2026-09-10-knowledge-governance-frontend-design.md`
**i18n 范围：** 只写 `zh-CN` + `en-US`；`zh-TW` / `ja-JP` 靠已配置的 `fallbackLocale: 'en-US'` 自动回落，**不改 i18n 配置**

---

## 文件结构

```
src/views/admin/knowledge/
├── DataSourcePanel.vue           容器（5 tabs）
│   └── data-source/{SourceManagement,MetadataExplorer,StandardManagement,
│                    BindingWorkbench,SqlWorkbench}.vue
├── KnowledgeBasePanel.vue        容器（4 tabs）
│   └── kb/{DatasetManagement,DocumentManagement,SearchTester,IndexStatus}.vue
├── ExternalKbPanel.vue           容器（2 tabs）
│   └── external/{InstanceManagement,SyncJobs}.vue
└── OntologyPanel.vue             容器（4 tabs）
    └── ontology/{OntologyList,ClassHierarchy,ModelingWorkbench,ReviewVersion}.vue

src/api/{dataops,knowledgeBase,externalKb,ontology}.ts
src/components/common/{JsonViewer,SchemaTree,ChunkPreview,DiffView}.vue
```

---

### Task 1（**最先做**）: 打通菜单链路

**Files:**
- 后端：`sys_menu` 插 1 目录 + 4 菜单行
- Modify: `frontend/src/views/admin/componentMap.ts`
- Modify: `frontend/src/router/index.ts`

> **这是最容易踩的坑：页面写完但侧栏看不到。必须先把菜单数据灌进去验证链路，再写页面。**

- [ ] **Step 1:** 在后端 `sys_menu` 插入目录与菜单
```sql
-- 目录
INSERT INTO sys_menu (name, i18n_key, path, icon, parent_id, sort, type, visible, menu_key)
VALUES ('知识治理', 'knowledge.menu.root', '/admin/knowledge', 'DatabaseOutlined', NULL, 100, 1, 1, 'knowledge');

-- 4 个二级菜单（parent_id 指向上面的目录）
-- menu_key 分别为 kg-data-source / kg-kb / kg-external-kb / kg-ontology
-- i18n_key 分别为 knowledge.menu.dataSource / .kb / .externalKb / .ontology
```

- [ ] **Step 2:** 在 `componentMap.ts` 注册 4 个占位组件（先放最小 `div`，验证渲染）
```ts
import DataSourcePanel from '@/views/admin/knowledge/DataSourcePanel.vue'
// ...
export const componentMap: Record<string, Component> = {
  // 既有映射保持不动
  'kg-data-source': markRaw(DataSourcePanel),
  'kg-kb': markRaw(KnowledgeBasePanel),
  'kg-external-kb': markRaw(ExternalKbPanel),
  'kg-ontology': markRaw(OntologyPanel),
}
```

- [ ] **Step 3:** 在 `router/index.ts` 补 4 条路由
```ts
{
  path: 'admin/knowledge/data-source',
  name: 'KgDataSource',
  component: () => import('@/views/admin/knowledge/DataSourcePanel.vue'),
  meta: { title: '数据源', icon: 'DatabaseOutlined', requiresAdmin: true }
},
```

- [ ] **Step 4:** 登录后在侧栏确认「知识治理」及 4 个子项可见且可点击
- [ ] **Step 5:** 在 `zh-CN.ts` / `en-US.ts` 加 `knowledge.menu.*` 四条键
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(knowledge): register knowledge governance menu entries"
```

---

### Task 2: i18n 骨架与回落验证

**Files:**
- Modify: `frontend/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/src/i18n/locales/en-US.ts`
- Test: `frontend/src/**/__tests__`（或手工验证清单）

- [ ] **Step 1:** 建立 `knowledge.*` 命名空间骨架（先放 Task 1 的菜单键）
- [ ] **Step 2:** 切到 `ja-JP`，确认页面显示英文而**不是** key 原文（如不能出现 `knowledge.menu.root`）
- [ ] **Step 3:** 若出现 key 泄漏 → 检查是否误用了不存在的键
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(i18n): knowledge namespace with en-US fallback"
```

---

### Task 3: 四个共享组件

**Files:**
- Create: `src/components/common/JsonViewer.vue`
- Create: `src/components/common/SchemaTree.vue`
- Create: `src/components/common/ChunkPreview.vue`
- Create: `src/components/common/DiffView.vue`

- [ ] **Step 1: `JsonViewer`** —— 折叠式 JSON 展示，接受 `value: unknown`；用于 `profile_json` / `impact_json` / `evidence_json` / `seg_metadata`
- [ ] **Step 2: `SchemaTree`** —— 库 → 表 → 列 三级树，**必须支持搜索 + 虚拟滚动**（应对上千表）
- [ ] **Step 3: `ChunkPreview`** —— 切片文本 + 序号 + token 数，分页
- [ ] **Step 4: `DiffView`** —— 版本快照字段级对比
- [ ] **Step 5:** 为四个组件各写一个渲染测试
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(common): JsonViewer, SchemaTree, ChunkPreview, DiffView"
```

---

### Task 4: P1 知识库四个子页

**Files:**
- Create: `src/views/admin/knowledge/KnowledgeBasePanel.vue` + `kb/*` 四个
- Create: `src/api/knowledgeBase.ts`

后端已改为挂载 AgentScope RAG Service → API 前缀 `/agentscope/knowledge_bases`。

- [ ] **Step 1: `knowledgeBase.ts`** —— 封装 CRUD、上传、批量状态、检索、四个能力发现端点
- [ ] **Step 2: `DatasetManagement.vue`** —— 列表 + CRUD；embedding 模型下拉由 `GET /embedding_models` 动态渲染（**不硬编码模型列表**）
- [ ] **Step 3: `DocumentManagement.vue`** —— 上传；状态用 `StatusTag` 渲染 `pending/parsing/chunking/indexing/ready/error`；批量轮询 `GET /documents/status?ids=...`；上传 `accept` 由 `GET /supported_content_types` 决定
- [ ] **Step 4: `SearchTester.vue`** —— 检索结果 + 对比模式（纯向量 vs 混合）
- [ ] **Step 5: `IndexStatus.vue`** —— 按状态分组统计；**长耗时任务一律走状态列表 + 轮询，不在弹窗里阻塞**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(knowledge): knowledge base management pages"
```

---

### Task 5: P2 数据源五个子页

**Files:**
- Create: `src/views/admin/knowledge/DataSourcePanel.vue` + `data-source/*` 五个
- Create: `src/api/dataops.ts`

- [ ] **Step 1: `SourceManagement.vue`** —— 列表（**不显示密码**，只显示 `has_password` 徽标）+ 新建/编辑 Modal（密码框 `type=password`，留空表示不改）+ 行内探活
- [ ] **Step 2: `MetadataExplorer.vue`** —— `SchemaTree` + 表/列详情 + 列画像抽屉（进度条 + Top-K 小柱状图 + `JsonViewer`）
- [ ] **Step 3: `StandardManagement.vue`** —— 标准项 CRUD + 版本历史（`DiffView`）
- [ ] **Step 4: `BindingWorkbench.vue`** —— 左列右标准；建议区支持批量接受/拒绝
- [ ] **Step 5: `SqlWorkbench.vue`** —— **只读查询与写操作物理分离成两个 Tab**；写操作四步：Dry-run 影响卡片 → 申请 → 批准（仅 `kg:datasource:write-approve`）→ 令牌执行；SQL 被篡改时给出明确错误提示而非静默失败
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(knowledge): data source management pages"
```

---

### Task 6: P4 本体四个子页

**Files:**
- Create: `src/views/admin/knowledge/OntologyPanel.vue` + `ontology/*` 四个
- Create: `src/api/ontology.ts`

- [ ] **Step 1: `OntologyList.vue`** —— 列表 + TTL 导入（拖拽 `.ttl`）/ 导出
- [ ] **Step 2: `ClassHierarchy.vue`** —— 左侧 `a-tree`（`SchemaTree` 复用）+ 右侧类详情 + 校验按钮（悬空父类/循环继承）
- [ ] **Step 3: `ModelingWorkbench.vue`** —— 对象类型/属性/关系类型/映射/CQ 五区；P2 候选标注"建议"徽标；映射选择器复用 `SchemaTree`
- [ ] **Step 4: `ReviewVersion.vue`** —— 待评审批量接受/拒绝；版本历史 `DiffView`
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(knowledge): ontology management pages"
```

---

### Task 7: P3 外部知识库两个子页

**Files:**
- Create: `src/views/admin/knowledge/ExternalKbPanel.vue` + `external/*` 两个
- Create: `src/api/externalKb.ts`

- [ ] **Step 1: `InstanceManagement.vue`** —— 后端 `get_create_params_config()` 返回 schema，前端**按 schema 动态渲染**：`password → a-input-password`、`text → a-input`、`number → a-input-number(min/max)`、`select → a-select`
- [ ] **Step 2:** 开启同步时需选目标数据集与同步间隔；**中文场景明确提示建议开启同步**
- [ ] **Step 3: `SyncJobs.vue`** —— 同步任务列表（新增/更新/删除计数、耗时、失败可展开）
- [ ] **Step 4:** 为表单渲染器写测试（覆盖 4 种 `type`）
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(knowledge): external knowledge base pages with schema-driven form"
```

---

### Task 8: 通用规范收口与空/错误态

- [ ] **Step 1:** 全部列表统一用 `DataTable`（不直接用 `a-table`）
- [ ] **Step 2:** 加载/空/错误统一用 `StateWrapper`
- [ ] **Step 3:** 危险操作统一 `a-popconfirm` 二次确认
- [ ] **Step 4:** 主题只用 CSS 变量，检查无写死颜色
- [ ] **Step 5:** 构造 500 响应，确认各页面错误态正常
- [ ] **Step 6: Commit**

```bash
git commit -m "chore(knowledge): unify loading/empty/error states and theming"
```

---

## 验收标准

| 项 | 标准 |
|---|---|
| 菜单 | 「知识治理」及 4 个二级菜单可见可点（Task 1 必须先通过） |
| i18n | 切 `ja-JP` 回落英文，无 key 原文泄漏 |
| 组件 | 4 个共享组件有渲染测试 |
| 大数据 | SchemaTree 在 1000+ 表下不卡（虚拟滚动） |
| 危险操作 | 删除等有二次确认 |
| 长任务 | 无弹窗阻塞，一律状态列表 + 轮询 |
| 动态表单 | P3 表单渲染器覆盖 4 种类型 |

## 风险与退路

| 风险 | 退路 |
|---|---|
| **`sys_menu` 漏插导致页面看不见** | Task 1 最先执行并验证 |
| 容器组件膨胀 | 已按子页面拆分；单个 .vue 超过 ~300 行即继续拆 |
| 大数据量卡顿 | `SchemaTree` 一开始就用虚拟滚动，不事后补 |
| i18n key 泄漏 | Task 2 专门验证回落 |
