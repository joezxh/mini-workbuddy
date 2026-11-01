/**
 * 本体错误码 → 文案映射（R3 错误契约，spec §6.1）。
 *
 * 后端仅本体新端点抛 `{code, message, detail?}`（见 app/core/api_error.py）；
 * 既有 47 端点仍是 `{detail}`。前端拦截器**优先按 code 映射**，缺 code 回落 detail，
 * 两套契约共存互不影响。文案已接入 vue-i18n：中文环境用 `ONTOLOGY_ERROR_TEXTS`，
 * 非中文环境优先取 `@/i18n/ontologyLocale` 的 `ONTOLOGY_ERRORS[locale]`（回落 en → 中文）。
 */
import i18n from '@/i18n'
import { ONTOLOGY_ERRORS } from '@/i18n/ontologyLocale'

/** code → 中文文案（与 api_error.py 常量严格一致） */
export const ONTOLOGY_ERROR_TEXTS: Record<string, string> = {
  ONTOLOGY_NOT_FOUND: '本体不存在',
  ONTOLOGY_CODE_DUPLICATED: '本体编码已存在',
  ONTOLOGY_STOPPED: '本体已停止，拒绝该操作',
  ONTOLOGY_HAS_VERSIONS: '本体已有发布版本，不可删除',
  BUILD_SCOPE_EMPTY: '构建作用域为空',
  BUILD_ALREADY_RUNNING: '已有构建任务在运行',
  REVIEW_ITEM_NOT_FOUND: '审阅项不存在',
  PUBLISH_BLOCKED_PENDING_REVIEW: '存在未决候选，发布被门禁阻断',
  PUBLISH_BLOCKED_REGRESSION: '相对上一版存在回归，发布被阻断',
  PUBLISH_BLOCKED_INTEGRITY: '结构完整性校验失败，发布被阻断',
  PUBLISH_BLOCKED_MASK_COVERAGE: '敏感列脱敏覆盖不足，发布被阻断',
  PUBLISH_BLOCKED_UNREVIEWED_SOURCE: '快照含未经人工确认的 LLM 来源，发布被阻断',
  SEMANTIC_UNAVAILABLE: 'AI 语义服务不可用',
  EXPORT_EMPTY: '导出内容为空',
  DRAFT_SCOPE_EMPTY: '作用域为空',
  ASSET_TAG_IN_USE: '标签仍被资产绑定，不可删除',
  TAG_CODE_DUPLICATED: '标签编码已存在',
  PUBLISH_TARGET_NOT_FOUND: '发布登记目标不存在或参数非法',
  ASSISTANT_INTENT_UNSUPPORTED: '助手不支持该 intent',
  ASSISTANT_BUILD_PREVIEW_STALE: '预览已过期或指纹不符，请重新预览后提交',
  ASSISTANT_BUILD_EMPTY: '模型未产出可解析候选',
}

/**
 * 解析后端错误响应体为一句可展示文案。
 * 优先 code 映射（按当前 locale 取中/英/日文案）；
 * 缺 code（既有端点 `{detail}` 契约）回落 detail/message。
 */
export function resolveApiError(data: Record<string, any> | undefined | null): string {
  if (!data) return ''
  const code = typeof data.code === 'string' ? data.code : ''
  if (code) {
    const locale = String(i18n.global.locale.value ?? 'zh-CN')
    const text = locale.startsWith('zh')
      ? ONTOLOGY_ERROR_TEXTS[code]
      : ONTOLOGY_ERRORS[locale]?.[code] ?? ONTOLOGY_ERRORS['en-US']?.[code] ?? ONTOLOGY_ERROR_TEXTS[code]
    if (text) return text
  }
  const detail = data.detail ?? data.message ?? data.msg
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && typeof detail.msg === 'string') return detail.msg
  return ''
}
