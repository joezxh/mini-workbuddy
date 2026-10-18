---
name: kb-collection-fields-referenced-files
overview: 修复表格知识库「集合与字段」Tab：①编辑字段弹窗能正确加载并展示已有字段（修复 schema_config 未返回导致的空字段行），并新增「排序序号」；②集合列表展示每个集合被引用的文件。
todos:
  - id: backend-collection-schema
    content: 后端：list_knowledge_collections 返回 schema_config；normalize_fields 保留并按 order 稳定排序
    status: pending
  - id: frontend-schema-order
    content: 前端：KbSchemaField 加 order；编辑弹窗加排序序号输入并排序后保存
    status: pending
    dependencies:
      - backend-collection-schema
  - id: frontend-ref-files
    content: 前端：KbCollectionManager 调 listDocuments 按 collection_id 分组，集合列表新增「引用文件」列展示数量与文件名
    status: pending
    dependencies:
      - backend-collection-schema
  - id: verify
    content: 后端 test_collection_crud 新增断言；前端改动文件跑 vue-tsc 类型校验
    status: pending
    dependencies:
      - frontend-schema-order
      - frontend-ref-files
---

## 产品概述
表格知识库「集合与字段」管理面板（`KbCollectionManager.vue`）的增强：修复编辑字段弹窗无法加载已有字段的问题，补充字段「排序序号」，并在集合列表中展示每个集合被引用的文件。

## 核心功能
- 修复编辑字段弹窗：打开已有集合的「编辑字段」时，正确加载并展示其已有字段列表（字段支持行内修改名称/类型、删除、新增、设置是否向量化）。此前的根因是列表接口未返回 `schema_config`，导致弹窗字段行为空。
- 字段新增「排序序号」：每个字段行可填写排序序号，保存时按序号稳定排序（序号影响向量化内容拼接顺序与表格条目列序）。
- 集合列表展示被引用文件：在集合表格中新增「引用文件」列，按 `collection_id` 分组展示归属该集合的文档数量与文件名（如文件名过多提供展开/悬浮查看）。

## 技术栈选择
- 前端：Vue 3 + TypeScript + Ant Design Vue（`a-table`/`a-modal`/`a-input-number`/`a-popover`/`a-tag`），状态用 `ref`/`reactive`/`computed`，沿用现有 `api/kb.ts` 请求层与 `useI18n` 多语言。
- 后端：FastAPI + SQLAlchemy，`schema_config` 为 `KbCollection` 上的 JSONB（加 `order` 无需数据库迁移），复用 `table_schema.normalize_fields`、`list_documents` 既有能力。

## 实现方案
### 1. 修复根因（后端列表接口补齐 schema_config）
`kb.py` 的 `list_knowledge_collections` 端点当前 item 仅返回 `{id, name, dimensions, field_count, embed_fields}`，缺少 `schema_config`，导致前端 `openEditFields(item)` 的 `item.schema_config` 为 `undefined`、弹窗字段行为空。
- 在 item 中追加 `schema_config: get_schema_fields(db, coll.name)`（已在同端点 import 了 `get_schema_fields`），使前端能加载已有字段。该字段为只读展示/编辑来源，列表接口额外返回不破坏现有 `embed_fields`/`field_count` 等字段。

### 2. 字段排序序号（前后端协同）
- 前端 `KbSchemaField` 接口新增 `order?: number`；编辑弹窗每行增加 `a-input-number` 绑定 `f.order`，新增字段默认 `order = fields.length`。
- 保存前：`submitSchema` 将字段按 `order`（缺失时用索引兜底）升序排列后再提交，保证向量化内容拼接与表格列序与序号一致。
- 后端 `table_schema.normalize_fields` 在生成每个字段 dict 时保留 `order`（缺失默认按出现顺序的索引），并在末尾对字段列表按 `order` 做稳定排序，使任何写入路径（含后台自动建集合）都保持有序，避免顺序漂移。

### 3. 集合列表展示被引用文件（纯前端，无需新接口）
- `KbCollectionManager` 已有 `knowledgeId` prop，复用既有前端 `listDocuments(kid)`（返回项含 `document_id`/`name`/`status`/`collection_id`）。
- 在 `load()` 中并行（或紧随）调用 `listDocuments(props.knowledgeId)`，按 `collection_id` 分组得到每个集合的文档数组。
- 集合表格新增「引用文件」列：展示文档数量徽标，并以 `a-popover`/展开形式列出文件名（文件名超长用 `a-tag` + 滚动容器），无引用时显示 `—`。

## 实现注意事项
- 性能：`listDocuments` 与 `listKnowledgeCollections` 均为单知识库维度查询，集合数/文档数有限；按 `collection_id` 做内存分组为 O(n)，无 N+1。不在列表接口内联聚合文档，避免每次集合操作都查文档。
- 兼容：问答/文档型知识库不使用集合，本次改动位于集合管理组件与集合接口，不影响其路径；`schema_config` 为可选字段，历史无 `order` 的集合 normalize 时按索引兜底，无破坏性。
- 日志/错误：沿用现有 `message.error` 提示，不引入新日志。

## 架构设计
- 数据流：`KbCollectionManager.load()` → 并发取「集合列表（含 schema_config）」+「文档列表」→ 前端按 `collection_id` 聚合引用文件 → 渲染表格；编辑字段走 `updateKnowledgeCollection`/`createKnowledgeCollection` 提交（含 `order` 排序后的 `schema_config`）。
- 复用：不新建后端端点，引用文件复用 `list_documents(kid)`；排序复用 `normalize_fields`。

## 目录结构与文件改动
```
backend/app/routers/kb/kb.py          # [MODIFY] list_knowledge_collections 端点 item 增加 schema_config
backend/app/services/kb/table_schema.py # [MODIFY] normalize_fields 保留并按 order 稳定排序
frontend/src/api/kb.ts                # [MODIFY] KbSchemaField 接口新增 order?: number
frontend/src/views/kms/kb/KbCollectionManager.vue # [MODIFY] 弹窗加排序序号输入并排序保存；集合列表加「引用文件」列（调 listDocuments 分组）
backend/tests/kb/test_collection_crud.py # [MODIFY] 新增断言：列表返回 schema_config；带 order 更新后顺序正确
```

## 关键代码结构
```ts
// frontend/src/api/kb.ts
export interface KbSchemaField {
  name: string
  type: 'string' | 'number' | 'boolean'
  enabled: boolean
  embedding: boolean
  filterable: boolean
  order?: number   // 排序序号，缺失按列表索引兜底
}
```
```python
# backend/app/services/kb/table_schema.py（normalize_fields 产出每个字段增加 order 并整体稳定排序）
fields.append({
    "name": name, "type": ftype,
    "enabled": ..., "embedding": ..., "filterable": ...,
    "order": int(item.get("order", idx)),
})
fields.sort(key=lambda f: (f.get("order", 0), f["name"]))  # 稳定排序
```
