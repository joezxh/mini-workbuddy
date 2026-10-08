# 知识库管理 Tab 内嵌 Wiki 首页 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Wiki 知识库首页内容直接嵌进 `KnowledgeBaseManager.vue` 的 `key="1"` 标签页，替换掉现有的 `<router-link to="/wiki">` 跳转链接，使 tab 1 与独立 `/wiki` 首页功能一致且就地展示。

**Architecture:** 采用「直接复用 + `embedded` 开关」方案（spec §方案选型 B+）。`/wiki` 路由与 tab 1 渲染**同一个文件** `src/views/kms/wiki/index.vue`，因此天然零代码重复；新增的可选 prop `embedded`（默认 `false`）只控制外观（隐藏与 tab 标签重复的标题、去掉页面级留白、高度改自适应），不引入任何逻辑分支，`/wiki` 原渲染路径行为零变化。文章「查看/编辑」与 RAG 仍 `router.push` 跳转到独立页面。

**Tech Stack:** Vue 3.4 (`<script setup lang="ts">`) + TypeScript 5.4 + ant-design-vue ^4.1.2 + vue-i18n 9 + vue-router 4 + Vitest 2（environment `node`，组件测试用 `@vue/server-renderer` 的 `createSSRApp` + `renderToString` 断言 HTML 字符串）。

## Global Constraints

- **禁止新增依赖**：`@vue/test-utils`、`jsdom`、`happy-dom` 均未安装，组件测试只能用 SSR 渲染断言 HTML 字符串。
- **`/wiki` 路由必须零变化**：`embedded` 默认 `false`，作为路由组件使用时渲染结果与改动前逐字节一致。
- **不新增/删除路由，不改后端，不改数据库**。
- **i18n 四语齐全**：涉及 key 的增删必须同步 `zh-CN.ts` / `zh-TW.ts` / `en-US.ts` / `ja-JP.ts`。
- **不新增硬编码颜色**：一律使用皮肤令牌 `var(--fg)` / `var(--fg-secondary)` / `var(--accent)` 等。
- **不改 `wiki/index.vue` 的业务逻辑**（树、筛选、搜索、分页、OKF、各类弹窗一律不动）。
- 命令均在 `d:\projects\MinWorkBuddy\frontend` 目录下执行。

---

### Task 1: `wiki/index.vue` 增加 `embedded` prop

**Files:**
- Modify: `src/views/kms/wiki/index.vue`（第 2 行根节点、第 7 行标题、第 242-243 行 script 顶部、第 746 行起的 `<style scoped>`）
- Test: `src/views/kms/wiki/__tests__/index.spec.ts`（新建）

**Interfaces:**
- Consumes: 无（本任务不依赖其它任务的产物）
- Produces: `wiki/index.vue` 暴露 prop `embedded?: boolean`（默认 `false`）；根节点在 `embedded` 为真时带修饰类 `wiki-index--embedded`，且此时不渲染 `.wiki-side__title` 标题。Task 2 依赖此 prop 与此类名。

- [ ] **Step 1: 写失败测试**

新建 `src/views/kms/wiki/__tests__/index.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import Antd from 'ant-design-vue'
import WikiHome from '../index.vue'

/** 用可辨识的占位文案替换真实 i18n，避免断言依赖翻译内容 */
const TITLE = 'WIKI_TITLE_MARKER'

function makeI18n() {
  return createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': { kmsWiki: { title: TITLE } } },
  })
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
}

async function ssr(props: Record<string, unknown> = {}) {
  const app = createSSRApp(WikiHome, props)
  app.use(Antd)
  app.use(makeI18n())
  app.use(makeRouter())
  return renderToString(app)
}

describe('wiki/index.vue embedded prop', () => {
  it('默认（非内嵌）：渲染标题且不带 embedded 修饰类', async () => {
    const html = await ssr()
    expect(html).toContain(TITLE)
    expect(html).not.toContain('wiki-index--embedded')
  })

  it('embedded=true：不渲染标题且带 embedded 修饰类', async () => {
    const html = await ssr({ embedded: true })
    expect(html).not.toContain(TITLE)
    expect(html).toContain('wiki-index--embedded')
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd d:\projects\MinWorkBuddy\frontend
npx vitest run src/views/kms/wiki/__tests__/index.spec.ts
```

Expected: FAIL —— 第二个用例失败（`embedded` prop 尚不存在，HTML 仍含 `TITLE` 且不含 `wiki-index--embedded`）。

- [ ] **Step 3: 若 SSR 因 api 模块加载期访问浏览器全局而报错，则加 mock**

只有在实际报错时才加。在 `index.spec.ts` 顶部 import 之后追加：

```ts
vi.mock('@/api/wiki', () => ({
  listArticles: vi.fn(), createArticle: vi.fn(),
  createCategory: vi.fn(), updateCategory: vi.fn(), deleteCategory: vi.fn(),
  listCategories: vi.fn(), searchArticles: vi.fn(),
  listKnowledges: vi.fn(), createKnowledge: vi.fn(),
  updateKnowledge: vi.fn(), deleteKnowledge: vi.fn(),
}))
vi.mock('@/api/kb', () => ({ exportOkfBundle: vi.fn(), importOkfBundle: vi.fn() }))
```

并把首行 import 改为 `import { describe, it, expect, vi } from 'vitest'`。

- [ ] **Step 4: 实现 prop**

`src/views/kms/wiki/index.vue` 第 243 行 `const { t } = useI18n()` 之后新增一行：

```ts
withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
```

（不赋值给常量 —— 模板直接使用 `embedded`，赋值会产生未使用变量触发 lint。）

- [ ] **Step 5: 根节点绑定修饰类**

第 2 行：

```diff
-<div class="wiki-index">
+<div class="wiki-index" :class="{ 'wiki-index--embedded': embedded }">
```

- [ ] **Step 6: 标题按 prop 隐藏**

第 7 行：

```diff
-  <h2 class="wiki-side__title">{{ t('kmsWiki.title') }}</h2>
+  <h2 v-if="!embedded" class="wiki-side__title">{{ t('kmsWiki.title') }}</h2>
```

- [ ] **Step 7: 新增内嵌样式**

在 `<style scoped>` 末尾（`src/views/kms/wiki/index.vue` 第 858 行 `@media (max-width: 900px)` 块之后）追加：

```css
/* 内嵌于知识库管理 tab：去掉页面级留白、高度改自适应、隐藏与 tab 标签重复的标题 */
.wiki-index--embedded {
  padding: 0;
  height: auto;
}

.wiki-index--embedded .wiki-side__head {
  justify-content: flex-end;
}
```

> `.wiki-side__head` 原为 `justify-content: space-between`；隐藏标题后改右对齐，保证「+ 分类 / + 知识库」两个图标按钮位置不变。

- [ ] **Step 8: 运行测试确认通过**

```bash
npx vitest run src/views/kms/wiki/__tests__/index.spec.ts
```

Expected: PASS（2 passed）

- [ ] **Step 9: 提交**

```bash
cd d:\projects\MinWorkBuddy
git add frontend/src/views/kms/wiki/index.vue frontend/src/views/kms/wiki/__tests__/index.spec.ts
git commit -m "feat(wiki): add embedded prop to wiki home for in-tab reuse"
```

---

### Task 2: `KnowledgeBaseManager.vue` tab 1 接入 Wiki 首页

**Files:**
- Modify: `src/views/kms/KnowledgeBaseManager.vue`（第 141-142 行 import 区、第 30-32 行提示块、第 292-295 行 style）

**Interfaces:**
- Consumes: Task 1 产出的 `WikiHome`（`src/views/kms/wiki/index.vue`）及其 prop `embedded?: boolean`
- Produces: tab 1 就地渲染 Wiki 首页；不再存在跳转型提示块与 `.kb-manager__wiki-hint` 样式

- [ ] **Step 1: 新增导入**

第 142 行 `import ExternalLinkPane from './kb/ExternalLinkPane.vue'` 之后：

```diff
 import ExternalLinkPane from './kb/ExternalLinkPane.vue'
+import WikiHome from '@/views/kms/wiki/index.vue'
```

- [ ] **Step 2: 用组件替换跳转提示块**

第 30-32 行：

```diff
-    <div v-else class="kb-manager__wiki-hint">
-      <router-link to="/wiki">{{ t('kmsWiki.openWiki') }}</router-link>
-    </div>
+    <WikiHome v-else embedded />
```

- [ ] **Step 3: 删除已失效的样式**

第 292-295 行，删除整块：

```css
.kb-manager__wiki-hint {
  padding: 48px;
  text-align: center;
}
```

- [ ] **Step 4: 类型检查**

```bash
cd d:\projects\MinWorkBuddy\frontend
npx vue-tsc
```

Expected: 无输出（无类型错误）。若报 `Cannot find module '@/views/kms/wiki/index.vue'`，确认 `@` 别名已在 `vite.config.ts` / `vitest.config.ts` 中映射到 `src`（两者都有）。

- [ ] **Step 5: 回归既有测试**

```bash
npx vitest run src/views/kms/wiki/__tests__/index.spec.ts
```

Expected: PASS（2 passed）—— 确认 Task 1 的 prop 契约未被破坏。

- [ ] **Step 6: 提交**

```bash
cd d:\projects\MinWorkBuddy
git add frontend/src/views/kms/KnowledgeBaseManager.vue
git commit -m "feat(kb): embed wiki home directly in knowledge manager tab 1"
```

---

### Task 3: 清理失效的 i18n key `kmsWiki.openWiki`

**Files:**
- Modify: `src/i18n/locales/zh-CN.ts:2140`
- Modify: `src/i18n/locales/zh-TW.ts:2134`
- Modify: `src/i18n/locales/ja-JP.ts:2133`
- Modify: `src/i18n/locales/en-US.ts:2129`

**Interfaces:**
- Consumes: Task 2 已移除唯一引用该 key 的 `<router-link>`（已确认：`openWiki` 此前仅被 `KnowledgeBaseManager.vue:31` 引用）
- Produces: 四语 locale 中不再有失效 key

- [ ] **Step 1: 删除四个语言包中的 key**

分别删除以下四行（含缩进与结尾逗号）：

```ts
// src/i18n/locales/zh-CN.ts
    openWiki: '打开 LLM Wiki',
// src/i18n/locales/zh-TW.ts
    openWiki: '打開 LLM Wiki',
// src/i18n/locales/ja-JP.ts
    openWiki: 'LLM Wiki を開く',
// src/i18n/locales/en-US.ts
    openWiki: 'Open LLM Wiki',
```

- [ ] **Step 2: 确认无残留引用**

```powershell
cd d:\projects\MinWorkBuddy\frontend
Get-ChildItem -Path src -Recurse -Include *.vue,*.ts | Select-String -Pattern 'openWiki'
```

Expected: 0 条匹配。

- [ ] **Step 3: 类型检查**

```bash
npx vue-tsc
```

Expected: 无类型错误。

- [ ] **Step 4: 提交**

```bash
cd d:\projects\MinWorkBuddy
git add frontend/src/i18n/locales/zh-CN.ts frontend/src/i18n/locales/zh-TW.ts frontend/src/i18n/locales/ja-JP.ts frontend/src/i18n/locales/en-US.ts
git commit -m "chore(i18n): drop unused kmsWiki.openWiki key"
```

---

### Task 4: 全量验证与手动验收

**Files:** 无新增改动（纯验证任务）

**Interfaces:**
- Consumes: Task 1-3 的全部产物

- [ ] **Step 1: 跑全量单测**

```bash
cd d:\projects\MinWorkBuddy\frontend
npx vitest run
```

Expected: 全部通过（至少含本次新增的 2 个用例）。若既有测试原本就有失败，记录基线并与本次改动前对比确认非本次引入。

- [ ] **Step 2: 类型检查 + 生产构建**

```bash
npm run build
```

Expected: 输出 `[build] Running vue-tsc...` → `[build] Running vite build --mode production...` → `[build] Build complete!`（构建脚本已内置 `--max-old-space-size=8192`）。

- [ ] **Step 3: Lint**

```bash
npm run lint
```

Expected: 无 error。（注意该脚本带 `--fix`，会自动修正格式，执行后确认 diff 仅涉及本次改动的文件。）

- [ ] **Step 4: 浏览器手动验收**

```bash
npm run dev
```

按 spec §验收标准逐条核对：

1. 切到 tab 1：原地显示左栏知识库/分类树 + 右栏工具栏（搜索 / RAG / OKF 导出导入 / 新建文章）、文章列表、分页；**不再出现跳转链接或空白提示**。
2. tab 1 内完成：按分类/知识库筛选、搜索、翻页、新建文章、新建/重命名/删除分类、新建/编辑/删除知识库、OKF 导出与导入 —— 结果与 `/wiki` 首页一致。
3. 点击文章「查看」「编辑」与「RAG」：仍跳转到 `/wiki/:slug`、`/wiki/edit/:id`、`/wiki/rag`。
4. 访问 `/wiki`：外观与交互**与改动前完全一致**（含左栏标题、`24px` 留白）。
5. tab 1 左栏**不出现**与 tab 标签重复的「Wiki 知识库」标题，图标按钮仍在原位置。
6. 深色与浅色皮肤下 tab 1 文字均清晰可读（无黑色不可读文字）。
7. 切走再切回 tab 1：数据重新加载且正确；tab 2 / tab 3 行为不受影响。
8. `kmsWiki.openWiki` 已从 4 个语言包移除且无残留引用。

- [ ] **Step 5: 若有修正则提交，否则本任务无提交**

```bash
cd d:\projects\MinWorkBuddy
git status --short
```

确认工作区只剩预期改动；若 Step 1-4 产生了修正，单独提交一条 `fix:` 提交。
