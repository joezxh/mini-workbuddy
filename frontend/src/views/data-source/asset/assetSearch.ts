/**
 * 检索条 / 新建标签载荷（AF-02/03，纯函数，无网络/无 i18n 依赖）。
 *
 * 修复 [bug]：旧 `AssetSearchBar` 建标签时把 `tag_kind` 硬编码为 `'table'`（后端 CHECK 只允许
 * biz/security/quality/custom）。这里以白名单收敛，非法值回落 `custom`，确保永不发送 `'table'`。
 * 同时把 E28 扩展位（`table_type`/`sort`/`size`）的归一化集中于此，供组件与测试共用。
 */

/** 标签色板（复制原型 COLORS 数组，7 色） */
export const COLORS = ['#3371fc', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2', '#eb2f96']

/** 后端 `onto_asset_tag.tag_kind` 合法枚举（CHECK 约束口径） */
export const TAG_KINDS = ['biz', 'security', 'quality', 'custom']

const SORTS = ['score', 'updated', 'rows']

export interface TagPayload {
  code: string
  name: string
  color: string
  tag_kind: string
}

export function buildTagPayload(f: Partial<TagPayload>): TagPayload {
  const kind = f.tag_kind && TAG_KINDS.includes(f.tag_kind) ? f.tag_kind : 'custom'
  return {
    code: (f.code || '').trim(),
    name: (f.name || '').trim(),
    color: f.color || COLORS[0],
    tag_kind: kind,
  }
}

export interface SearchPayload {
  kw: string
  tag_ids: number[]
  kind: string
  table_type?: string
  sort: string
  size: number
}

export function buildSearchPayload(s: {
  kw?: string
  tag_ids?: number[]
  kind?: string
  table_type?: string
  sort?: string
  size?: number
}): SearchPayload {
  return {
    kw: (s.kw || '').trim(),
    tag_ids: s.tag_ids || [],
    kind: s.kind || 'table',
    // 'all'/空 → 不下发对象类型过滤（后端 pattern 仅接受 BASE TABLE/VIEW）
    table_type: s.table_type && s.table_type !== 'all' ? s.table_type : undefined,
    sort: s.sort && SORTS.includes(s.sort) ? s.sort : 'score',
    size: s.size || 50,
  }
}

/** 关键词是否含 CJK（原型口径：命中则走 LIKE+trgm，非 similarity，前端显「检索降级」徽标） */
export function isCjkQuery(kw: string): boolean {
  return /[\u4e00-\u9fa5]/.test(kw || '')
}
