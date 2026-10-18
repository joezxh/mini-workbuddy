/**
 * 表格导入/预校验的错误文案映射。
 *
 * 后端按 code 返回结构化 detail（缺列 / 多列 / 单元格类型不符），
 * 这里统一映射成可读提示，供「已上传文件」与「测试」两个 tab 复用。
 */

/** 与 vue-i18n 的 `t` 兼容的最小签名（避免把 Composer 泛型带进来） */
export type TranslateFn = (key: string, named?: Record<string, any>) => string

/** 表格列类型 → 本地化标签（错误提示里回显定义的类型） */
function typeLabel(t: TranslateFn, type?: string): string {
  return (
    {
      string: t('kbMgmt.typeString'),
      number: t('kbMgmt.typeNumber'),
      boolean: t('kbMgmt.typeBoolean'),
    }[String(type || '')] ||
    type ||
    ''
  )
}

/** 导入/预校验失败文案：优先解析结构化 detail，其次字符串 detail，最后兜底 */
export function tableImportErrorMessage(e: any, t: TranslateFn): string {
  const detail = e?.response?.data?.detail
  if (detail && typeof detail === 'object' && detail.code) {
    if (detail.code === 'table_schema_mismatch') {
      const parts: string[] = []
      if (detail.missing?.length) {
        parts.push(t('kbMgmt.tableSchemaMissing', { cols: detail.missing.join('、') }))
      }
      if (detail.extra?.length) {
        parts.push(t('kbMgmt.tableSchemaExtra', { cols: detail.extra.join('、') }))
      }
      return parts.join('；') || t('kbMgmt.tableSchemaMismatch')
    }
    if (detail.code === 'table_cell_type_mismatch') {
      return t('kbMgmt.tableSchemaCellType', {
        row: detail.row,
        col: detail.column,
        type: typeLabel(t, detail.expected),
      })
    }
    return detail.message || t('kbMgmt.importFailed')
  }
  return typeof detail === 'string' && detail ? detail : t('kbMgmt.importFailed')
}
