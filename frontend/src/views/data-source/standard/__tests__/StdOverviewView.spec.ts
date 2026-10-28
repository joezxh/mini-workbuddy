import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import { createI18n } from 'vue-i18n'
import Antd from 'ant-design-vue'

// 柱状图只需验证喂进去的三态数值，用桩把 option 序列化进 DOM
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
            values: props.option?.series?.[0]?.data?.map((d: any) => d.value) ?? null,
            categories: props.option?.xAxis?.data ?? null,
            title: props.option?.title?.text ?? null,
          }),
        )
    },
  },
}))

import StdOverviewView from '../StdOverviewView.vue'

const CATALOGS = 'OV_CATALOGS_MARKER'
const OBJECTS = 'OV_OBJECTS_MARKER'
const RELATIONS = 'OV_RELATIONS_MARKER'
const CHART = 'OV_CHART_MARKER'
const HIT = 'OV_HIT_MARKER'
const MISSING = 'OV_MISSING_MARKER'
const CONFLICT = 'OV_CONFLICT_MARKER'
const DEGRADED = 'OV_DEGRADED_MARKER'
const SUMMARY = 'OV_SUMMARY_MARKER'
const EMPTY = 'OV_EMPTY_MARKER'

const STATS = {
  catalogs: 2,
  objects: 5,
  relations: 3,
  relation_check: { hit: 3, missing: 1, conflict: 2 },
}

function ssr(props: Record<string, unknown>) {
  const app = createSSRApp(StdOverviewView, props)
  app.use(Antd)
  app.use(
    createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: {
        'zh-CN': {
          kbMgmt: {
            overview: {
              catalogs: CATALOGS,
              objects: OBJECTS,
              relations: RELATIONS,
              chart: CHART,
              hit: HIT,
              missing: MISSING,
              conflict: CONFLICT,
              degraded: DEGRADED,
              summary: SUMMARY,
              empty: EMPTY,
              searchPlaceholder: 'ask',
            },
          },
        },
      },
    }),
  )
  return renderToString(app)
}

/** SSR 会转义引号，断言 JSON 前还原 */
function unescapeHtml(html: string) {
  return html.replace(/&quot;/g, '"')
}

describe('StdOverviewView', () => {
  it('渲染三项计数与校验三态柱状', async () => {
    const html = unescapeHtml(await ssr({ stats: STATS }))
    expect(html).toContain(CATALOGS)
    expect(html).toContain(OBJECTS)
    expect(html).toContain(RELATIONS)
    // 图表标题进 option.title，由桩序列化后断言
    expect(html).toContain(`"title":"${CHART}"`)
    // 三态数值按 hit/missing/conflict 顺序喂给柱状图
    expect(html).toContain('"values":[3,1,2]')
    expect(html).toContain(`"categories":["${HIT}","${MISSING}","${CONFLICT}"]`)
  })

  it('无校验结论：空态替代图表', async () => {
    const zero = { catalogs: 0, objects: 0, relations: 0, relation_check: { hit: 0, missing: 0, conflict: 0 } }
    const html = await ssr({ stats: zero })
    expect(html).toContain(EMPTY)
    expect(html).not.toContain('chart-option')
  })

  it('NL 降级：只提示降级，不展示 summary', async () => {
    const html = await ssr({ stats: STATS, degraded: true, summary: '' })
    expect(html).toContain(DEGRADED)
    expect(html).not.toContain(SUMMARY)
  })

  it('NL 命中：展示 AI 解读摘要', async () => {
    const html = await ssr({ stats: STATS, degraded: false, summary: '订单通过 customer_id 关联客户' })
    expect(html).toContain(SUMMARY)
    expect(html).toContain('订单通过 customer_id 关联客户')
    expect(html).not.toContain(DEGRADED)
  })
})
