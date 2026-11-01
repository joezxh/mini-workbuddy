// stateMap.spec.ts —— 四态→StateWrapper 三态 + masked 独立位
import { describe, it, expect } from 'vitest'
import { widgetState } from '../stateMap'
import type { WidgetDatum, TwinMode } from '@/types/twin'

const base: WidgetDatum = {
  widget_id: 1, widget_key: 'w', title: 't', query_id: 1, state: 'ok', reason: null,
  result_shape: 'kpi', columns: ['v'], data: { value: 1, records: [] }, row_count: 1,
  truncated: false, masked_fields: [], error: null, cached: false, updated_at: 'x',
}
const s = (over: Partial<WidgetDatum>, mode: TwinMode = 'edit') => widgetState({ ...base, ...over }, mode)

describe('widgetState（W6）', () => {
  it('ok → content', () => expect(s({}).branch).toBe('content'))
  it('empty+unbound 编辑态 → 绑定 CTA 文案', () => {
    const v = s({ state: 'empty', reason: 'unbound' })
    expect(v.branch).toBe('empty')
    expect(v.emptyTitle).toContain('未绑定')
  })
  it('empty+unbound 运行态 → 不出现可操作暗示', () => {
    // 计划原稿断言 not.toContain('绑定查询') 会被 run 文案「未绑定查询」子串命中而假红；
    // 契约意图是「无操作暗示」，改钉 CTA 短语「点击绑定」（见计划缺陷 D-08）
    expect(s({ state: 'empty', reason: 'unbound' }, 'run').emptyTitle).not.toContain('点击绑定')
  })
  it('empty+zero_rows → 结果为零文案', () => {
    expect(s({ state: 'empty', reason: 'zero_rows' }).emptyTitle).toContain('为空')
  })
  it('error → code: message 逐字回显（W6 码+人话）且可重试', () => {
    const v = s({ state: 'error', error: { code: 'TWIN_DATA_TIMEOUT', message: '取数超时（>5s）' } })
    expect(v.branch).toBe('error')
    expect(v.errorText).toBe('TWIN_DATA_TIMEOUT: 取数超时（>5s）')
    expect(v.retryable).toBe(true)
  })
  it('masked → branch=content 且 masked=true（数据照常渲染，绝不落 empty/error）', () => {
    const v = s({ state: 'masked', masked_fields: ['phone'] })
    expect(v.branch).toBe('content')
    expect(v.masked).toBe(true)
  })
})
