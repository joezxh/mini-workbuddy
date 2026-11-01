// gridStyle.spec.ts
import { describe, it, expect } from 'vitest'
import { gridStyleOf } from '../gridStyle'

describe('gridStyleOf（12 列制）', () => {
  it('缺省 x=1,y=1,w=3,h=2', () => {
    expect(gridStyleOf(null)).toEqual({ gridColumn: '1 / span 3', gridRow: '1 / span 2' })
  })
  it('全字段透传', () => {
    expect(gridStyleOf({ x: 5, y: 2, w: 6, h: 3 }))
      .toEqual({ gridColumn: '5 / span 6', gridRow: '2 / span 3' })
  })
  it('w 越界钳到 1-12，x 钳到 1-12', () => {
    expect(gridStyleOf({ x: 0, y: 1, w: 99, h: 1 }).gridColumn).toBe('1 / span 12')
  })
})
