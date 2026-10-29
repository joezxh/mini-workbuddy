import { describe, it, expect } from 'vitest'
import { mergeViaOptions } from '../viaOptions'

describe('mergeViaOptions', () => {
  it('两端属性合并，from 端在前', () => {
    const opts = mergeViaOptions([
      { code: 'obj_order', attributes: [{ standard_id: 11, code: 'customer_id', name: '客户ID' }] },
      { code: 'obj_customer', attributes: [{ standard_id: 11, code: 'customer_id', name: '客户ID' }] },
    ])
    expect(opts).toEqual([
      { value: 11, label: 'obj_order·客户ID（customer_id）', objectCode: 'obj_order' },
    ])
  })

  it('同一属性被两端引用只保留一条（from 端）', () => {
    const opts = mergeViaOptions([
      { code: 'a', attributes: [{ standard_id: 1, code: 'x', name: 'X' }] },
      { code: 'b', attributes: [{ standard_id: 1, code: 'x', name: 'X' }, { standard_id: 2, code: 'y', name: 'Y' }] },
    ])
    expect(opts.map((o) => [o.value, o.objectCode])).toEqual([
      [1, 'a'],
      [2, 'b'],
    ])
  })

  it('缺 standard_id 时回落到 id', () => {
    const opts = mergeViaOptions([{ code: 'a', attributes: [{ id: 7, code: 'k' }] }])
    expect(opts).toEqual([{ value: 7, label: 'a·k（k）', objectCode: 'a' }])
  })

  it('无 code/name 时 label 不带前缀', () => {
    const opts = mergeViaOptions([{ attributes: [{ standard_id: 5, code: 'k', name: '键' }] }])
    expect(opts[0].label).toBe('键（k）')
  })

  it('null 端与空属性被忽略', () => {
    expect(mergeViaOptions([null, undefined, {}])).toEqual([])
    expect(mergeViaOptions([{ code: 'a', attributes: [] }, { code: 'b' }])).toEqual([])
  })

  it('非法 id（0 / 缺失）不进入候选', () => {
    const opts = mergeViaOptions([{ code: 'a', attributes: [{ standard_id: 0, code: 'z' }, { code: 'w' }] }])
    expect(opts).toEqual([])
  })
})
