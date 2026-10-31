import { describe, it, expect } from 'vitest'
import {
  bindingTitle,
  statusBadgeClass,
  statusTextKey,
  verdictBadgeClass,
  verdictTextKey,
} from '../inspectorFormat'

describe('inspectorFormat', () => {
  it('对象/关系状态 -> 文案 key 与 badge 类', () => {
    expect(statusTextKey('published')).toBe('kbMgmt.graph.statusPublished')
    expect(statusTextKey('draft')).toBe('kbMgmt.graph.statusDraft')
    expect(statusBadgeClass('published')).toBe('kg-badge--ok')
    expect(statusBadgeClass('draft')).toBe('kg-badge--warn')
    expect(statusBadgeClass('deprecated')).toBe('kg-badge--err')
    // 未知状态不编造文案：key 为 null，组件回落原值
    expect(statusTextKey('weird')).toBeNull()
    expect(statusBadgeClass('weird')).toBe('')
    expect(statusTextKey(null)).toBeNull()
  })

  it('校验三态 -> overview.* 复用 + badge 三色', () => {
    expect(verdictTextKey('hit')).toBe('kbMgmt.overview.hit')
    expect(verdictTextKey('missing')).toBe('kbMgmt.overview.missing')
    expect(verdictTextKey('conflict')).toBe('kbMgmt.overview.conflict')
    expect(verdictBadgeClass('hit')).toBe('kg-badge--ok')
    expect(verdictBadgeClass('conflict')).toBe('kg-badge--warn')
    expect(verdictBadgeClass('missing')).toBe('kg-badge--err')
    expect(verdictBadgeClass(undefined)).toBe('')
  })

  it('绑定表标题：db 层级按需拼接，缺字段不出现孤点', () => {
    expect(bindingTitle({ db_name: 'dw', database: 'ods', table_name: 't_c' })).toBe('dw.ods.t_c')
    expect(bindingTitle({ table_name: 't_c' })).toBe('t_c')
    expect(bindingTitle({ database: 'ods', table_name: 't_c' })).toBe('ods.t_c')
    expect(bindingTitle({})).toBe('')
  })
})
