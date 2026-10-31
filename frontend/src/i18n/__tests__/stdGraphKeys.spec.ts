import { describe, it, expect } from 'vitest'
import zhCN from '../locales/zh-CN'
import zhTW from '../locales/zh-TW'
import enUS from '../locales/en-US'

const NEW_KEYS = [
  'modeFull',
  'modeSubgraph',
  'objectFilterAll',
  'relationFilterAll',
  'depthLabel',
  'nodeLimit',
  'expandFromSeed',
  'seedPickFirst',
  'exportGraph',
  'exported',
  'nodeEdgeCount',
  'legendNodeSize',
  'graphEmptyDesc',
  'objectDetail',
  'relationDetail',
  'adjacentRelations',
  'noAttributes',
  'noAdjacent',
  'noBindings',
  'locateInGraph',
  'statusDraft',
  'statusPublished',
]

const LOCALES: [string, any][] = [
  ['zh-CN', zhCN],
  ['zh-TW', zhTW],
  ['en-US', enUS],
]

describe('kbMgmt.graph 新文案 key', () => {
  it.each(LOCALES)('%s：22 个新 key 齐备且非空', (_name, messages) => {
    const graph = messages?.kbMgmt?.graph || {}
    NEW_KEYS.forEach((key) => {
      expect(graph[key], `${key} 在 ${_name} 缺失`).toBeTypeOf('string')
      expect((graph[key] as string).trim(), `${key} 在 ${_name} 为空`).not.toBe('')
    })
  })

  it('插值占位符三份一致', () => {
    expect(zhCN.kbMgmt.graph.nodeEdgeCount).toContain('{objects}')
    expect(zhTW.kbMgmt.graph.nodeEdgeCount).toContain('{objects}')
    expect(enUS.kbMgmt.graph.nodeEdgeCount).toContain('{objects}')
    expect(enUS.kbMgmt.graph.exported).toContain('{name}')
  })

  it('复用既有 key 未被误删', () => {
    ;['empty', 'selectHint', 'boundTables', 'drill', 'checks', 'noChecks', 'relationType'].forEach((key) => {
      expect((zhCN.kbMgmt.graph as Record<string, string>)[key]).toBeTypeOf('string')
    })
    ;['hit', 'missing', 'conflict'].forEach((key) => {
      expect((zhCN.kbMgmt.overview as Record<string, string>)[key]).toBeTypeOf('string')
    })
  })
})
