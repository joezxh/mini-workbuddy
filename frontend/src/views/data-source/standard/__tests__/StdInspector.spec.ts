import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import { createI18n } from 'vue-i18n'
import Antd from 'ant-design-vue'
import { typeTone } from '@/components/common/graph/graphTheme'

vi.mock('@/api/dataops', () => ({
  getObject: vi.fn(() => Promise.resolve({ attributes: [{ id: 5, code: 'attr_id', name: '客户编号', required: true, security_level: 'L2' }] })),
  listObjectBindings: vi.fn(() => Promise.resolve([{ source_id: 3, db_name: 'dw', database: 'ods', table_name: 't_customer', status: 'accepted' }])),
  listRelationChecks: vi.fn(() => Promise.resolve([{ source_id: 3, database: 'ods', verdict: 'hit', confidence: 0.91 }])),
}))

import StdInspector from '../StdInspector.vue'

const M = {
  hint: 'SELECT_HINT_MARKER',
  attrs: 'ATTR_SECTION_MARKER',
  adjacent: 'ADJACENT_SECTION_MARKER',
  bound: 'BOUND_TABLES_MARKER',
  checks: 'CHECKS_SECTION_MARKER',
  action: 'ACTION_SECTION_MARKER',
}

const OBJECTS = [
  { id: 1, code: 'OBJ_CUSTOMER', name: '客户', domain: 'crm', aliases: ['customer'], status: 'published' },
]
const RELATIONS = [
  { id: 9, code: 'REL_ORDER_CUSTOMER', name: '订单属客户', from_object_id: 2, to_object_id: 1, relation_type: 'N:1', status: 'published', description: '' },
  { id: 10, code: 'REL_SERVE', name: '客户服务', from_object_id: 1, to_object_id: 3, relation_type: '1:N', status: 'draft', description: '' },
]

function ssr(props: Record<string, unknown> = {}) {
  const app = createSSRApp({
    render: () => h(StdInspector, { selected: null, objects: [], relations: [], ...props }),
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
              selectHint: M.hint,
              required: 'REQ',
              boundTables: M.bound,
              drill: 'DRILL',
              checks: M.checks,
              noChecks: 'NO_CHECKS',
              relationType: 'CARD',
              fromObject: 'SRC',
              toObject: 'TGT',
              objectDetail: 'OBJ_DETAIL',
              relationDetail: 'REL_DETAIL',
              adjacentRelations: M.adjacent,
              locateInGraph: 'LOCATE',
              statusDraft: 'DRAFT',
              statusPublished: 'PUBLISHED',
              noAttributes: 'NO_ATTRS',
              noAdjacent: 'NO_ADJ',
              noBindings: 'NO_BINDINGS',
            },
            catalog: { description: 'DESC', attributes: M.attrs },
            overview: { hit: 'HIT', missing: 'MISSING', conflict: 'CONFLICT' },
            meta: { domain: 'DOMAIN' },
            std: { aliases: 'ALIAS' },
            common: { name: 'NAME', type: 'TYPE', edit: 'EDIT', delete: 'DEL', deleteConfirm: 'CONFIRM', status: 'STATUS', actions: M.action },
          },
        },
      },
    }),
  )
  return renderToString(app)
}

// SSR 只渲染一次，且发生在 load() 里的 await 之前：因此接口桩的数据
// （引用属性列表 / 绑定行 / 校验行）不会出现在 HTML 里。组件测试只断言
// 「分区标题 + 骨架 + 从 props 池同步取到的字段」；badge 与文案映射下沉到
// inspectorFormat.spec（Step 1 已覆盖）。

describe('StdInspector', () => {
  it('未选中：kg-insp 骨架 + 点选提示', async () => {
    const html = await ssr()
    expect(html).toContain('kg-insp')
    expect(html).toContain(M.hint)
  })

  it('选中对象：类型 tag 按 code 上色，属性/邻接/绑定/操作四分区齐备', async () => {
    const html = await ssr({ selected: { kind: 'node', id: 1 }, objects: OBJECTS, relations: RELATIONS })
    expect(html).toContain('kg-type-tag')
    expect(html).toContain(typeTone('OBJ_CUSTOMER').bg)
    expect(html).toContain('OBJ_CUSTOMER')
    expect(html).toContain(M.attrs)
    expect(html).toContain(M.adjacent)
    expect(html).toContain(M.bound)
    expect(html).toContain(M.action)
    // SSR 阶段属性/绑定为空集 → 各自的空态文案而非行项目
    expect(html).toContain('NO_ATTRS')
    expect(html).toContain('NO_BINDINGS')
    expect(html).not.toContain(M.checks)
  })

  it('选中对象：邻接关系行给方向与对端名（数据同步来自 props.relations 池）', async () => {
    const html = await ssr({ selected: { kind: 'node', id: 1 }, objects: OBJECTS, relations: RELATIONS })
    expect(html).toContain('订单属客户')
    expect(html).toContain('←')
    expect(html).toContain('→')
    expect(html).toContain('kg-mini')
  })

  it('选中关系：两端链接 + 基数 + 校验分区', async () => {
    const html = await ssr({ selected: { kind: 'edge', id: 9 }, objects: OBJECTS, relations: RELATIONS })
    expect(html).toContain('订单属客户')
    expect(html).toContain('N:1')
    expect(html).toContain(M.checks)
    expect(html).toContain('kg-insp__link')
    // 校验行要 await 后才出现，SSR 下为空态文案
    expect(html).toContain('NO_CHECKS')
  })

  it('状态徽标从对象/关系池同步取到：published 绿、draft 橙', async () => {
    const pub = await ssr({
      selected: { kind: 'node', id: 1 },
      objects: [{ id: 1, code: 'OBJ_CUSTOMER', name: '客户', status: 'published' }],
      relations: [],
    })
    expect(pub).toContain('kg-badge--ok')
    const draft = await ssr({ selected: { kind: 'edge', id: 10 }, objects: OBJECTS, relations: RELATIONS })
    expect(draft).toContain('kg-badge--warn')
  })

  it('操作分区：在图中定位', async () => {
    const html = await ssr({ selected: { kind: 'node', id: 1 }, objects: OBJECTS, relations: RELATIONS })
    expect(html).toContain('LOCATE')
  })
})
