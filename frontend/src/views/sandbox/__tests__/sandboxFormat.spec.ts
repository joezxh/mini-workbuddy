import { describe, it, expect } from 'vitest'
import type { Observation } from '@/api/sandbox'
import { sceneStatusLabel, sceneTagClass, obsSevClass, sevIcon, truncate, escapeHtml, formatFutureSummary } from '../sandboxFormat'

describe('sandboxFormat', () => {
  it('状态标签/样式', () => {
    expect(sceneStatusLabel('running')).toBe('进行中')
    expect(sceneStatusLabel('draft')).toBe('克隆中')
    expect(sceneTagClass('completed')).toBe('g')
    expect(sceneTagClass('running')).toBe('p')
  })
  it('严重度 → class/icon', () => {
    expect(obsSevClass('error')).toBe('err'); expect(obsSevClass('info')).toBe('info'); expect(obsSevClass('warn')).toBe('')
    expect(sevIcon('err')).toBe('⚠'); expect(sevIcon('warn')).toBe('◑'); expect(sevIcon('info')).toBe('◷')
  })
  it('truncate + escapeHtml', () => {
    expect(truncate('abcdefgh', 5)).toBe('abcde…')
    expect(escapeHtml('a<b>&c\nd')).toBe('a&lt;b&gt;&amp;c<br>d')
  })
  it('formatFutureSummary', () => {
    const f = { kind: 'future', tick: null, title: 'x', severity: 'info',
      detail_json: { element_code: 'CE1', target_ref: 'FAC007.capacity', expected_tick: 4, effect_summary: '23.83' } } as Observation
    expect(formatFutureSummary(f)).toContain('CE1 → FAC007.capacity · 预期 T4')
  })
})
