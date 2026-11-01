/**
 * 资产分组树数据映射（AF-01，纯函数）。
 *
 * E40 `/assets/tree` 返回按 `external_type` 分组的 10 节点（空组保留）+ 源节点带 `status`；
 * 本模块把后端结构转成 `a-tree` 需要的 `treeData`：
 * - 组标题 `label（count）`；
 * - 空组渲染一个禁用的「暂无连接」占位（不可选）；
 * - 源节点标题带 `[表数]` 角标，并按探活状态落 `dotClass`（online→绿，其余→`.off` 灰）。
 *
 * 文案经 `tr` 注入（组件传 `t2`，测试传恒等），保持纯函数零 i18n/网络依赖。
 */
export interface AssetTreeNode {
  key: string
  title: string
  selectable: boolean
  disabled?: boolean
  isLeaf?: boolean
  children?: AssetTreeNode[]
  /** 仅源节点：探活状态（online/offline/...），模板据此渲染状态点 */
  status?: string
  /** 仅源节点：状态点样式后缀（'' = 绿，'off' = 灰） */
  dotClass?: string
  /** 仅空组占位 */
  empty?: boolean
}

export function buildAssetTree(
  groups: any[],
  tr: (s: string) => string = (s) => s,
): AssetTreeNode[] {
  const groupNodes: AssetTreeNode[] = (Array.isArray(groups) ? groups : []).map((g) => {
    const kids: AssetTreeNode[] = (g.children || []).map((c: any) => ({
      key: `source:${c.id}`,
      title: `${c.label}${c.count != null ? ` [${c.count}]` : ''}`,
      selectable: true,
      isLeaf: true,
      status: c.status,
      dotClass: c.status === 'online' ? '' : 'off',
    }))
    return {
      key: `type:${g.code}`,
      title: `${g.label}（${g.count ?? 0}）`,
      selectable: false,
      children: kids.length
        ? kids
        : [{ key: `type:${g.code}:empty`, title: tr('暂无连接'), selectable: false, disabled: true, isLeaf: true, empty: true }],
    }
  })
  return [{ key: 'all', title: tr('全部来源'), selectable: true, children: groupNodes }]
}
