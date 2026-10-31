/**
 * 共享图谱画布的数据契约（spec §3.1）。
 * 图谱知识库与标准中心都用它：颜色与显示名在调用方算好，画布只负责呈现。
 */
export interface CanvasNode {
  id: number
  name: string
  /** 类型码（标准侧 = 对象标准 code，kg 侧 = code || type_code）：图例与命中集据此聚合 */
  code: string
  color: string
  typeLabel: string
}

export interface CanvasEdge {
  id: number
  from: number
  to: number
  /** 边上显示的文字（标准侧为关系标准 name，kg 侧为 relation_type/predicate） */
  label: string
  /** 关系码：NL 命中集按 code 比对，无命中时可不传 */
  code?: string
}

export interface CanvasSelection {
  kind: 'node' | 'edge'
  id: number
}
