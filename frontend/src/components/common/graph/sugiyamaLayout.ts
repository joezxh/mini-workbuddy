/**
 * Sugiyama 定向分层布局（纯函数，零依赖，零随机）——流程图风格呈现。
 *
 * 四阶段流水线（全部以 id 为次序键、并列按 id 决胜，同输入输出逐字节一致）：
 *  1. 环消除：迭代 DFS 标记回边并在布局期临时反转（有环全库图可分层；
 *     调用方绘制仍按原 from→to 方向画箭头）；
 *  2. 分层：DAG 上 Kahn 拓扑序做最长路（layer = max(layer(pred)+1)）；
 *  3. 交叉减少：重心法（barycenter）上下交替 sweep——这是「边尽量减少交叉」
 *     的核心启发式，O(sweeps×E)；节点 >300 时轮数自动折半护性能；
 *  4. 坐标分配：层内按最终排序落等距槽位（槽宽 = 层内最大半径×2 + 节点间距），
 *     各层相对公共中轴居中，y = 层号 × 层距（自上而下 TB）。
 *
 * 输出坐标：x 以 0 为中轴、y 自 0 起（调用方平移到视口）。层内槽位天然错开，
 * 不存在重合节点——不依赖 FR 的「重合伪随机方向」解锁。
 */
import type { CanvasEdge, CanvasNode } from './graphTypes'

export interface SugiyamaOptions {
  /** 层内节点间距（默认 24） */
  nodeGap?: number
  /** 层间垂直间距（默认 96，需大于上下两层最大半径之和） */
  layerGap?: number
  /** 交叉优化 sweep 轮数上限（默认 8；节点 >300 自动降为 4 护性能） */
  sweepLimit?: number
}

interface Pt {
  x: number
  y: number
}

const DEFAULT_NODE_GAP = 24
const DEFAULT_LAYER_GAP = 96
const DEFAULT_SWEEPS = 8
/** 超过该节点数时交叉优化轮数折半（性能护栏，与 FR 按规模降迭代同思路） */
const SWEEP_HALF_THRESHOLD = 300

/** 迭代 DFS 环消除：返回被判定为回边、布局期临时反转的边集合 */
function findBackEdges(
  ids: number[],
  outAdj: Map<number, number[]>,
): Set<string> {
  const WHITE = 0
  const GRAY = 1
  const BLACK = 2
  const color = new Map<number, number>()
  ids.forEach((id) => color.set(id, WHITE))
  const back = new Set<string>()
  for (const root of ids) {
    if (color.get(root) !== WHITE) continue
    // 显式栈：帧 = [节点, 邻接游标]；邻接已按目标 id 升序 → 确定性
    const stack: Array<{ id: number; idx: number }> = [{ id: root, idx: 0 }]
    color.set(root, GRAY)
    while (stack.length) {
      const frame = stack[stack.length - 1]
      const adj = outAdj.get(frame.id) || []
      if (frame.idx >= adj.length) {
        color.set(frame.id, BLACK)
        stack.pop()
        continue
      }
      const next = adj[frame.idx]
      frame.idx += 1
      const c = color.get(next)
      if (c === WHITE) {
        color.set(next, GRAY)
        stack.push({ id: next, idx: 0 })
      } else if (c === GRAY) {
        // 回边：next → ... → frame.id 路径存在，next 在当前 DFS 栈上
        back.add(`${frame.id}->${next}`)
      }
    }
  }
  return back
}

/**
 * Sugiyama 分层布局主入口。
 * @param nodes 画布节点（内部按 id 归一，输入顺序不影响结果）
 * @param edges 画布有向边（自环/重复边/端点缺失的边在布局约束中忽略，绘制不受影响）
 * @param radiusOf 节点渲染半径（GraphCanvas.nodeRadius 复用，槽宽按真实半径预留）
 */
export function sugiyamaLayout(
  nodes: CanvasNode[],
  edges: CanvasEdge[],
  radiusOf: (id: number) => number,
  options?: SugiyamaOptions,
): Record<number, Pt> {
  const nodeGap = options?.nodeGap ?? DEFAULT_NODE_GAP
  const layerGap = options?.layerGap ?? DEFAULT_LAYER_GAP
  const ids = [...new Set(nodes.map((n) => n.id))].sort((a, b) => a - b)
  if (!ids.length) return {}
  const idSet = new Set(ids)

  // 邻接（升序）：布局约束只用「端点都在节点集、非自环」的边，去重
  const outAdj = new Map<number, number[]>()
  const edgeSet = new Set<string>()
  const laidEdges: Array<{ from: number; to: number }> = []
  for (const e of edges) {
    if (!idSet.has(e.from) || !idSet.has(e.to) || e.from === e.to) continue
    const key = `${e.from}->${e.to}`
    if (edgeSet.has(key)) continue
    edgeSet.add(key)
    laidEdges.push({ from: e.from, to: e.to })
  }
  for (const id of ids) outAdj.set(id, [])
  for (const e of laidEdges) outAdj.get(e.from)!.push(e.to)
  for (const [, arr] of outAdj) arr.sort((a, b) => a - b)

  // 阶段 1：环消除（回边布局期反转）
  const back = findBackEdges(ids, outAdj)
  const dagEdges = laidEdges.map((e) =>
    back.has(`${e.from}->${e.to}`) ? { from: e.to, to: e.from } : e,
  )

  // 阶段 2：最长路分层（Kahn 拓扑序，就绪集按 id 升序处理 → 确定性）
  const layer = new Map<number, number>()
  ids.forEach((id) => layer.set(id, 0))
  const indeg = new Map<number, number>()
  ids.forEach((id) => indeg.set(id, 0))
  const dagAdj = new Map<number, number[]>()
  for (const id of ids) dagAdj.set(id, [])
  for (const e of dagEdges) {
    dagAdj.get(e.from)!.push(e.to)
    indeg.set(e.to, (indeg.get(e.to) || 0) + 1)
  }
  for (const [, arr] of dagAdj) arr.sort((a, b) => a - b)
  const ready = ids.filter((id) => (indeg.get(id) || 0) === 0)
  const topo: number[] = []
  while (ready.length) {
    // 取最小 id（就绪集有序插入 + splice，规模内开销可忽略）
    ready.sort((a, b) => a - b)
    const u = ready.shift()!
    topo.push(u)
    for (const v of dagAdj.get(u) || []) {
      layer.set(v, Math.max(layer.get(v) || 0, (layer.get(u) || 0) + 1))
      indeg.set(v, (indeg.get(v) || 0) - 1)
      if ((indeg.get(v) || 0) <= 0) ready.push(v)
    }
  }
  // 拓扑未覆盖（理论上环消除后不存在）兜底：保持 layer 0

  // 孤挂节点（无任何布局边）归入末层之下的独立层
  const hasEdge = new Set<number>()
  for (const e of laidEdges) {
    hasEdge.add(e.from)
    hasEdge.add(e.to)
  }
  const isolated = ids.filter((id) => !hasEdge.has(id))
  const maxLayer = Math.max(0, ...ids.map((id) => layer.get(id) || 0))
  for (const id of isolated) layer.set(id, maxLayer + 1)

  // 层分组（层内初始序 = id 升序）
  const numLayers = maxLayer + (isolated.length ? 1 : 0) + 1
  const layers: number[][] = Array.from({ length: numLayers }, () => [])
  for (const id of ids) layers[layer.get(id) || 0].push(id)
  for (const arr of layers) arr.sort((a, b) => a - b)

  // 阶段 3：重心法交叉减少（上下交替 sweep；邻接仅计相邻层，跨层跳边忽略）
  const sweeps =
    options?.sweepLimit ?? (ids.length > SWEEP_HALF_THRESHOLD ? 4 : DEFAULT_SWEEPS)
  const order = new Map<number, number>()
  const refreshOrder = (arr: number[]) => arr.forEach((id, i) => order.set(id, i))
  layers.forEach(refreshOrder)

  const inAdj = new Map<number, number[]>()
  const outMap = new Map<number, number[]>()
  for (const id of ids) {
    inAdj.set(id, [])
    outMap.set(id, [])
  }
  for (const e of dagEdges) {
    outMap.get(e.from)!.push(e.to)
    inAdj.get(e.to)!.push(e.from)
  }

  const barycenter = (id: number, neighbors: number[]): number => {
    // 邻居的「归一化层内序」（0..1），跨层宽差不影响比较；无邻居保持现位（返回现序）
    if (!neighbors.length) return order.get(id) || 0
    let sum = 0
    for (const nb of neighbors) sum += order.get(nb) || 0
    return sum / neighbors.length
  }

  for (let sweep = 0; sweep < sweeps; sweep += 1) {
    const downward = sweep % 2 === 0
    const span = layers.length
    for (let li = 0; li < span; li += 1) {
      const i = downward ? li : span - 1 - li
      if (i === 0 && downward) continue
      if (i === span - 1 && !downward) continue
      const upper = downward ? i - 1 : i + 1
      const neighborMap = downward ? inAdj : outMap
      layers[i]
        .map((id) => {
          const nbs = (neighborMap.get(id) || []).filter(
            (nb) => (layer.get(nb) || 0) === upper,
          )
          return { id, key: barycenter(id, nbs) }
        })
        .sort((a, b) => a.key - b.key || a.id - b.id)
        .forEach((row, idx) => {
          layers[i][idx] = row.id
        })
      refreshOrder(layers[i])
    }
  }

  // 阶段 4：坐标分配——层 y = 层号 × 层距；层内等距槽位、相对中轴 x=0 居中
  const pos: Record<number, Pt> = {}
  for (let i = 0; i < layers.length; i += 1) {
    const arr = layers[i]
    if (!arr.length) continue
    const maxR = Math.max(...arr.map((id) => radiusOf(id)))
    const slot = maxR * 2 + nodeGap
    arr.forEach((id, idx) => {
      pos[id] = {
        x: (idx - (arr.length - 1) / 2) * slot,
        y: i * layerGap,
      }
    })
  }
  // 层可能因无节点而空缺（极端构造），y 仍按层号走——不会产生重叠
  return pos
}
