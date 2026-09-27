import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import Antd from 'ant-design-vue'
import ContextHistoryList from '../ContextHistoryList.vue'

const sampleEntries = [
  {
    id: 1,
    session_id: 100,
    source_mode: 'skill',
    context_key: 'skill_100_t1',
    context_data: { skill_name: 'report_gen', result: '已生成' },
    context_tags: ['skill', 'report_gen'],
    priority: 2,
    is_cross_mode_accessible: false,
    case_number: 'default',
    expires_at: null,
    created_at: '2026-09-27T01:23:45Z',
    last_accessed: null,
  },
  {
    id: 2,
    session_id: 100,
    source_mode: 'agent',
    context_key: 'agent_100_t2',
    context_data: { agent_name: 'a1', final_answer: 'x' },
    context_tags: ['agent'],
    priority: 2,
    is_cross_mode_accessible: true,
    case_number: null,
    expires_at: null,
    created_at: '2026-09-27T02:00:00Z',
    last_accessed: null,
  },
]

async function ssr(props: Record<string, any>) {
  const app = createSSRApp(ContextHistoryList, props)
  app.use(Antd)
  return renderToString(app)
}

describe('ContextHistoryList (PR-3 Task 14)', () => {
  it('shows empty state when entries is empty', async () => {
    const html = await ssr({ entries: [] })
    expect(html).toContain('暂无历史记录')
  })

  it('renders source_mode tag for each entry', async () => {
    const html = await ssr({ entries: sampleEntries })
    expect(html).toContain('skill')
    expect(html).toContain('agent')
  })

  it('shows 跨模式可读 badge when is_cross_mode_accessible=true', async () => {
    const html = await ssr({ entries: sampleEntries })
    expect(html).toContain('跨模式可读')
  })

  it('renders context_tags', async () => {
    const html = await ssr({ entries: sampleEntries })
    expect(html).toContain('report_gen')
  })

  it('renders formatted created_at time', async () => {
    const html = await ssr({ entries: sampleEntries })
    expect(html).toContain('2026')
  })

  it('renders JSON-formatted context_data preview', async () => {
    const html = await ssr({ entries: sampleEntries })
    expect(html).toContain('skill_name')
    expect(html).toContain('report_gen')
  })
})
