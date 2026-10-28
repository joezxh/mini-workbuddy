import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import { createI18n } from 'vue-i18n'
import Antd from 'ant-design-vue'

// 检视面板的数据全来自接口：桩掉 api 模块，SSR 期间不发真实请求
vi.mock('@/api/dataops', () => ({
  getObject: vi.fn(() => Promise.resolve({ attributes: [] })),
  listObjectBindings: vi.fn(() => Promise.resolve([])),
  listRelationChecks: vi.fn(() => Promise.resolve([])),
}))

import StdInspector from '../StdInspector.vue'

const HINT_MARKER = 'SELECT_HINT_MARKER'
const ATTR_MARKER = 'ATTR_SECTION_MARKER'
const BOUND_MARKER = 'BOUND_TABLES_MARKER'
const CHECKS_MARKER = 'CHECKS_SECTION_MARKER'

const OBJECTS = [{ id: 1, code: 'obj_customer', name: '客户', domain: 'crm', aliases: [] }]
const RELATIONS = [
  {
    id: 9,
    code: 'rel_order_customer',
    name: '订单属客户',
    from_object_id: 2,
    to_object_id: 1,
    relation_type: 'N:1',
  },
]

function ssr(props: Record<string, unknown>) {
  const app = createSSRApp(StdInspector, props)
  app.use(Antd)
  app.use(
    createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: {
        'zh-CN': {
          kbMgmt: {
            graph: {
              selectHint: HINT_MARKER,
              required: 'required',
              boundTables: BOUND_MARKER,
              drill: 'drill',
              checks: CHECKS_MARKER,
              noChecks: 'no-checks',
              relationType: 'relation-type',
              fromTo: 'from-to',
            },
            catalog: { description: 'description', attributes: ATTR_MARKER },
            meta: { domain: 'domain' },
            std: { aliases: 'aliases' },
            common: { edit: 'edit', delete: 'delete', deleteConfirm: 'confirm' },
          },
        },
      },
    }),
  )
  return renderToString(app)
}

describe('StdInspector', () => {
  it('未选中：渲染点选提示', async () => {
    const html = await ssr({ selected: null, objects: [], relations: [] })
    expect(html).toContain(HINT_MARKER)
  })

  it('选中对象：渲染定义、属性与绑定表分区', async () => {
    const html = await ssr({ selected: { kind: 'node', id: 1 }, objects: OBJECTS, relations: [] })
    expect(html).toContain('客户')
    expect(html).toContain('obj_customer')
    expect(html).toContain(ATTR_MARKER)
    expect(html).toContain(BOUND_MARKER)
    expect(html).not.toContain(HINT_MARKER)
  })

  it('选中关系：渲染关系两端与校验分区', async () => {
    const html = await ssr({ selected: { kind: 'edge', id: 9 }, objects: OBJECTS, relations: RELATIONS })
    expect(html).toContain('订单属客户')
    expect(html).toContain('N:1')
    expect(html).toContain(CHECKS_MARKER)
    // to 端对象名由 objects 池解析
    expect(html).toContain('客户')
  })
})
