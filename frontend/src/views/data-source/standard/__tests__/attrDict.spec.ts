import { describe, it, expect } from 'vitest'
import { EMPTY_USAGE, filterAttributes, isOrphan, usageOf } from '../attrDict'

const used = { id: 1, code: 'customer_id', name: '客户ID', usage: { columns: 2, objects: 1, relations: 0 } }
const orphan = { id: 2, code: 'tmp_note', name: '临时备注', aliases: ['remark'] }
const viaOnly = { id: 3, code: 'order_no', name: '订单号', usage: { columns: 0, objects: 0, relations: 1 } }

describe('usageOf', () => {
  it('无 usage 时按零引用处理', () => {
    expect(usageOf(orphan)).toEqual(EMPTY_USAGE)
  })

  it('有 usage 时原样返回', () => {
    expect(usageOf(used)).toEqual({ columns: 2, objects: 1, relations: 0 })
  })
})

describe('isOrphan', () => {
  it('三类引用全为 0 才是孤儿', () => {
    expect(isOrphan(orphan)).toBe(true)
    expect(isOrphan({ id: 9, code: 'c', name: 'n', usage: { columns: 0, objects: 0, relations: 0 } })).toBe(true)
  })

  it('只被关系连接键引用也不算孤儿', () => {
    expect(isOrphan(viaOnly)).toBe(false)
  })

  it('被列绑定或对象引用都不算孤儿', () => {
    expect(isOrphan(used)).toBe(false)
  })
})

describe('filterAttributes', () => {
  const rows = [used, orphan, viaOnly]

  it('默认全量返回且保持原序', () => {
    expect(filterAttributes(rows).map((r) => r.id)).toEqual([1, 2, 3])
  })

  it('onlyOrphan 只留孤儿', () => {
    expect(filterAttributes(rows, { onlyOrphan: true }).map((r) => r.id)).toEqual([2])
  })

  it('关键字命中 code / name / aliases，忽略大小写与空白', () => {
    expect(filterAttributes(rows, { keyword: ' CUSTOMER ' }).map((r) => r.id)).toEqual([1])
    expect(filterAttributes(rows, { keyword: '订单' }).map((r) => r.id)).toEqual([3])
    expect(filterAttributes(rows, { keyword: 'remark' }).map((r) => r.id)).toEqual([2])
  })

  it('onlyOrphan 与关键字同时生效', () => {
    expect(filterAttributes(rows, { onlyOrphan: true, keyword: 'customer' })).toEqual([])
    expect(filterAttributes(rows, { onlyOrphan: true, keyword: '临时' }).map((r) => r.id)).toEqual([2])
  })

  it('空关键字等价于不过滤', () => {
    expect(filterAttributes(rows, { keyword: '   ' }).length).toBe(3)
  })
})
