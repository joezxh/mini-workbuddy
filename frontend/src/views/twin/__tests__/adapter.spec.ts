// adapter.spec.ts —— 逐字对齐 shape_result 归一形状（ontology_query_service.py:99-114）
import { describe, it, expect } from 'vitest'
import { toMultiLine, toBar, toPie, kpiValue } from '../widgets/adapter'

describe('renderer 适配层（只转置键名，不重定义语义）', () => {
  it('trend：{records,t,values} → {xAxis,series[]}', () => {
    const d = { records: [{ ts: '09:00', load: 12, temp: 30 }, { ts: '10:00', load: 18, temp: 31 }],
                t: 'ts', values: ['load', 'temp'] }
    expect(toMultiLine(d)).toEqual({
      xAxis: ['09:00', '10:00'],
      series: [{ name: 'load', data: [12, 18] }, { name: 'temp', data: [30, 31] }],
    })
  })
  it('bar：只取 values[0]（C3 单序列订正）', () => {
    const d = { records: [{ line: 'A', qty: 7, extra: 9 }], t: 'line', values: ['qty', 'extra'] }
    expect(toBar(d)).toEqual([{ name: 'A', value: 7 }])
  })
  it('donut：parts 前两列 → {name,value}', () => {
    const d = { records: [{ st: 'run', n: 5 }, { st: 'idle', n: 2 }], parts: ['st', 'n'] }
    expect(toPie(d)).toEqual([{ name: 'run', value: 5 }, { name: 'idle', value: 2 }])
  })
  it('kpi：{value,records} → value；空 records → null', () => {
    expect(kpiValue({ value: 42, records: [{ v: 42 }] })).toBe(42)
    expect(kpiValue({ value: null, records: [] })).toBe(null)
  })
})
