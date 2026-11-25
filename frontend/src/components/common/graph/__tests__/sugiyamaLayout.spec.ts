import { describe, it, expect } from 'vitest'
import { sugiyamaLayout } from '../sugiyamaLayout'
import type { CanvasEdge, CanvasNode } from '../graphTypes'

function node(id: number, name = `n${id}`): CanvasNode {
  return { id, name, code: 'T', color: '#333', typeLabel: 'T' }
}

function edge(id: number, from: number, to: number): CanvasEdge {
  return { id, from, to, label: '' }
}

/** 统一半径：测试里所有节点等半径（8），简化无重叠断言 */
const R = 8
const radiusOf = () => R

/** 由布局结果统计「跨层相邻边的交叉数」（与层内 x 序有关） */
function countCrossings(
  edges: CanvasEdge[],
  pos: Record<number, { x: number; y: number }>,
): number {
  // 按 y 分层（同层 y 相同），层内按 x 排序得到序号
  const layers = new Map<number, number[]>()
  for (const idStr of Object.keys(pos)) {
    const id = Number(idStr)
    const y = pos[id].y
    const arr = layers.get(y) || []
    arr.push(id)
    layers.set(y, arr)
  }
  const orderOf = new Map<number, number>()
  for (const [, arr] of layers) {
    arr.sort((a, b) => pos[a].x - pos[b].x)
    arr.forEach((id, i) => orderOf.set(id, i))
  }
  let crossings = 0
  for (let i = 0; i < edges.length; i += 1) {
    for (let j = i + 1; j < edges.length; j += 1) {
      const e1 = edges[i]
      const e2 = edges[j]
      if (e1.from === e2.from || e1.to === e2.to) continue
      if (pos[e1.from].y === pos[e2.from].y && pos[e1.to].y === pos[e2.to].y) {
        const a1 = orderOf.get(e1.from)!
        const a2 = orderOf.get(e2.from)!
        const b1 = orderOf.get(e1.to)!
        const b2 = orderOf.get(e2.to)!
        if ((a1 - a2) * (b1 - b2) < 0) crossings += 1
      }
    }
  }
  return crossings
}

describe('sugiyamaLayout', () => {
  it('空输入：返回空坐标，不崩溃', () => {
    expect(sugiyamaLayout([], [], radiusOf)).toEqual({})
  })

  it('链式 DAG：边方向自上而下（y 严格递增）', () => {
    const nodes = [node(1), node(2), node(3)]
    const edges = [edge(10, 1, 2), edge(11, 2, 3)]
    const pos = sugiyamaLayout(nodes, edges, radiusOf)
    expect(Object.keys(pos).length).toBe(3)
    expect(pos[1].y).toBeLessThan(pos[2].y)
    expect(pos[2].y).toBeLessThan(pos[3].y)
  })

  it('确定性：同输入两次布局坐标一致', () => {
    const nodes = [node(1), node(2), node(3), node(4)]
    const edges = [edge(10, 1, 3), edge(11, 2, 4), edge(12, 1, 4)]
    const a = sugiyamaLayout(nodes, edges, radiusOf)
    const b = sugiyamaLayout(nodes, edges, radiusOf)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('确定性：输入数组顺序打乱后布局结果不变（内部按 id 归一）', () => {
    const edges = [edge(10, 1, 3), edge(11, 2, 4), edge(12, 1, 4)]
    const ordered = [node(1), node(2), node(3), node(4)]
    const shuffled = [node(4), node(3), node(1), node(2)]
    const a = sugiyamaLayout(ordered, edges, radiusOf)
    const b = sugiyamaLayout(shuffled, [...edges].reverse(), radiusOf)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('层内无重叠：同层相邻节点水平间距 >= 半径和 + 节点间距', () => {
    // 星型：一个源指向 5 个叶（同层）
    const nodes = [node(0), node(1), node(2), node(3), node(4), node(5)]
    const edges = [1, 2, 3, 4, 5].map((i) => edge(10 + i, 0, i))
    const pos = sugiyamaLayout(nodes, edges, radiusOf)
    const ys = [...new Set(Object.values(pos).map((p) => p.y))]
    expect(ys.length).toBe(2)
    const leafY = Math.max(...ys)
    const leaves = Object.keys(pos)
      .map(Number)
      .filter((id) => pos[id].y === leafY)
      .sort((a, b) => pos[a].x - pos[b].x)
    for (let i = 1; i < leaves.length; i += 1) {
      expect(pos[leaves[i]].x - pos[leaves[i - 1]].x).toBeGreaterThanOrEqual(R * 2 + 20)
    }
  })

  it('有环图：a→b→c→a 全部节点有有限坐标（回边被临时反转，不崩溃不 NaN）', () => {
    const nodes = [node(1), node(2), node(3)]
    const edges = [edge(10, 1, 2), edge(11, 2, 3), edge(12, 3, 1)]
    const pos = sugiyamaLayout(nodes, edges, radiusOf)
    expect(Object.keys(pos).length).toBe(3)
    for (const p of Object.values(pos)) {
      expect(Number.isFinite(p.x)).toBe(true)
      expect(Number.isFinite(p.y)).toBe(true)
    }
  })

  it('交叉减少：交叉双菱形经重心法后交叉数降为 0', () => {
    // 初始按 id 序必然 1 交叉：L0=[1,2] L1=[3,4]，边 1→4, 2→3
    const nodes = [node(1), node(2), node(3), node(4)]
    const edges = [edge(10, 1, 4), edge(11, 2, 3)]
    const pos = sugiyamaLayout(nodes, edges, radiusOf)
    expect(countCrossings(edges, pos)).toBe(0)
  })

  it('孤挂节点：无边节点也有有限坐标且不与连通节点重叠', () => {
    const nodes = [node(1), node(2), node(9)]
    const edges = [edge(10, 1, 2)]
    const pos = sugiyamaLayout(nodes, edges, radiusOf)
    expect(Number.isFinite(pos[9].x)).toBe(true)
    expect(Number.isFinite(pos[9].y)).toBe(true)
    // 孤挂节点不与任何节点完全重合
    expect(pos[9].x !== pos[1].x || pos[9].y !== pos[1].y).toBe(true)
    expect(pos[9].x !== pos[2].x || pos[9].y !== pos[2].y).toBe(true)
  })

  it('真实规模（300 节点 / 500 边）：全部坐标有限且层内无重叠', () => {
    const nodes = Array.from({ length: 300 }, (_, i) => node(i + 1))
    const edges: CanvasEdge[] = []
    for (let i = 0; i < 500; i += 1) {
      const from = (i % 299) + 1
      const to = ((i * 37) % 299) + 1
      if (from !== to) edges.push(edge(1000 + i, from, to))
    }
    const pos = sugiyamaLayout(nodes, edges, radiusOf)
    expect(Object.keys(pos).length).toBe(300)
    for (const p of Object.values(pos)) {
      expect(Number.isFinite(p.x)).toBe(true)
      expect(Number.isFinite(p.y)).toBe(true)
    }
    // 同层内按 x 排序后相邻节点间距 >= 半径和（无重叠覆盖）
    const byY = new Map<number, number[]>()
    for (const idStr of Object.keys(pos)) {
      const id = Number(idStr)
      const arr = byY.get(pos[id].y) || []
      arr.push(id)
      byY.set(pos[id].y, arr)
    }
    for (const [, arr] of byY) {
      arr.sort((a, b) => pos[a].x - pos[b].x)
      for (let i = 1; i < arr.length; i += 1) {
        expect(pos[arr[i]].x - pos[arr[i - 1]].x).toBeGreaterThanOrEqual(R * 2)
      }
    }
  })
})
