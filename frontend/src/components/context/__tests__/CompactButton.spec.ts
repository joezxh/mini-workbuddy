import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h, defineComponent } from 'vue'
import Antd from 'ant-design-vue'
import CompactButton from '../CompactButton.vue'

/**
 * Task 15: CompactButton
 *
 * 9 模式通用压缩按钮:
 *  - props.mode: 9 模式之一(默认 'shared')
 *  - props.contextKey: 要压缩的上下文件键(默认 'default')
 *  - 点击触发 useCrossModeCompaction.triggerCompaction
 *  - 展示策略下拉(sliding_window / priority_eviction / access_based / summary_and_keep_latest)
 *  - emit compaction-success 事件携带 CompactionResponse
 *  - 失败时显示错误状态
 */
async function ssr(props: Record<string, any>) {
  const app = createSSRApp(CompactButton, props)
  app.use(Antd)
  return renderToString(app)
}

describe('CompactButton (PR-3 Task 15)', () => {
  it('renders 压缩上下文 button by default', async () => {
    const html = await ssr({ mode: 'shared', contextKey: 'k1' })
    expect(html).toContain('压缩上下文')
  })

  it('renders different label when result is success', async () => {
    const html = await ssr({
      mode: 'shared',
      contextKey: 'k1',
      lastResult: {
        success: true,
        mode: 'shared',
        key: 'k1',
        strategy: 'sliding_window',
        entries_before: 10,
        entries_after: 5,
        tokens_before: 1000,
        tokens_after: 600,
        compaction_ratio: 1.67,
        compacted_at: '2026-09-27T00:00:00Z',
      },
    })
    // After success the button label flips to 优化上下文
    expect(html).toContain('优化上下文')
  })

  it('shows error message when lastError is set', async () => {
    const html = await ssr({
      mode: 'shared',
      contextKey: 'k1',
      lastError: 'Mem0 不可达',
    })
    expect(html).toContain('Mem0 不可达')
  })

  it('reflects isCompacting disabled state via prop', async () => {
    const html = await ssr({ mode: 'skill', contextKey: 'k', isCompacting: true })
    // Ant Design Vue 渲染 loading 时输出 ant-btn-loading + disabled 属性
    expect(html).toContain('ant-btn-loading')
    expect(html).toMatch(/\bdisabled\b/)
  })

  it('uses 9-mode display label', async () => {
    const html = await ssr({ mode: 'deep_research', contextKey: 'k' })
    expect(html).toContain('deep_research')
  })
})
