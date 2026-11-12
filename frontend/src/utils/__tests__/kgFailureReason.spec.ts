import { describe, expect, it } from 'vitest'
import enUS from '@/i18n/locales/en-US'
import jaJP from '@/i18n/locales/ja-JP'
import zhCN from '@/i18n/locales/zh-CN'
import zhTW from '@/i18n/locales/zh-TW'
import {
  KG_FAILURE_CODES,
  isKgFailureCode,
  resolveKgFailure,
} from '../kgFailureReason'

describe('isKgFailureCode', () => {
  it('只认后端声明过的码', () => {
    expect(isKgFailureCode('json_truncated')).toBe(true)
    expect(isKgFailureCode('embedding_unavailable')).toBe(true)
    // 与后端 kg_failure.ALL_CODES 的条目数对齐（改码表就同批改这里与四套语言包）
    expect(KG_FAILURE_CODES.length).toBe(14)
  })

  it('未声明的码、空值与非字符串一律不认（后端加码不能把前端打挂）', () => {
    for (const bad of ['gpu_oom', '', null, undefined, 42, {}]) {
      expect(isKgFailureCode(bad)).toBe(false)
    }
  })
})

describe('resolveKgFailure', () => {
  it('新契约：平级字段优先，文案键按码取', () => {
    const r = resolveKgFailure({
      stage: 'structure',
      error_code: 'model_no_text',
      error: "NoTextResponseError: 模型只返回了思考/工具块（blocks=['thinking']）",
      details: { error_code: 'json_invalid' },
    })
    expect(r.code).toBe('model_no_text')
    expect(r.stage).toBe('structure')
    expect(r.textKey).toBe('kbMgmt.kg.fail.model_no_text')
    expect(r.fixKey).toBe('kbMgmt.kg.fix.model_no_text')
    expect(r.detail).toContain('blocks=')
  })

  it('thinking_overflow 按码取文案（与 model_no_text 分开：修法一个是预算、一个是模型行为）', () => {
    const r = resolveKgFailure({
      stage: 'structure',
      error_code: 'thinking_overflow',
      error: 'ThinkingOverflowError: 思考链占满输出预算，正文为空（thinking_chars=119 output_tokens=64 budget=64）',
    })
    expect(r.code).toBe('thinking_overflow')
    expect(r.textKey).toBe('kbMgmt.kg.fail.thinking_overflow')
    expect(r.fixKey).toBe('kbMgmt.kg.fix.thinking_overflow')
    expect(r.detail).toContain('budget=64')
  })

  it('旧数据只有 details：结构取 error_code，向量取 vector_error_code', () => {
    const structure = resolveKgFailure({
      structure_indexed: false,
      details: { error: 'ValueError: 响应截断修复后无任何实体/关系', error_code: 'json_truncated' },
    })
    expect(structure.code).toBe('json_truncated')
    expect(structure.stage).toBe('structure')
    expect(structure.detail).toContain('截断')

    const vector = resolveKgFailure({
      structure_indexed: true,
      vector_indexed: false,
      details: { vector_error: 'RuntimeError: failed to establish a new connection',
                 vector_error_code: 'embedding_unavailable' },
    })
    expect(vector.stage).toBe('vector')
    expect(vector.code).toBe('embedding_unavailable')
    expect(vector.detail).toContain('connection')
  })

  it('认不得的码回落 unknown，但原始串仍然带出', () => {
    const r = resolveKgFailure({ error_code: 'gpu_oom', error: 'CUDA out of memory' })
    expect(r.code).toBe('unknown')
    expect(r.textKey).toBe('kbMgmt.kg.fail.unknown')
    expect(r.detail).toBe('CUDA out of memory')
  })

  it('更早的数据（向量阶段从没写 details）也只能给 unknown', () => {
    const r = resolveKgFailure({ structure_indexed: true, vector_indexed: false, details: null })
    expect(r.stage).toBe('vector')
    expect(r.code).toBe('unknown')
    expect(r.detail).toBe('')
  })

  it('缺切片时不抛错（组件里 v-for 数据形状不一）', () => {
    expect(resolveKgFailure().code).toBe('unknown')
    expect(resolveKgFailure(null).stage).toBe('vector')
  })
})

/** 码是跨端契约：后端加码必须同批补文案，否则界面直接显键名 */
describe('语言包完备性', () => {
  const locales = { enUS, jaJP, zhCN, zhTW }

  for (const [name, dict] of Object.entries(locales)) {
    it(`${name}：每个码都有 fail 与 fix 文案`, () => {
      const kg = (dict as any).kbMgmt.kg
      for (const code of KG_FAILURE_CODES) {
        expect(kg.fail[code], `${name} fail.${code}`).toBeTruthy()
        expect(kg.fix[code], `${name} fix.${code}`).toBeTruthy()
      }
    })
  }
})
