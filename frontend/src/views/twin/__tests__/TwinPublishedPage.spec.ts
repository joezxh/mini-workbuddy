import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'

// 计划注（:1221）降级：renderToString 不执行 onMounted，SSR 一次渲染拿不到异步拒绝态
// （实测初始帧为空画布）。断言意图不变——反枚举同源文案改钉 denyView 纯函数出口。
vi.mock('@/api/twin', () => ({
  getPublished: vi.fn().mockRejectedValue(
    Object.assign(new Error('x'), { response: { data: { code: 'TWIN_ACCESS_REQUIRED', message: '无权访问该页面' } } })),
  runPublished: vi.fn(),
}))
import TwinPublishedPage, { denyView } from '../TwinPublishedPage.vue'

const DENY_TEXT = '无权访问该页面'

describe('denyView（W12 反枚举同源文案）', () => {
  it('任何错误 → 同一拒绝文案，不泄露拒绝原因差异', () => {
    for (const err of [
      { code: 'TWIN_NOT_FOUND' },                                  // 未知 slug
      { code: 'TWIN_ACCESS_REQUIRED', message: 'x' },              // 角色不命中
      Object.assign(new Error('boom'), { response: { status: 403 } }), // 跨租/停用（HTTP 层）
      'string-err',
    ]) {
      expect(denyView(err)).toEqual({ show: true, text: DENY_TEXT })
    }
  })
  it('无错误 → 不展示拒绝视图', () => {
    expect(denyView(null)).toEqual({ show: false, text: '' })
  })
})

describe('TwinPublishedPage 初始渲染', () => {
  it('SSR 初始帧为唯一画布（widget-grid run），非拒绝视图', async () => {
    const html = await renderToString(createSSRApp(TwinPublishedPage, { slug: 'zzz' }))
    expect(html).toContain('widget-grid run')
    expect(html).not.toContain(DENY_TEXT)   // 拒绝态由 denyView 驱动，初始 err=null
  })
})
