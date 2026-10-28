import { describe, it, expect } from 'vitest'
import { resolveFocusScope } from '../focusScope'

describe('resolveFocusScope', () => {
  it('PG 族：db_name 是物理库、database 是 schema', () => {
    const s = resolveFocusScope(
      { source_id: 1, db_name: 'appdb', database: 'public', table: 'orders' },
      true,
    )
    expect(s.physicalDb).toBe('appdb')
    expect(s.scope).toBe('public')
    expect(s.table).toBe('orders')
  })

  it('PG 族：缺 db_name 时用 database 兜底（不丢落点）', () => {
    const s = resolveFocusScope({ source_id: 1, database: 'public', table: 'orders' }, true)
    expect(s.physicalDb).toBe('public')
    expect(s.scope).toBe('public')
  })

  it('非 PG 族：库名即作用域，无物理库层级', () => {
    const s = resolveFocusScope(
      { source_id: 2, db_name: 'shop', database: 'shop', table: 'items' },
      false,
    )
    expect(s.physicalDb).toBeUndefined()
    expect(s.scope).toBe('shop')
    expect(s.table).toBe('items')
  })

  it('非 PG 族：只有 db_name 时也能定位', () => {
    const s = resolveFocusScope({ source_id: 2, db_name: 'shop', table: 'items' }, false)
    expect(s.physicalDb).toBeUndefined()
    expect(s.scope).toBe('shop')
  })
})
