import { describe, it, expect } from 'vitest'
import { COLORS, TAG_KINDS, buildTagPayload, buildSearchPayload } from '../assetSearch'

/**
 * 检索条 / 新建标签载荷（AF-02/03，纯函数）。
 * 重点回归 [bug]：旧实现把 tag_kind 硬编码为 'table'（非法），现必须落真实选择值且绝不出现 'table'。
 */
describe('buildTagPayload（tag_kind 修复）', () => {
  it('落真实 tag_kind，不再硬编码 table', () => {
    const p = buildTagPayload({ code: 'pii', name: '敏感', color: '#52c41a', tag_kind: 'security' })
    expect(p).toEqual({ code: 'pii', name: '敏感', color: '#52c41a', tag_kind: 'security' })
  })

  it('非法/缺失 tag_kind 回落 custom（永不为 table）', () => {
    expect(buildTagPayload({ code: 'x', name: 'y', tag_kind: 'table' }).tag_kind).toBe('custom')
    expect(buildTagPayload({ code: 'x', name: 'y' }).tag_kind).toBe('custom')
  })

  it('色板取原型 7 色，第 2 色为 #52c41a；默认色取首个', () => {
    expect(COLORS).toHaveLength(7)
    expect(COLORS[1]).toBe('#52c41a')
    expect(TAG_KINDS).toEqual(['biz', 'security', 'quality', 'custom'])
    expect(buildTagPayload({ code: 'a', name: 'b', color: '' }).color).toBe(COLORS[0])
  })
})

describe('buildSearchPayload（table_type/sort/size 扩展）', () => {
  it('携带 sort/size，关键词 trim，kind 默认 table', () => {
    const p = buildSearchPayload({ kw: '  ord ', sort: 'rows' })
    expect(p).toEqual({ kw: 'ord', tag_ids: [], kind: 'table', table_type: undefined, sort: 'rows', size: 50 })
  })

  it('table_type=all 归一为 undefined（全部对象不下发过滤）', () => {
    expect(buildSearchPayload({ table_type: 'all' }).table_type).toBeUndefined()
    expect(buildSearchPayload({ table_type: 'VIEW' }).table_type).toBe('VIEW')
  })

  it('sort 非法回落 score', () => {
    expect(buildSearchPayload({ sort: 'bogus' }).sort).toBe('score')
  })
})
