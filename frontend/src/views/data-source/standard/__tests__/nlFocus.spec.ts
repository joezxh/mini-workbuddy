import { describe, it, expect } from 'vitest'
import { toNlFocus } from '../nlFocus'

describe('toNlFocus', () => {
  it('正常返回：取对象/关系 code 与摘要', () => {
    const focus = toNlFocus({
      degraded: false,
      highlight_object_codes: ['obj_order', 'obj_customer'],
      highlight_relation_codes: ['rel_order_customer'],
      focus_catalog_code: 'ecom',
      summary: '订单与客户通过 customer_id 关联',
    })
    expect(focus.objectCodes).toEqual(['obj_order', 'obj_customer'])
    expect(focus.relationCodes).toEqual(['rel_order_customer'])
    expect(focus.focusCatalogCode).toBe('ecom')
    expect(focus.degraded).toBe(false)
  })

  it('降级返回：标记 degraded 且高亮为空', () => {
    const focus = toNlFocus({ degraded: true, error: 'no model' })
    expect(focus.degraded).toBe(true)
    expect(focus.objectCodes).toEqual([])
    expect(focus.relationCodes).toEqual([])
    expect(focus.focusCatalogCode).toBeNull()
    expect(focus.error).toBe('no model')
  })

  it('降级原因：换行压成空格并截断', () => {
    expect(toNlFocus({ degraded: true, error: '  a\nb  ' }).error).toBe('a b')
    expect(toNlFocus({ degraded: true, error: 'x'.repeat(300) }).error.length).toBe(201)
    expect(toNlFocus({ degraded: true, error: 123 }).error).toBe('')
  })

  it('脏数据：数组内非字符串被过滤，缺字段走默认值', () => {
    const focus = toNlFocus({ highlight_object_codes: ['ok', 1, '', null, 'ok2'] })
    expect(focus.objectCodes).toEqual(['ok', 'ok2'])
    expect(focus.summary).toBe('')
    expect(focus.degraded).toBe(false)
  })

  it('空返回体：全部落到安全默认值', () => {
    const focus = toNlFocus(null)
    expect(focus).toEqual({
      objectCodes: [],
      relationCodes: [],
      focusCatalogCode: null,
      summary: '',
      degraded: false,
      error: '',
    })
  })
})
