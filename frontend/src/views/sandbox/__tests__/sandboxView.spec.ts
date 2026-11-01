import { describe, it, expect } from 'vitest'
import type { WorldEntity, KpiPoint, Observation } from '@/api/sandbox'
import {
  buildCanvasLayout, resolveEdgeEntity, buildCanvasEdges, selectLatestKpi,
  deriveHealth, deriveControllability, deriveRiskTop3, timelineItems, traceObservations,
} from '../sandboxView'

const ent = (code: string, obj: string, risk: number, masked = false): WorldEntity =>
  ({ entity_code: code, object_code: obj, props: { name: code }, risk_score: risk, masked, origin: 'clone', source_ref: null })

describe('buildCanvasLayout', () => {
  it('网格列数 ≤3，SimEvent 标记 isEvent', () => {
    const nodes = buildCanvasLayout([ent('A', 'Supplier', 0.7), ent('E', 'SimEvent', 0)])
    expect(nodes).toHaveLength(2)
    expect(nodes[0].x).toBeGreaterThanOrEqual(0)
    expect(nodes[1].isEvent).toBe(true)
    expect(nodes[0].riskColor).toBe('#ff7b72') // ≥0.6
  })
})

describe('resolveEdgeEntity', () => {
  const nodes = buildCanvasLayout([ent('SUP006', 'Supplier', 0.5), ent('FAC007', 'Factory', 0.5)])
  it('A.prop → A', () => expect(resolveEdgeEntity('SUP006.supply_cut', nodes)).toBe('SUP006'))
  it('OBJ:prop → 匹配 object_code 实体', () => expect(resolveEdgeEntity('Factory:capacity', nodes)).toBe('FAC007'))
  it('未知 → null', () => expect(resolveEdgeEntity('NOPE:x', nodes)).toBeNull())
})

describe('buildCanvasEdges', () => {
  it('仅两端可解析才成边；tick≥activation 点亮', () => {
    const nodes = buildCanvasLayout([ent('SUP006', 'Supplier', 0.5), ent('FAC007', 'Factory', 0.5)])
    const edges = [{ code: 'CE1', label: '断供→减产', from_ref: 'SUP006', to_ref: 'FAC007.capacity', activation_tick: 2 }]
    const out = buildCanvasEdges(nodes, edges as any, 3)
    expect(out).toHaveLength(1)
    expect(out[0].active).toBe(true)
    expect(buildCanvasEdges(nodes, edges as any, 1)[0].active).toBe(false)
  })
})

describe('KPI 选择', () => {
  const kpis: KpiPoint[] = [
    { tick: 1, kind: 'kpi_point', detail_json: { health: '0.9', controllability: '0.95' } },
    { tick: 2, kind: 'kpi_point', detail_json: { health: '0.5', controllability: '0.4' } },
    { tick: 2, kind: 'risk_point', detail_json: [{ entity_code: 'SUP006', score: '0.8' }] },
  ]
  it('selectLatestKpi ≤tick 末值', () => expect(selectLatestKpi(kpis, 2, 'kpi_point')!.tick).toBe(2))
  it('deriveHealth 0.5 → 预警 C err', () => { expect(deriveHealth(selectLatestKpi(kpis, 2, 'kpi_point')).label).toBe('预警 C') })
  it('deriveControllability 0.4 → low', () => { expect(deriveControllability(selectLatestKpi(kpis, 2, 'kpi_point')).label).toBe('low') })
  it('deriveRiskTop3 取 ≤tick 末 risk_point', () => { expect(deriveRiskTop3(kpis, 2)[0].score).toBe(0.8) })
})

describe('观察过滤', () => {
  const obs: Observation[] = [
    { tick: 1, kind: 'edge_fired', severity: 'info', title: 'x', detail_json: {} },
    { tick: 3, kind: 'kpi_point', severity: 'info', title: 'y', detail_json: {} },
    { tick: 5, kind: 'rule_fired', severity: 'warn', title: 'z', detail_json: {} },
  ]
  it('timelineItems 排除 kpi/risk', () => expect(timelineItems(obs).map(o => o.kind)).toEqual(['edge_fired', 'rule_fired']))
  it('traceObservations 仅 ≤tick', () => expect(traceObservations(obs, 1).map(o => o.title)).toEqual(['x']))
})
