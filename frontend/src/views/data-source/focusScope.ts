/**
 * 标准检视面板「下钻」→ 元数据浏览的作用域换算（纯函数，便于单测）。
 *
 * 字段契约对齐后端快照（backend/app/services/dataops/scan_service.py）：
 * - ``meta_table.db_name``：物理库（PG 族三级第一级）；其余族与作用域同值
 * - ``meta_table.database``：作用域（PG 族=schema；其余族=库名）
 */
export interface DrillFocus {
  source_id: number
  db_name?: string
  database?: string
  table: string
}

export interface FocusScope {
  /** 第一级下拉（物理库，重连目标）；非 PG 族无此层级 */
  physicalDb?: string
  /** 快照过滤作用域：PG 族=schema，其余族=库名 */
  scope: string
  table: string
}

/**
 * 下钻落点 → 元数据浏览的两级作用域。
 *
 * PG 族：db_name 是物理库、database 是 schema，缺一不可但可互相兜底；
 * 其余族：db_name 与 database 同值，统一落在 scope 上。
 */
export function resolveFocusScope(focus: DrillFocus, isPgFamily: boolean): FocusScope {
  if (isPgFamily) {
    return {
      physicalDb: focus.db_name || focus.database,
      scope: focus.database || focus.db_name || '',
      table: focus.table,
    }
  }
  return {
    physicalDb: undefined,
    scope: focus.database || focus.db_name || '',
    table: focus.table,
  }
}
