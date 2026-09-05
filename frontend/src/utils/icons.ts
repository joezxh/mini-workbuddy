// Resolve Ant Design icon components by name.
//
// Menus store the icon as a plain string (`sys_menu.icon`, e.g.
// "DashboardOutlined") so the database never has to import front-end code.
// This module maps that string back onto a component from
// `@ant-design/icons-vue`, falling back to a neutral placeholder.
import * as AntIcons from '@ant-design/icons-vue'
import { h } from 'vue'
import type { Component } from 'vue'

type IconMap = Record<string, Component>

const registry = AntIcons as unknown as IconMap

/** Component rendered for an unknown or missing icon name. */
const FallbackIcon: Component = {
  name: 'RcsFallbackIcon',
  render() {
    return h('span', { class: 'rcs-icon-fallback' })
  },
}

const cache = new Map<string, Component>()

export function resolveIcon(name?: string | null): Component {
  if (!name) return FallbackIcon
  const cached = cache.get(name)
  if (cached) return cached

  const component = registry[name]
  if (component) {
    cache.set(name, component)
    return component
  }

  // Tolerate "dashboard" / "dashboard-outlined" spellings.
  const pascal = name
    .split(/[-_\s]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('')
  for (const suffix of ['Outlined', 'Filled', 'TwoTone', '']) {
    const candidate = registry[pascal + suffix]
    if (candidate) {
      cache.set(name, candidate)
      return candidate
    }
  }
  return FallbackIcon
}

/** Names offered by the menu editor's icon picker. */
export const COMMON_ICONS = [
  'DashboardOutlined', 'RobotOutlined', 'ControlOutlined', 'UnorderedListOutlined',
  'AppstoreOutlined', 'EnvironmentOutlined', 'ShoppingOutlined', 'DeploymentUnitOutlined',
  'FileTextOutlined', 'ClusterOutlined', 'GlobalOutlined', 'FundProjectionScreenOutlined',
  'SettingOutlined', 'UserOutlined', 'SafetyCertificateOutlined', 'MenuOutlined',
  'HistoryOutlined', 'BookOutlined', 'IdcardOutlined', 'DatabaseOutlined',
  'ThunderboltOutlined', 'ApartmentOutlined', 'BellOutlined', 'ToolOutlined',
]
