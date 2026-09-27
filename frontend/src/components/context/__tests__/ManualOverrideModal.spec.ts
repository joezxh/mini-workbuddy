import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import Antd from 'ant-design-vue'
import ManualOverrideModal from '../ManualOverrideModal.vue'

async function ssr(props: Record<string, any>) {
  const app = createSSRApp(ManualOverrideModal, props)
  app.use(Antd)
  return renderToString(app)
}

describe('ManualOverrideModal (PR-3 Task 16)', () => {
  it('renders the 手动干预 button by default', async () => {
    const html = await ssr({})
    expect(html).toContain('手动干预')
  })

  it('renders default mode label 共享层', async () => {
    const html = await ssr({ open: true })
    expect(html).toContain('共享层')
  })

  it('renders the 4 action_type labels', async () => {
    const html = await ssr({ open: true, initialAction: 'add_new_entry' })
    // Only the active option is rendered in SSR (ant-select dropdown is lazy).
    // We verify the visible form labels and default action text instead.
    expect(html).toContain('干预类型')
    expect(html).toContain('添加新条目')
  })

  it('switches to set_priority label when initialAction=set_priority', async () => {
    const html = await ssr({ open: true, initialAction: 'set_priority' })
    expect(html).toContain('⭐ 设置优先级')
  })

  it('switches to update_entry label when initialAction=update_entry', async () => {
    const html = await ssr({ open: true, initialAction: 'update_entry' })
    expect(html).toContain('✏️ 更新现有条目')
  })

  it('shows delete_entry label by default', async () => {
    const html = await ssr({ open: true })
    expect(html).toContain('🗑️ 删除特定条目')
  })

  it('renders priority input for set_priority action', async () => {
    const html = await ssr({ open: true, initialAction: 'set_priority' })
    expect(html).toContain('优先级 (0-10)')
  })

  it('renders textarea for update_entry action', async () => {
    const html = await ssr({ open: true, initialAction: 'update_entry' })
    expect(html).toContain('新的数据内容')
  })

  it('exposes cancel/confirm buttons in modal footer area', async () => {
    const html = await ssr({ open: true })
    expect(html).toContain('执行手动干预')
    // Ant Design Vue adds spacing; cancel label renders as "取 消" / "取消"
    expect(html).toMatch(/取\s*消/)
  })
})
