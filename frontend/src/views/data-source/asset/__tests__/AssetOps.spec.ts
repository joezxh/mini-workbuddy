import { describe, it, expect } from 'vitest'
import {
  PROBE_BATCH_LIMIT,
  checkBatchProbeLimit,
  buildBindTagPayload,
  probeView,
} from '../assetOps'

/**
 * 卡片/选择条操作逻辑（AF-03/06/07，纯函数，无网络/无 i18n 依赖）。
 * 覆盖三处计划要求：批量探活限流 20、打标载荷、探活按钮态。
 */
describe('checkBatchProbeLimit（批量探活限流 20）', () => {
  it('21 张 → 拒绝并提示"单次最多 20 张"，count 回传实际数', () => {
    const ids = Array.from({ length: 21 }, (_, i) => i + 1)
    const r = checkBatchProbeLimit(ids)
    expect(r.ok).toBe(false)
    expect(r.count).toBe(21)
    expect(r.message).toContain('单次最多')
    expect(r.message).toContain(String(PROBE_BATCH_LIMIT))
  })

  it('恰好 20 张 → 放行，无提示', () => {
    const ids = Array.from({ length: 20 }, (_, i) => i + 1)
    expect(checkBatchProbeLimit(ids)).toEqual({ ok: true, count: 20 })
  })

  it('空勾选 → 拒绝（count=0）', () => {
    expect(checkBatchProbeLimit([]).ok).toBe(false)
  })
})

describe('buildBindTagPayload（打标载荷）', () => {
  it('落 {tag_id, asset_kind:"table", asset_ids:[tid], op:"bind"}', () => {
    expect(buildBindTagPayload(7, [42])).toEqual({
      tag_id: 7, asset_kind: 'table', asset_ids: [42], op: 'bind',
    })
  })

  it('asset_kind 可覆盖（column）', () => {
    expect(buildBindTagPayload(7, [1, 2], 'column').asset_kind).toBe('column')
  })
})

describe('probeView（探活按钮态）', () => {
  it('无结果 → 空闲"测试"', () => {
    expect(probeView(null)).toEqual({ text: '测试', cls: 'idle' })
    expect(probeView(undefined)).toEqual({ text: '测试', cls: 'idle' })
  })

  it('成功 → "测试通过"(ok)', () => {
    expect(probeView({ ok: true, code: null })).toEqual({ text: '测试通过', cls: 'ok' })
  })

  it('失败 → "测试失败"(err)', () => {
    expect(probeView({ ok: false, code: 'SOURCE_UNREACHABLE' })).toEqual({ text: '测试失败', cls: 'err' })
  })
})
