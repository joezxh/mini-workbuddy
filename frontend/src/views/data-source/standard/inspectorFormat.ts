/**
 * 检视面板的展示映射（纯函数）：状态 / 校验三态 / 绑定表标题。
 *
 * 抽成独立文件与仓内 `attrDict.ts`、`nlFocus.ts` 同一理由：node 环境下的 SSR
 * 拿不到 `await` 后的数据，badge 与文案 key 的映射必须在组件外单独可测。
 * 未知值一律回落（key 返回 null → 组件直接显原值），不编造中文词表。
 */

const STATUS_KEY: Record<string, string> = {
  draft: 'kbMgmt.graph.statusDraft',
  published: 'kbMgmt.graph.statusPublished',
  accepted: 'kbMgmt.graph.statusPublished',
}

export function statusTextKey(status?: string | null): string | null {
  return STATUS_KEY[status || ''] || null
}

export function statusBadgeClass(status?: string | null): string {
  if (status === 'published' || status === 'accepted' || status === 'active') return 'kg-badge--ok'
  if (status === 'draft' || status === 'suggested') return 'kg-badge--warn'
  if (status === 'deprecated' || status === 'rejected') return 'kg-badge--err'
  return ''
}

/** 三态词复用 kbMgmt.overview.hit/missing/conflict（同一套业务词汇，不另起 key） */
const VERDICT_KEY: Record<string, string> = {
  hit: 'kbMgmt.overview.hit',
  missing: 'kbMgmt.overview.missing',
  conflict: 'kbMgmt.overview.conflict',
}

export function verdictTextKey(verdict?: string | null): string | null {
  return VERDICT_KEY[verdict || ''] || null
}

export function verdictBadgeClass(verdict?: string | null): string {
  if (verdict === 'hit') return 'kg-badge--ok'
  if (verdict === 'conflict') return 'kg-badge--warn'
  if (verdict === 'missing') return 'kg-badge--err'
  return ''
}

export function bindingTitle(row: any): string {
  return [row?.db_name, row?.database, row?.table_name].filter(Boolean).join('.')
}
