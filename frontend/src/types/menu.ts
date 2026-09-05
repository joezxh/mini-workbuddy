// 侧边栏菜单节点。
//
// 既兼容后端 `sys_menu` 的行结构（id / parent / type / visible …），也用于
// 本地静态菜单配置。皮肤迁移后侧边栏由 `@/layouts/components/AppSidebar.vue`
// 渲染，节点只需提供 path / icon / 标题。
export interface MenuNode {
  id: number | string
  /** 默认标题（i18n 缺失时的兜底文案） */
  name: string
  /** 按语言映射的标题，例如 { 'zh-CN': '控制台', 'en-US': 'Dashboard' } */
  i18n?: Partial<Record<string, string>>
  /** vue-i18n 的键，优先于 i18n 映射（本地静态菜单使用） */
  titleKey?: string
  /** 后端菜单配置的 i18n_key（sys_menu.i18n_key），优先级高于 titleKey */
  i18nKey?: string
  /** 路由路径（点击菜单跳转的目标，建议为绝对路径，如 /admin/dashboard） */
  path?: string
  /** 图标名，例如 'DashboardOutlined'，由 @/utils/icons 解析 */
  icon?: string
  // —— 后端字段兼容 ——
  /** 菜单唯一键，等于 path 末段，与后端 componentMap 对应 */
  menuKey?: string
  /** 权限标识，例如 'console:read' */
  permission?: string
  /** 前端组件路径（后端自带，仅作信息保留，路由仍由前端 router 决定） */
  component?: string
  /** 菜单类型：1=目录 2=菜单 3=按钮 */
  type?: number
  /** 父级菜单 id，顶级为 null */
  parentId?: number | null
  sort?: number
  status?: number
  visible?: number
  keepAlive?: number
  alwaysShow?: number
  children?: MenuNode[]
}
