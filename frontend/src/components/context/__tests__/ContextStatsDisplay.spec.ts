import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import Antd from 'ant-design-vue'
import ContextStatsDisplay from '../ContextStatsDisplay.vue'

const sampleBreakdown = [
  { source_mode: 'skill', entry_count: 12 },
  { source_mode: 'agent', entry_count: 4 },
  { source_mode: 'deep_research', entry_count: 2 },
]

const sampleStrategies = [
  { source_mode: 'skill', write_mem0: true, ttl_hours: 168 },
  { source_mode: 'agent', write_mem0: true, ttl_hours: 720 },
]

async function ssr(props: Record<string, any>) {
  const app = createSSRApp(ContextStatsDisplay, props)
  app.use(Antd)
  return renderToString(app)
}

describe('ContextStatsDisplay (PR-3 Task 15)', () => {
  it('renders the 上下文统计 header', async () => {
    const html = await ssr({ breakdown: sampleBreakdown, strategies: sampleStrategies })
    expect(html).toContain('上下文统计')
  })

  it('shows total entries count', async () => {
    const html = await ssr({ breakdown: sampleBreakdown })
    // 12 + 4 + 2 = 18
    expect(html).toContain('18')
  })

  it('renders per-mode table rows', async () => {
    const html = await ssr({ breakdown: sampleBreakdown })
    expect(html).toContain('skill')
    expect(html).toContain('agent')
    expect(html).toContain('deep_research')
  })

  it('shows empty state when breakdown is empty', async () => {
    const html = await ssr({ breakdown: [], strategies: [] })
    expect(html).toContain('暂无数据')
  })

  it('displays Mem0 indicator when write_mem0=true', async () => {
    const html = await ssr({
      breakdown: [{ source_mode: 'skill', entry_count: 1 }],
      strategies: sampleStrategies,
    })
    expect(html).toContain('Mem0')
  })

  it('displays refresh button', async () => {
    const html = await ssr({ breakdown: sampleBreakdown })
    expect(html).toContain('刷新')
  })
})
