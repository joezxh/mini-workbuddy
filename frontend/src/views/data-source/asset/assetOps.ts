/**
 * 卡片/选择条操作逻辑（AF-03/06/07，纯函数，无网络/无 i18n 依赖）。
 *
 * 收敛三处可单测的决策：批量探活限流（后端 PROBE_BATCH_LIMIT=20，前端提前拦截避免空发请求）、
 * 打标载荷（复用既有 `bindAssetTag` 契约）、探活按钮态（成功/失败/空闲三态文案与配色）。
 */

/** 与后端 `PROBE_BATCH_LIMIT` 对齐的单次批量探活上限 */
export const PROBE_BATCH_LIMIT = 20

/** 批量探活前置校验：超限或空勾选都不应发请求 */
export function checkBatchProbeLimit(ids: number[]): { ok: boolean; count: number; message?: string } {
  const count = ids.length
  if (count === 0) return { ok: false, count, message: '请先勾选要探活的表' }
  if (count > PROBE_BATCH_LIMIT) return { ok: false, count, message: `单次最多 ${PROBE_BATCH_LIMIT} 张` }
  return { ok: true, count }
}

/** 打标载荷：默认表级（asset_kind='table'），op 固定 bind */
export function buildBindTagPayload(
  tagId: number,
  assetIds: number[],
  assetKind = 'table',
): { tag_id: number; asset_kind: string; asset_ids: number[]; op: 'bind' } {
  return { tag_id: tagId, asset_kind: assetKind, asset_ids: assetIds, op: 'bind' }
}

/** 探活按钮态：无结果=空闲「测试」，成功=「测试通过」，失败=「测试失败」 */
export function probeView(
  result: { ok: boolean; code?: string | null } | null | undefined,
): { text: string; cls: 'idle' | 'ok' | 'err' } {
  if (!result) return { text: '测试', cls: 'idle' }
  if (result.ok) return { text: '测试通过', cls: 'ok' }
  return { text: '测试失败', cls: 'err' }
}
