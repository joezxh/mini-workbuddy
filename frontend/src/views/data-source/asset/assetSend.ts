/**
 * 送数回显闭环（AF-08，纯函数，无网络/无 i18n 依赖）。
 *
 * 从 `AssetPickerPanel` 抽出的三处可单测决策：
 * - 打开面板/切换目标本体时，按后端 `getDraftScope` 回显勾选（仅恢复锁定源且命中的表，异源丢弃）；
 * - `removed_stale>0` 时给出一条剔除提示；
 * - 卡片层跨源拦截文案，携带与后端单源终防线一致的 `BUILD_SCOPE_SINGLE_SOURCE` 错误码。
 */

/** 与后端 `app.core.api_error.BUILD_SCOPE_SINGLE_SOURCE` 对齐的前端错误码常量 */
export const BUILD_SCOPE_SINGLE_SOURCE = 'BUILD_SCOPE_SINGLE_SOURCE'

/** 跨源拦截文案（卡片复选框禁用/点击时提示，含错误码便于排障定位） */
export const CROSS_SOURCE_BLOCK_MSG =
  `一个建模作用域仅允许单一数据源（${BUILD_SCOPE_SINGLE_SOURCE}），请先清空勾选`

interface DraftScope {
  source_id?: number
  tables?: string[]
  mode?: string
}

/**
 * 依据 draft_scope 恢复当前页勾选：仅取 `source_id` 锁定且 `table_name` 命中的项。
 * 缺 source_id / 空 tables → 返回空（不猜测恢复）；异源命中项因 source_id 过滤被丢弃。
 */
export function restoreSelection<T extends { table_name: string; source_id: number }>(
  draftScope: DraftScope | null | undefined,
  items: T[],
): T[] {
  const sid = draftScope?.source_id
  const names = draftScope?.tables || []
  if (!sid || !names.length) return []
  const want = new Set(names)
  return items.filter((it) => it.source_id === sid && want.has(it.table_name))
}

/** 失效剔除提示：removed_stale>0 返回文案，否则 null */
export function staleNotice(removedStale?: number | null): string | null {
  if (removedStale && removedStale > 0) return `已从作用域剔除 ${removedStale} 张失效表`
  return null
}
