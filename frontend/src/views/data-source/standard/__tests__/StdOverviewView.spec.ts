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
const CHECK_CONCLUSION = 'OV_CONCLUSION_MARKER'
const CHECK_PASS = 'OV_PASS_MARKER'
const CHECK_FAIL = 'OV_FAIL_MARKER'
const NO_RELATION = 'OV_NO_RELATION_MARKER'
const NO_RELATION_HINT = 'OV_NO_RELATION_HINT_MARKER'
const HAS_RELATION = 'OV_HAS_RELATION_MARKER'
const HAS_RELATION_HINT = 'OV_HAS_RELATION_HINT_MARKER'
const DEGRADED_REASON = 'OV_DEGRADED_REASON_MARKER'
const FALLBACK = 'OV_FALLBACK_MARKER'
const KEYWORD_RESULT = 'OV_KEYWORD_RESULT_MARKER'
const KEYWORD_SUMMARY = 'OV_KEYWORD_SUMMARY_MARKER'
const HIT_OBJECTS = 'OV_HIT_OBJECTS_MARKER'
const HIT_RELATIONS = 'OV_HIT_RELATIONS_MARKER'
const NO_HIT = 'OV_NO_HIT_MARKER'
const VIEW_IN_GRAPH = 'OV_VIEW_IN_GRAPH_MARKER'

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
              searchHint: 'hint',
              checkConclusion: `${CHECK_CONCLUSION} total={total} hit={hit} missing={missing} conflict={conflict}`,
              checkPass: CHECK_PASS,
              checkFail: `${CHECK_FAIL} missing={missing} conflict={conflict}`,
              noCheckNoRelation: NO_RELATION,
              noCheckNoRelationHint: NO_RELATION_HINT,
              noCheckHasRelation: `${HAS_RELATION} n={n}`,
              noCheckHasRelationHint: HAS_RELATION_HINT,
              degradedReason: `${DEGRADED_REASON} {reason}`,
              fallbackNotice: FALLBACK,
              keywordResult: KEYWORD_RESULT,
              keywordSummary: `${KEYWORD_SUMMARY} objects={objects} relations={relations}`,
              hitObjects: HIT_OBJECTS,
              hitRelations: HIT_RELATIONS,
              noHit: NO_HIT,
              viewInGraph: VIEW_IN_GRAPH,
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

  it('无校验结论：空态替代图表，并区分「没建关系」', async () => {
    const zero = { catalogs: 0, objects: 0, relations: 0, relation_check: { hit: 0, missing: 0, conflict: 0 } }
    const html = await ssr({ stats: zero })
    expect(html).toContain(EMPTY)
    expect(html).not.toContain('chart-option')
    // 不能只丢一句「暂无校验结论」，要补解释与下一步
    expect(html).toContain(NO_RELATION)
    expect(html).toContain(NO_RELATION_HINT)
  })

  it('无校验结论但已建关系：提示去执行校验', async () => {
    const noCheck = { catalogs: 1, objects: 4, relations: 3, relation_check: { hit: 0, missing: 0, conflict: 0 } }
    const html = await ssr({ stats: noCheck })
    expect(html).not.toContain('chart-option')
    expect(html).toContain(`${HAS_RELATION} n=3`)
    expect(html).toContain(HAS_RELATION_HINT)
    expect(html).not.toContain(NO_RELATION)
  })

  it('有校验结论：三态数值与整体判定都写出来', async () => {
    const html = await ssr({ stats: STATS })
    expect(html).toContain(`${CHECK_CONCLUSION} total=6 hit=3 missing=1 conflict=2`)
    // 存在缺失/冲突 → 不能报通过
    expect(html).toContain(`${CHECK_FAIL} missing=1 conflict=2`)
    expect(html).not.toContain(CHECK_PASS)
  })

  it('全部命中：整体判定为通过', async () => {
    const ok = { catalogs: 1, objects: 2, relations: 1, relation_check: { hit: 5, missing: 0, conflict: 0 } }
    const html = await ssr({ stats: ok })
    expect(html).toContain('total=5 hit=5 missing=0 conflict=0')
    expect(html).toContain(CHECK_PASS)
    expect(html).not.toContain(CHECK_FAIL)
  })

  it('NL 降级：提示降级原因并说明已降级为关键字检索', async () => {
    const html = await ssr({ stats: STATS, degraded: true, degradedReason: 'no model' })
    expect(html).toContain(DEGRADED)
    expect(html).toContain(`${DEGRADED_REASON} no model`)
    expect(html).toContain(FALLBACK)
    expect(html).not.toContain(SUMMARY)
  })

  it('关键字命中：展示命中 code 与跳转入口', async () => {
    const html = await ssr({
      stats: STATS,
      degraded: true,
      hits: { objects: ['obj_order', 'obj_customer'], relations: ['rel_order_customer'] },
    })
    expect(html).toContain(KEYWORD_RESULT)
    expect(html).toContain(`${KEYWORD_SUMMARY} objects=2 relations=1`)
    expect(html).toContain(HIT_OBJECTS)
    expect(html).toContain('obj_order')
    expect(html).toContain(HIT_RELATIONS)
    expect(html).toContain('rel_order_customer')
    expect(html).toContain(VIEW_IN_GRAPH)
    // 降级时不能把关键字结果包装成「AI 解读」
    expect(html).not.toContain(SUMMARY)
  })

  it('检索无命中：给出可行动的提示', async () => {
    const html = await ssr({ stats: STATS, searchEmpty: true })
    expect(html).toContain(NO_HIT)
    expect(html).not.toContain(VIEW_IN_GRAPH)
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
