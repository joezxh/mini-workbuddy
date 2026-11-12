import { describe, it, expect } from 'vitest'
import {
  CONSOLE_TAB_KEY,
  SHELL_PATH,
  consoleTabDefinition,
  isMenuActive,
  resolveInitialTab,
  resolveMenuTarget,
} from '../shellTab'

/** 模拟 componentMap 的已注册页签键集合 */
const KEYS = ['dashboard', 'apikey', 'profile', 'agent-team']

describe('resolveInitialTab', () => {
  it('?tab= 命中已注册页签则激活它，未注册/缺省回落控制台页签', () => {
    expect(resolveInitialTab('apikey', KEYS)).toBe('apikey')
    expect(resolveInitialTab('not-registered', KEYS)).toBe(CONSOLE_TAB_KEY)
    expect(resolveInitialTab(undefined, KEYS)).toBe(CONSOLE_TAB_KEY)
    expect(resolveInitialTab('', KEYS)).toBe(CONSOLE_TAB_KEY)
  })

  it('重复 query 参数（数组）取首个再校验，非字符串值一律回落', () => {
    expect(resolveInitialTab(['profile', 'apikey'], KEYS)).toBe('profile')
    expect(resolveInitialTab(['nope'], KEYS)).toBe(CONSOLE_TAB_KEY)
    expect(resolveInitialTab(42, KEYS)).toBe(CONSOLE_TAB_KEY)
  })
})

describe('consoleTabDefinition', () => {
  it('控制台页签恒为 dashboard 且不可关闭', () => {
    const tab = consoleTabDefinition()
    expect(tab.key).toBe(CONSOLE_TAB_KEY)
    expect(tab.closable).toBe(false)
    expect(tab.titleKey).toBe('userMenu.dashboard')
    expect(tab.icon).toBe('DashboardOutlined')
  })
})

describe('resolveMenuTarget', () => {
  it('壳内页面（/admin/<key>）统一转为 /dashboard?tab=<key>', () => {
    expect(SHELL_PATH).toBe('/dashboard')
    expect(resolveMenuTarget('/admin/system-management')).toEqual({
      path: SHELL_PATH,
      query: { tab: 'system-management' },
    })
    expect(resolveMenuTarget('/admin/apikey/')).toEqual({ path: SHELL_PATH, query: { tab: 'apikey' } })
  })

  it('裸 /admin 等于壳首页；更深路径与业务路由保持真实路由', () => {
    expect(resolveMenuTarget('/admin')).toEqual({ path: SHELL_PATH })
    expect(resolveMenuTarget('/admin/agent-team/123')).toEqual({ path: '/admin/agent-team/123' })
    expect(resolveMenuTarget('/wiki')).toEqual({ path: '/wiki' })
  })
})

describe('isMenuActive', () => {
  it('壳内按 tab 命中菜单路径末段', () => {
    expect(isMenuActive('/admin/apikey', SHELL_PATH, 'apikey')).toBe(true)
    expect(isMenuActive('/admin/apikey', SHELL_PATH, 'profile')).toBe(false)
    expect(isMenuActive('/admin/agent-team', SHELL_PATH, 'agent-team')).toBe(true)
  })

  it('无 tab 参数时只有 dashboard 菜单高亮', () => {
    expect(isMenuActive('/admin/dashboard', SHELL_PATH, undefined)).toBe(true)
    expect(isMenuActive('/dashboard', SHELL_PATH, undefined)).toBe(true)
    expect(isMenuActive('/admin/apikey', SHELL_PATH, undefined)).toBe(false)
  })

  it('非壳路由沿用既有的等值/前缀判定', () => {
    expect(isMenuActive('/wiki', '/wiki/article-1')).toBe(true)
    expect(isMenuActive('/wiki', '/meeting')).toBe(false)
    expect(isMenuActive('/admin/agent-team', '/admin/agent-team')).toBe(true)
  })

  it('空路径不高亮', () => {
    expect(isMenuActive('', SHELL_PATH, 'apikey')).toBe(false)
    expect(isMenuActive(undefined, SHELL_PATH, 'apikey')).toBe(false)
  })
})
