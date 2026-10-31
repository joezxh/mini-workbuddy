/**
 * 标准图的前端视图计算（纯函数，便于 node 环境单测）。
 *
 * 口径：现有 /standards/graph 已一次返回所选目录的整个子树，
 * 因此筛选、种子子图、节点上限、导出全部本地算，零后端改动（spec §6）。
 */
import { typeLabel, typeTone } from '@/components/common/graph/graphTheme'
import type { CanvasEdge, CanvasNode } from '@/components/common/graph/graphTypes'

export interface StdGraphNode {
  id: number
  code: string
  name: string
  domain?: string | null
  status?: string
}

export interface StdGraphEdge {
  id: number
  code: string
  name?: string | null
  from: number
  to: number
  relation_type?: string | null
}

export interface StdFilters {
  /** full = 全图；seed = 以选中对象为种子的子图 */
  mode: 'full' | 'seed'
  seedId: number | null
  depth: number
  objectCode: string
  relationType: string
  limit: number
}

export interface FacetOption {
  value: string
  label: string
  count: number
}

export interface StdGraphResult {
  nodes: StdGraphNode[]
  edges: StdGraphEdge[]
}

export function degreeMap(edges: StdGraphEdge[]): Record<number, number> {
  const deg: Record<number, number> = {}
  edges.forEach((e) => {
    deg[e.from] = (deg[e.from] || 0) + 1
    deg[e.to] = (deg[e.to] || 0) + 1
  })
  return deg
}

export function neighborsOf(id: number, edges: StdGraphEdge[]): Set<number> {
  const set = new Set<number>()
  edges.forEach((e) => {
    if (e.from === id) set.add(e.to)
    else if (e.to === id) set.add(e.from)
  })
  return set
}

/** 从种子出发按跳数扩张；种子为空/不在任何边上（不存在或完全孤立）返回空集，depth 0 只保留种子 */
export function bfsSubgraph(seedId: number | null, edges: StdGraphEdge[], depth: number): Set<number> {
  const reached = new Set<number>()
  if (seedId === null || seedId === undefined) return reached
  // 种子必须出现在至少一条边上，否则（id 不存在或完全孤立）无子图可展开
  const incident = edges.some((e) => e.from === seedId || e.to === seedId)
  if (!incident) return reached
  reached.add(seedId)
  let frontier = [seedId]
  const maxDepth = Math.max(0, depth)
  for (let d = 0; d < maxDepth && frontier.length; d += 1) {
    const next: number[] = []
    frontier.forEach((id) => {
      neighborsOf(id, edges).forEach((n) => {
        if (!reached.has(n)) {
          reached.add(n)
          next.push(n)
        }
      })
    })
    frontier = next
  }
  return reached
}

/** 按对象标准过滤：该对象 + 与它直接相连的边与对端 */
export function filterByObjectCode(nodes: StdGraphNode[], edges: StdGraphEdge[], code: string): StdGraphResult {
  if (!code) return { nodes, edges }
  const seeds = nodes.filter((n) => n.code === code)
  if (!seeds.length) return { nodes: [], edges: [] }
  const keep = new Set<number>(seeds.map((n) => n.id))
  const keptEdges = edges.filter((e) => {
    const hit = seeds.some((s) => s.id === e.from || s.id === e.to)
    if (!hit) return false
    keep.add(e.from)
    keep.add(e.to)
    return true
  })
  return { nodes: nodes.filter((n) => keep.has(n.id)), edges: keptEdges }
}

/** 按关系基数过滤：边收窄后，失去所有边的节点一并丢弃 */
export function filterByRelationType(
  nodes: StdGraphNode[],
  edges: StdGraphEdge[],
  relationType: string,
): StdGraphResult {
  if (!relationType) return { nodes, edges }
  const kept = edges.filter((e) => e.relation_type === relationType)
  const alive = new Set<number>()
  kept.forEach((e) => {
    alive.add(e.from)
    alive.add(e.to)
  })
  return { nodes: nodes.filter((n) => alive.has(n.id)), edges: kept }
}

/** 度数降序截断（同度数按 id 升序，保证可复现），再丢弃悬空边 */
export function applyNodeLimit(nodes: StdGraphNode[], edges: StdGraphEdge[], cap: number): StdGraphResult {
  if (!cap || nodes.length <= cap) return { nodes, edges }
  const deg = degreeMap(edges)
  const sorted = [...nodes].sort((a, b) => (deg[b.id] || 0) - (deg[a.id] || 0) || a.id - b.id)
  const kept = sorted.slice(0, cap)
  const ids = new Set(kept.map((n) => n.id))
  return { nodes: kept, edges: edges.filter((e) => ids.has(e.from) && ids.has(e.to)) }
}

/** 视图计算总入口：模式 → 对象 → 基数 → 上限 */
export function selectVisibleGraph(nodes: StdGraphNode[], edges: StdGraphEdge[], f: StdFilters): StdGraphResult {
  let view = { nodes, edges }
  if (f.mode === 'seed') {
    const ids = bfsSubgraph(f.seedId, edges, f.depth)
    view = { nodes: view.nodes.filter((n) => ids.has(n.id)), edges: view.edges.filter((e) => ids.has(e.from) && ids.has(e.to)) }
  }
  view = filterByObjectCode(view.nodes, view.edges, f.objectCode)
  view = filterByRelationType(view.nodes, view.edges, f.relationType)
  return applyNodeLimit(view.nodes, view.edges, f.limit)
}

export function objectFacets(nodes: StdGraphNode[]): FacetOption[] {
  const counts = new Map<string, number>()
  nodes.forEach((n) => counts.set(n.code, (counts.get(n.code) || 0) + 1))
  // 计数降序，同计数按 code 字典序（保证下拉项顺序可复现）
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count, label: `${typeLabel(value) || value}（${count}）` }))
}

export function relationTypeFacets(edges: StdGraphEdge[]): FacetOption[] {
  const counts = new Map<string, number>()
  edges.forEach((e) => {
    if (!e.relation_type) return
    counts.set(e.relation_type, (counts.get(e.relation_type) || 0) + 1)
  })
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count, label: `${value}（${count}）` }))
}

export function toCanvasNodes(nodes: StdGraphNode[]): CanvasNode[] {
  return nodes.map((n) => ({
    id: n.id,
    name: n.name,
    code: n.code,
    color: typeTone(n.code).color,
    typeLabel: typeLabel(n.code) || n.code,
  }))
}

export function toCanvasEdges(edges: StdGraphEdge[]): CanvasEdge[] {
  return edges.map((e) => ({
    id: e.id,
    from: e.from,
    to: e.to,
    // 边标签给语义名（原型口径），基数移到检视面板；无 name 回落 code
    label: e.name || e.code,
    code: e.code,
  }))
}

export function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return ''
  const s = String(value)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/** 导出当前可见子图：JSON 保结构，CSV 为边表（两端解析为对象 code） */
export function serializeGraph(nodes: StdGraphNode[], edges: StdGraphEdge[], fmt: 'json' | 'csv'): string {
  if (fmt !== 'csv') return JSON.stringify({ nodes, edges }, null, 2)
  const codeOf = new Map(nodes.map((n) => [n.id, n.code]))
  const head = 'edge_id,edge_code,edge_name,from_code,to_code,relation_type'
  const rows = edges.map((e) =>
    [
      e.id,
      csvEscape(e.code),
      csvEscape(e.name),
      csvEscape(codeOf.get(e.from) ?? ''),
      csvEscape(codeOf.get(e.to) ?? ''),
      csvEscape(e.relation_type),
    ].join(','),
  )
  return [head, ...rows].join('\n')
}
