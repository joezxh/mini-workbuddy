import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import Antd from 'ant-design-vue'
import GraphCanvas from '../GraphCanvas.vue'
import { typeTone } from '../graphTheme'

const NODES = [
  { id: 1, name: '客户', code: 'OBJ_CUSTOMER', color: typeTone('OBJ_CUSTOMER').color, typeLabel: '客户' },
  { id: 2, name: '订单', code: 'OBJ_ORDER', color: typeTone('OBJ_ORDER').color, typeLabel: 'ORDER' },
  { id: 3, name: '部门', code: 'OBJ_DEPT', color: typeTone('OBJ_DEPT').color, typeLabel: '部门' },
]
const EDGES = [
  { id: 11, from: 2, to: 1, label: '订单属客户', code: 'REL_ORDER_CUSTOMER' },
  { id: 12, from: 3, to: 1, label: '客户服务', code: 'REL_SERVE' },
]

const TEXT = {
  hintText: 'HINT_TEXT',
  legendSizeText: 'LEGEND_SIZE',
  emptyTitle: 'EMPTY_TITLE',
  emptyDesc: 'EMPTY_DESC',
}

function ssr(props: Record<string, unknown> = {}) {
  const app = createSSRApp({
    render: () => h(GraphCanvas, { nodes: [], edges: [], selection: null, ...TEXT, ...props }),
  })
  app.use(Antd)
  return renderToString(app)
}

/** 造一张真实规模的图（kb=12 全库图量级：65 实体 / 46 关系） */
function bigGraph(nodeCount: number, edgeCount: number) {
  const nodes = Array.from({ length: nodeCount }, (_, i) => ({
    id: i + 1,
    name: `实体${i + 1}`,
    code: i === 0 ? 'OBJ_CUSTOMER' : 'OBJ_ORDER',
    color: '#3371fc',
    typeLabel: i === 0 ? '客户' : '订单',
  }))
  const edges = Array.from({ length: edgeCount }, (_, i) => ({
    id: 1000 + i,
    from: (i % nodeCount) + 1,
    to: ((i * 7) % nodeCount) + 1,
    label: `关系${i}`,
    code: 'REL_ORDER_CUSTOMER',
  })).filter((e) => e.from !== e.to)
  return { nodes, edges }
}

/** 从 SSR 结果里取节点圆盘（渲染顺序与 props.nodes 一致） */
function circles(html: string) {
  return [...html.matchAll(/<circle cx="([\d.-]+)" cy="([\d.-]+)" r="([\d.-]+)"/g)].map((m) => ({
    x: Number(m[1]),
    y: Number(m[2]),
    r: Number(m[3]),
  }))
}

/** 从 SSR 结果里取每条边的可见路径（起点 / 终点） */
function edgeLines(html: string) {
  return [...html.matchAll(/class="kg-edge__line"[^>]*d="M([\d.-]+),([\d.-]+) [^"]* ([\d.-]+),([\d.-]+)"/g)].map(
    (m) => ({
      sx: Number(m[1]),
      sy: Number(m[2]),
      tx: Number(m[3]),
      ty: Number(m[4]),
    }),
  )
}

describe('GraphCanvas', () => {
  it('渲染画布骨架与皮肤作用域类名', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain('kg-canvas')
    expect(html).toContain('kg-canvas__svg')
    expect(html).toContain('kg-canvas__hint')
    expect(html).toContain(TEXT.hintText)
  })

  it('同码同色：circle 的 fill 取 props.color', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain(`fill="${typeTone('OBJ_CUSTOMER').color}"`)
    expect(html).toContain('kg-node__name')
    expect(html).toContain('客户')
  })

  it('布局确定性：同输入两次渲染坐标一致', async () => {
    const a = await ssr({ nodes: NODES, edges: EDGES })
    const b = await ssr({ nodes: NODES, edges: EDGES })
    const cx = (html: string) => (html.match(/cx="([\d.]+)"/g) || []).join(',')
    expect(cx(a)).toBe(cx(b))
    expect(cx(a)).not.toBe('')
  })

  it('图例：按节点数降序列出可见 code + 度数说明', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain('kg-canvas__legend')
    expect(html).toContain(TEXT.legendSizeText)
    // 每个 code 各 1 个节点：三者都出现
    expect(html).toContain('客户')
    expect(html).toContain('部门')
  })

  it('选中节点：该节点 is-on，非邻居淡化，邻边 is-hl', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES, selection: { kind: 'node', id: 2 } })
    expect(html).toContain('is-on kg-node')
    expect(html).toContain('opacity:0.35')
    expect(html).toContain('is-hl kg-edge')
  })

  it('无选中但有命中集：命中节点 is-hit，其余淡化；选中优先于命中集', async () => {
    const html = await ssr({
      nodes: NODES,
      edges: EDGES,
      focusNodeCodes: ['OBJ_ORDER'],
      focusEdgeCodes: ['REL_ORDER_CUSTOMER'],
    })
    expect(html).toContain('is-hit')
    expect(html).toContain('opacity:0.35')

    const both = await ssr({
      nodes: NODES,
      edges: EDGES,
      selection: { kind: 'node', id: 1 },
      focusNodeCodes: ['OBJ_ORDER'],
    })
    // 有选中时走邻接语义：节点 2 是节点 1 的邻居 → 不淡化
    expect(both).not.toContain('opacity:0.35')
  })

  it('空态：标题/说明/按钮，且不渲染任何节点', async () => {
    const html = await ssr({ nodes: [], edges: [], emptyActionText: 'GO_BACK' })
    expect(html).toContain(TEXT.emptyTitle)
    expect(html).toContain(TEXT.emptyDesc)
    expect(html).toContain('GO_BACK')
    expect(html).not.toContain('kg-node"')
  })

  it('loading：遮罩层出现', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES, loading: true })
    expect(html).toContain('kg-canvas__mask')
  })

  it('有向关系：箭头模板存在，且可见边线绑定 marker-end', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toMatch(/<marker[^>]*id="kg-arrow"/)
    expect(html).toContain('marker-end="url(#kg-arrow)"')
  })

  it('选中/邻接的边换用高亮箭头，方向语义跟手', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES, selection: { kind: 'node', id: 2 } })
    expect(html).toContain('marker-end="url(#kg-arrow-hl)"')
  })

  it('边端点按节点半径裁剪：路径不落在圆心，箭头不被圆盘盖住', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    const discs = circles(html)
    const lines = edgeLines(html)
    expect(lines.length).toBe(EDGES.length)
    // EDGES：2→1、3→1（下标 = id-1）
    const pairs: [number, number][] = EDGES.map((e) => [e.from - 1, e.to - 1])
    lines.forEach((line, i) => {
      const [a, b] = pairs[i]
      const fromGap = Math.hypot(line.sx - discs[a].x, line.sy - discs[a].y)
      const toGap = Math.hypot(line.tx - discs[b].x, line.ty - discs[b].y)
      expect(fromGap).toBeGreaterThan(discs[a].r)
      expect(toGap).toBeGreaterThan(discs[b].r)
    })
  })

  it('真实规模（>40 边）：关系标签不被静默抑制', async () => {
    const g = bigGraph(65, 46)
    expect(g.edges.length).toBeGreaterThan(40)
    const html = await ssr(g)
    expect(html).toContain('kg-edge__label')
    expect(html).toContain('关系1')
  })

  it('真实规模（>60 节点）：节点名不被静默抑制（否则满屏孤点）', async () => {
    const html = await ssr(bigGraph(65, 46))
    expect(html).toContain('实体2')
    expect(html).toContain('实体40')
  })

  // ── 分层布局（Sugiyama，layout=layered）────────────────────────────────
  it('分层布局：边方向自上而下（被指向的实体层级更低、y 更大）', async () => {
    // EDGES：2→1、3→1 → 节点 1 在下层（y 更大）
    const html = await ssr({ nodes: NODES, edges: EDGES, layout: 'layered' })
    const cs = circles(html)
    expect(cs.length).toBe(3)
    expect(cs[0].y).toBeGreaterThan(cs[1].y)
    expect(cs[0].y).toBeGreaterThan(cs[2].y)
  })

  it('分层布局确定性：同输入两次 SSR 坐标逐字节一致', async () => {
    const a = await ssr({ nodes: NODES, edges: EDGES, layout: 'layered' })
    const b = await ssr({ nodes: NODES, edges: EDGES, layout: 'layered' })
    const cx = (html: string) => (html.match(/cx="([\d.]+)"/g) || []).join(',')
    expect(cx(a)).toBe(cx(b))
    expect(cx(a)).not.toBe('')
  })

  it('分层布局真实规模：65 节点 / 46 边全部有坐标（无 NaN 圆盘）', async () => {
    const html = await ssr({ ...bigGraph(65, 46), layout: 'layered' })
    expect(circles(html).length).toBe(65)
  })

  it('缩放按钮组：＋/−/复位三个按钮渲染', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain('kg-canvas__zoom')
    expect((html.match(/kg-canvas__zoom[\s\S]*?<\/div>/) || [''])[0].split('<button').length - 1).toBe(3)
  })
})
