import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import ContextBar from '../components/ContextBar.vue'
import KpiModal from '../components/KpiModal.vue'
import TickBar from '../components/TickBar.vue'
import ScenePanel from '../components/ScenePanel.vue'
import CausalCanvas from '../components/CausalCanvas.vue'
import TracePanel from '../components/TracePanel.vue'
import AdvisorPanel from '../components/AdvisorPanel.vue'
import CompareView from '../components/CompareView.vue'

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

describe('TickBar', () => {
  it('渲染 Step 控件与风险 TOP3', async () => {
    const html = await renderToString(createSSRApp(TickBar, {
      tick: 3, maxTick: 12, scrubTicks: [0,1,2,3,4], cpTicks: new Set([0]),
      canAdvance: true, autoOn: false, health: { label: '关注 B', color: 'var(--amber)' },
      controllability: { label: 'high', color: 'var(--ok)' }, goalCount: 2,
      riskTop3: [{ entity_code: 'SUP006', score: 0.8, name: 'SUP006' }],
    }))
    expect(html).toContain('Step +1'); expect(html).toContain('SUP006'); expect(html).toContain('风险 TOP 3')
  })
})

describe('ScenePanel', () => {
  it('空态与分支对比按钮', async () => {
    const html = await renderToString(createSSRApp(ScenePanel, {
      scenes: [], currentSceneId: null, timeline: [], branches: [], selectedBranchId: null, compareSet: new Set(),
    }))
    expect(html).toContain('暂无推演场景'); expect(html).toContain('对比所选分支')
  })
})

describe('CausalCanvas', () => {
  it('无世界时空渲染 + 视图 Tab', async () => {
    const html = await renderToString(createSSRApp(CausalCanvas, {
      world: null, tick: 0, cview: 'causal', zoomK: 1, selectedEntity: null, detail: null,
    }))
    expect(html).toContain('世界概览'); expect(html).toContain('因果传播'); expect(html).toContain('施加行动')
  })
})

describe('TracePanel/AdvisorPanel/CompareView', () => {
  it('TracePanel trace tab 计数框', async () => {
    const html = await renderToString(createSSRApp(TracePanel, {
      tview: 'trace', goalElements: [], ruleElements: [], traceObs: [], futureItems: [],
      entityCount: 3, relationCount: 0, tick: 2,
    }))
    expect(html).toContain('实体'); expect(html).toContain('传播过程')
  })
  it('AdvisorPanel chat tab 输入框', async () => {
    const html = await renderToString(createSSRApp(AdvisorPanel, {
      aview: 'chat', chat: [], chatInput: '', asking: false, actionLogs: [], recommendations: [], hasScene: true,
    }))
    expect(html).toContain('输入消息'); expect(html).toContain('发送')
  })
  it('CompareView 富差异表', async () => {
    const html = await renderToString(createSSRApp(CompareView, {
      show: true, summary: [{ branch_id: 1, name: '基线', final_tick: 2, final_health: '0.5', health_delta: '0.0000', goal_reached_count: 0, rule_fired_count: 2, action_count: 1 }],
    }))
    expect(html).toContain('基线'); expect(html).toContain('0.0000')
  })
})
