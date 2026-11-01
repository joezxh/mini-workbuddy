import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import Antd from 'ant-design-vue'

// node 环境下 ontologyText → @/i18n 会在 import 期读 localStorage，测试里直接桩为恒等
vi.mock('@/views/data-source/ontology/ontologyText', () => ({ t2: (s: string) => s }))

import AssetCardList from '../AssetCardList.vue'
import { hl, fmtRows } from '../assetText'

/** 纯函数：高亮与行数格式化（从原型 JS 移植，忠实复刻取整口径） */
describe('assetText 纯函数', () => {
  it('hl：命中处包 <mark>，无命中/空词只转义', () => {
    expect(hl('sales_order', 'order')).toBe('sales_<mark>order</mark>')
    expect(hl('abc', 'zzz')).toBe('abc')
    expect(hl('abc', '')).toBe('abc')
    expect(hl('a<b', 'b')).toBe('a&lt;<mark>b</mark>')
  })

  it('fmtRows：亿/万/取整口径与 null 占位', () => {
    expect(fmtRows(123456789)).toBe('1.2亿')
    expect(fmtRows(1284550)).toBe('128万') // ≥1e6 → 0 位小数
    expect(fmtRows(284300)).toBe('28.4万') // 1e4..1e6 → 1 位小数
    expect(fmtRows(730)).toBe('730')
    expect(fmtRows(null)).toBe('-')
  })
})

const ITEMS = [
  { table_id: 1, source_id: 5, db_name: 'sales', table_name: 'sales_order', table_comment: '销售订单', column_digest: 'x', column_count: 6, row_count: 1284550, pii_max_level: 'L1', bound_object_code: 'obj_order', score: 3, tags: [] },
  { table_id: 2, source_id: 5, db_name: 'sales', table_name: 'crm_customer', table_comment: '客户', column_digest: 'y', column_count: 5, row_count: 284300, pii_max_level: 'L3', bound_object_code: null, score: 2, tags: [] },
]

async function render(extra: Record<string, unknown> = {}) {
  const app = createSSRApp(AssetCardList, {
    items: ITEMS, total: 2, page: 1, size: 50, selected: [], kw: 'order', ...extra,
  })
  app.use(Antd)
  return await renderToString(app)
}

describe('AssetCardList 渲染（AF-05）', () => {
  it('score 徽章 class s3/s2', async () => {
    const html = await render()
    expect(html).toContain('score s3')
    expect(html).toContain('score s2')
  })

  it('已映射回显映射码', async () => {
    const html = await render()
    expect(html).toContain('已映射 obj_order')
  })

  it('PII 分级配色：L1 告警(warn)、L3 错误(err)', async () => {
    const html = await render()
    expect(html).toMatch(/b-warn[^>]*>\s*PII L1/)
    expect(html).toMatch(/b-err[^>]*>\s*PII L3/)
  })

  it('表名关键词高亮 <mark>', async () => {
    const html = await render()
    expect(html).toContain('sales_<mark>order</mark>')
  })

  it('行数格式化', async () => {
    const html = await render()
    expect(html).toContain('128万')
  })
})
