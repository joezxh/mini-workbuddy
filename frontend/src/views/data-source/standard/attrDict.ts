/**
 * 属性字典治理（纯函数，便于单测）。
 *
 * 属性标准是全局字典：被物理列、对象标准、关系连接键三类引用。
 * 孤儿 = 三类引用都为 0，删除安全；被引用则删除受限（后端 400 + 可读原因）。
 */
export interface AttrUsage {
  columns: number
  objects: number
  relations: number
}

export interface AttrRow {
  id: number
  code: string
  name: string
  aliases?: string[]
  usage?: AttrUsage | null
}

export const EMPTY_USAGE: AttrUsage = { columns: 0, objects: 0, relations: 0 }

export function usageOf(row: AttrRow): AttrUsage {
  return row.usage || EMPTY_USAGE
}

/** 三类引用皆 0 即孤儿属性 */
export function isOrphan(row: AttrRow): boolean {
  const u = usageOf(row)
  return u.columns + u.objects + u.relations === 0
}

/** 字典列表筛选：孤儿过滤 + 关键字（code / name / aliases 任一命中，忽略大小写） */
export function filterAttributes(
  rows: AttrRow[],
  opts: { onlyOrphan?: boolean; keyword?: string } = {},
): AttrRow[] {
  const keyword = (opts.keyword || '').trim().toLowerCase()
  return rows.filter((row) => {
    if (opts.onlyOrphan && !isOrphan(row)) return false
    if (!keyword) return true
    return [row.code, row.name, ...(row.aliases || [])]
      .join(' ')
      .toLowerCase()
      .includes(keyword)
  })
}
