/**
 * 推演沙盘纯视图逻辑（从 SimulationSandbox.vue 抽出，去响应式，参数注入以便单测）。
 * 世界真源恒在后端沙箱表，本模块只做「已取回的快照 → 画布/游标展示值」的纯计算。
 */
import type { WorldEntity, CausalEdge, KpiPoint, Observation } from '@/api/sandbox'

export type LayoutNode = WorldEntity & {
  x: number; y: number; isEvent: boolean; name: string; risk: number; riskColor: string
}

export function entityDisplayName(entities: WorldEntity[], code: string): string {
  const e = entities.find(x => x.entity_code === code)
  if (!e) return code
  return e.props?.name || e.props?.display_name || e.object_code || code
}

export function riskColorOf(score: number): string {
  return score >= 0.6 ? '#ff7b72' : score >= 0.35 ? '#f2b66d' : '#4cc38a'
}

/** 确定性网格布局：列数 ≤3，行自适应；SimEvent 为菱形节点。 */
export function buildCanvasLayout(entities: WorldEntity[]): LayoutNode[] {
  const W = 960, H = 460
  const cols = Math.min(3, Math.max(1, Math.ceil(Math.sqrt(entities.length))))
  const rows = Math.max(1, Math.ceil(entities.length / cols))
  const cellW = W / cols, cellH = H / rows
  return entities.map((e, i) => {
    const r = Math.floor(i / cols), c = i % cols
    return {
      ...e,
      isEvent: e.object_code === 'SimEvent',
      name: entityDisplayName(entities, e.entity_code),
      risk: Number(e.risk_score) || 0,
      riskColor: riskColorOf(Number(e.risk_score) || 0),
      x: c * cellW + 60, y: r * cellH + 20,
    }
  })
}

/** 边端点引用解析：'A.prop'→'A'；'OBJ:prop'→匹配 object_code；否则按 entity_code。 */
export function resolveEdgeEntity(ref: string | null, nodes: LayoutNode[]): string | null {
  if (!ref) return null
  if (ref.includes('.')) return ref.split('.', 1)[0]
  if (ref.includes(':')) {
    const obj = ref.split(':', 1)[0]
    const hit = nodes.find(n => n.object_code === obj)
    return hit ? hit.entity_code : null
  }
  return nodes.find(n => n.entity_code === ref) ? ref : null
}

export interface CanvasEdge {
  path: string; mx: number; my: number; wl: number; label: string; active: boolean
}

/** 两端均可解析为节点才成边；activation_tick≤当前 tick 视为点亮。 */
export function buildCanvasEdges(nodes: LayoutNode[], edges: CausalEdge[], tick: number): CanvasEdge[] {
  const pos = new Map(nodes.map(n => [n.entity_code, n]))
  const out: CanvasEdge[] = []
  for (const e of edges) {
    const a = pos.get(resolveEdgeEntity(e.from_ref, nodes) || '')
    const b = pos.get(resolveEdgeEntity(e.to_ref, nodes) || '')
    if (!a || !b) continue
    const x1 = a.x + (a.isEvent ? 92 : 156), y1 = a.y + 22
    const x2 = b.x, y2 = b.y + 22
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
    const path = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`
    const active = e.activation_tick == null || tick >= e.activation_tick
    out.push({ path, mx, my, wl: (e.label || '').length * 6 + 12, label: e.label || '', active })
  }
  return out
}

export function selectLatestKpi(kpis: KpiPoint[], tick: number, kind: string): KpiPoint | null {
  const pts = kpis
    .filter(k => k.kind === kind && (k.tick ?? 0) <= tick)
    .sort((a, b) => (a.tick ?? 0) - (b.tick ?? 0))
  return pts.length ? pts[pts.length - 1] : null
}

export function deriveHealth(kpi: KpiPoint | null): { num: number; label: string; color: string } {
  const num = Number(kpi?.detail_json?.health ?? 1)
  return {
    num,
    label: num >= 0.8 ? '健康 A' : num >= 0.6 ? '关注 B' : '预警 C',
    color: num >= 0.8 ? 'var(--ok)' : num >= 0.6 ? 'var(--amber)' : 'var(--err)',
  }
}

export function deriveControllability(kpi: KpiPoint | null): { label: 'high' | 'medium' | 'low'; color: string } {
  const c = Number(kpi?.detail_json?.controllability ?? 1)
  const label = (c >= 0.8 ? 'high' : c >= 0.5 ? 'medium' : 'low') as 'high' | 'medium' | 'low'
  return { label, color: label === 'high' ? 'var(--ok)' : label === 'medium' ? 'var(--amber)' : 'var(--err)' }
}

export function deriveRiskTop3(kpis: KpiPoint[], tick: number): { entity_code: string; score: number }[] {
  const pts = kpis
    .filter(k => k.kind === 'risk_point' && (k.tick ?? 0) <= tick)
    .sort((a, b) => (a.tick ?? 0) - (b.tick ?? 0))
  const last = pts[pts.length - 1]
  if (!last) return []
  const arr = last.detail_json
  return Array.isArray(arr) ? arr.map((x: any) => ({ entity_code: x.entity_code, score: Number(x.score) })) : []
}

export function timelineItems(obs: Observation[]): Observation[] {
  return obs.filter(o => o.kind !== 'kpi_point' && o.kind !== 'risk_point').slice(0, 60)
}

export function traceObservations(obs: Observation[], tick: number): Observation[] {
  return obs.filter(o => (o.tick ?? 0) <= tick && o.kind !== 'kpi_point' && o.kind !== 'risk_point')
}
