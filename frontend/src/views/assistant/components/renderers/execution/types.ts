/**
 * 执行面板内部类型 — ToolRenderer 接口
 * 从 renderers/types/timeline.ts 导入共享数据类型
 */
import type { VNode } from 'vue'
import type { ToolCallPair } from '../types/timeline'

/**
 * 工具渲染器接口 — 渲染器只提供*内容*，共享的 ToolCallRow 控制
 * 折叠壳、状态图标、chevron 和布局。
 */
export interface ToolRenderer {
  /** 获取工具的显示名称 */
  getDisplayName?: (pair: ToolCallPair) => string
  /** 触发行内容（header） */
  renderHeader?: (pair: ToolCallPair) => VNode | string
  /** 可展开内容（body）；返回 null 使行不可展开 */
  renderBody?: (pair: ToolCallPair) => VNode | null
}
