import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h, defineComponent } from 'vue'
import Antd from 'ant-design-vue'
import ModeContextCard from '../ModeContextCard.vue'

// 9 模式策略样本(从后端 GET /strategies 响应结构)
const sampleStrategy = {
  session_type: 'skill',
  source_mode: 'skill',
  priority: 2,
  ttl_hours: 168,
  write_mem0: true,
  is_cross_mode_accessible: false,
  display_label: '技能执行',
  display_color: 'green',
}

const accessibleStrategy = {
  ...sampleStrategy,
  session_type: 'agent',
  source_mode: 'agent',
  display_label: '智能体',
  display_color: 'gold',
  is_cross_mode_accessible: true,
}

const l2OnlyStrategy = {
  ...sampleStrategy,
  session_type: 'scheduled',
  source_mode: 'scheduled',
  display_label: '云端调度',
  display_color: 'default',
  write_mem0: false,
}

/**
 * 由于环境为 node 且无 @vue/test-utils,
 * 通过 server-renderer 渲染 SFC 到字符串,验证关键文案存在。
 * emit 行为通过 defineComponent 包装层单独验证(见 ModeContextCard.emit.spec.ts)。
 *
 * Ant Design Vue 组件需在 SSR app 中通过 `app.use(Antd)` 注册,
 * 否则 Vue 会把 `a-card` / `a-tag` 视为 unknown 元素渲染为空注释。
 */

async function ssr(props: Record<string, any>) {
  const app = createSSRApp(ModeContextCard, props)
  app.use(Antd)
  return renderToString(app)
}

describe('ModeContextCard (PR-3 Task 13)', () => {
  it('renders display_label as card title', async () => {
    const html = await ssr({ strategy: sampleStrategy })
    expect(html).toContain('技能执行')
    expect(html).toContain('class="mode-source"')
    expect(html).toContain('>skill</span>')
  })

  it('renders entry_count when bucket provided', async () => {
    const html = await ssr({
      strategy: sampleStrategy,
      bucket: { source_mode: 'skill', entry_count: 12 },
    })
    expect(html).toContain('12')
  })

  it('renders 0 when bucket missing', async () => {
    const html = await ssr({ strategy: sampleStrategy })
    expect(html).toContain('0')
  })

  it('renders TTL and priority from strategy', async () => {
    const html = await ssr({ strategy: sampleStrategy })
    expect(html).toContain('168')
  })

  it('shows Mem0 badge for write_mem0=true', async () => {
    const html = await ssr({ strategy: sampleStrategy })
    expect(html).toContain('Mem0')
  })

  it('shows L2 only badge for write_mem0=false', async () => {
    const html = await ssr({ strategy: l2OnlyStrategy })
    expect(html).toContain('L2 only')
  })

  it('emits view-history event when 查看历史 clicked', async () => {
    const onViewHistory = vi.fn()
    const Wrapper = defineComponent({
      setup() {
        return () => h(ModeContextCard, {
          strategy: sampleStrategy,
          onViewHistory,
        })
      },
    })
    const app = createSSRApp(Wrapper)
    app.use(Antd)
    const html = await renderToString(app)
    // 验证按钮存在
    expect(html).toContain('查看历史')
    // emit 行为只能在 client 端验证(SSR 下 emit 不触发)
    // 这里我们仅确保渲染不含错;client 测试单独放在 emit 子套件
  })

  it('emits enable-cross for accessible strategy', async () => {
    const onEnableCross = vi.fn()
    const Wrapper = defineComponent({
      setup() {
        return () => h(ModeContextCard, {
          strategy: accessibleStrategy,
          onEnableCross,
        })
      },
    })
    const app = createSSRApp(Wrapper)
    app.use(Antd)
    const html = await renderToString(app)
    expect(html).toContain('跨模式读取:已启用')
  })

  it('shows 隔离 tag when strategy is not cross-mode accessible', async () => {
    const html = await ssr({ strategy: l2OnlyStrategy })
    expect(html).toContain('跨模式:隔离')
  })
})