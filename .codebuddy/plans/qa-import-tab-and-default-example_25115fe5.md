---
name: qa-import-tab-and-default-example
overview: 对问答类型知识库的前端「问题导入」手动录入卡片与「问答条目」列表，从上下两栏改为 Tab 切换；手动录入框默认预填一份完整 QA 范例；确认问答的问题部分已向量化、检索依赖问题向量（设计已具备，本次以验证为主）。
design:
  architecture:
    framework: vue
  styleKeywords:
    - Ant Design Vue 后台
    - Tab 切换
    - 信息提示 Alert
    - 蓝主色
    - 轻量卡片
  fontSystem:
    fontFamily: PingFang SC, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif
    heading:
      size: 16px
      weight: 600
    subheading:
      size: 14px
      weight: 500
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#1677FF"
    background:
      - "#FFFFFF"
      - "#F5F5F5"
    text:
      - rgba(0,0,0,0.88)
      - rgba(0,0,0,0.65)
    functional:
      - "#52C41A"
      - "#FF4D4F"
      - "#FAAD14"
todos:
  - id: refactor-qa-tabs
    content: 重构 KbDocumentPane.vue 的 qa 形态为 a-tabs 双标签（问答导入/问答条目），移除上下两栏
    status: completed
  - id: prefill-qa-example
    content: 为 qaText 预填完整 QA 范例并保留导入成功清空逻辑
    status: completed
    dependencies:
      - refactor-qa-tabs
  - id: verify-qa-vector-retrieval
    content: 在 test_qa_import_api.py 补充断言：QA 分段 content=问题、chunk_type=qa、answer 进 metadata
    status: completed
  - id: ui-verify-with-playwright
    content: 用 [mcp:Playwright MCP Server] 验证 Tab 切换与默认范例渲染
    status: completed
    dependencies:
      - refactor-qa-tabs
      - prefill-qa-example
---

## 用户需求
针对「问答（qa）」形态知识库的右侧面板，做以下调整（含用户二次追加的两项）：

1. **Tab 化切换**：将当前「问答导入」手动录入卡片（上方）与「问答条目」列表（下方）从上下两栏堆叠，改为同一区域内的 Tab 切换。
2. **默认范例**：手动录入文本框内默认预填一份完整、可直接点击「导入问答」的 QA 范例（格式 `问题|答案|标签`，多行），导入成功仍清空。
3. **向量化与检索**：确认问答的「问题」部分被向量化、检索命中依赖问题部分的向量检索。经核查该能力后端已具备（`build_qa_chunks` 把 question 写入 Chunk.content 并嵌入，answer 仅进 metadata；`retrieve` 端点对 content 向量检索），本次以验证为主、不新增向量化逻辑。
4. **【新增】去掉底部「检索测试」**：qa 形态右侧面板底部不再渲染检索测试卡片（该能力已由知识库「检索」标签页 SearchTester 提供，避免重复）。
5. **【新增】Tab 顺序与默认态**：「问答条目」Tab 放在前面，「问答导入」放后面；默认激活「问答条目」。

## 核心功能
- 单区域内 Tab 切换：问答条目 / 问答导入，二选一展示，去除上下两栏。
- 手动录入框预置范例，降低首次使用门槛。
- qa 形态移除底部检索测试卡片。
- 保留并验证：问题向量化入库、按问题语义检索命中；CSV 批量导入入口保留在「问答条目」Tab 内。

## 技术栈
- 前端：Vue 3 + TypeScript + Ant Design Vue（`a-tabs`/`a-tab-pane`/`a-textarea`/`a-button`/`a-alert`/`a-card`/`a-input-search`），Vite 构建；i18n 用 `vue-i18n`。
- 后端：FastAPI + SQLAlchemy + pgvector（本任务不改动）。

## 实现方案
### 1. 前端布局改造（KbDocumentPane.vue）
当前 `formatMode === 'qa'` 分支（约 114–131 行）已改为 `a-tabs`。按新需求调整：

- **Tab 顺序 + 默认态**：`<a-tab-pane key="list" :tab="t('kbMgmt.qaRecords')">` 放**第一位**（含 `<QaRecordList :collection="collection" />`），`<a-tab-pane key="import" :tab="t('kbMgmt.qaImport')">` 放**第二位**（提示 + 文本框 + 导入按钮）。脚本 `const qaTab = ref('list')`，默认激活问答条目。
- 保留 `force-render` 于 list 面板（挂载即加载列表，切回不丢状态）。

### 2. 默认范例（KbDocumentPane.vue 脚本）
`qaText` 初始值改为完整多行范例（`QA_SAMPLE` 常量），保留 `runQaImport()` 成功后 `qaText.value = ''` 的清空逻辑：
```
退款政策?|支持 7 天无理由退款，商品需保持完好并附带原包装
如何查询物流?|在「我的订单」中点击「查看物流」即可实时跟踪|物流,售后
发票怎么开?|订单完成后在订单详情页申请电子发票，1 个工作日内发送到预留邮箱|发票,财务
会员有哪些权益?|会员可享全场包邮、专属折扣与优先客服响应|会员,权益
```

### 3. 【新增】移除 qa 形态底部检索测试
底部检索测试卡片位于模板约 164–190 行：
```vue
<a-card v-if="!HIDE_TESTER_FORMATS.includes(formatMode)" class="kb-doc-pane__tester" :title="t('kbMgmt.retrievalTest')" size="small">
```
脚本第 229 行：
```ts
const HIDE_TESTER_FORMATS: Array<typeof formatMode.value> = ['document', 'table']
```
**改动**：在 `HIDE_TESTER_FORMATS` 中追加 `'qa'` → `['document', 'table', 'qa']`。

选择此方案的原因：检索测试卡片对 `pipeline`（管线调试）形态仍有用途，用既有的 `HIDE_TESTER_FORMATS` 白名单机制屏蔽 qa，是最小改动面（blast radius 最小、零风险），不破坏 pipeline 形态，也不需要删除模板与 `runRetrieve`/`query`/`results` 等相关代码。

### 4. 向量化与检索验证（后端测试）— 已完成
- 已在 `backend/tests/kb/test_qa_import_api.py` 新增 `test_qa_segment_embeds_question_only`：断言 QA 分段 `content == 问题`、`chunk_type == 'qa'`、`metadata_.answer` 为答案值、`answer` 列与 metadata 一致、`tags` 正确解析，锚定需求 3 防止回归。真实语义检索依赖线上 embedding，测试用伪 `kb_factory` 仅锚定落库结构。

## 实现注意
- 仅改动 qa 形态分支与 `HIDE_TESTER_FORMATS` 常量，不触碰 `document`/`table`/`pipeline` 其他形态的渲染逻辑。
- `a-tabs` 切换为纯前端状态，无额外接口请求。
- 保留既有 i18n 键（`qaImport`/`qaRecords`/`qaHint`/`qaPlaceholder`/`importQa`/`retrievalTest`），不新增也不删除文案键，避免多语言遗漏。
- 检索测试相关函数（`runRetrieve`/`query`/`results`/`indexMode`）保留不动，仅对 qa 形态隐藏卡片，避免死代码误删。

## 架构设计
```
KbDocumentPane(qa 形态)
├── a-tabs (qaTab，默认 'list')
│   ├── [1] 问答条目  → QaRecordList(列表 + 批量导入问答 CSV + 导出 + 单条启停)   ← 默认激活
│   └── [2] 问答导入  → 提示 + a-textarea(qaText 预填范例) + 导入问答按钮 → runQaImport()
└── (qa 形态不再渲染检索测试卡片)
```
后端链路不变：`create_qa_records` / `import_qa_records` → `ingest_qa_records` → `build_qa_chunks` → `_insert_via_kb`（已修复 async 路由 500）→ `retrieve`（content 向量检索）。

## 目录结构
```
frontend/src/views/kms/kb/
└── KbDocumentPane.vue          # [MODIFY] ①qa 形态 a-tabs 双标签（问答条目在前、默认激活）；
                                 #           ②qaText 预填完整 QA 范例；
                                 #           ③HIDE_TESTER_FORMATS 追加 'qa' 去掉底部检索测试。
backend/tests/kb/
└── test_qa_import_api.py       # [DONE] 新增断言：QA 分段 content=问题、chunk_type=qa、answer 进 metadata。
```

## 关键代码结构
- 模板（qa 分支）：
```vue
<a-tabs v-else-if="formatMode === 'qa'" v-model:activeKey="qaTab" class="kb-doc-pane__qa-tabs">
  <a-tab-pane key="list" :tab="t('kbMgmt.qaRecords')" force-render>
    <QaRecordList :collection="collection" />
  </a-tab-pane>
  <a-tab-pane key="import" :tab="t('kbMgmt.qaImport')">
    <a-alert class="kb-doc-pane__hint" type="info" :message="t('kbMgmt.qaHint')" show-icon />
    <a-textarea v-model:value="qaText" :rows="14" :auto-size="{ minRows: 14, maxRows: 24 }" :placeholder="t('kbMgmt.qaPlaceholder')" />
    <a-button class="kb-doc-pane__form" type="primary" :loading="qaImporting" @click="runQaImport">
      {{ t('kbMgmt.importQa') }}
    </a-button>
  </a-tab-pane>
</a-tabs>
```
- 脚本：`const qaTab = ref('list')`；`const HIDE_TESTER_FORMATS = ['document', 'table', 'qa']`。

## 设计说明
沿用 Ant Design Vue 管理后台风格：
- **布局**：`a-tabs` 替代上下两栏；qa 形态底部不再出现检索测试卡片，面板更聚焦。
- **Tab 顺序**：「问答条目」在前并默认激活 —— 用户进入后优先看到已有问答资产与批量导入入口，需要时再切到「问答导入」手动录入。
- 其余交互（提示 Alert、文本框预填范例、导入 loading、成功/失败 message）保持不变。

## Agent Extensions
### MCP
- **Playwright MCP Server**：验证 qa 面板已为 Tab 布局、「问答条目」在前且默认激活、切到「问答导入」可见预填范例、底部无检索测试卡片。
