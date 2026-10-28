import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import { createI18n } from 'vue-i18n'
import Antd from 'ant-design-vue'
import StdCatalogTree from '../StdCatalogTree.vue'

/** 用可辨识的占位文案替换真实 i18n，避免断言依赖翻译内容 */
const EMPTY_MARKER = 'CATALOG_EMPTY_MARKER'
const TREE = [
  {
    id: 1,
    parent_id: null,
    code: 'ecom',
    name: '电商场景',
    children: [{ id: 2, parent_id: 1, code: 'order', name: '订单域', children: [] }],
  },
]

function ssr(props: Record<string, unknown>) {
  const app = createSSRApp(StdCatalogTree, props)
  app.use(Antd)
  app.use(
    createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: { 'zh-CN': { kbMgmt: { catalog: { empty: EMPTY_MARKER } } } },
    }),
  )
  return renderToString(app)
}

describe('StdCatalogTree', () => {
  it('有数据：渲染目录名（含子节点）', async () => {
    const html = await ssr({ treeData: TREE })
    expect(html).toContain('电商场景')
    expect(html).toContain('订单域')
    expect(html).not.toContain(EMPTY_MARKER)
  })

  it('无数据：渲染空态文案', async () => {
    const html = await ssr({ treeData: [] })
    expect(html).toContain(EMPTY_MARKER)
  })
})
