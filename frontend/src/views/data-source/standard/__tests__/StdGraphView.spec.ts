import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import { createI18n } from 'vue-i18n'
import Antd from 'ant-design-vue'
import { typeTone } from '@/components/common/graph/graphTheme'

import StdGraphView from '../StdGraphView.vue'

const EMPTY_TITLE = 'GRAPH_EMPTY_TITLE'
const HINT = 'GRAPH_HINT'

const NODES = [
  { id: 1, code: 'OBJ_CUSTOMER', name: '客户', domain: 'crm', catalog_id: 1, status: 'published' },
  { id: 2, code: 'OBJ_ORDER', name: '订单', domain: 'trade', catalog_id: 1, status: 'published' },
]
const EDGES = [
  { id: 9, code: 'REL_ORDER_CUSTOMER', name: '订单属客户', from: 2, to: 1, relation_type: 'N:1', catalog_id: 1 },
]

function ssr(props: Record<string, unknown> = {}) {
  const app = createSSRApp({
    render: () => h(StdGraphView, { nodes: [], edges: [], selection: null, ...props }),
  })
  app.use(Antd)
  app.use(
    createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: {
        'zh-CN': {
          kbMgmt: {
            graph: {
              selectHint: HINT,
              legendNodeSize: 'LEGEND_SIZE',
              empty: EMPTY_TITLE,
              graphEmptyDesc: 'EMPTY_DESC',
              modeFull: 'FULL_MODE',
            },
          },
        },
      },
    }),
  )
  return renderToString(app)
}

describe('StdGraphView', () => {
  it('不再依赖 ECharts：渲染的是 SVG 画布', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain('kg-canvas__svg')
    expect(html).not.toContain('echarts')
  })

  it('节点按对象标准 code 分色，边标签取关系标准 name', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain(`fill="${typeTone('OBJ_CUSTOMER').color}"`)
    expect(html).toContain(`fill="${typeTone('OBJ_ORDER').color}"`)
    expect(html).toContain('订单属客户')
    // 基数不上边（原型边标签是语义名）
    expect(html).not.toContain('N:1')
  })

  it('图例与提示胶囊文案来自 kbMgmt.graph', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain(HINT)
    expect(html).toContain('LEGEND_SIZE')
  })

  it('空节点：空态而不是画布节点', async () => {
    const html = await ssr({ nodes: [], edges: [] })
    expect(html).toContain(EMPTY_TITLE)
    expect(html).not.toContain('kg-node"')
  })

  it('选中节点：画布标记 is-on', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES, selection: { kind: 'node', id: 2 } })
    expect(html).toContain('is-on')
  })

  it('NL 命中集当焦点：命中节点 is-hit', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES, highlightCodes: ['OBJ_ORDER'] })
    expect(html).toContain('is-hit')
  })
})
