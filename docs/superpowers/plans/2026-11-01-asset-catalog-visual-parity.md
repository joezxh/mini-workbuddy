# 数据资产目录全视觉对齐原型 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/admin/data-asset` 数据资产目录的前后端交互与视觉形态逐项对齐到原型 `ontology-asset-catalog-preview.html`（AF-01~AF-08 全视觉奇偶对齐）。

**Architecture:** 后端仅在 `OntologyAssetService._card` 增结构化列 + `_tags_for` 增 `id`（不新增接口/SQL）；前端把可单测决策继续下沉到纯函数模块（`assetText`/`assetSearch`/`assetTree`/`assetSend`/新 `ontologyNav`），组件层消费；`AssetPickerPanel` 由 2 栏扩为 3 栏并引入新 `AssetSendDock`；送数后跨页跳本体工作台构建页签（`OntologyWorkspace` 读 route query）。

**Tech Stack:** FastAPI + SQLAlchemy + PostgreSQL；Vue 3 Composition API + Ant Design Vue + Vue Router + vue-i18n(t2)；Vitest（无 @vue/test-utils/jsdom，纯函数 + `@vue/server-renderer` `renderToString` + `vi.mock` ontologyText）；后端 pytest（per-tenant `client_a`/`db` fixtures）。

**Spec:** `docs/superpowers/specs/2026-11-01-asset-catalog-visual-parity-design.md`

## Global Constraints

- 检索禁用 `pg_trgm.similarity()` / `word_similarity()`（对 CJK 恒 0），GIN 仅加速 `LIKE`。
- 送数不写任何结构表，只覆盖 `draft_scope_json`。
- 一个建模作用域仅单一 `source_id`（`BUILD_SCOPE_SINGLE_SOURCE`）。
- 同分排序恒按 `table_name` 字典序（可复现）。
- `asset_tag_binding.asset_id` 不建外键。
- 清单强制 `page/size`（默认 50，上限 200）；**不加** `show-size-changer`。
- 文案经 `t2(中文原文)` 收口；新短语补 `ontologyLocale.ts` en/ja，zh 回落原文。
- 可见性开关/引擎不做（§10 Q1 裁决 A）。
- 后端测试用 `backend/.venv/Scripts/python.exe -m pytest`；命令在 `backend/` 目录内执行（PowerShell，勿用 `cd /d`）。
- 前端测试/类型检查在 `frontend/` 目录内执行：`npx vitest run …`、`npx vue-tsc --noEmit`。
- 提交用 scoped `git add <本次文件>`，中文 commit message。

---

### Task 1: 后端卡片结构化列 + 标签 id

**Files:**
- Modify: `backend/app/services/ontology/ontology_asset_service.py:146-197`（`_card`、`_tags_for`）
- Test: `backend/tests/ontology/test_asset_search.py`

**Interfaces:**
- Produces: `search()` 返回 `items[].columns: [{name,type,comment,pii}]`（`pii` 为 `L0|L1|L2|L3`）、`items[].tags[].id`；`column_digest` 保留。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/ontology/test_asset_search.py` 末尾追加：

```python
# ── Task 1：结构化列 + 标签 id（AF-05/AF-03 视觉对齐）──

def test_card_returns_structured_columns(db):
    from app.models.dataops.meta import MetaColumn

    ds = _source(db)
    t = _add_table(db, ds.id, "crm_customer", comment="客户主数据")
    db.add(MetaColumn(tenant_id=100, table_id=t.id, column_name="cust_name",
                      data_type="VARCHAR", column_comment="客户名称", pii_level="L1", ordinal=1))
    db.add(MetaColumn(tenant_id=100, table_id=t.id, column_name="id_card",
                      data_type="VARCHAR", column_comment="身份证号", pii_level="L3", ordinal=2))
    db.flush()
    item = OntologyAssetService(db, 100).search(kw="客户")["items"][0]
    cols = {c["name"]: c for c in item["columns"]}
    assert cols["id_card"]["pii"] == "L3"
    assert cols["id_card"]["type"] == "VARCHAR"
    assert cols["cust_name"]["comment"] == "客户名称"
    assert item["column_digest"]  # 扁平串向后兼容仍在


def test_card_tags_carry_id(db):
    from app.models.ontology.asset_tag import MetaAssetTag, MetaAssetTagBinding

    ds = _source(db)
    t = _add_table(db, ds.id, "sales_order")
    tag = MetaAssetTag(tenant_id=100, code="core", name="核心表", color="#3371fc", tag_kind="biz")
    db.add(tag)
    db.flush()
    db.add(MetaAssetTagBinding(tenant_id=100, tag_id=tag.id, asset_kind="table", asset_id=t.id))
    db.flush()
    item = OntologyAssetService(db, 100).search(kw="sales")["items"][0]
    assert item["tags"] and item["tags"][0]["id"] == tag.id
```

> 若 `MetaAssetTagBinding` 构造函数要求额外非空列（如 `source`/`op`），按模型 `app/models/ontology/asset_tag.py` 补默认值后再 `db.add`。

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/ontology/test_asset_search.py -q`（工作目录 `backend/`）
Expected: FAIL —`KeyError: 'columns'` / `KeyError: 'id'`

- [ ] **Step 3: 实现**

`_card` 内 `digest` 赋值之后、`pii_max` 之前，新增 `columns`：

```python
        columns = [
            {"name": c.column_name, "type": c.data_type or "",
             "comment": (c.column_comment or c.biz_name or ""), "pii": c.pii_level or "L0"}
            for c in cols
        ]
```

`_card` 返回 dict 中，`"column_digest": digest,` 之后加一行：

```python
            "columns": columns,
```

`_tags_for` 整体替换为带 `id` 版本：

```python
    def _tags_for(self, table_id: int) -> List[dict]:
        rows = self.db.execute(
            select(MetaAssetTag.id, MetaAssetTag.code, MetaAssetTag.name, MetaAssetTag.color)
            .join(MetaAssetTagBinding, MetaAssetTagBinding.tag_id == MetaAssetTag.id)
            .where(
                MetaAssetTagBinding.tenant_id == self.tenant_id,
                MetaAssetTagBinding.asset_kind == "table",
                MetaAssetTagBinding.asset_id == table_id,
            )
        ).all()
        return [{"id": tid, "code": c, "name": n, "color": col} for tid, c, n, col in rows]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/ontology/test_asset_search.py -q`
Expected: PASS（新增 2 用例通过，原用例不回退）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/ontology/ontology_asset_service.py backend/tests/ontology/test_asset_search.py
git commit -m "feat(backend): 资产卡片返回结构化列与标签 id（对齐原型 AF-05/AF-03）"
```

---

### Task 2: `renderColumnDigest` 纯函数

**Files:**
- Modify: `frontend/src/views/data-source/asset/assetText.ts`
- Test: `frontend/src/views/data-source/asset/__tests__/AssetCardList.spec.ts`

**Interfaces:**
- Consumes: `hl`、`esc`（同文件既有）。
- Produces: `renderColumnDigest(cols: DigestColumn[], kw?: string): string`；`interface DigestColumn { name: string; type?: string; comment?: string; pii?: string }`。输出 HTML：PII `L2/L3` 列包 `class="cc-pii"`，注释段包 `class="cc"`，`· ` 分隔，含 `<mark>` 高亮。

- [ ] **Step 1: 写失败测试**

在 `AssetCardList.spec.ts` 顶部 import 改为 `import { hl, fmtRows, renderColumnDigest } from '../assetText'`，并追加：

```typescript
describe('renderColumnDigest（AF-05）', () => {
  it('PII L2/L3 标红 + COMMENT 段 + 关键词高亮', () => {
    const html = renderColumnDigest(
      [{ name: 'id_card', type: 'VARCHAR', comment: '身份证号', pii: 'L3' },
       { name: 'qty', type: 'INT', comment: '', pii: 'L0' }], 'id')
    expect((html.match(/cc-pii/g) || []).length).toBe(1)
    expect(html).toContain('COMMENT')
    expect(html).toContain('<mark>id</mark>_card')
    expect(html).toContain('qty INT')
  })
  it('空列返回空串', () => {
    expect(renderColumnDigest([], 'x')).toBe('')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetCardList.spec.ts`（工作目录 `frontend/`）
Expected: FAIL —`renderColumnDigest is not exported`/undefined

- [ ] **Step 3: 实现**

在 `assetText.ts` 末尾追加：

```typescript
export interface DigestColumn { name: string; type?: string; comment?: string; pii?: string }

/** 逐列内联摘要（移植原型 dg）：PII L2/L3 标红、关键词高亮、COMMENT 注释段、`·` 分隔 */
export function renderColumnDigest(cols: DigestColumn[], kw = ''): string {
  if (!cols || !cols.length) return ''
  return cols.map((c) => {
    const pii = c.pii === 'L2' || c.pii === 'L3'
    const head = `${hl(c.name, kw)} ${esc(c.type || '')}`.trimEnd()
    const tail = c.comment ? ` <span class="cc">COMMENT <b>'${hl(c.comment, kw)}'</b></span>` : ''
    return `<span class="${pii ? 'cc-pii' : ''}">${head}${tail}</span>`
  }).join(' <span class="dot">·</span> ')
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetCardList.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/data-source/asset/assetText.ts frontend/src/views/data-source/asset/__tests__/AssetCardList.spec.ts
git commit -m "feat(ui): 新增 renderColumnDigest 逐列摘要纯函数（AF-05）"
```

---

### Task 3: `isCjkQuery` 纯函数

**Files:**
- Modify: `frontend/src/views/data-source/asset/assetSearch.ts`
- Test: `frontend/src/views/data-source/asset/__tests__/AssetSearchBar.spec.ts`

**Interfaces:**
- Produces: `isCjkQuery(kw: string): boolean`。

- [ ] **Step 1: 写失败测试**

在 `AssetSearchBar.spec.ts` 追加（import 补 `isCjkQuery`）：

```typescript
import { isCjkQuery } from '../assetSearch'

describe('isCjkQuery（AF-02 检索降级判定）', () => {
  it('含 CJK true；ASCII/空 false', () => {
    expect(isCjkQuery('订单表')).toBe(true)
    expect(isCjkQuery('sales_order')).toBe(false)
    expect(isCjkQuery('')).toBe(false)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetSearchBar.spec.ts`
Expected: FAIL —`isCjkQuery` undefined

- [ ] **Step 3: 实现**

`assetSearch.ts` 末尾追加：

```typescript
/** 关键词是否含 CJK（原型口径：命中则走 LIKE+trgm，非 similarity，前端显「检索降级」徽标） */
export function isCjkQuery(kw: string): boolean {
  return /[\u4e00-\u9fa5]/.test(kw || '')
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetSearchBar.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/data-source/asset/assetSearch.ts frontend/src/views/data-source/asset/__tests__/AssetSearchBar.spec.ts
git commit -m "feat(ui): 新增 isCjkQuery 检索降级判定纯函数（AF-02）"
```

---

### Task 4: 树分组徽标 + 计数字段 + 组件渲染

**Files:**
- Modify: `frontend/src/views/data-source/asset/assetTree.ts`
- Modify: `frontend/src/views/data-source/asset/AssetTypeTree.vue`
- Test: `frontend/src/views/data-source/asset/__tests__/AssetTypeTree.spec.ts`

**Interfaces:**
- Produces: `groupBadge(code: string): string`；`AssetTreeNode` 增 `label: string`、`count: number | null`、`badge?: string`（`title`/`dotClass`/`empty` 保留）。

- [ ] **Step 1: 写失败测试**

`AssetTypeTree.spec.ts` 顶部 import 补 `groupBadge`，追加：

```typescript
import { buildAssetTree, groupBadge } from '../assetTree'

describe('groupBadge + 树节点字段（AF-01 视觉）', () => {
  it('9 组映射 + 未知码回落前两位大写', () => {
    expect(groupBadge('rdbms')).toBe('RL')
    expect(groupBadge('warehouse')).toBe('WH')
    expect(groupBadge('saas')).toBe('AP')
    expect(groupBadge('foo')).toBe('FO')
  })
  it('组节点带 badge/label/count，源节点带 count 药丸值', () => {
    const tree = buildAssetTree(GROUPS, id)
    const wh = tree[0].children!.find((g) => g.key === 'type:warehouse')!
    expect(wh.badge).toBe('WH')
    expect(wh.label).toBe('数仓 / 大数据')
    expect(wh.count).toBe(3)
    expect(wh.children![0].count).toBe(3)
    expect(wh.children![0].label).toBe('CH 集群')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetTypeTree.spec.ts`
Expected: FAIL —`groupBadge` undefined；`badge`/`label`/`count` undefined

- [ ] **Step 3: 实现（`assetTree.ts`）**

接口增字段并加 `BADGES`/`groupBadge`，`buildAssetTree` 填 label/count/badge：

```typescript
export interface AssetTreeNode {
  key: string
  title: string
  label?: string
  count?: number | null
  badge?: string
  selectable: boolean
  disabled?: boolean
  isLeaf?: boolean
  children?: AssetTreeNode[]
  status?: string
  dotClass?: string
  empty?: boolean
}

const BADGES: Record<string, string> = {
  rdbms: 'RL', tsdb: 'TS', warehouse: 'WH', graph: 'GR', kv: 'KV',
  vector: 'VC', search: 'SE', file: 'FS', saas: 'AP',
}

export function groupBadge(code: string): string {
  return BADGES[code] || (code || '').slice(0, 2).toUpperCase()
}
```

组节点 map 内：source 子节点对象加 `label: c.label, count: c.count ?? null`；group 对象加 `label: g.label, count: g.count ?? 0, badge: groupBadge(g.code)`（`title` 维持原 `${g.label}（${g.count ?? 0}）`）。

- [ ] **Step 4: 实现（`AssetTypeTree.vue`）** 标题模板与样式

```vue
<template #title="node">
  <span v-if="node.badge" class="tg-h">
    <span class="ic">{{ node.badge }}</span>
    <span class="nm">{{ node.label ?? node.title }}</span>
    <span class="ct">{{ node.count ?? 0 }}</span>
  </span>
  <span v-else-if="node.dotClass !== undefined" class="tn">
    <span :class="['dotk', node.dotClass]" />
    <span class="nm">{{ node.label ?? node.title }}</span>
    <span v-if="node.count != null" class="cnt">{{ node.count }}</span>
  </span>
  <span v-else>{{ node.title }}</span>
</template>
```

`<style scoped>` 追加（复制原型口径）：

```less
.tg-h { display: inline-flex; align-items: center; gap: 7px; }
.tg-h .ic { width: 17px; height: 17px; border-radius: 4px; background: #e8edf5; color: #646a73;
  display: inline-flex; align-items: center; justify-content: center; font-size: 9.5px; font-family: var(--mono, monospace); }
.tg-h .ct, .tn .cnt { font-size: 10px; background: #eceff4; color: #646a73; border-radius: 9px;
  padding: 0 6px; font-family: var(--mono, monospace); }
.tg-h .nm { font-weight: 600; }
```

- [ ] **Step 5: 跑测试确认通过**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetTypeTree.spec.ts && npx vue-tsc --noEmit`
Expected: PASS；`AssetTypeTree.vue`/`assetTree.ts` 无类型错误

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/data-source/asset/assetTree.ts frontend/src/views/data-source/asset/AssetTypeTree.vue frontend/src/views/data-source/asset/__tests__/AssetTypeTree.spec.ts
git commit -m "feat(ui): 资产树补分组字母徽标与计数药丸（AF-01）"
```

---

### Task 5: `buildSendPreviewPayload` + `formatPayloadJson`

**Files:**
- Modify: `frontend/src/views/data-source/asset/assetSend.ts`
- Test: `frontend/src/views/data-source/asset/__tests__/AssetPickerSend.spec.ts`

**Interfaces:**
- Produces: `buildSendPreviewPayload(selected: SendItem[]): SendBody`；`SendItem = { table_id:number; source_id:number; table_name:string; db_name?:string; database?:string }`；`SendBody = { mode:'tables'; source_id:number|null; db_name?:string; database?:string; tables:string[]; tag_ids:number[]; catalog_ids:number[]; origin:'asset_picker' }`；`formatPayloadJson(o: unknown): string`（着色 HTML）。

- [ ] **Step 1: 写失败测试**

`AssetPickerSend.spec.ts` import 补两函数，追加：

```typescript
import { buildSendPreviewPayload, formatPayloadJson } from '../assetSend'

describe('buildSendPreviewPayload / formatPayloadJson（AF-08 dock）', () => {
  it('同源取首项 source/db，tables 为全表名', () => {
    const p = buildSendPreviewPayload([
      { table_id: 1, source_id: 5, table_name: 'b_tab', db_name: 'd1' },
      { table_id: 2, source_id: 5, table_name: 'a_tab', db_name: 'd1' },
    ])
    expect(p.source_id).toBe(5)
    expect(p.db_name).toBe('d1')
    expect(p.tables).toEqual(['b_tab', 'a_tab'])
    expect(p.mode).toBe('tables')
    expect(p.origin).toBe('asset_picker')
  })
  it('空选择 → tables:[] 且 source_id:null', () => {
    const p = buildSendPreviewPayload([])
    expect(p.tables).toEqual([])
    expect(p.source_id).toBeNull()
  })
  it('formatPayloadJson 输出着色 key span', () => {
    const html = formatPayloadJson({ tables: ['x'] })
    expect(html).toContain('class="k"')
    expect(html).toContain('tables')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetPickerSend.spec.ts`
Expected: FAIL —两函数 undefined

- [ ] **Step 3: 实现**

`assetSend.ts` 末尾追加：

```typescript
export interface SendItem { table_id: number; source_id: number; table_name: string; db_name?: string; database?: string }
export interface SendBody {
  mode: 'tables'; source_id: number | null; db_name?: string; database?: string
  tables: string[]; tag_ids: number[]; catalog_ids: number[]; origin: 'asset_picker'
}

/** 送数请求体（dock 预览与 doSend 共用，保证所见即所发）：source/db 取首个勾选项 */
export function buildSendPreviewPayload(selected: SendItem[]): SendBody {
  const first = selected[0]
  return {
    mode: 'tables',
    source_id: first?.source_id ?? null,
    db_name: first?.db_name,
    database: first?.database,
    tables: selected.map((s) => s.table_name),
    tag_ids: [],
    catalog_ids: [],
    origin: 'asset_picker',
  }
}

/** 请求体 JSON 着色（移植原型 jsonColor，含转义防注入），供 dock `v-html` */
export function formatPayloadJson(o: unknown): string {
  const e = (s: string) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string))
  return e(JSON.stringify(o, null, 2))
    .replace(/&quot;([^&]+?)&quot;(\s*:)/g, '<span class="k">"$1"</span>$2')
    .replace(/:\s&quot;(.*?)&quot;/g, ': <span class="s">"$1"</span>')
    .replace(/:\s(\d+)/g, ': <span class="n">$1</span>')
    .replace(/:\s(true|false|null)/g, ': <span class="b">$1</span>')
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetPickerSend.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/data-source/asset/assetSend.ts frontend/src/views/data-source/asset/__tests__/AssetPickerSend.spec.ts
git commit -m "feat(ui): 抽送数请求体构造与 JSON 着色纯函数（AF-08 dock）"
```

---

### Task 6: 卡片消费结构化列 + chip 筛选 + 分页增强

**Files:**
- Modify: `frontend/src/views/data-source/asset/AssetCardList.vue`
- Test: `frontend/src/views/data-source/asset/__tests__/AssetCardList.spec.ts`

**Interfaces:**
- Consumes: `renderColumnDigest`（Task 2）；`items[].columns`（Task 1）。
- Produces: 新 emit `filter-tag(tagId:number)`；pager 增 `show-quick-jumper` + 富化总数。

- [ ] **Step 1: 写失败测试**

`AssetCardList.spec.ts`：`ITEMS` 里第 1 项补 `columns: [{ name: 'id_card', type: 'VARCHAR', comment: '身份证号', pii: 'L3' }]`，新增断言：

```typescript
  it('结构化列摘要：PII 标红 + 高亮', async () => {
    const html = await render()
    expect(html).toContain('cc-pii')
    expect(html).toContain('COMMENT')
  })
  it('标签 chip 渲染（可点筛选数据就绪）', async () => {
    const html = await render({
      items: [{ ...ITEMS[0], tags: [{ id: 9, code: 'core', name: '核心表', color: '#3371fc' }] }],
    })
    expect(html).toContain('核心表')
  })
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetCardList.spec.ts`
Expected: FAIL —摘要仍显 `column_digest`，无 `cc-pii`

- [ ] **Step 3: 实现摘要 + chip**

`<script setup>` 改 import：`import { hl, fmtRows, renderColumnDigest } from './assetText'`。`emits` 增 `(e: 'filter-tag', tagId: number): void`。新增：

```typescript
function digestHtml(it: any): string {
  return renderColumnDigest(it.columns || [], props.kw || '')
}
```

摘要 div 内容体改为：

```vue
<div class="asset-cards__digest" :class="{ exp: isExp(it.table_id) }" :title="it.column_digest" @click="toggleExp(it.table_id)">
  <span v-if="it.columns && it.columns.length" v-html="digestHtml(it)" />
  <template v-else>{{ it.column_digest || t2('（无字段摘要）') }}</template>
</div>
```

foot 标签由只读改可点：

```vue
<a-tag v-for="tg in it.tags || []" :key="tg.id" :color="tg.color || undefined"
  style="cursor: pointer" @click="emit('filter-tag', tg.id)">{{ tg.name }}</a-tag>
```

`<style scoped>` 追加：

```less
.asset-cards__digest { :deep(.cc-pii) { color: #cf1322; } :deep(.cc) { color: #8a6d3b; } :deep(.dot) { opacity: .4; } }
```

- [ ] **Step 4: 实现分页（AF-07）**

`a-pagination` 改为：

```vue
<a-pagination
  :current="page"
  :page-size="size"
  :total="total"
  size="small"
  show-quick-jumper
  :show-total="(n: number) => `${t2('共')} ${n} ${t2('条')} / ${Math.ceil(total / size) || 1} ${t2('页')} · size ${size}`"
  @change="(p: number) => emit('page-change', p)"
/>
```

- [ ] **Step 5: 跑测试确认通过**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetCardList.spec.ts`
Expected: PASS（新断言 + 原 5 断言全绿）

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/data-source/asset/AssetCardList.vue frontend/src/views/data-source/asset/__tests__/AssetCardList.spec.ts
git commit -m "feat(ui): 卡片逐列摘要+标签chip筛选+分页前往页（AF-03/05/07）"
```

---

### Task 7: 检索条降级徽标 + `setTagFilter`

**Files:**
- Modify: `frontend/src/views/data-source/asset/AssetSearchBar.vue`

**Interfaces:**
- Consumes: `isCjkQuery`（Task 3）。
- Produces: `defineExpose` 增 `setTagFilter(tagId:number)`（供卡片 chip 驱动筛选）。

- [ ] **Step 1: 加降级徽标**

`<script setup>` import 补 `isCjkQuery`：`import { COLORS, TAG_KINDS, buildSearchPayload, buildTagPayload, isCjkQuery } from './assetSearch'`。模板在「新建标签」按钮后加：

```vue
<a-tag v-if="isCjkQuery(kw)" color="orange" :title="t2('走 LIKE + gin_trgm_ops，未用 similarity()')">{{ t2('检索降级') }}</a-tag>
```

- [ ] **Step 2: 加 `setTagFilter`**

`defineExpose({ reloadTags: loadTags, setTagFilter })`，并在 script 内新增：

```typescript
/** 卡片标签 chip → 锁定单标签筛选并即时重查 */
function setTagFilter(tagId: number) {
  tagIds.value = [tagId]
  emitSearch()
}
```

- [ ] **Step 3: 校验**

Run: `npx vue-tsc --noEmit`
Expected: `AssetSearchBar.vue` 无类型错误（现有 `AssetSearchBar.spec.ts` 初始 kw 为空 → 不显徽标，无回归）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/data-source/asset/AssetSearchBar.vue
git commit -m "feat(ui): 检索条 CJK 降级徽标 + setTagFilter 暴露（AF-02/03）"
```

---

### Task 8: 新组件 `AssetSendDock.vue`

**Files:**
- Create: `frontend/src/views/data-source/asset/AssetSendDock.vue`
- Test: `frontend/src/views/data-source/asset/__tests__/AssetSendDock.spec.ts`

**Interfaces:**
- Consumes: `buildSendPreviewPayload`、`formatPayloadJson`（Task 5）。
- Produces: props `{ selected: any[]; ontologies: any[]; targetId: number|null; loadingOnt?: boolean }`；emit `update:targetId`。渲染目标下拉（状态标签 + `v{current_version}`，`stopped` 禁用）+ 实时 JSON + 得分规则 + 关键约束。

- [ ] **Step 1: 写失败测试**

新建 `AssetSendDock.spec.ts`：

```typescript
import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import Antd from 'ant-design-vue'
vi.mock('@/views/data-source/ontology/ontologyText', () => ({ t2: (s: string) => s }))
import AssetSendDock from '../AssetSendDock.vue'

const ONTS = [
  { id: 1, code: 'sales_ontology', name: '销售域本体', status: 'published', current_version: 3 },
  { id: 2, code: 'crm_ontology', name: '客户域本体', status: 'stopped', current_version: 1 },
]

async function render(props: Record<string, unknown>) {
  const app = createSSRApp(AssetSendDock, { selected: [], ontologies: ONTS, targetId: null, ...props })
  app.use(Antd)
  return await renderToString(app)
}

describe('AssetSendDock（AF-08）', () => {
  it('渲染标题/得分规则/关键约束', async () => {
    const html = await render({})
    expect(html).toContain('送数预览')
    expect(html).toContain('相关度得分规则')
    expect(html).toContain('关键约束')
  })
  it('勾选后预览含 tables 与 source_id 着色 JSON', async () => {
    const html = await render({ selected: [{ table_id: 1, source_id: 5, table_name: 'sales_order', db_name: 'sales' }] })
    expect(html).toContain('sales_order')
    expect(html).toContain('class="k"')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetSendDock.spec.ts`
Expected: FAIL —模块不存在

- [ ] **Step 3: 实现组件**

新建 `AssetSendDock.vue`：

```vue
<template>
  <div class="ont-dock">
    <div class="ont-dock__h">
      <h3>{{ t2('送数预览') }} <span class="ont-dock__badge">{{ t2('契约实时对齐 §6.5') }}</span></h3>
      <p>{{ t2('点击「送入本体建模」时发出的请求体，与后端 PUT /ontologies/{id}/draft-scope 同构') }}</p>
    </div>
    <div class="ont-dock__b">
      <div class="ont-dock__sec">
        <h4>{{ t2('目标本体') }}</h4>
        <a-select
          :value="targetId"
          style="width: 100%"
          :loading="loadingOnt"
          :placeholder="t2('选择目标本体')"
          show-search option-filter-prop="label"
          @update:value="(v: number) => emit('update:targetId', v)"
        >
          <a-select-option v-for="o in ontologies" :key="o.id" :value="o.id" :disabled="o.status === 'stopped'"
            :label="`${o.name} (${o.code})`">
            <span>{{ o.name }}</span>
            <a-tag :color="statusColor(o.status)" style="margin-left: 8px">{{ o.status }}</a-tag>
            <span class="ont-dock__ver">v{{ o.current_version }}</span>
            <a-tag v-if="o.status === 'stopped'" color="orange" style="margin-left: 6px">{{ t2('已停止') }}</a-tag>
          </a-select-option>
        </a-select>
      </div>
      <div class="ont-dock__sec">
        <h4>PUT /ontologies/{id}/draft-scope</h4>
        <pre class="ont-dock__json" v-html="jsonHtml" />
      </div>
      <div class="ont-dock__sec">
        <h4>{{ t2('相关度得分规则') }}</h4>
        <div class="ont-dock__rule">
          <ul>
            <li><span class="score s3">3</span> {{ t2('命中表名 / 库名 / 表注释') }}</li>
            <li><span class="score s2">2</span> {{ t2('命中字段名') }}</li>
            <li><span class="score s1">1</span> {{ t2('仅命中字段注释') }}</li>
          </ul>
        </div>
      </div>
      <div class="ont-dock__sec">
        <h4>{{ t2('关键约束') }}</h4>
        <div class="ont-dock__rule">
          <ul>
            <li>{{ t2('送数不写任何结构表，只覆盖 draft_scope_json') }}</li>
            <li>{{ t2('跨源勾选即时拦截 BUILD_SCOPE_SINGLE_SOURCE') }}</li>
            <li>{{ t2('空清单送数拒绝 DRAFT_SCOPE_EMPTY') }}</li>
            <li>{{ t2('清单强制 page/size（默认 50，上限 200）') }}</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 送数预览 dock（AF-08，右侧契约面板）：目标本体选择 + 实时请求体 JSON + 得分规则 + 关键约束。
 * 预览与 `doSend` 共用 :func:`buildSendPreviewPayload`，保证所见即所发；纯展示，无网络。
 */
import { computed } from 'vue'
import { t2 } from '../ontology/ontologyText'
import { buildSendPreviewPayload, formatPayloadJson } from './assetSend'

const props = defineProps<{
  selected: any[]
  ontologies: any[]
  targetId: number | null
  loadingOnt?: boolean
}>()
const emit = defineEmits<{ (e: 'update:targetId', v: number): void }>()

const jsonHtml = computed(() => formatPayloadJson(buildSendPreviewPayload(props.selected)))

function statusColor(s: string) {
  return ({ published: 'green', draft: 'blue', archived: 'default', stopped: 'orange' } as Record<string, string>)[s] || 'default'
}
</script>

<style lang="less" scoped>
.ont-dock {
  border-left: 1px solid var(--border);
  background: var(--bg-soft, #f7f9fc);
  display: flex; flex-direction: column; overflow: hidden;
  &__h { padding: 12px 15px 9px; border-bottom: 1px solid var(--border);
    h3 { font-size: 12.5px; font-weight: 600; } p { font-size: 11px; color: #8f959e; margin-top: 3px; } }
  &__badge { font-size: 10px; color: #722ed1; background: #f9f0ff; border: 1px solid #efdbff; border-radius: 10px; padding: 0 7px; margin-left: 6px; }
  &__b { flex: 1; overflow: auto; padding: 13px 15px 22px; }
  &__sec { margin-bottom: 15px; h4 { font-size: 10.5px; letter-spacing: .7px; color: #8f959e; margin-bottom: 7px; } }
  &__ver { margin-left: 8px; color: #999; font-size: 12px; }
  &__json { background: #161b22; color: #c9d1d9; border-radius: 6px; padding: 10px 12px;
    font-family: var(--mono, monospace); font-size: 11px; line-height: 1.7; overflow: auto; max-height: 250px;
    white-space: pre-wrap; word-break: break-word;
    :deep(.k) { color: #79c0ff; } :deep(.s) { color: #a5d6ff; } :deep(.n) { color: #f0883e; } :deep(.b) { color: #ff7b72; } }
  &__rule ul { margin: 0; padding-left: 15px; font-size: 11px; color: #646a73; li { margin-bottom: 2px; } }
}
.score { font-family: var(--mono, monospace); font-size: 9.5px; border: 1px solid #d0d5dd; border-radius: 3px; padding: 0 4px;
  &.s3 { background: #f6ffed; border-color: #b7eb8f; color: #389e0d; } &.s2 { background: #f0f6ff; border-color: #bcd8ff; color: #3371fc; } &.s1 { background: #fffbe6; border-color: #ffe58f; color: #874d00; } }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run src/views/data-source/asset/__tests__/AssetSendDock.spec.ts && npx vue-tsc --noEmit`
Expected: PASS（2 用例）；组件无类型错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/data-source/asset/AssetSendDock.vue frontend/src/views/data-source/asset/__tests__/AssetSendDock.spec.ts
git commit -m "feat(ui): 新增送数预览 dock（目标选择+实时契约JSON+规则）（AF-08）"
```

---

### Task 9: 本体工作台跳转纯函数

**Files:**
- Create: `frontend/src/views/data-source/ontology/ontologyNav.ts`
- Test: `frontend/src/views/data-source/ontology/__tests__/OntologyNav.spec.ts`

**Interfaces:**
- Produces: `parseWorkspaceQuery(q: Record<string, string | string[] | undefined>): { id: number | null; tab: string | null }`；`VALID_TABS` 常量。

- [ ] **Step 1: 写失败测试**

新建 spec：

```typescript
import { describe, it, expect } from 'vitest'
import { parseWorkspaceQuery } from '../ontologyNav'

describe('parseWorkspaceQuery（AF-08 送数后跳转）', () => {
  it('ontology 数字→id；ot 命中合法 tab→tab', () => {
    expect(parseWorkspaceQuery({ ontology: '7', ot: 'build' })).toEqual({ id: 7, tab: 'build' })
  })
  it('非法 tab 忽略；缺省 null', () => {
    expect(parseWorkspaceQuery({ ontology: 'x', ot: 'bogus' })).toEqual({ id: null, tab: null })
    expect(parseWorkspaceQuery({})).toEqual({ id: null, tab: null })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/views/data-source/ontology/__tests__/OntologyNav.spec.ts`
Expected: FAIL —模块不存在

- [ ] **Step 3: 实现**

新建 `ontologyNav.ts`：

```typescript
/** 本体工作台路由查询解析（送数跳转后预选本体 + 切页签）：纯函数，无 Vue 依赖。 */
export const VALID_TABS = ['overview', 'build', 'review', 'graph', 'inspector', 'version', 'publish']

export function parseWorkspaceQuery(q: Record<string, string | string[] | undefined>): { id: number | null; tab: string | null } {
  const rawOnt = Array.isArray(q.ontology) ? q.ontology[0] : q.ontology
  const rawTab = Array.isArray(q.ot) ? q.ot[0] : q.ot
  const id = rawOnt != null && /^\d+$/.test(rawOnt) ? Number(rawOnt) : null
  const tab = rawTab && VALID_TABS.includes(rawTab) ? rawTab : null
  return { id, tab }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run src/views/data-source/ontology/__tests__/OntologyNav.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/data-source/ontology/ontologyNav.ts frontend/src/views/data-source/ontology/__tests__/OntologyNav.spec.ts
git commit -m "feat(ui): 抽本体工作台跳转查询解析纯函数（AF-08）"
```

---

### Task 10: `AssetPickerPanel` 三栏集成 + 送数共用 + 跳转 + chip 筛选

**Files:**
- Modify: `frontend/src/views/data-source/asset/AssetPickerPanel.vue`

**Interfaces:**
- Consumes: `AssetSendDock`（T8）、`buildSendPreviewPayload`（T5）、卡片 `filter-tag`（T6）、`setTagFilter`（T7）。

- [ ] **Step 1: 模板改三栏 + dock**

`asset-picker__body` 内 main 之后插入 dock，目标选择从 send bar 移入 dock：

```vue
      <div class="asset-picker__dock">
        <AssetSendDock :selected="selected" :ontologies="ontologies" :loading-ont="loadingOnt"
          v-model:target-id="targetId" />
      </div>
```

`<AssetSearchBar ref="searchBarRef" ... @search="onSearch" />`（补 ref）。`<AssetCardList>` 事件补 `@filter-tag="onFilterTag"`。send bar 删除原目标 `a-select`（保留 计数/打标签/批量探活/重新分级/送入/清空）。

`<style>` 内 `&__body` 与 `&__main` 间加：

```less
  &__dock { width: 372px; border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
  @media (max-width: 1420px) { &__dock { display: none; } }
```

- [ ] **Step 2: script 接线**

import 补 `AssetSendDock`、`buildSendPreviewPayload`、`useRouter`；新增 `const router = useRouter()`、`const searchBarRef = ref<any>(null)`、`const ontologies = ref<any[]>([])` 已有则复用（dock 用同一 `ontologies`）。`ontOptions` 可删（选择移入 dock）。doSend 体改用共用构造并跳转：

```typescript
function onFilterTag(tagId: number) {
  searchBarRef.value?.setTagFilter?.(tagId)
}

async function doSend() {
  if (!targetId.value || !selected.value.length) return
  const body = buildSendPreviewPayload(selected.value)
  sending.value = true
  try {
    await putDraftScope(targetId.value, body as Record<string, any>)
    message.success(t2('已送入本体建模作用域（未写结构表）'))
    selected.value = []
    router.push({ path: '/admin', query: { tab: 'kg-ontology', ontology: String(targetId.value), ot: 'build' } })
  } catch {
    /* ONTOLOGY_STOPPED / DRAFT_SCOPE_EMPTY 已由拦截器按 code 提示 */
  } finally {
    sending.value = false
  }
}
```

> `loadOntologies()` 维持填充 `ontologies.value`（dock 读取），不再需要 `ontOptions` computed。

- [ ] **Step 3: 校验**

Run: `npx vue-tsc --noEmit && npx vitest run src/views/data-source/asset`
Expected: `AssetPickerPanel.vue` 无类型错误；`src/views/data-source/asset` 全绿

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/data-source/asset/AssetPickerPanel.vue
git commit -m "feat(ui): 资产面板三栏集成送数dock+共用载荷+跳转+chip筛选（AF-08）"
```

---

### Task 11: `OntologyWorkspace` 读 query 预选

**Files:**
- Modify: `frontend/src/views/data-source/ontology/OntologyWorkspace.vue:82-175`

**Interfaces:**
- Consumes: `parseWorkspaceQuery`（T9）。

- [ ] **Step 1: 接线**

import 补 `import { useRoute } from 'vue-router'`、`import { parseWorkspaceQuery } from './ontologyNav'`；`const route = useRoute()`。`loadList` 成功后应用跳转预选——把 `onMounted` 改为：

```typescript
onMounted(async () => {
  await loadList(true)
  const nav = parseWorkspaceQuery(route.query as Record<string, string | string[] | undefined>)
  if (nav.id != null && ontologies.value.some((o) => o.id === nav.id)) currentId.value = nav.id
  if (nav.tab) tab.value = nav.tab
})
```

- [ ] **Step 2: 校验**

Run: `npx vue-tsc --noEmit`
Expected: `OntologyWorkspace.vue` 无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/data-source/ontology/OntologyWorkspace.vue
git commit -m "feat(ui): 本体工作台读 query 预选本体并切构建页签（AF-08）"
```

---

### Task 12: i18n 补 dock/降级短语（en/ja）

**Files:**
- Modify: `frontend/src/i18n/ontologyLocale.ts`（`UI_EN` 46-67 段、`UI_JA` 141+ 段）
- Test: `frontend/src/i18n/__tests__/parityLocale.spec.ts`

**Interfaces:**
- Consumes: `translateOntology`（既有）。

- [ ] **Step 1: 写失败测试**

新建 spec：

```typescript
import { describe, it, expect } from 'vitest'
import { translateOntology } from '../ontologyLocale'

describe('全视觉对齐新短语（AF-08 dock）', () => {
  it('送数预览 en', () => {
    expect(translateOntology('送数预览', 'en-US')).toBe('Send preview')
  })
  it('检索降级 en/ja 有译文', () => {
    expect(translateOntology('检索降级', 'en-US')).toBe('Degrade search')
    expect(translateOntology('检索降级', 'ja-JP')).toBe('検索フォールバック')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/i18n/__tests__/parityLocale.spec.ts`
Expected: FAIL —回落原文（en 返 '送数预览'）

- [ ] **Step 3: 补 `UI_EN`**

在 `UI_EN`（`'（无字段摘要）'` 行附近）追加：

```typescript
  '送数预览': 'Send preview',
  '契约实时对齐 §6.5': 'Contract live-aligned §6.5',
  '目标本体': 'Target ontology',
  '相关度得分规则': 'Relevance score rules',
  '关键约束': 'Key constraints',
  '检索降级': 'Degrade search',
  '走 LIKE + gin_trgm_ops，未用 similarity()': "Uses LIKE + gin_trgm_ops; no similarity()",
  '已停止': 'Stopped',
  '页': 'page',
  '前往': 'Go to',
```

- [ ] **Step 4: 补 `UI_JA`**

在 `UI_JA`（`'资产送数'` 行附近）追加：

```typescript
  '送数预览': 'スコープ送信プレビュー',
  '契约实时对齐 §6.5': '契約リアルタイム整合 §6.5',
  '目标本体': '対象オントロジー',
  '相关度得分规则': '関連度スコアルール',
  '关键约束': '主要制約',
  '检索降级': '検索フォールバック',
  '已停止': '停止中',
  '页': 'ページ',
```

- [ ] **Step 5: 跑测试确认通过**

Run: `npx vitest run src/i18n/__tests__/parityLocale.spec.ts`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/i18n/ontologyLocale.ts frontend/src/i18n/__tests__/parityLocale.spec.ts
git commit -m "i18n(ui): 补送数dock与检索降级短语 en/ja"
```

---

### Task 13: 全链路回归 + 原型页脚同步

**Files:**
- Modify: `docs/prototypes/ontology-asset-catalog-preview.html`（页脚实现状态注记）

- [ ] **Step 1: 后端全量回归**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/ontology tests/dataops -q`（工作目录 `backend/`）
Expected: ≥ 一期基线（172 passed/10 skipped）且不回退

- [ ] **Step 2: 前端全量回归**

Run: `npx vitest run src/views/data-source src/i18n`（工作目录 `frontend/`）
Expected: 全绿（含新增 dock/nav/parity 用例）

- [ ] **Step 3: 类型检查触及文件**

Run: `npx vue-tsc --noEmit`，过滤本次触及文件
Expected: 触及文件零错误（既有基线错误在无关文件，非本次范围）

- [ ] **Step 4: 原型页脚注记**

`ontology-asset-catalog-preview.html` 页脚 `.tree-f` 内「Q1 裁决 B：物化列（见 spec §1.1）」后补一行：

```html
<br>已对齐实现：AF-01~08 全视觉奇偶（含送数 dock）
```

- [ ] **Step 5: 提交**

```bash
git add docs/prototypes/ontology-asset-catalog-preview.html
git commit -m "docs(proto): 标注资产目录已对齐全视觉奇偶实现"
```

---

## 手工冒烟（回归外，交付前人工确认）

- 浏览器打开 `/admin/data-asset`：树分组字母徽标 + 计数药丸 + 状态点；搜索中文 → 「检索降级」徽标出现；卡片摘要逐列着色 + 高亮；点标签 chip → 列表按该标签重查；分页「前往 N 页」；勾选跨源被拦截；右侧 dock 目标下拉显状态且「已停止」禁用、JSON 随勾选实时更新；送入后跳本体工作台并落在「构建」页签。
