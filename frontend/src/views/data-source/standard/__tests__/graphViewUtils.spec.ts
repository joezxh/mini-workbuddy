import { describe, it, expect } from 'vitest'
import {
  applyNodeLimit,
  bfsSubgraph,
  csvEscape,
  degreeMap,
  filterByObjectCode,
  neighborsOf,
  objectFacets,
  relationTypeFacets,
  selectVisibleGraph,
  serializeGraph,
  toCanvasEdges,
  toCanvasNodes,
} from '../graphViewUtils'

const NODES = [
  { id: 1, code: 'OBJ_CUSTOMER', name: '客户' },
  { id: 2, code: 'OBJ_ORDER', name: '订单' },
  { id: 3, code: 'OBJ_WAREHOUSE', name: '仓库' },
  { id: 4, code: 'OBJ_ORDER', name: '退单' },
]
const EDGES = [
  { id: 11, code: 'REL_A', name: '订单属客户', from: 2, to: 1, relation_type: 'N:1' },
  { id: 12, code: 'REL_B', name: '仓库收订单', from: 3, to: 2, relation_type: '1:N' },
  { id: 13, code: 'REL_C', name: '退单属客户', from: 4, to: 1, relation_type: 'N:1' },
]

describe('graphViewUtils', () => {
  it('degreeMap 按边累计两端', () => {
    expect(degreeMap(EDGES)).toEqual({ 1: 2, 2: 2, 3: 1, 4: 1 })
  })

  it('neighborsOf 无向取 1 跳', () => {
    expect([...neighborsOf(2, EDGES)].sort()).toEqual([1, 3])
  })

  it('bfsSubgraph 深度边界：null/0 给空集，1 跳与 3 跳', () => {
    expect(bfsSubgraph(null, EDGES, 1).size).toBe(0)
    expect(bfsSubgraph(999, EDGES, 3).size).toBe(0)
    expect([...bfsSubgraph(2, EDGES, 1)].sort()).toEqual([1, 2, 3])
    expect([...bfsSubgraph(4, EDGES, 3)].sort()).toEqual([1, 2, 3, 4])
    expect([...bfsSubgraph(4, EDGES, 0)].sort()).toEqual([4])
  })

  it('filterByObjectCode：对象本身 + 关联边 + 对端节点', () => {
    const r = filterByObjectCode(NODES, EDGES, 'OBJ_ORDER')
    expect(r.nodes.map((n) => n.id).sort()).toEqual([1, 2, 3, 4])
    expect(r.edges.map((e) => e.id)).toEqual([11, 12, 13])
  })

  it('filterByObjectCode 未命中 code：只剩该 code 为空集', () => {
    expect(filterByObjectCode(NODES, EDGES, 'NO_SUCH').nodes).toEqual([])
  })

  it('applyNodeLimit：度数降序截断 + 丢弃悬空边', () => {
    const r = applyNodeLimit(NODES, EDGES, 2)
    // 度数 2 的节点优先：1 与 2（同度按 id 升序保证稳定）
    expect(r.nodes.map((n) => n.id)).toEqual([1, 2])
    expect(r.edges.map((e) => e.id)).toEqual([11])
    const ids = new Set(r.nodes.map((n) => n.id))
    expect(r.edges.every((e) => ids.has(e.from) && ids.has(e.to))).toBe(true)
  })

  it('applyNodeLimit 上限不小于节点数时原样返回', () => {
    expect(applyNodeLimit(NODES, EDGES, 99)).toEqual({ nodes: NODES, edges: EDGES })
  })

  it('selectVisibleGraph：种子模式未选种子为空集', () => {
    const r = selectVisibleGraph(NODES, EDGES, {
      mode: 'seed',
      seedId: null,
      depth: 2,
      objectCode: '',
      relationType: '',
      limit: 200,
    })
    expect(r).toEqual({ nodes: [], edges: [] })
  })

  it('selectVisibleGraph：基数筛选先于截断，端点缺失的节点被丢弃', () => {
    const r = selectVisibleGraph(NODES, EDGES, {
      mode: 'full',
      seedId: null,
      depth: 2,
      objectCode: '',
      relationType: '1:N',
      limit: 200,
    })
    expect(r.edges.map((e) => e.id)).toEqual([12])
    expect(r.nodes.map((n) => n.id).sort()).toEqual([2, 3])
  })

  it('facets：按计数降序、同计数按 code 字典序，标签带计数', () => {
    // OBJ_ORDER 两个节点（订单 + 退单）计 2，其余各 1
    expect(objectFacets(NODES).map((f) => f.value)).toEqual(['OBJ_ORDER', 'OBJ_CUSTOMER', 'OBJ_WAREHOUSE'])
    expect(objectFacets(NODES)[0].count).toBe(2)
    expect(objectFacets(NODES).find((f) => f.value === 'OBJ_ORDER')?.label).toBe('ORDER（2）')
    expect(relationTypeFacets(EDGES)[0]).toMatchObject({ value: 'N:1', count: 2 })
  })

  it('toCanvasNodes/toCanvasEdges：分色按 code，边标签取 name 回落 code', () => {
    const cn = toCanvasNodes(NODES)
    const co = toCanvasEdges(EDGES)
    expect(cn.every((n) => !!n.code && !!n.color)).toBe(true)
    // OBJ_CUSTOMER 是 graphTheme 登记过的语义名
    expect(cn.find((n) => n.id === 1)?.typeLabel).toBe('客户')
    expect(cn.find((n) => n.id === 2)?.typeLabel).toBe('ORDER')
    expect(co.find((e) => e.id === 11)?.label).toBe('订单属客户')
    expect(co.find((e) => e.id === 11)?.code).toBe('REL_A')
    // 同码同色
    expect(cn.find((n) => n.id === 4)?.color).toBe(cn.find((n) => n.id === 2)?.color)
  })

  it('边无 name 时回落 code', () => {
    const co = toCanvasEdges([{ id: 1, code: 'REL_X', from: 1, to: 2, relation_type: 'N:1' }])
    expect(co[0].label).toBe('REL_X')
  })

  it('csvEscape：逗号/引号/换行加引号，内部引号翻倍', () => {
    expect(csvEscape('a,b')).toBe('"a,b"')
    expect(csvEscape('say"hi"')).toBe('"say""hi"""')
    expect(csvEscape('l1\nl2')).toBe('"l1\nl2"')
    expect(csvEscape(null)).toBe('')
    expect(csvEscape(12)).toBe('12')
  })

  it('serializeGraph：JSON 保结构，CSV 是边表且解析到两端 code', () => {
    const json = JSON.parse(serializeGraph(NODES, EDGES, 'json'))
    expect(json.nodes).toHaveLength(4)
    expect(json.edges[0].code).toBe('REL_A')
    const csv = serializeGraph(NODES, EDGES, 'csv')
    expect(csv.split('\n')[0]).toBe('edge_id,edge_code,edge_name,from_code,to_code,relation_type')
    expect(csv).toContain('订单属客户,OBJ_ORDER,OBJ_CUSTOMER,N:1')
    expect(csv.trim().split('\n')).toHaveLength(4)
  })
})
