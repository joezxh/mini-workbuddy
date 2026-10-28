import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import { createI18n } from 'vue-i18n'
import Antd from 'ant-design-vue'

// node 环境无 canvas，且不需要真实渲染：用桩组件把传入的 option 序列化进 DOM
vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChartStub',
    props: { option: { type: Object, default: () => ({}) } },
    setup(props: any) {
      return () =>
        h(
          'pre',
          { class: 'chart-option' },
          JSON.stringify({
            nodes: props.option?.series?.[0]?.data?.length ?? -1,
            links: props.option?.series?.[0]?.links?.length ?? -1,
            first: props.option?.series?.[0]?.data?.[0]?.name ?? null,
            sizes: props.option?.series?.[0]?.data?.map((d: any) => d.symbolSize) ?? null,
          }),
        )
    },
  },
}))

import StdGraphView from '../StdGraphView.vue'

const EMPTY_MARKER = 'GRAPH_EMPTY_MARKER'

const NODES = [
  { id: 1, code: 'obj_customer', name: '客户', domain: 'crm', catalog_id: 1, status: 'published' },
  { id: 2, code: 'obj_order', name: '订单', domain: 'trade', catalog_id: 1, status: 'published' },
]
const EDGES = [{ id: 9, code: 'rel_order_customer', from: 2, to: 1, relation_type: 'N:1', catalog_id: 1 }]

function ssr(props: Record<string, unknown>) {
  const app = createSSRApp(StdGraphView, props)
  app.use(Antd)
  app.use(
    createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: { 'zh-CN': { kbMgmt: { graph: { empty: EMPTY_MARKER } } } },
    }),
  )
  return renderToString(app)
}

/** SSR 会把属性与文本里的引号转义成 &quot;，断言前还原 */
function unescapeHtml(html: string) {
  return html.replace(/&quot;/g, '"')
}

describe('StdGraphView', () => {
  it('nodes/edges 映射进 series.data 与 series.links', async () => {
    const html = unescapeHtml(await ssr({ nodes: NODES, edges: EDGES }))
    expect(html).toContain('"nodes":2')
    expect(html).toContain('"links":1')
    expect(html).toContain('"first":"客户"')
  })

  it('无节点：渲染空态而不是图表', async () => {
    const html = await ssr({ nodes: [], edges: [] })
    expect(html).toContain(EMPTY_MARKER)
    expect(html).not.toContain('chart-option')
  })

  it('highlightCodes 命中时放大节点', async () => {
    const html = unescapeHtml(await ssr({ nodes: NODES, edges: EDGES, highlightCodes: ['obj_order'] }))
    // obj_customer 未命中=48，obj_order 命中=64
    expect(html).toContain('"sizes":[48,64]')
  })
})
