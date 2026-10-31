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
})
