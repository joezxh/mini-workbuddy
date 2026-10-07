import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import Antd from 'ant-design-vue'
import WikiHome from '../index.vue'

// SSR 环境为 node（无 window）：@/api/wiki → @/utils/request → @/router 会在模块加载期
// 调用 createWebHistory() 并抛 ReferenceError。用工厂式 mock 阻断该加载链。
vi.mock('@/api/wiki', () => ({
  listArticles: vi.fn(), createArticle: vi.fn(),
  createCategory: vi.fn(), updateCategory: vi.fn(), deleteCategory: vi.fn(),
  listCategories: vi.fn(), searchArticles: vi.fn(),
  listKnowledges: vi.fn(), createKnowledge: vi.fn(),
  updateKnowledge: vi.fn(), deleteKnowledge: vi.fn(),
}))
vi.mock('@/api/kb', () => ({ exportOkfBundle: vi.fn(), importOkfBundle: vi.fn() }))

/** 用可辨识的占位文案替换真实 i18n，避免断言依赖翻译内容 */
const TITLE = 'WIKI_TITLE_MARKER'

function makeI18n() {
  return createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': { kmsWiki: { title: TITLE } } },
  })
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
}

async function ssr(props: Record<string, unknown> = {}) {
  const app = createSSRApp(WikiHome, props)
  app.use(Antd)
  app.use(makeI18n())
  app.use(makeRouter())
  return renderToString(app)
}

describe('wiki/index.vue embedded prop', () => {
  it('默认（非内嵌）：渲染标题且不带 embedded 修饰类', async () => {
    const html = await ssr()
    expect(html).toContain(TITLE)
    expect(html).not.toContain('wiki-index--embedded')
  })

  it('embedded=true：不渲染标题且带 embedded 修饰类', async () => {
    const html = await ssr({ embedded: true })
    expect(html).not.toContain(TITLE)
    expect(html).toContain('wiki-index--embedded')
  })
})
