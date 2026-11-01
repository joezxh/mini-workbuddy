/** 推演沙盘纯格式化（从 SimulationSandbox.vue 抽出）。 */
import type { Observation } from '@/api/sandbox'

export const sceneStatusLabel = (st: string): string =>
  st === 'running' ? '进行中' : st === 'draft' ? '克隆中' : st === 'completed' ? '已完成' : st

export const sceneTagClass = (st: string): string => (st === 'running' ? 'p' : st === 'completed' ? 'g' : 'a')

export const obsSevClass = (sev: string): string => (sev === 'err' || sev === 'error' ? 'err' : sev === 'info' ? 'info' : '')

export const sevIcon = (sev: string): string => (sev === 'err' || sev === 'error' ? '⚠' : sev === 'warn' ? '◑' : '◷')

export const truncate = (s: string, n: number): string => (s.length > n ? s.slice(0, n) + '…' : s)

export const escapeHtml = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')

export function formatFutureSummary(f: Observation): string {
  const d = (f.detail_json || {}) as Record<string, any>
  return `${d.element_code || ''} → ${d.target_ref || ''} · 预期 T${d.expected_tick ?? '?'} · 效应 ${d.effect_summary ?? ''}`
}
