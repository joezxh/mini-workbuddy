import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, defineComponent, h } from 'vue'
import Antd from 'ant-design-vue'

// Stub the contexts store + composable to avoid axios/network in unit tests.
const strategiesRef: { value: any[] } = { value: [] }
const breakdownRef: { value: any[] } = { value: [] }
const entriesByModeRef: { value: Record<string, any[]> } = { value: {} }
const loadingRef: { value: boolean } = { value: false }
const lastErrorRef: { value: any } = { value: null }

// loadAll is a no-op by default — tests opt-in to populate strategies/breakdown.
const loadAll = vi.fn(async () => {})

vi.mock('@/stores/contexts', () => {
  return {
    useContextsStore: () => ({
      strategies: strategiesRef,
      breakdown: breakdownRef,
      entriesByMode: entriesByModeRef,
      loading: loadingRef,
      lastError: lastErrorRef,
      loadAll,
      loadStrategies: vi.fn(),
      loadBreakdown: vi.fn(),
      loadEntriesByMode: vi.fn(async (_sid: number, mode: string) => {
        entriesByModeRef.value = {
          ...entriesByModeRef.value,
          [mode]: [{ id: 1, source_mode: mode }],
        }
      }),
      findBucket: (mode: string) =>
        breakdownRef.value.find((b: any) => b.source_mode === mode),
      reset: vi.fn(),
    }),
  }
})

// Inline-import CrossModeStatsPage AFTER mocking the store.
import CrossModeStatsPage from '../CrossModeStatsPage.vue'

async function ssr(props: Record<string, any>) {
  const Wrapper = defineComponent({
    setup() {
      return () => h(CrossModeStatsPage, props)
    },
  })
  const app = createSSRApp(Wrapper)
  app.use(Antd)
  return renderToString(app)
}

describe('CrossModeStatsPage (PR-3 Task 17)', () => {
  beforeEach(() => {
    strategiesRef.value = []
    breakdownRef.value = []
    entriesByModeRef.value = {}
    loadingRef.value = false
    lastErrorRef.value = null
    loadAll.mockClear()
  })

  it('renders page header 跨模式上下文记忆', async () => {
    const html = await ssr({ sessionId: 1 })
    expect(html).toContain('跨模式上下文记忆')
  })

  it('renders refresh button', async () => {
    const html = await ssr({ sessionId: 1 })
    // Ant Design Vue adds spacing; "刷 新" is rendered
    expect(html).toMatch(/刷\s*新/)
  })

  it('renders 9-mode fallback list when strategies empty', async () => {
    const html = await ssr({ sessionId: 1 })
    // strategies stays empty (loadAll is a no-op), so DEFAULT_STRATEGIES (9 modes) kicks in
    expect(html).toContain('通用对话')
    expect(html).toContain('ReAct')
    expect(html).toContain('深度思考')
    expect(html).toContain('深度研究')
    expect(html).toContain('技能执行')
    expect(html).toContain('智能体')
    expect(html).toContain('智能体团队')
    expect(html).toContain('云端调度')
    expect(html).toContain('共享层')
  })

  it('does NOT show empty state when 9-mode fallback present', async () => {
    const html = await ssr({ sessionId: 1 })
    expect(html).not.toContain('暂无 9 模式策略数据')
  })

  it('triggers loadAll on mount via watch immediate', async () => {
    await ssr({ sessionId: 42 })
    expect(loadAll).toHaveBeenCalledWith(42)
  })

  it('does not render error banner when lastError is null', async () => {
    const html = await ssr({ sessionId: 1 })
    expect(html).not.toContain('ant-alert-error')
  })
})
