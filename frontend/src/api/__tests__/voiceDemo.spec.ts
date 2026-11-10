import { describe, it, expect, vi } from 'vitest'

// 隔离 request 导入链（apiBase 顶层访问 window.fetch，node 环境无 window）——对齐 twin.spec.ts 先例
vi.mock('@/utils/request', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('@/utils/auth', () => ({ getToken: () => 'jwt-x' }))

describe('voiceDemo api', () => {
  it('buildVoiceDemoWsUrl 携带 token query 并转 ws 协议', async () => {
    const { buildVoiceDemoWsUrl } = await import('../voiceDemo')
    const url = buildVoiceDemoWsUrl('jwt-x')
    expect(url.startsWith('ws')).toBe(true)
    expect(url).toContain('/api/v1/voice-demo/ws')
    expect(url).toContain('token=jwt-x')
  })
})
