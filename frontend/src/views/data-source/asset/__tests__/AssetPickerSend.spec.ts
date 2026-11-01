import { describe, it, expect } from 'vitest'
import {
  BUILD_SCOPE_SINGLE_SOURCE,
  CROSS_SOURCE_BLOCK_MSG,
  restoreSelection,
  staleNotice,
  buildSendPreviewPayload,
  formatPayloadJson,
} from '../assetSend'

/**
 * 送数回显闭环（AF-08，纯函数，无网络/无 i18n 依赖）。
 * 覆盖：draft_scope 回显勾选（同源命中、异源丢弃）、失效剔除提示、跨源拦截文案带错误码。
 */
const ITEMS = [
  { table_id: 1, table_name: 'a', source_id: 12 },
  { table_id: 2, table_name: 'b', source_id: 12 },
  { table_id: 3, table_name: 'c', source_id: 12 },
  { table_id: 9, table_name: 'a', source_id: 99 }, // 同名但异源
]

describe('restoreSelection（送数回显恢复勾选）', () => {
  it('draft_scope 命中当前页 a/b → 仅恢复 a/b，未命中 c 不勾', () => {
    const sel = restoreSelection({ mode: 'tables', source_id: 12, tables: ['a', 'b'] }, ITEMS)
    expect(sel.map((s) => s.table_name)).toEqual(['a', 'b'])
  })

  it('异源命中项丢弃（锁定 source_id 才恢复）', () => {
    const sel = restoreSelection({ source_id: 99, tables: ['a'] }, ITEMS)
    expect(sel).toEqual([{ table_id: 9, table_name: 'a', source_id: 99 }])
  })

  it('空/缺 source_id 或 tables → 不恢复任何项', () => {
    expect(restoreSelection(null, ITEMS)).toEqual([])
    expect(restoreSelection({ tables: ['a'] }, ITEMS)).toEqual([])
    expect(restoreSelection({ source_id: 12, tables: [] }, ITEMS)).toEqual([])
  })
})

describe('staleNotice（失效剔除提示）', () => {
  it('removed_stale>0 → 文本含"已从作用域剔除"', () => {
    const msg = staleNotice(2)
    expect(msg).not.toBeNull()
    expect(msg).toContain('已从作用域剔除')
    expect(msg).toContain('2')
  })

  it('removed_stale 为 0/缺省 → null（不打扰）', () => {
    expect(staleNotice(0)).toBeNull()
    expect(staleNotice(undefined)).toBeNull()
  })
})

describe('CROSS_SOURCE_BLOCK_MSG（跨源拦截文案）', () => {
  it('文案携带后端错误码 BUILD_SCOPE_SINGLE_SOURCE', () => {
    expect(BUILD_SCOPE_SINGLE_SOURCE).toBe('BUILD_SCOPE_SINGLE_SOURCE')
    expect(CROSS_SOURCE_BLOCK_MSG).toContain(BUILD_SCOPE_SINGLE_SOURCE)
  })
})

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
