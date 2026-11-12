/**
 * 图谱抽取失败 → 可读原因（与后端 `app/services/kb/kg/kg_failure.py` 的错误码一一对应）。
 *
 * 分工：后端在异常**发生处**就把「为什么失败」归成稳定码（平级返回 `error_code`），
 * 本层只做「码 → i18n 文案键」，因此改措辞只动语言包、不需要发后端；
 * 码是对外契约，只增不改（新增码在前端认不得时一律回落 `unknown`，
 * 仍会把后端原始串显示在悬浮里，不至于丢信息）。
 *
 * 纯函数、不依赖 vue-i18n 实例：调用方拿到 `textKey` / `fixKey` 自己 `t()`。
 */

/** 与 kg_failure.ALL_CODES 严格一致的码集合 */
export const KG_FAILURE_CODES = [
  'model_unavailable',
  'model_no_text',
  'thinking_overflow',
  'json_truncated',
  'json_invalid',
  'ctx_window_exceeded',
  'timeout',
  'auth_failed',
  'endpoint_unreachable',
  'rate_limited',
  'embedding_unavailable',
  'embedding_dim_mismatch',
  'rule_zero_output',
  'unknown',
] as const

export type KgFailureCode = (typeof KG_FAILURE_CODES)[number]

export type KgFailureStage = 'structure' | 'vector'

const KNOWN_CODES = new Set<string>(KG_FAILURE_CODES)

/** 文案键前缀：语言包里的 `kbMgmt.kg.fail.<code>` 与 `kbMgmt.kg.fix.<code>` */
export const KG_FAILURE_TEXT_PREFIX = 'kbMgmt.kg.fail.'
export const KG_FAILURE_FIX_PREFIX = 'kbMgmt.kg.fix.'

export function isKgFailureCode(value: unknown): value is KgFailureCode {
  return typeof value === 'string' && KNOWN_CODES.has(value)
}

/** 失败切片（`/graph/failed-segments` 的 item，含旧版仅有 details 的形状） */
export interface KgFailureSegment {
  stage?: string | null
  error_code?: string | null
  error?: string | null
  structure_indexed?: boolean | null
  vector_indexed?: boolean | null
  details?: Record<string, unknown> | null
}

export interface KgFailureReason {
  code: KgFailureCode
  stage: KgFailureStage
  /** 原因文案键（人话） */
  textKey: string
  /** 处置建议键（该改哪个配置） */
  fixKey: string
  /** 后端原始技术串，只作悬浮/排障展示 */
  detail: string
}

/** 阶段以两个标志位为准：结构是根因，缺省按结构失败处理。 */
function resolveStage(seg: KgFailureSegment): KgFailureStage {
  if (seg.stage === 'structure' || seg.stage === 'vector') return seg.stage
  return seg.structure_indexed === false ? 'structure' : 'vector'
}

function asText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

/**
 * 归一一条失败切片。
 *
 * 兼容三种数据形状：新契约（平级 `stage/error_code/error`）、旧数据只有
 * `details`（结构用 `error/error_code`，向量用 `vector_error/vector_error_code`）、
 * 以及更早的「向量阶段从不写 details」。取不到码时回落 `unknown`。
 */
export function resolveKgFailure(seg?: KgFailureSegment | null): KgFailureReason {
  const stage = resolveStage(seg || {})
  const details = (seg?.details || {}) as Record<string, unknown>
  const vector = stage === 'vector'

  const rawCode = seg?.error_code
    ?? (vector ? details.vector_error_code : details.error_code)
  const code: KgFailureCode = isKgFailureCode(rawCode) ? rawCode : 'unknown'

  return {
    code,
    stage,
    textKey: KG_FAILURE_TEXT_PREFIX + code,
    fixKey: KG_FAILURE_FIX_PREFIX + code,
    detail: seg?.error
      || asText(vector ? details.vector_error : details.error)
      || asText(details.error),
  }
}
