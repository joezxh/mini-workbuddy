# 知识库管理 Tab 内嵌 Wiki 首页 设计

## 背景与问题

`src/views/kms/KnowledgeBaseManager.vue` 用 `a-tabs` 分三个标签页管理三类知识库：

- `key="1"` Wiki 知识库（`t('kmsWiki.title')`）
- `key="2"` 通用知识库（`t('kbMgmt.generalKb')`）
- `key="3"` 外部知识库（`t('kbMgmt.externalKb')`）

现状：tab 2 / tab 3 会在标签页下方原地渲染左侧知识库树 + 右侧内容面板（`KbDocumentPane` / `ExternalLinkPane`）；**只有 tab 1 是空的**，仅显示一个跳转链接 `<router-link to="/wiki">`，用户必须点击跳转离开管理页才能看到 Wiki 内容。

诉求：把 Wiki 知识库首页内容**直接嵌进 `key="1"` 标签页**，使其与独立 Wiki 首页功能一致、就地展示，不再靠链接跳转关联。

### 关键现状事实

| 事实 | 说明 |
|---|---|
| `KnowledgeBaseManager` **不是路由页面** | 注册于 `src/views/admin/componentMap.ts` 的 `kg-knowledge-manager`，由动态组件宿主渲染 |
| Wiki 首页**是真实路由** | `/wiki` → `src/views/kms/wiki/index.vue`（`src/router/index.ts`） |
| 文章页挂在 `/wiki` 路径下 | `/wiki/:slug`（ArticleView）、`/wiki/edit/:id`（ArticleEdit）、`/wiki/rag`（RagTest） |
| wiki 首页不依赖路由参数 | 只用 `useRouter` 做跳转，未使用 `useRoute`，因此可安全内嵌复用 |
| tab 默认值 | `activeType = ref('2')`，tab 1 非默认，初次进入管理页不会加载 Wiki 数据 |

## 目标 / 非目标

**目标**

1. tab 1 原地渲染 Wiki 首页（左栏知识库/分类树、右栏搜索 + 文章列表 + 分页 + 工具栏、各类弹窗），无需跳转。
2. tab 1 与独立 `/wiki` 首页**功能一致**，且不产生代码重复导致日后漂移。
3. 改动最小化，独立 `/wiki` 路由行为零变化。

**非目标**

- 不改变文章「查看 / 编辑」与「RAG 测试」的跳转行为（仍 `router.push` 到独立页面，会离开管理页）。
- 不重构 `wiki/index.vue` 的内部逻辑（树、筛选、搜索、OKF 等一律沿用）。
- 不改动 `/wiki` 路由、菜单入口，不新增/删除路由。
- 不做 tab 1 与 `/wiki` 两个实例之间的状态同步与缓存。
- 不调整 tab 2 / tab 3 的既有布局与逻辑。

## 方案选型

| 方案 | 做法 | 结论 |
|---|---|---|
| **A. 抽出 `WikiHomePane.vue`** | 把 `wiki/index.vue` 约 860 行搬到新 Pane 组件，`/wiki` 退化成薄壳 | 架构最干净、符合 Pane 惯例，但 diff 巨大、对既有 `/wiki` 页面有回归风险。**不采用** |
| **B+. 直接复用 + `embedded` 开关** | tab 1 `import WikiHome from '@/views/kms/wiki/index.vue'`，给该组件加可选 `embedded` prop 做外观适配 | **采用**。两入口共用同一文件，天然零代码重复；diff 约 10 行 + 少量样式 |
| **C. 复制首页到管理页** | 复制模板与逻辑 | 代码重复、必然漂移，**否决** |

选型理由：B+ 已满足「单一事实来源」——`/wiki` 与 tab 1 渲染的是**同一个文件**，不存在两份实现。`embedded` 仅用于消除「标题重复」与「内边距」这类观感差异，不引入任何逻辑分支。

## 详细设计

### 1. `src/views/kms/KnowledgeBaseManager.vue`

**模板**：删掉跳转型提示块，替换为组件。

```diff
     <a-row v-if="activeType !== '1'" :gutter="16">
       ...
     </a-row>
-    <div v-else class="kb-manager__wiki-hint">
-      <router-link to="/wiki">{{ t('kmsWiki.openWiki') }}</router-link>
-    </div>
+    <WikiHome v-else embedded />
```

**脚本**：新增导入。

```diff
 import KbDocumentPane from './kb/KbDocumentPane.vue'
 import ExternalLinkPane from './kb/ExternalLinkPane.vue'
+import WikiHome from '@/views/kms/wiki/index.vue'
```

**样式**：`.kb-manager__wiki-hint` 已无引用，删除其规则块。

### 2. `src/views/kms/wiki/index.vue`

新增可选 prop，默认 `false` —— 作为路由组件使用时行为**完全不变**。

```diff
 const router = useRouter()
 const { t } = useI18n()
+withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
```

模板根节点绑定修饰类，并按 prop 隐藏与 tab 标签重复的标题：

```diff
-<div class="wiki-index">
+<div class="wiki-index" :class="{ 'wiki-index--embedded': embedded }">
   ...
-  <h2 class="wiki-side__title">{{ t('kmsWiki.title') }}</h2>
+  <h2 v-if="!embedded" class="wiki-side__title">{{ t('kmsWiki.title') }}</h2>
```

样式新增（置于 `<style scoped>` 末尾）：

```css
/* 内嵌于知识库管理 tab：去掉页面级留白、高度改为自适应、隐藏与 tab 标签重复的标题 */
.wiki-index--embedded {
  padding: 0;
  height: auto;
}

.wiki-index--embedded .wiki-side__head {
  justify-content: flex-end;
}
```

> `.wiki-side__head` 原为 `justify-content: space-between`；隐藏标题后改右对齐，保证「+ 分类 / + 知识库」两个图标按钮位置不变。

### 3. i18n 清理

`kmsWiki.openWiki` 经查**仅**被即将删除的提示链接引用（`KnowledgeBaseManager.vue:31`）。移除链接后该 key 失去唯一用处，一并从 4 个语言包删除：

- `src/i18n/locales/zh-CN.ts`
- `src/i18n/locales/zh-TW.ts`
- `src/i18n/locales/en-US.ts`
- `src/i18n/locales/ja-JP.ts`

## 数据流与生命周期

- tab 1 由 `v-else` 条件渲染 → 切到该 tab 时组件**挂载**，`onMounted` 并行拉取分类树、知识库列表与文章列表；切走时**卸载**。
- 因此**每次进入 tab 1 都会重新取数**，与刷新 `/wiki` 首页等价，保证数据新鲜；不使用 `keep-alive`（符合 YAGNI）。
- 树选中过滤、搜索、分页、新建/重命名/删除 分类与知识库、右键菜单、OKF 导出导入、新建文章：全部沿用组件内部现有实现，**一行逻辑都不改**，故与首页天然一致。
- 查看文章 → `/wiki/:slug`、编辑 → `/wiki/edit/:id`、RAG → `/wiki/rag`，仍为 `router.push`，离开管理页。

## 布局与样式

- 内嵌后左右两栏沿用 `grid-template-columns: minmax(240px, 320px) 1fr`，<900px 断点纵向堆叠保持不变。
- `.wiki-index` 原 `padding: 24px; height: 100%`；内嵌时改 `padding: 0; height: auto` —— 父级（动态组件宿主）无确定高度，`height: 100%` 在此无意义，改自适应由宿主滚动。
- 不新增任何硬编码颜色，沿用 `var(--fg)` / `var(--fg-secondary)` 等皮肤令牌，深色/浅色均自动适配。

## 边界与取舍

- **`/wiki` 路由与菜单保留**：文章详情、编辑、RAG 页面都挂在 `/wiki` 路径下，删除会连带破坏这些路由。
- **两实例状态独立**：`/wiki` 与 tab 1 各自取数、各自维护选中态，不做跨实例同步。
- **内嵌实例不感知宿主**：组件内不引入任何「我是否在管理页」的判断，仅通过 `embedded` 这一显式 prop 控制外观。
- **`embedded` 不触发逻辑分支**：不因内嵌而跳过任何数据加载或改变任何交互行为，避免两套语义。

## 验收标准

1. 切到 tab 1：原地显示左栏知识库/分类树 + 右栏工具栏（搜索 / RAG / OKF 导出导入 / 新建文章）、文章列表、分页；不再出现跳转链接或空白提示。
2. 在 tab 1 内完成：按分类/知识库筛选、搜索、翻页、新建文章、新建/重命名/删除分类、新建/编辑/删除知识库、OKF 导出与导入——结果与 `/wiki` 首页一致。
3. 点击文章「查看」「编辑」与「RAG」：仍跳转到对应独立页面（`/wiki/:slug`、`/wiki/edit/:id`、`/wiki/rag`）。
4. 访问 `/wiki`：外观与交互**与改动前完全一致**（含左栏标题、24px 留白）。
5. tab 1 左栏不出现与 tab 标签重复的「Wiki 知识库」标题，图标按钮仍在原位置。
6. 深色与浅色皮肤下 tab 1 文字均清晰可读（无黑色不可读文字）。
7. 切走再切回 tab 1：数据重新加载且结果正确；tab 2 / tab 3 行为不受影响。
8. `kmsWiki.openWiki` 已从 4 个语言包移除且无残留引用；前端构建无报错。

## 影响面与风险

- **影响文件**：2 个组件（`KnowledgeBaseManager.vue`、`wiki/index.vue`）+ 4 个语言包，**共 6 个文件**，无后端改动、无数据库改动、无路由改动。
- **风险**：极低。`wiki/index.vue` 的改动是纯新增（默认关闭的 prop + 一个修饰类），现有 `/wiki` 渲染路径无任何行为变化；`KnowledgeBaseManager.vue` 仅替换 tab 1 的内容块。
- **回归关注点**：`/wiki` 首页（必须零变化）、tab 2 / tab 3（不受影响）、4 语言 i18n 完整性。
