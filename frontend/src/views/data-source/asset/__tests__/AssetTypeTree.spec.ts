import { describe, it, expect } from 'vitest'
import { buildAssetTree } from '../assetTree'

/**
 * AF-01 分组树数据映射（纯函数，不触网/不依赖 i18n）：
 * 10 组 external_type 全保留、空组渲染禁用「暂无连接」、源节点按 status 落状态点 class。
 * `tr` 用恒等桩注入，隔离 ontologyText 的全局 i18n 依赖。
 */
const id = (s: string) => s

const GROUPS = [
  { kind: 'type', code: 'rdbms', label: '关系型数据库', count: 0, children: [] },
  { kind: 'type', code: 'warehouse', label: '数仓 / 大数据', count: 3, children: [
    { kind: 'source', id: 7, label: 'CH 集群', source_type: 'clickhouse', external_type: 'warehouse', status: 'online', count: 3 },
  ] },
  { kind: 'type', code: 'graph', label: '图数据库', count: 0, children: [] },
  { kind: 'type', code: 'other', label: '其他', count: 1, children: [
    { kind: 'source', id: 9, label: '未知源', source_type: 'x', external_type: 'other', status: 'offline', count: 1 },
  ] },
]

describe('buildAssetTree（AF-01）', () => {
  it('根为「全部来源」，子节点数等于分组数', () => {
    const tree = buildAssetTree(GROUPS, id)
    expect(tree).toHaveLength(1)
    expect(tree[0].key).toBe('all')
    expect(tree[0].title).toBe('全部来源')
    expect(tree[0].children).toHaveLength(4)
  })

  it('组标题带 label（count），未知桶显式保留', () => {
    const tree = buildAssetTree(GROUPS, id)
    const titles = tree[0].children!.map((g) => g.title)
    expect(titles).toContain('数仓 / 大数据（3）')
    expect(titles).toContain('其他（1）')
  })

  it('空组渲染禁用「暂无连接」占位', () => {
    const tree = buildAssetTree(GROUPS, id)
    const rdbms = tree[0].children!.find((g) => g.key === 'type:rdbms')!
    expect(rdbms.children).toHaveLength(1)
    expect(rdbms.children![0].empty).toBe(true)
    expect(rdbms.children![0].title).toBe('暂无连接')
    expect(rdbms.children![0].disabled).toBe(true)
    expect(rdbms.children![0].selectable).toBe(false)
  })

  it('online 源状态点无 off（绿），非 online 落 off（灰）', () => {
    const tree = buildAssetTree(GROUPS, id)
    const wh = tree[0].children!.find((g) => g.key === 'type:warehouse')!
    const online = wh.children!.find((c) => c.key === 'source:7')!
    expect(online.dotClass).toBe('')
    const other = tree[0].children!.find((g) => g.key === 'type:other')!
    const offline = other.children!.find((c) => c.key === 'source:9')!
    expect(offline.dotClass).toBe('off')
  })

  it('非空组子节点保留源计数角标文本', () => {
    const tree = buildAssetTree(GROUPS, id)
    const wh = tree[0].children!.find((g) => g.key === 'type:warehouse')!
    expect(wh.children![0].title).toBe('CH 集群 [3]')
  })
})
