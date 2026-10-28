/**
 * NL 检索结果的标准化形态：视图与测试共用，避免各处猜测后端字段。
 */
export interface NlFocus {
  /** 命中的对象标准 code（图节点高亮） */
  objectCodes: string[]
  /** 命中的关系标准 code（图边高亮） */
  relationCodes: string[]
  /** 建议聚焦的目录 code（可选） */
  focusCatalogCode: string | null
  summary: string
  /** AI 不可用时的降级标记：仍返回空高亮，不阻断视图 */
  degraded: boolean
}

function toCodes(input: unknown): string[] {
  return Array.isArray(input) ? input.filter((x): x is string => typeof x === 'string' && !!x) : []
}

/** 正常 / 降级 / 异常三种返回体都收敛到这里 */
export function toNlFocus(data: any): NlFocus {
  return {
    objectCodes: toCodes(data?.highlight_object_codes),
    relationCodes: toCodes(data?.highlight_relation_codes),
    focusCatalogCode: typeof data?.focus_catalog_code === 'string' ? data.focus_catalog_code : null,
    summary: typeof data?.summary === 'string' ? data.summary : '',
    degraded: data?.degraded === true,
  }
}
