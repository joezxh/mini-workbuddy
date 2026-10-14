---
name: kb-manager-unified-tree
overview: 重构 KnowledgeBaseManager.vue：移除顶部 3 个 tab，改为单一界面统一管理 3 类知识库（Wiki/通用/外部）。左侧复用现有共享分类树，但不再按类型过滤——所有类型的知识库叶子混排在分类下，仅用叶子图标区分类型；右侧根据所选知识库的类型分别渲染 WikiHome（聚焦所选 Wiki）、KbDocumentPane（通用）或 ExternalLinkPane（外部）。需为 WikiHome 增加 wikiId 入参以实现「聚焦所选 Wiki」。
design:
  styleKeywords:
    - Yao Agents CUI
    - antd v6
    - 两栏树+内容
    - 类型图标区分
    - 聚焦模式
  fontSystem:
    fontFamily: Outfit
    heading:
      size: 18px
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
    background:
      - "#ffffff"
      - "#f5f7fa"
    text:
      - "#1f2329"
      - "#646a73"
    functional:
      - "#3371fc"
      - "#d0d5dd"
      - "#e6f0ff"
todos:
  - id: refactor-template
    content: 删除 a-tabs，重构两栏模板并按 selectedKbType 渲染三类右栏界面
    status: completed
  - id: refactor-tree-logic
    content: rebuildTree 取消类型过滤并补 kbType，移除 activeType 及其 watch，新增 selectedKbType 派生
    status: completed
    dependencies:
      - refactor-template
  - id: type-icons-wizard
    content: 左树叶子按 kbType 渲染三类图标，向导 form.type 改由选中节点推断
    status: completed
    dependencies:
      - refactor-tree-logic
  - id: wiki-home-focus
    content: WikiHome 增加 wikiId 入参与聚焦模式，隐藏内部分类树并自动定位
    status: completed
  - id: verify-build
    content: 运行 oxlint 与定向 build 校验改动无类型错误
    status: completed
    dependencies:
      - refactor-template
      - refactor-tree-logic
      - type-icons-wizard
      - wiki-home-focus
---

## 用户需求

移除知识库管理页（KnowledgeBaseManager.vue）顶部的 3 个 tab（Wiki / 通用 / 外部），改为在同一界面统一管理 3 类知识库。

## 核心特性

- 删除顶部 tab 切换，左栏知识库树延续现有共享分类树结构，但不再按类型过滤：所有类型（Wiki=1 / 通用=2 / 外部=3）的知识库叶子混排在分类下，不加分组节点。
- 左树叶子图标按知识库类型区分：Wiki 用 ReadOutlined、通用用 BookOutlined、外部用 LinkOutlined，一眼可辨类型。
- 右侧内容区根据所选知识库类型分别渲染不同界面：Wiki → 聚焦该 Wiki 的文章/分类管理（WikiHome 聚焦模式）；通用 → 文档/表格/QA 管理（KbDocumentPane）；外部 → 外部知识库面板（ExternalLinkPane）；未选中时显示空态提示。
- 新建/编辑向导保留类型下拉，默认类型由当前选中节点类型推断（选中知识库取其一，选中分类/空则默认通用）。

## 技术栈

- 前端：Vue 3 + TypeScript + Vite 8 + Ant Design Vue (antd v6)，i18n 多语（复用现有 `t()` 与 key）。
- 组件复用：`WikiHome`（views/kms/wiki/index.vue）、`KbDocumentPane`（views/kms/kb/KbDocumentPane.vue）、`ExternalLinkPane`（views/kms/kb/ExternalLinkPane.vue）均已有，无需新建。
- 图标：@ant-design/icons-vue 的 `ReadOutlined` / `BookOutlined` / `LinkOutlined`（项目已依赖该包）。

## 实现方案

### 总体策略

删除 `activeType` 这个「tab 状态」，将其替换为「选中知识库 id + 选中类型」的派生状态。左树数据 `rebuildTree()` 停止按 `activeType` 过滤，所有类型知识库都挂到共享分类树下；右栏改用 `selectedKbType` 计算属性做条件渲染。Wiki 聚焦能力通过在 `WikiHome` 增加可选 `wikiId` prop 实现，避免「树中树」——聚焦模式隐藏 WikiHome 内部分类侧栏，挂载时自动按 wikiId 定位该 Wiki。

### 关键技术决策

1. **移除 `activeType` 而非改值**：tab 删除后 `activeType` 失去意义，相关 `rebuildTree` 过滤、`resetForm`/`openEdit` 默认值、`watch(activeType)` 全部需改写，避免遗留死分支。
2. **叶子补充 `kbType` 字段**：在 `rebuildTree` 生成叶子节点时写入 `kbType: k.type`，供模板图标渲染、右键菜单、选中类型推断统一读取，避免重复在多处查 `knowledges`。
3. **`selectedKbType` 用 computed 派生**：`knowledges.value.find(k => k.id === selectedId.value)?.type`，与现有 `selectedKbFormat` 模式一致，零额外状态、自动同步。
4. **WikiHome 聚焦模式**：新增 `wikiId?: number` prop；有值时在 `onMounted` 设置 `selectedKind='knowledge'`、`selectedId=wikiId` 并 `loadArticles()`，同时通过新 class（如 `.wiki-index--focus`）隐藏 `.wiki-side` 内部分类树（复用 `embedded` 已有样式体系）。这样复用既有文章列表/分页/搜索逻辑，改动最小。
5. **向导默认类型推断**：`openCreate` 时若 `selectedKbType` 存在取其值，否则默认 2（通用）；`openEdit` 直接用 `kb.type`（去掉 `|| activeType.value`）。保留向导内 type 下拉，用户仍可手动改。

### 性能与可靠性

- 左树仍只在 `load()` 后 `rebuildTree()` 一次构建，不做逐节点监听；选中仅更新 `selectedId` 派生右栏，无额外请求。
- WikiHome 聚焦仅多一次文章列表请求（已含分页/缓存结构），无 N+1；挂载即定位，用户无需二次点击。
- 右栏 `v-if` 切换组件时 Vue 自动卸载旧组件，释放 WikiHome 的树/列表状态，无内存泄漏。

## 实现注意（防回归）

- 复用现有 `var(--accent)`/`var(--fg-secondary)` 等 CSS 变量与 `.kb-manager__*` 样式，不引入新主题。
- 新建向导里 `form.type===2`/`===3` 的分支形态逻辑保持不变，仅去掉对 `activeType` 的引用。
- `load()` 与 `rebuildTree()` 的调用链（Promise.all 拉取 knowledges+categories）保持原样，仅去掉 `typeKbs` 过滤；`uncategorized` 分组逻辑保留。
- 验证用定向 build：参考 AGENTS.md，前端 `oxlint` 检查；改完后用 `npm run build 2>&1 | Select-String "KnowledgeBaseManager"` 过滤确认无新增类型错误。

## 架构与目录结构

仅修改 2 个已有文件，无新增模块：

```
frontend/src/views/kms/
├── KnowledgeBaseManager.vue   # [MODIFY] 删除 a-tabs；右栏按 selectedKbType 渲染三组件；rebuildTree 去掉类型过滤并给叶子加 kbType；onSelectKnowledge 仅记录 id（类型由 computed 派生）；移除 activeType ref 及 watch；左树 #title 按 kbType 渲染图标；新建/编辑向导 form.type 改由选中节点推断；新增 ReadOutlined/LinkOutlined 图标引入。
└── wiki/index.vue             # [MODIFY] defineProps 增加 wikiId?: number；有值时进入聚焦模式——onMounted 按 wikiId 定位 selectedKind/selectedId 并 loadArticles，新增 .wiki-index--focus 样式隐藏 .wiki-side 内部分类树以避免树中树。
```

### 关键代码要点（接口级）

```ts
// KnowledgeBaseManager.vue
const selectedKbType = computed<number | null>(() =>
  knowledges.value.find((k) => k.id === selectedId.value)?.type ?? null,
)

// wiki/index.vue props
const props = withDefaults(defineProps<{ embedded?: boolean; wikiId?: number }>(), {
  embedded: false,
  wikiId: undefined,
})
```

## 左树叶子图标映射

| 类型 | kbType | 图标 |
| --- | --- | --- |
| Wiki | 1 | ReadOutlined |
| 通用 | 2 | BookOutlined |
| 外部 | 3 | LinkOutlined |


## 设计风格

沿用项目既有的 Yao Agents CUI 设计语言（antd v6 + 顶部 64px 图标轨 + 256px 上下文栏，主色 `#3371fc`），保持与工作台其它页面一致的视觉调性，不引入新设计体系。布局为「左树 + 右内容」两栏栅格，与现有 KnowledgeBaseManager / WikiHome 一致。

## 布局区块（自上而下）

1. **顶部操作条（无 tab）**：原 tab 行移除，左树头部保留「+ 分类 / + 知识库」两个图标按钮（右对齐），维持现有 hover 变主色交互。
2. **左栏：共享分类树**：沿用现有卡片化树（`minmax(240px,320px)` 流式宽），分类为父节点、知识库为叶子；叶子前按类型显示不同图标（Wiki 书卷 / 通用书本 / 外部链接），图标色沿用 `var(--accent)`；右键菜单保持原有「查看/编辑/删除」。
3. **右栏：按类型切换的内容区**：

- Wiki 聚焦：隐藏 WikiHome 内部分类树，仅显示该 Wiki 的文章列表/搜索/分页（复用既有样式）。
- 通用：KbDocumentPane 文档/表格/QA 形态切换与上传区。
- 外部：ExternalLinkPane 占位面板。
- 未选中：空态提示「请选择知识库」。

4. **新建/编辑向导 Modal**：保留类型下拉与全部形态字段，仅默认类型改为按选中节点推断。

## 交互与响应式

- 选中叶子即时切换右栏，无整页刷新；组件卸载/挂载自动清理。
- 两栏栅格在窄屏保持最小 240px 侧栏、主区自适应；树内长文本不换行（沿用 `.ant-tree-node-content-wrapper` 现有规则）。
- 图标微交互：hover 时图标与文字主色高亮（延续 `.kb-icon`/`.kb-manager__tree-icon-btn:hover` 行为）。