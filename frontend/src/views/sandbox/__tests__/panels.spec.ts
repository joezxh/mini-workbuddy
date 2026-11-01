import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import ContextBar from '../components/ContextBar.vue'
import KpiModal from '../components/KpiModal.vue'

describe('ContextBar', () => {
  it('渲染来源标签与检查点计数', async () => {
    const html = await renderToString(createSSRApp(ContextBar, {
      sourceLabel: '断供传导 · v1', cloneScopeLabel: '3 实体 / 0 关系',
      tick: 2, maxTick: 12, execMode: 'auto', checkpointCount: 1, hasScene: true,
    }))
    expect(html).toContain('断供传导 · v1')
    expect(html).toContain('检查点 1/5')
    expect(html).not.toContain('Step')  // Step 属 TickBar，ContextBar 不应有
  })
})

describe('KpiModal', () => {
  it('show=false 不渲染内容', async () => {
    const html = await renderToString(createSSRApp(KpiModal, {
      show: false, sceneName: 'X', tick: 1, health: { label: '健康 A', color: 'var(--ok)' },
      controllability: { label: 'high', color: 'var(--ok)' }, entityCount: 3,
      branchName: '基线', observationCount: 0, maxTick: 12,
    }))
    expect(html).not.toContain('场景 KPI')
  })
})
