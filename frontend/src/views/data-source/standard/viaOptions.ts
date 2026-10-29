/**
 * 关系标准「连接键」候选（纯函数，便于单测）。
 *
 * 连接键通过 ``via_attribute_ids`` 引用全局属性标准：候选来自关系两端对象
 * 各自引用的属性，按 standard_id 去重并保留先出现顺序（from 端优先）。
 */
export interface ViaOption {
  value: number
  label: string
  objectCode: string
}

/** 对象详情（getObject 返回值）中参与合并的最小形状 */
export interface ViaSide {
  code?: string
  name?: string
  attributes?: Array<{ standard_id?: number; id?: number; code?: string; name?: string }>
}

export function mergeViaOptions(sides: Array<ViaSide | null | undefined>): ViaOption[] {
  const seen = new Set<number>()
  const out: ViaOption[] = []
  for (const side of sides) {
    if (!side) continue
    const owner = side.code || side.name || ''
    for (const attr of side.attributes || []) {
      const id = Number(attr.standard_id ?? attr.id)
      if (!id || seen.has(id)) continue
      seen.add(id)
      out.push({
        value: id,
        label: owner ? `${owner}·${attr.name || attr.code}（${attr.code}）` : `${attr.name || attr.code}（${attr.code}）`,
        objectCode: owner,
      })
    }
  }
  return out
}
