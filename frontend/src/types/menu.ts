// 侧边栏菜单节点。
//
// 既兼容后端 `sys_menu` 的行结构（id / parent / type / visible …），也用于
// 本地静态菜单配置。皮肤迁移后侧边栏由 `@/layouts/components/AppSidebar.vue`
// 渲染，节点只需提供 path / icon / 标题。
export interface MenuNode {
  id: number
  /** 默认标题（i18n 缺失时的兜底文案） */
  name: string
  /** 按语言映射的标题，例如 { 'zh-CN': '控制台', 'en-US': 'Dashboard' } */
  i18n?: Partial<Record<string, string>>
  /** vue-i18n 的键，优先于 i18n 映射（本地静态菜单使用） */
  titleKey?: string
  path?: string
  /** 图标名，例如 'DashboardOutlined'，由 @/utils/icons 解析 */
  icon?: string
  type?: number
  sort?: number
  status?: number
  visible?: number
  keepAlive?: number
  alwaysShow?: number
  children?: MenuNode[]
}
