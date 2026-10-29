import { describe, it, expect } from 'vitest'
import { keywordHits, queryTokens } from '../keywordSearch'

const OBJECTS = [
  { code: 'obj_order', name: '订单', aliases: ['order', '交易单'] },
  { code: 'obj_customer', name: '客户', aliases: ['customer'] },
  { code: 'obj_product', name: '商品', aliases: null },
]

const RELATIONS = [
  { code: 'rel_order_customer', name: '下单客户' },
  { code: 'rel_order_product', name: '订单商品' },
]

describe('queryTokens', () => {
  it('按非字母数字切词并丢掉单字', () => {
    expect(queryTokens('order CUStomer')).toEqual(['order', 'customer'])
    expect(queryTokens('订单和客户 怎么关联')).toEqual(['订单和客户', '怎么关联'])
    expect(queryTokens('a b')).toEqual([])
    expect(queryTokens('')).toEqual([])
  })
})

describe('keywordHits', () => {
  it('按 code 命中', () => {
    const hits = keywordHits('obj_customer', OBJECTS, RELATIONS)
    expect(hits.objectCodes).toEqual(['obj_customer'])
    expect(hits.relationCodes).toEqual([])
  })

  it('按名称命中（中文整句里包含实体名）', () => {
    const hits = keywordHits('订单和客户怎么关联', OBJECTS, RELATIONS)
    expect(hits.objectCodes).toEqual(['obj_order', 'obj_customer'])
  })

  it('按别名命中', () => {
    const hits = keywordHits('交易单的买方是谁', OBJECTS, [])
    expect(hits.objectCodes).toEqual(['obj_order'])
  })

  it('对象与关系各自按自身词条判定，不做连带', () => {
    const hits = keywordHits('order', OBJECTS, RELATIONS)
    // 对象侧只命中 obj_order；关系 code 含 order 的两条都算命中
    expect(hits.objectCodes).toEqual(['obj_order'])
    expect(hits.relationCodes).toEqual(['rel_order_customer', 'rel_order_product'])
  })

  it('未命中返回空数组', () => {
    const hits = keywordHits('完全不存在的词', OBJECTS, RELATIONS)
    expect(hits).toEqual({ objectCodes: [], relationCodes: [] })
  })

  it('空查询不返回任何命中', () => {
    expect(keywordHits('   ', OBJECTS, RELATIONS)).toEqual({ objectCodes: [], relationCodes: [] })
  })

  it('重复 code 去重且保持入参顺序', () => {
    const dup = [...OBJECTS, { code: 'obj_order', name: '订单副本' }]
    expect(keywordHits('订单', dup, []).objectCodes).toEqual(['obj_order'])
  })
})
