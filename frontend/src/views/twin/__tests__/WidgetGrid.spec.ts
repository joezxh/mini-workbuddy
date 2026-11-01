import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import WidgetGrid from '../WidgetGrid.vue'
import type { TwinWidget, WidgetDatum } from '@/types/twin'

const mkWidget = (id: number, over = {}): TwinWidget => ({
  id, page_id: 1, widget_key: `w${id}`, title: `标题${id}`, query_id: 1,
  param_values_json: {}, display_json: {}, grid_json: { x: 1, y: id, w: 3, h: 2 },
  refresh_json: null, sort_order: id, updated_at: null, ...over,
})
const mkDatum = (id: number, over = {}): WidgetDatum => ({
  widget_id: id, widget_key: `w${id}`, title: `标题${id}`, query_id: 1,
  state: 'ok', reason: null, result_shape: 'kpi', columns: ['v'],
  data: { value: 42, records: [{ v: 42 }] }, row_count: 1, truncated: false,
  masked_fields: [], error: null, cached: false, updated_at: 'x', ...over,
})

async function render(w: TwinWidget[], d: Record<number, WidgetDatum>, mode: 'edit' | 'run') {
  return await renderToString(createSSRApp(WidgetGrid, { widgets: w, pageData: d, mode }))
}

describe('WidgetGrid / WidgetShell（W3/W6/承重）', () => {
  it('run 态不渲染任何把手（.wops 缺失 = 模式差异唯一实现）', async () => {
    const html = await render([mkWidget(1)], { 1: mkDatum(1) }, 'run')
    expect(html).not.toContain('wops')
    expect(html).toContain('标题1')
  })
  it('edit 态渲染把手', async () => {
    const html = await render([mkWidget(1)], { 1: mkDatum(1) }, 'edit')
    expect(html).toContain('wops')
  })
  it('kpi 出数值；masked 出现 🔒 且绝不出现空态文案', async () => {
    const html = await render([mkWidget(1)], { 1: mkDatum(1) }, 'run')
    expect(html).toContain('42')
    const m = await render([mkWidget(1)],
      { 1: mkDatum(1, { state: 'masked', data: { value: 1380000, records: [] }, masked_fields: ['v'] }) }, 'run')
    expect(m).toContain('🔒')
    expect(m).not.toContain('暂无数据')
  })
  it('error 态回显 code: message（W6）', async () => {
    const html = await render([mkWidget(1)],
      { 1: mkDatum(1, { state: 'error', error: { code: 'TWIN_DATA_TIMEOUT', message: '取数超时（>5s）' } }) }, 'run')
    expect(html).toContain('TWIN_DATA_TIMEOUT')
    expect(html).toContain('取数超时')
  })
  it('empty+unbound 编辑态含绑定 CTA', async () => {
    const html = await render([mkWidget(1)], { 1: mkDatum(1, { state: 'empty', reason: 'unbound' }) }, 'edit')
    expect(html).toContain('未绑定查询，点击绑定')
  })
})
