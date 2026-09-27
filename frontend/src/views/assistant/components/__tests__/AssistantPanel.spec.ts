import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

/**
 * AssistantPanel integration (PR-3 Task 18)
 *
 * Full SSR of AssistantPanel.vue requires jsdom (Ant Design Vue drawer needs
 * document.getElementsByTagName). We instead verify:
 *   1. The SFC source contains the 跨模式上下文 button + CrossModeStatsPage modal
 *   2. The required imports/state are present in the file
 *   3. Existing async-task button is preserved
 */
describe('AssistantPanel integration (PR-3 Task 18)', () => {
  const src = readFileSync(
    resolve(__dirname, '../AssistantPanel.vue'),
    'utf-8',
  )

  it('imports CrossModeStatsPage', () => {
    expect(src).toMatch(
      /import\s+CrossModeStatsPage\s+from\s+['"]@\/views\/context\/CrossModeStatsPage\.vue['"]/,
    )
  })

  it('declares crossModeVisible ref', () => {
    expect(src).toMatch(/const\s+crossModeVisible\s*=\s*ref\(false\)/)
  })

  it('renders 跨模式上下文 button in chat-main-header', () => {
    expect(src).toContain('跨模式上下文')
    expect(src).toMatch(/@click=["']crossModeVisible\s*=\s*true["']/)
  })

  it('renders a-modal wired to crossModeVisible', () => {
    expect(src).toMatch(/<a-modal[^>]*v-model:open=["']crossModeVisible["']/)
    expect(src).toContain('CrossModeStatsPage')
  })

  it('passes session-id to CrossModeStatsPage', () => {
    expect(src).toMatch(
      /<CrossModeStatsPage[^>]*:session-id=["']currentSession\.session_id["']/,
    )
  })

  it('preserves existing 我的异步任务 button', () => {
    expect(src).toContain('我的异步任务')
    expect(src).toMatch(/@click=["']openAsyncTaskManage["']/)
  })

  it('preserves DatabaseOutlined icon import', () => {
    expect(src).toMatch(/import\s+\{[^}]*DatabaseOutlined[^}]*\}\s+from\s+['"]@ant-design\/icons-vue['"]/)
  })
})
